#!/usr/bin/env python3
"""Versioned local study contracts and paired source-cluster analysis.

The evaluator verifies recorded bytes and accounting, not the authenticity of a
human permission or a provider observation. It performs no worker execution,
policy activation, publication, network request or artifact mutation.
"""
from __future__ import annotations

from collections import defaultdict
import copy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics

SCHEMA = 2
VERIFIER = "autopilot-evaluation/2"
METHODS = {"paired-cluster-bca/1", "paired-cluster-hoeffding/1"}
FAMILIES = {"software", "research", "writing", "data", "browser", "project"}
DIMENSIONS = ("cost", "tokens", "tool_calls", "wall_seconds", "human_minutes", "human_interventions")
HARMS = ("unauthorized_effects", "duplicate_effects", "unrecoverable_loss", "false_completion", "isolation_failure")
SPEC_KEYS = {"schema_version", "study_id", "phase", "authority_ref", "task_registry", "arms", "lanes",
             "repetitions", "seed", "analysis", "resources", "stopping"}
EPISODE_KEYS = {"assignment_id", "episode_index", "parent_digest", "reason", "actor", "status",
                "authority_ref", "observed_configuration", "target", "timing", "conditions", "outcome", "usage"}
BOOTSTRAP_MIN_CLUSTERS = 20  # Method adequacy recommendation, never a power guarantee.
NORMAL = statistics.NormalDist()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _object(value, keys, label, optional=()):
    if not isinstance(value, dict) or not set(keys) <= set(value) or set(value) - set(keys) - set(optional):
        raise ValueError(f"{label}: required/unknown object fields")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: nonempty text required")
    return value


def _id(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value):
        raise ValueError(f"{label}: invalid identifier")
    return value


def _number(value, label, low=0, high=None):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < low or (high is not None and value > high):
        raise ValueError(f"{label}: finite number in registered range required")
    return value


def _integer(value, label, low=0, high=None):
    if type(value) is not int:
        raise ValueError(f"{label}: integer required")
    return _number(value, label, low, high)


def _boolean(value, label):
    if type(value) is not bool:
        raise ValueError(f"{label}: Boolean required")
    return value


def _list(value, label, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{label}: {'nonempty ' if nonempty else ''}list required")
    return value


def _unique_texts(value, label, nonempty=True):
    rows = _list(value, label, nonempty)
    for row in rows:
        _text(row, label)
    if len(set(rows)) != len(rows):
        raise ValueError(f"{label}: duplicate value")
    return rows


def _sha(value, label):
    if not isinstance(value, str) or not re.fullmatch("[a-f0-9]{64}", value):
        raise ValueError(f"{label}: SHA-256 required")
    return value


def _json(data, label):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"{label}: duplicate JSON key {key}")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"{label}: nonfinite JSON number {value}")
    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            invalid(value)
        return parsed
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid, parse_float=number)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: invalid JSON") from exc


class _Reader:
    """A fresh byte snapshot per operation; never a persistent evidence cache."""
    def __init__(self):
        self.files = {}

    def pin(self, value, label):
        _object(value, {"path", "sha256"}, label)
        path = Path(_text(value["path"], label))
        expected = _sha(value["sha256"], label)
        if not path.is_absolute() or not path.is_file():
            raise ValueError(f"{label}: pin must identify an existing absolute regular-file path")
        actual = path.resolve()
        if actual not in self.files:
            self.files[actual] = actual.read_bytes()
        data = self.files[actual]
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"{label}: artifact pin changed")
        return data

    def document(self, value, label):
        return _json(self.pin(value, label), label)


def _limits(value, label):
    _object(value, DIMENSIONS, label)
    for name in DIMENSIONS:
        _number(value[name], f"{label}.{name}")


def _calibration(reader, task, rubric):
    record = reader.document(task["calibration"], "calibration")
    _object(record, {"rubric_sha256", "grader", "reviewer", "blinded", "source", "controls", "quality_controls"}, "calibration")
    if record["rubric_sha256"] != task["rubric"]["sha256"] or record["blinded"] is not True:
        raise ValueError("calibration: wrong rubric or unblinded controls")
    _text(record["grader"], "calibration grader")
    _text(record["reviewer"], "calibration reviewer")
    if record["grader"] == record["reviewer"]:
        raise ValueError("calibration requires a reviewer distinct from the grader")
    reader.pin(record["source"], "calibration observation source")
    ids, hashes, expected = set(), set(), set()
    for control in _list(record["controls"], "calibration controls"):
        _object(control, {"id", "artifact", "expected", "observed"}, "control")
        ident = _id(control["id"], "control id")
        reader.pin(control["artifact"], "control artifact")
        sha = control["artifact"]["sha256"]
        if ident in ids or sha in hashes:
            raise ValueError("calibration: duplicate control")
        ids.add(ident)
        hashes.add(sha)
        if control["expected"] not in {"PASS", "FAIL"} or control["observed"] not in {"PASS", "FAIL", "UNKNOWN"}:
            raise ValueError("calibration: invalid control outcome")
        expected.add(control["expected"])
    if expected != {"PASS", "FAIL"}:
        raise ValueError("calibration: sound and defective controls required")
    anchors, quality_valid, quality_ids, quality_hashes = [], True, set(), set()
    for control in _list(record["quality_controls"], "quality calibration controls", nonempty=False):
        _object(control, {"id", "artifact", "expected_score", "observed_score", "tolerance"}, "quality control")
        ident = _id(control["id"], "quality control id")
        if ident in quality_ids:
            raise ValueError("duplicate quality calibration control")
        quality_ids.add(ident)
        reader.pin(control["artifact"], "quality control artifact")
        if control["artifact"]["sha256"] in quality_hashes:
            raise ValueError("duplicate quality control artifact")
        quality_hashes.add(control["artifact"]["sha256"])
        _number(control["expected_score"], "quality anchor", 1, 5)
        _number(control["tolerance"], "frozen quality calibration tolerance", 0, .25)
        score = control["observed_score"]
        if score is None:
            quality_valid = False
        else:
            _number(score, "observed quality control", 1, 5)
            quality_valid &= abs(score - control["expected_score"]) <= control["tolerance"]
        anchors.append(control)
    expected_scores = {c["expected_score"] for c in anchors}
    quality_valid &= len(expected_scores) >= 2 and max(expected_scores, default=0) - min(expected_scores, default=0) >= 1
    for left in anchors:
        for right in anchors:
            if left["expected_score"] < right["expected_score"] and left["observed_score"] is not None and right["observed_score"] is not None:
                quality_valid &= left["observed_score"] < right["observed_score"]
    return {"grader": record["grader"], "reviewer": record["reviewer"],
            "valid": all(c["expected"] == c["observed"] for c in record["controls"]),
            "quality_valid": quality_valid,
            "criteria": rubric["criteria"]}


