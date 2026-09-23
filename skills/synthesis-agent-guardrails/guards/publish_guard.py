#!/usr/bin/env python3
"""publish_guard.py — fail-closed pre-publish gate for live-site deployments.

The intent this enforces (2026-08-20, restating the intent behind the
original 2026-03-23 `disable-model-invocation` flags): **no change reaches a
live site without the principal previewing it and giving explicit in-chat
approval.** The old flag gated skill *loading*, which was always a proxy —
the dangerous act is the push/deploy itself, reachable with or without any
skill loaded. This guard gates the act.

Gated commands (PreToolUse on Bash / exec):
  * any `wrangler pages deploy` (manual-deploy sites, e.g. a personal site)
  * any `git push` that targets a configured AUTO-DEPLOY site repository
    (Cloudflare Pages publishes these on push to main)

A gated command passes only when a FRESH, SINGLE-USE approval ledger exists,
bound to the repository and its current HEAD:

    ~/.synthesis/publish-guard/approval.json
    { "repo": "<abs path>", "head_sha": "<rev-parse HEAD at approval>",
      "created_at": "<ISO-8601 UTC>", "summary": "<what the principal approved>",
      "approved_via": "in-chat" }

The composing agent writes the ledger ONLY after showing the principal the
change (preview, diff, or built output) and receiving their yes for THIS
publish — permission never carries forward. `--approve <repo> --summary
"..."` writes it correctly (it snapshots HEAD itself). The gate consumes
the ledger on use; HEAD moving after approval invalidates it.

CONFIG. ~/.synthesis/publish-guard/config.json (PUBLISH_GUARD_CONFIG
overrides the path):
{"auto_deploy_repos": ["<abs repo>", ...],
 "principal_name": "<optional; messages use 'the principal' when empty>",
 "sites": {"<abs repo>": {"label": "<name>",
   "principal_name": "<optional per-site override>",
   "content_layout": "nested-date | flat",
   "content_roots": ["<repo-relative dir>", ...]}}}.
Repos without a sites entry use the default descriptor (both historical
article layouts). The installing principal's identity lives ONLY in this
file, never in the guard.

Design principles (inherited from synthesis-message-guard / git-hooks v2):
  1. FAIL CLOSED. Unparseable command, unreadable config, missing repo,
     failed rev-parse: the gated class blocks. Non-gated commands still pass
     when config is broken — a dead config must not brick every shell call,
     only publishing.
  2. ZERO DEPENDENCIES. Stdlib only.
  3. SELF-DIAGNOSING. --doctor runs positive and negative controls; --test
     is a hermetic behavioral suite.

Modes:
  --gate     (default) PreToolUse hook: read tool-call JSON on stdin,
             allow (exit 0) or block (exit 2, reason on stderr).
  --approve REPO --summary TEXT   write the approval ledger for REPO.
  --doctor   self-check; exit 0 HEALTHY / 2 UNHEALTHY.
  --test     behavioral suite; exit 0 all pass / 2 failures.

Environment overrides (used by --test):
  PUBLISH_GUARD_CONFIG     path to config JSON
                           (default ~/.synthesis/publish-guard/config.json)
  PUBLISH_GUARD_STATE_DIR  ledger dir (default ~/.synthesis/publish-guard)
"""

from __future__ import annotations

import hashlib
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# The shell parser is a same-repo public module; this guard binds it lazily
# by file location. Import-time loading is forbidden — collection and
# doctor runs must not pay import cost — so every entry below calls
# _ensure_shell_parser first.
artifact_consumer_position = None
inspect_command = None
wrangler_operation = None


def _ensure_shell_parser() -> None:
    """Bind the public shell parser on first use."""
    global artifact_consumer_position, inspect_command, wrangler_operation
    if inspect_command is not None:
        return
    scripts = (Path(__file__).resolve().parent.parent.parent
               / "synthesis-project-management" / "scripts")
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import publication_command as parser
    artifact_consumer_position = parser.artifact_consumer_position
    inspect_command = parser.inspect_command
    wrangler_operation = parser.wrangler_operation

ENGINE_VERSION = "1.3.1"
LEDGER_MAX_AGE_MINUTES = 15
# A second publish of the SAME repo shortly after the last one is the
# error-cascade shape: the rushed follow-up "fix" is the highest-risk
# publish there is (2026-08-29 — a live post was re-dated and republished
# 28 minutes after the publish it was correcting, compounding the harm).
# Within this window the ledger must carry the principal's explicit
# rapid-redeploy approval, quoted.
RAPID_REDEPLOY_WINDOW_MINUTES = 45
# Clock-skew allowance for the future-date invariant. A page "published now"
# with a timestamp minutes ahead is a clock artifact; hours ahead is a
# future-dated publication, the 2026-08-29 incident class.
FUTURE_DATE_SKEW_MINUTES = 15

WRANGLER_RX = re.compile(r"\bwrangler\s+pages\s+deploy\b")
# `push` must be the git subcommand itself (flags may precede it), not a
# word inside a commit message or other argument — the loose form gated
# `git commit -m "...site push..."` (2026-08-29 false positive).
#
# Flags that take a SEPARATE argument must consume it, or the bare value sits
# between the flag and `push` and the whole pattern misses. `git -C <path>
# push` bypassed this guard entirely until 2026-08-30 — detection returned
# before the approval ledger was ever consulted, and a live site was published
# with no approval check performed. Attached forms (`--git-dir=/x`) always
# worked; the separated forms did not.
GIT_VALUE_FLAGS = r"(?:-C|-c|--git-dir|--work-tree|--namespace|--exec-path|--config-env|--super-prefix)"
GIT_PUSH_RX = re.compile(
    rf"\bgit\s+(?:(?:{GIT_VALUE_FLAGS}\s+[^\s;&|]+|-[-\w=./]*)\s+)*push\b"
)
# Explicit repository references inside the command itself. An explicit
# reference states intent and outranks the ambient shell cwd, which is often
# just wherever the session happens to live. Before 2026-08-30 the cwd check
# won unconditionally, so a command that plainly named a different repository
# was still attributed to whatever directory the shell sat in — blocking
# legitimate publishes and, worse, teaching operators to route around the
# guard.
GIT_C_RX = re.compile(r"\bgit\s+(?:-c\s+[^\s;&|]+\s+)*-C\s+([^\s;&|]+)")
CD_RX = re.compile(r"\bcd\s+([^\s;&|]+)")
FRONTMATTER_DATE_RX = re.compile(
    r"^date:\s*'?\"?(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})", re.MULTILINE
)


def _content_date(text: str) -> datetime | None:
    """The frontmatter publication timestamp of one content file, naive local."""
    m = FRONTMATTER_DATE_RX.search(text)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def future_dated_files(repo: str, now: datetime | None = None,
                       cfg: dict | None = None) -> list[tuple[str, str]]:
    """Content files whose stated publication time is still in the future.

    Invariant (2026-08-29, after a post dated the next afternoon went live
    the evening before): a page never goes live before its stated date.
    "Publish at its date" means holding the push until the date, never
    deploying early. This runs ABOVE the approval ledger: an approval covers
    a publish, not a violation of the site's own timeline.
    """
    moment = now or datetime.now()
    horizon = moment.timestamp() + FUTURE_DATE_SKEW_MINUTES * 60
    offenders: list[tuple[str, str]] = []
    # Both article layouts across the configured sites — see the note in
    # published_date_mutations. Scanning only content/posts exempted the
    # flat-layout site from the never-live-before-its-date invariant, which
    # is the invariant a real take-down was needed to enforce on 2026-08-29.
    for rel_root, pattern in content_scans(cfg, repo):
        root = Path(repo) / rel_root
        if not root.is_dir():
            continue
        for index in sorted(root.rglob(pattern)):
            try:
                stamp = _content_date(index.read_text(encoding="utf-8"))
            except OSError:
                offenders.append((str(index.relative_to(repo)), "unreadable"))
                continue
            if stamp is not None and stamp.timestamp() > horizon:
                offenders.append(
                    (str(index.relative_to(repo)), stamp.strftime("%Y-%m-%d %H:%M"))
                )
    return offenders


