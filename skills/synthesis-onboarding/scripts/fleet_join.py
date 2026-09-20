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


def prompt_text(question: str, hint: str, *, can_prompt: bool) -> str:
    """Ask one free-text question; the hint names the flag alternative."""
    _require_prompt(hint, can_prompt)
    answer = _read_answer(f"{question}: ", hint)
    if not answer:
        raise FleetJoinError(f"an answer is required; or pass {hint}")
    return answer


def prompt_choice(question: str, options: list[str], hint: str, *,
                  can_prompt: bool) -> str:
    """Ask one numbered question over ``options``; return the chosen one."""
    _require_prompt(hint, can_prompt)
    print(question, flush=True)
    for position, option in enumerate(options, start=1):
        print(f"  {position}. {option}", flush=True)
    answer = _read_answer(f"Choice [1-{len(options)}]: ", hint)
    if not answer.isdigit() or not 1 <= int(answer) <= len(options):
        raise FleetJoinError(
            f"choice must be 1-{len(options)}; or pass {hint}"
        )
    return options[int(answer) - 1]


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
    try:
        completed = runner(["clone", "--quiet", kb, str(target)], None)
    except (OSError, subprocess.SubprocessError) as exc:
        raise FleetJoinError(f"{target}: clone failed: {exc}") from exc
    if completed.returncode != 0:
        raise FleetJoinError(
            f"{target}: clone failed: {completed.stderr.strip()}; check the "
            "remote URL and auth, then rerun the same command"
        )
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
        label = getattr(args, "label", None) or default_label()
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
            progress=announce,
        )
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
