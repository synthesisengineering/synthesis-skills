#!/usr/bin/env python3
"""Fleet secrets provider: backend interface, 1Password backend, age/SOPS stub.

Provider interface::

    provider = SecretsProvider(OnePasswordBackend())
    value = provider.get("op://ExampleVault/ExampleItem/api-key")
    report = provider.materialize(manifest)

Hard rules enforced here:

- Values are returned to the caller only. This module never logs, prints, or
  embeds a value in an exception message; errors name the ref, never the value.
- The 1Password backend shells out to the ``op`` CLI and fails closed when the
  binary is missing or the account is not signed in.
- Headless authentication (service accounts) is the ``op`` CLI's own concern:
  the token lives in the OS credential store and is never passed as a CLI
  flag, stored in a file, or read from the environment by this module.
- The age/SOPS backend is a stub that raises ``NotImplementedError``. Its
  enrollment design is documented below and in the skill; the dual-mode seam
  is the ``SecretsBackend`` interface plus the manifest ``backend`` field.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import materialize as _materialize
import secrets_manifest as _manifest

log = logging.getLogger(__name__)

OP_READ_TIMEOUT_SECONDS = 30


class SecretError(RuntimeError):
    """Base error for secrets-provider failures. Never carries a value."""


class BackendUnavailableError(SecretError):
    """The backend cannot serve requests (missing CLI, signed out, timeout)."""


class SecretRefError(SecretError):
    """The ref is malformed or the backend reports it missing."""


@dataclass(frozen=True)
class BackendStatus:
    name: str
    available: bool
    detail: str


class SecretsBackend(ABC):
    """Dual-mode seam: every backend serves refs and reports availability."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> BackendStatus:
        """Probe the backend without fetching any secret."""

    @abstractmethod
    def get(self, ref: str) -> str:
        """Return the secret value for ``ref``. Callers must not log it."""


class OnePasswordBackend(SecretsBackend):
    """1Password backend shelling out to the ``op`` CLI (fleet Variant 1)."""

    name = "onepassword"

    def __init__(self, *, op_path: str = "op", timeout: int = OP_READ_TIMEOUT_SECONDS) -> None:
        self._op_path = op_path
        self._timeout = timeout

    def _resolve_op(self) -> str | None:
        if Path(self._op_path).is_absolute() or "/" in self._op_path:
            candidate = Path(self._op_path)
            return str(candidate) if candidate.is_file() else None
        return shutil.which(self._op_path)

    def is_available(self) -> BackendStatus:
        op = self._resolve_op()
        if op is None:
            return BackendStatus(
                name=self.name, available=False, detail="op CLI not found on PATH"
            )
        try:
            result = subprocess.run(
                [op, "whoami"],
                capture_output=True, text=True, timeout=self._timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return BackendStatus(
                name=self.name, available=False, detail="op CLI did not respond"
            )
        if result.returncode != 0:
            return BackendStatus(
                name=self.name, available=False,
                detail="op CLI present but not signed in (run `op signin`)",
            )
        # Deliberately generic: `op whoami` output names the account.
        return BackendStatus(name=self.name, available=True, detail="op CLI present and signed in")

    def get(self, ref: str) -> str:
        if not isinstance(ref, str) or not ref.startswith("op://"):
            raise SecretRefError("malformed 1Password ref %r (expected 'op://...')" % (ref,))
        op = self._resolve_op()
        if op is None:
            raise BackendUnavailableError("op CLI not found on PATH")
        try:
            result = subprocess.run(
                [op, "read", ref],
                capture_output=True, text=True, timeout=self._timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BackendUnavailableError("op read timed out for ref %r" % ref) from exc
        except OSError as exc:
            raise BackendUnavailableError("op read failed to start: %s" % exc) from exc
        if result.returncode != 0:
            # stderr may echo the ref; stdout (which could hold a value on
            # partial failure) is never quoted.
            log.warning("op read failed for ref %r (exit %d)", ref, result.returncode)
            raise SecretRefError("1Password has no readable value for ref %r" % (ref,))
        value = result.stdout
        if value.endswith("\n"):
            value = value[:-1]
        return value


class AgeSopsBackend(SecretsBackend):
    """age/SOPS backend stub (fleet Variant 2 seam, not implemented).

    Enrollment design (to implement when Variant 2 is ruled):

    - Ciphertext lives in a DEDICATED secrets repo, never co-located with the
      bootstrap personal KB.
    - Per-environment age keypairs only. A new Mac generates its keypair
      locally; the owner adds the new public key as a SOPS recipient from an
      enrolled Mac and runs ``sops updatekeys``. Private keys never move.
    - Loss/offboard = remove the recipient, ``sops updatekeys``, then rotate
      every value the removed Mac could decrypt (enumerable from the secrets
      manifest — refs are ``<file>#<key>`` for this reason).
    - Ciphertext-only in git; history permanence accepted (old ciphertext stays
      decryptable by old keys until rotation covers value AND recipients).
    """

    name = "age-sops"

    def is_available(self) -> BackendStatus:
        return BackendStatus(
            name=self.name, available=False,
            detail="age/SOPS backend not implemented (see enrollment design)",
        )

    def get(self, ref: str) -> str:
        raise NotImplementedError(
            "age/SOPS backend is not implemented; enrollment design is documented "
            "in AgeSopsBackend and references/enrollment-age-sops.md"
        )


class SecretsProvider:
    """Provider interface: ``get(ref)`` for one secret, ``materialize`` for a manifest."""

    def __init__(self, backend: SecretsBackend) -> None:
        self._backend = backend

    @property
    def backend(self) -> SecretsBackend:
        return self._backend

    def get(self, ref: str) -> str:
        """Return the secret value for ``ref`` via the configured backend."""
        return self._backend.get(ref)

    def materialize(
        self,
        manifest: _manifest.SecretsManifest,
        *,
        home: Path | None = None,
        dry_run: bool = False,
        backup: bool = True,
    ) -> _materialize.MaterializeReport:
        """Materialize every manifest entry through the configured backend."""
        return _materialize.materialize_manifest(
            manifest, self._backend, home=home, dry_run=dry_run, backup=backup
        )
