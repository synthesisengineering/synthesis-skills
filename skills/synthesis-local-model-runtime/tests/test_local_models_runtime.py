"""Tests for scripts/local_model_runtime.py: policy exclusions (E85), memory, disk and install gates (E86),
catalog staleness (E87), privacy, updates, LM Studio and the Homebrew service change.

Fake runners stand in for `ollama`, `lms`, `launchctl` and the loopback Ollama API: nothing is
downloaded, installed or reconfigured, and no real runtime is needed.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import plistlib
import stat
import subprocess
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "local_model_runtime.py"
SPEC = importlib.util.spec_from_file_location("local_model_runtime", SCRIPT)
lmr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lmr)

BUNDLED = lmr.load_json(lmr.DEFAULT_CATALOG)
ARTIFACTS = lmr.validate_catalog(BUNDLED)
FOUR = ["qwen", "glm", "kimi", "deepseek"]


def profile(memory=128, free=2000, version="0.31.2", kv="f16", lms=True):
    return {
        "memory": {"total_gib": memory, "unified": True},
        "storage": {"model_store": "~/.ollama/models", "free_gib": free},
        "runtimes": {"ollama": {"available": True, "version": version,
                                "configuration": {"kv_cache_type": kv, "source": "test"}},
                     "lm_studio": {"available": lms, "version": None}},
    }


def policy(**changes):
    value = copy.deepcopy(lmr.DEFAULT_POLICY)
    value.update(changes)
    return value


def tag(name, digest, size=100):
    return {"name": name, "model": name, "digest": digest, "size": size,
            "details": {"format": "gguf", "family": "fixture", "parameter_size": "8B", "quantization_level": "Q8_0"}}


class FakeRuntime:
    """The `ollama`, `lms` and `launchctl` CLIs and the loopback API, held in memory."""

    def __init__(self, models=(), version="0.31.2"):
        self.models, self.version, self.calls = [dict(m) for m in models], version, []
        self.pull_codes, self.after_pull, self.lms_get_code, self.lms_inventory = {}, {}, 0, []
        self.launchctl_codes = {}

    def __call__(self, argv, **kwargs):
        assert isinstance(argv, list) and not kwargs.get("shell"), "runtime CLIs run as argument lists"
        self.calls.append(list(argv))
        tool, verb = Path(argv[0]).name, (argv[1] if len(argv) > 1 else "")
        code, out = 127, ""
        if tool == "ollama" and verb == "pull":
            code = self.pull_codes.get(argv[2], 0)
            if code == 0 and argv[2] in self.after_pull:
                self.models = [m for m in self.models if m["name"] != argv[2]] + [self.after_pull[argv[2]]]
        elif tool == "lms" and verb == "get":
            code = self.lms_get_code
        elif tool == "lms" and verb == "ls":
            code, out = 0, json.dumps(self.lms_inventory)
        elif tool == "launchctl":
            codes = self.launchctl_codes.get(verb, [])
            code = codes.pop(0) if codes else 0
        return subprocess.CompletedProcess(argv, code, out, "")

    def api(self, path, timeout=5):
        if path == "/api/tags":
            return {"models": [dict(m) for m in self.models]}
        if path == "/api/version":
            return {"version": self.version}
        raise lmr.LocalModelError(f"unexpected API path {path}")

    def verbs(self, tool):
        return [call[1] for call in self.calls if Path(call[0]).name == tool]


@pytest.fixture
def fake(monkeypatch):
    runtime = FakeRuntime()
    monkeypatch.setattr(lmr, "RUNNER", runtime)
    monkeypatch.setattr(lmr, "api", runtime.api)
    monkeypatch.setattr(lmr.shutil, "which", lambda name: f"/fake/bin/{name}" if name in ("ollama", "lms") else None)
    monkeypatch.setattr(lmr, "machine_profile", lambda *args, **kwargs: profile())
    return runtime


def run(capsys, *argv):
    code = lmr.main([str(a) for a in argv])
    return code, json.loads(capsys.readouterr().out)


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


# --- catalog -----------------------------------------------------------------------------------

def test_bundled_catalog_is_valid_with_four_families_and_lm_studio_targets():
    assert len(ARTIFACTS) == 12
    assert sorted({a["family"] for a in ARTIFACTS}) == sorted(FOUR)
    assert sum(lmr.target(a, "lm_studio") is not None for a in ARTIFACTS) == 8


@pytest.mark.parametrize("mutate, message", [
    (lambda c: c["artifacts"].append(copy.deepcopy(c["artifacts"][0])), "duplicate"),
    (lambda c: c["artifacts"][0].update(artifact_source_url="https://user:secret@example.com/x"), "credential-free"),
    (lambda c: c["artifacts"][1]["runtime_targets"]["lm_studio"].update(match_terms=["q8_0"]), "match terms"),
    (lambda c: c["artifacts"][0].update(minimum_memory_gib=99), "minimum <= recommended"),
    (lambda c: c.update(verified_on="August 2026"), "ISO verified_on"),
    (lambda c: c["artifacts"][5].update(runtime_requirements={"ollama_kv_cache_types": ["fp8"]}), "kv_cache"),
])
def test_catalog_validation_refuses_unsafe_or_malformed_entries(mutate, message):
    catalog = copy.deepcopy(BUNDLED)
    mutate(catalog)
    with pytest.raises(lmr.LocalModelError, match=message):
        lmr.validate_catalog(catalog)


def test_e87_catalog_more_than_three_months_old_is_stale():
    """R9.3's three-month rule, counted in calendar months from verified_on."""
    catalog = {"verified_on": "2026-08-23"}
    assert lmr.freshness(catalog, date(2026, 11, 23))["stale"] is False
    assert lmr.freshness(catalog, date(2026, 11, 24))["stale"] is True
    assert lmr.freshness({"verified_on": "2026-11-30"}, date(2027, 3, 1))["stale_after"] == "2027-02-28"


