"""Read-only Muse command grammar, never infer support from successful help fallback."""

from pathlib import Path
import importlib.util
import subprocess
import sys
import pytest

spec = importlib.util.spec_from_file_location(
    "release_contract", Path(__file__).with_name("release.py")
)
release = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release
spec.loader.exec_module(release)


def test_top_level_help_is_not_plugin_support(monkeypatch):
    generic = "Usage: muse [OPTIONS] [COMMAND]\nCommands:\n  exec\n  schema\n"
    monkeypatch.setattr(
        release,
        "bounded_run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, generic, ""),
    )
    assert release.muse_plugin_capability("/fixture/muse")["status"] == "UNAVAILABLE"


def test_plugin_help_requires_all_actual_verbs(monkeypatch):
    rows = [
        "Usage: muse [OPTIONS] [COMMAND]\nCommands:\n  plugins\n",
        "Usage: muse plugins [COMMAND]\nCommands:\n  list\n  install\n  update\n",
    ]
    monkeypatch.setattr(
        release,
        "bounded_run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, rows.pop(0), ""),
    )
    result = release.muse_plugin_capability("/fixture/muse")
    assert result["status"] == "AVAILABLE"
    assert result["native_hooks"] == "UNVERIFIED"


def test_unsupported_muse_refuses_before_staging(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "resolve_client_binary", lambda _: "/fixture/muse")
    monkeypatch.setattr(
        release,
        "bounded_run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0], 0, "Usage: muse [COMMAND]\nCommands:\n  exec\n", ""
        ),
    )
    monkeypatch.setattr(release, "source_version", lambda _: ("9.9.9", "consistent"))
    monkeypatch.setattr(
        release,
        "_materialize_muse_bundle",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("staged unsupported client")
        ),
    )
    assert release.refresh_client("muse", release.Result(), False, tmp_path) is False




@pytest.mark.parametrize(
    "bad",
    [
        subprocess.CompletedProcess([], 1, "", "failure"),
        subprocess.CompletedProcess([], 0, "not json", ""),
        subprocess.CompletedProcess([], 0, '{"unexpected":[]}', ""),
    ],
)
def test_unavailable_install_inventory_refuses_before_staging(
    monkeypatch, tmp_path, bad
):
    top = "Usage: muse [COMMAND]\nCommands:\n  plugins\n"
    sub = "Usage: muse plugins [COMMAND]\nCommands:\n  list\n  install\n  update\n"

    def fake(argv, **kw):
        if argv[1:] == ["--help"]:
            return subprocess.CompletedProcess(argv, 0, top, "")
        if argv[1:] == ["plugins", "--help"]:
            return subprocess.CompletedProcess(argv, 0, sub, "")
        return bad

    monkeypatch.setattr(release, "run", fake)
    monkeypatch.setattr(release, "bounded_run", fake)
    monkeypatch.setattr(release, "resolve_client_binary", lambda _: "/fixture/muse")
    monkeypatch.setattr(release, "source_version", lambda _: ("9.9.9", "consistent"))
    monkeypatch.setattr(
        release,
        "_materialize_muse_bundle",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("staged with unknown install inventory")
        ),
    )
    assert release.refresh_client("muse", release.Result(), False, tmp_path) is False


TOP = "Usage: muse [COMMAND]\nCommands:\n  plugins\n"
SUB = "Usage: muse plugins [COMMAND]\nCommands:\n  list\n  install\n  update\n"


def inventory_cli(monkeypatch, raw, *, stderr=""):
    def query(argv, **kwargs):
        text = TOP if argv[1:] == ["--help"] else SUB if argv[1:] == ["plugins", "--help"] else raw
        return subprocess.CompletedProcess(argv, 0, text, stderr)
    monkeypatch.setattr(release, "bounded_run", query)
    monkeypatch.setattr(release, "resolve_client_binary", lambda _: "/fixture/muse")
    monkeypatch.setattr(release, "source_version", lambda _: ("9.9.9", "consistent"))


