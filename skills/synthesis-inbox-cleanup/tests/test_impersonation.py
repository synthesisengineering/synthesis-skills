"""IR-19 and the brand rules of scan_impersonation.py, on synthetic data only.

Carried from the unshipped 4.154.13 candidate (branch
fix/phase1-reported-breakage-20261005). Importing the scanner never reads mail
configuration; every main() call below runs against a stub connector.
"""

import base64
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scan_impersonation.py"
spec = importlib.util.spec_from_file_location("principal_scanner", SCRIPT)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def config():
    return {"principal": {"names": ["Casey Morgan", "C. Morgan"],
                          "addresses": ["casey@public.example", "casey.work@company.example"]}}


def assess(header):
    brands, principal = scan.validate_config(config())
    return scan.assess_header(header, brands, principal)


# E62: a display name equal to the principal's own, from an address not listed, is flagged.
@pytest.mark.parametrize("name", ["Casey Morgan", "casey morgan", "  Casey   Morgan  ",
                                  "Ｃａｓｅｙ Ｍｏｒｇａｎ", "Casey​ Morgan", "C. Morgan",
                                  "=?utf-8?b?Q2FzZXkgTW9yZ2Fu?="])
def test_principal_names_and_aliases_from_unlisted_addresses_are_high(name):
    assert assess(f'"{name}" <impostor@public.example>')[0] == "high"


@pytest.mark.parametrize("address", ["casey@public.example", "CASEY@PUBLIC.EXAMPLE",
                                     "casey.work@company.example"])
def test_only_explicit_exact_addresses_are_allowed(address):
    assert assess(f"Casey Morgan <{address}>") is None


@pytest.mark.parametrize("address", ["anyone@public.example", "casey@sub.public.example",
                                     "casey@public.example.attacker.test", "casey+tag@public.example",
                                     "ca.sey@public.example", "casey@another.example"])
def test_domain_and_mailbox_variants_do_not_inherit_principal_permission(address):
    assert assess(f"Casey Morgan <{address}>")[0] == "high"


@pytest.mark.parametrize("header", [
    "Casey Morgan <casey@public.example>, Other <outsider@example.test>",
    "Casey Morgan <invalid>",
    "Casey Morgan <casey@public.example>\nBcc: outsider@example.test",
    "Casey Morgan <casey@public.example>, Casey Morgan <other@public.example>",
])
def test_ambiguous_principal_headers_never_get_address_allowlist_clearance(header):
    assert assess(header)[0] == "high"


# E61: a brand claimed from a domain that is not the brand's is flagged, never trashed.
def test_exact_name_boundary_and_brand_rules_remain_distinct():
    assert assess("Casey Morgan Advisory <outsider@example.test>") is None
    assert assess("Another Person <other@public.example>") is None
    assert assess("PayPal <billing@paypal.com>") is None
    assert assess("PayPal <billing@sub.paypal.com>") is None
    assert assess("PayPal <billing@surveyplatform.example>")[0] == "medium"
    assert assess("PayPal <billing@mailchimp.example>")[0] == "high"
    assert assess("Notice <billing@account-verify.example>")[0] == "medium"


def test_folded_name_and_idna_domain_normalize_without_alias_expansion():
    data = config()
    data["principal"]["addresses"] = ["casey@bücher.example"]
    brands, principal = scan.validate_config(data)
    assert scan.assess_header("Casey\r\n Morgan <casey@xn--bcher-kva.example>", brands, principal) is None
    assert scan.assess_header("Casey Morgan <other@xn--bcher-kva.example>", brands, principal)[0] == "high"


@pytest.mark.parametrize("addresses", [
    [], "casey@public.example", ["*@public.example"], ["public.example"],
    ["Casey <casey@public.example>"], ["casey@public.example "],
    ["casey@public.example", "CASEY@PUBLIC.EXAMPLE"], [None], [".casey@public.example"],
    ["casey@public.example."], ["casey\n@public.example"]])
def test_invalid_exact_address_policy_refuses(addresses):
    data = config()
    data["principal"]["addresses"] = addresses
    with pytest.raises(scan.ConfigError):
        scan.validate_config(data)


@pytest.mark.parametrize("names", [[], "Casey Morgan", [""], ["​"], [None],
                                   ["Casey Morgan", "casey morgan"], ["Casey\nMorgan"]])
def test_invalid_name_policy_refuses(names):
    data = config()
    data["principal"]["names"] = names
    with pytest.raises(scan.ConfigError):
        scan.validate_config(data)


