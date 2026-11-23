def build_followup_prompt(message):
    """A chat reply into a resumed session. Scope, authorization, and tools carry over from the run it continues."""
    return "\n".join(
        [
            "OPERATOR FOLLOW-UP (scope and authorization are unchanged from earlier in this conversation):",
            "",
            message.strip(),
        ]
    )


def build_prompt(agent, task, scope, authorization, orchestrated):
    """The run prompt sent to claude over stdin (user input never reaches argv)."""
    auth_line = authorization.strip() if authorization and authorization.strip() else "NONE PROVIDED — treat this as unauthorized; passive work only."
    scope_line = scope.strip() if scope and scope.strip() else "(none specified)"
    head = (
        "Per CLAUDE.md you are Dann of Thursday, the orchestrator. Confirm authorization, then route this to the right specialist subagent(s)."
        if orchestrated
        else "Operate strictly as the agent described in the appended dossier. Follow its Rules of Engagement."
    )
    return "\n".join(
        [
            head,
            "",
            f"TASK:\n{task.strip()}",
            "",
            f"SCOPE:\n{scope_line}",
            "",
            f"AUTHORIZATION:\n{auth_line}",
            "",
            "If no authorization is established, do the passive part, refuse the active part, and say what is missing. "
            "Report honestly; distinguish confirmed from suspected.",
        ]
    )