def _git_out(repo: str, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True, text=True, check=False, timeout=20,
        )
    except Exception:
        return None
    return proc.stdout if proc.returncode == 0 else None


def published_date_mutations(repo: str,
                             cfg: dict | None = None) -> list[tuple[str, str, str]] | None:
    """Content files whose ALREADY-PUBLISHED date changes in this push.

    The compounding half of the 2026-08-29 incident: re-dating a live post
    converts a timeline oddity into visible evidence of date editing.
    Published dates are immutable; the remedy is take down and republish at
    the correct time. Returns None when the published base cannot be
    established — the caller fails closed on that.
    """
    base = None
    for ref in ("origin/main", "origin/master"):
        if _git_out(repo, "rev-parse", "--verify", f"{ref}^{{commit}}"):
            base = ref
            break
    if base is None:
        return None
    # Two article layouts exist across the configured sites. Most keep
    # content/posts/YYYY/MM/DD-slug/index.md; the flat-layout site keeps flat
    # files at astro-site/src/content/articles/*.md. Scanning only the first
    # silently exempted the flat site from the immutability rule even though
    # its URLs carry dates exactly like the others (found 2026-08-31 during
    # the completion audit). Both roots are scanned; a repo lacking one
    # simply yields nothing. Per-site descriptors narrow this via
    # content_roots + content_layout.
    scans = content_scans(cfg, repo)
    changed = _git_out(
        repo, "diff", "--name-only", "--diff-filter=M", f"{base}...HEAD",
        "--", *[root for root, _ in scans],
    )
    if changed is None:
        return None
    mutations: list[tuple[str, str, str]] = []
    for rel in [line.strip() for line in changed.splitlines() if line.strip()]:
        if not _scan_match(rel, scans):
            continue
        old_text = _git_out(repo, "show", f"{base}:{rel}")
        if old_text is None:
            continue
        try:
            new_text = (Path(repo) / rel).read_text(encoding="utf-8")
        except OSError:
            continue
        old_date, new_date = _content_date(old_text), _content_date(new_text)
        if old_date and new_date and old_date != new_date:
            mutations.append(
                (rel, old_date.strftime("%Y-%m-%d %H:%M"),
                 new_date.strftime("%Y-%m-%d %H:%M"))
            )
    return mutations


def config_path() -> str:
    return os.environ.get(
        "PUBLISH_GUARD_CONFIG",
        os.path.expanduser("~/.synthesis/publish-guard/config.json"),
    )


def state_dir() -> str:
    return os.environ.get(
        "PUBLISH_GUARD_STATE_DIR", os.path.expanduser("~/.synthesis/publish-guard")
    )


def ledger_path() -> str:
    return os.path.join(state_dir(), "approval.json")


def _safe_path(path: str | Path) -> Path:
    path = Path(os.path.abspath(os.path.expanduser(str(path))))
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise ValueError("symlink in approval or artifact path")
    return path


@contextmanager
def approval_lock():
    root = _safe_path(state_dir())
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = _safe_path(root / ".approval.lock")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield root
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _sync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_json(path: Path, value: dict) -> None:
    path = _safe_path(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".approval-")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _sync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _fresh_approval(led: dict) -> None:
    created = datetime.fromisoformat(str(led.get("created_at")))
    if created.tzinfo is None:
        raise ValueError("approval timestamp must carry a timezone")
    age = (datetime.now(timezone.utc) - created).total_seconds()
    if age < -90 or age > LEDGER_MAX_AGE_MINUTES * 60:
        raise ValueError("approval expired or timestamp is in the future")
    if led.get("approved_via") != "in-chat" or not str(led.get("summary", "")).strip():
        raise ValueError("approval provenance or summary missing")