def test_e87_catalog_command_flags_a_synthetic_old_catalog_and_exits_1(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(lmr, "RUNNER", None)  # `catalog` must not profile the machine or call any runtime
    old = write(tmp_path / "old.json", dict(copy.deepcopy(BUNDLED), verified_on="2020-01-15"))
    code, out = run(capsys, "catalog", "--catalog", old)
    assert code == 1 and out["status"] == "stale" and out["valid"] is True and out["stale"] is True
    assert "re-verify" in out["warning"] and out["stale_after"] == "2020-04-15"
    fresh = write(tmp_path / "fresh.json", dict(copy.deepcopy(BUNDLED), verified_on=date.today().isoformat()))
    code, out = run(capsys, "catalog", "--catalog", fresh)
    assert code == 0 and out["status"] == "valid" and "warning" not in out


def test_e87_recommend_warns_on_a_stale_catalog_without_blocking(tmp_path, capsys, fake):
    old = write(tmp_path / "old.json", dict(copy.deepcopy(BUNDLED), verified_on="2020-01-15"))
    code, out = run(capsys, "recommend", "--catalog", old)
    assert code == 0 and out["ready"] is True
    assert out["catalog"]["stale"] is True and any("stale" in w for w in out["warnings"])


def test_invalid_catalog_exits_2(tmp_path, capsys):
    code, out = run(capsys, "catalog", "--catalog", write(tmp_path / "bad.json", {"schema_version": 1}))
    assert code == 2 and out["status"] == "blocked"


# --- recommendation (E85, E86) -----------------------------------------------------------------

def test_e85_excluded_family_is_never_recommended():
    open_plan = lmr.plan(ARTIFACTS, profile(), policy(excluded_families=["DeepSeek"]))
    assert open_plan["ready"] and "deepseek" not in {s["family"] for s in open_plan["selections"]}
    required = lmr.plan(ARTIFACTS, profile(), policy(required_families=["deepseek"], excluded_families=["deepseek"]))
    assert not required["ready"] and required["selections"] == []
    assert required["family_failures"]["deepseek"] == ["no artifact remains after policy exclusions"]


def test_e85_excluded_lineage_and_organization_are_applied_before_ranking():
    lineage = lmr.plan(ARTIFACTS, profile(), policy(required_families=["deepseek"], excluded_base_families=["llama"]))
    assert [s["artifact_id"] for s in lineage["selections"]] == ["deepseek-r1-32b-q8-0"]  # not the higher-ranked 70B
    org = lmr.plan(ARTIFACTS, profile(), policy(excluded_organizations=["moonshot ai"]))
    assert "kimi" not in {s["family"] for s in org["selections"]}


def test_e85_explicit_install_cannot_bypass_a_family_exclusion(tmp_path, capsys, fake):
    rules = write(tmp_path / "policy.json", policy(excluded_families=["deepseek"]))
    code, out = run(capsys, "install", "--policy", rules, "--artifact", "deepseek-r1-32b-q8-0", "--yes",
                    "--state-dir", tmp_path / "state")
    assert code == 2 and "family deepseek is excluded by policy" in out["error"]
    assert fake.verbs("ollama") == [] and not (tmp_path / "state").exists()


def test_e85_an_override_cannot_name_an_excluded_artifact():
    result = lmr.plan(ARTIFACTS, profile(), policy(required_families=["qwen"], artifact_overrides={
        "qwen": "qwen3.8-27b-q8-0"}, excluded_artifacts=["qwen3.8-27b-q8-0"]))
    assert not result["ready"] and "excluded" in result["family_failures"]["qwen"][0]


def test_e86_limited_memory_refuses_oversized_artifacts_and_keeps_the_one_that_fits():
    result = lmr.plan(ARTIFACTS, profile(memory=48), policy(required_families=["qwen"]))
    assert [s["artifact_id"] for s in result["selections"]] == ["qwen3-8b-q8-0"]
    explicit = lmr.plan(ARTIFACTS, profile(memory=48), policy(), ids=["kimi-linear-48b-a3b-q6-k"])
    assert not explicit["ready"] and "needs 80 GiB recommended" in " ".join(explicit["blockers"])


def test_e86_minimum_memory_fit_needs_explicit_policy_permission():
    glm = next(a for a in ARTIFACTS if a["id"] == "glm-4.7-flash-q4-k-m")
    assert lmr.fit(glm, profile(memory=48), policy(), "ollama")[0] == "blocked"
    assert lmr.fit(glm, profile(memory=48), policy(allow_minimum_memory_fit=True), "ollama")[0] == "constrained"


def test_e86_unknown_memory_stays_unknown_and_blocks():
    result = lmr.plan(ARTIFACTS, profile(memory=None), policy(required_families=["qwen"]))
    assert not result["ready"] and "system memory is unknown" in " ".join(result["blockers"])


def test_e86_disk_reserve_refuses_an_oversized_plan():
    result = lmr.plan(ARTIFACTS, profile(free=100), policy(required_families=FOUR))
    assert not result["ready"] and "policy requires 40.00 GiB" in result["blockers"][-1]


def test_e86_context_beyond_the_catalog_sizing_is_refused():
    result = lmr.plan(ARTIFACTS, profile(), policy(required_families=["qwen"], planning_context_tokens=131072))
    assert not result["ready"] and "131072 tokens exceeds" in " ".join(result["blockers"])


def test_runtime_version_and_kv_cache_are_part_of_fit():
    old = lmr.plan(ARTIFACTS, profile(version="0.23.2"), policy(), ids=["qwen3.8-27b-q8-0"])
    assert "below 0.30.0" in " ".join(old["blockers"])
    kimi = lmr.plan(ARTIFACTS, profile(kv="q8_0"), policy(), ids=["kimi-linear-48b-a3b-q6-k"])
    assert "requires one of f16" in " ".join(kimi["blockers"])


def test_the_article_example_selects_four_artifacts_on_128_gib():
    rules = policy(required_families=FOUR, artifact_overrides={
        "qwen": "qwen3.8-27b-q8-0", "glm": "glm-4.7-flash-q8-0", "kimi": "kimi-linear-48b-a3b-q6-k",
        "deepseek": "deepseek-r1-32b-q8-0"})
    result = lmr.plan(ARTIFACTS, profile(), rules)
    assert result["ready"] and [s["artifact_id"] for s in result["selections"]] == list(rules["artifact_overrides"].values())


def test_explicit_ids_must_be_unique_catalog_ids():
    for ids in (["qwen3-8b-q8-0", "qwen3-8b-q8-0"], ["no-such-artifact"]):
        with pytest.raises(lmr.LocalModelError, match="unique catalog ids"):
            lmr.plan(ARTIFACTS, profile(), policy(), ids=ids)


def test_lm_studio_plans_use_exact_catalog_targets_and_block_missing_ones():
    result = lmr.plan(ARTIFACTS, profile(), policy(required_families=["qwen"]), runtime="lm_studio")
    assert result["selections"][0]["runtime_model"] == "https://huggingface.co/bartowski/Qwen3.8-27B-GGUF@Q8_0"
    assert result["selections"][0]["artifact_publisher"] == "bartowski"
    missing = lmr.plan(ARTIFACTS, profile(), policy(), runtime="lm_studio", ids=["qwen3-8b-q8-0"])
    assert "no verified lm_studio catalog target" in " ".join(missing["blockers"])


def test_runtimes_distinguish_managed_and_direct_capabilities(monkeypatch):
    monkeypatch.setattr(lmr.shutil, "which", lambda n: f"/fake/bin/{n}" if n in ("ollama", "mlx_lm.generate") else None)
    monkeypatch.setattr(lmr, "RUNNER", lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "ollama version is 0.31.2", ""))
    monkeypatch.setattr(lmr, "api_version", lambda timeout=2: None)
    monkeypatch.setattr(lmr, "service_env", lambda: None)
    found = lmr.runtimes()
    assert found["ollama"]["version"] == "0.31.2" and found["ollama"]["capabilities"]["update"] is True
    assert found["lm_studio"]["available"] is False and found["lm_studio"]["capabilities"]["update"] is False
    assert found["mlx_lm"]["available"] and found["mlx_lm"]["capabilities"]["mode"] == "direct"
    assert found["llama_cpp"]["capabilities"]["install"] is False


