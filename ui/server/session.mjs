/**
 * argv for `claude -p`. `--tools` withholds tools from the session;
 * `--allowedTools` only pre-approves them, so it is never the restriction.
 */
export function buildSessionArgs({ tools, mcpConfigPath, mcpTools = [], agentDef, systemPrompt }) {
  const args = [
    "-p",
    "--output-format", "stream-json",
    "--verbose",
    "--tools", tools.join(","),
    "--strict-mcp-config",
  ];
  if (mcpConfigPath) args.push("--mcp-config", mcpConfigPath);
  args.push("--allowedTools", [...tools, ...mcpTools].join(","));
  if (agentDef) args.push("--agent", agentDef);
  if (systemPrompt) args.push("--append-system-prompt", systemPrompt);
  return args;
}
