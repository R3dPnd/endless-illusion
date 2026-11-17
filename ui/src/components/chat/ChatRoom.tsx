import { useEffect, useRef } from "react";
import type { Chat } from "../../chat";
import { CopyButton, EmptyState, TypingIndicator } from "pnd-lib-react";
import { speakerFor } from "../../speakers";
import MessageBubble from "./MessageBubble";
import Roster from "./Roster";

export default function ChatRoom({ chat, status }: { chat: Chat; status: string }) {
  const { messages, active, finalText } = chat;
  const running = status === "running";
  const typing = running && active ? speakerFor(active) : null;
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);

  // Follow new messages unless the reader has scrolled up.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [messages.length, active]);

  function onScroll() {
    const el = scrollRef.current;
    if (el) pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  }

  return (
    <div className="chat">
      <div className="toolbar">
        <Roster messages={messages} active={running ? active : undefined} />
        {finalText && <CopyButton text={finalText} label="Copy final" className="push-right" />}
      </div>
      <div className="chat__scroll" ref={scrollRef} onScroll={onScroll}>
        {messages.length === 0 ? (
          <EmptyState center>The agents' conversation appears here when you trigger a run.</EmptyState>
        ) : (
          messages.map((m) => <MessageBubble key={m.key} m={m} />)
        )}
        {typing && <TypingIndicator name={typing.name} color={typing.color} />}
      </div>
    </div>
  );
}
