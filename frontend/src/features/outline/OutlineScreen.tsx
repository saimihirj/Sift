import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { ThemeMode } from "../../app/types";
import { getOutline, postAnalyticsEvent } from "../../lib/api/client";

type Props = {
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
  onExitSession: () => void;
  clientId: string;
  displayName: string;
};

export function OutlineScreen({ theme, onThemeChange, onExitSession, clientId, displayName }: Props) {
  const navigate = useNavigate();
  const { sessionId = "" } = useParams();
  const [content, setContent] = useState("Loading refined pitch...");
  const [status, setStatus] = useState("Generating refined pitch");

  useEffect(() => {
    let cancelled = false;
    if (!sessionId) {
      setContent("Session not found.");
      return;
    }
    void getOutline(sessionId)
      .then((response) => {
        if (cancelled) return;
        setContent(response.markdown);
        setStatus(`Generated with ${response.responseProfile === "balanced" ? "Sharper" : "Fast"}`);
        void postAnalyticsEvent({
          eventType: "outline_viewed",
          clientId,
          sessionId,
          displayName,
          pathname: `/outline/${sessionId}`,
          metadata: {
            responseProfile: response.responseProfile,
          },
        }).catch(() => undefined);
      })
      .catch((error) => {
        if (cancelled) return;
        setStatus("Refined pitch unavailable");
        setContent(error instanceof Error ? error.message : "Failed to load refined pitch");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  void theme;
  void onThemeChange;

  const handleDownload = () => {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `signal-refined-pitch-${sessionId || "session"}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const renderInline = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
      }
      return <span key={`${part}-${index}`}>{part}</span>;
    });
  };

  const renderMarkdown = (markdown: string) => {
    const lines = markdown.replace(/\r\n/g, "\n").split("\n");
    const blocks: Array<
      | { type: "h1" | "h2" | "h3" | "p"; text: string }
      | { type: "ul" | "ol"; items: string[] }
    > = [];
    let paragraph: string[] = [];
    let listType: "ul" | "ol" | null = null;
    let listItems: string[] = [];

    const flushParagraph = () => {
      if (!paragraph.length) {
        return;
      }
      blocks.push({ type: "p", text: paragraph.join(" ").trim() });
      paragraph = [];
    };

    const flushList = () => {
      if (!listType || !listItems.length) {
        return;
      }
      blocks.push({ type: listType, items: [...listItems] });
      listType = null;
      listItems = [];
    };

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) {
        flushParagraph();
        flushList();
        continue;
      }
      if (line.startsWith("# ")) {
        flushParagraph();
        flushList();
        blocks.push({ type: "h1", text: line.slice(2).trim() });
        continue;
      }
      if (line.startsWith("## ")) {
        flushParagraph();
        flushList();
        blocks.push({ type: "h2", text: line.slice(3).trim() });
        continue;
      }
      if (line.startsWith("### ")) {
        flushParagraph();
        flushList();
        blocks.push({ type: "h3", text: line.slice(4).trim() });
        continue;
      }
      if (line.startsWith("- ") || line.startsWith("* ")) {
        flushParagraph();
        if (listType && listType !== "ul") {
          flushList();
        }
        listType = "ul";
        listItems.push(line.slice(2).trim());
        continue;
      }
      const orderedMatch = line.match(/^\d+\.\s+(.*)$/);
      if (orderedMatch) {
        flushParagraph();
        if (listType && listType !== "ol") {
          flushList();
        }
        listType = "ol";
        listItems.push(orderedMatch[1].trim());
        continue;
      }
      flushList();
      paragraph.push(line);
    }

    flushParagraph();
    flushList();

    return blocks.map((block, index) => {
      switch (block.type) {
        case "h1":
          return <h1 key={`block-${index}`}>{renderInline(block.text)}</h1>;
        case "h2":
          return <h2 key={`block-${index}`}>{renderInline(block.text)}</h2>;
        case "h3":
          return <h3 key={`block-${index}`}>{renderInline(block.text)}</h3>;
        case "ul":
          return (
            <ul key={`block-${index}`}>
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        case "ol":
          return (
            <ol key={`block-${index}`}>
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>{renderInline(item)}</li>
              ))}
            </ol>
          );
        case "p":
          return <p key={`block-${index}`}>{renderInline(block.text)}</p>;
      }
    });
  };

  return (
    <div className="report-doc-shell">
      <header className="pane-header">
        <div>
          <span className="eyebrow">Ideate output</span>
          <h2>Refined pitch</h2>
        </div>
        <div className="status-stack">
          <div className="header-actions">
            <button type="button" className="ghost-button compact" onClick={() => navigate(-1)}>
              Back
            </button>
            <button type="button" className="ghost-button compact" onClick={handleDownload}>
              Download
            </button>
            <button type="button" className="ghost-button compact" onClick={onExitSession}>
              Exit
            </button>
          </div>
          <small>{status}</small>
        </div>
      </header>
      <main className="report-doc-main">
        <article className="outline-card report-doc-card outline-doc-card">
          <div className="report-doc-head">
            <div className="report-doc-title">
              <span className="eyebrow">Current draft</span>
              <h1>Refined from the current Ideate conversation</h1>
              <p>This is a working draft of the pitch story. Keep the Ideate chat going if you want a sharper version later.</p>
            </div>
          </div>
          <div className="doc-markdown">{renderMarkdown(content)}</div>
        </article>
      </main>
    </div>
  );
}
