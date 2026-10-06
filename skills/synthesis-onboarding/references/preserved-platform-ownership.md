# Preserved: `skills/synthesis-onboarding/references/platform-ownership.md` before v5 (verbatim)

Retired: the platform ownership catalog was cut with the other catalogs; v5 requirements are Mac-first (Linux and WSL are an open decision, install-release evaluation section 5).

## Contents of the preserved text

- Console accessibility acceptance

---

# Accessible setup and platform ownership

`synthesis explain` describes each lifecycle state, keyboard-first named
arguments, `--help`, `--json`, unknown evidence, and human-owned trust/account
boundaries. It does not initialize mutable state. `synthesis machine platform
--json` displays the versioned mapping in `platform-ownership-v1.json`; Console's
`autostart status` consumes the identical catalog. Mapping is not installation
or service-state evidence.

| Environment | Existing service owner | Exact service target |
| --- | --- | --- |
| macOS | User launchd, Aqua login domain | `HOME/Library/LaunchAgents/org.synthesisengineering.console.plist` |
| Linux | systemd user manager | `XDG_CONFIG_HOME/systemd/user/synthesis-console.service` |
| WSL | Linux systemd user manager, when actually available | Same Linux path within the WSL user's home |
| Native Windows | Unsupported by the current runtime/service owners | None; no Task Scheduler or Windows service is invented |

An absent XDG setting defaults to `.config`, `.local/state`, or `.local/share`
under the selected home. Explicit roots must be canonical absolute POSIX paths.
The Console Python owner lives at `XDG_DATA_HOME/synthesis-console/python-runtime`.
Its service receipt and retirement journal live under
`XDG_STATE_HOME/synthesis-console/`. Public shared runtime roots remain the
existing git-hooks, message-guard, kernel and day-end owner roots; listing them
never grants mutation. WSL is a separate Linux installation and identity, not a
Windows-home alias. The mapping does not enable lingering or change WSL boot.

A declared machine inventory can include exactly
`{"id":"console","kind":"service","component":"console"}`.
Machine review reads only that declared unit and its existing version-2 receipt.
Exact path/hash/mode agreement is OBSERVED; missing both is ABSENT; mismatch,
unsafe objects or partial custody is UNKNOWN. It preserves files and never
claims running/stopped service state or repairs the unit itself. Real service
operations remain in Console's receipt owner, which refuses foreign files.

Console retirement commands now use its existing finite process owner: at most
30 seconds and 1 MiB combined output for each manager command, within a total
120-second operation. Cancellation and descendant cleanup must settle before
success or further manager commands. Unresolved custody preserves the journal;
it does not roll back through another uncontrolled command. Existing exact
retirement/rollback admission remains mandatory. Fixtures exercise both managers,
but this Mac's fixture results do not establish a real Linux/WSL installation.

Official platform grounding: Microsoft's
[WSL systemd guidance](https://learn.microsoft.com/en-us/windows/wsl/systemd)
and [WSL configuration reference](https://learn.microsoft.com/en-us/windows/wsl/wsl-config).
The declared user-manager prerequisite must be observed on the actual machine.

## Console accessibility acceptance

The shared layout supplies a skip link, named navigation, current-page markers,
visible keyboard focus, and a main landmark. The source selector uses native
details/summary, fieldset/legend and checkboxes with an explicit Apply button;
Escape returns focus to the summary. Changing a checkbox does not reload the
page. Conformance statuses are readable in text, independent of color, with
named columns and focus-preserving live audit feedback. A sandboxed Chromium
fixture verifies Tab/Enter/Space/Escape and the accessibility tree using synthetic
local data. It is not a human usability study or native-agent qualification.
