-- Microsoft 365 / outlook.com inbox cleanup — Mac-native via Mail.app.
--
-- WHY AppleScript (not the IMAP manifest engine): Microsoft 365 blocks
-- basic-auth IMAP on most tenants, and the M365 MCP connector needs
-- admin consent. Mail.app already has the account authenticated locally,
-- so AppleScript reaches it with no admin wall and no extra credentials.
--
-- THIS IS A TEMPLATE. Copy it to a per-account file and customize:
--
--   cp m365_mailapp_cleanup.template.applescript ~/m365-myaccount.applescript
--   ${EDITOR} ~/m365-myaccount.applescript
--   osascript ~/m365-myaccount.applescript
--
-- Required edits (search for {PLACEHOLDER}):
--   {ACCOUNT_NAME}    — the Mail.app account name (Mail → Settings → Accounts)
--   {TRASH_FOLDER}    — usually "Deleted Items" on M365, "Trash" on Apple/Gmail
--   {ARCHIVE_FOLDER}  — usually "Archive" on M365 too
--   Sender / subject match clauses — replace the examples with your actual patterns
--
-- IDEMPOTENT + SELF-CORRECTING. Uses whole-set `whose` moves (NOT per-item
-- index refs, which go stale mid-move with error -1728). Re-running only
-- moves whatever currently matches. Safe to schedule via launchd / cron.
--
-- REVERSIBLE. Trash and archive both move messages, not delete. Recovery
-- is "drag back to Inbox in Mail.app" or "move via this script to a different
-- folder by editing the clauses."

tell application "Mail"
  set acct to account "{ACCOUNT_NAME}"
  set ibox to mailbox "Inbox" of acct
  set trashBox to mailbox "{TRASH_FOLDER}" of acct
  set archBox to mailbox "{ARCHIVE_FOLDER}" of acct
  set n0 to count of messages of ibox

  -- ─────────────────────────────────────────────────────────────────────
  -- TRASH: recurring auto-noise (notifications, expired codes, digests)
  -- ─────────────────────────────────────────────────────────────────────
  -- Pattern: move (every message of ibox whose <criterion>) to trashBox

  -- Example: trash a noisy notification sender
  -- move (every message of ibox whose sender contains "notifications@example.com") to trashBox

  -- Example: trash one-time sign-in codes (expire in 10 minutes)
  -- move (every message of ibox whose (sender contains "noreply@example.com" and subject contains "one-time sign in code")) to trashBox

  -- Example: trash auth provider expired codes
  -- move (every message of ibox whose (sender contains "id.atlassian.com" and (subject contains "code" or subject contains "Verifying"))) to trashBox

  -- ─────────────────────────────────────────────────────────────────────
  -- ARCHIVE: notifications worth keeping but not in inbox
  -- ─────────────────────────────────────────────────────────────────────
  -- Pattern: move (every message of ibox whose <criterion>) to archBox

  -- Example: archive sign-in notifications (audit trail, low importance)
  -- move (every message of ibox whose (sender contains "noreply@example.com" and subject contains "New Sign-In")) to archBox

  -- Example: archive past calendar cancellations
  -- move (every message of ibox whose subject starts with "Canceled:") to archBox

  -- ─────────────────────────────────────────────────────────────────────
  -- ANY MAIL FROM HUMANS STAYS IN INBOX. Do not add patterns that match
  -- human correspondence — keep this script purely for auto-mail noise.
  -- ─────────────────────────────────────────────────────────────────────

  set n1 to count of messages of ibox
  return "inbox_before=" & n0 & " inbox_after=" & n1 & " moved=" & (n0 - n1)
end tell
