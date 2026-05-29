"""harness CLI. PRD §9."""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

from openharness import (config, employees, extensions, inboxes, policy, restart,
                          state, tick, verify, checkpoint, providers, daemon,
                          reflection, memory, cron, skills, hooks)


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


def _cmd_reflect(args):
    result = reflection.reflect(args.employee, since_hours=args.since_hours,
                                 dry_run=args.dry_run)
    print(f"Employee: {result['employee']}")
    print(f"Window:   {result['since_hours']}h")
    print(f"Reviewed: {result['rows_reviewed']} chat rows, "
          f"{result['decisions_reviewed']} decisions")
    print(f"Cost:     ${result['cost_usd']:.4f}  "
          f"Duration: {result.get('duration_seconds', 0):.2f}s")
    print(f"Appended to memory: {result['appended_to_memory']}")
    print()
    print("=== Findings ===")
    print(result["findings_text"])


def _cmd_memory(args):
    if args.subcmd == "add":
        row_id = memory.add(args.employee, args.content,
                            layer=args.layer, tag=args.tag)
        print(f"Appended to {args.employee}'s MEMORY.md (chat.db row #{row_id})")
        return
    if args.subcmd == "tail":
        print(memory.tail(args.employee, n=args.n))
        return
    if args.subcmd == "search":
        results = memory.search(args.employee, args.query, limit=args.limit)
        for r in results:
            print(f"#{r['id']} [{r['kind']}] {r['sender']}: {r['content'][:150]}")
        return
    if args.subcmd == "capacity":
        cap = memory.capacity(args.employee)
        print(json.dumps(cap, indent=2))
        return


def _cmd_cron(args):
    if args.subcmd == "list":
        for j in cron.list_jobs():
            print(f"{j['id']:14s} {'on' if j.get('enabled') else 'off':3s}  "
                  f"{j['schedule']:30s} {j['target']}")
        return
    if args.subcmd == "add":
        kwargs_dict = json.loads(args.args) if args.args else {}
        j = cron.add(schedule=args.schedule, target=args.target, args=kwargs_dict)
        print(f"Added cron job {j['id']}")
        return
    if args.subcmd == "remove":
        ok = cron.remove(args.job_id)
        print("removed" if ok else "not found")
        sys.exit(0 if ok else 1)
    if args.subcmd == "enable":
        ok = cron.enable(args.job_id, True)
        print("enabled" if ok else "not found")
        sys.exit(0 if ok else 1)
    if args.subcmd == "disable":
        ok = cron.enable(args.job_id, False)
        print("disabled" if ok else "not found")
        sys.exit(0 if ok else 1)
    if args.subcmd == "run":
        for j in cron.list_jobs():
            if j["id"] == args.job_id:
                result = cron.run_job(j)
                if result.get("ok"):
                    cron.mark_ran(args.job_id)
                print(json.dumps(result, indent=2, default=str))
                return
        print(f"job not found: {args.job_id}", file=sys.stderr)
        sys.exit(1)
    if args.subcmd == "due":
        for j in cron.due_now():
            print(f"{j['id']:14s} {j['schedule']:30s} {j['target']}")
        return


def _cmd_skill(args):
    if args.subcmd == "list":
        for s in skills.list_skills():
            fm = s.get("frontmatter") or {}
            desc = fm.get("description", "")[:80]
            print(f"{s['name']:30s} {desc}")
        return
    if args.subcmd == "show":
        s = skills.get_skill(args.name)
        if s is None:
            print(f"unknown skill: {args.name}", file=sys.stderr); sys.exit(1)
        print(json.dumps(s, indent=2, default=str))
        return
    if args.subcmd == "run":
        kwargs = json.loads(args.args) if args.args else {}
        try:
            result = skills.run(args.name, runtime_key=args.runtime, **kwargs)
            print(json.dumps(result, indent=2, default=str))
        except skills.SkillError as e:
            print(f"error: {e}", file=sys.stderr); sys.exit(1)


def _cmd_hooks(args):
    if args.subcmd == "list":
        print(json.dumps(hooks.registered(), indent=2))
        return


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

    sp = sub.add_parser("reflect", help="Run self-improvement reflection on an employee")
    sp.add_argument("employee")
    sp.add_argument("--since-hours", type=int, default=168, help="Window in hours (default 168 = 7 days)")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=_cmd_reflect)

    sp = sub.add_parser("memory", help="Memory tool: add / tail / search / capacity")
    msub = sp.add_subparsers(dest="subcmd", required=True)
    p_add = msub.add_parser("add"); p_add.add_argument("employee")
    p_add.add_argument("content")
    p_add.add_argument("--layer", choices=["episodic", "semantic", "procedural"],
                       default="episodic")
    p_add.add_argument("--tag")
    p_tail = msub.add_parser("tail"); p_tail.add_argument("employee")
    p_tail.add_argument("--n", type=int, default=30)
    p_search = msub.add_parser("search"); p_search.add_argument("employee")
    p_search.add_argument("query"); p_search.add_argument("--limit", type=int, default=20)
    p_cap = msub.add_parser("capacity"); p_cap.add_argument("employee")
    sp.set_defaults(func=_cmd_memory)

    sp = sub.add_parser("cron", help="First-class scheduled jobs")
    csub = sp.add_subparsers(dest="subcmd", required=True)
    csub.add_parser("list")
    p_add = csub.add_parser("add")
    p_add.add_argument("--schedule", required=True,
                       help="e.g. 'every 30m', 'daily 06:00', 'weekly sunday 18:00', 'monthly day 1'")
    p_add.add_argument("--target", required=True,
                       help="e.g. 'harness:reflect:bookie' or 'employee:bookie:run_self_check'")
    p_add.add_argument("--args", help="JSON dict passed to target function")
    p_rm = csub.add_parser("remove"); p_rm.add_argument("job_id")
    p_en = csub.add_parser("enable"); p_en.add_argument("job_id")
    p_dis = csub.add_parser("disable"); p_dis.add_argument("job_id")
    p_run = csub.add_parser("run"); p_run.add_argument("job_id")
    csub.add_parser("due")
    sp.set_defaults(func=_cmd_cron)

    sp = sub.add_parser("skill", help="Skill registry: list / show / run")
    ssub = sp.add_subparsers(dest="subcmd", required=True)
    ssub.add_parser("list")
    p_show = ssub.add_parser("show"); p_show.add_argument("name")
    p_run = ssub.add_parser("run"); p_run.add_argument("name")
    p_run.add_argument("--runtime", default="bookie", help="frontmatter metadata key")
    p_run.add_argument("--args", help="JSON dict of kwargs")
    sp.set_defaults(func=_cmd_skill)

    sp = sub.add_parser("hooks", help="List registered hook handlers")
    sp.add_argument("subcmd", choices=["list"])
    sp.set_defaults(func=_cmd_hooks)

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
