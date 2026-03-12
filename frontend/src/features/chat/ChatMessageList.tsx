import { useEffect, useMemo, useRef, useState } from "react";

import type { ChatTurn } from "../../app/types";

type Props = {
  history: ChatTurn[];
  streamingAssistant: string;
  assistantLabel?: string;
  sessionId?: string;
  maxVisibleTurns?: number;
};

type MessageBlock =
  | { kind: "paragraph"; text: string }
  | { kind: "label"; text: string }
  | { kind: "bullets"; items: string[] }
  | { kind: "numbered"; items: string[] };

function normalizeMessageText(text: string): string {
  return (text || "")
    .replace(/\r\n/g, "\n")
    .replace(/^\s{0,3}#{1,6}\s*/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .trim();
}

function parseMessageBlocks(text: string): MessageBlock[] {
  const normalized = normalizeMessageText(text);
  if (!normalized) {
    return [];
  }
  return normalized
    .split(/\n{2,}/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => {
      const lines = chunk.split("\n").map((line) => line.trim()).filter(Boolean);
      if (lines.length > 1 && lines.every((line) => /^[-*]\s+/.test(line))) {
        return { kind: "bullets", items: lines.map((line) => line.replace(/^[-*]\s+/, "")) } satisfies MessageBlock;
      }
      if (lines.length > 1 && lines.every((line) => /^\d+\.\s+/.test(line))) {
        return { kind: "numbered", items: lines.map((line) => line.replace(/^\d+\.\s+/, "")) } satisfies MessageBlock;
      }
      if (lines.length === 1 && lines[0].length <= 72 && /:$/.test(lines[0])) {
        return { kind: "label", text: lines[0].slice(0, -1) } satisfies MessageBlock;
      }
      return { kind: "paragraph", text: chunk } satisfies MessageBlock;
    });
}

function MessageContent({ content }: { content: string }) {
  const blocks = useMemo(() => parseMessageBlocks(content), [content]);
  return (
    <div className="message-body">
      {blocks.map((block, index) => {
        if (block.kind === "label") {
          return <strong key={`label-${index}`} className="message-section-label">{block.text}</strong>;
        }
        if (block.kind === "bullets") {
          return (
            <ul key={`bullets-${index}`} className="message-list-block bulleted">
              {block.items.map((item, itemIndex) => <li key={`bullet-${index}-${itemIndex}`}>{item}</li>)}
            </ul>
          );
        }
        if (block.kind === "numbered") {
          return (
            <ol key={`numbered-${index}`} className="message-list-block numbered">
              {block.items.map((item, itemIndex) => <li key={`numbered-${index}-${itemIndex}`}>{item}</li>)}
            </ol>
          );
        }
        return <p key={`paragraph-${index}`} className="message-paragraph">{block.text}</p>;
      })}
    </div>
  );
}

export function ChatMessageList({
  history,
  streamingAssistant,
  assistantLabel = "Ideate",
  sessionId = "",
  maxVisibleTurns = 80,
}: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);
  const [showFullHistory, setShowFullHistory] = useState(false);

  useEffect(() => {
    setShowFullHistory(false);
  }, [sessionId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [history, streamingAssistant]);

  const hiddenTurns = Math.max(history.length - maxVisibleTurns, 0);
  const visibleHistory = useMemo(
    () => (showFullHistory || hiddenTurns === 0 ? history : history.slice(-maxVisibleTurns)),
    [history, hiddenTurns, maxVisibleTurns, showFullHistory],
  );

  return (
    <div className="message-list">
      {hiddenTurns > 0 ? (
        <button type="button" className="history-window-button" onClick={() => setShowFullHistory((current) => !current)}>
          {showFullHistory ? "Collapse earlier messages" : `Show ${hiddenTurns} earlier message${hiddenTurns === 1 ? "" : "s"}`}
        </button>
      ) : null}
      {visibleHistory.map((turn, index) => (
        <article key={`${turn.role}-${index}-${turn.content.slice(0, 16)}`} className={`message ${turn.role}`}>
          <span className="message-role">{turn.role === "assistant" ? assistantLabel : "You"}</span>
          <MessageContent content={turn.content} />
        </article>
      ))}
      {streamingAssistant && (
        <article className="message assistant streaming">
          <span className="message-role">{assistantLabel}</span>
          <MessageContent content={streamingAssistant} />
        </article>
      )}
      <div ref={endRef} />
    </div>
  );
}
