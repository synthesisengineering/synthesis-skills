"""Bring a workspace onto this Mac, and enroll an organization's configuration.

A workspace is `~/workspaces/<name>/` with its knowledge repository
`ai-knowledge-<name>`, whose `.agents/repos.yaml` lists the workspace's repositories.
`bring_workspace` finds the knowledge repository (through `gh`, or by asking once),
clones it, then clones every listed repository with progress per repository.
Existing clean checkouts fast-forward; dirty, diverged or wrong-origin ones are
skipped by name, never repointed or overwritten. A rerun resumes.

An organization repository is data only: `.agents/onboarding.yaml` (schema 2, see
references/org-manifest.md) and one tracked instruction file. No code from it runs.
Called from setup.py; see its usage.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

import setup
from synthesis import yamlish  # the plugin's YAML reader; setup put the plugin root on sys.path

ARCHIVE_NOTE = "<!-- synthesis-instructions:generated -->"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
LEGACY_KEYS = {"workspace_instructions", "migrations", "installer", "installer_args", "source_env",
               "status_args", "primary", "fallbacks", "superseded_remotes"}
WHERE_TO_FIND = ("Your knowledge repository is on GitHub under your account; it looks like "
                 "https://github.com/<you>/ai-knowledge-<name>.git")


def normalize(url: str) -> str:
    text = url.strip().rstrip("/")
    return text[:-4] if text.endswith(".git") else text


def workspace_from(remote: str) -> str:
    stem = normalize(remote).rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return stem[len("ai-knowledge-"):] if stem.startswith("ai-knowledge-") and len(stem) > 13 else ""


def _git(args: list, cwd=None, env=None, timeout: float = 600):
    return setup.run(["git", *args], timeout, cwd=str(cwd) if cwd else None, env=env)


# ---- one repository: clone, or fast-forward when that is safe ---------------------

def clone_or_update(remote: str, target: Path, branch: str = "", extra_remotes=None, env=None) -> str:
    """'cloned', 'updated', 'current' or 'skipped: <reason>'. Raises on a wrong origin."""
    if (target / ".git").exists():
        origin = _git(["config", "--get", "remote.origin.url"], target, env).stdout.strip()
        if normalize(origin) != normalize(remote):
            raise setup.SetupError(f"{target}: origin is {origin or 'missing'}, not {remote}; "
                                   "refusing to repoint it (move it aside or fix its origin, then rerun)")
        if _git(["status", "--porcelain"], target, env).stdout.strip():
            return "skipped: uncommitted changes"
        if _git(["fetch", "--quiet", "origin"], target, env).returncode:
            return "skipped: fetch failed"
        counts = _git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], target, env).stdout.split()
        if len(counts) != 2:
            return "skipped: no upstream branch"
        ahead, behind = int(counts[0]), int(counts[1])
        if ahead:
            return "skipped: diverged from its upstream" if behind else "skipped: has unpushed commits"
        if not behind:
            return "current"
        merged = _git(["merge", "--ff-only", "--quiet", "@{upstream}"], target, env)
        return "updated" if merged.returncode == 0 else f"skipped: {setup._tail(merged)}"
    if os.path.lexists(target):
        raise setup.SetupError(f"{target} exists and is not a git checkout; refusing to overwrite it")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f"{target.name}.partial-{os.getpid()}")
    for leftover in target.parent.glob(f"{target.name}.partial-*"):  # an interrupted earlier clone
        shutil.rmtree(leftover, ignore_errors=True)
    proc = _git(["clone", "--quiet", *(["--branch", branch] if branch else []), remote, str(staging)], env=env)
    if proc.returncode:
        shutil.rmtree(staging, ignore_errors=True)
        raise setup.SetupError(f"{target.name}: clone failed: {setup._tail(proc)}")
    for name, url in (extra_remotes or {}).items():
        _git(["remote", "add", name, url], staging, env)
    os.rename(staging, target)  # only a complete clone ever appears at the target
    return "cloned"


def clone_all(entries: list, progress, env=None, auth_help: str = "") -> list:
    """entries: (remote, target, branch, extra remotes). One line per repository, as it lands."""
    lines = []
    for i, (remote, target, branch, extra) in enumerate(entries, 1):
        progress(f"[{i}/{len(entries)}] {target.name} ...")
        try:
            status = clone_or_update(remote, target, branch, extra, env)
        except setup.SetupError as exc:
            status = f"needs action: {exc}" + (f"\n{auth_help.strip()}" if auth_help and "clone failed" in str(exc) else "")
        lines.append(f"{target.name}: {status}")
        progress(f"[{i}/{len(entries)}] {target.name}: {status}")
    return lines


# ---- a workspace from its knowledge repository's repos.yaml ------------------------

def discover_kb(interactive: bool) -> str:
    """The knowledge repository: found through `gh` (signing in when needed), else asked once."""
    found = setup.run(["gh", "repo", "list", "--json", "url", "--limit", "200"], 60)
    if found.returncode and interactive and found.returncode != 127:  # 127: no gh at all
        print("GitHub sign-in is needed to find your knowledge repository; starting it now", flush=True)
        stream, opened = setup._terminal()
        try:
            signed_in = subprocess.run(["gh", "auth", "login"], stdin=stream).returncode == 0
        finally:
            if opened:
                stream.close()
        if signed_in:
            found = setup.run(["gh", "repo", "list", "--json", "url", "--limit", "200"], 60)
    urls = [r.get("url", "") for r in setup._json(found.stdout) or [] if "ai-knowledge-" in str(r.get("url", ""))] \
        if found.returncode == 0 else []
    if len(urls) == 1:
        return urls[0]
    if len(urls) > 1 and interactive:
        return setup.choose("Which knowledge repository holds this workspace?", urls, "--kb URL")
    if not interactive:
        raise setup.SetupError("cannot tell which knowledge repository to use; pass --kb URL")
    print(WHERE_TO_FIND, flush=True)
    return setup.ask("Knowledge repository URL or path", "--kb URL")


def workspace_entries(kb_dir: Path, ws_root: Path) -> tuple:
    """(clone entries, notes) from the knowledge repository's .agents/repos.yaml."""
    manifest = kb_dir / ".agents" / "repos.yaml"
    if not manifest.is_file():
        return [], [f"{manifest} not found: only the knowledge repository was set up"]
    repos = yamlish.load_mapping(manifest.read_text(encoding="utf-8"), str(manifest)).get("repos") or []
    entries, notes = [], []
    for repo in repos:
        remotes = repo.get("remotes") or {}
        relative = str(repo.get("path") or repo.get("name") or "").strip("/")
        if not remotes.get("origin") or not relative or ".." in Path(relative).parts or relative.startswith("/"):
            notes.append(f"{repo.get('name', '?')}: no origin or an unsafe path in repos.yaml; skipped")
        elif str(repo.get("status", "")).lower() in ("dormant", "archived", "retired"):
            notes.append(f"{relative}: {repo['status']}; not cloned")
        else:
            branches = repo.get("default_branches") or []
            entries.append((remotes["origin"], ws_root / relative, branches[0] if branches else "",
                            {k: v for k, v in remotes.items() if k != "origin"}))
    return entries, notes


