import { DELEGATE_TOOLS } from "../../chat";
import { Chip } from "../ui";
import FeedRow from "./FeedRow";
import ToolInput from "./ToolInput";

export default function ToolCallRow({ ts, name, input }: { ts: number; name: string; input?: unknown }) {
  const isTask = DELEGATE_TOOLS.has(name);
  return (
    <FeedRow ts={ts} variant={isTask ? "tool row--task" : "tool"}>
      <div>
        <Chip tone={isTask ? "task" : "tool"}>{isTask ? "→ delegate" : name}</Chip>
        <ToolInput name={name} input={input} />
      </div>
    </FeedRow>
  );
}
