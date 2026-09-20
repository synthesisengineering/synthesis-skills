#!/usr/bin/env python3
"""One-command fleet enrollment for a new Mac.

``synthesis fleet join`` asks for what it cannot discover and sets the
rest up itself: home, label (hostname), skill source (this verified
release), knowledge repo (GitHub discovery or one question), workspace,
repos manifest, and role (founding primary vs joining secondary follows
from whether the knowledge repo already holds a fleet). It clones the
knowledge repo when needed, runs the idempotent bootstrap with live
progress, and publishes this Mac's enrollment back so the fleet
converges. Every flag (``--kb``, ``--label``, ``--role``,
``--workspace``) is an override for the interactive answer.

A rerun after any failure or interrupt resumes safely; finished steps
report ``noop`` instead of redoing work.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

GIT_TIMEOUT_SECONDS = 300
GH_TIMEOUT_SECONDS = 60
ONBOARD_ONE_LINER = (
    "curl -fsSL https://raw.githubusercontent.com/"
    "synthesisengineering/synthesis-skills/stable/onboard.sh | sh"
)

WHERE_TO_FIND_KB = (
    "Find it under your repositories on github.com; it looks like "
    "https://github.com/<you>/ai-knowledge-<name>.git"
)


class FleetJoinError(ValueError):
    """A join that cannot proceed, with the remedy in the message."""


def _run_git(args: list[str], cwd: Path | None = None):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )


def _run_gh(args: list[str]):
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        timeout=GH_TIMEOUT_SECONDS,
        check=False,
    )


def _prompt_stream():
    """stdin when it is a terminal, else the controlling terminal."""
    if sys.stdin.isatty():
        return sys.stdin, False
    try:
        return open("/dev/tty", "r", encoding="utf-8"), True
    except OSError:
        return None, False


def terminal_available() -> bool:
    """True when a question can reach a human (pipe-safe via /dev/tty)."""
    stream, close = _prompt_stream()
    if stream is None:
        return False
    if close:
        stream.close()
    return True


def _read_answer(display: str, hint: str) -> str:
    stream, close = _prompt_stream()
    if stream is None:  # pragma: no cover - guarded by terminal_available
        raise FleetJoinError(
            f"cannot ask questions (not interactive); pass {hint}"
        )
    print(display, end="", flush=True)
    try:
        value = stream.readline()
    finally:
        if close:
            stream.close()
    if value == "":
        raise FleetJoinError(f"no answer given; pass {hint}")
    return value.strip()


def _require_prompt(hint: str, can_prompt: bool) -> None:
    if not can_prompt:
        raise FleetJoinError(
            f"cannot ask questions (not interactive); pass {hint}"
        )


def prompt_text(
    question: str, hint: str, *, can_prompt: bool, default: str | None = None
) -> str:
    """Ask one free-text question; the hint names the flag alternative."""
    _require_prompt(hint, can_prompt)
    suffix = f" [{default}]" if default else ""
    answer = _read_answer(f"{question}{suffix}: ", hint)
    if not answer and default is not None:
        return default
    if not answer:
        raise FleetJoinError(f"an answer is required; or pass {hint}")
    return answer


def prompt_choice(
    question: str, options: list[str], hint: str, *,
    can_prompt: bool, default: int | None = None,
) -> str:
    """Ask one numbered question over ``options``; return the chosen one.

    ``default`` is the 1-based recommended option taken on an empty
    answer; without it an empty answer is refused.
    """
    _require_prompt(hint, can_prompt)
    if default is not None and not 1 <= default <= len(options):
        raise FleetJoinError(f"recommended choice {default} is out of range")
    print(question, flush=True)
    for position, option in enumerate(options, start=1):
        marker = " (recommended)" if position == default else ""
        print(f"  {position}. {option}{marker}", flush=True)
    if default is None:
        display = f"Choice [1-{len(options)}]: "
    else:
        display = f"Choice [1-{len(options)}, recommended {default}]: "
    answer = _read_answer(display, hint)
    if not answer and default is not None:
        return options[default - 1]
    if not answer.isdigit() or not 1 <= int(answer) <= len(options):
        raise FleetJoinError(
            f"choice must be 1-{len(options)}; or pass {hint}"
        )
    return options[int(answer) - 1]


def prompt_confirm(
    question: str, *, default: bool, can_prompt: bool, hint: str,
) -> bool:
    """Ask one yes/no question; the hint guides automation past it."""
    _require_prompt(hint, can_prompt)
    suffix = "Y/n" if default else "y/N"
    answer = _read_answer(f"{question} [{suffix}]: ", hint)
    if not answer:
        return default
    if answer.lower() in ("y", "yes"):
        return True
    if answer.lower() in ("n", "no"):
        return False
    raise FleetJoinError(f"answer y or n ({hint})")


def gh_kb_remotes(*, gh_runner=None) -> tuple[str, list[str]]:
    """GitHub discovery of knowledge repos.

    Returns (status, remotes) where status is ``ok``, ``no-gh`` (the
    CLI is missing or unusable), or ``auth-needed`` (installed but the
    list call failed, almost always sign-in).
    """
    runner = gh_runner or _run_gh
    try:
        completed = runner(["repo", "list", "--json", "url", "--limit", "100"])
    except (OSError, subprocess.SubprocessError):
        return ("no-gh", [])
    if completed.returncode != 0:
        return ("auth-needed", [])
    try:
        entries = json.loads(completed.stdout or "[]")
    except ValueError:
        return ("ok", [])
    if not isinstance(entries, list):
        return ("ok", [])
    remotes = [
        str(entry["url"])
        for entry in entries
        if isinstance(entry, dict) and "ai-knowledge-" in str(entry.get("url", ""))
    ]
    return ("ok", remotes)


def gh_auth_login(auth_runner=None) -> bool:
    """Run the interactive GitHub sign-in; True when it succeeds."""
    if auth_runner is None:
        def auth_runner():
            return subprocess.run(["gh", "auth", "login"], check=False)

    try:
        completed = auth_runner()
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def resolve_kb_interactive(
    workspace: str | None,
    *,
    gh_runner=None,
    auth_runner=None,
    announce=None,
    can_prompt: bool = True,
) -> tuple[str, str | None]:
    """Find the knowledge remote: GitHub discovery, else one question."""
    tell = announce or (lambda line: print(line, flush=True))
    status, remotes = gh_kb_remotes(gh_runner=gh_runner)
    if status == "auth-needed" and can_prompt:
        tell("GitHub sign-in is needed; starting it now")
        if gh_auth_login(auth_runner=auth_runner):
            status, remotes = gh_kb_remotes(gh_runner=gh_runner)
    if status == "ok" and len(remotes) == 1:
        tell(f"found knowledge repo {remotes[0]}")
        return remotes[0], workspace or workspace_from_remote(remotes[0])
    if status == "ok" and len(remotes) > 1:
        choice = prompt_choice(
            "Which knowledge repo holds this fleet?", remotes,
            "--kb <url-or-path>", can_prompt=can_prompt,
        )
        return choice, workspace or workspace_from_remote(choice)
    tell(WHERE_TO_FIND_KB)
    url = prompt_text(
        "Knowledge repo URL", "--kb <url-or-path>", can_prompt=can_prompt
    )
    return url, workspace or workspace_from_remote(url)


def setup_present(home: Path) -> bool:
    """True when `synthesis setup` has converged under this home."""
    try:
        import system_contract

        state = system_contract.SystemState(
            home=Path(home).expanduser()
        )
        return state.read_desired() is not None
    except Exception:
        return False


def _run_setup_inline() -> int:
    """Run the release's own setup with full defaults, in-process."""
    import synthesis_cli

    return synthesis_cli.main(["setup"])


