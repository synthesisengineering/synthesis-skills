#!/bin/sh
# Skills-only compatibility door. New installations use the same immutable
# bootstrap and reconciler as the full system. Explicit source/target variables
# select the internal direct-copy capability used by controlled adapters/tests.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DIRECT_COPY="$ROOT/skills/synthesis-onboarding/scripts/direct_copy.sh"
COMMAND="${1:-install}"

if [ -n "${SYNTHESIS_SKILLS_SOURCE_DIR:-}" ] || [ -n "${SYNTHESIS_SKILLS_TARGETS:-}" ]; then
  exec "$DIRECT_COPY" "$@"
fi

case "$COMMAND" in
  install)
    shift || true
    exec "$ROOT/onboard.sh" setup --profile skills-only "$@"
    ;;
  update|status|uninstall)
    shift || true
    exec "$ROOT/onboard.sh" "$COMMAND" "$@"
    ;;
  *)
    echo "Usage: install.sh [install|update|status|uninstall]" >&2
    exit 2
    ;;
esac