def deployment_binding(path: str) -> tuple[dict, str, str]:
    """Re-derive protected inputs, never trusting a stored success receipt."""
    candidate = _safe_path(path)
    if not candidate.is_file() or not Path(path).is_absolute():
        raise ValueError("binding must be an absolute regular file")
    raw = candidate.read_bytes()
    binding = json.loads(raw)
    keys = {"schema", "transaction_id", "surface", "repo", "head_sha", "tree_sha",
            "consumer_path", "consumer_sha256", "bound_files", "artifact_manifest_sha256", "plan"}
    if set(binding) != keys or binding["schema"] != 1:
        raise ValueError("unknown artifact binding schema or fields")
    if not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", str(binding["transaction_id"])):
        raise ValueError("invalid transaction identity")
    if binding["surface"] not in ("pages", "worker", "database") or not isinstance(binding["plan"], dict):
        raise ValueError("invalid deployment surface or plan")
    root, common = git_identity(binding["repo"])
    if root != binding["repo"]:
        raise ValueError("binding repository is not its exact working-tree root")
    if head_sha(root) != binding["head_sha"]:
        raise ValueError("working-tree HEAD changed")
    if (_git_out(root, "rev-parse", "HEAD^{tree}") or "").strip() != binding["tree_sha"]:
        raise ValueError("working-tree tree changed")
    if _git_out(root, "status", "--porcelain", "--untracked-files=all") != "":
        raise ValueError("source working tree is not clean")
    files = binding["bound_files"]
    if not isinstance(files, list) or not files:
        raise ValueError("artifact and tool bindings are required")
    seen = set()
    for item in files:
        if set(item) != {"path", "sha256"} or item["path"] in seen:
            raise ValueError("invalid or duplicate input binding")
        input_path = _safe_path(item["path"])
        if not Path(item["path"]).is_absolute() or not input_path.is_file():
            raise ValueError("bound input must be an absolute regular file")
        if hashlib.sha256(input_path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("artifact or tool input changed")
        seen.add(item["path"])
    consumer = {"path": binding["consumer_path"], "sha256": binding["consumer_sha256"]}
    if consumer not in files:
        raise ValueError("executing consumer must be a bound input")
    if not re.fullmatch(r"[a-f0-9]{64}", binding["artifact_manifest_sha256"]):
        raise ValueError("invalid artifact digest")
    return binding, hashlib.sha256(raw).hexdigest(), common


def _deployment_dir(root: Path, binding: dict) -> Path:
    return _safe_path(root / "deployments" / (binding["transaction_id"] + "-" + binding["surface"]))


def approve_deployment(path: str, summary: str, quote: str, rapid_redeploy: bool = False) -> int:
    """Agent attestation of the principal's current exact approval, not inferred authority."""
    try:
        load_config()
        if not summary.strip() or not quote.strip():
            raise ValueError("exact approval quote and summary are required")
        with approval_lock() as root:
            binding, digest, common = deployment_binding(path)
            destination = _deployment_dir(root, binding)
            if destination.exists():
                raise ValueError("transaction already has an approval or consumed attempt; use a fresh accepted transaction")
            destination.mkdir(parents=True, mode=0o700)
            led = {"schema": 1, "binding_path": str(_safe_path(path)), "binding_sha256": digest,
                   "git_common_dir": common, "created_at": datetime.now(timezone.utc).isoformat(),
                   "approved_via": "in-chat", "summary": summary.strip(), "quote": quote.strip(),
                   "rapid_redeploy": rapid_redeploy, "binding": binding}
            _atomic_json(destination / "approval.json", led)
            _sync_dir(destination.parent)
        print(json.dumps({"status": "approved", "transaction_id": binding["transaction_id"],
                          "surface": binding["surface"], "binding_sha256": digest}))
        return 0
    except Exception as exc:
        print(f"publish-guard BLOCKED: {exc}", file=sys.stderr)
        return 2


def consume_deployment(path: str, *, peek: bool = False) -> int:
    """Current invocation consumes once under the lock; a prior receipt never authorizes."""
    try:
        cfg = load_config()
        with approval_lock() as root:
            binding, digest, common = deployment_binding(path)
            directory = _deployment_dir(root, binding)
            approval = _safe_path(directory / "approval.json")
            consumed = _safe_path(directory / "consumed.json")
            if consumed.exists():
                raise ValueError("approval already consumed, including interrupted attempts")
            led = json.loads(approval.read_bytes())
            _fresh_approval(led)
            if (led.get("binding_path") != str(_safe_path(path)) or led.get("binding_sha256") != digest
                    or led.get("binding") != binding or led.get("git_common_dir") != common):
                raise ValueError("approval does not match exact candidate")
            if not str(led.get("quote", "")).strip():
                raise ValueError("exact principal approval is missing")
            if future_dated_files(binding["repo"], cfg=cfg) or published_date_mutations(binding["repo"], cfg=cfg) != []:
                raise ValueError("publication timeline invariant failed or cannot be verified")
            recent, _ = rapid_redeploy_state(binding["repo"], surface=binding["surface"])
            if recent and not led.get("rapid_redeploy"):
                raise ValueError("rapid redeployment requires explicit quoted approval")
            if peek:
                print(json.dumps({"status": "admitted", "authority_receipt": False, "binding_sha256": digest}))
                return 0
            # Rename is the one-way commit point. A crash from here burns the
            # attempt; neither a receipt-write failure nor a retry resurrects it.
            os.rename(approval, consumed)
            _sync_dir(directory)
            record_publish(binding["repo"], led["summary"], binding["surface"])
            result = {"schema": 1, "status": "consumed", "metadata_class": "approval-consumption",
                      "transaction_id": binding["transaction_id"], "surface": binding["surface"],
                      "binding_sha256": digest, "approval_sha256": hashlib.sha256(consumed.read_bytes()).hexdigest(),
                      "consumed_path": str(consumed), "consumed_at": datetime.now(timezone.utc).isoformat(),
                      "guard_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(f"publish-guard BLOCKED: {exc}", file=sys.stderr)
        return 2


def load_config() -> dict:
    with open(config_path()) as fh:
        cfg = json.load(fh)
    repos = cfg.get("auto_deploy_repos")
    if not isinstance(repos, list) or not repos:
        raise ValueError("config must declare a non-empty auto_deploy_repos list")
    cfg["auto_deploy_repos"] = [os.path.expanduser(r).rstrip("/") for r in repos]
    if "principal_name" in cfg and not isinstance(cfg["principal_name"], str):
        raise ValueError("config principal_name must be a string")
    if "sites" in cfg and not isinstance(cfg["sites"], dict):
        raise ValueError("config sites must be a map of repo path to descriptor")
    for site_path, desc in (cfg.get("sites") or {}).items():
        if not isinstance(desc, dict):
            raise ValueError(f"site descriptor for {site_path} must be a map")
        roots = desc.get("content_roots")
        if roots is not None and (
            not isinstance(roots, list) or not all(isinstance(r, str) for r in roots)
        ):
            raise ValueError(f"site {site_path} content_roots must be a list of directory paths")
        if desc.get("content_layout", "nested-date") not in ("nested-date", "flat"):
            raise ValueError(f"site {site_path} content_layout must be nested-date or flat")
        if "principal_name" in desc and not isinstance(desc["principal_name"], str):
            raise ValueError(f"site {site_path} principal_name must be a string")
    return cfg


def site_descriptor(cfg: dict | None, repo: str) -> dict:
    """The per-site descriptor for REPO, or {} for the default descriptor."""
    sites = (cfg or {}).get("sites")
    if not isinstance(sites, dict):
        return {}
    key = os.path.abspath(os.path.expanduser(repo)).rstrip("/")
    for site_path, desc in sites.items():
        if not isinstance(desc, dict):
            continue
        if os.path.abspath(os.path.expanduser(site_path)).rstrip("/") == key:
            return desc
    return {}


def principal_name(cfg: dict | None, repo: str | None = None) -> str:
    """Per-site principal name, else top-level, else "" (messages say "the principal")."""
    if repo is not None:
        site = site_descriptor(cfg, repo).get("principal_name")
        if isinstance(site, str) and site.strip():
            return site.strip()
    top = (cfg or {}).get("principal_name")
    if isinstance(top, str) and top.strip():
        return top.strip()
    return ""


def principal_display(cfg: dict | None, repo: str | None = None) -> str:
    return principal_name(cfg, repo) or "the principal"


# Default timeline scans for repos without a sites entry: the nested-date
# layout (content/posts/**/index.md) and the flat layout
# (astro-site/src/content/articles/*.md). Both are generic static-site
# shapes; a repo lacking a root simply yields nothing from it.
DEFAULT_CONTENT_SCANS = (
    ("content/posts", "index.md"),
    ("astro-site/src/content/articles", "*.md"),
)


def content_scans(cfg: dict | None, repo: str) -> list[tuple[str, str]]:
    """(repo-relative dir, filename pattern) pairs for the timeline invariants."""
    desc = site_descriptor(cfg, repo)
    roots = desc.get("content_roots")
    if not roots:
        return list(DEFAULT_CONTENT_SCANS)
    if not isinstance(roots, list) or not all(isinstance(r, str) for r in roots):
        raise ValueError("site content_roots must be a list of directory paths")
    layout = desc.get("content_layout", "nested-date")
    if layout not in ("nested-date", "flat"):
        raise ValueError("site content_layout must be nested-date or flat")
    pattern = "*.md" if layout == "flat" else "index.md"
    return [(r, pattern) for r in roots]


def _scan_match(rel: str, scans: list[tuple[str, str]]) -> bool:
    for root, pattern in scans:
        root = root.rstrip("/")
        if rel != root and not rel.startswith(root + "/"):
            continue
        base = rel.rsplit("/", 1)[-1]
        if pattern == "index.md":
            if base == "index.md":
                return True
        elif base.endswith(".md"):
            return True
    return False


def head_sha(repo: str) -> str:
    out = subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=15,
    )
    if out.returncode != 0:
        raise RuntimeError(f"rev-parse failed in {repo}: {out.stderr.strip()}")
    return out.stdout.strip()


def git_identity(path: str) -> tuple[str, str]:
    """Actual worktree plus shared Git identity; neither basename nor HEAD aliases."""
    if any(os.environ.get(k) for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_CONFIG_COUNT")):
        raise ValueError("alternate Git environment cannot select an approval repository")
    root = _git_out(path, "rev-parse", "--show-toplevel")
    common = _git_out(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not root or not common:
        raise ValueError("cannot resolve Git working-tree identity")
    return os.path.realpath(root.strip()), os.path.realpath(common.strip())


def _remote_key(url: str) -> str:
    value = url.strip().rstrip("/").removesuffix(".git")
    ssh = re.fullmatch(r"[^/@]+@([^/:]+):(.+)", value)
    if ssh:
        return ssh[1].lower() + "/" + ssh[2]
    parsed = urlparse(value)
    return (parsed.hostname.lower() + parsed.path if parsed.hostname else value)


def _shell_segments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    segments: list[list[str]] = [[]]
    for token in lexer:
        if token and all(c in ";&|()<>\n" for c in token):
            if token != "&&" and token.strip("\n"):
                raise ValueError("only fail-fast publication command chains are supported")
            if "\n" in token and any(s and s[0] == "cd" for s in segments):
                raise ValueError("directory selection must be chained with &&")
            if segments[-1]:
                segments.append([])
        else:
            segments[-1].append(token)
    return [s for s in segments if s]


def _literal_path(token: str, cwd: str) -> str:
    if not token or any(c in token for c in "$`*?{}"):
        raise ValueError("unresolved shell target; use an explicit literal path")
    return os.path.abspath(os.path.join(cwd, os.path.expanduser(token)))


def _safe_publication_prefix(words: list[str]) -> bool:
    """Known output-only commands or the separately validated literal cd."""
    if not words:
        return False
    executable = Path(words[0]).name
    return words[0] == "cd" or executable in {"echo", "true", ":"} or (
        executable == "printf" and (len(words) == 1 or not words[1].startswith("-v")))


def publication_targets(command: str, cwd: str, repos: list[str], *,
                        parsed_segments: list[list[str]] | None = None) -> list[str]:
    """Interpret the actual command sequence, retaining the pushed source identity.

    Shell variables, alternate Git environments and ambiguous ref expansion are
    refused for publishing. This is a bounded shell interface, not shell execution.
    A matching remote protects a site's destination even from an unrelated clone.
    """
    _ensure_shell_parser()
    segments = _shell_segments(command) if parsed_segments is None else parsed_segments
    for tokens in segments:
        # Assignment syntax matters only in assignment/export positions. A
        # printf argument that resembles an environment variable is data.
        assignment_words = tokens[1:] if tokens[0] == "export" else tokens[:1]
        if any(re.match(r"(?:GIT_[A-Z_]+|PATH|CDPATH|PUBLISH_GUARD_[A-Z_]+)=", token) for token in assignment_words):
            raise ValueError("publication environment changes must not share the command")
        if Path(tokens[0]).name in ("sh", "bash", "zsh", "eval"):
            raise ValueError("nested shell publication requires an explicit top-level command")
    identities, destinations = set(), set()
    for repo in repos:
        _, common = git_identity(repo)
        identities.add(common)
        for remote in (_git_out(repo, "remote") or "").splitlines():
            urls = _git_out(repo, "remote", "get-url", "--push", "--all", remote)
            if urls is None:
                raise ValueError("cannot read configured publication destination")
            destinations.update(_remote_key(v) for v in urls.splitlines())
    current = os.path.abspath(os.path.expanduser(cwd or os.getcwd()))
    unknown_cwd = False
    targets = []
    for sequence, tokens in enumerate(segments):
        if tokens[0] == "cd":
            if any(not _safe_publication_prefix(prior) for prior in segments[:sequence]):
                raise ValueError("conditional directory changes cannot select a publication target")
            try:
                args = tokens[1:]
                if args and args[0] == "--":
                    args = args[1:]
                if len(args) != 1:
                    raise ValueError("ambiguous cd")
                current = _literal_path(args[0], current)
                unknown_cwd = False
            except ValueError:
                unknown_cwd = True
            continue
        # Only actual executables count: a commit message saying 'push' does not.
        # Classification is about executable position, never arbitrary argv.
        # The outer classifier already rejects nested/ambiguous publication.
        first = (0 if Path(tokens[0]).name in ("git", "wrangler", "wrangler.js")
                 else 1 if Path(tokens[0]).name in ("npx", "node")
                 and len(tokens) > 1 and Path(tokens[1]).name in ("wrangler", "wrangler.js")
                 else None)
        if first is None:
            continue
        executable = Path(tokens[first]).name
        args = tokens[first + 1:]
        if executable in ("wrangler", "wrangler.js"):
            operation = wrangler_operation(args)
            if not operation:
                continue
            if operation == "database":
                raise ValueError("remote database change requires the exact artifact approval consumer")
            # The CLI applies --cwd before running the command. We cannot
            # bind an ambient approval to a different checkout/configuration.
            if any(arg.split("=")[0] in {"--cwd", "--config", "-c"} or arg.startswith("-c") and not arg.startswith("--") for arg in args):
                raise ValueError("Wrangler target-changing options require an exact artifact approval consumer")
            if "--" in args:
                raise ValueError("Wrangler option terminator requires an exact supported invocation")
            if "--dry-run" in args:
                if operation != "worker" or args[:1] != ["deploy"]:
                    raise ValueError("Pages deployment has no supported dry-run option")
                # Only the exact documented nonpublishing shape is admitted.
                # Extra flags can negate a boolean or consume it as a value.
                if args == ["deploy", "--dry-run"] or (
                    len(args) == 3 and args[-1] == "--dry-run" and
                    not args[1].startswith("-") and not any(c in args[1] for c in "$`")):
                    continue
                raise ValueError("ambiguous or conflicting dry-run options")
            if not (args[:2] == ["pages", "deploy"] or args[:1] == ["deploy"]):
                raise ValueError("unsupported Wrangler deployment invocation")
            if args[:1] == ["deploy"]:
                raise ValueError("Worker deployment requires the exact artifact approval consumer")
            if unknown_cwd:
                raise ValueError("unresolved deployment working directory")
            targets.append(git_identity(current)[0])
            continue
        git_cwd, git_dir, work_tree = current, None, None
        index = 0
        while index < len(args) and args[index].startswith("-"):
            flag = args[index]
            if flag in ("-C", "-c", "--git-dir", "--work-tree"):
                if index + 1 >= len(args):
                    raise ValueError("missing Git option value")
                value = args[index + 1]
                index += 2
            elif flag.startswith(("--git-dir=", "--work-tree=")):
                flag, value = flag.split("=", 1)
                index += 1
            else:
                # Leave harmless non-push commands alone; reject unknown push options.
                if "push" in args[index:]:
                    raise ValueError("unsupported Git publication option")
                break
            if flag == "-C":
                git_cwd = _literal_path(value, git_cwd)
            elif flag == "--git-dir":
                git_dir = _literal_path(value, git_cwd)
            elif flag == "--work-tree":
                work_tree = _literal_path(value, git_cwd)
            elif not value.startswith(("user.name=", "user.email=")) and "push" in args[index:]:
                raise ValueError("Git configuration override at publication boundary")
        if index >= len(args) or args[index] != "push":
            continue
        if unknown_cwd or first != 0:
            raise ValueError("unresolved Git publication environment or working directory")
        if any(os.environ.get(k) for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_CONFIG_COUNT")):
            raise ValueError("alternate Git environment at publication boundary")
        if git_dir:
            backlink = Path(git_dir) / "gitdir"
            inferred = str(Path(backlink.read_text().strip()).parent) if backlink.is_file() else str(Path(git_dir).parent)
            root, common = git_identity(work_tree or inferred)
            actual = _git_out(root, "rev-parse", "--absolute-git-dir")
            if not actual or os.path.realpath(actual.strip()) != os.path.realpath(git_dir):
                raise ValueError("Git directory and working-tree mismatch")
        else:
            root, common = git_identity(work_tree or git_cwd)
        push_args = args[index + 1:]
        if any(arg == "--repo" or arg.startswith("--repo=") for arg in push_args):
            raise ValueError("publication destination must be an explicit positional remote")
        positional = [arg for arg in push_args if not arg.startswith("-")]
        remote = positional[0] if positional else "origin"
        urls = _git_out(root, "remote", "get-url", "--push", "--all", remote)
        remote_values = urls.splitlines() if urls is not None else [remote]
        protected = common in identities or any(_remote_key(url) in destinations for url in remote_values)
        if not protected:
            continue
        safe_flags = {"--quiet", "-q", "--verbose", "-v", "--porcelain", "--set-upstream", "-u",
                      "--atomic", "--progress", "--no-progress", "--dry-run", "-n"}
        if any(arg.startswith("-") and arg not in safe_flags for arg in push_args):
            raise ValueError("multi-ref, deletion or flag-bearing publication requires an exact supported operation")
        if "--dry-run" in push_args or "-n" in push_args:
            continue
        refs = positional[1:]
        if len(refs) != 1 or refs[0].startswith("+") or any(c in refs[0] for c in "*?$"):
            raise ValueError("publication must name one exact source ref")
        source = refs[0].split(":", 1)[0]
        pushed = _git_out(root, "rev-parse", "--verify", source + "^{commit}")
        if not pushed or pushed.strip() != head_sha(root):
            raise ValueError("pushed ref is not the approved working-tree HEAD")
        targets.append(root)
    if len(targets) > 1:
        raise ValueError("one approval cannot authorize multiple publication operations")
    if targets and any("--approve" in tokens or "--approve-deployment" in tokens for tokens in segments):
        raise ValueError("approval recording and publishing must be separate fail-closed operations")
    return targets


def command_mentions_repo(command: str, cwd: str, repos: list[str]) -> str | None:
    """Return the configured repo a git-push command targets, else None.

    Detection is deliberately generous (fail-closed direction): a push counts
    as targeting a repo when the hook cwd sits inside it, when the command
    `cd`s into it, when `git -C <path>` names it, or when the command simply
    mentions the repo's directory name near a push.

    The one narrowing: when the command explicitly names an absolute path
    inside a DIFFERENT git checkout and no explicit path names a configured
    repo, the answer is None. The command has stated which repository it acts
    on, and it is not one of ours.
    """
    def _inside(path: str, repo: str) -> bool:
        # normpath so `.../x/../synthesis-coding-site` cannot dodge the match
        p = os.path.normpath(os.path.expanduser(path or "")).rstrip("/")
        return bool(p) and p != "." and (p == repo or p.startswith(repo + "/"))

    def _git_root(path: str) -> str | None:
        """Enclosing git checkout of `path`, or None. `.git` may be a file
        (linked worktree) or a directory, so test existence, not is-dir."""
        probe = Path(os.path.normpath(path))
        for parent in [probe, *probe.parents]:
            if (parent / ".git").exists():
                return str(parent)
        return None

    # Pass 1 — EXPLICIT references in the command outrank the ambient cwd.
    # `cd <path>` and `git -C <path>` state which repository this command acts
    # on; the shell's cwd is frequently incidental (an agent session pinned to
    # some worktree). Resolving cwd first mis-attributed such commands to the
    # wrong repository (2026-08-30).
    # An unexpanded shell variable is not a path. `cd "$R" && git push` yields the
    # literal `"$R"`, and resolving that against the cwd lands it INSIDE whichever
    # repo the shell happens to sit in — which then wins as an "explicit" reference
    # and mis-attributes the publish to the wrong site (observed 2026-08-31). Such a
    # token carries no location information, so it is dropped and the command's
    # literal repo mention (Pass 2) or the cwd backstop (Pass 3) decides instead.
    UNRESOLVED = set('$"\'`*?{}')

    raw: list[str] = []
    for rx in (CD_RX, GIT_C_RX):
        for m in rx.finditer(command):
            token = m.group(1)
            if UNRESOLVED & set(token):
                continue
            raw.append(os.path.expanduser(token))

    absolute = [os.path.normpath(p) for p in raw if os.path.isabs(p)]
    # A relative reference is resolved against the shell cwd AND against each
    # absolute reference already seen, so `cd <repo> && cd ../<sibling>` binds
    # to the sibling rather than being dropped.
    candidates: list[str] = list(absolute)
    for p in raw:
        if os.path.isabs(p):
            continue
        for base in (cwd, *absolute):
            if base:
                candidates.append(os.path.normpath(os.path.join(base, p)))

    # 1a — an explicit reference landing inside a configured repo wins outright.
    for path in candidates:
        for repo in repos:
            if _inside(path, repo):
                return repo

    # 1b — the command explicitly names some OTHER git repository, so it is not
    # a site publish and the ambient cwd must not make it look like one.
    # Without this, a session pinned inside a site worktree could not push any
    # unrelated repo: `cd ~/workspaces/example/control-plane && git push`
    # fell through to Pass 3, which named the site the shell happened to sit in
    # and blocked the push (2026-08-31 — cost a day of hand-run pushes).
    # Only ABSOLUTE references qualify: a relative one whose base is ambiguous
    # falls through to the cwd backstop instead, keeping the failure closed.
    # Non-repo targets (`cd /tmp && git push`) also fall through — naming a
    # scratch directory says nothing about which repository is being pushed.
    for path in absolute:
        root = _git_root(path)
        if root is not None and not any(_inside(root, repo) for repo in repos):
            return None

    # Pass 2 — the command names a configured repo by path or directory name.
    for repo in repos:
        if repo in command or os.path.basename(repo) in command:
            return repo

    # Pass 3 — fall back to the ambient cwd. A command with no explicit target
    # (a bare `git push` inside a site repo) still lands here, so this remains
    # the fail-closed backstop it always was.
    for repo in repos:
        if _inside(cwd, repo):
            return repo
    return None


def explicit_repo_root(command: str) -> str | None:
    """Git root of the first repository the COMMAND explicitly names.

    Resolves `cd <path>` and `git -C <path>` and walks up to the enclosing git
    checkout. Used for wrangler deploys, where the command's own `cd` is the
    authoritative statement of which site is being published — the shell's cwd
    is frequently just wherever the agent session happens to be pinned.

    Returns None when the command names no path, or names one that is not
    inside a git checkout; the caller then falls back to cwd-based resolution,
    so this can only redirect attribution to a real repository, never suppress
    the gate.
    """
    for rx in (CD_RX, GIT_C_RX):
        for m in rx.finditer(command):
            candidate = os.path.normpath(os.path.expanduser(m.group(1)))
            if not os.path.isabs(candidate):
                continue
            probe = Path(candidate)
            for parent in [probe, *probe.parents]:
                if (parent / ".git").exists():
                    return str(parent)
    return None


def last_publish_path(repo: str, surface: str = "pages") -> str:
    # Linked worktrees share the brake, but never substitute each other's HEAD.
    try:
        _, identity = git_identity(repo)
        repo = str(Path(identity).parent) if Path(identity).name == ".git" else identity
    except ValueError:
        pass  # fixture/retired paths retain their own identity, never another repo
    identity = repo.rstrip("/") + ("#" + surface if surface != "pages" else "")
    key = hashlib.sha1(identity.encode()).hexdigest()[:8]
    base = os.path.basename(repo.rstrip("/"))
    return os.path.join(state_dir(), "last-publish", f"{base}-{key}.json")


def record_publish(repo: str, summary: str, surface: str = "pages") -> None:
    """Persist the brake before admitting execution; I/O failure blocks."""
    path = _safe_path(last_publish_path(repo, surface))
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _atomic_json(path, {"repo": repo.rstrip("/"),
                       "consumed_at": datetime.now(timezone.utc).isoformat(), "summary": summary})


def rapid_redeploy_state(repo: str, now: datetime | None = None, surface: str = "pages") -> tuple[bool, dict | None]:
    """Whether this repo published within the brake window, and the record.

    Missing or unreadable state means no evidence of a recent publish — the
    brake does not engage. The fail-closed core of this guard is the
    approval ledger; the brake is an additional condition ON that ledger,
    and it cannot manufacture recency that was never recorded.
    """
    path = last_publish_path(repo, surface)
    try:
        with open(path) as fh:
            prior = json.load(fh)
        consumed = datetime.fromisoformat(str(prior.get("consumed_at")))
    except Exception:
        return False, None
    if consumed.tzinfo is None:
        return False, None
    now = now or datetime.now(timezone.utc)
    age = (now - consumed).total_seconds()
    return 0 <= age < RAPID_REDEPLOY_WINDOW_MINUTES * 60, prior


def ledger_authorizes_rapid() -> bool:
    """Peek (never consume): does the current ledger carry an explicit
    rapid-redeploy approval with the principal's quoted words?"""
    try:
        with open(ledger_path()) as fh:
            led = json.load(fh)
    except Exception:
        return False
    return (led.get("rapid_redeploy") is True
            and bool(str(led.get("rapid_redeploy_quote", "")).strip()))


def consume_ledger(repo: str) -> tuple[bool, str]:
    try:
        with approval_lock():
            return _consume_ledger_locked(repo)
    except Exception as exc:
        return False, f"approval consumption failed: {exc}"


def _consume_ledger_locked(repo: str) -> tuple[bool, str]:
    lp = ledger_path()
    if not os.path.exists(lp):
        return False, f"no approval ledger at {lp}"
    try:
        with open(lp) as fh:
            led = json.load(fh)
    except Exception as exc:
        return False, f"approval ledger unreadable: {exc}"
    lrepo = os.path.expanduser(str(led.get("repo", ""))).rstrip("/")
    if lrepo != repo.rstrip("/"):
        return False, f"ledger approves {lrepo or '<none>'}, not {repo}"
    try:
        created = datetime.fromisoformat(str(led.get("created_at")))
    except Exception:
        return False, "ledger created_at unparseable"
    now = datetime.now(timezone.utc)
    if created.tzinfo is None:
        return False, "ledger created_at must carry a timezone"
    age = (now - created).total_seconds()
    if age < -90:
        return False, "ledger created_at is in the future"
    if age > LEDGER_MAX_AGE_MINUTES * 60:
        return False, f"ledger is stale ({int(age)}s old; max {LEDGER_MAX_AGE_MINUTES}m)"
    if led.get("approved_via") != "in-chat":
        return False, "ledger must attest approved_via: in-chat"
    if not str(led.get("summary", "")).strip():
        return False, "ledger must carry a non-empty summary of what was approved"
    try:
        current = head_sha(repo)
    except Exception as exc:
        return False, f"cannot verify HEAD for {repo}: {exc}"
    if led.get("head_sha") != current:
        return False, (
            f"HEAD moved since approval (approved {str(led.get('head_sha'))[:12]}, "
            f"now {current[:12]}) — re-preview and re-approve"
        )
    if led.get("git_common_dir") and led["git_common_dir"] != git_identity(repo)[1]:
        return False, "Git common-directory identity changed"
    recent, _ = rapid_redeploy_state(repo)
    if recent and not (led.get("rapid_redeploy") is True and str(led.get("rapid_redeploy_quote", "")).strip()):
        return False, "exact consumed ledger does not authorize rapid redeployment"
    _safe_path(lp)
    os.remove(lp)  # single-use, including a subsequent brake-recording failure
    _sync_dir(Path(state_dir()))
    record_publish(repo, str(led.get("summary", "")))
    return True, "approved"


def gate() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # No parseable tool payload: nothing gated can be identified — but a
        # gate that cannot see cannot pass publishes. Allow (other hooks run
        # on the same event; blocking ALL Bash on a harness hiccup bricks the
        # session, and the command text is unavailable to match anyway).
        return 0
    tool = str(payload.get("tool_name", ""))
    if tool not in ("Bash", "exec_command", "exec"):
        return 0
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command", tool_input.get("cmd", "")))
    cwd = str(tool_input.get("workdir", payload.get("cwd", "")) or "")
    if not command:
        return 0

    try:
        _ensure_shell_parser()
        inspection = inspect_command(command)
        if not inspection.publication:
            return 0
        if inspection.restricted:
            # BUG-6: say the policy, not just the verdict — a chained,
            # wrapped, or dynamic publication cannot be matched to an
            # approval ledger, so splitting the push/deploy into its own
            # literal top-level command is the remedy, not a workaround.
            print("publish-guard BLOCKED: chained, wrapped, or dynamic publication "
                  "cannot be matched to an approval ledger (deliberate policy). "
                  "Run the push or deploy as its own literal top-level command",
                  file=sys.stderr)
            return 2
    except ValueError as exc:
        print(f"publish-guard BLOCKED: cannot classify shell execution ({exc})", file=sys.stderr)
        return 2
    # Resolve only literal directory changes before publication. Other shell
    # state mutations and repository writes could change what the command will
    # publish after this hook has checked the current snapshot. Output-only
    # commands are harmless, including publication-shaped quoted arguments.
    for publication_index in inspection.publication_indices:
        for i, words in enumerate(inspection.commands[:publication_index]):
            if not _safe_publication_prefix(words) or i in inspection.write_indices:
                print("publish-guard BLOCKED: earlier command can change publication state", file=sys.stderr)
                return 2
            if words[0] == "cd" and inspection.separators[i] != "&&":
                print("publish-guard BLOCKED: directory selection must fail closed", file=sys.stderr)
                return 2
    strict = True
    try:
        segments = _shell_segments(command)
    except ValueError:
        strict = False
        segments = inspection.commands
        # Output filtering is harmless for an ordinary repository push, but
        # target selection cannot depend on an earlier arbitrary command or
        # a directory change that may fail and still reach the push.
        if len(inspection.publication_indices) != 1:
            print("publish-guard BLOCKED: compound publication has ambiguous execution or directory selection", file=sys.stderr)
            return 2
    # Hook admission peeks only. The bound consumer consumes in its current
    # invocation immediately before spawning the fixed real deployment plan.
    publication_segments = [inspection.commands[i] for i in inspection.publication_indices]
    wrappers = [(s, position) for s in publication_segments
                if (position := artifact_consumer_position(s)) is not None]
    if wrappers:
        try:
            if not strict or len(wrappers) != 1 or len(segments) != 1:
                raise ValueError("deployment consumer must be the only command")
            tokens, position = wrappers[0]
            if position != 1 or Path(tokens[0]).name != "node":
                raise ValueError("explicit Node consumer invocation required")
            script, mode, head, receipt = tokens[position:]
            if mode not in ("deploy-pages", "deploy-worker", "deploy-database"):
                raise ValueError("exact deployment surface required")
            record = json.loads(_safe_path(receipt).read_bytes())
            snapshot = record["snapshot"]
            if snapshot["source_head"] != head:
                raise ValueError("consumer candidate HEAD differs")
            binding_path = Path(snapshot["root"]).parent / (mode[7:] + ".binding.json")
            binding, _, _ = deployment_binding(str(binding_path))
            if binding["consumer_path"] != str(_safe_path(script)):
                raise ValueError("unapproved deployment consumer")
            return consume_deployment(str(binding_path), peek=True)
        except Exception as exc:
            print(f"publish-guard BLOCKED: {exc}", file=sys.stderr)
            return 2
    wrangler_hit = any(Path(s[0]).name in ("wrangler", "wrangler.js") or
                       len(s) > 1 and Path(s[0]).name in ("npx", "node") and
                       Path(s[1]).name in ("wrangler", "wrangler.js") for s in publication_segments)
    push_hit = any(Path(s[0]).name == "git" for s in publication_segments)
    if not (wrangler_hit or push_hit):
        print("publish-guard BLOCKED: classified publication has no supported direct consumer", file=sys.stderr)
        return 2

    try:
        cfg = load_config()
    except Exception as exc:
        print(
            "publish-guard BLOCKED (fail closed): config unavailable "
            f"({exc}). Gated command classes (git push to site repos, "
            "wrangler pages deploy) stay blocked until "
            f"{config_path()} is valid.",
            file=sys.stderr,
        )
        return 2
    repos = cfg["auto_deploy_repos"]

    try:
        targets = publication_targets(command, cwd, repos, parsed_segments=segments)
        target = targets[0] if targets else None
        if target is not None and not strict:
            raise ValueError("protected publication requires an exact fail-fast command without output redirection or pipeline")
    except Exception as exc:
        print(f"publish-guard BLOCKED: {exc}", file=sys.stderr)
        return 2
    if target is None:
        return 0  # a git push to a non-site repo: not this guard's business

    # --- timeline invariants: run ABOVE the approval ledger ----------------
    # An approval covers a publish; it cannot authorize violating the site's
    # own timeline. Escape hatch requires the principal's explicit instruction.
    name = principal_display(cfg, target)
    name_cap = name[:1].upper() + name[1:]
    if os.environ.get("PUBLISH_GUARD_ALLOW_FUTURE_DATES") != "1":
        offenders = future_dated_files(target, cfg=cfg)
        if offenders:
            listing = "; ".join(f"{p} dated {d}" for p, d in offenders)
            print(
                "publish-guard BLOCKED: future-dated content — a page must "
                f"never go live before its stated date. {listing}. Hold this "
                "push until the date arrives, or correct the date with "
                f"{name}. PUBLISH_GUARD_ALLOW_FUTURE_DATES=1 overrides ONLY on "
                f"{name}'s explicit instruction for this specific publish.",
                file=sys.stderr,
            )
            return 2
        mutations = published_date_mutations(target, cfg=cfg)
        if mutations is None:
            print(
                "publish-guard BLOCKED (fail closed): cannot establish the "
                "published base (origin/main unreadable) to verify that no "
                "already-published date changes in this push. Fetch origin "
                "and retry.",
                file=sys.stderr,
            )
            return 2
        if mutations:
            listing = "; ".join(f"{p}: {a} -> {b}" for p, a, b in mutations)
            print(
                "publish-guard BLOCKED: published dates are immutable — "
                f"this push re-dates live content ({listing}). Re-dating a "
                "live post is visible date-editing; take it down and "
                "republish at the correct time instead. "
                "PUBLISH_GUARD_ALLOW_FUTURE_DATES=1 overrides ONLY on "
                f"{name}'s explicit instruction.",
                file=sys.stderr,
            )
            return 2

    # --- rapid-redeploy brake: a second publish of the same repo inside the
    # window needs the principal's explicit, quoted rapid-redeploy approval
    # in the ledger. Runs above consumption so the standard ledger cannot
    # carry it implicitly.
    in_window, prior = rapid_redeploy_state(target)
    if in_window and not ledger_authorizes_rapid():
        prior_at = str((prior or {}).get("consumed_at", "?"))[:16]
        prior_sum = str((prior or {}).get("summary", ""))[:80]
        print(
            f"publish-guard BLOCKED: second publish of {os.path.basename(target)} "
            f"within {RAPID_REDEPLOY_WINDOW_MINUTES} minutes of the last one "
            f"({prior_at}: {prior_sum}). This window is the error-cascade "
            "brake — the rushed follow-up fix is the highest-risk publish "
            f"there is. If {name_cap} explicitly approved a rapid follow-up, write "
            "the ledger with their words: publish_guard.py --approve "
            f"{target} --rapid-redeploy --quote '<their exact words>' "
            "--summary '<what they approved>'. Otherwise: stop, enumerate "
            "options with trade-offs, and put the choice to them first.",
            file=sys.stderr,
        )
        return 2

    try:
        ok, why = consume_ledger(target)
    except Exception as exc:
        ok, why = False, f"approval consumption failed: {exc}"
    if ok:
        print(f"publish-guard: approved publish for {target} (ledger consumed)")
        return 0
    print(
        f"publish-guard BLOCKED: {why}. This command publishes to a LIVE site "
        f"({os.path.basename(target)}). Before retrying: (1) show {name} the "
        "change (preview/diff/built output), (2) get their explicit in-chat "
        "yes for THIS publish — approval never carries forward, (3) write the "
        f"single-use ledger: publish_guard.py --approve {target} "
        "--summary '<what they approved>'.",
        file=sys.stderr,
    )
    return 2


def approve(repo: str, summary: str, rapid_redeploy: bool = False,
            quote: str = "") -> int:
    repo = os.path.expanduser(repo).rstrip("/")
    try:
        cfg = load_config()
    except Exception as exc:
        print(f"cannot approve: config unavailable: {exc}", file=sys.stderr)
        return 2
    try:
        repo, common = git_identity(repo)
        sha = head_sha(repo)
    except Exception as exc:
        print(f"cannot approve: {exc}", file=sys.stderr)
        return 2
    name = principal_display(cfg, repo)
    if not summary.strip():
        print("cannot approve: --summary must describe what "
              f"{name} approved",
              file=sys.stderr)
        return 2
    if rapid_redeploy and not quote.strip():
        print("cannot approve: --rapid-redeploy requires --quote with "
              f"{name}'s exact words approving the rapid follow-up",
              file=sys.stderr)
        return 2
    led = {
        "repo": repo,
        "head_sha": sha,
        "git_common_dir": common,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary.strip(),
        "approved_via": "in-chat",
    }
    if rapid_redeploy:
        led["rapid_redeploy"] = True
        led["rapid_redeploy_quote"] = quote.strip()
    try:
        with approval_lock():
            _atomic_json(Path(ledger_path()), led)
    except Exception as exc:
        print(f"cannot approve: {exc}", file=sys.stderr)
        return 2
    print(f"approval ledger written for {repo} @ {sha[:12]} "
          f"(single-use, {LEDGER_MAX_AGE_MINUTES}m TTL)")
    return 0


def run_doctor() -> int:
    ok = True

    def report(good: bool, label: str, detail: str = "") -> None:
        nonlocal ok
        print("  %s %s%s" % ("ok " if good else "FAIL", label,
                             (": " + detail) if detail else ""))
        if not good:
            ok = False

    print(f"publish-guard doctor (engine v{ENGINE_VERSION})")
    try:
        cfg = load_config()
        repos = cfg["auto_deploy_repos"]
        report(True, "config parses", f"{len(repos)} auto-deploy repo(s)")
        missing = []
        for repo in repos:
            try:
                git_identity(repo)
            except ValueError:
                missing.append(repo)
        report(not missing, "configured repos are git checkouts",
               "; ".join(missing) if missing else "all present")
    except Exception as exc:
        report(False, "config", str(exc))
        print("UNHEALTHY: gated publishes will BLOCK until config is fixed "
              "(fail closed, not fail open).")
        return 2

    # positive control: a push into the first configured repo, no ledger -> block
    env = dict(os.environ)
    # Doctor must never spend a real pending approval as its positive control.
    probe_state = tempfile.TemporaryDirectory(prefix="publish-guard-doctor-")
    env["PUBLISH_GUARD_STATE_DIR"] = os.path.realpath(probe_state.name)
    sample = {"tool_name": "Bash",
              "tool_input": {"command": f"cd {repos[0]} && git push origin main"},
              "cwd": repos[0]}
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--gate"],
        input=json.dumps(sample), capture_output=True, text=True, env=env)
    report(proc.returncode == 2, "positive control (site push, no ledger, blocks)",
           f"exit {proc.returncode}")
    neutral = {"tool_name": "Bash", "tool_input": {"command": "git status"},
               "cwd": repos[0]}
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--gate"],
        input=json.dumps(neutral), capture_output=True, text=True, env=env)
    report(proc.returncode == 0, "negative control (git status passes)",
           f"exit {proc.returncode}")
    probe_state.cleanup()
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--test"],
                          capture_output=True, text=True, timeout=120)
    report(proc.returncode == 0, "hermetic approval and linked-worktree controls",
           proc.stdout.splitlines()[-1] if proc.stdout.splitlines() else proc.stderr)

    for label, path_ in (("Claude Code", "~/.claude/settings.json"),
                         ("Codex", "~/.codex/hooks.json")):
        p = os.path.expanduser(path_)
        try:
            wired = "publish_guard.py" in Path(p).read_text()
        except Exception:
            wired = False
        report(wired, f"{label} hook wiring references publish_guard", p)

    try:
        _safe_path(state_dir())
        os.makedirs(state_dir(), exist_ok=True)
        _safe_path(Path(state_dir()) / ".doctor-probe")
        fd, probe = tempfile.mkstemp(dir=state_dir(), prefix=".doctor-probe-")
        os.close(fd)
        os.remove(probe)
        report(True, "state dir writable", state_dir())
    except Exception as exc:
        report(False, "state dir writable", str(exc))

    print("HEALTHY: publish guard fully operational." if ok else
          "UNHEALTHY: fix the failures above. The guard FAILS CLOSED, so "
          "publishes will be blocked (not unprotected) until this is fixed.")
    return 0 if ok else 2


def run_tests() -> int:
    results: list[tuple[bool, str]] = []

    def check(label: str, got: int, want: int) -> None:
        okc = got == want
        results.append((okc, label))
        print("  %s %s (exit %d, want %d)" % ("ok " if okc else "FAIL",
                                              label, got, want))

    tmp = os.path.realpath(tempfile.mkdtemp(prefix="publish-guard-test-"))
    site = os.path.join(tmp, "fake-site-repo")
    other = os.path.join(tmp, "other-repo")
    for r in (site, other):
        os.makedirs(r)
        subprocess.run(["git", "-C", r, "init", "-q", "-b", "main"], check=True)
        # Neutralize any global core.hooksPath: the operator's own commit
        # hooks must not run (or fail) inside throwaway fixture repos.
        subprocess.run(["git", "-C", r, "config", "core.hooksPath",
                        os.devnull], check=True)
        subprocess.run(["git", "-C", r, "-c", "user.email=t@t", "-c",
                        "user.name=t", "commit", "-q", "--allow-empty",
                        "-m", "seed"], check=True)
        # The timeline invariants (v1.1.0) resolve the published base from
        # origin/main and fail closed without one; give the fixture a base.
        subprocess.run(["git", "-C", r, "update-ref",
                        "refs/remotes/origin/main", "HEAD"], check=True)
    cfg_path = os.path.join(tmp, "config.json")
    Path(cfg_path).write_text(json.dumps({"auto_deploy_repos": [site]}))
    env = dict(os.environ)
    env["PUBLISH_GUARD_CONFIG"] = cfg_path
    env["PUBLISH_GUARD_STATE_DIR"] = tmp
    me = os.path.abspath(__file__)

    def invoke(payload: dict) -> int:
        proc = subprocess.run([sys.executable, me, "--gate"],
                              input=json.dumps(payload),
                              capture_output=True, text=True, env=env)
        return proc.returncode

    def write_ledger(**over) -> None:
        led = {"repo": site, "head_sha": head_sha(site),
               "created_at": datetime.now(timezone.utc).isoformat(),
               "summary": "test approval", "approved_via": "in-chat"}
        led.update(over)
        Path(os.path.join(tmp, "approval.json")).write_text(json.dumps(led))

    push = {"tool_name": "Bash",
            "tool_input": {"command": f"cd {site} && git push origin main"},
            "cwd": site}
    check("site push without ledger -> block", invoke(push), 2)
    check("non-site push -> allow",
          invoke({"tool_name": "Bash",
                  "tool_input": {"command": "git push origin main"},
                  "cwd": other}), 0)
    check("plain command -> allow",
          invoke({"tool_name": "Bash", "tool_input": {"command": "ls"},
                  "cwd": site}), 0)
    write_ledger()
    def clear_recency() -> None:
        import shutil
        shutil.rmtree(os.path.join(tmp, "last-publish"), ignore_errors=True)

    check("fresh matching ledger -> allow", invoke(push), 0)
    check("ledger consumed (second push blocks)", invoke(push), 2)
    # Rapid-redeploy brake: the allow above stamped recency for this repo.
    write_ledger()
    check("in-window plain ledger -> brake blocks", invoke(push), 2)
    write_ledger(rapid_redeploy=True,
                 rapid_redeploy_quote="yes, go again right now")
    check("in-window quoted rapid ledger -> allow", invoke(push), 0)
    clear_recency()
    write_ledger(repo=other)
    check("wrong-repo ledger -> block", invoke(push), 2)
    write_ledger(created_at="2020-01-01T00:00:00+00:00")
    check("stale ledger -> block", invoke(push), 2)
    write_ledger(head_sha="0" * 40)
    check("HEAD-moved ledger -> block", invoke(push), 2)
    write_ledger(approved_via="assumed")
    check("wrong approved_via -> block", invoke(push), 2)
    wr = {"tool_name": "Bash",
          "tool_input": {"command": f"cd {site} && wrangler pages deploy dist "
                                    "--project-name=x"},
          "cwd": site}
    check("wrangler deploy without ledger -> block", invoke(wr), 2)
    write_ledger()
    clear_recency()  # independent scenario: outside any rapid window
    check("wrangler deploy with ledger -> allow", invoke(wr), 0)
    bad_env = dict(env)
    bad_env["PUBLISH_GUARD_CONFIG"] = os.path.join(tmp, "missing.json")
    proc = subprocess.run([sys.executable, me, "--gate"],
                          input=json.dumps(push), capture_output=True,
                          text=True, env=bad_env)
    check("missing config + push-shaped command -> block (fail closed)",
          proc.returncode, 2)
    proc = subprocess.run(
        [sys.executable, me, "--gate"],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "echo hi"}, "cwd": tmp}),
        capture_output=True, text=True, env=bad_env)
    check("missing config + harmless command -> allow", proc.returncode, 0)
    approve_proc = subprocess.run(
        [sys.executable, me, "--approve", site, "--summary", "test via cli"],
        capture_output=True, text=True, env=env)
    check("--approve writes a ledger", approve_proc.returncode, 0)
    clear_recency()  # independent scenario: outside any rapid window
    check("cli-approved push -> allow", invoke(push), 0)
    rapid_refused = subprocess.run(
        [sys.executable, me, "--approve", site, "--rapid-redeploy",
         "--summary", "no quote supplied"],
        capture_output=True, text=True, env=env)
    check("--rapid-redeploy without --quote refused",
          rapid_refused.returncode, 2)

    linked = os.path.join(tmp, "linked candidate")
    subprocess.run(["git", "-C", site, "worktree", "add", "-q", "-b", "candidate", linked], check=True)
    linked_push = {"tool_name": "exec_command", "cwd": other,
                   "tool_input": {"cmd": f"cd {shlex.quote(linked)} && git push origin HEAD:main"}}
    local_approval = Path(tmp) / "approval.json"
    if local_approval.exists():
        local_approval.unlink()
    check("linked Codex push without approval blocks", invoke(linked_push), 2)
    clear_recency()
    approved_link = subprocess.run([sys.executable, me, "--approve", linked, "--summary", "fixture"],
                                   capture_output=True, text=True, env=env)
    check("linked approval accepted", approved_link.returncode, 0)
    check("linked Codex matching approval consumed", invoke(linked_push), 0)
    check("linked approval cannot replay", invoke(linked_push), 2)
    clear_recency()
    write_ledger()
    double_push = dict(push, tool_input={"command": push["tool_input"]["command"] + " && git push origin main"})
    check("one approval cannot cover two pushes", invoke(double_push), 2)
    check("raw Worker deployment blocked", invoke({"tool_name": "Bash", "cwd": site,
          "tool_input": {"command": f"cd {site} && wrangler deploy index.js"}}), 2)

    failures = [r for r in results if not r[0]]
    print(f"{len(results) - len(failures)}/{len(results)} passed")
    return 0 if not failures else 2


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] == "--gate":
        return gate()
    if argv[0] in ("--approve-deployment", "--consume-deployment", "--check-deployment"):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument(argv[0], required=True)
        parser.add_argument("--summary", default="")
        parser.add_argument("--quote", default="")
        parser.add_argument("--rapid-redeploy", action="store_true")
        parsed = vars(parser.parse_args(argv))
        path = parsed[argv[0][2:].replace("-", "_")]
        if argv[0] == "--approve-deployment":
            return approve_deployment(path, parsed["summary"], parsed["quote"], parsed["rapid_redeploy"])
        return consume_deployment(path, peek=argv[0] == "--check-deployment")
    if argv[0] == "--approve":
        repo = argv[1] if len(argv) > 1 else ""
        summary = ""
        if "--summary" in argv:
            summary = " ".join(argv[argv.index("--summary") + 1:])
        rapid = "--rapid-redeploy" in argv
        quote = ""
        if "--quote" in argv:
            start = argv.index("--quote") + 1
            end = argv.index("--summary") if "--summary" in argv else len(argv)
            quote = " ".join(argv[start:end])
        return approve(repo, summary, rapid_redeploy=rapid, quote=quote)
    if argv[0] == "--doctor":
        return run_doctor()
    if argv[0] == "--test":
        return run_tests()
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