def _tasks(reader, spec):
    tasks, content_clusters, cluster_splits = {}, {}, {}
    for task in _list(spec["task_registry"], "task registry"):
        _object(task, {"id", "family", "split", "cluster_id", "author", "source", "sealed", "exposed_to_candidate",
                       "worker", "oracle", "rubric", "consumer", "preservation", "calibration"}, "task")
        ident = _id(task["id"], "task id")
        cluster = _id(task["cluster_id"], "source/project cluster id")
        _text(task["author"], "independent task author")
        if ident in tasks:
            raise ValueError("duplicate task id")
        if task["family"] not in FAMILIES or task["split"] not in {"development", "holdout", "canary", "regression"}:
            raise ValueError("invalid task family or split")
        _boolean(task["sealed"], "task sealed")
        _boolean(task["exposed_to_candidate"], "task exposure")
        if re.fullmatch(r"[SRWDBK]0[1-5]", ident) and task["split"] != "regression":
            raise ValueError("historical corpus ids belong to regression material")
        if cluster in cluster_splits and cluster_splits[cluster] != task["split"]:
            raise ValueError("source/project cluster leaks across task splits")
        cluster_splits[cluster] = task["split"]
        required_split = {"development": "development", "confirmation": "holdout", "canary": "canary", "regression": "regression"}[spec["phase"]]
        if task["split"] != required_split:
            raise ValueError("task split differs from study phase")
        if spec["phase"] == "confirmation" and (not task["sealed"] or task["exposed_to_candidate"]):
            raise ValueError("confirmation requires sealed untouched holdout tasks")
        for name in ("source", "worker", "oracle", "rubric", "consumer", "preservation"):
            reader.pin(task[name], f"task {ident} {name}")
        worker = reader.document(task["worker"], "worker manifest")
        _object(worker, {"prompt", "inputs"}, "worker manifest")
        _text(worker["prompt"], "worker prompt")
        worker_root = Path(task["worker"]["path"]).resolve().parent
        visible = [task["worker"]]
        for item in _list(worker["inputs"], "worker inputs", nonempty=False):
            reader.pin(item, "worker input")
            if not Path(item["path"]).resolve().is_relative_to(worker_root):
                raise ValueError("worker input escapes its declared worker directory")
            visible.append(item)
        visible_bytes = b"\n".join(reader.pin(item, "worker-visible artifact") for item in visible)
        for name in ("oracle", "rubric", "consumer", "calibration"):
            hidden = task[name]
            if Path(hidden["path"]).resolve().is_relative_to(worker_root):
                raise ValueError("hidden grader artifact is inside worker entitlement")
            if hidden["path"].encode() in visible_bytes or hidden["sha256"].encode() in visible_bytes:
                raise ValueError("hidden grader pin exposed to worker")
        rubric = reader.document(task["rubric"], "rubric")
        _object(rubric, {"version", "scale", "criteria"}, "rubric")
        _text(rubric["version"], "rubric version")
        if rubric["scale"] != [1, 5]:
            raise ValueError("quality rubric must use the registered 1–5 scale")
        criteria = set()
        for criterion in _list(rubric["criteria"], "rubric criteria"):
            _object(criterion, {"id", "kind"}, "rubric criterion")
            cid = _id(criterion["id"], "criterion id")
            if cid in criteria or criterion["kind"] not in {"deterministic", "semantic"}:
                raise ValueError("duplicate or invalid rubric criterion")
            criteria.add(cid)
        if not any(c["kind"] == "deterministic" for c in rubric["criteria"]):
            raise ValueError("rubric requires an independent consumer criterion")
        preservation = reader.document(task["preservation"], "preservation manifest")
        _object(preservation, {"sentinels"}, "preservation manifest")
        for pin in _list(preservation["sentinels"], "sentinels", nonempty=False):
            reader.pin(pin, "preservation sentinel")
        control = _calibration(reader, task, rubric)
        if spec["phase"] == "confirmation" and not (control["valid"] and control["quality_valid"]):
            raise ValueError("confirmation requires passing inspected calibration controls")
        identity = tuple(task[name]["sha256"] for name in ("worker", "oracle", "consumer"))
        if identity in content_clusters and content_clusters[identity] != cluster:
            raise ValueError("identical task content cannot create independent clusters")
        content_clusters[identity] = cluster
        tasks[ident] = {**task, "grading": control, "task_digest": digest(task)}
    return tasks


def _arms(reader, spec, tasks):
    arms = {}
    for arm in _list(spec["arms"], "arms"):
        _object(arm, {"id", "role", "authors", "implementation", "runtime", "entitlement", "intervention"}, "arm")
        ident = _id(arm["id"], "arm id")
        if ident in arms or arm["role"] not in {"native", "candidate", "reference"}:
            raise ValueError("duplicate or invalid arm")
        _unique_texts(arm["authors"], "arm authors")
        reader.pin(arm["implementation"], "implementation pin")
        _object(arm["runtime"], {"client", "surface", "build", "capabilities"}, "runtime")
        for key in ("client", "surface", "build"):
            if _text(arm["runtime"][key], f"runtime {key}").lower() in {"unknown", "pending"}:
                raise ValueError("required runtime pins cannot be unknown")
        reader.pin(arm["runtime"]["capabilities"], "runtime capability observations")
        entitlement = arm["entitlement"]
        _object(entitlement, {"model", "effort", "tools", "permissions", "input_entitlement", "context_tokens",
                              "persistent_context", "environment", "resources"}, "entitlement")
        for key in ("model", "effort"):
            if _text(entitlement[key], key).lower() in {"unknown", "pending"}:
                raise ValueError("requested model/effort must be pinned; observed values may be unknown")
        _unique_texts(entitlement["tools"], "tools")
        reader.pin(entitlement["permissions"], "authority scope reference")
        reader.pin(entitlement["persistent_context"], "persistent context entitlement")
        if entitlement["input_entitlement"] != "registered-worker-only":
            raise ValueError("only registered worker inputs are entitled")
        _integer(entitlement["context_tokens"], "context tokens", 1)
        _object(entitlement["environment"], {"hardware", "network"}, "environment")
        for value in entitlement["environment"].values():
            _text(value, "environment")
        _limits(entitlement["resources"], "arm resources")
        if entitlement["resources"] != spec["resources"]["episode_limits"]:
            raise ValueError("arm envelope differs from whole-episode resource envelope")
        _object(arm["intervention"], {"workflow", "instructions"}, "intervention")
        _text(arm["intervention"]["workflow"], "workflow")
        reader.pin(arm["intervention"]["instructions"], "intervention instructions")
        if arm["role"] == "candidate" and any(t["author"] in arm["authors"] for t in tasks.values()):
            raise ValueError("task author is not independent of candidate authors")
        arms[ident] = arm
    if len(arms) < 2 or sum(a["role"] == "candidate" for a in arms.values()) != 1:
        raise ValueError("one candidate and at least one baseline arm required")
    used, lanes = set(), {}
    for lane in _list(spec["lanes"], "lanes"):
        _object(lane, {"id", "kind", "baseline", "candidate", "baseline_qualification", "context_difference"}, "lane")
        ident = _id(lane["id"], "lane id")
        if ident in lanes or lane["kind"] not in {"controlled", "strongest-native", "ablation"}:
            raise ValueError("duplicate or invalid lane")
        if lane["candidate"] not in arms or lane["baseline"] not in arms or lane["candidate"] == lane["baseline"]:
            raise ValueError("lane must reference distinct registered arms")
        candidate, baseline = arms[lane["candidate"]], arms[lane["baseline"]]
        if candidate["role"] != "candidate" or baseline["role"] == "candidate":
            raise ValueError("lane arm roles invalid")
        if lane["kind"] == "strongest-native" and baseline["role"] != "native":
            raise ValueError("strongest-native lane requires a native baseline")
        reader.pin(lane["baseline_qualification"], "baseline development qualification")
        if lane["context_difference"] not in {"matched", "system-component"}:
            raise ValueError("persistent context/cache differences must be explicitly scoped")
        a, b = candidate["entitlement"], baseline["entitlement"]
        common = ("permissions", "input_entitlement", "resources")
        if any(a[key] != b[key] for key in common):
            raise ValueError("lane outcome/authority/input/resource entitlement differs")
        if lane["kind"] in {"controlled", "ablation"}:
            if a != b or candidate["runtime"] != baseline["runtime"] or lane["context_difference"] != "matched":
                raise ValueError("controlled entitlement/runtime differs; intervention may differ")
        elif lane["context_difference"] == "matched" and a["persistent_context"] != b["persistent_context"]:
            raise ValueError("persistent context differs without system-component registration")
        used.update((lane["baseline"], lane["candidate"]))
        lanes[ident] = lane
    if used != set(arms):
        raise ValueError("every registered arm must participate in a lane")
    return arms, lanes


