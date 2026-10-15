import { useState } from "react";
import Button from "./Button";

export default function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be unavailable (permissions / insecure context); ignore.
    }
  }

  return (
    <Button variant="ghost" className="push-right" onClick={copy}>
      {copied ? "Copied" : label}
    </Button>
  );
}