@pytest.mark.parametrize("raw", [
    '{"plugins":[{"record":{"id":"synthesis-skills","source":{"path":"/retained"}}}],"plugins":[]}',
    '{"plugins":[{"unknown_record":{"id":"synthesis-skills"}}]}',
    '{"plugins":[{"record":null}]}',
    '{"plugins":[{"record":{}}]}',
    '{"plugins":[{"record":{"id":"foreign"}},{"record":{"id":"foreign"}}]}',
    '{"plugins":[{"record":{"id":"foreign","id":"other"}}]}',
    '{"plugins":[{"record":{"id":"synthesis-skills"}}]}',
    '{"plugins":[{"record":{"id":"synthesis-skills","source":null}}]}',
    '{"plugins":[{"record":{"id":"synthesis-skills","source":{"path":"relative"}}}]}',
    '{"plugins":[{"record":{"id":"synthesis-skills","source":{"path":42}}}]}',
    '{"plugins":[{"record":{"id":"foreign","enabled":"false"}}]}',
    '{"plugins":[{"record":{"id":"foreign","version":42}}]}',
    '{"plugins":[{"record":{"id":"foreign","cache_path":[]}}]}',
    '{"plugins":[],"extra":NaN}',
    '{"plugins":[],"extra":1e999}',
    '{"plugins":[]} {"plugins":[]}',
    'warning: {"plugins":[]}',
])
def test_ambiguous_inventory_never_stages_or_reports_version(monkeypatch, tmp_path, raw):
    inventory_cli(monkeypatch, raw)
    effects = []
    monkeypatch.setattr(release, "_materialize_muse_bundle", lambda *a, **k: effects.append("staged"))
    assert release.refresh_client("muse", release.Result(), False, tmp_path) is False
    assert effects == []
    assert release.client_reported_version("muse") == (None, None)


@pytest.mark.parametrize("raw", [
    '{"plugins":[]}',
    '{"plugins":[{"record":{"id":"foreign","enabled":false}}]}',
])
def test_complete_inventory_can_establish_absence(monkeypatch, raw):
    inventory_cli(monkeypatch, raw, stderr='diagnostic with {"not":"inventory"}')
    assert release._muse_install_record("/fixture/muse") is None


def test_disabled_record_is_present_and_retains_exact_source(monkeypatch):
    raw = '{"plugins":[{"record":{"id":"synthesis-skills","enabled":false,"version":"1.2.3","cache_path":"/cache","source":{"path":"/retained"}}}]}'
    inventory_cli(monkeypatch, raw)
    assert release._muse_install_record("/fixture/muse")["source"]["path"] == "/retained"
    assert release.client_reported_version("muse") == (None, None)


@pytest.mark.parametrize("shape", ["bytes", "rows", "depth"])
def test_inventory_bounds_refuse(monkeypatch, shape):
    import json
    raw = (' ' * (1024 * 1024 + 1) if shape == "bytes" else
           json.dumps({"plugins": [{"record": {"id": str(i)}} for i in range(4097)]}) if shape == "rows" else
           '[' * 2000 + '0' + ']' * 2000)
    inventory_cli(monkeypatch, raw)
    with pytest.raises(OSError):
        release._muse_install_record("/fixture/muse")


@pytest.mark.parametrize("grammar", [
    SUB.replace("muse plugins ", "muse plugins-unsupported "),
    SUB + "Usage: muse [COMMAND]\n",
    SUB + "Commands:\n  unrelated\n",
    TOP,
])
def test_ambiguous_plugin_grammar_never_stages(monkeypatch, tmp_path, grammar):
    def query(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, TOP if argv[1:] == ["--help"] else grammar, "")
    monkeypatch.setattr(release, "bounded_run", query)
    monkeypatch.setattr(release, "resolve_client_binary", lambda _: "/fixture/muse")
    monkeypatch.setattr(release, "source_version", lambda _: ("9.9.9", "consistent"))
    effects = []
    monkeypatch.setattr(release, "_materialize_muse_bundle", lambda *a, **k: effects.append("staged"))
    assert release.refresh_client("muse", release.Result(), False, tmp_path) is False
    assert effects == []