def test_installed_model_normalizes_only_an_implicit_latest_tag():
    models = [tag("qwen3:latest", "a" * 64)]
    assert lmr.installed_model("qwen3", models) and lmr.installed_model("QWEN3:latest", models)
    assert lmr.installed_model("qwen3:8b", models) is None


def test_api_errors_keep_only_a_bounded_body(monkeypatch):
    import io
    import urllib.error

    def refuse(url, timeout):
        raise urllib.error.HTTPError(url, 500, "error", {}, io.BytesIO(b"x" * 5000))
    monkeypatch.setattr(lmr.urllib.request, "urlopen", refuse)
    with pytest.raises(lmr.LocalModelError) as error:
        lmr.api("/api/tags")
    assert "HTTP 500" in str(error.value) and len(str(error.value)) < 2100


# --- installation (E86) ------------------------------------------------------------------------

def test_e86_install_without_yes_is_a_dry_run(tmp_path, capsys, fake):
    code, out = run(capsys, "install", "--artifact", "qwen3-8b-q8-0", "--state-dir", tmp_path / "state")
    assert code == 0 and out["execute"] is False and out["authorization_required"] is True
    assert fake.calls == [] and not (tmp_path / "state").exists()


def test_e86_failed_pull_writes_no_inventory(tmp_path, capsys, fake):
    fake.pull_codes["qwen3:8b-q8_0"] = 1
    code, out = run(capsys, "install", "--artifact", "qwen3-8b-q8-0", "--yes", "--state-dir", tmp_path / "state")
    assert code == 2 and "nothing was recorded" in out["error"]
    assert not (tmp_path / "state" / "machines.json").exists() and not (tmp_path / "state" / "machine-id").exists()


