# Canonical JSON for receipt bindings

This contract pins the byte representation used by
`coordination-check-staged-v1`. It documents the existing Python producer;
it is not RFC 8785/JCS. Other receipt schemas must explicitly adopt this
contract before their serialization can be changed.

For a check-staged receipt, remove only its top-level `binding_sha256` member,
then serialize the remaining object with:

```python
json.dumps(receipt_without_binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

The binding is the lowercase hexadecimal SHA-256 digest of those bytes.
The hash input has no byte-order mark, spaces added by the encoder, indentation,
or trailing newline. Pretty-printed receipt files may have whitespace; parse
them before reconstructing the binding. Hashing the file bytes is incorrect.

## Values and ordering

- Object keys are strings, ordered by Unicode code point at every depth.
  Array order is retained and is part of the binding. No Unicode normalization,
  path normalization, timestamp conversion, or list sorting takes place.
- Separators are exactly comma and colon. A slash is not escaped.
- `ensure_ascii=True` is the Python default and is required. Non-ASCII code
  points use lowercase `\u` escapes; non-BMP code points use a surrogate pair.
  Quote, backslash, backspace, form feed, newline, carriage return and tab use
  their JSON escapes. Other control characters use lowercase hex escapes.
- Integers use decimal digits, with a minus sign for negative values. There is
  no leading plus or zero padding. Booleans are `true` and `false`, not integers;
  the null value is `null`.
- Finite floating-point values use CPython's binary64 JSON representation.
  Integral floats retain `.0` when emitted in decimal form; negative zero is
  `-0.0`. Scientific notation uses lowercase `e`, an explicit positive exponent
  sign when appropriate, and at least two exponent digits. The frozen vectors
  pin boundary cases such as `1e-07`, `1e-06`, `1e+20`, and `1e+21`.
  Another implementation must reproduce these bytes, not use its own default
  number formatter. Check-staged-v1 currently contains no float fields.
- The supported receipt domain is JSON values with string object keys and
  finite numbers. Python's permissive NaN/Infinity and non-string-key encoding
  are not portable JSON and are not added to the receipt domain by this
  specification. This document does not introduce a new schema validator.

## Fixtures and verification

`tests/fixtures/receipts/check-staged.json` is a relocated receipt captured from
a successful authenticated check-staged invocation. Machine paths, project and
branch identifiers, session identity, Git tree identity and board content are
replaced with fixture values; the derived binding is recomputed after relocation.
The fixture grants no authority. Original evidence stays outside this public
repository.

`check-staged-input.json` contains the public inputs that recreate the relocated
receipt. `check-staged.canonical.json` is the exact hash input without a trailing
newline. `canonical-vectors.json` freezes nested ordering, escape sequences,
numbers, booleans/null, empty containers, and sequence order with independent
expected byte strings and digests.

`test_canonical_json_contract.py` compares the producer against the frozen
receipt and bytes, exercises the scalar vectors, and proves that array order
and inclusion of the binding member change the digest. Changes to this contract
require an explicit receipt-schema decision and regenerated, reviewed fixtures;
do not regenerate golden expectations merely to make a changed producer pass.
