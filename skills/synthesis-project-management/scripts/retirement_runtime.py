"""Retain the source-selected coordination runtime across worktree deletion.

This extends retire_worktree's existing digest-addressed runtime store. Its
closed coordination dependency set is checked against runtime_payload's existing
git-hooks payload owner; no installed or unrelated checkout is a fallback.
The coordination owner alone authenticates and mutates claims.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
import types
from pathlib import Path

COORDINATION_SCRIPTS = (
    "coordination.py", "claim_scope.py", "native_git.py", "coordination_schema.py",
    "board_grammar.py",
    "team_contract.py", "native_identity.py", "coordination_archive.py", "pointer_lock.py", "peer_addressing.py",
    "fleet_identity.py", "fleet_paths.py", "fleet_bootstrap.py", "fleet_doctor.py",
    "fleet_handoff.py", "fleet_logical.py", "fleet_subscriptions.py", "coordination_process.py", "coordination_lock.py", "project_recipient.py",
    "run_admission.py", "project_state.py", "plan_reference.py",
)
# Stdlib-only modules the coordination closure imports from the conformance skill.
CONFORMANCE_SCRIPTS = ("native_transcript_identity.py", "client_binaries.py", "yaml_runtime.py")
# Cross-skill registry intent readers are executable dependencies of coordination.
# Keep source paths explicit; no installed cache or source-name guessing is used.
CROSS_SKILL_SOURCES = {
    "context_currency.py": "synthesis-context-lifecycle/scripts/context_currency.py",
    "context_edit.py": "synthesis-context-lifecycle/scripts/context_edit.py",
    "record_succession.py": "synthesis-context-lifecycle/scripts/record_succession.py",
    "record_transaction.py": "synthesis-context-lifecycle/scripts/record_transaction.py",
    "build_packet.py": "synthesis-decision-packet/scripts/build_packet.py",
    "record_rulings.py": "synthesis-decision-packet/scripts/record_rulings.py",
    "release_runtime.py": "synthesis-onboarding/scripts/release_runtime.py",
    "publication_receipt.py": "synthesis-repo-guard/publication_receipt.py",
}
YAML_SCRIPTS = ("__init__.py", "composer.py", "constructor.py", "cyaml.py", "dumper.py",
                "emitter.py", "error.py", "events.py", "loader.py", "nodes.py", "parser.py",
                "reader.py", "representer.py", "resolver.py", "scanner.py", "serializer.py", "tokens.py")
MEMBERS = tuple("scripts/" + name for name in COORDINATION_SCRIPTS + CONFORMANCE_SCRIPTS) + (
    *("scripts/" + name for name in CROSS_SKILL_SOURCES),
    *("scripts/yaml/" + name for name in YAML_SCRIPTS),
    "references/session-words-v1.txt.zlib.b85",
    "references/pyyaml-manifest.json", "references/pyyaml-LICENSE",
)
MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
INVOKE_TIMEOUT = 60
INVOKE_OUTPUT_BYTES = 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def safe_path(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"retirement runtime path is a symlink: {part}")
    return path


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_regular(path, *, limit=MAX_FILE):
    path = safe_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                or before.st_nlink != 1 or before.st_mode & 0o022
                or not before.st_mode & 0o400 or before.st_size > limit):
            raise ValueError(f"unsafe or oversized retirement runtime member: {path}")
        content = bytearray()
        while len(content) <= limit:
            chunk = os.read(descriptor, min(65536, limit + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        if (len(content) > limit or identity(before) != identity(os.fstat(descriptor))
                or identity(before) != identity(path.lstat())):
            raise ValueError(f"retirement runtime member changed during read: {path}")
        safe_path(path)
        return bytes(content)
    finally:
        os.close(descriptor)


def source_storage_detail(source, worktree, entry, reason):
    """Use the exact fleet owner without writing bytecode into retiring source."""
    path = Path(source) / "scripts/fleet_paths.py"
    content = read_regular(path)
    name = "_synthesis_retirement_storage_owner"
    module = types.ModuleType(name)
    module.__file__ = str(path)
    previous = sys.modules.get(name)
    # Dataclass annotation processing needs its module during definition.
    # Neither a normal import nor its pyc cache is used for source ownership.
    sys.modules[name] = module
    try:
        exec(compile(content, str(path), "exec"), module.__dict__)
        return module.missing_worktree_detail(worktree, entry, reason)
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous


def fsync_directory(path):
    descriptor = os.open(safe_path(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_directory(path):
    info = safe_path(path).lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError(f"unsafe retirement runtime directory: {path}")


def verify(store, digest, *, snapshot=False):
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("invalid retained coordination runtime digest")
    root = safe_path(store) / ("coordination-" + digest)
    validate_directory(store)
    validate_directory(root)
    manifest_bytes = read_regular(root / "MANIFEST.json", limit=65536)
    if hashlib.sha256(manifest_bytes).hexdigest() != digest:
        raise ValueError("retained coordination runtime manifest changed")
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "files"} or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("invalid retained coordination manifest")
    files = manifest["files"]
    if not isinstance(files, dict) or set(files) != set(MEMBERS):
        raise ValueError("retained coordination runtime dependency set changed")
    expected = {"": {"MANIFEST.json", "scripts", "references"},
                "scripts": set(COORDINATION_SCRIPTS) | set(CONFORMANCE_SCRIPTS) | set(CROSS_SKILL_SOURCES) | {"yaml"},
                "scripts/yaml": set(YAML_SCRIPTS),
                "references": {"session-words-v1.txt.zlib.b85", "pyyaml-manifest.json", "pyyaml-LICENSE"}}
    total = 0
    for relative, names in expected.items():
        directory = root / relative
        validate_directory(directory)
        seen = set()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name not in names or len(seen) >= len(names):
                    raise ValueError("unexpected retained runtime member")
                seen.add(entry.name)
        if seen != names:
            raise ValueError("retained coordination runtime dependency is missing")
    contents = {}
    for relative in MEMBERS:
        content = read_regular(root / relative)
        contents[relative] = content
        total += len(content)
        if total > MAX_TOTAL or files[relative] != {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}:
            raise ValueError(f"retained coordination runtime content changed: {relative}")
    if snapshot:
        return root, manifest_bytes, contents
    return root / "scripts/coordination.py"


def source_member(source, relative):
    name = relative.removeprefix("scripts/")
    if name in CONFORMANCE_SCRIPTS:
        return source.parent / "synthesis-agent-conformance/scripts" / name
    if name in CROSS_SKILL_SOURCES:
        return source.parent / CROSS_SKILL_SOURCES[name]
    if relative.startswith("scripts/yaml/"):
        return source.parent / "synthesis-agent-conformance/vendor/pyyaml" / name
    if relative in {"references/pyyaml-manifest.json", "references/pyyaml-LICENSE"}:
        return source.parent / "synthesis-agent-conformance/vendor/pyyaml" / relative.removeprefix("references/pyyaml-")
    return source / relative


def stage(source, store):
    source, store = safe_path(source), safe_path(store)
    store.mkdir(parents=True, exist_ok=True, mode=0o700)
    validate_directory(store)
    # Reuse the release-owned dependency verifier before retaining its bytes.
    # The retained executor subsequently consumes only its immutable snapshot.
    yaml_path = source_member(source, "scripts/yaml_runtime.py")
    yaml_module = types.ModuleType("_retirement_yaml_owner")
    yaml_module.__file__ = str(yaml_path)
    exec(compile(read_regular(yaml_path), str(yaml_path), "exec"), yaml_module.__dict__)
    yaml_contents = yaml_module.verified_bytes(source.parent / "synthesis-agent-conformance/vendor/pyyaml")
    contents = {}
    total = 0
    for relative in MEMBERS:
        content = read_regular(source_member(source, relative))
        total += len(content)
        if total > MAX_TOTAL:
            raise ValueError("retirement runtime source exceeds aggregate capacity")
        contents[relative] = content
    if any(read_regular(source_member(source, key)) != content for key, content in contents.items()):
        raise ValueError("coordination source changed while staging")
    for key, data in yaml_contents.items():
        retained = "references/pyyaml-LICENSE" if key == "LICENSE" else "scripts/" + key
        if contents[retained] != data:
            raise ValueError("release-owned YAML changed while retaining its bytes")
    if hashlib.sha256(contents["references/pyyaml-manifest.json"]).hexdigest() != yaml_module.MANIFEST_SHA256:
        raise ValueError("release-owned YAML manifest changed while retaining its bytes")
    manifest = {"schema_version": 1, "files": {
        key: {"sha256": hashlib.sha256(value).hexdigest(), "size": len(value)}
        for key, value in contents.items()
    }}
    manifest_bytes = canonical(manifest)
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    destination = store / ("coordination-" + digest)
    if destination.exists() or destination.is_symlink():
        verify(store, digest)
        return digest
    temporary = Path(tempfile.mkdtemp(prefix=".coordination-", dir=store))
    for relative, content in {**contents, "MANIFEST.json": manifest_bytes}.items():
        target = temporary / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fchmod(handle.fileno(), 0o400)
            os.fsync(handle.fileno())
    for directory in (temporary / "scripts/yaml", temporary / "scripts", temporary / "references", temporary):
        fsync_directory(directory)
    # Interrupted staging directories are retained evidence; never resumed or
    # selected as runtime. The digest-addressed complete directory alone is used.
    os.rename(temporary, destination)
    fsync_directory(store)
    verify(store, digest)
    return digest


def process_owner(executable, digest):
    """Load the exact retained dependency without imports from a deleted tree.

    Verify the bytes that will execute against the intent-bound manifest again;
    a pathname check before reading code is not sufficient against replacement.
    compile/exec avoids bytecode writes and ambient module-cache substitution.
    """
    root = executable.parent.parent
    manifest_bytes = read_regular(root / "MANIFEST.json", limit=65536)
    if hashlib.sha256(manifest_bytes).hexdigest() != digest:
        raise ValueError("retained coordination runtime manifest changed")
    expected = json.loads(manifest_bytes)["files"]["scripts/coordination_process.py"]
    path = root / "scripts/coordination_process.py"
    content = read_regular(path)
    if expected != {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}:
        raise ValueError("retained process owner changed before execution")
    module = types.ModuleType("retirement_coordination_process")
    module.__file__ = str(path)
    exec(compile(content, str(path), "exec"), module.__dict__)
    return module


# This follows the existing yaml_runtime verified in-memory module loader pattern.
# The child never reopens retained code or resources after their byte snapshot.
_EXECUTOR = r"""
import hashlib, importlib.abc, importlib.util, json, os, stat, sys, types
fd, digest, wire_digest, limit, root = sys.argv[1:6]
fd, limit = int(fd), int(limit)
info = os.fstat(fd)
if not stat.S_ISREG(info.st_mode) or info.st_size > limit or info.st_nlink != 0:
    raise ValueError('invalid retained runtime byte transport')