def ensure_setup(
    home: Path,
    *,
    setup_check=None,
    setup_runner=None,
    announce=None,
    can_prompt: bool = True,
) -> None:
    """Set the Mac up inline when setup never ran; fail only headless.

    One command must be enough: a missing installation runs the guided
    setup first (answering its questions), then the join continues.
    Only a run with no terminal at all refuses, naming the setup-first
    remedy for automation.
    """
    tell = announce or (lambda line: print(line, flush=True))
    present = (
        setup_check(home) if setup_check is not None
        else setup_present(home)
    )
    if present:
        return
    if not can_prompt:
        if shutil.which("synthesis") is None:
            remedy = (
                "run the installer first:\n"
                f"  {ONBOARD_ONE_LINER}\n"
                "then rerun: synthesis fleet join"
            )
        else:
            remedy = (
                "run synthesis setup first (add --answers for "
                "automation), then rerun: synthesis fleet join"
            )
        raise FleetJoinError(
            "synthesis isn't set up on this Mac yet and this run "
            f"cannot ask questions — {remedy}"
        )
    tell("synthesis isn't set up yet — setting it up now (answer its "
         "questions first, then the join continues)")
    run = setup_runner or _run_setup_inline
    try:
        code = run()
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        raise FleetJoinError(f"setup failed: {exc}") from exc
    if code != 0:
        raise FleetJoinError(
            f"setup failed (exit {code}); fix it and rerun the same command"
        )


