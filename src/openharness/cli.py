"""harness CLI. PRD §9."""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

from openharness import config, employees, extensions, inboxes, policy, restart, state, tick, verify, checkpoint, providers, daemon


def _cmd_restart(args):
    out = restart.run()
    print(out)


def _cmd_tick(args):
    result = tick.run()
    if result["changes"]:
        print(f"Tick: {len(result['changes'])} inbox(es) changed → {', '.join(result['changes'])}")
    else:
        print("Tick: nothing new.")


def _cmd_inbox(args):
    if args.employee:
        content = inboxes.read_inbox(args.employee)
        if not content:
            print(f"(no inbox file for {args.employee})")
        else:
            print(content)
    else:
        lst = inboxes.list_inboxes()
        if not lst:
            print("(no inboxes)")
            return
        for name, info in lst.items():
            print(f"{name:20s}  {info['size_bytes']:8d} bytes  modified {info['last_modified']:.0f}")


def _cmd_send(args):
    msg = sys.stdin.read() if not args.message else args.message
    if not msg.strip():
        print("error: empty message (pipe via stdin or pass --message)", file=sys.stderr)
        sys.exit(2)
    inboxes.write_to_outbox(args.employee, msg)
    state.append(
        sender="cos",
        recipient=args.employee,
        kind="outbox",
        content=msg,
    )
    print(f"Sent to outbox/{args.employee}.md ({len(msg)} chars)")


def _cmd_employee(args):
    if args.subcmd == "list":
        for e in employees.list_employees():
            print(f"{e['name']:20s}  mode={e.get('autonomy_mode', 'tiered'):11s}  {e['path']}")
        return
    if args.subcmd == "install":
        target = employees.install(args.name)
        # Ensure default autonomy mode is set
        emps = config.load_employees()
        for e in emps:
            if e["name"] == args.name and "autonomy_mode" not in e:
                e["autonomy_mode"] = "manual"
        config.save_employees(emps)
        print(f"Installed employee at {target}")
        print(f"Default autonomy mode: manual (use `harness employee set-mode {args.name} tiered` when ready)")
        return
    if args.subcmd == "set-mode":
        valid = {"manual", "tiered", "autonomous"}
        if args.mode not in valid:
            print(f"error: mode must be one of {valid}", file=sys.stderr)
            sys.exit(2)
        emps = config.load_employees()
        found = False
        for e in emps:
            if e["name"] == args.name:
                e["autonomy_mode"] = args.mode
                found = True
        if not found:
            print(f"error: no employee named {args.name}", file=sys.stderr)
            sys.exit(2)
        config.save_employees(emps)
        print(f"Set {args.name} autonomy mode → {args.mode}")
        return


def _cmd_memory(args):
    cfg = config.load()
    path = Path(cfg["_root"]) / cfg["chief_of_staff"]["memory_path"]
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a") as f:
        f.write(f"\n## {stamp}\n\n{args.fact.strip()}\n")
    print(f"Appended to {path}")


def _cmd_state(args):
    if args.subcmd == "search":
        results = state.search(args.query, limit=args.limit)
        for r in results:
            print(f"#{r['id']} [{r['kind']}] {r['sender']}: {r['content'][:120]}")
        return
    if args.subcmd == "metrics":
        # Phase 1.5 — basic metrics
        with state.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            by_kind = conn.execute(
                "SELECT kind, COUNT(*) FROM messages GROUP BY kind ORDER BY 2 DESC"
            ).fetchall()
        print(f"Total messages: {total}")
        print("By kind:")
        for kind, n in by_kind:
            print(f"  {kind:15s} {n}")
        return
    # default: tail
    rows = state.tail(limit=args.limit)
    for r in rows:
        print(f"#{r['id']} [{r['kind']}] {r['sender']}→{r['recipient'] or '*'}: "
              f"{r['content'][:120]}{'...' if len(r['content']) > 120 else ''}")


def _cmd_verify(args):
    result = verify.run()
    if result["ok"]:
        print("OK — workspace integrity check passed.")
    else:
        print("ISSUES:")
        for i in result["issues"]:
            print(f"  - {i}")
        sys.exit(1)
    ext = result["extensions"]
    print(f"Employees registered: {result['employees_registered']}")
    print(f"Extensions — skills: {ext['skills']}, mcps: {ext['mcps']}, templates: {ext['templates']}, vendored: {ext['vendored']}")


def _cmd_extensions(args):
    if args.subcmd == "list":
        print("Skills:")
        for s in extensions.discover_skills():
            print(f"  {s['name']:30s} {s['source']}")
        print("MCP definitions:")
        for m in extensions.discover_mcp_definitions():
            print(f"  {m['name']:30s} {m['source']}")
        print("SOUL templates:")
        for t in extensions.discover_soul_templates():
            print(f"  {t['name']:30s} {t['source']}")
        print("Vendored:")
        for v in extensions.list_vendored():
            print(f"  {v}")
        return
    if args.subcmd == "verify":
        result = extensions.verify()
        if result["ok"]:
            print("OK — all external sources reachable.")
        else:
            print("Missing paths:")
            for m in result["missing"]:
                print(f"  - {m}")
            sys.exit(1)


