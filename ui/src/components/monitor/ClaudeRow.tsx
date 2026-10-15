import type { ClaudeEvent } from "../../types";
import { Chip } from "../ui";
import FeedRow from "./FeedRow";
import FinalRow from "./FinalRow";
import ToolCallRow from "./ToolCallRow";

/** Render one stream-json event from the claude CLI. */
export default function ClaudeRow({ ts, data }: { ts: number; data: ClaudeEvent }) {
  if (data.type === "system" && data.subtype === "init") {
    return (
      <FeedRow ts={ts} variant="init">
        <div>
          <strong>Session initialized</strong>
          {data.model && <Chip>{String(data.model)}</Chip>}
          {Array.isArray(data.tools) && <div className="tools">allowed: {data.tools.join(", ")}</div>}
        </div>
      </FeedRow>
    );
  }

  if (data.type === "assistant" && Array.isArray(data.message?.content)) {
    return (
      <>
        {data.message.content.map((block, i) => {
          if (block.type === "text") {
            return (
              <FeedRow key={i} ts={ts} variant="text">
                <div className="md">{(block as { text: string }).text}</div>
              </FeedRow>
            );
          }
          if (block.type === "tool_use") {
            const b = block as { name: string; input?: unknown };
            return <ToolCallRow key={i} ts={ts} name={b.name} input={b.input} />;
          }
          return null;
        })}
      </>
    );
  }

  if (data.type === "user" && Array.isArray(data.message?.content)) {
    if (data.message.content.some((b) => b.type === "tool_result")) {
      return (
        <FeedRow ts={ts} variant="result-in">
          <Chip tone="muted">tool result</Chip>
        </FeedRow>
      );
    }
  }

  if (data.type === "result") return <FinalRow ts={ts} data={data} />;

  return null;
}
