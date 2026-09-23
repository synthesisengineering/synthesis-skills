"""Publish-guard promotion tests: resolve the guard from the skill layout.

The guard lives in guards/ while its tests live in tests/; this makes
`import publish_guard` work for test modules that bind the guard as a
plain module instead of loading it by file location.
"""
import sys
from pathlib import Path

GUARDS = Path(__file__).resolve().parent.parent / "guards"
if str(GUARDS) not in sys.path:
    sys.path.insert(0, str(GUARDS))
