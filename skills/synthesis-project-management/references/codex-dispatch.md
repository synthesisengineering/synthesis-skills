# Dispatching to Codex — the wrapper and the failures it removes

`scripts/codex_dispatch.py` is the supported path for sending a prompt to
Codex non-interactively. Use it instead of shelling out to `codex` directly.

```bash
python3 scripts/codex_dispatch.py --doctor
python3 scripts/codex_dispatch.py --prompt-file brief.md --out review.txt --report-only
```

Three failures it removes, each observed in production on 2026-08-30:

- **The silent stdin hang.** `codex exec` reads stdin when stdin is open.
  Backgrounded from a shell that leaves it open, it prints
  `Reading additional input from stdin...` and blocks forever. One dispatch
  sat at 0.0% CPU with a 39-byte output file for two and a half hours while
  the dispatching agent assumed a long review was running. The wrapper always
  passes `stdin=DEVNULL`.
- **Stall indistinguishable from work.** The wrapper watches *output growth*,
  not elapsed time, so a genuinely slow review is not killed while a blocked
  process is. It reports which one it found.
- **"Codex is unavailable."** The binary is not on PATH; it lives under
  `~/.codex/plugins/`. An agent that runs `codex` and gets *command not
  found* may wrongly report that cross-agent dispatch is impossible and stop.
  `--doctor` resolves the binary, prints the version, and proves
  authentication with a live round trip. Never report Codex as unreachable
  without running it.
