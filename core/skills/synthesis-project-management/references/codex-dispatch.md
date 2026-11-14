# Dispatching to Codex — the wrapper and the failures it removes

`scripts/codex_dispatch.py` is the supported path for sending a prompt to
Codex non-interactively. Use it instead of shelling out to `codex` directly.

```bash
python3 <skill>/scripts/codex_dispatch.py --doctor
python3 <skill>/scripts/codex_dispatch.py --prompt-file brief.md --out review.txt --report-only
python3 <skill>/scripts/codex_dispatch.py --prompt "one-line question" --stall-seconds 300
```

`--doctor` prints the binary it found, whether it is on PATH, its version, and
whether a trivial prompt came back (`authenticated: yes`); it exits 0 only when
the round trip worked. A dispatch prints the output (or with `--report-only`
just the final report after Codex's tool-use trace) and exits with Codex's
code, or 124 with `DISPATCH FAILED: <reason>` and the partial output's size
when it stalled.

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
- **"Codex is unavailable."** The binary is usually not on PATH: the CLI ships
  inside the desktop app and is put on PATH only in Codex-managed shells. An
  agent that runs `codex` and gets *command not found* may wrongly report that
  cross-agent dispatch is impossible and stop. `--doctor` resolves the binary,
  prints the version, and proves authentication with a live round trip. Never
  report Codex as unreachable without running it.

Discovery order: `SYNTHESIS_CODEX_BIN` when set (an empty value means absent,
and a path that is not executable is absent rather than a reason to fall
through), then PATH, then the documented desktop-app install locations. Each
found launcher must pass a bounded `--version` probe, because in 4.149.8 an old
PATH launcher that no longer ran shadowed the current one. This is the finder
`synthesis doctor` itself uses (`find_client` in `synthesis/doctor.py`), so the
doctor and the wrapper never disagree about where Codex is.