with os.fdopen(fd, 'rb', closefd=True) as stream:
    wire = stream.read(limit + 1)
if len(wire) > limit or hashlib.sha256(wire).hexdigest() != wire_digest:
    raise ValueError('retained runtime byte transport changed')
value = json.loads(wire)
manifest_bytes = bytes.fromhex(value['manifest'])
if hashlib.sha256(manifest_bytes).hexdigest() != digest:
    raise ValueError('retained runtime manifest binding changed')
manifest = json.loads(manifest_bytes)
contents = {name: bytes.fromhex(data) for name, data in value['files'].items()}
if set(contents) != set(manifest['files']):
    raise ValueError('retained runtime snapshot members changed')
for name, data in contents.items():
    if manifest['files'][name] != {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}:
        raise ValueError('retained runtime snapshot member changed')
modules = {(name.removeprefix('scripts/').removesuffix('/__init__.py').removesuffix('.py').replace('/', '.')): name
           for name in contents if name.startswith('scripts/') and name.endswith('.py')}
isolated_search_path = tuple(sys.path)
class VerifiedModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'yaml.cyaml', 'yaml._yaml'}:
            raise ModuleNotFoundError('retained runtime permits release-owned pure Python YAML only')
        if fullname not in modules:
            # Admitted scripts may insert their historical source directory.
            # A late unlisted file there must not shadow standard-library code.
            sys.path[:] = isolated_search_path
            return None
        return importlib.util.spec_from_loader(fullname, self,
             origin=os.path.join(root, modules[fullname]), is_package=fullname == 'yaml')
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        filename = os.path.join(root, modules[module.__name__])
        module.__file__ = filename
        exec(compile(contents[modules[module.__name__]], filename, 'exec'), module.__dict__)
    def get_data(self, path):
        relative = os.path.relpath(path, root)
        if relative != 'references/session-words-v1.txt.zlib.b85':
            raise OSError('resource is outside the admitted runtime byte snapshot')
        return contents[relative]