def _analysis(reader, spec, families):
    analysis = spec["analysis"]
    _object(analysis, {"method", "confidence", "resamples", "primary", "reliability_margin",
                       "family_quality_margin", "efficiency", "sample_plan"}, "analysis")
    if analysis["method"] not in METHODS:
        raise ValueError("unknown frozen inference method")
    _number(analysis["confidence"], "confidence", .8, .999)
    _integer(analysis["resamples"], "bootstrap resamples", 1000, 200000)
    _object(analysis["primary"], {"metric", "minimum_effect"}, "primary")
    if analysis["primary"]["metric"] not in {"accepted", "quality"}:
        raise ValueError("one accepted-delivery or calibrated-quality primary endpoint required")
    maximum = 1 if analysis["primary"]["metric"] == "accepted" else 4
    if not 0 < _number(analysis["primary"]["minimum_effect"], "primary meaningful effect", 0, maximum):
        raise ValueError("primary meaningful effect must be positive")
    _number(analysis["reliability_margin"], "reliability margin", 0, 1)
    _number(analysis["family_quality_margin"], "family quality margin", 0, 4)
    efficiency = analysis["efficiency"]
    if efficiency is not None:
        _object(efficiency, {"metric", "minimum_reduction"}, "efficiency")
        if efficiency["metric"] not in {"cost", "human_minutes"}:
            raise ValueError("efficiency metric must measure cost or active human time")
        if not 0 < _number(efficiency["minimum_reduction"], "efficiency reduction", 0, 1) < 1:
            raise ValueError("efficiency reduction must be between zero and one")
    plan = analysis["sample_plan"]
    if not isinstance(plan, dict) or plan.get("kind") not in {"development-budget", "pilot-informed"}:
        raise ValueError("sample plan kind required")
    keys = {"kind", "basis", "maximum_clusters"}
    _object(plan, keys | ({"power", "assumptions"} if plan["kind"] == "pilot-informed" else set()), "sample plan")
    reader.pin(plan["basis"], "sample-planning evidence")
    _integer(plan["maximum_clusters"], "maximum source clusters", 1, 100000)
    if spec["phase"] == "confirmation" and plan["kind"] != "pilot-informed":
        raise ValueError("confirmation requires a pilot-informed sample plan")
    if plan["kind"] == "pilot-informed":
        _number(plan["power"], "planning power", .5, .999)
        _object(plan["assumptions"], {"all", *families}, "planning scopes")
        metrics = {"accepted", "quality"} | ({"efficiency"} if efficiency else set())
        for scope, row in plan["assumptions"].items():
            _object(row, metrics, "planning metrics")
            for metric, assumption in row.items():
                _object(assumption, {"variance", "anticipated_effect"}, "planning assumption")
                bound = 4 if metric == "quality" else 1
                if _number(assumption["variance"], "pilot variance", 0, bound * bound) == 0:
                    raise ValueError("zero pilot variance cannot establish sample adequacy")
                _number(assumption["anticipated_effect"], "anticipated effect", -bound, bound)
    return analysis


def _validate_spec(spec, reader):
    _object(spec, SPEC_KEYS, "registration specification")
    if type(spec["schema_version"]) is not int or spec["schema_version"] != SCHEMA:
        raise ValueError("unsupported evaluation schema")
    _id(spec["study_id"], "study id")
    if spec["phase"] not in {"development", "confirmation", "canary", "regression"}:
        raise ValueError("invalid study phase")
    reader.pin(spec["authority_ref"], "authority source reference")
    _integer(spec["repetitions"], "repetitions", 1, 100)
    _integer(spec["seed"], "randomization seed", 0)
    resources = spec["resources"]
    _object(resources, {"episode_limits", "study_limits", "integration_reserve", "evaluation_reserve", "limit_kind",
                        "shared_overhead_allocation", "cost_unit"}, "resources",
            optional={"enforcement_evidence"})
    _text(resources["cost_unit"], "study cost unit")
    _limits(resources["episode_limits"], "episode limits")
    _limits(resources["study_limits"], "study limits")
    if resources["limit_kind"] not in {"forecast", "externally-enforced"}:
        raise ValueError("resource enforcement must be distinguished from forecasts")
    if resources["limit_kind"] == "externally-enforced":
        reader.pin(resources.get("enforcement_evidence"), "external resource enforcement evidence")
    elif resources.get("enforcement_evidence") is not None:
        raise ValueError("forecast envelopes cannot supply an enforcement claim")
    for reserve in ("integration_reserve", "evaluation_reserve"):
        if not isinstance(resources[reserve], dict) or not resources[reserve] or set(resources[reserve]) - set(DIMENSIONS):
            raise ValueError("explicit resource reserves required")
        for key, value in resources[reserve].items():
            _number(value, "reserve")
    stopping = spec["stopping"]
    _object(stopping, {"rule", "max_rescues", "max_pair_gap_seconds", "immediate_harm", "invalidation_reasons"}, "stopping")
    if stopping["rule"] != "fixed-assignment-final" or stopping["immediate_harm"] is not True:
        raise ValueError("only frozen final efficacy looks and immediate harm stopping are supported")
    _integer(stopping["max_rescues"], "maximum rescue episodes", 0, 100)
    _number(stopping["max_pair_gap_seconds"], "matched assignment window", 0)
    _unique_texts(stopping["invalidation_reasons"], "registered invalidation reasons", nonempty=False)
    tasks = _tasks(reader, spec)
    arms, lanes = _arms(reader, spec, tasks)
    _object(resources["shared_overhead_allocation"], arms, "frozen shared overhead allocation")
    for proportion in resources["shared_overhead_allocation"].values():
        _number(proportion, "frozen overhead allocation", 0, 1)
    if not math.isclose(math.fsum(resources["shared_overhead_allocation"].values()), 1, abs_tol=1e-12):
        raise ValueError("shared study overhead must be allocated exactly once before measurement")
    _analysis(reader, spec, {t["family"] for t in tasks.values()})
    count = len({t["cluster_id"] for t in tasks.values()})
    if count > spec["analysis"]["sample_plan"]["maximum_clusters"]:
        raise ValueError("task source count exceeds the frozen affordable maximum")
    for key in DIMENSIONS:
        reserves = sum(resources[r].get(key, 0) for r in ("integration_reserve", "evaluation_reserve"))
        if resources["study_limits"][key] < resources["episode_limits"][key] + reserves:
            raise ValueError("study envelope cannot preserve completion/evaluation reserves")
    return tasks, arms, lanes


def preregister(**spec):
    """Freeze independently supplied tasks; no execution or permission is granted."""
    spec = copy.deepcopy(spec)
    tasks, arms, lanes = _validate_spec(spec, _Reader())
    rng = random.Random(spec["seed"])
    blocks = [(task, repetition) for task in tasks for repetition in range(1, spec["repetitions"] + 1)]
    rng.shuffle(blocks)
    schedule = []
    for block_index, (task, repetition) in enumerate(blocks, 1):
        order = list(arms)
        rng.shuffle(order)
        for position, arm in enumerate(order, 1):
            schedule.append({"assignment_id": f"{task}-r{repetition}-{arm}", "task_id": task,
                             "cluster_id": tasks[task]["cluster_id"], "arm": arm, "repetition": repetition,
                             "block_id": f"{task}-r{repetition}", "block_position": block_index,
                             "position": position, "task_digest": tasks[task]["task_digest"],
                             "configuration_digest": digest(arms[arm])})
    if len({row["assignment_id"] for row in schedule}) != len(schedule):
        raise ValueError("task/arm identifiers create colliding assignment identities")
    # Identical arm references share assignments only when frozen in these lanes.
    contrasts = sorted({(lane["baseline"], lane["candidate"]) for lane in lanes.values()})
    families = sorted({t["family"] for t in tasks.values()})
    result = {"schema_version": SCHEMA, "verifier": VERIFIER, "spec": spec, "schedule": schedule,
              "evaluator_code": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                 for name in ("evaluation.py", "evaluation_v2.py")},
              "contrasts": [{"baseline": b, "candidate": c} for b, c in contrasts],
              "interval_family_size": len(contrasts) * (2 * (len(families) + 1) + int(spec["analysis"]["efficiency"] is not None)),
              "execution_authorized": False}
    result["digest"] = digest(result)
    return result


def _registration(registration):
    _object(registration, {"schema_version", "verifier", "evaluator_code", "spec", "schedule", "contrasts", "interval_family_size",
                           "execution_authorized", "digest"}, "frozen registration")
    value = {k: v for k, v in registration.items() if k != "digest"}
    if registration["digest"] != digest(value):
        raise ValueError("registration digest mismatch")
    expected = preregister(**registration["spec"])
    if registration != expected:
        raise ValueError("frozen registration schedule or pins differ from its specification")
    reader = _Reader()
    tasks, arms, lanes = _validate_spec(registration["spec"], reader)
    return reader, tasks, arms, lanes


