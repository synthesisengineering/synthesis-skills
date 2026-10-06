"""Project continuity (R1): find a project, brief a session on it, resume it, hand it off.

Resume reads local files and local git only; it never fetches. Handoff commits
only the paths this session changed inside its own claims, runs every hook,
pushes only as a fast-forward, and reads its result back from git.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from synthesis import board, paths

BRIEF_LIMIT = 6000
STATE_BLOCK = re.compile(r"<!-- synthesis-current-state:start -->(.*?)<!-- synthesis-current-state:end -->", re.S)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
PLAN_LINE = re.compile(r"^[ \t]*(?:\*\*)?(?:Controlling plan|Plan):(?:\*\*)?[ \t]*(.*)$", re.M | re.I)
LINK = re.compile(r"\[[^\]\n]*\]\(<?([^()<>\n]+?)>?\)")
CHECKLIST = re.compile(r"^(?:[-*]|\d+\.)\s+\[([ xX])\]\s+")
SESSION_HEADING = re.compile(r"^#{2,3}\s+(\d{4}-\d{2}-\d{2})", re.M)
LITERAL = {"GIT_LITERAL_PATHSPECS": "1", "GIT_OPTIONAL_LOCKS": "0"}


def roots() -> list[Path]:
    configured = paths.config().get("knowledge_roots")
    if configured:
        return [Path(os.path.expanduser(r)) for r in configured]
    workspaces = Path.home() / "workspaces"
    return sorted(workspaces.glob("*/ai-knowledge-*")) if workspaces.is_dir() else []


def locate(project_id: str) -> list[Path]:
    """Every project folder with this exact id, or the folder itself when given its absolute path."""
    given = Path(os.path.expanduser(project_id))
    if given.is_absolute():
        return [given] if (given / "CONTEXT.md").is_file() else []
    return [r / "projects" / project_id for r in roots() if project_id and (r / "projects" / project_id).is_dir()]


def find(project_id: str) -> Path | None:
    matches = locate(project_id)
    return matches[0] if len(matches) == 1 else None


def _visible(text: str) -> str:
    """The text without fenced code blocks: an example is never a declaration."""
    kept, fence = [], None
    for line in text.splitlines():
        marker = FENCE.match(line)
        if fence:
            fence = None if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence) else fence
        elif marker:
            fence = marker.group(1)
        else:
            kept.append(line)
    return "\n".join(kept)


def field(text: str, name: str) -> str:
    match = re.search(rf"^\*\*{re.escape(name)}:\*\*[ \t]*(.+)$", _visible(text), re.M)
    return match.group(1).strip() if match else ""


def plan(project_dir: Path, text: str) -> tuple[str | None, str]:
    """(plan path, one line) from the one `Plan:` field (`Controlling plan:` is the same field). `none` means
    no plan; links elsewhere never count; two declarations are reported as ambiguous, never chosen between."""
    declared = [d.strip() for d in PLAN_LINE.findall(_visible(text))]
    if not declared:
        return None, "Plan: none declared"
    if len(declared) > 1:
        return None, f"Plan: ambiguous, {len(declared)} declarations ({' | '.join(declared)}); the record must name one"
    value = declared[0]
    if value.lower().strip("*_ .") in ("", "none", "no active plan"):
        return None, "Plan: none"
    link = LINK.search(value)
    target = (link.group(1) if link else value).strip("` ")
    found = (project_dir / target).is_file() or (project_dir.parent.parent / target).is_file()
    return target, f"Plan: {target}" + ("" if found else " (file not found)")


def next_actions(context: str, limit: int = 5) -> list[str]:
    """Pending `## What's Next` checklist items with their continuation lines, else a `**Next:**` field's items."""
    text = _visible(context)
    match = re.search(r"^## What's Next[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if match:
        items: list[tuple[bool, list[str]]] = []
        for line in (l.strip() for l in match.group(1).splitlines()):
            item = CHECKLIST.match(line)
            if item:
                items.append((item.group(1).lower() == "x", [line]))
            elif items and line:
                items[-1][1].append(line)
        return [" ".join(parts) for done, parts in items if not done][:limit]
    match = re.search(r"^\*\*Next(?: actions?)?:\*\*[ \t]*(.*)$((?:\n[ \t]*[-*][ \t].*)*)", text, re.M)
    if not match:
        return []
    found = [match.group(1).strip()] if match.group(1).strip() else []
    for line in match.group(2).split("\n")[1:]:
        line = line.strip()[1:].strip()
        if not re.match(r"\[[xX]\]", line):
            found.append(re.sub(r"^\[ \]\s*", "", line))
    return found[:limit]


def newest_session(project_dir: Path) -> tuple[str, str] | None:
    """(date, file) of the newest dated entry heading in sessions/. A date inside an entry's
    body and the generated sessions/INDEX.md never count."""
    found = [(d, log.name) for log in sorted((project_dir / "sessions").glob("*.md")) if log.name != "INDEX.md"
             for d in SESSION_HEADING.findall(log.read_text(encoding="utf-8", errors="replace"))]
    return max(found) if found else None


def brief(project_dir: Path) -> str:
    """What a session must have in context to continue: the directive, then current state."""
    parts = []
    directive = project_dir / "PRIME-DIRECTIVE.md"
    if directive.is_file():
        parts.append(directive.read_text(encoding="utf-8").strip())
    context = project_dir / "CONTEXT.md"
    if context.is_file():
        text = context.read_text(encoding="utf-8")
        block = STATE_BLOCK.search(text)
        parts.append("Current state (CONTEXT.md):\n" + (block.group(1).strip() if block else "\n".join(text.splitlines()[:60])))
        parts.append(plan(project_dir, text)[1])
    text = f"Active project: {project_dir.name} ({project_dir})\n\n" + "\n\n".join(parts)
    return text if len(text) <= BRIEF_LIMIT else text[: BRIEF_LIMIT - 40] + "\n[... read the files for the rest]"


def check(project_dir: Path, *, max_context_lines: int = 150) -> list[str]:
    problems = []
    context = project_dir / "CONTEXT.md"
    if not context.is_file():
        problems.append("CONTEXT.md is missing")
    elif len(context.read_text(encoding="utf-8").splitlines()) > max_context_lines:
        problems.append(f"CONTEXT.md is over {max_context_lines} lines; move history to sessions/ or REFERENCE.md")
    return problems


def _git(repo: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=120,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})})


