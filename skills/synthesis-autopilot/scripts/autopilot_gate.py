#!/usr/bin/env python3
"""Native Stop entry point for durable autopilot runs.

State mutations belong to autopilot.py and its authenticated transaction API.
Legacy records are preserved and explicitly imported, never silently reprofiled.
This entry point is retained because native hook registrations address it.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

ENGINE_VERSION = "2.0.0"
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else "--gate"
    if mode in {"--gate", "--combined-stop"}:
        try:
            if mode == "--combined-stop":
                import native_stop
                return native_stop.main()
            import autopilot
            return autopilot.main(["stop"])
        except Exception as exc:
            # Infrastructure failure ends this attempted turn but does not
            # erase obligations or authorize any protected mutation.
            reason = "UNRESOLVED: autopilot lifecycle helper is unavailable: " + str(exc)
            print(json.dumps({"continue": False, "stopReason": reason, "systemMessage": reason}))
            return 0
    if mode == "--doctor":
        import autopilot
        return autopilot.main(["doctor"])
    if mode in {"--help", "-h"}:
        print(__doc__)
        print("Use autopilot.py create/command/status/import/explain/doctor for durable execution.")
        return 0
    print("autopilot_gate: attestation-only legacy mutations are retired. Use autopilot.py import "
          "to preserve and convert your owned legacy run, or autopilot.py create for a new "
          "outcome contract; then use typed commands with current native claim, revision and command ID.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
