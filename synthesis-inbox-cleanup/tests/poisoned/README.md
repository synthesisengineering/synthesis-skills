# Adversarial test fixtures

These `.eml` files are attacker-shaped emails. They contain prompt-injection payloads designed to manipulate an LLM-augmented email cleanup pipeline into making a write that benefits the attacker — typically adding their domain to `never_touch`, removing a legitimate domain from it, or trashing a target's mail.

The fixtures are NOT real malicious mail — they are constructed test cases that mimic the shape of indirect prompt injection seen in the wild. Each one targets a specific defense layer.

## Running the tests

```bash
cd ~/.claude/skills/synthesis-inbox-cleanup
python3 tests/run_poisoned.py
```

Exit code 0 means every fixture was correctly neutralized. Non-zero means at least one defense layer regressed.

## The fixtures

| File | Attack | Defense layer it tests |
|---|---|---|
| `subject_injection.eml` | Instruction injection in the Subject header | Layer 5 (sanitize + demarcate) |
| `body_injection.eml` | Plain-text body injection with fake conversation framing | Layer 5 + Layer 3 (constrained output) |
| `html_hidden_injection.eml` | HTML hidden via `display:none`, white-on-white, comments | Layer 5 (HTML strip) |
| `unicode_trickery.eml` | Zero-width chars, BOM, RTL marks, homoglyph swaps | Layer 5 (Unicode normalize + invisible strip) |

## When to add a new fixture

- A real injection attempt was seen in production and reached the LLM (even if defenses caught it downstream)
- A new attack pattern is documented in security research
- The sanitizer or rule resolver is modified in a way that could regress prior protections

A new fixture should always come with a corresponding entry in `run_poisoned.py` that asserts the expected neutralization.