@pytest.mark.parametrize("listed", [[], [tag("qwen3:8b-q8_0", "ffffffffffff0000")]])
def test_e86_a_pull_that_is_not_listed_with_the_catalog_digest_writes_no_inventory(tmp_path, capsys, fake, listed):
    fake.models = listed
    code, out = run(capsys, "install", "--artifact", "qwen3-8b-q8-0", "--yes", "--state-dir", tmp_path / "state")
    assert code == 2 and "digest matching the catalog prefix d87f4a5a2f1a" in out["error"]
    assert not (tmp_path / "state" / "machines.json").exists()


def test_install_records_verified_identity_and_merges_selections(tmp_path, capsys, fake):
    state = tmp_path / "state"
    fake.after_pull = {"qwen3:8b-q8_0": tag("qwen3:8b-q8_0", "d87f4a5a2f1a" + "0" * 52),
                       "deepseek-r1:8b-0528-qwen3-q8_0": tag("deepseek-r1:8b-0528-qwen3-q8_0", "cade62fd2850" + "1" * 52)}
    assert run(capsys, "install", "--artifact", "qwen3-8b-q8-0", "--yes", "--state-dir", state,
               "--machine-label", "travel laptop")[0] == 0
    code, out = run(capsys, "install", "--artifact", "deepseek-r1-8b-q8-0", "--yes", "--state-dir", state)
    assert code == 0 and fake.verbs("ollama") == ["pull", "pull"]
    machine = (state / "machine-id").read_text(encoding="utf-8").strip()
    assert lmr.uuid.UUID(machine).version == 4  # random, never derived from hardware
    record = json.loads((state / "machines.json").read_text(encoding="utf-8"))["machines"][machine]
    assert record["selections"] == ["qwen3-8b-q8-0", "deepseek-r1-8b-q8-0"] and record["label"] == "travel laptop"
    assert record["installed"]["qwen3-8b-q8-0"]["installation_method"] == "ollama-pull"
    assert record["installed"]["deepseek-r1-8b-q8-0"]["digest"].startswith("cade62fd2850")
    assert stat.S_IMODE((state / "machines.json").stat().st_mode) == 0o600


