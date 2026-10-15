/** Surface the most useful field per tool without dumping huge payloads. */
export default function ToolInput({ name, input }: { name: string; input?: unknown }) {
  if (input == null) return null;
  const obj = input as Record<string, unknown>;
  const preview =
    (obj.subagent_type as string) ||
    (obj.description as string) ||
    (obj.query as string) ||
    (obj.command as string) ||
    (obj.url as string) ||
    (obj.pattern as string) ||
    (obj.file_path as string) ||
    "";
  if (!preview) return null;
  return (
    <span className="tool-input" title={name}>
      {String(preview).slice(0, 160)}
    </span>
  );
}
