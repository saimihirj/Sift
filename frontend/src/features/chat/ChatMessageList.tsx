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

type InlineSpan =
  | { kind: "text"; text: string }
  | { kind: "bold"; text: string }
  | { kind: "code"; text: string };

type MessageBlock =
  | { kind: "paragraph"; spans: InlineSpan[] }
  | { kind: "label"; text: string }
  | { kind: "bullets"; items: InlineSpan[][] }
  | { kind: "numbered"; items: InlineSpan[][] }
  | { kind: "code_block"; language: string; code: string }
  | { kind: "table"; headers: string[]; rows: string[][] };

// ── Inline parser ────────────────────────────────────────────────────────────
// Converts `**bold**` and `` `code` `` into typed spans so we can render them
// as <strong> and <code> tags without stripping markdown during streaming.
function parseInline(text: string): InlineSpan[] {
  const spans: InlineSpan[] = [];
  // Pattern: **bold** or `code` — captured in order.
  const RE = /(\*\*(.+?)\*\*|`([^`]+)`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      spans.push({ kind: "text", text: text.slice(lastIndex, match.index) });
    }
    if (match[0].startsWith("**")) {
      spans.push({ kind: "bold", text: match[2] });
    } else {
      spans.push({ kind: "code", text: match[3] });
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    spans.push({ kind: "text", text: text.slice(lastIndex) });
  }
  return spans;
}

function renderInline(spans: InlineSpan[], keyPrefix: string): React.ReactNode[] {
  return spans.map((span, i) => {
    if (span.kind === "bold") {
      return <strong key={`${keyPrefix}-b${i}`}>{span.text}</strong>;
    }
    if (span.kind === "code") {
      return <code key={`${keyPrefix}-c${i}`} className="inline-code">{span.text}</code>;
    }
    return <span key={`${keyPrefix}-t${i}`}>{span.text}</span>;
  });
}

// ── Block-level normalise ────────────────────────────────────────────────────
function normalizeRaw(text: string): string {
  return (text || "")
    .replace(/\r\n/g, "\n")
    .replace(/^\s{0,3}#{1,6}\s*/gm, "")  // strip heading markers only
    .trim();
}

function splitTableCells(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isMarkdownTable(lines: string[]): boolean {
  if (lines.length < 2) return false;
  const [header, divider, ...rows] = lines;
  if (!header.includes("|") || !divider.includes("|")) return false;
  const dividerCells = splitTableCells(divider);
  if (!dividerCells.length || !dividerCells.every((c) => /^:?-{3,}:?$/.test(c))) return false;
  return rows.length > 0 && rows.every((l) => l.includes("|"));
}

function parseMessageBlocks(text: string): MessageBlock[] {
  const normalized = normalizeRaw(text);
  if (!normalized) return [];

  const blocks: MessageBlock[] = [];
  // Split on blank lines but handle fenced code blocks as atomic units.
  const lines = normalized.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (/^```/.test(line.trim())) {
      const lang = line.trim().slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // consume closing ```
      blocks.push({ kind: "code_block", language: lang, code: codeLines.join("\n") });
      continue;
    }

    // Accumulate a paragraph-group (lines until next blank)
    const group: string[] = [];
    while (i < lines.length && lines[i].trim() !== "") {
      group.push(lines[i].trim());
      i++;
    }
    // skip blank separator lines
    while (i < lines.length && lines[i].trim() === "") i++;

    if (!group.length) continue;

    // Table
    if (isMarkdownTable(group)) {
      const [header, , ...rowLines] = group;
      const headers = splitTableCells(header);
      const rows = rowLines.map((l) => {
        const cells = splitTableCells(l);
        return cells.length >= headers.length
          ? cells.slice(0, headers.length)
          : [...cells, ...Array.from({ length: headers.length - cells.length }, () => "")];
      });
      blocks.push({ kind: "table", headers, rows });
      continue;
    }

    // Bullet list
    if (group.length > 1 && group.every((l) => /^[-*]\s+/.test(l))) {
      blocks.push({
        kind: "bullets",
        items: group.map((l) => parseInline(l.replace(/^[-*]\s+/, ""))),
      });
      continue;
    }

    // Numbered list
    if (group.length > 1 && group.every((l) => /^\d+\.\s+/.test(l))) {
      blocks.push({
        kind: "numbered",
        items: group.map((l) => parseInline(l.replace(/^\d+\.\s+/, ""))),
      });
      continue;
    }

    // Label (single short line ending with colon)
    if (group.length === 1 && group[0].length <= 72 && /:$/.test(group[0])) {
      blocks.push({ kind: "label", text: group[0].slice(0, -1) });
      continue;
    }

    // Paragraph
    blocks.push({ kind: "paragraph", spans: parseInline(group.join(" ")) });
  }

  return blocks;
}