def worker(registration, task_id):
    """Project only the worker manifest, with no oracle/rubric/calibration pins."""
    reader, tasks, _, _ = _registration(registration)
    if task_id not in tasks:
        raise ValueError("unknown registered task")
    return {"task_id": task_id, "worker": reader.document(tasks[task_id]["worker"], "worker")}


def _time(value, label):
    _text(value, label)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError("timezone absent")
        return result.timestamp()
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{label}: timezone-aware ISO timestamp required") from exc


def _ledger(reader, ledger, seen_components):
    """Sum exclusive component observations against a separately pinned tree."""
    _object(ledger, {"inventory", "components"}, "usage ledger")
    inventory = reader.document(ledger["inventory"], "usage tree inventory")
    _object(inventory, {"closed", "source", "nodes"}, "usage tree inventory")
    _boolean(inventory["closed"], "usage tree closure")
    reader.pin(inventory["source"], "tree observation source")
    nodes = {}
    for node in _list(inventory["nodes"], "tree nodes", nonempty=False):
        _object(node, {"id", "parent", "role"}, "tree node")
        ident = _id(node["id"], "usage component id")
        if ident in nodes or ident in seen_components:
            raise ValueError("duplicate usage component; aggregate and exclusive amounts cannot be counted twice")
        _text(node["role"], "usage role")
        if node["parent"] is not None:
            _id(node["parent"], "parent component")
        nodes[ident] = node
    for node in nodes.values():
        chain, current = set(), node
        while current["parent"] is not None:
            if current["id"] in chain or current["parent"] not in nodes:
                raise ValueError("usage tree has a cycle or missing parent")
            chain.add(current["id"])
            current = nodes[current["parent"]]
    seen_components.update(nodes)
    observed = {}
    for component in _list(ledger["components"], "usage components", nonempty=False):
        _object(component, {"id", "measurement", "values", "source"}, "component measurement")
        ident = component["id"]
        if ident not in nodes or ident in observed or component["measurement"] != "exclusive":
            raise ValueError("unknown/duplicate component or nonexclusive accounting")
        _object(component["values"], DIMENSIONS, "component values")
        for name, value in component["values"].items():
            if value is not None:
                (_integer if name in {"tokens", "tool_calls", "human_interventions"} else _number)(value, name)
        if component["source"] is None:
            if any(v is not None for v in component["values"].values()):
                raise ValueError("measured usage lacks a source")
        else:
            reader.pin(component["source"], "usage observation source")
        observed[ident] = component["values"]
    result = {}
    for name in DIMENSIONS:
        known = [values[name] for values in observed.values() if values[name] is not None]
        unknown = sorted(ident for ident in nodes if ident not in observed or observed[ident][name] is None)
        complete = inventory["closed"] and not unknown
        result[name] = {"known_sum": math.fsum(known), "complete": complete,
                        "unknown_components": unknown, "tree_closed": inventory["closed"]}
    return result


def _unknown_usage():
    return {key: {"known_sum": 0.0, "complete": False, "unknown_components": ["unobserved"],
                  "tree_closed": False} for key in DIMENSIONS}


def _add_usage(rows):
    rows = list(rows)
    return {key: {"known_sum": math.fsum(row[key]["known_sum"] for row in rows),
                  "complete": bool(rows) and all(row[key]["complete"] for row in rows),
                  "unknown_components": sorted({name for row in rows for name in row[key]["unknown_components"]}),
                  "tree_closed": bool(rows) and all(row[key]["tree_closed"] for row in rows)} for key in DIMENSIONS}


def _outcome(reader, outcome, task, actor):
    _object(outcome, {"criteria", "quality", "quality_evidence", "grader", "harms", "harm_evidence",
                      "harm_observer", "critical_regressions"}, "outcome")
    expected = {c["id"]: c for c in task["grading"]["criteria"]}
    observations = {}
    for observation in _list(outcome["criteria"], "criterion observations", nonempty=False):
        _object(observation, {"id", "status", "evidence", "observer"}, "criterion observation")
        ident = observation["id"]
        if ident not in expected or ident in observations or observation["status"] not in {"PASS", "FAIL", "UNKNOWN"}:
            raise ValueError("unknown/duplicate criterion or invalid observation status")
        disposition = observation["status"]
        if observation["evidence"] is not None:
            reader.pin(observation["evidence"], "criterion observation evidence")
        if disposition != "UNKNOWN":
            _text(observation["observer"], "independent criterion observer")
            if observation["observer"] == actor or observation["evidence"] is None:
                raise ValueError("worker assertion cannot substitute for independent consumer evidence")
        if expected[ident]["kind"] == "semantic" and not task["grading"]["valid"]:
            disposition = "UNKNOWN"
        if expected[ident]["kind"] == "semantic" and disposition != "UNKNOWN" and observation["observer"] != task["grading"]["grader"]:
            raise ValueError("semantic observation was not produced by the frozen calibrated grader")
        observations[ident] = disposition
    statuses = [observations.get(ident, "UNKNOWN") for ident in expected]
    criterion_status = "FAIL" if "FAIL" in statuses else "UNKNOWN" if "UNKNOWN" in statuses else "PASS"
    score = outcome["quality"]
    if score is not None:
        _number(score, "family quality score", 1, 5)
        if outcome["grader"] == actor:
            raise ValueError("worker cannot grade its own numeric quality")
        if outcome["quality_evidence"] is None or outcome["grader"] != task["grading"]["grader"]:
            raise ValueError("quality score lacks its calibrated grader/evidence")
        reader.pin(outcome["quality_evidence"], "quality review source")
        if not task["grading"]["valid"] or not task["grading"]["quality_valid"] or any(
                observations.get(c["id"], "UNKNOWN") == "UNKNOWN"
                for c in expected.values() if c["kind"] == "semantic"):
            score = None
    elif outcome["quality_evidence"] is not None:
        reader.pin(outcome["quality_evidence"], "unscored review source")
    _object(outcome["harms"], (), "critical harm counts", optional=HARMS)
    counts = [outcome["harms"].get(key) for key in HARMS]
    for value in counts:
        if value is not None:
            _integer(value, "critical harm count")
    if outcome["harm_evidence"] is not None:
        reader.pin(outcome["harm_evidence"], "harm observation source")
    harm_source = outcome["harm_evidence"] is not None and outcome["harm_observer"] not in {None, actor}
    if outcome["harm_observer"] is not None:
        _text(outcome["harm_observer"], "harm observer")
    harm = ("FAIL" if any(value is not None and value > 0 for value in counts) else
            "PASS" if all(value == 0 for value in counts) and harm_source else "UNKNOWN")
    regressions = _list(outcome["critical_regressions"], "critical regressions", nonempty=False)
    for item in regressions:
        reader.pin(item, "known critical regression")
    return {"criterion_status": criterion_status, "quality": score, "harm": harm,
            "critical_regression": bool(regressions),
            "missing_criteria": sorted(set(expected) - set(observations))}