@pytest.mark.parametrize("defect", ["missing", "yaml", "duplicate", "unknown", "symlink", "oversize"])
def test_config_refusals_happen_before_mail_import_or_auth(tmp_path, monkeypatch, defect):
    p = tmp_path / "impersonation.yaml"
    p.write_text(yaml.safe_dump(config()))
    if defect == "missing":
        p.unlink()
    elif defect == "yaml":
        p.write_text("principal: [")
    elif defect == "duplicate":
        p.write_text("principal: {}\nprincipal: {}\n")
    elif defect == "unknown":
        p.write_text(yaml.safe_dump({**config(), "principal_domains": ["public.example"]}))
    elif defect == "symlink":
        p.rename(tmp_path / "target")
        p.symlink_to(tmp_path / "target")
    elif defect == "oversize":
        p.write_bytes(b" " * (scan.MAX_CONFIG_BYTES + 1))
    stub = types.ModuleType("_lib")
    stub.connect = lambda **kw: pytest.fail("mail accessed despite refused config")
    monkeypatch.setitem(sys.modules, "_lib", stub)
    assert scan.main(["--config", str(p), "--json"]) == 2


def test_check_config_and_import_are_independent_of_mail_config(tmp_path):
    p = tmp_path / "impersonation.yaml"
    p.write_text(yaml.safe_dump(config()))
    env = dict(os.environ, HOME=str(tmp_path / "empty-home"))
    result = subprocess.run([sys.executable, str(SCRIPT), "--config", str(p), "--check-config"],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"status": "CONFIGURED", "principal_names": 2,
                                         "principal_addresses": 2, "brands": len(scan.SEED_BRANDS)}


def test_header_budget_is_an_explicit_refusal():
    brands, principal = scan.validate_config(config())
    with pytest.raises(ValueError, match="bounded"):
        scan.assess_header("x" * (scan.MAX_HEADER_CHARS + 1), brands, principal)


def _main_findings(raw_headers, data, tmp_path, monkeypatch, capsys):
    """Run the read-only main path against synthetic connector bytes."""
    p = tmp_path / "header-policy.yaml"
    p.write_text(yaml.safe_dump(data))

    class Mail:
        def __init__(self):
            self.calls = []

        def uid(self, *args):
            self.calls.append(args)
            if args[0] == "SEARCH":
                return "OK", [b"73"]
            assert args[0] == "FETCH" and "BODY.PEEK" in args[2]
            return "OK", [(b"1 (UID 73)", raw_headers + b"\r\n\r\n")]

        def logout(self):
            self.calls.append(("LOGOUT",))

    mail = Mail()
    stub = types.ModuleType("_lib")

    def connect(*, readonly):
        assert readonly is True
        return mail, "synthetic@example.test"

    stub.connect = connect
    monkeypatch.setitem(sys.modules, "_lib", stub)
    assert scan.main(["--config", str(p), "--json", "--strict-only"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert [call[0] for call in mail.calls] == ["SEARCH", "FETCH", "LOGOUT"]
    return result["findings"]


def test_main_scans_readonly_flags_principal_and_never_moves(tmp_path, monkeypatch, capsys):
    findings = _main_findings(b"From: Casey Morgan <outsider@public.example>\r\nSubject: synthetic",
                              config(), tmp_path, monkeypatch, capsys)
    assert len(findings) == 1 and findings[0]["uid"] == "73" and findings[0]["confidence"] == "high"


@pytest.mark.parametrize("header", [
    "Casey Morgan: other@public.example;",
    "Casey Morgan: casey@public.example;",
    "Casey Morgan:;",
    "Other: other@public.example;, Casey Morgan: casey@public.example;",
    "=?utf-8?b?Q2FzZXkgTW9yZ2Fu?=: other@public.example;",
])
def test_principal_group_claims_require_review_even_if_empty_or_listed(header, tmp_path, monkeypatch, capsys):
    findings = _main_findings(("From: " + header).encode(), config(), tmp_path, monkeypatch, capsys)
    assert len(findings) == 1 and findings[0]["confidence"] == "high"
    assert "group" in findings[0]["reason"]


@pytest.mark.parametrize("name", ["Casey Morgan", "Morgan, Casey", "Casey <Morgan>"])
@pytest.mark.parametrize("allowed", [False, True])
def test_encoded_name_punctuation_is_not_address_syntax(name, allowed, tmp_path, monkeypatch, capsys):
    data = config()
    data["principal"]["names"] = [name]
    encoded = "=?utf-8?b?" + base64.b64encode(name.encode()).decode() + "?="
    address = "casey@public.example" if allowed else "other@public.example"
    findings = _main_findings(f"From: {encoded} <{address}>".encode(), data, tmp_path, monkeypatch, capsys)
    if allowed:
        assert findings == []
    else:
        assert len(findings) == 1 and findings[0]["confidence"] == "high"


@pytest.mark.parametrize("headers", [
    b"From: Casey Morgan <casey@public.example>\r\nFrom: Other <other@public.example>",
    b"From: Other <other@public.example>\r\nFrom: Casey Morgan <casey@public.example>",
    b"From: Casey Morgan <casey@public.example",
])
def test_duplicate_and_malformed_principal_headers_still_require_review(headers, tmp_path, monkeypatch, capsys):
    findings = _main_findings(headers, config(), tmp_path, monkeypatch, capsys)
    assert len(findings) == 1 and findings[0]["confidence"] == "high"