// ── Streaming block: stabilise re-renders ───────────────────────────────────
// During streaming we re-parse every delta tick. To prevent layout shifts:
// 1. Wrap the streaming article in `contain: content` via CSS.
// 2. Only re-render the *last* paragraph block as raw text while streaming;
//    all preceding completed blocks are rendered as full structured HTML.
function StreamingContent({ content }: { content: string }) {
  // Split into "settled" portion (all text up to the last \n\n) and
  // "in-flight" tail (what the model is still typing).
  const lastBreak = content.lastIndexOf("\n\n");
  const settled = lastBreak > 0 ? content.slice(0, lastBreak) : "";
  const tail = lastBreak > 0 ? content.slice(lastBreak + 2) : content;

  const settledBlocks = useMemo(() => parseMessageBlocks(settled), [settled]);

  return (
    <div className="message-body streaming-body">
      <BlockList blocks={settledBlocks} keyBase="settled" />
      {tail && (
        // Render the in-flight tail as a plain paragraph — no expensive parsing.
        // `contain: content` on the parent means its layout won't cascade.
        <p className="message-paragraph streaming-tail">
          {renderInline(parseInline(tail), "tail")}
        </p>
      )}
    </div>
  );
}

// ── Block renderer ───────────────────────────────────────────────────────────
function BlockList({ blocks, keyBase }: { blocks: MessageBlock[]; keyBase: string }) {
  return (
    <>
      {blocks.map((block, index) => {
        const k = `${keyBase}-${index}`;
        if (block.kind === "label") {
          return <strong key={k} className="message-section-label">{block.text}</strong>;
        }
        if (block.kind === "bullets") {
          return (
            <ul key={k} className="message-list-block bulleted">
              {block.items.map((spans, j) => (
                <li key={`${k}-li${j}`}>{renderInline(spans, `${k}-li${j}`)}</li>
              ))}
            </ul>
          );
        }
        if (block.kind === "numbered") {
          return (
            <ol key={k} className="message-list-block numbered">
              {block.items.map((spans, j) => (
                <li key={`${k}-li${j}`}>{renderInline(spans, `${k}-li${j}`)}</li>
              ))}
            </ol>
          );
        }
        if (block.kind === "code_block") {
          return (
            <div key={k} className="message-code-block">
              {block.language && <span className="code-lang-label">{block.language}</span>}
              <pre><code>{block.code}</code></pre>
            </div>
          );
        }
        if (block.kind === "table") {
          return (
            <div key={k} className="message-table-wrap">
              <table className="message-table">
                <thead>
                  <tr>{block.headers.map((h, hi) => <th key={`${k}-h${hi}`}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {block.rows.map((row, ri) => (
                    <tr key={`${k}-r${ri}`}>
                      {row.map((cell, ci) => <td key={`${k}-r${ri}-c${ci}`}>{cell}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        // paragraph
        return (
          <p key={k} className="message-paragraph">
            {renderInline((block as { kind: "paragraph"; spans: InlineSpan[] }).spans, k)}
          </p>
        );
      })}
    </>
  );
}

function MessageContent({ content }: { content: string }) {
  const blocks = useMemo(() => parseMessageBlocks(content), [content]);
  return (
    <div className="message-body">
      <BlockList blocks={blocks} keyBase="msg" />
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
          <StreamingContent content={streamingAssistant} />
        </article>
      )}
      <div ref={endRef} />
    </div>
  );
}
