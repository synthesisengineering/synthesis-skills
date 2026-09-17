#!/bin/sh
# The package owns acquisition; only an explicit setup command changes a user environment.
set -eu
PACKAGE_BIN=$0
while [ -L "$PACKAGE_BIN" ]; do
  LINK=$(readlink "$PACKAGE_BIN")
  case "$LINK" in /*) PACKAGE_BIN=$LINK ;; *) PACKAGE_BIN=$(dirname "$PACKAGE_BIN")/$LINK ;; esac
done
PACKAGE_ROOT=$(CDPATH= cd -- "$(dirname "$PACKAGE_BIN")/.." && pwd)
PYTHON_CHECK='import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,12),(3,13),(3,14)) else 1)'
CANDIDATES='python3.12 python3.13 python3.14 python3'
if [ "${1:-}" = stage-core ]; then
  for ARGUMENT in "$@"; do
    if [ "$ARGUMENT" = --no-dormant-core ]; then
      PYTHON_CHECK='import sys; raise SystemExit(0 if (3,9) <= sys.version_info[:2] < (4,0) else 1)'
      CANDIDATES='python3 python3.12 python3.13 python3.14 python3.9 python3.10 python3.11'
      break
    fi
  done
fi
if [ -n "${SYNTHESIS_BOOTSTRAP_PYTHON:-}" ]; then
  PYTHON=$SYNTHESIS_BOOTSTRAP_PYTHON
  case "$PYTHON" in /*) ;; *) echo 'SYNTHESIS_BOOTSTRAP_PYTHON must be an absolute executable path.' >&2; exit 2 ;; esac
else
  PYTHON=
  for CANDIDATE in $CANDIDATES; do
    if command -v "$CANDIDATE" >/dev/null 2>&1 && "$CANDIDATE" -I -B -c "$PYTHON_CHECK" >/dev/null 2>&1; then
      PYTHON=$(command -v "$CANDIDATE")
      break
    fi
  done
fi
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ] || ! "$PYTHON" -I -B -c "$PYTHON_CHECK" >/dev/null 2>&1; then
  echo 'Synthesis requires Python 3.12, 3.13 or 3.14 and Git. Install these prerequisites, then run setup.' >&2
  exit 2
fi
exec "$PYTHON" -I -B "$PACKAGE_ROOT/lib/package_launcher.py" "$@"