def _cmd_policy(args):
    if args.subcmd == "check":
        action = policy.Action(
            employee=args.employee,
            kind=args.kind,
            target=args.target,
            amount=args.amount,
            description=args.description or "",
        )
        decision = policy.check(action)
        print(json.dumps({
            "result": decision.result,
            "rule": decision.rule,
            "rationale": decision.rationale,
            "autonomy_mode": decision.autonomy_mode,
        }, indent=2))


def _cmd_provider(args):
    if args.subcmd == "list":
        auth_path = Path(config.load()["_root"]) / "config" / "auth-profiles.json"
        with auth_path.open() as f:
            data = json.load(f)
        print(f"Default profile: {data.get('default_profile')}")
        for name, prof in data.get("profiles", {}).items():
            print(f"  {name:25s} type={prof.get('type')}")
        return
    if args.subcmd == "test":
        try:
            prov = providers.load_default_provider()
        except providers.ProviderError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        resp = prov.call(
            system_prompt="You are a test agent. Respond in one short sentence.",
            user_prompt="Reply with exactly: OpenHarness provider test OK.",
            timeout=60,
        )
        print(f"Response: {resp.text.strip()}")
        print(f"Cost: ${resp.cost_usd:.4f}  Duration: {resp.duration_seconds:.2f}s")


def _cmd_daemon(args):
    daemon.run(
        interval_seconds=args.interval,
        git_sync_enabled=not args.no_git_sync,
        once=args.once,
    )


def _cmd_checkpoint(args):
    if args.subcmd == "list":
        for c in checkpoint.list_in_flight():
            print(f"{c['task_id']:30s} last_step={c['last_step']:20s} saved_at={c['saved_at']:.0f}")
        return
    if args.subcmd == "resume":
        result = checkpoint.resume(args.task_id)
        if result is None:
            print(f"No checkpoint found for task {args.task_id}")
            sys.exit(1)
        step, state_dict = result
        print(f"Last step: {step}")
        print(json.dumps(state_dict, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness", description="OpenHarness CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("restart", help="Run restart protocol; print Chief of Staff briefing").set_defaults(func=_cmd_restart)
    sub.add_parser("tick", help="Run one heartbeat tick").set_defaults(func=_cmd_tick)

    sp = sub.add_parser("inbox", help="List or show employee inbox")
    sp.add_argument("employee", nargs="?")
    sp.set_defaults(func=_cmd_inbox)

    sp = sub.add_parser("send", help="Append a message to outbox/<employee>.md")
    sp.add_argument("employee")
    sp.add_argument("--message", help="Message text (otherwise read from stdin)")
    sp.set_defaults(func=_cmd_send)

    sp = sub.add_parser("employee", help="Manage AI employees")
    esub = sp.add_subparsers(dest="subcmd", required=True)
    esub.add_parser("list")
    p_install = esub.add_parser("install")
    p_install.add_argument("name")
    p_setmode = esub.add_parser("set-mode")
    p_setmode.add_argument("name")
    p_setmode.add_argument("mode", choices=["manual", "tiered", "autonomous"])
    sp.set_defaults(func=_cmd_employee)

    sp = sub.add_parser("memory", help="Append to Chief of Staff MEMORY.md")
    sp.add_argument("subcmd", choices=["append"])
    sp.add_argument("fact")
    sp.set_defaults(func=_cmd_memory)

    sp = sub.add_parser("state", help="Browse chat.db state")
    ssub = sp.add_subparsers(dest="subcmd")
    ssub.add_parser("metrics")
    p_search = ssub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=20)
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=_cmd_state)

    sub.add_parser("verify", help="Workspace integrity check").set_defaults(func=_cmd_verify)

    sp = sub.add_parser("extensions", help="External-source discovery")
    xsub = sp.add_subparsers(dest="subcmd", required=True)
    xsub.add_parser("list")
    xsub.add_parser("verify")
    sp.set_defaults(func=_cmd_extensions)

    sp = sub.add_parser("policy", help="Policy engine")
    psub = sp.add_subparsers(dest="subcmd", required=True)
    p_check = psub.add_parser("check")
    p_check.add_argument("--employee", required=True)
    p_check.add_argument("--kind", required=True)
    p_check.add_argument("--target", required=True)
    p_check.add_argument("--amount", type=float, default=0.0)
    p_check.add_argument("--description", default="")
    sp.set_defaults(func=_cmd_policy)

    sp = sub.add_parser("provider", help="LLM provider management")
    psub2 = sp.add_subparsers(dest="subcmd", required=True)
    psub2.add_parser("list")
    psub2.add_parser("test")
    sp.set_defaults(func=_cmd_provider)

    sp = sub.add_parser("daemon", help="Run the scheduler / agent loop")
    sp.add_argument("--interval", type=int, default=60, help="Seconds between scheduler ticks (default 60)")
    sp.add_argument("--no-git-sync", action="store_true", help="Skip git commit+push after each cycle")
    sp.add_argument("--once", action="store_true", help="Run a single cycle and exit (for testing)")
    sp.set_defaults(func=_cmd_daemon)

    sp = sub.add_parser("checkpoint", help="Task checkpoints")
    csub = sp.add_subparsers(dest="subcmd", required=True)
    csub.add_parser("list")
    p_resume = csub.add_parser("resume")
    p_resume.add_argument("task_id")
    sp.set_defaults(func=_cmd_checkpoint)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
