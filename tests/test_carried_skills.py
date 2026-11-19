"""BACKLOG A16: what the runtime carries is what the plugin being installed declares.

The release tool runs from the running runtime, so its installer staged the new runtime, and the release listed it, by
the running runtime's own `install.STABLE_SKILL_SCRIPTS`: 5.25.1 added synthesis-slack-sync to that list, and the 5.25.0
installer that released it left the skill out, so the doctor failed its package checks until the tag was installed
again with its own installer (2026-11-18). Now staging, the grant's spend and the release's listing all read the list
from the plugin being installed: its install.py, parsed as data and never run (`install.carried_in`).
"""
from pathlib import Path

import pytest

from synthesis import doctor, install

ROOT = Path(__file__).resolve().parents[1]


def test_this_trees_declaration_reads_back_as_the_list_it_holds():
    assert install.carried(ROOT) == install.STABLE_SKILL_SCRIPTS


def test_a_folder_with_no_install_py_carries_nothing(tmp_path):
    assert install.carried(tmp_path) == ()


@pytest.mark.parametrize("text", [
    "STABLE_SKILL_SCRIPTS = tuple(['synthesis-a'])\n",
    "STABLE_SKILL_SCRIPTS = ['synthesis-a']\n",
    "STABLE_SKILL_SCRIPTS = ()\n",
    "STABLE_SKILL_SCRIPTS = ('../synthesis-a',)\n",
    "STABLE_SKILL_SCRIPTS = ('synthesis-a/scripts',)\n",
    "STABLE_SKILL_SCRIPTS = ('.hidden',)\n",
    "STABLE_SKILL_SCRIPTS = ('synthesis-a', 'synthesis-a')\n",
    "STABLE_SKILL_SCRIPTS = ('synthesis-a',)\nSTABLE_SKILL_SCRIPTS += ('synthesis-b',)\n",
    "STABLE_SKILL_SCRIPTS = ('synthesis-a',)\nif X:\n    STABLE_SKILL_SCRIPTS = ('synthesis-b',)\n",
    "def f():\n    global STABLE_SKILL_SCRIPTS\n    STABLE_SKILL_SCRIPTS = ('synthesis-b',)\nSTABLE_SKILL_SCRIPTS = ('synthesis-a',)\n",
    "A = STABLE_SKILL_SCRIPTS = ('synthesis-a',)\n",
    "OTHER = ('synthesis-a',)\n",
    "STABLE_SKILL_SCRIPTS = (\n",
], ids=["computed", "a list", "empty", "a parent folder", "a path", "hidden", "twice", "added to", "bound in a branch",
        "bound in a function", "two targets", "not bound", "does not parse"])
def test_a_declaration_that_is_not_one_literal_tuple_of_skill_folder_names_is_refused(text):
    with pytest.raises(install.Refused, match="STABLE_SKILL_SCRIPTS|parse"):
        install.carried_in(text)


def test_a_harness_plugin_whose_declaration_cannot_be_read_fails_its_package_check(tmp_path):
    plugin = tmp_path / "plugin"
    (plugin / "synthesis").mkdir(parents=True)
    (plugin / "synthesis" / "hook.py").write_text("")
    (plugin / "synthesis" / "install.py").write_text("STABLE_SKILL_SCRIPTS = tuple()\n")
    check = doctor.check_package("claude", plugin, "0123456789abcdef")
    assert check.status == "fail" and "STABLE_SKILL_SCRIPTS" in check.detail, check