def _episode(reader, tasks, arms, registration, value, seen_components):
    _object(value, EPISODE_KEYS, "episode input")
    schedule = {row["assignment_id"]: row for row in registration["schedule"]}
    ident = value["assignment_id"]
    if ident not in schedule:
        raise ValueError("episode does not match a registered assignment")
    assigned = schedule[ident]
    index = _integer(value["episode_index"], "episode index", 0, registration["spec"]["stopping"]["max_rescues"])
    if index == 0:
        if value["parent_digest"] is not None or value["reason"] is not None:
            raise ValueError("first episode cannot have rescue lineage")
        if value["authority_ref"] != registration["spec"]["authority_ref"]:
            raise ValueError("first episode authority differs from frozen scope")
    else:
        _sha(value["parent_digest"], "rescue parent digest")
        if value["reason"] not in {"new-launch", "operator-repair", "prompt-change", "extra-authority"}:
            raise ValueError("rescue must explain the new episode boundary")
        if value["authority_ref"] != registration["spec"]["authority_ref"] and value["reason"] != "extra-authority":
            raise ValueError("changed authority must be an explicit rescue reason")
    reader.pin(value["authority_ref"], "recorded episode authority source")
    _text(value["actor"], "worker actor")
    if value["status"] not in {"completed", "startup_failed", "failed", "timeout", "cancelled", "incomplete"}:
        raise ValueError("invalid terminal episode status")
    observed = value["observed_configuration"]
    _object(observed, {"configuration_digest", "model", "effort", "unknown_reason", "source", "observer"}, "observed configuration")
    if observed["configuration_digest"] != assigned["configuration_digest"]:
        raise ValueError("episode configuration changed")
    reader.pin(observed["source"], "native configuration observation")
    if _text(observed["observer"], "configuration observer") == value["actor"]:
        raise ValueError("worker cannot authenticate its own native configuration")
    for key in ("model", "effort"):
        if observed[key] is not None:
            _text(observed[key], f"observed {key}")
        elif not observed["unknown_reason"]:
            raise ValueError("unknown effective configuration requires an explicit reason")
    if observed["unknown_reason"] is not None:
        _text(observed["unknown_reason"], "unknown configuration reason")
    target = value["target"]
    _object(target, {"id", "mutable", "initial_state"}, "target")
    _text(target["id"], "independent target identity")
    _boolean(target["mutable"], "mutable target")
    reader.pin(target["initial_state"], "independent starting state")
    timing = value["timing"]
    _object(timing, {"assigned", "started", "ended"}, "timing")
    assigned_at = _time(timing["assigned"], "assignment time")
    end = _time(timing["ended"], "terminal time")
    start = _time(timing["started"], "start time") if timing["started"] is not None else None
    if end < assigned_at or (start is not None and not assigned_at <= start <= end):
        raise ValueError("episode time ordering is invalid")
    if start is None and value["status"] != "startup_failed":
        raise ValueError("only a startup failure may lack an execution start")
    conditions = value["conditions"]
    _object(conditions, {"load", "outage", "cache", "concurrency", "source"}, "matched-window conditions")
    for key in ("load", "outage", "cache"):
        if conditions[key] is not None:
            _text(conditions[key], key)
    if conditions["concurrency"] is not None:
        _integer(conditions["concurrency"], "observed concurrency", 0)
    if conditions["source"] is not None:
        reader.pin(conditions["source"], "environment observation")
    elif any(conditions[k] is not None for k in ("load", "outage", "cache", "concurrency")):
        raise ValueError("environment measurements lack a source")
    task = tasks[assigned["task_id"]]
    outcome = _outcome(reader, value["outcome"], task, value["actor"])
    usage = _ledger(reader, value["usage"], seen_components)
    limits = registration["spec"]["resources"]["episode_limits"]
    exceeded = [key for key in DIMENSIONS if usage[key]["known_sum"] > limits[key]]
    elapsed = end - assigned_at
    if elapsed > limits["wall_seconds"] and "wall_seconds" not in exceeded:
        exceeded.append("wall_seconds")
    if value["status"] != "completed" or outcome["harm"] == "FAIL" or outcome["criterion_status"] == "FAIL" or outcome["critical_regression"] or exceeded:
        accepted = 0
    elif outcome["harm"] == "UNKNOWN" or outcome["criterion_status"] == "UNKNOWN":
        accepted = None
    else:
        accepted = 1
    return {**assigned, **outcome, "accepted": accepted, "usage": usage,
            "assigned_at": assigned_at, "started_at": start, "ended_at": end,
            "queue_seconds": (start if start is not None else end) - assigned_at,
            "elapsed_seconds": elapsed, "budget_exceeded": exceeded,
            "configuration_observed": observed["model"] is not None and observed["effort"] is not None,
            "configuration_deviations": [key for key in ("model", "effort") if observed[key] is not None and
                                         observed[key] != arms[assigned["arm"]]["entitlement"][key]],
            "observed_configuration": copy.deepcopy(observed),
            "conditions_observed": all(conditions[k] is not None for k in ("load", "outage", "cache", "concurrency")),
            "status": value["status"], "target": target, "episode_index": index}


def episode(registration, **value):
    """Seal one observed episode. This does not grant the recorded authority."""
    reader, tasks, arms, _ = _registration(registration)
    _episode(reader, tasks, arms, registration, value, set())
    result = {"schema_version": SCHEMA, "registration_digest": registration["digest"], **copy.deepcopy(value)}
    result["digest"] = digest(result)
    return result


def _quantile(ordered, probability):
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _bca_limits(estimate, distribution, jackknife, alpha):
    """BCa transform, including mid-rank ties and delete-one acceleration.

    Equations: Efron/Tibshirani, as documented in scipy.stats.bootstrap.
    No SciPy dependency or provider/model grader is used at runtime.
    """
    percentile = (sum(x < estimate for x in distribution) + sum(x <= estimate for x in distribution)) / (2 * len(distribution))
    center = statistics.fmean(jackknife)
    deviations = [center - x for x in jackknife]
    square = math.fsum(x * x for x in deviations)
    if not 0 < percentile < 1 or square <= 1e-30:
        return None
    bias = NORMAL.inv_cdf(percentile)
    acceleration = math.fsum(x ** 3 for x in deviations) / (6 * square ** 1.5)
    probabilities = []
    for probability in (alpha / 2, 1 - alpha / 2):
        adjusted = bias + NORMAL.inv_cdf(probability)
        divisor = 1 - acceleration * adjusted
        if divisor <= 0:
            return None
        probabilities.append(NORMAL.cdf(bias + adjusted / divisor))
    # Fewer than ten expected draws in a transformed tail is unresolved Monte
    # Carlo precision, not evidence for a benefit at an unobserved quantile.
    if min(probabilities[0], 1 - probabilities[1]) * len(distribution) < 10:
        return None
    ordered = sorted(distribution)
    return [_quantile(ordered, probability) for probability in probabilities]


def paired_interval(values, *, method, confidence=.95, multiplicity=1, resamples=9999, seed=0, bounds=(-1, 1)):
    """Mean interval for already aggregated independent paired cluster values."""
    if method not in METHODS:
        raise ValueError("unknown interval method")
    _number(confidence, "confidence", .8, .999)
    _integer(multiplicity, "multiplicity", 1)
    _integer(resamples, "resamples", 1000, 200000)
    _integer(seed, "seed", 0)
    if len(bounds) != 2 or bounds[0] >= bounds[1]:
        raise ValueError("invalid interval support")
    values = list(values)
    for value in values:
        _number(value, "cluster difference", bounds[0], bounds[1])
    n = len(values)
    alpha = (1 - confidence) / multiplicity
    mean = statistics.fmean(values) if n else None
    result = {"estimate": mean, "interval": None, "independent_clusters": n,
              "method_requested": method, "method_used": None, "confidence": 1 - alpha,
              "multiplicity": multiplicity, "reason": None}
    if not n:
        result["reason"] = "no complete independent pairs"
        return result
    fallback = None
    if method == "paired-cluster-bca/1":
        if n < BOOTSTRAP_MIN_CLUSTERS:
            fallback = "fewer than 20 independent clusters; method adequacy is not power"
        elif max(values) - min(values) <= 1e-12:
            fallback = "degenerate paired differences"
        else:
            rng = random.Random(seed)
            distribution = [statistics.fmean(rng.choices(values, k=n)) for _ in range(resamples)]
            total = math.fsum(values)
            jackknife = [(total - value) / (n - 1) for value in values]
            interval = _bca_limits(mean, distribution, jackknife, alpha)
            if interval is not None and interval[1] - interval[0] > 1e-12:
                result.update(interval=[max(bounds[0], interval[0]), min(bounds[1], interval[1])],
                              method_used="paired-cluster-bca/1")
                return result
            fallback = "BCa acceleration or transformed-tail precision is insufficient"
    radius = (bounds[1] - bounds[0]) * math.sqrt(math.log(2 / alpha) / (2 * n))
    result.update(interval=[max(bounds[0], mean - radius), min(bounds[1], mean + radius)],
                  method_used="paired-cluster-hoeffding/1", reason=fallback)
    return result


