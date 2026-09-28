"""CLI routes for existing inventory, runtime, native-receipt and record owners."""

from pathlib import Path
import sys


def register(commands, common_output):
    team = commands.add_parser(
        "team",
        help="inspect declared contributions or publish exact team record decisions",
    )
    subs = team.add_subparsers(dest="team_command", required=True)
    for verb in (
        "contributions",
        "propose-role",
        "observe-offboarding",
        "appoint",
        "offboard",
        "assets-plan",
        "assets-retire",
    ):
        selected = subs.add_parser(verb)
        common_output(selected)
        selected.add_argument("--request", type=Path, required=True)
    machine = commands.add_parser(
        "machine",
        help="review declared machine scope or consent to exact owned derived repair",
    )
    subs = machine.add_subparsers(dest="machine_command", required=True)
    for verb in ("review", "plan", "apply", "recover", "platform"):
        p = subs.add_parser(verb)
        common_output(p)
        if verb not in {"recover", "platform"}:
            p.add_argument("--inventory", type=Path, required=True)
        if verb == "plan":
            p.add_argument("--select", action="append", required=True)
        if verb == "apply":
            p.add_argument("--plan", type=Path, required=True)
            p.add_argument("--approve", required=True)
            p.add_argument("--dry-run", action="store_true")
        if verb == "recover":
            p.add_argument("--approve-recovery", action="store_true", required=True)
    campaign = commands.add_parser(
        "campaign",
        help="inspect report-only campaigns or record one exact native response",
    )
    subs = campaign.add_subparsers(dest="campaign_command", required=True)
    status = subs.add_parser("status")
    common_output(status)
    status.add_argument("--client", required=True, choices=["claude", "codex", "muse"])
    status.add_argument("--release")
    status.add_argument("--project")
    report = subs.add_parser("report")
    common_output(report)
    for name in ("event", "native-payload"):
        report.add_argument("--" + name, type=Path, required=True)
    report.add_argument("--id", required=True)
    report.add_argument("--version", required=True, type=int)
    report.add_argument(
        "--outcome",
        required=True,
        choices=["acknowledged", "blocked", "reported-complete", "not-applicable"],
    )
    report.add_argument("--detail", required=True)
    migration = commands.add_parser(
        "project-migrate",
        help="preview and consent to explicit selected-project format migration",
    )
    subs = migration.add_subparsers(dest="migration_command", required=True)
    for verb in ("plan", "apply", "recover", "verify"):
        p = subs.add_parser(verb)
        common_output(p)
        if verb == "plan":
            p.add_argument("--index", required=True, type=Path)
            choice = p.add_mutually_exclusive_group(required=True)
            choice.add_argument("--select", action="append")
            choice.add_argument("--all-declared", action="store_true")
            p.add_argument("--target-format", type=int, required=True)
        else:
            p.add_argument("--plan", type=Path, required=True)
        if verb in ("apply", "recover"):
            p.add_argument("--approve", required=True)
            p.add_argument("--board", required=True, type=Path)
            p.add_argument("--native-payload", required=True, type=Path)
            p.add_argument(
                "--project",
                help="operate only this reviewed project under its real native owner",
            )
        if verb == "apply":
            p.add_argument("--dry-run", action="store_true")


def dispatch(args, state, source_root):
    if args.command == "team":
        pm = (
            Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
        )
        if str(pm) not in sys.path:
            sys.path.insert(0, str(pm))
        import team_records
        import team_contract

        request = team_contract.load_document(args.request)
        if args.team_command in {"assets-plan", "assets-retire"}:
            import team_retirement

            return (
                team_retirement.plan(state, **request)
                if args.team_command == "assets-plan"
                else team_retirement.apply(state, **request)
            )
        return team_records.dispatch(args.team_command, request)
    if args.command not in ("machine", "campaign", "project-migrate"):
        return None
    # Lazy loading keeps ordinary setup/reporting independent of these owners.
    import machine_review as machine
    import record_transaction as records

    if args.command == "machine":
        verb = args.machine_command
        if verb == "platform":
            import runtime_payload
            return runtime_payload.platform_ownership(state.home, state.state_dir)
        if verb == "recover":
            return machine.repair_recover(state, approve_recovery=args.approve_recovery)
        inventory = records.read_request(args.inventory)
        if verb == "review":
            return machine.review(state, inventory, source_root=source_root)
        if verb == "plan":
            return machine.repair_plan(
                state, inventory, args.select, source_root=source_root
            )
        return machine.repair_apply(
            state,
            inventory,
            records.read_request(args.plan),
            approval_digest=args.approve,
            source_root=source_root,
            dry_run=args.dry_run,
        )
    if args.command == "campaign":
        import upgrade_campaigns as campaigns

        if args.campaign_command == "status":
            return campaigns.applicability(
                state, client=args.client, release=args.release, project=args.project
            )
        return campaigns.report(
            state,
            args.event,
            records.read_request(args.native_payload),
            campaign_id=args.id,
            campaign_version=args.version,
            outcome=args.outcome,
            detail=args.detail,
        )
    pm = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
    if str(pm) not in sys.path:
        sys.path.insert(0, str(pm))
    import project_migration as migration

    if args.migration_command == "plan":
        selected = (
            machine.project_ids(records._snapshot(args.index)[0])
            if args.all_declared
            else args.select
        )
        return migration.propose(args.index, selected, target_format=args.target_format)
    plan = records.read_request(args.plan)
    if args.migration_command == "verify":
        return migration.verify(plan)
    kwargs = {
        "approval_digest": args.approve,
        "board": args.board,
        "native_payload": records.read_request(args.native_payload),
    }
    if args.migration_command == "recover":
        return migration.recover(plan, selected_project=args.project, **kwargs)
    return migration.apply(
        plan, dry_run=args.dry_run, selected_project=args.project, **kwargs
    )