def bring_workspace(kb: str, workspace: str, progress, adopt: bool = False, interactive: bool = False) -> list:
    kb = kb or discover_kb(interactive)
    local = Path(os.path.expanduser(kb))
    is_remote = "://" in kb or kb.startswith("git@") or kb.rstrip("/").endswith(".git")
    if not is_remote:
        if not (local / ".git").exists():
            raise setup.SetupError(f"{kb} is neither a git checkout nor a repository URL")
        kb_dir = local.resolve()
        workspace = workspace or kb_dir.parent.name
        lines = [f"{kb_dir.name}: using this checkout"]
    else:
        workspace = workspace or workspace_from(kb) or (interactive and setup.ask("Workspace name", "--workspace"))
        if not workspace or not SAFE_ID.fullmatch(workspace):
            raise setup.SetupError("cannot derive a safe workspace name from the repository; pass --workspace NAME")
        kb_dir = Path.home() / "workspaces" / workspace / normalize(kb).rsplit("/", 1)[-1]
        progress(f"{kb_dir.name} ...")  # a wrong origin or a failed clone stops here: nothing else to read
        lines = [f"{kb_dir.name}: {clone_or_update(kb, kb_dir)}"]
    ws_root = kb_dir.parent
    entries, notes = workspace_entries(kb_dir, ws_root)
    lines += notes + clone_all([e for e in entries if e[1] != kb_dir], progress)
    return lines + link_workspace(ws_root, kb_dir, adopt)