def sample_size_estimate(*, variance, distance, power, confidence, multiplicity=1):
    """Normal-approximation planning estimate; not achieved or guaranteed power.

    NIST Engineering Statistics Handbook 7.2.2.2; the variance and distance
    concern paired source-cluster differences, not repeated work episodes.
    """
    _number(variance, "planning variance")
    _number(power, "power", .5, .999)
    _number(confidence, "confidence", .8, .999)
    _integer(multiplicity, "multiplicity", 1)
    _number(distance, "distance from null", -1000000)
    if variance <= 0 or distance <= 0:
        return None
    alpha = (1 - confidence) / multiplicity
    value = (NORMAL.inv_cdf(1 - alpha / 2) + NORMAL.inv_cdf(power)) ** 2 * variance / distance ** 2
    return max(2, math.ceil(value))


def _planning(spec, scope, metric, n, multiplicity, null=0):
    plan, analysis = spec["analysis"]["sample_plan"], spec["analysis"]
    method_min = BOOTSTRAP_MIN_CLUSTERS if analysis["method"] == "paired-cluster-bca/1" else 2
    required = None
    if plan["kind"] == "pilot-informed":
        assumption = plan["assumptions"][scope][metric]
        required = sample_size_estimate(variance=assumption["variance"],
                                        distance=assumption["anticipated_effect"] - null,
                                        power=plan["power"], confidence=analysis["confidence"],
                                        multiplicity=multiplicity)
    return {"available_clusters": n, "normal_approximation_required": required,
            "method_adequacy_minimum": method_min, "affordable_maximum": plan["maximum_clusters"],
            "adequate": required is not None and n >= max(method_min, required),
            "power_established": False,
            "interpretation": "Pilot-informed planning estimate; neither a coverage floor nor observed significance establishes achieved power."}


def _gate(interval, planning, *, null, minimum=None, complete=True):
    value, bounds = interval["estimate"], interval["interval"]
    if not complete or value is None or bounds is None:
        return "INCONCLUSIVE"
    if value < null:
        return "NEGATIVE"
    if not planning["adequate"]:
        return "INCONCLUSIVE"
    if bounds[0] > null and (minimum is None or value >= minimum):
        return "PASS"
    return "INCONCLUSIVE"


def _cluster_values(tasks, first, baseline, candidate, repetitions, invalid_blocks, scope):
    """Equal repeats within tasks, then equal tasks within source/project clusters."""
    grouped = defaultdict(list)
    missing, task_count = [], 0
    for ident, task in tasks.items():
        if scope != "all" and task["family"] != scope:
            continue
        task_count += 1
        rows = []
        for repetition in range(1, repetitions + 1):
            block = f"{ident}-r{repetition}"
            pair = (first.get(f"{block}-{baseline}"), first.get(f"{block}-{candidate}"))
            if block in invalid_blocks or any(row is None for row in pair):
                missing.append(block)
                continue
            rows.append(pair)
        grouped[task["cluster_id"]].append((ident, rows))
    output = {"accepted": [], "quality": []}
    for cluster, cluster_tasks in sorted(grouped.items()):
        for metric in output:
            values = []
            for ident, pairs in cluster_tasks:
                if len(pairs) != repetitions or any(pair[0][metric] is None or pair[1][metric] is None for pair in pairs):
                    missing.append(ident + ":" + metric)
                    break
                values.append(statistics.fmean(pair[1][metric] - pair[0][metric] for pair in pairs))
            else:
                output[metric].append((cluster, statistics.fmean(values)))
    return output, sorted(set(missing)), len(grouped), task_count


def _study_usage(reader, value, arms, seen_components, allocation):
    if value is None:
        return {arm: _unknown_usage() for arm in arms}, _unknown_usage()
    _object(value, {"by_arm", "shared", "allocation"}, "study overhead")
    _object(value["by_arm"], arms, "arm overhead ledgers")
    _object(value["allocation"], arms, "shared overhead allocation")
    if value["allocation"] != allocation:
        raise ValueError("study overhead allocation differs from frozen registration")
    for proportion in value["allocation"].values():
        _number(proportion, "overhead allocation", 0, 1)
    if not math.isclose(math.fsum(value["allocation"].values()), 1, abs_tol=1e-12):
        raise ValueError("shared study overhead must be allocated exactly once")
    shared = _ledger(reader, value["shared"], seen_components)
    rows = {}
    for arm in arms:
        own = _ledger(reader, value["by_arm"][arm], seen_components)
        portion = copy.deepcopy(shared)
        for metric in DIMENSIONS:
            portion[metric]["known_sum"] *= value["allocation"][arm]
        rows[arm] = _add_usage([own, portion])
    return rows, shared


def _efficiency(spec, tasks, first, episodes, overhead, baseline, candidate, invalid, multiplicity, seed):
    declaration = spec["analysis"]["efficiency"]
    if declaration is None:
        return {"status": "NOT_REGISTERED"}
    metric = declaration["metric"]
    groups = defaultdict(list)
    support_valid = True
    complete = all(overhead[arm][metric]["complete"] for arm in (baseline, candidate))
    for ident, task in tasks.items():
        pairs = []
        for repetition in range(1, spec["repetitions"] + 1):
            block = f"{ident}-r{repetition}"
            ids = [f"{block}-{arm}" for arm in (baseline, candidate)]
            if block in invalid or any(key not in first for key in ids):
                complete = False
                continue
            records = [first[key] for key in ids]
            amounts = []
            for key in ids:
                all_usage = [record[metric] for record in episodes[key]]
                if not all(item["complete"] for item in all_usage):
                    complete = False
                amounts.append(math.fsum(item["known_sum"] for item in all_usage))
            if any(amount > spec["resources"]["episode_limits"][metric] * (1 + spec["stopping"]["max_rescues"]) for amount in amounts):
                support_valid = False
            if any(record["accepted"] is None for record in records):
                complete = False
                continue
            pairs.append((amounts[0], amounts[1], records[0]["accepted"], records[1]["accepted"]))
        if len(pairs) == spec["repetitions"]:
            groups[task["cluster_id"]].append(tuple(statistics.fmean(row[i] for row in pairs) for i in range(4)))
    clusters = [tuple(statistics.fmean(task[i] for task in rows) for i in range(4)) for _, rows in sorted(groups.items())]
    planning = _planning(spec, "all", "efficiency", len(clusters), multiplicity)
    assigned = len(tasks) * spec["repetitions"]
    fixed = [overhead[arm][metric]["known_sum"] / assigned for arm in (baseline, candidate)]

    def reduction(rows):
        means = [statistics.fmean(row[i] for row in rows) for i in range(4)]
        if means[2] <= 0 or means[3] <= 0 or means[0] + fixed[0] <= 0:
            return None
        return 1 - ((means[1] + fixed[1]) / means[3]) / ((means[0] + fixed[0]) / means[2])

    estimate = reduction(clusters) if clusters and complete else None
    interval = None
    reason = "incomplete full-tree/study accounting or accepted-outcome denominator"
    analysis = spec["analysis"]
    if estimate is not None and support_valid:
        reason = "ratio inference requires nondegenerate complete source-cluster BCa observations"
        if analysis["method"] == "paired-cluster-bca/1" and len(clusters) >= BOOTSTRAP_MIN_CLUSTERS:
            rng = random.Random(seed)
            distribution = [reduction(rng.choices(clusters, k=len(clusters))) for _ in range(analysis["resamples"])]
            jackknife = [reduction(clusters[:i] + clusters[i + 1:]) for i in range(len(clusters))]
            if all(x is not None and math.isfinite(x) for x in distribution + jackknife):
                interval = _bca_limits(estimate, distribution, jackknife, (1 - analysis["confidence"]) / multiplicity)
                if interval is not None and interval[1] - interval[0] <= 1e-12:
                    interval = None
                if interval is not None:
                    reason = None
        elif analysis["method"] == "paired-cluster-hoeffding/1" and spec["resources"]["limit_kind"] == "externally-enforced":
            # Bound four cluster means simultaneously, then propagate the ratio.
            # Costs include every rescue, and fixed study expense is added once.
            means = []
            limit = spec["resources"]["episode_limits"][metric] * (1 + spec["stopping"]["max_rescues"])
            for i in range(4):
                bound = limit if i < 2 else 1
                if bound <= 0:
                    break
                means.append(paired_interval([row[i] for row in clusters], method="paired-cluster-hoeffding/1",
                                             confidence=analysis["confidence"], multiplicity=multiplicity * 4,
                                             bounds=(0, bound))["interval"])
            if len(means) == 4 and means[2][0] > 0 and means[3][0] > 0 and means[0][0] + fixed[0] > 0:
                b_low, b_high = (means[0][0] + fixed[0]) / means[2][1], (means[0][1] + fixed[0]) / means[2][0]
                c_low, c_high = (means[1][0] + fixed[1]) / means[3][1], (means[1][1] + fixed[1]) / means[3][0]
                interval = [1 - c_high / b_low, 1 - c_low / b_high]
                reason = None
        elif analysis["method"] == "paired-cluster-hoeffding/1":
            reason = "a forecast expense ceiling cannot establish bounded cost/attention uncertainty"
    status = _gate({"estimate": estimate, "interval": interval}, planning, null=0,
                   minimum=declaration["minimum_reduction"], complete=complete and not invalid)
    if not support_valid:
        reason = "observed expense exceeds the frozen interval support"
    return {"status": status, "metric": metric, "relative_reduction": estimate, "interval": interval,
            "planning": planning, "accounting_complete": complete, "reason": reason,
            "estimand": "All episode and allocated study expense per first-episode accepted outcome; equal source clusters."}