def _out(repo: Path, *args: str) -> str:
    result = _git(repo, *args, env=LITERAL)
    return result.stdout.strip() if result.returncode == 0 else ""


def record_freshness(project_dir: Path) -> tuple[bool, str]:
    """Upstream commits touching the project that are absent locally, against the last fetch only:
    a checkout another machine left behind reports a stale phase, status and plan with full confidence."""
    inside = _git(project_dir, "rev-parse", "--show-toplevel")
    if inside.returncode != 0:
        return False, inside.stderr.strip() or "not inside a git repository"
    upstream = _out(project_dir, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if not upstream:
        return True, "no fetched upstream; freshness not comparable"
    behind = _git(project_dir, "rev-list", "--count", f"HEAD..{upstream}", "--", ".")
    if behind.returncode != 0:
        return False, behind.stderr.strip() or "freshness comparison failed"
    count = int(behind.stdout.strip() or "0")
    return (True, f"record current with fetched {upstream}") if count == 0 else (False, (
        f"project record is {count} commit(s) behind fetched {upstream}; pull the checkout before trusting phase, status, or plan"))


def _changed(repo: Path, specs: list[str]) -> list[tuple[str, str]]:
    """(status, path) for every changed or untracked file under the pathspecs, one file per entry."""
    if not specs:
        return []
    result = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames", "--", *specs, env=LITERAL)
    if result.returncode != 0:
        raise RuntimeError(f"git status failed in {repo}: {result.stderr.strip()}")
    return [(r[:2], r[3:]) for r in result.stdout.split("\0") if len(r) > 3]


def _copies(repo: Path, rel: str, dirty_here: bool) -> list[str]:
    """Other local copies of the records: other worktrees' uncommitted edits and local branches
    whose committed records are newer than, or diverged from, this checkout. Ancestry, never dates."""
    notes, here = [], os.path.realpath(repo)
    worktrees, entry = {}, {}
    for line in _out(repo, "worktree", "list", "--porcelain").splitlines() + [""]:
        if line:
            key, _, value = line.partition(" ")
            entry[key] = value
            continue
        path = entry.get("worktree", "")
        if path and os.path.realpath(path) != here and os.path.isdir(path):
            worktrees[entry.get("branch", "")[len("refs/heads/"):]] = path
            try:
                dirty = len(_changed(Path(path), [rel]))
            except RuntimeError as exc:
                notes.append(f"worktree {path} could not be read: {exc}")
                dirty = 0
            if dirty and dirty_here:
                notes.append(f"CONFLICT: worktree {path} and this checkout both have uncommitted changes "
                             "to these records; reconcile by hand before writing either")
            elif dirty:
                notes.append(f"worktree {path} has {dirty} uncommitted change(s) to these records")
        entry = {}
    current = _out(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    branches = [b for b in _out(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines() if b != current]
    query = "".join(f"{rev}:{rel}\n" for rev in ["HEAD"] + branches)
    listed = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch-check=%(objectname)"], input=query,
                            capture_output=True, text=True, timeout=60).stdout.splitlines()
    trees = ["" if t.endswith(" missing") else t for t in listed]  # one object id per rev; "" where absent
    head_tree = trees[0] if trees else ""
    for name, tree in zip(branches, trees[1:]):
        if not tree or tree == head_tree or _git(repo, "merge-base", "--is-ancestor", name, "HEAD").returncode == 0:
            continue
        base = _out(repo, "merge-base", "HEAD", name)
        at_base = _out(repo, "rev-parse", "--verify", "--quiet", f"{base}:{rel}") if base else ""
        if at_base == tree:
            continue  # the branch never changed the records since it split; this checkout's copy is newer
        where = f"branch {name}" + (f" (worktree {worktrees[name]})" if name in worktrees else "")
        commits = _out(repo, "rev-list", "--count", f"{base}..{name}" if base else name, "--", rel)
        if base and at_base != head_tree:
            notes.append(f"CONFLICT: {where} and this checkout both changed these records since they split "
                         f"({commits} commit(s) there); reconcile by hand, never by which is newer by date")
        else:
            last = _out(repo, "log", "-1", "--format=%ad %s", "--date=short", name, "--", rel)
            notes.append(f"newer copy on {where}: {commits} commit(s) not in this checkout, last {last}")
    return notes


def _upstream(project_dir: Path, repo: Path, rel: str, dirty: list[tuple[str, str]]) -> list[str]:
    """This checkout against its already-fetched upstream, for this project's records only."""
    fresh, detail = record_freshness(project_dir)
    if fresh:
        return [] if detail.startswith("record current") else [
            "No fetched upstream to compare with, so other machines' changes are unknown here; resuming from local files."]
    upstream = _out(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    behind = _out(repo, "log", "--format=%h %ad %s", "--date=short", f"HEAD..{upstream}", "--", rel).splitlines()
    if not upstream or not behind:
        return [detail]
    notes = [f"This checkout is {len(behind)} commit(s) behind its fetched {upstream} for these records "
             "(as of the last fetch):"] + [f"  {line}" for line in behind[:10]]
    ahead = _out(repo, "rev-list", "--count", f"{upstream}..HEAD", "--", rel)
    if ahead not in ("", "0"):
        notes.append(f"CONFLICT: this checkout also has {ahead} unpushed commit(s) to these records; reconcile by hand.")
    elif dirty:
        notes.append("Uncommitted changes here; do not pull over them: " + ", ".join(p for _, p in dirty[:10]))
    else:
        notes.append(f"Fast-forward before working: git -C {repo} pull --ff-only")
    return notes


def resume(name: str, session_id: str = "", *, switch: bool = False) -> str:
    """The text a session needs to pick up a project, or the question it must ask first."""
    me = board.load(session_id) if session_id else None
    found = locate(name)
    if not found:
        known = roots()
        where = (", ".join(str(r) for r in known) if len(known) < 4 else f"{len(known)} knowledge roots") or "no knowledge root"
        return (f"No project with the id {name!r} in {where}. Start a new project named {name!r}? "
                "Nothing similar was picked: give the exact id to resume an existing project.")
    if len(found) > 1:
        return f"{name!r} exists in {len(found)} places; resume one by its path:\n" + "\n".join(f"  {p}" for p in found)
    project_dir = found[0]
    pid = project_dir.name
    if me and me.project and me.project != pid and not switch:
        return (f"This session is working project {me.project}; you asked to resume {pid}. Switch this session "
                f"to {pid}, or stay on {me.project}? Nothing was switched (after a yes: synthesis resume {pid} --switch).")
    if me and me.project == pid and not switch:
        return f"Already working {pid} in this session; continuing without reloading."
    text = (project_dir / "CONTEXT.md").read_text(encoding="utf-8") if (project_dir / "CONTEXT.md").is_file() else ""
    newest = newest_session(project_dir)
    lines = [brief(project_dir), "",
             " | ".join(f"{k}: {field(text, k) or 'not stated'}" for k in ("Phase", "Status", "Last session"))
             + (f" | newest session entry: {newest[0]} in sessions/{newest[1]}" if newest else " | no dated session entry")]
    lines += [f"Next: {a}" for a in next_actions(text, 3)] or ["Next: none listed in CONTEXT.md"]
    warnings = []
    top = _out(project_dir, "rev-parse", "--show-toplevel")
    if not top:
        warnings.append("not in a git repository, so newer copies elsewhere cannot be checked")
    else:
        repo = Path(top)
        rel = os.path.relpath(os.path.realpath(project_dir), os.path.realpath(repo))
        try:
            dirty = _changed(repo, [rel])
            warnings += _upstream(project_dir, repo, rel, dirty) + _copies(repo, rel, bool(dirty))
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            warnings.append(f"could not compare these records with other copies: {exc}")
    for other in board.sessions():
        if other.session != session_id and not other.stale and (
                other.project == pid or any(board.overlaps(c, str(project_dir) + "/**") for c in other.claims)):
            warnings.append(f"Live session {other.session} ({other.harness or '?'}, project {other.project or '-'}: "
                            f"{other.goal or 'no goal'}) works here; one session owns CONTEXT.md, so read only "
                            f"where it holds claims and coordinate with synthesis msg {other.short}.")
    if warnings:
        lines += ["", "Before working:"] + [f"- {w}" if not w.startswith("  ") else w for w in warnings]
    if session_id:
        board.touch(session_id, project=pid, harness=paths.harness(), briefed=pid)  # the brief is in this text
    return "\n".join(lines)


def _handoff_repo(repo: Path, specs: list[str], message: str) -> tuple[bool, list[str]]:
    lock = _out(repo, "rev-parse", "--git-path", "index.lock")
    if lock and (repo / lock if not os.path.isabs(lock) else Path(lock)).exists():
        return False, [f"{repo}: index.lock exists (another git command is running, or one crashed). "
                       "Left alone and nothing committed; run handoff again once it is gone."]
    branch = _out(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    if not branch:
        return False, [f"{repo}: detached HEAD, so nothing was committed; check out a branch first."]
    lines, changed = [], _changed(repo, specs)
    if changed:
        before = _out(repo, "log", "-1", "--format=%H")
        files = [p for _, p in changed]
        untracked = [p for code, p in changed if code == "??"]
        if untracked:
            _git(repo, "add", "--intent-to-add", "--", *untracked, env=LITERAL)
        result = _git(repo, "commit", "--only", "-m", message, "--", *files, env=LITERAL)  # hooks always run
        after, left = _out(repo, "log", "-1", "--format=%H"), _changed(repo, files)
        if after == before or left:
            if untracked and after == before:
                _git(repo, "reset", "--quiet", "--", *untracked, env=LITERAL)
            said = (result.stderr or result.stdout).strip().splitlines()
            return False, [f"{repo}: NOT committed (git log still shows {before[:12] or 'no commit'}; "
                           f"{len(left)} of {len(files)} file(s) still changed). Git said: {' / '.join(said[-3:])}"]
        lines.append(f"{repo}: committed {len(files)} file(s) at {after[:12]}")
    remote, merge = _out(repo, "config", f"branch.{branch}.remote"), _out(repo, "config", f"branch.{branch}.merge")
    if not remote or remote == "." or not merge.startswith("refs/heads/"):
        return False, lines + [f"{repo}: branch {branch} has no upstream, so nothing was pushed and no other machine can see it."]
    target = merge[len("refs/heads/"):]
    fetched = _git(repo, "fetch", "--quiet", remote)
    if fetched.returncode != 0:
        return False, lines + [f"{repo}: fetch from {remote} failed ({fetched.stderr.strip()[:200]}); commits are safe locally, nothing pushed."]
    tracking = f"refs/remotes/{remote}/{target}"
    exists = bool(_out(repo, "rev-parse", "--verify", "--quiet", tracking))
    counts = _out(repo, "rev-list", "--left-right", "--count", f"HEAD...{tracking}").split() if exists else ["1", "0"]
    ahead, behind = (int(counts[0]), int(counts[1])) if len(counts) == 2 else (-1, -1)
    if ahead < 0:
        return False, lines + [f"{repo}: cannot compare {branch} with {remote}/{target}; nothing pushed."]
    if ahead and behind:
        return False, lines + [f"{repo}: {branch} and {remote}/{target} diverged ({ahead} local, {behind} remote commit(s)). "
                               "Commits are safe locally; integrate by hand (no rebase or force here), then run handoff again."]
    if ahead:
        pushed = _git(repo, "push", "--quiet", remote, f"HEAD:refs/heads/{target}")  # a fast-forward or nothing
        _git(repo, "fetch", "--quiet", remote)
        left = _out(repo, "rev-list", "--count", f"{tracking}..HEAD")
        if pushed.returncode != 0 or left != "0":
            return False, lines + [f"{repo}: push to {remote}/{target} did not land ({(pushed.stderr or '').strip()[:200]}); "
                                   f"git rev-list shows {left or 'unknown'} commit(s) not on {remote}."]
        if lines:
            lines[-1] += f" and pushed to {remote}/{target}"
        else:
            lines.append(f"{repo}: pushed {ahead} earlier commit(s) to {remote}/{target}")
    elif not changed:
        lines.append(f"{repo}: nothing changed in this session's claims; already on {remote}/{target}")
    if behind:
        lines.append(f"{repo}: this checkout is {behind} commit(s) behind {remote}/{target}; pull --ff-only before working here again")
    return True, lines


def handoff(session_id: str, message: str = "Update project records") -> list[str]:
    """Commit and push the changes inside this session's claims (R1.4). Claims are the attribution:
    a file outside them is never committed, whoever changed it. The last line says READY or NOT READY."""
    session = board.load(session_id) if session_id else None
    if session is None or not session.claims:
        return ["NOT READY: this session holds no claims, so no change is attributable to it. "
                "Claim the records you changed (synthesis claim <paths>), then run handoff again."]
    by_repo: dict[Path, list[str]] = {}
    report, ok = [], True
    for claim in session.claims:
        base = os.path.realpath(claim[:-3] if claim.endswith("/**") else claim)
        probe = base if os.path.isdir(base) else os.path.dirname(base)
        top = _out(Path(probe), "rev-parse", "--show-toplevel") if os.path.isdir(probe) else ""
        if top:
            by_repo.setdefault(Path(os.path.realpath(top)), []).append(os.path.relpath(base, os.path.realpath(top)))
        else:
            report.append(f"{claim}: not inside a git checkout (or no longer exists); skipped")
    for repo, specs in sorted(by_repo.items()):
        try:
            done, lines = _handoff_repo(repo, specs, message)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            done, lines = False, [f"{repo}: {exc}"]
        ok, report = ok and done, report + lines
    report.append("READY: every record this session changed is committed and on its upstream." if ok else
                  "NOT READY: the problems above stop another machine from resuming these records; nothing was forced.")
    return report
