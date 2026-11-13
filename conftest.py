"""One rule for the whole test run, core and skills alike.

An interpreter may keep its compiled code under one folder of the person's own instead of beside each source file:
Apple's Python does, under ~/Library/Caches. The installer compiles a runtime where the interpreter that installs
looks for compiled code, and a test's runtime lives in a temporary folder, so under such an interpreter every test
that installs would leave compiled files for a path that no longer exists in the person's cache. This run keeps its
compiled code under a temporary folder of its own instead, in this process and in every process a test starts.
"""
import os
import sys

import pytest


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