def new_workspace(name: str, remote: str = "") -> list:
    """Start ~/workspaces/<name>/ai-knowledge-<name>, the knowledge repository a person's project
    records live in, from assets/workspace/. A seed that exists is the person's and is never
    rewritten. Git identity is checked before anything is created, because the seeds are committed."""
    _safe_id(name, "workspace name")
    repo = Path.home() / "workspaces" / name / f"ai-knowledge-{name}"
    if not (repo / ".git").exists() and not all(_git(["config", key]).stdout.strip()
                                                for key in ("user.name", "user.email")):
        raise setup.SetupError('git has no identity for the first commit: run git config --global user.name '
                               '"Your Name" and git config --global user.email you@example.com, then rerun')
    assets, written = Path(__file__).resolve().parents[1] / "assets" / "workspace", []
    seeds = {(".agents/" + r[7:] if r.startswith("agents/") else r): src.read_text(encoding="utf-8")
             for src in assets.rglob("*") if src.is_file() for r in [src.relative_to(assets).as_posix()]}
    seeds.update({"CLAUDE.md": "@AGENTS.md\n", ".gitignore": ".DS_Store\n"})
    for rel, text in sorted(seeds.items()):
        if not (repo / rel).exists():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(text.replace("{workspace}", name).replace("{remote}", f'"{remote}"'), encoding="utf-8")
            written.append(rel)
    if not (repo / ".git").exists():
        _git(["init", "-q", "-b", "main"], repo)
    if written:
        _git(["add", "--", *written], repo)
        made = _git(["commit", "-q", "-m", "Set up the knowledge repository", "--", *written], repo)
        if made.returncode:  # git's own reason, never a guessed one
            raise setup.SetupError(f"{repo}: the first commit was refused: {setup._tail(made)}")
    if remote and not _git(["remote", "get-url", "origin"], repo).stdout.strip():
        _git(["remote", "add", "origin", remote], repo)
    lines = [f"{repo.name}: {'created ' + str(len(written)) + ' files' if written else 'already set up'}"]
    return lines + link_workspace(repo.parent, repo, adopt=False)