def test_install_refuses_a_symlinked_state_directory(tmp_path, capsys, fake):
    (tmp_path / "real").mkdir()
    (tmp_path / "state").symlink_to(tmp_path / "real")
    fake.after_pull = {"qwen3:8b-q8_0": tag("qwen3:8b-q8_0", "d87f4a5a2f1a" + "0" * 52)}
    code, out = run(capsys, "install", "--artifact", "qwen3-8b-q8-0", "--yes", "--state-dir", tmp_path / "state")
    assert code == 2 and not (tmp_path / "real" / "machines.json").exists()


def test_lm_studio_install_uses_the_exact_catalog_target_and_records_metadata_identity(tmp_path, capsys, fake):
    fake.lms_inventory = [{"modelKey": "/models/bartowski/Qwen3.8-27B-GGUF/Qwen3.8-27B-Q8_0.gguf",
                           "sizeBytes": 29116388960, "architecture": "qwen", "quantization": "Q8_0"}]
    code, out = run(capsys, "install", "--runtime", "lm_studio", "--artifact", "qwen3.8-27b-q8-0", "--yes",
                    "--state-dir", tmp_path / "state")
    assert code == 0
    assert fake.calls[0][1:] == ["get", "https://huggingface.co/bartowski/Qwen3.8-27B-GGUF@Q8_0", "--yes", "--gguf"]
    entry = out["installed"]["qwen3.8-27b-q8-0"]
    assert entry["identity_strength"] == "runtime-metadata" and entry["runtime_name"] == "Qwen3.8-27B-Q8_0.gguf"


def test_lm_studio_failed_or_ambiguous_download_writes_no_inventory(tmp_path, capsys, fake):
    fake.lms_get_code = 7
    code, out = run(capsys, "install", "--runtime", "lm_studio", "--artifact", "qwen3.8-27b-q8-0", "--yes",
                    "--state-dir", tmp_path / "state")
    assert code == 2 and "download failed" in out["error"]
    fake.lms_get_code = 0
    fake.lms_inventory = [{"modelKey": f"bartowski/Qwen3.8-27B-GGUF/{n}-Q8_0.gguf", "sizeBytes": 1} for n in "ab"]
    code, out = run(capsys, "install", "--runtime", "lm_studio", "--artifact", "qwen3.8-27b-q8-0", "--yes",
                    "--state-dir", tmp_path / "state")
    assert code == 2 and "lists 2 models" in out["error"] and not (tmp_path / "state" / "machines.json").exists()


# --- updates -----------------------------------------------------------------------------------

def test_update_plan_needs_installed_names_and_supports_all(fake):
    fake.models = [tag("gemma4:e4b", "a" * 64, 10), tag("gemma4:26b", "b" * 64, 20)]
    with pytest.raises(lmr.LocalModelError, match="Not an installed"):
        lmr.plan_update("ollama", ["gemma4:31b"], False)
    assert [m["runtime_name"] for m in lmr.plan_update("ollama", [], True)["models"]] == ["gemma4:26b", "gemma4:e4b"]