def live_label_holders(document: dict, label: str) -> list[str]:
    """Live machine-ids holding ``label`` in a registry document."""
    machines = document.get("machines", {})
    if not isinstance(machines, dict):
        return []
    return [
        machine_id
        for machine_id, entry in machines.items()
        if isinstance(entry, dict)
        and entry.get("retired_at") is None
        and entry.get("label") == label
    ]


def suggest_label(document: dict, label: str) -> str:
    """First free ``label``, ``label-2``, ``label-3``, ... among live."""
    candidate = label
    suffix = 2
    while live_label_holders(document, candidate):
        candidate = f"{label}-{suffix}"
        suffix += 1
    return candidate


def local_machine_id(home: Path) -> str | None:
    """This Mac's minted id, or None when it never minted (or is broken)."""
    path = Path(home).expanduser() / ".synthesis" / "fleet" / "machine-id"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        import uuid as uuid_module

        parsed = uuid_module.UUID(value, version=4)
    except (ValueError, AttributeError, TypeError):
        return None
    if str(parsed) != value.lower():
        return None
    return value


def local_registry(home: Path) -> dict | None:
    """This Mac's registry document, or None when absent/unreadable."""
    path = Path(home).expanduser() / ".synthesis" / "fleet" / "machines.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def resolve_label(
    document: dict | None,
    label: str,
    own_id: str | None,
    *,
    can_prompt: bool,
) -> str:
    """A label this Mac may enroll under; ask when it collides.

    Retired holders never block (their labels are reusable). A live
    other holder prompts for a distinct label with the first free
    suggestion as the default; headless runs name ``--label`` instead.
    """
    if document is None:
        return label
    rivals = [
        holder for holder in live_label_holders(document, label)
        if holder != own_id
    ]
    if not rivals:
        return label
    suggestion = suggest_label(document, label)
    if not can_prompt:
        raise FleetJoinError(
            f"label '{label}' is already held by live machine {rivals[0]}; "
            "rerun with a distinct --label"
        )
    return prompt_text(
        f"Another Mac already uses '{label}' — label for this Mac",
        "--label NAME", can_prompt=can_prompt, default=suggestion,
    )


def reconcile_rename(
    home: Path,
    kb_dir: Path,
    role: str,
    engine,
    *,
    announce=None,
    can_prompt: bool = True,
    git_runner=None,
) -> str | None:
    """Offer a relabel when an auto-labeled Mac was renamed; a note or None.

    Only auto-labeled entries with a recorded hostname participate: an
    explicit label is the owner's words and never touched, and entries
    without provenance predate this tracking. A contested new name
    keeps the old label with an explanation; otherwise the human
    decides (keeping wins ties, so DHCP flaps never churn the fleet).
    """
    tell = announce or (lambda line: print(line, flush=True))
    current = default_label()
    own_id = local_machine_id(home)
    document = local_registry(home)
    if own_id is None or document is None:
        return None
    machines = document.get("machines", {})
    entry = machines.get(own_id) if isinstance(machines, dict) else None
    if not isinstance(entry, dict):
        return None
    if entry.get("label_source") != "auto":
        return None
    recorded = entry.get("hostname")
    if not recorded or recorded == current:
        return None
    old_label = entry.get("label", recorded)
    rivals = [
        holder for holder in live_label_holders(document, current)
        if holder != own_id
    ]
    if rivals:
        return (
            f"this Mac was renamed from '{recorded}' to '{current}', but "
            f"'{current}' is held by live machine {rivals[0]}; keeping "
            f"the label '{old_label}'"
        )
    if not can_prompt:
        return (
            f"this Mac was renamed from '{recorded}' to '{current}'; "
            f"keeping the label '{old_label}' (rerun with --label to change)"
        )
    try:
        agreed = prompt_confirm(
            f"This Mac was renamed from '{recorded}' to '{current}' — "
            f"update its fleet label from '{old_label}'?",
            default=False, can_prompt=can_prompt,
            hint="answer n to keep the label",
        )
    except FleetJoinError as exc:
        return (
            f"rename question skipped ({exc}); keeping the label "
            f"'{old_label}'"
        )
    if not agreed:
        tell(f"keeping the fleet label '{old_label}'")
        return None
    relabeled = engine.step_enroll(
        Path(home).expanduser(), label=current, role=entry.get("role", role),
        fleet_registry=None, hostname=current, label_source="auto",
    )
    if relabeled.status != "done":
        return f"relabel refused: {relabeled.detail}"
    publish_kwargs: dict = {}
    if git_runner is not None:
        publish_kwargs["git_runner"] = git_runner
    published = engine.step_publish(
        Path(home).expanduser(), own_id, label=current,
        role=entry.get("role", role), kb_repo=Path(kb_dir),
        **publish_kwargs,
    )
    if published.status == "fail":
        return f"relabel kept locally but not published: {published.detail}"
    return f"fleet label updated from '{old_label}' to '{current}'"