def compare(registration, observations):
    """Analyze the whole assigned cohort. Missing evidence never becomes a pass."""
    reader, tasks, arms, lanes = _registration(registration)
    spec = registration["spec"]
    if isinstance(observations, list):
        bundle = {"episodes": observations, "study_usage": None, "invalidations": []}
    else:
        bundle = _object(observations, {"episodes", "study_usage", "invalidations"}, "observation bundle")
    by_assignment, digests, seen_components = defaultdict(list), set(), set()
    target_owners, retained = {}, []
    for record in _list(bundle["episodes"], "episodes", nonempty=False):
        _object(record, EPISODE_KEYS | {"schema_version", "registration_digest", "digest"}, "sealed episode")
        body = {k: v for k, v in record.items() if k != "digest"}
        if record["schema_version"] != SCHEMA or record["registration_digest"] != registration["digest"] or record["digest"] != digest(body):
            raise ValueError("episode schema/registration/digest mismatch")
        if record["digest"] in digests:
            raise ValueError("duplicate episode")
        digests.add(record["digest"])
        value = {key: record[key] for key in EPISODE_KEYS}
        summary = _episode(reader, tasks, arms, registration, value, seen_components)
        target = value["target"]
        previous = target_owners.get(target["id"])
        if previous and previous[0] != record["assignment_id"] and (previous[1] or target["mutable"]):
            raise ValueError("assignments share a mutable external target")
        target_owners[target["id"]] = (record["assignment_id"], target["mutable"])
        by_assignment[record["assignment_id"]].append((record, summary))
        retained.append({"digest": record["digest"], "assignment_id": record["assignment_id"],
                         "episode_index": record["episode_index"], "status": record["status"],
                         "accepted": summary["accepted"], "parent_digest": record["parent_digest"]})
    first, usage_by_assignment = {}, {}
    for ident, chain in by_assignment.items():
        chain.sort(key=lambda row: row[0]["episode_index"])
        if [row[0]["episode_index"] for row in chain] != list(range(len(chain))):
            raise ValueError("duplicate episode index or missing original/rescue episode")
        for index, (record, summary) in enumerate(chain[1:], 1):
            parent, parent_summary = chain[index - 1]
            if record["parent_digest"] != parent["digest"]:
                raise ValueError("rescue lineage does not preserve the original terminal episode")
            if summary["assigned_at"] < parent_summary["ended_at"] or parent_summary["accepted"] == 1:
                raise ValueError("rescue must follow a terminal unsuccessful/unknown episode")
        first[ident] = chain[0][1]
        usage_by_assignment[ident] = [row[1]["usage"] for row in chain]
    scheduled = {row["assignment_id"]: row for row in registration["schedule"]}
    missing = sorted(set(scheduled) - set(first))
    invalid, invalid_reasons = set(), {}
    blocks = {row["block_id"] for row in registration["schedule"]}
    for record in _list(bundle["invalidations"], "block invalidations", nonempty=False):
        _object(record, {"block_id", "reason", "evidence"}, "invalidation")
        if record["block_id"] not in blocks or record["block_id"] in invalid or record["reason"] not in spec["stopping"]["invalidation_reasons"]:
            raise ValueError("duplicate/unregistered invalidation or unknown block")
        reader.pin(record["evidence"], "invalidation evidence")
        invalid.add(record["block_id"])
        invalid_reasons[record["block_id"]] = record["reason"]
    # Assignment time is before provider queue delay. Concurrent equal times
    # are allowed; a known inversion cannot silently replace randomized order.
    latest = None
    schedule_deviations = set()
    for assignment in registration["schedule"]:
        row = first.get(assignment["assignment_id"])
        if row is None:
            continue
        if latest is not None and row["assigned_at"] < latest["assigned_at"]:
            for affected in (latest, row):
                schedule_deviations.add(affected["assignment_id"])
                invalid.add(affected["block_id"])
                invalid_reasons.setdefault(affected["block_id"], "registered assignment order violated")
        if latest is None or row["assigned_at"] > latest["assigned_at"]:
            latest = row
    for contrast in registration["contrasts"]:
        for block in blocks:
            rows = [first.get(f"{block}-{contrast[role]}") for role in ("baseline", "candidate")]
            if all(rows) and (abs(rows[0]["assigned_at"] - rows[1]["assigned_at"]) > spec["stopping"]["max_pair_gap_seconds"] or
                              not all(row["conditions_observed"] for row in rows)):
                invalid.add(block)
                invalid_reasons.setdefault(block, "matched-window evidence incomplete")
    overhead, shared = _study_usage(reader, bundle["study_usage"], arms, seen_components,
                                  spec["resources"]["shared_overhead_allocation"])
    summaries, all_records = {}, [row[1] for chain in by_assignment.values() for row in chain]
    for arm in arms:
        ids = [ident for ident, row in scheduled.items() if row["arm"] == arm]
        rows = [first[ident] for ident in ids if ident in first]
        episodes = [row[1] for ident in ids for row in by_assignment.get(ident, [])]
        accounting = [row["usage"] for row in episodes] + [overhead[arm]]
        if len(rows) != len(ids):
            accounting.append(_unknown_usage())
        harm = ("FAIL" if any(row["harm"] == "FAIL" for row in episodes) else
                "UNKNOWN" if len(rows) != len(ids) or any(row["harm"] == "UNKNOWN" for row in episodes) else "PASS")
        rescued_passed = sum(any(row[1]["accepted"] == 1 for row in by_assignment.get(ident, [])) for ident in ids)
        summaries[arm] = {"assigned": len(ids), "first_episodes_received": len(rows),
                          "first_episode_passed": sum(row["accepted"] == 1 for row in rows),
                          "first_episode_failed": sum(row["accepted"] == 0 for row in rows),
                          "first_episode_unknown": len(ids) - len(rows) + sum(row["accepted"] is None for row in rows),
                          "startup_failures": sum(row["status"] == "startup_failed" for row in rows),
                          "rescue_episodes": len(episodes) - len(rows), "rescue_adjusted_passed": rescued_passed,
                          "first_episode_pass_rate": sum(row["accepted"] == 1 for row in rows) / len(ids),
                          "rescue_adjusted_pass_rate": rescued_passed / len(ids), "authority_integrity": harm,
                          "critical_regression": any(row["critical_regression"] for row in episodes),
                          "usage": _add_usage(accounting),
                          "queue_seconds": math.fsum(row["queue_seconds"] for row in episodes),
                          "episode_elapsed_sum": math.fsum(row["elapsed_seconds"] for row in episodes),
                          "concurrent_makespan": max((row["ended_at"] for row in episodes), default=0) - min((row["assigned_at"] for row in episodes), default=0)}
    study_usage = _add_usage(row["usage"] for row in summaries.values())
    resource_breaches = [key for key in DIMENSIONS if study_usage[key]["known_sum"] > spec["resources"]["study_limits"][key]]
    budget_breaches = [{"assignment_id": row["assignment_id"], "episode_index": row["episode_index"], "dimensions": row["budget_exceeded"]}
                      for row in all_records if row["budget_exceeded"]]
    harms = any(row["harm"] == "FAIL" for row in all_records)
    analysis, multiplicity = spec["analysis"], registration["interval_family_size"]
    families = sorted({task["family"] for task in tasks.values()})
    comparisons = {}
    for contrast in registration["contrasts"]:
        baseline, candidate = contrast["baseline"], contrast["candidate"]
        name = f"{baseline}:{candidate}"
        configuration_qualified = all(first.get(ident) is not None and
                                      first[ident]["configuration_observed"] and not first[ident]["configuration_deviations"]
                                      for ident, assignment in scheduled.items() if assignment["arm"] in {baseline, candidate})
        efficiency_configuration_qualified = configuration_qualified and all(
            row["configuration_observed"] and not row["configuration_deviations"]
            for row in all_records if row["arm"] in {baseline, candidate})
        scopes = {}
        for scope in ["all", *families]:
            values, absent, cluster_count, task_count = _cluster_values(tasks, first, baseline, candidate,
                                                                      spec["repetitions"], invalid, scope)
            metrics = {}
            for metric in ("accepted", "quality"):
                seed = int(digest([spec["seed"], name, scope, metric])[:16], 16)
                estimate = paired_interval([v for _, v in values[metric]], method=analysis["method"],
                                           confidence=analysis["confidence"], multiplicity=multiplicity,
                                           resamples=analysis["resamples"], seed=seed,
                                           bounds=(-1, 1) if metric == "accepted" else (-4, 4))
                null = -analysis["reliability_margin"] if metric == "accepted" else -analysis["family_quality_margin"]
                planning = _planning(spec, scope, metric, len(values[metric]), multiplicity, null)
                complete = len(values[metric]) == cluster_count
                metrics[metric] = {**estimate, "assigned_clusters": cluster_count, "planning": planning,
                                   "protection_status": _gate(estimate, planning, null=null, complete=complete),
                                   "cluster_values": [{"cluster_id": key, "difference": val} for key, val in values[metric]]}
            primary_metric = analysis["primary"]["metric"]
            primary = metrics[primary_metric]
            plan = _planning(spec, scope, primary_metric, primary["independent_clusters"], multiplicity)
            scopes[scope] = {"tasks": task_count, "source_clusters": cluster_count, "metrics": metrics,
                             "incomplete_pairs": absent, "primary_planning": plan,
                             "primary_status": _gate(primary, plan, null=0, minimum=analysis["primary"]["minimum_effect"],
                                                     complete=primary["independent_clusters"] == cluster_count)}
        protected = [metrics[metric]["protection_status"] for row in scopes.values()
                     for metrics in [row["metrics"]] for metric in ("accepted", "quality")]
        checks = [scopes["all"]["primary_status"], *protected]
        integrity = summaries[candidate]["authority_integrity"]
        if integrity == "FAIL" or summaries[candidate]["critical_regression"] or "NEGATIVE" in checks:
            outcome_status = "NEGATIVE"
        elif spec["phase"] != "confirmation":
            outcome_status = "DESCRIPTIVE"
        elif integrity != "PASS" or not configuration_qualified or missing or invalid or harms or budget_breaches or resource_breaches or any(s != "PASS" for s in checks):
            outcome_status = "INCONCLUSIVE"
        else:
            outcome_status = "SUPPORTED"
        efficiency = _efficiency(spec, tasks, first, usage_by_assignment, overhead, baseline, candidate,
                                 invalid, multiplicity, int(digest([spec["seed"], name, "efficiency"])[:16], 16))
        if efficiency["status"] == "PASS":
            # Efficiency needs quality/reliability protection, not a quality
            # superiority result. A null primary can still support lower cost.
            efficiency["status"] = ("SUPPORTED" if spec["phase"] == "confirmation" and integrity == "PASS" and
                                    efficiency_configuration_qualified and
                                    not summaries[candidate]["critical_regression"] and not missing and not invalid and
                                    not harms and not budget_breaches and not resource_breaches and all(s == "PASS" for s in protected)
                                    else "DESCRIPTIVE" if spec["phase"] != "confirmation" else "INCONCLUSIVE")
        comparisons[name] = {**contrast, "outcome_status": outcome_status, "scopes": scopes,
                             "configuration_qualified": configuration_qualified,
                             "support_scope": "Paired endpoint evidence; lane configuration qualification also required.",
                             "efficiency": efficiency, "family_protection": "PASS" if all(s == "PASS" for s in protected) else "NEGATIVE" if "NEGATIVE" in protected else "INCONCLUSIVE"}
    lane_reports = {}
    for ident, lane in lanes.items():
        differences, unknown, deviations = [], [], []
        for block in sorted(blocks):
            pair = [first.get(f"{block}-{lane[role]}") for role in ("baseline", "candidate")]
            if any(row is not None and row["configuration_deviations"] for row in pair):
                deviations.append(block)
            if not all(pair) or not all(row["configuration_observed"] for row in pair):
                unknown.append(block)
            elif any(pair[0]["observed_configuration"][key] != pair[1]["observed_configuration"][key] for key in ("model", "effort")):
                differences.append(block)
        name = f"{lane['baseline']}:{lane['candidate']}"
        status = comparisons[name]["outcome_status"]
        efficiency_status = comparisons[name]["efficiency"]["status"]
        configuration_qualified = not deviations and not unknown and not (lane["kind"] in {"controlled", "ablation"} and differences)
        if not configuration_qualified:
            if status == "SUPPORTED":
                status = "INCONCLUSIVE"
            if efficiency_status == "SUPPORTED":
                efficiency_status = "INCONCLUSIVE"
        lane_reports[ident] = {"kind": lane["kind"], "contrast": name, "outcome_status": status,
                               "efficiency_status": efficiency_status, "configuration_qualified": configuration_qualified,
                               "configuration_reuse_registered": sum(l["baseline"] == lane["baseline"] and l["candidate"] == lane["candidate"] for l in lanes.values()) > 1,
                               "context_difference": lane["context_difference"], "effective_configuration_differences": differences,
                               "effective_configuration_unknown": unknown,
                               "effective_configuration_deviations": deviations,
                               "adoption_evidence_supported": lane["kind"] == "strongest-native" and
                                   (status == "SUPPORTED" or efficiency_status == "SUPPORTED")}
    return {"schema_version": SCHEMA, "verifier": VERIFIER, "registration_digest": registration["digest"],
            "status": "INCOMPLETE" if missing else "HARM" if harms else "ANALYZED",
            "phase": spec["phase"], "arms": summaries, "comparisons": comparisons, "lanes": lane_reports,
            "missing_assignments": missing, "retained_episodes": sorted(retained, key=lambda x: (x["assignment_id"], x["episode_index"])),
            "invalidated_blocks": invalid_reasons, "study_usage": study_usage, "shared_overhead": shared,
            "schedule_order_deviations": sorted(schedule_deviations),
            "episode_budget_breaches": budget_breaches, "study_budget_breaches": resource_breaches,
            "resource_limit_kind": spec["resources"]["limit_kind"],
            "cost_unit": spec["resources"]["cost_unit"],
            "enforcement_authentication": "external owner; evaluator verifies the referenced bytes only",
            "harm_stop_required": harms, "effective_configuration_complete": bool(all_records) and not missing and all(row["configuration_observed"] for row in all_records),
            "public_claim_authorized": False, "activation_authorized": False,
            "interpretation": "Independent source/project clusters; first episodes define benefit, rescues and all known expense remain visible. Source authenticity, native capability, sample independence and action authority require their existing owners."}
