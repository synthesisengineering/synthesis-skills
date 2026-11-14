"""Where the published tree comes from, and the library that keeps the last good copy serving.

GitSource asks the remote for its head (`git ls-remote`) and, only when that changed, makes a
fresh shallow clone into a new snapshot folder beside the one being served. The new copy replaces
the old only after it loads; the old folder is removed then. A failed check, clone or load leaves
the last good copy serving and shows in health(); a commit whose content would not load is not
cloned again until the remote moves. An SSH remote needs a deploy key file and known-hosts lines:
the key is copied to a private 0600 file (a secret the platform mounts may be readable by others)
and host keys are checked strictly. Git never runs hooks here. DirectorySource serves a local
folder, reread on every refresh, for tests and local runs.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
from collections import namedtuple
from pathlib import Path

from .corpus import Corpus
from .search import Index

LOG = logging.getLogger("kb_connector")
SNAPSHOT = re.compile(r"snapshot-[0-9a-f]{12}-\d+")
GIT_TIMEOUT = 300
Snapshot = namedtuple("Snapshot", "commit corpus index root")


class SourceError(Exception):
    """The source could not be read; the message carries no credentials."""


def scrub(text: str) -> str:
    """Error text safe to log: user:password@ removed from URLs, cut to 500 characters."""
    return re.sub(r"(\w+://)[^/@\s]+@", r"\1", text or "").strip()[:500]


def is_ssh(url: str) -> bool:
    return url.startswith("ssh://") or bool(re.match(r"^[\w.-]+@[\w.-]+:", url))


class DirectorySource:
    def __init__(self, path):
        self.root = Path(path).resolve()

    def head(self) -> str:
        return ""  # no cheap head to compare: a folder is reread on every refresh

    def fetch(self, head: str):
        """(the folder's git commit, or '' when it is not a checkout; the folder)."""
        if not self.root.is_dir():
            raise SourceError(f"KB_SOURCE_DIR {self.root} is not a folder")
        done = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"], capture_output=True, text=True)
        return (done.stdout.strip() if done.returncode == 0 else ""), self.root

    def discard(self, keep) -> None:
        """Nothing to remove: the folder is never copied."""


class GitSource:
    def __init__(self, url: str, workdir, branch: str = "", ssh_key_file: str = "", known_hosts: str = ""):
        self.url, self.branch = url, branch
        self.workdir = Path(workdir).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        if is_ssh(url):
            if not ssh_key_file or not known_hosts.strip():
                raise SourceError("an SSH remote needs KB_GIT_SSH_KEY_FILE and KB_GIT_KNOWN_HOSTS")
            private = self.workdir / ".ssh"
            private.mkdir(mode=0o700, exist_ok=True)
            os.chmod(private, 0o700)
            key, hosts = private / "deploy_key", private / "known_hosts"
            try:
                material = Path(ssh_key_file).read_text(encoding="utf-8")
            except OSError as error:
                raise SourceError(f"cannot read KB_GIT_SSH_KEY_FILE: {error.strerror}") from None
            fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(material.rstrip("\n") + "\n")  # ssh rejects a key without its final newline
            hosts.write_text(known_hosts.strip() + "\n", encoding="utf-8")
            self.env["GIT_SSH_COMMAND"] = " ".join(["ssh", "-i", shlex.quote(str(key)), "-o", "IdentitiesOnly=yes",
                                                    "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                                                    "-o", "UserKnownHostsFile=" + shlex.quote(str(hosts))])

    def _git(self, *args, cwd=None) -> str:
        try:
            done = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd, env=self.env,
                                  capture_output=True, text=True, timeout=GIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise SourceError(f"git {args[0]} timed out after {GIT_TIMEOUT} s") from None
        if done.returncode != 0:
            raise SourceError(f"git {args[0]} failed: {scrub(done.stderr) or done.returncode}")
        return done.stdout

    def head(self) -> str:
        """The commit the remote's branch (or default branch) points at now."""
        out = self._git("ls-remote", "--exit-code", self.url, f"refs/heads/{self.branch}" if self.branch else "HEAD")
        sha = out.split()[0] if out.split() else ""
        if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
            raise SourceError("git ls-remote returned no commit")
        return sha

    def fetch(self, head: str):
        """A shallow clone of the newest commit in a new snapshot folder: (commit, folder)."""
        target = self.workdir / f"snapshot-{head[:12]}-{time.time_ns()}"
        branch = ["--branch", self.branch] if self.branch else []
        try:
            self._git("clone", "--quiet", "--depth", "1", "--single-branch", "--no-tags", *branch, "--", self.url,
                      str(target))
            return self._git("rev-parse", "HEAD", cwd=target).strip(), target
        except SourceError:
            self._remove(target)
            raise

    def _remove(self, folder: Path) -> None:
        """Delete one snapshot folder: only a direct child of the work folder, named like a snapshot."""
        if folder.parent == self.workdir and SNAPSHOT.fullmatch(folder.name) and folder.is_dir() \
                and not folder.is_symlink():
            shutil.rmtree(folder)

    def discard(self, keep) -> None:
        """Remove every snapshot folder except `keep` (all of them when keep is None)."""
        for child in list(self.workdir.iterdir()):
            if child != keep:
                self._remove(child)


class Library:
    """The snapshot being served: commit, corpus, index and folder, swapped whole by refresh()."""

    def __init__(self, source, references_path: str = "", clock=time.time):
        self.source, self.references_path, self.clock = source, references_path, clock
        self.current = None
        self.refreshed_at = self.attempted_at = None
        self.last_error = self.failed_head = ""
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def refresh(self) -> bool:
        """Serve the newest copy that loads; on any failure keep the last good one. True when serving."""
        with self._lock:
            self.attempted_at = self.clock()
            try:
                head = self.source.head()
                if head and self.current and head == self.current.commit:
                    self.refreshed_at, self.last_error = self.attempted_at, ""
                elif not (head and head == self.failed_head):
                    commit, root = self.source.fetch(head)
                    try:
                        corpus = Corpus.load(root, self.references_path)
                        loaded = Snapshot(commit, corpus, Index(corpus.documents.values()), root)
                    except Exception:
                        self.failed_head = head
                        self.source.discard(self.current.root if self.current else None)
                        raise
                    self.current, self.failed_head = loaded, ""
                    self.source.discard(root)
                    self.refreshed_at, self.last_error = self.attempted_at, ""
                    LOG.info("serving %d documents from commit %s", len(corpus), commit[:12] or "(no git checkout)")
            except Exception as error:  # noqa: BLE001 - any failure keeps the last good copy serving
                self.last_error = scrub(str(error)) or type(error).__name__
                LOG.error("refresh failed (%s): %s", "last good copy kept" if self.current else "nothing to serve",
                          self.last_error)
            return self.current is not None

    def start(self, interval: float) -> None:
        """Refresh every `interval` seconds on a daemon thread; 0 or less never refreshes."""
        if interval <= 0 or self._thread:
            return

        def loop():
            while not self._stop.wait(interval):
                self.refresh()
        self._thread = threading.Thread(target=loop, name="kb-refresh", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def health(self) -> dict:
        snap = self.current
        stamp = lambda t: None if t is None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))  # noqa: E731
        return {"status": "ok" if snap else "unavailable", "commit": (snap.commit or None) if snap else None,
                "files": len(snap.corpus) if snap else 0, "refreshed_at": stamp(self.refreshed_at),
                "last_attempt_at": stamp(self.attempted_at), "last_refresh_failed": bool(self.last_error)}
