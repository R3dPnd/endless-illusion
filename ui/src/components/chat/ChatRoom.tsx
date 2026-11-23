import { useEffect, useRef, type ReactNode } from "react";
import type { Chat } from "../../chat";
import { Button, CopyButton, EmptyState, TypingIndicator } from "pnd-lib-react";
import { speakerFor } from "../../speakers";
import Composer from "./Composer";
import MessageBubble from "./MessageBubble";
import Roster from "./Roster";

interface Props {
  chat: Chat;
  status: string;
  /** Live console only; the archive replay is read-only and omits these. */
  canReply?: boolean;
  replyAgent?: string;
  onReply?: (text: string) => void;
  onClear?: () => void;
  /** Extra toolbar controls (e.g. the Monitor toggle). */
  actions?: ReactNode;
}

export default function ChatRoom({ chat, status, canReply, replyAgent, onReply, onClear, actions }: Props) {
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
        <span className="push-right chat__actions">
          {finalText && <CopyButton text={finalText} label="Copy final" />}
          {actions}
          {onClear && messages.length > 0 && (
            <Button variant="link" onClick={onClear} disabled={running}>
              New chat
            </Button>
          )}
        </span>
      </div>
      <div className="chat__scroll" ref={scrollRef} onScroll={onScroll}>
        {messages.length === 0 ? (
          <EmptyState center>The agents' conversation appears here when you trigger a run.</EmptyState>
        ) : (
          messages.map((m) => <MessageBubble key={m.key} m={m} />)
        )}
        {typing && <TypingIndicator name={typing.name} color={typing.color} />}
      </div>
      {onReply && messages.length > 0 && (
        <Composer
          disabled={!canReply}
          to={replyAgent ? speakerFor(replyAgent).name : undefined}
          running={running}
          onSend={(text) => {
            pinned.current = true;
            onReply(text);
          }}
        />
      )}
    </div>
  );
}
