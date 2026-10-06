# Support

Synthesis Skills is solo-maintainer infrastructure. The support posture below
keeps it sustainable, and a module can move to a stronger posture when it earns
one.

## Before you report a problem

Run `synthesis doctor`. It checks the runtime, each harness's installed plugin,
hook wiring and trust, and Codex's settings, and it names hooks still waiting
for your approval in Codex's `/hooks` or in `muse plugins approve`. Many
install problems end there. If yours does not, include its output in the bug
report along with the harness, its version and `synthesis version`.

## Posture: community-maintained, opinions excluded

- Enforcement and capability code is public and tested. Anyone can use it, fix
  it, and extend it.
- The maintainer answers no tickets on code moved here from private layers and
  ships no opinions in it. Workflow opinions (rule texts, catalogs,
  person-specific defaults) live in private configuration, never in public
  defaults. Each such guard and detector ships inert until the person
  installing it configures it.
- Bug reports with reproduction evidence are welcome and may be fixed; there
  is no response-time promise. Security and disclosure issues are the
  exception: report them privately and they are handled first.

## What belongs here

Mechanisms strangers can configure: detectors, guards, parsers, and
capabilities whose personal surface (accounts, names, site shapes, rule texts)
has been factored into configuration and audited out. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the acceptance criteria.