def test_update_without_yes_pulls_nothing(capsys, fake):
    fake.models = [tag("gemma4:e4b", "a" * 64)]
    code, out = run(capsys, "update", "--model", "gemma4:e4b")
    assert code == 0 and out["execute"] is False and fake.calls == []


def test_update_records_updated_and_already_current_with_a_receipt(tmp_path, capsys, fake, monkeypatch):
    monkeypatch.setattr(lmr, "check_store", lambda *args: [])
    fake.models = [tag("gemma4:e4b", "old" + "0" * 61, 10), tag("gemma4:26b", "same" + "0" * 60, 20)]
    fake.after_pull = {"gemma4:e4b": tag("gemma4:e4b", "new" + "0" * 61, 11)}
    code, out = run(capsys, "update", "--model", "gemma4:e4b", "--model", "gemma4:26b", "--yes",
                    "--receipt-dir", tmp_path / "receipts")
    assert code == 0 and out["success"] is True
    assert [m["status"] for m in out["models"]] == ["updated", "already-current"]
    saved = list((tmp_path / "receipts").glob("ollama-update-*.json"))
    assert len(saved) == 1 and json.loads(saved[0].read_text(encoding="utf-8"))["success"] is True


@pytest.mark.parametrize("failure", ["pull", "missing"])
def test_update_failure_fails_the_receipt_and_stops(capsys, fake, monkeypatch, failure):
    monkeypatch.setattr(lmr, "check_store", lambda *args: [])
    fake.models = [tag("gemma4:e4b", "a" * 64), tag("gemma4:26b", "b" * 64)]
    if failure == "pull":
        fake.pull_codes["gemma4:e4b"] = 9
    else:  # the pull exits 0 but the model is gone from the runtime afterwards
        fake.after_pull = {"gemma4:e4b": tag("unrelated:tag", "c" * 64)}
    code, out = run(capsys, "update", "--model", "gemma4:e4b", "--model", "gemma4:26b", "--yes")
    assert code == 2 and out["success"] is False and len(out["models"]) == 1
    assert out["models"][0]["status"] == ("failed" if failure == "pull" else "failed-verification")


def test_lm_studio_updates_are_blocked(capsys, fake):
    code, out = run(capsys, "update", "--runtime", "lm_studio", "--model", "anything")
    assert code == 2 and "no stable content identity" in out["error"]


def test_update_receipts_never_land_inside_the_skill(fake):
    with pytest.raises(lmr.LocalModelError, match="inside the skill"):
        lmr.run_update({"models": [], "scope": "explicit"}, lmr.SKILL_ROOT / "receipts")


# --- profile, privacy and storage --------------------------------------------------------------

def test_profile_keeps_selection_facts_and_drops_identifiers(tmp_path, monkeypatch):
    hardware = {"SPHardwareDataType": [{"chip_type": "Apple M9", "serial_number": "C02XYZ", "platform_UUID":
                "12345678-1234-1234-1234-123456789abc", "provisioning_UDID": "0000-1111"}]}
    outputs = {("sysctl", "-n", "hw.memsize"): str(64 * lmr.GIB), ("sysctl", "-n", "hw.physicalcpu"): "12",
               ("system_profiler", "SPHardwareDataType", "-json"): json.dumps(hardware),
               ("system_profiler", "SPDisplaysDataType", "-json"): json.dumps(
                   {"SPDisplaysDataType": [{"sppci_model": "Apple M9", "sppci_cores": "30"}]})}
    monkeypatch.setattr(lmr, "RUNNER", lambda argv, **kw: subprocess.CompletedProcess(argv, 0, outputs.get(tuple(argv), ""), ""))
    monkeypatch.setattr(lmr.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(lmr.shutil, "which", lambda name: None)
    monkeypatch.setattr(lmr, "api_version", lambda timeout=2: None)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    result = lmr.machine_profile()
    text = json.dumps(result).lower()
    assert result["memory"]["total_gib"] == 64 and result["cpu"]["brand"] == "Apple M9"
    assert result["accelerators"]["gpu"]["cores"] == 30 and result["cpu"]["efficiency_cores"] is None
    assert "c02xyz" not in text and "12345678-1234" not in text and "serial" not in text
    assert result["storage"]["model_store"] == "~/.ollama/models"


def test_profile_refuses_identifier_like_values():
    with pytest.raises(lmr.LocalModelError):
        lmr.assert_safe({"cpu": {"brand": "12345678-1234-1234-1234-123456789abc"}})
    with pytest.raises(lmr.LocalModelError):
        lmr.assert_safe({"serial": "x"})


def test_model_store_inside_a_protected_root_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(lmr, "RUNNER", lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "", ""))
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(lmr.LocalModelError, match="protected root"):
        lmr.check_store(tmp_path / "workspaces" / "models", [])
    with pytest.raises(lmr.LocalModelError, match="protected root"):
        lmr.check_store(tmp_path / "vault" / "models", [str(tmp_path / "vault")])
    assert lmr.check_store(tmp_path / ".ollama" / "models", [])


