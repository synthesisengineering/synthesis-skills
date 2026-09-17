# Source-audit YAML runtime

The `source` audit, including the source plane selected by `all`, uses a bundled
pure-Python PyYAML 6.0.3 dependency. A fresh supported Python interpreter can run
the audit without PyYAML or jsonschema installed in its site packages. Other
conformance planes still require their own applicable configuration and evidence.

The dependency is included in the released conformance skill and its modular
runtime dependency closure. Loading it does not install packages, change the
interpreter or native client configuration, access the network, or write bytecode.
It adds approximately 219 KB of upstream payload on disk, plus its manifest and
loader. Existing release verification still binds the complete source and any
projected payload to the selected release.

## Provenance and license

The 17 `yaml/*.py` modules and `LICENSE` under `vendor/pyyaml/` are copied without
modification from the official PyYAML 6.0.3 source distribution. The upstream MIT
license is retained verbatim. PyYAML remains separately MIT licensed; the
conformance loader is covered by the repository's Apache-2.0 license.

- Source: `https://files.pythonhosted.org/packages/05/8e/961c0007c59b8dd7729d542c61a4d537767a59645b82a0b521206e1e25c2/pyyaml-6.0.3.tar.gz`
- Source archive SHA-256: `d76623373421df22fb4cf8817020cbb7ef15c725b9d5e45f17e189bfc384190f`
- Bundled inventory manifest SHA-256: `2a165696e79bb9c0251cd5ad63f425163a964c1563c0462b5db96dd203d62cf0`

`vendor/pyyaml/manifest.json` records each upstream file's SHA-256 and canonical
mode. No compiled LibYAML extension is included or loaded. The upstream
`cyaml.py` file remains unchanged as part of the recorded payload, but the loader
excludes its optional import path: that path otherwise imports ambient
`yaml._yaml`. Upstream PyYAML consequently selects its pure-Python implementation.

## Execution and failure behavior

The loader checks the pinned manifest, exact payload membership, regular-file
boundaries, modes, and file hashes. It imports the verified bytes from memory
under a private package namespace and leaves any existing `yaml` module intact.
The temporary importer is removed when initialization finishes. Standard
`__pycache__/*.pyc` files produced by tools such as `compileall` are ignored and
never executed. No dependency fallback is attempted on a verification failure;
the source audit reports `source.yaml-runtime` as failed.

YAML documents are parsed with `safe_load`. Arbitrary Python object tags are
rejected. An integrity failure should be handled through the existing release
repair/update flow, which reacquires verified release files. Editing the manifest
or installing a different global PyYAML package does not repair bundled drift.