loader = VerifiedModules()
sys.meta_path.insert(0, loader)
filename = os.path.join(root, 'scripts/coordination.py')
sys.argv = [filename, *sys.argv[6:]]
main = types.ModuleType('__main__')
main.__file__, main.__loader__ = filename, loader
main.__package__, main.__spec__ = None, None
sys.modules['__main__'] = main
exec(compile(contents['scripts/coordination.py'], filename, 'exec'), main.__dict__)
"""


def invoke(store, digest, board, arguments):
    executable = verify(store, digest)
    bounded = process_owner(executable, digest)
    root, manifest, contents = verify(store, digest, snapshot=True)
    wire = canonical({"manifest": manifest.hex(), "files": {
        name: data.hex() for name, data in contents.items()
    }})
    limit = 2 * MAX_TOTAL + 2 * 65536
    if len(wire) > limit:
        raise ValueError("retained runtime byte transport exceeds capacity")
    # Anonymous descriptor custody keeps the admitted bytes separate from their
    # replaceable source paths. -I -B and the shared process owner remain active.
    with tempfile.TemporaryFile(mode="w+b") as snapshot:
        snapshot.write(wire)
        snapshot.flush()
        snapshot.seek(0)
        descriptor = snapshot.fileno()
        result = bounded.run(
            [sys.executable, "-I", "-B", "-c", _EXECUTOR, str(descriptor), digest,
             hashlib.sha256(wire).hexdigest(), str(limit), str(root),
             "--board", str(board), *arguments],
            cwd=executable.parent, timeout=INVOKE_TIMEOUT, output_bytes=INVOKE_OUTPUT_BYTES,
            pass_fds=(descriptor,),
        )
    verify(store, digest)
    return result


def owner(store, digest, board, session):
    result = invoke(store, digest, board, ["verify-owner", "--session", session])
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "retirement caller ownership is unverified")
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or set(data) != {"session_uuid", "native"}:
        raise ValueError("invalid coordination ownership proof")
    return data


def prepare(source, store, board):
    session = os.environ.get("SYNTHESIS_COORDINATION_SESSION", "").strip()
    if not session:
        return None
    board = safe_path(board if board is not None else Path.home() / ".synthesis/coordination/active-sessions.md")
    digest = stage(source, store)
    proof = owner(store, digest, board, session)
    return {"schema_version": 1, "sha256": digest, "board": str(board), **proof}


def authenticate(data, store, board):
    if data is None:
        if os.environ.get("SYNTHESIS_COORDINATION_SESSION", "").strip():
            raise ValueError("retirement intent has no retained claim runtime; no live-source fallback is authorized")
        return None
    if (not isinstance(data, dict) or set(data) != {"schema_version", "sha256", "board", "session_uuid", "native"}
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or not isinstance(data["board"], str) or not Path(data["board"]).is_absolute()
            or ".." in Path(data["board"]).parts
            or not isinstance(data["session_uuid"], str) or not data["session_uuid"]
            or not isinstance(data["native"], dict)):
        raise ValueError("invalid retained retirement claim binding")
    from_session = os.environ.get("SYNTHESIS_COORDINATION_SESSION", "").strip()
    if not from_session:
        raise ValueError("retirement intent requires its original authenticated claim owner")
    expected_board = safe_path(data["board"])
    if board is not None and safe_path(board) != expected_board:
        raise ValueError("retirement board differs from the pinned claim board")
    proof = owner(store, data["sha256"], expected_board, from_session)
    if proof != {"session_uuid": data["session_uuid"], "native": data["native"]}:
        raise ValueError("caller differs from the retirement intent's native owner")
    return expected_board