def _archive(paths: list) -> Path:
    folder = setup.install._home() / "archive" / time.strftime("%Y%m%dT%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    for path in (p for p in paths if os.path.lexists(p)):
        shutil.move(str(path), str(folder / path.name))
    return folder


def _place_instructions(ws_root: Path, write_agents, adopt: bool, generated_only: bool) -> list:
    """Write AGENTS.md (via write_agents) and a CLAUDE.md that imports it, preserving files
    someone else wrote unless `adopt`, which archives the old pair first."""
    agents, claude = ws_root / "AGENTS.md", ws_root / "CLAUDE.md"
    ours = not os.path.lexists(agents) or (generated_only and agents.is_file() and not agents.is_symlink()
                                            and agents.read_text(encoding="utf-8").startswith(ARCHIVE_NOTE))
    if not ours and not adopt:
        return [f"{agents}: kept as it is (not written by setup); pass --adopt-workspace-instructions to replace it"]
    lines = [] if ours else [f"archived the previous AGENTS.md and CLAUDE.md to {_archive([agents, claude])}"]
    write_agents(agents)
    if not os.path.lexists(claude) or claude.read_text(encoding="utf-8", errors="replace").strip() != "@AGENTS.md":
        if os.path.lexists(claude) and not adopt:
            return lines + [f"{agents}: written; {claude} kept (not `@AGENTS.md`)"]
        if os.path.lexists(claude):
            claude.unlink()
        claude.write_text("@AGENTS.md\n", encoding="utf-8")
    return lines + [f"{agents}: written, with CLAUDE.md importing it"]


def link_workspace(ws_root: Path, kb_dir: Path, adopt: bool) -> list:
    """The workspace's instructions and repos.yaml are links into its knowledge repository."""
    lines, source = [], kb_dir / ".agents" / "workspace-AGENTS.md"
    repos_link = ws_root / ".agents" / "repos.yaml"
    if (kb_dir / ".agents" / "repos.yaml").is_file() and not os.path.lexists(repos_link):
        repos_link.parent.mkdir(exist_ok=True)
        repos_link.symlink_to(Path("..") / kb_dir.name / ".agents" / "repos.yaml")
        lines.append(f"linked {repos_link}")
    if source.is_file():
        relative = Path(kb_dir.name) / ".agents" / "workspace-AGENTS.md"
        if (ws_root / "AGENTS.md").is_symlink() and os.readlink(ws_root / "AGENTS.md") == str(relative):
            return lines + [f"{ws_root / 'AGENTS.md'}: already links to {relative}"]
        lines += _place_instructions(ws_root, lambda path: path.symlink_to(relative), adopt, generated_only=False)
    return lines


# ---- an organization's configuration repository -----------------------------------

def validate_repository_url(url) -> str:
    """Authenticated HTTPS or SSH only; no credentials, local paths, file: or git: transports."""
    if not isinstance(url, str) or not url:
        raise setup.SetupError("a repository URL is required")
    if re.fullmatch(r"[A-Za-z0-9._-]+@[A-Za-z0-9.-]+:[A-Za-z0-9._~/-]+", url):
        return url
    parsed = urlsplit(url)
    if parsed.scheme not in ("https", "ssh") or not parsed.hostname:
        raise setup.SetupError(f"{url}: repository transport must be HTTPS or SSH")
    if parsed.password is not None or (parsed.scheme == "https" and parsed.username is not None):
        raise setup.SetupError("repository URLs must not contain credentials")
    if parsed.query or parsed.fragment:
        raise setup.SetupError("a repository URL must not contain a query or fragment")
    return url


def _safe_id(value, label: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise setup.SetupError(f"{label} must be a safe identifier")
    return value


def _mapping(value, label: str, allowed: set) -> dict:
    if not isinstance(value, dict):
        raise setup.SetupError(f"{label} must be a mapping")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise setup.SetupError(f"{label} has unknown keys: {', '.join(unknown)}")
    return value


def _keys(value) -> set:
    if isinstance(value, dict):
        return set(value).union(*(_keys(v) for v in value.values()))
    return set().union(*(_keys(v) for v in value)) if isinstance(value, list) else set()


def validate_org_manifest(data) -> dict:
    """Schema 2. It has no executable, argument, environment or status-command field: every action
    belongs to this public code. Unknown keys fail; schema-1 manifests are refused with the migration."""
    if isinstance(data, dict) and (data.get("version") == 1 or LEGACY_KEYS & _keys(data)):
        raise setup.SetupError("this is a schema-1 manifest; migrate it as described in "
                               "skills/synthesis-onboarding/references/org-manifest.md#migrating-from-schema-1")
    data = _mapping(data, "manifest", {"version", "org", "ecosystem", "skills_repos", "knowledge_bases",
                                       "instruction_sources", "acceptance", "auth_help", "welcome", "team_contract"})
    if data.get("version") != 2:
        raise setup.SetupError("manifest version must be 2")
    org = _mapping(data.get("org"), "org", {"id", "name", "workspace"})
    _safe_id(org.get("id"), "org.id")
    _safe_id(org.get("workspace"), "org.workspace")
    eco = _mapping(data.get("ecosystem") or {}, "ecosystem", {"plugin", "clients", "channel", "version_pin"})
    if not isinstance(eco.get("plugin", True), bool):
        raise setup.SetupError("ecosystem.plugin must be true or false")
    clients = eco.get("clients", ["claude", "codex"])
    if not isinstance(clients, list) or not clients or set(clients) - set(setup.doctor.HARNESSES):
        raise setup.SetupError("ecosystem.clients may name only claude, codex and muse")
    if eco.get("channel", "stable") not in ("stable", "edge"):
        raise setup.SetupError("ecosystem.channel must be stable or edge")
    if eco.get("version_pin") is not None and not re.fullmatch(r"\d+\.\d+\.\d+", str(eco["version_pin"])):
        raise setup.SetupError("ecosystem.version_pin must be an exact X.Y.Z version")
    seen = set()
    for key, allowed in (("skills_repos", {"name", "repository", "capability", "entitlement"}),
                         ("knowledge_bases", {"name", "repository", "default_branch", "local_hooks", "entitlement"})):
        entries = data.get(key) or []
        if not isinstance(entries, list) or len(entries) > 4096:
            raise setup.SetupError(f"{key} must be a bounded list")
        for i, entry in enumerate(entries):
            entry = _mapping(entry, f"{key}[{i}]", allowed)
            if (key, _safe_id(entry.get("name"), f"{key}[{i}].name")) in seen:
                raise setup.SetupError(f"{key}[{i}] repeats the name {entry['name']}")
            seen.add((key, entry["name"]))
            validate_repository_url(entry.get("repository"))
            if key == "skills_repos" and entry.get("capability") != "skills-install":
                raise setup.SetupError(f"{key}[{i}].capability must be skills-install")
            branch = entry.get("default_branch", "main")
            if key == "knowledge_bases" and (not isinstance(branch, str) or ".." in branch
                                             or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch)):
                raise setup.SetupError(f"{key}[{i}].default_branch is unsafe")
            if "entitlement" in entry and data.get("team_contract") is None:
                raise setup.SetupError("entitlement requires a team_contract")
    sources = data.get("instruction_sources") or []
    if not isinstance(sources, list) or len(sources) != 1:
        raise setup.SetupError("the manifest needs exactly one tracked instruction source")
    path = str(_mapping(sources[0], "instruction_sources[0]", {"path", "required"}).get("path") or "")
    if not path or path.startswith("/") or ".." in Path(path).parts:
        raise setup.SetupError("instruction_sources[0].path must be a relative path inside the repository")
    if data.get("acceptance"):
        _safe_id(_mapping(data["acceptance"], "acceptance", {"task"}).get("task"), "acceptance.task")
    if data.get("auth_help") is not None and not isinstance(data["auth_help"], str):
        raise setup.SetupError("auth_help must be text")
    welcome = _mapping(data.get("welcome") or {}, "welcome", {"title", "try_asking", "docs"})
    for key in ("try_asking", "docs"):
        if not isinstance(welcome.get(key, []), list) or not all(isinstance(v, str) for v in welcome.get(key, [])):
            raise setup.SetupError(f"welcome.{key} must be a list of text")
    return data


ORG_GIT = ["-c", "protocol.file.allow=never", "-c", "protocol.ext.allow=never"]


def org_git_env() -> dict:
    """The person's credentials stay usable; injected git config and transports beyond https and ssh do not."""
    env = {k: v for k, v in os.environ.items()
           if not (k in ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS") or re.fullmatch(r"GIT_CONFIG_(KEY|VALUE)_\d+", k))}
    return {**env, "GIT_ALLOW_PROTOCOL": "https:ssh", "GIT_PROTOCOL_FROM_USER": "0"}


def org_root(url: str) -> Path:
    """Two organizations with the same repository name never share a folder."""
    name = normalize(url).rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "synthesis" / "organizations"
    return data / f"{_safe_id(name, 'repository name')}-{hashlib.sha256(normalize(url).encode()).hexdigest()}"


def acquire_org(url: str) -> tuple:
    """Clone, or refresh a clean clone of, the organization repository. Returns (folder, commit)."""
    validate_repository_url(url)
    root, env, git = org_root(url), org_git_env(), ORG_GIT
    if root.exists():
        if root.is_symlink() or not (root / ".git").is_dir():
            raise setup.SetupError(f"{root} is not a real git clone")
        origin = _git(git + ["remote", "get-url", "origin"], root, env).stdout.strip()
        if normalize(origin) != normalize(url):
            raise setup.SetupError(f"{root} has origin {origin}, not {url}")
        if _git(git + ["status", "--porcelain"], root, env).stdout.strip():
            raise setup.SetupError(f"{root} has local changes; an organization clone is never edited by hand")
        for step in (["fetch", "--prune", "--quiet", "origin"], ["checkout", "--quiet", "--detach", "origin/HEAD"]):
            proc = _git(git + step, root, env)
            if proc.returncode:
                raise setup.SetupError(f"organization repository: {setup._tail(proc)}")
    else:
        root.parent.mkdir(parents=True, exist_ok=True)
        staging = root.with_name(f".{root.name}.{os.getpid()}")
        shutil.rmtree(staging, ignore_errors=True)
        proc = _git(git + ["clone", "--quiet", url, str(staging)], env=env)
        if proc.returncode:
            shutil.rmtree(staging, ignore_errors=True)
            raise setup.SetupError(f"organization repository: clone failed: {setup._tail(proc)}; check that "
                                   "your account can read it, then rerun the same command")
        os.rename(staging, root)
    manifest = root / ".agents" / "onboarding.yaml"
    tracked = _git(git + ["ls-files", "--error-unmatch", "--", ".agents/onboarding.yaml"], root, env)
    if manifest.is_symlink() or not manifest.is_file() or tracked.returncode:
        raise setup.SetupError("the organization repository has no tracked, regular .agents/onboarding.yaml")
    return root, _git(git + ["rev-parse", "HEAD"], root, env).stdout.strip()


def install_org_skills(repo: Path) -> list:
    """Copy the repository's skills into Claude Code's and the Agent Skills folders (never
    ~/.codex/skills, which Codex owns). A copy someone edited since setup wrote it is kept."""
    nested, flat = sorted(repo.glob("skills/*/SKILL.md")), sorted(repo.glob("*/SKILL.md"))
    if nested and flat:
        raise setup.SetupError(f"{repo.name} has skills both under skills/ and at its root; use one layout")
    ledger_path = setup.install._home() / "org-skills.json"
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ledger = {}
    lines = []
    for skill in [p.parent for p in nested or flat]:
        for root in (Path.home() / ".claude" / "skills", Path.home() / ".agents" / "skills"):
            dest = root / skill.name
            if dest.exists() and ledger.get(str(dest)) != _digest(dest):
                lines.append(f"{dest}: kept (changed since setup wrote it, or not written by setup)")
                continue
            setup.export_tree(skill, dest)  # staging, then an atomic rename
            ledger[str(dest)] = _digest(dest)
        lines.append(f"skill {skill.name}: installed for Claude Code and Codex")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return lines


def _digest(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        digest.update(str(path.relative_to(folder)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def render_instructions(org_text: str, personal_text: str = "") -> str:
    kernel = (Path(__file__).resolve().parents[1] / "references" / "kernel.example.md").read_text(encoding="utf-8")
    parts = [ARCHIVE_NOTE, "# Workspace Instructions", "## Public", kernel.strip(), "## Organization", org_text.strip()]
    return "\n\n".join(parts + (["## Personal", personal_text.strip()] if personal_text.strip() else [])) + "\n"


def org_preferences(url: str) -> tuple:
    """(clients, marketplace ref) the organization's manifest asks for."""
    root, _ = acquire_org(url)
    eco = validate_org_manifest(yamlish.load_mapping((root / ".agents" / "onboarding.yaml").read_text(
        encoding="utf-8"), ".agents/onboarding.yaml")).get("ecosystem") or {}
    ref = f"v{eco['version_pin']}" if eco.get("version_pin") else ("main" if eco.get("channel") == "edge" else "stable")
    return list(eco.get("clients") or ["claude", "codex"]), ref


def enroll(url: str, progress, personal_source: str = "", adopt: bool = False) -> list:
    root, commit = acquire_org(url)
    manifest = validate_org_manifest(yamlish.load_mapping((root / ".agents" / "onboarding.yaml").read_text(
        encoding="utf-8"), ".agents/onboarding.yaml"))
    org, help_text = manifest["org"], manifest.get("auth_help") or ""
    ws_root = Path.home() / "workspaces" / org["workspace"]
    lines = [f"organization {org.get('name') or org['id']}: configuration at commit {commit[:12]}"]
    lines += clone_all([(kb["repository"], ws_root / kb["name"], kb.get("default_branch", ""), {})
                        for kb in manifest.get("knowledge_bases") or []], progress, org_git_env(), help_text)
    for entry in manifest.get("skills_repos") or []:
        target = root.parent / "skills" / org_root(entry["repository"]).name
        status = clone_all([(entry["repository"], target, "", {})], progress, org_git_env(), help_text)
        lines += status
        if (target / ".git").exists():
            lines += install_org_skills(target)
    source = root / manifest["instruction_sources"][0]["path"]
    tracked = _git(["ls-files", "--error-unmatch", "--", manifest["instruction_sources"][0]["path"]], root)
    if source.is_symlink() or not source.is_file() or tracked.returncode:
        raise setup.SetupError(f"{source.name} is not a tracked, regular file in the organization repository")
    records_path = setup.install._home() / "organizations.json"
    try:
        records = json.loads(records_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        records = {}
    if not personal_source:  # a rerun keeps the personal layer chosen before; "none" clears it
        personal_source = (records.get(normalize(url)) or {}).get("personal_source", "")
    personal_source = "" if personal_source == "none" else personal_source
    personal = Path(os.path.expanduser(personal_source)) if personal_source else None
    if personal and (personal.is_symlink() or not personal.is_file()):
        raise setup.SetupError(f"{personal_source} is not a regular file")
    records[normalize(url)] = {"workspace": org["workspace"], "commit": commit, "personal_source": personal_source}
    records_path.parent.mkdir(parents=True, exist_ok=True)
    records_path.write_text(json.dumps(records, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    text = render_instructions(source.read_text(encoding="utf-8"), personal.read_text(encoding="utf-8") if personal else "")
    ws_root.mkdir(parents=True, exist_ok=True)
    lines += _place_instructions(ws_root, lambda path: path.write_text(text, encoding="utf-8"), adopt, True)
    welcome = manifest.get("welcome") or {}
    if welcome:
        lines += [welcome.get("title", "Your workspace is ready")] + [f"  try: {q}" for q in welcome.get("try_asking", [])]
    return lines


if __name__ == "__main__":  # check an organization manifest: python3 workspace.py check <onboarding.yaml>
    import sys
    if len(sys.argv) != 3 or sys.argv[1] != "check":
        sys.exit("usage: python3 workspace.py check <path to .agents/onboarding.yaml>")
    try:
        manifest = validate_org_manifest(yamlish.load_mapping(Path(sys.argv[2]).read_text(encoding="utf-8"), sys.argv[2]))
    except (OSError, ValueError, setup.SetupError) as exc:
        print(f"invalid: {exc}")
        sys.exit(2)
    print(f"valid schema-2 manifest for {manifest['org']['id']} (workspace {manifest['org']['workspace']})")
