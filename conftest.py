"""Two rules for the whole test run, core and skills alike.

An interpreter may keep its compiled code under one folder of the person's own instead of beside each source file:
Apple's Python does, under ~/Library/Caches. The installer compiles a runtime where the interpreter that installs
looks for compiled code, and a test's runtime lives in a temporary folder, so under such an interpreter every test
that installs would leave compiled files for a path that no longer exists in the person's cache. This run keeps its
compiled code under a temporary folder of its own instead: this process, and each one started with its environment.

A rituals state folder named in the shell that starts the run is the person's own, with their config in it. No
test reads it: the name is taken out before each test, and a test that needs one names its own (2026-11-13, a
review: sixteen core tests failed under such a shell, and a skill's test read the config it found there).
"""
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def no_rituals_folder_from_the_shell(monkeypatch):
    monkeypatch.delenv("RITUAL_STATE_DIR", raising=False)


@pytest.fixture(scope="session", autouse=True)
def compiled_code_stays_in_the_run(tmp_path_factory):
    if not sys.pycache_prefix:  # beside the source: a test's files are in its own temporary folder already
        yield
        return
    folder, before, named = str(tmp_path_factory.mktemp("compiled")), sys.pycache_prefix, os.environ.get("PYTHONPYCACHEPREFIX")
    sys.pycache_prefix = os.environ["PYTHONPYCACHEPREFIX"] = folder
    yield
    sys.pycache_prefix = before
    if named is None:
        os.environ.pop("PYTHONPYCACHEPREFIX", None)
    else:
        os.environ["PYTHONPYCACHEPREFIX"] = named