def resolve_role(
    explicit: str | None, registry: Path, announce=None
) -> str:
    """The role follows from shared state: found or join, never asked.

    An explicit ``--role`` still wins; a contradicting choice fails
    closed downstream (secondary without a fleet, primary against one).
    """
    tell = announce or (lambda line: print(line, flush=True))
    if explicit:
        return explicit
    if registry.is_file():
        try:
            document = json.loads(registry.read_text(encoding="utf-8"))
            count = len(document.get("machines", {}))
            tell(f"found a fleet of {count} machine(s); joining as secondary")
        except (OSError, ValueError, AttributeError):
            tell("found a fleet; joining as secondary")
        return "secondary"
    tell("no fleet found in this knowledge repo; founding one as primary")
    return "primary"


def looks_like_remote(value: str) -> bool:
    """True when ``value`` is a remote URL, not a local path."""
    text = value.strip()
    if "://" in text or text.startswith("git@"):
        return True
    if text.endswith(".git"):
        return True
    head, _, _ = text.partition("/")
    return ":" in head and not Path(text).exists()


def normalize_remote(value: str) -> str:
    """Canonical remote form for origin comparison."""
    text = value.strip().rstrip("/")
    if text.endswith(".git"):
        text = text[: -len(".git")]
    return text.rstrip("/")


def workspace_from_remote(remote: str) -> str | None:
    """Derive the workspace from a knowledge remote name, if conventional."""
    stem = remote.strip().rstrip("/").rsplit("/", 1)[-1]
    if stem.endswith(".git"):
        stem = stem[: -len(".git")]
    prefix = "ai-knowledge-"
    if stem.startswith(prefix) and len(stem) > len(prefix):
        return stem[len(prefix):]
    return None


def workspace_from_kb_path(path: Path) -> str | None:
    """Derive the workspace from a knowledge checkout path, if possible."""
    parts = Path(path).expanduser().parts
    if "workspaces" in parts:
        position = parts.index("workspaces")
        if position + 1 < len(parts):
            return parts[position + 1]
    name = Path(path).name
    prefix = "ai-knowledge-"
    if name.startswith(prefix) and len(name) > len(prefix):
        return name[len(prefix):]
    return None


def clone_target_for(home: Path, workspace: str, remote: str) -> Path:
    """Conventional checkout path for a cloned knowledge remote."""
    stem = remote.strip().rstrip("/").rsplit("/", 1)[-1]
    if stem.endswith(".git"):
        stem = stem[: -len(".git")]
    return Path(home).expanduser() / "workspaces" / workspace / stem


