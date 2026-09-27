# macOS file-access attribution and update acceptance

A desktop application's child engine may be the process macOS attributes file
access to. Do not assume that granting the visible application access grants its
versioned engine the same access. Identify the responsible process from the
observed denial and process chain for the actual client and version. This is a
diagnostic hypothesis until that evidence identifies the caller; an EACCES message
alone cannot distinguish TCC from filesystem modes, sandbox policy or other controls.

Apple documents user-controlled access to protected files in
[Controlling app access to files](https://support.apple.com/guide/security/controlling-app-access-to-files-secddd1d86a6/web)
and application-scoped protected-resource permissions in
[Resetting access to protected resources](https://developer.apple.com/documentation/xcode/resetting-access-to-protected-resources-in-macos).
This protocol does not reset privacy permissions, edit the TCC database or grant
Full Disk Access. User consent remains a separate action.

For an authorized acceptance check, use a synthetic file containing no private
information in the protected location the user selected. Retain the macOS version,
client version, engine path, process attribution, bundle/signing identity, requested
operation, observed result and evidence reference. Check the same file with an
unprotected positive control. Record a denial as a denial, never as authorization
to change permissions or disable confinement. Redact unrelated private paths from
shared reports.

After the user grants the specific intended permission, repeat the same bounded
read through the same client. On a genuinely observed client update that changes
the engine path, repeat it again and compare the exact engine/signing identity and
result. Label update survival VERIFIED only if the pre-update permitted operation
and post-update operation are both observed with the unchanged grant and protection.
A simulator, copied app, inferred signature or manually refreshed grant cannot
prove survival. Keep it UNKNOWN when no qualifying update or grant has occurred;
name the missing human action or empirical input. Native loading and file-access
acceptance are separate from installation-byte verification.
