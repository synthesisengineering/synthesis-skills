"""Small package-owned acquisition command. Installation has no side effects."""
import hashlib
import json
import os
from pathlib import Path
import sys
import re
import importlib.util
import argparse


def main():
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / "release.json").read_text())
    if (metadata.get("schema_version") != 1
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", str(metadata.get("version", "")))
            or not re.fullmatch(r"[0-9a-f]{40}", str(metadata.get("commit", "")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(metadata.get("bootstrap_sha256", "")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(metadata.get("source_content_digest", "")))):
        raise ValueError("package release metadata is invalid")
    args = sys.argv[1:]
    if args[:1] == ["stage-core"] and "--no-dormant-core" in args:
        # Declining optional staging needs neither an ecosystem runtime nor
        # acquisition. Do not inspect or mutate another selection's receipts.
        parser = argparse.ArgumentParser(prog="synthesis stage-core", allow_abbrev=False)
        parser.add_argument("--for-tool", required=True, choices=("slopcheck", "console", "ownwords"))
        parser.add_argument("--no-dormant-core", action="store_true", required=True)
        parser.add_argument("--json", action="store_true")
        choice = parser.parse_args(args[1:])
        print(json.dumps({"status": "PASS", "tool": choice.for_tool, "core_state": "declined",
                          "optional_core_bytes": 0, "payload": None,
                          "detail": "No acquisition or state changes. Existing staged core and receipts remain preserved."}))
        return 0
    if args == ["--version"]:
        print("synthesis " + metadata["version"])
        return 0
    if not args or "--help" in args or "-h" in args:
        print("Synthesis installation and lifecycle\n\n"
              "  synthesis setup --profile full|skills-only\n"
              "  synthesis setup --profile modular --skill NAME [--no-dormant-core]\n"
              "  synthesis activate --profile full|skills-only\n"
              "  synthesis deactivate\n"
              "  synthesis stage-core --for-tool slopcheck|console|ownwords [--no-dormant-core]\n"
              "  synthesis doctor|status|repair|update|enroll|uninstall\n\n"
              "Package installation is inert. Run setup to configure an environment.\n"
              "Python 3.12–3.14 and Git are required. No telemetry or automatic updates.")
        return 0
    environment = dict(os.environ)
    environment["SYNTHESIS_RUNTIME_POLICY"] = "packaged-python-v1"
    environment["SYNTHESIS_BOOTSTRAP_PYTHON"] = sys.executable
    home = Path(environment.get("SYNTHESIS_HOME", str(Path.home())))
    data = Path(environment.get("XDG_DATA_HOME", str(home / ".local/share")))
    managed = data / "synthesis/bin"
    environment["SYNTHESIS_INSTALL_BIN_DIR"] = str(managed)
    active = Path(environment.get("SYNTHESIS_ACTIVE_DESCRIPTOR", str(Path(environment.get("XDG_STATE_HOME", str(home / ".local/state"))) / "synthesis/active-release.json")))
    if args[0] == "activate" and not active.exists():
        state = Path(environment.get("XDG_STATE_HOME", str(home / ".local/state"))) / "synthesis"
        spec = importlib.util.spec_from_file_location("package_release_verifier", root / "release_runtime.py")
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        for receipt in sorted((state / "modular/tools").glob("*.json")):
            if receipt.is_symlink():
                raise ValueError("tool receipt must be a regular file")
            value = json.loads(receipt.read_text())
            descriptor = value.get("release_descriptor")
            if not value.get("stage_core") or not descriptor:
                continue
            if descriptor.get("commit") != metadata["commit"] or descriptor.get("version") != metadata["version"]:
                continue
            payload = Path(value["payload"])
            if not payload.is_absolute() or payload.is_symlink() or not payload.is_dir() or payload.resolve() != payload:
                raise ValueError("staged core path is invalid")
            if (descriptor.get("content_digest") != metadata["source_content_digest"]
                    or verifier.tree_digest(payload) != metadata["source_content_digest"]):
                raise ValueError("staged core differs from the immutable package source")
            environment["SYNTHESIS_ONBOARD_EXPECTED_COMMIT"] = metadata["commit"]
            os.execve(sys.executable, [sys.executable, "-B", str(payload / "skills/synthesis-onboarding/scripts/bootstrap.py"),
                "--checkout", str(payload), "--source-descriptor", str(receipt),
                "--releases-dir", str(Path(environment.get("XDG_CACHE_HOME", str(home / ".cache"))) / "synthesis/releases"),
                "--launcher", str(managed / "synthesis"), "--active-descriptor", str(active),
                "--channel", descriptor["channel"], "--ref", descriptor["ref"],
                "--source-url", descriptor["source_url"], "--", *args], environment)
        # Opt-out deliberately has no cached core. Explicit activation may
        # acquire it, still pinned to this package's reviewed release.
        environment["SYNTHESIS_ONBOARD_VERSION_PIN"] = metadata["version"]
        acquisition = True
    else:
        acquisition = args[0] in {"setup", "stage-core"}
    if not acquisition and active.exists():
        if active.is_symlink() or not active.is_file():
            raise ValueError("active descriptor must be a regular file")
        # A mutable path/hash pair cannot authorize executable launcher bytes.
        # Enter through the package-owned verifier, which checks the complete
        # active generation and dispatches its declared CLI itself.
        spec = importlib.util.spec_from_file_location("package_release_verifier", root / "release_runtime.py")
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        os.environ.update(environment)
        return verifier.launcher_main(active, args)
    if not acquisition:
        print("Synthesis is not configured. Run synthesis setup --profile full or --profile skills-only.", file=sys.stderr)
        return 2
    bootstrap = root / "onboard.sh"
    if bootstrap.is_symlink() or hashlib.sha256(bootstrap.read_bytes()).hexdigest() != metadata["bootstrap_sha256"]:
        raise ValueError("packaged bootstrap integrity check failed; reinstall the package")
    # Package release pins are exact. Changing release policy is an explicit
    # lifecycle operation after setup, not mutable execution during acquisition.
    if any(value == "--pin" or value.startswith("--pin=") for value in args):
        raise ValueError("this package pins release %s; select another package version to change it" % metadata["version"])
    environment["SYNTHESIS_ONBOARD_EXPECTED_COMMIT"] = metadata["commit"]
    forwarded = [*args, "--pin", metadata["version"]] if args[0] in {"setup", "stage-core"} else args
    os.execve("/bin/sh", ["/bin/sh", str(bootstrap), *forwarded], environment)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Synthesis package refused: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
