import { useState } from "react";
import { Button } from "pnd-lib-react";

interface Props {
  disabled: boolean;
  running: boolean;
  /** Display name of the agent the reply goes to. */
  to?: string;
  onSend: (text: string) => void;
}

/** Reply box under the channel. Enter sends, Shift+Enter adds a line. */
export default function Composer({ disabled, running, to, onSend }: Props) {
  const [text, setText] = useState("");
  const canSend = !disabled && text.trim().length > 0;

  function send() {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  }

  const placeholder = running
    ? "Agents are working — you can reply when they finish…"
    : to
      ? `Reply to ${to}… (Enter to send, Shift+Enter for a new line)`
      : "Reply…";

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
    >
      <textarea
        className="composer__input"
        value={text}
        rows={2}
        placeholder={placeholder}
        aria-label="Reply"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            send();
          }
        }}
      />
      <Button type="submit" variant="primary" disabled={!canSend}>
        Send
      </Button>
    </form>
  );
}