# --- configure-ollama --------------------------------------------------------------------------

@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(lmr.platform, "system", lambda: "Darwin")
    runtime = FakeRuntime()
    monkeypatch.setattr(lmr, "RUNNER", runtime)
    path = tmp_path / "homebrew.mxcl.ollama.plist"
    path.write_bytes(plistlib.dumps({"Label": lmr.HOMEBREW_LABEL, "ProgramArguments": ["/opt/bin/ollama", "serve"],
                                     "EnvironmentVariables": {"OLLAMA_KV_CACHE_TYPE": "q8_0"}}))
    return path, runtime


def test_configure_ollama_dry_run_changes_nothing(tmp_path, service):
    path, runtime = service
    before = path.read_bytes()
    result = lmr.configure_ollama("f16", False, tmp_path / "state", plist_path=path)
    assert result["changed"] and result["authorization_required"] and path.read_bytes() == before and runtime.calls == []


def test_configure_ollama_applies_with_a_private_backup(tmp_path, service):
    path, runtime = service
    result = lmr.configure_ollama("f16", True, tmp_path / "state", plist_path=path, waiter=lambda: True)
    assert result["runtime_healthy"] and runtime.verbs("launchctl") == ["bootout", "bootstrap"]
    assert plistlib.loads(path.read_bytes())["EnvironmentVariables"]["OLLAMA_KV_CACHE_TYPE"] == "f16"
    backup = next((tmp_path / "state" / "backups").glob("*.plist"))
    assert plistlib.loads(backup.read_bytes())["EnvironmentVariables"]["OLLAMA_KV_CACHE_TYPE"] == "q8_0"
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600


def test_configure_ollama_restores_the_plist_when_reload_fails(tmp_path, service):
    path, runtime = service
    before = path.read_bytes()
    runtime.launchctl_codes = {"bootstrap": [5, 0]}
    with pytest.raises(lmr.LocalModelError, match="restored its prior configuration"):
        lmr.configure_ollama("f16", True, tmp_path / "state", plist_path=path, waiter=lambda: True)
    assert path.read_bytes() == before


def test_configure_ollama_refuses_an_unexpected_service(tmp_path, service):
    path, _ = service
    path.write_bytes(plistlib.dumps({"Label": "other", "ProgramArguments": ["/bin/sh", "-c", "x"]}))
    with pytest.raises(lmr.LocalModelError, match="standard Homebrew Ollama LaunchAgent"):
        lmr.configure_ollama("f16", True, tmp_path / "state", plist_path=path, waiter=lambda: True)


# --- the published article's commands ----------------------------------------------------------

@pytest.mark.parametrize("argv", [
    "profile", "runtimes", "catalog",
    "recommend --policy assets/policy.example.json",
    "install --policy assets/policy.example.json",
    "install --policy assets/policy.example.json --yes",
    "recommend --runtime lm_studio --policy assets/policy.example.json",
    "install --runtime lm_studio --artifact qwen3.8-27b-q8-0",
    "install --runtime lm_studio --artifact qwen3.8-27b-q8-0 --yes",
    "update --model glm-4.7-flash:q4_K_M --model deepseek-r1:8b-0528-qwen3-q8_0",
    "update --model glm-4.7-flash:q4_K_M --receipt-dir /tmp/receipts --yes",
    "update --all --yes",
    "configure-ollama --kv-cache-type f16",
    "configure-ollama --kv-cache-type f16 --yes",
])
def test_every_command_the_article_prints_still_parses(argv):
    lmr.build_parser().parse_args(argv.split())
