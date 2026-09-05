"""Shared recovery wording; this module does not verify or mutate client state."""

RECORDED_SESSION_SCOPE = "recorded-selected-client-sessions"
RECORDED_SESSION_DETAIL = (
    "Recorded selected-client session evidence, not acceptance of the invoking task."
)


def recovery_instruction(clients, *, initial=False):
    """Prefer existing conversations, conditional on genuine lifecycle evidence."""
    names = {"claude": "Claude Code", "codex": "Codex"}
    selected = list(dict.fromkeys(clients))
    steps = [
        "restart %s and reopen the existing %s if supported"
        % (names[client], "chat" if client == "claude" else "task")
        for client in selected
    ]
    if not steps:
        steps = ["restart selected clients and reopen the existing conversation if supported"]
    advice = "; ".join(steps) + (
        ". Continue only after a genuine transcript-bound SessionStart for the same "
        "session UUID reports the installed version and enabled immutable plugin root, "
        "and loaded skill metadata matches. If same-session recovery is unsupported "
        "or those checks fail, start a new conversation and verify its fresh SessionStart."
    )
    if initial:
        advice += " If there is no existing conversation, start one after restart."
    if "codex" in selected:
        advice += (
            " If Codex shows pending hook review, approve the synthesis-skills hooks; "
            "human trust is separate from evidence that the hooks executed."
        )
    return advice
