"""Credentials by their built-in patterns: what the commit check refuses in any commit (Tier 0), and what a journal
snapshot never keeps (5.19.0). Kept apart from the commit check so a session's start can read them without loading it."""

from __future__ import annotations

import re

CREDENTIALS = {
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "GitHub token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b",
    "GitLab token": r"\bglpat-[A-Za-z0-9_-]{20,}\b",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
    "Anthropic key": r"\bsk-ant-[A-Za-z0-9_-]{20,}\b",
    "OpenAI key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}\b",
    # A Docs image exported to markdown: the key opens the image to anyone with the URL (Rajiv, 2026-10-13).
    # Gemini notes also link docs.google.com/docs-images-rt/ (2026-10-20: 14 such keys were committed).
    "Docs image link key": r"(?:googleusercontent\.com|docs\.google\.com/docs-images-rt)/[^\s\"'<>)]*[?&]key=[A-Za-z0-9_-]{16,}",
}
KEY_HEADER = re.compile(rb"BEGIN (?:(?:RSA|EC|DSA|OPENSSH|PGP|ENCRYPTED|SSH2) ){0,2}PRIVATE KEY", re.I)
KEY_INLINE = re.compile(rb"PRIVATE KEY(?: BLOCK)?-----(?:\\[nr]|\s)+[A-Za-z0-9+/]{40,}", re.I)
KEY_BODY = re.compile(rb"[\s\"'>#*;-]*[A-Za-z0-9+/]{40,}={0,2}(?:\\[nr])*[\s\"',;]*")
# Published example keys pass by exact value; no credential is approvable. AWS's: docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html
EXAMPLE_KEYS = re.compile(rb"(?<![A-Za-z0-9/+])(?:AKIAIOSFODNN7EXAMPLE|wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY)(?![A-Za-z0-9/+])")
SECRET_FILE = re.compile(r"(?:^|/)(?:\.env(?:\.(?!(?:example|sample|template|dist|defaults)$)[^/]+)?|id_(?:rsa|dsa|ecdsa|ed25519)"
                         r"|[^/]+\.(?:pem|p12|pfx|jks|keystore)|\.netrc|\.pgpass|\.aws/credentials)$", re.I)


def held(rel: str, data: bytes) -> str:
    """The credential a file at `rel` holding `data` carries, by its name or its words; "" when none."""
    if SECRET_FILE.search(rel):
        return "a credential's file name"
    probe = EXAMPLE_KEYS.sub(b" ", data)
    if KEY_HEADER.search(probe) or KEY_INLINE.search(probe):
        return "a private key"
    text = probe.decode("utf-8", "replace")
    return next((name for name, pattern in CREDENTIALS.items() if re.search(pattern, text)), "")