def discover_manifest(
    kb_dir: Path,
    workspace: str | None,
    *,
    allow_empty: bool = False,
    choose=None,
) -> tuple[Path | None, str | None]:
    """Resolve (manifest, workspace); derive the workspace when unambiguous.

    ``allow_empty`` covers founding a fleet in a fresh knowledge repo:
    no manifest yet means no repos to clone, not an error. ``choose``
    answers the which-workspace question interactively; without it an
    ambiguous choice names ``--workspace`` and refuses.
    """
    fleet_dir = Path(kb_dir) / "fleet"
    if workspace:
        candidate = fleet_dir / f"repos.{workspace}.json"
        if not candidate.is_file():
            if allow_empty and not list(fleet_dir.glob("repos.*.json")):
                return None, workspace
            available = sorted(
                path.name for path in fleet_dir.glob("repos.*.json")
            )
            hint = (
                f"available: {', '.join(available)}"
                if available
                else "no repos manifest found"
            )
            raise FleetJoinError(
                f"no repos manifest for workspace {workspace!r} in "
                f"{fleet_dir} ({hint})"
            )
        return candidate, workspace
    candidates = sorted(fleet_dir.glob("repos.*.json"))
    if not candidates:
        if allow_empty:
            return None, workspace
        raise FleetJoinError(
            f"no repos manifest in {fleet_dir} "
            "(expected repos.<workspace>.json)"
        )
    if len(candidates) > 1:
        if choose is None:
            names = ", ".join(path.name for path in candidates)
            raise FleetJoinError(
                f"multiple repos manifests in {fleet_dir} ({names}); "
                "pass --workspace <name>"
            )
        chosen = choose([path.name for path in candidates])
        candidates = [path for path in candidates if path.name == chosen]
        if not candidates:
            raise FleetJoinError(
                f"chosen manifest {chosen} is not in {fleet_dir}"
            )
    only = candidates[0]
    derived = only.name[len("repos."):-len(".json")]
    return only, derived


def default_label() -> str:
    """This Mac's short hostname, for the machine label."""
    try:
        short = socket.gethostname().split(".")[0].strip()
    except OSError:
        short = ""
    return short or "mac"


