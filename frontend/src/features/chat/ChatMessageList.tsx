import { useEffect, useMemo, useRef, useState } from "react";
import { API_BASE } from "../../lib/api/client";

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
  | { kind: "numbered"; items: string[] }
  | { kind: "table"; headers: string[]; rows: string[][] };

function normalizeMessageText(text: string): string {
  return (text || "")
    .replace(/\r\n/g, "\n")
    .replace(/^\s{0,3}#{1,6}\s*/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .trim();
}

function splitTableCells(line: string): string[] {
  const trimmed = line.trim();
  const rawCells = trimmed
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
  return rawCells;
}

function isMarkdownTable(lines: string[]): boolean {
  if (lines.length < 2) {
    return false;
  }
  const [header, divider, ...rows] = lines;
  if (!header.includes("|") || !divider.includes("|")) {
    return false;
  }
  const dividerCells = splitTableCells(divider);
  if (!dividerCells.length || !dividerCells.every((cell) => /^:?-{3,}:?$/.test(cell))) {
    return false;
  }
  return rows.length > 0 && rows.every((line) => line.includes("|"));
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
      if (isMarkdownTable(lines)) {
        const [header, , ...rowLines] = lines;
        const headers = splitTableCells(header);
        const rows = rowLines.map((line) => {
          const cells = splitTableCells(line);
          if (cells.length >= headers.length) {
            return cells.slice(0, headers.length);
          }
          return [...cells, ...Array.from({ length: headers.length - cells.length }, () => "")];
        });
        return { kind: "table", headers, rows } satisfies MessageBlock;
      }
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
        if (block.kind === "table") {
          return (
            <div key={`table-${index}`} className="message-table-wrap">
              <table className="message-table">
                <thead>
                  <tr>
                    {block.headers.map((header, headerIndex) => <th key={`header-${index}-${headerIndex}`}>{header}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={`row-${index}-${rowIndex}`}>
                      {row.map((cell, cellIndex) => <td key={`cell-${index}-${rowIndex}-${cellIndex}`}>{cell}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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

  const handleFeedback = async (messageIndex: number, rating: "up" | "down") => {
    if (!sessionId) return;
    try {
      await fetch(`${API_BASE}/api/chat/feedback`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, messageIndex, rating, reason: "" })
      });
      // Optionally show a toast or change icon color here
    } catch (e) {
      console.error("Failed to submit feedback", e);
    }
  };

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
          {turn.role === "assistant" && sessionId && (
            <div className="message-feedback" style={{ display: "flex", gap: "8px", marginTop: "8px", opacity: 0.6 }}>
              <button type="button" className="ghost-button compact" onClick={() => handleFeedback(index, "up")} title="Helpful response" style={{ fontSize: "12px", padding: "2px 6px" }}>👍</button>
              <button type="button" className="ghost-button compact" onClick={() => handleFeedback(index, "down")} title="Unhelpful or hallucinated" style={{ fontSize: "12px", padding: "2px 6px" }}>👎</button>
            </div>
          )}
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
