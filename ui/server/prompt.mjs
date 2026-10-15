/** The run prompt sent to claude over stdin (user input never reaches argv). */
export function buildPrompt({ agent, task, scope, authorization, orchestrated }) {
  const authLine = authorization?.trim()
    ? authorization.trim()
    : "NONE PROVIDED — treat this as unauthorized; passive work only.";
  const scopeLine = scope?.trim() ? scope.trim() : "(none specified)";
  const head = orchestrated
    ? "Per CLAUDE.md you are Dann of Thursday, the orchestrator. Confirm authorization, then route this to the right specialist subagent(s)."
    : `Operate strictly as the agent described in the appended dossier. Follow its Rules of Engagement.`;
  return [
    head,
    "",
    `TASK:\n${task.trim()}`,
    "",
    `SCOPE:\n${scopeLine}`,
    "",
    `AUTHORIZATION:\n${authLine}`,
    "",
    "If no authorization is established, do the passive part, refuse the active part, and say what is missing. Report honestly; distinguish confirmed from suspected.",
  ].join("\n");
}