def ensure_kb_checkout(
    kb: str,
    home: Path,
    workspace: str | None,
    *,
    git_runner=None,
    progress=None,
) -> tuple[Path, str | None]:
    """Resolve the knowledge checkout, cloning once when given a remote."""
    runner = git_runner or _run_git
    if not looks_like_remote(kb):
        target = Path(kb).expanduser()
        if not target.is_dir() or not (target / ".git").exists():
            raise FleetJoinError(
                f"{kb} is not a git checkout; pass the knowledge repo "
                "path or its remote URL"
            )
        if workspace is None:
            workspace = workspace_from_kb_path(target)
        return target, workspace
    workspace = workspace or workspace_from_remote(kb)
    if not workspace:
        raise FleetJoinError(
            f"cannot derive the workspace from {kb}; pass --workspace <name>"
        )
    target = clone_target_for(home, workspace, kb)
    if (target / ".git").exists():
        try:
            origin = runner(["config", "--get", "remote.origin.url"], target)
        except (OSError, subprocess.SubprocessError) as exc:
            raise FleetJoinError(f"{target}: git failed: {exc}") from exc
        if origin.returncode != 0:
            raise FleetJoinError(
                f"{target}: existing checkout has no origin remote"
            )
        if normalize_remote(origin.stdout) != normalize_remote(kb):
            raise FleetJoinError(
                f"{target}: origin {origin.stdout.strip()} does not match "
                f"{kb}; refusing to reuse it"
            )
        if progress is not None:
            progress(f"verified {target} (already cloned)")
        return target, workspace
    if target.exists():
        raise FleetJoinError(
            f"{target} exists but is not a git checkout; refusing to clobber"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    if progress is not None:
        progress(f"cloning {kb} -> {target}")
    staging = target.parent / f"{target.name}.partial-{os.getpid()}"
    for leftover in target.parent.glob(f"{target.name}.partial-*"):
        if leftover != staging:
            shutil.rmtree(leftover, ignore_errors=True)
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    try:
        completed = runner(["clone", "--quiet", kb, str(staging)], None)
    except (OSError, subprocess.SubprocessError) as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise FleetJoinError(f"{target}: clone failed: {exc}") from exc
    if completed.returncode != 0:
        shutil.rmtree(staging, ignore_errors=True)
        raise FleetJoinError(
            f"{target}: clone failed: {completed.stderr.strip()}; check the "
            "remote URL and auth, then rerun the same command"
        )
    try:
        os.rename(staging, target)
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise FleetJoinError(
            f"{target}: clone landed but rename failed: {exc}; "
            "rerun the same command"
        ) from exc
    if progress is not None:
        progress(f"cloned {target}")
    return target, workspace


def load_bootstrap(release_root: Path):
    """Import the verified release's bootstrap engine."""
    scripts = (
        Path(release_root)
        / "skills"
        / "synthesis-project-management"
        / "scripts"
    )
    engine = scripts / "fleet_bootstrap.py"
    if not engine.is_file():
        raise FleetJoinError(
            f"release is missing {engine}; run synthesis update, then rerun"
        )
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import fleet_bootstrap

    return fleet_bootstrap


def join(
    args,
    *,
    release_root: Path,
    home: Path | None = None,
    bootstrap=None,
    git_runner=None,
    gh_runner=None,
    auth_runner=None,
    progress=None,
    setup_check=None,
    setup_runner=None,
) -> int:
    """Run ``synthesis fleet join``; return the process exit code."""
    home = Path(home).expanduser() if home is not None else Path.home()
    engine = bootstrap if bootstrap is not None else load_bootstrap(
        release_root
    )
    as_json = bool(getattr(args, "json", False))
    can_prompt = terminal_available() and not as_json

    def announce(line: str) -> None:
        if as_json:
            return
        if progress is not None:
            progress(line)
        else:
            print(line, flush=True)

    def choose_workspace(names: list[str]) -> str:
        return prompt_choice(
            "Which workspace is this Mac joining?",
            names, "--workspace <name>", can_prompt=can_prompt,
        )

    try:
        ensure_setup(
            home, setup_check=setup_check, setup_runner=setup_runner,
            announce=announce, can_prompt=can_prompt,
        )
        kb_arg = getattr(args, "kb", None)
        explicit_workspace = getattr(args, "workspace", None)
        if kb_arg:
            kb_dir, workspace = ensure_kb_checkout(
                kb_arg, home, explicit_workspace,
                git_runner=git_runner, progress=announce,
            )
            workspace = explicit_workspace or workspace
        else:
            remote, workspace = resolve_kb_interactive(
                explicit_workspace, gh_runner=gh_runner,
                auth_runner=auth_runner, announce=announce,
                can_prompt=can_prompt,
            )
            kb_dir, _ = ensure_kb_checkout(
                remote, home, workspace,
                git_runner=git_runner, progress=announce,
            )
        registry = kb_dir / "fleet" / "machines.json"
        role = resolve_role(
            getattr(args, "role", None), registry, announce=announce
        )
        manifest, workspace = discover_manifest(
            kb_dir, workspace, allow_empty=(role == "primary"),
            choose=choose_workspace,
        )
        if manifest is None:
            announce("no repos manifest yet; skipping clones")
            repos: list[dict] = []
        else:
            repos = engine.parse_repos_manifest(manifest, home)
        explicit = getattr(args, "label", None)
        hostname = default_label()
        label = (explicit or hostname).strip()
        if not label:
            raise FleetJoinError(
                "machine label is empty; pass --label NAME"
            )
        label_source = "explicit" if explicit else "auto"
        own_id = local_machine_id(home)
        try:
            shared = (
                json.loads(registry.read_text(encoding="utf-8"))
                if registry.is_file() else None
            )
        except (OSError, ValueError):
            shared = None
        if not isinstance(shared, dict):
            shared = None
        label = resolve_label(
            shared, label, own_id, can_prompt=can_prompt
        )
        announce(f"joining as {label} ({role})")
        problems = engine.preflight(home, role, registry)
        if problems:
            raise FleetJoinError("; ".join(problems))
        report = engine.bootstrap(
            home=home,
            source_root=Path(release_root),
            label=label,
            role=role,
            repos=repos,
            fleet_registry=registry,
            kb_repo=kb_dir,
            hostname=hostname or None,
            label_source=label_source,
            progress=announce,
        )
        if report["ok"]:
            note = reconcile_rename(
                home, kb_dir, role, engine,
                announce=announce, can_prompt=can_prompt,
            )
            if note is not None:
                announce(f"note: {note}")
                report = {**report, "note": note}
    except KeyboardInterrupt:
        print(
            "INTERRUPTED fleet join: rerun the same command to resume; "
            "finished steps are kept",
            file=sys.stderr,
        )
        return engine.EXIT_INTERRUPTED
    if as_json:
        print(json.dumps(report, sort_keys=True))
    else:
        for step in report["steps"]:
            print(
                f"{step['status'].upper()} bootstrap-{step['step']}: "
                f"{step['detail']}"
            )
            if step["receipt"]:
                print(f"  receipt: {step['receipt']}")
    return 0 if report["ok"] else 1
