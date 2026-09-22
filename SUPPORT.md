# Support

Synthesis Skills is solo-maintainer infrastructure. The support contract below
is how promotion stays sustainable; it was adopted 2026-09-21 (POL-2) and can
be upgraded per module when one earns it.

## Posture: community-maintained, opinions excluded

- Promoted enforcement and capability code is public and tested. Outsiders can
  use it, fix it, and extend it.
- The maintainer answers no tickets on promoted modules and ships no opinions
  in them. Workflow opinions (rule texts, catalogs, principal-specific
  defaults) live in private configuration, never in public defaults — every
  promoted guard and detector ships inert until its installing principal
  configures it.
- Bug reports with reproduction evidence are welcome and may be fixed; there
  is no response-time promise. Security and disclosure issues are the
  exception: report them privately and they are handled first.

## What belongs here

Mechanisms strangers can configure: detectors, guards, parsers, and
capabilities whose personal surface (accounts, names, site shapes, rule
texts) has been factored into configuration and audited out. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the promotion acceptance criteria.
