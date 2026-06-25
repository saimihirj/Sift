import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, OutlineSlide, SiftSession } from "../../app/sift.types";
import { createChatAbortController, sendChatMessage } from "../../lib/api/client";

interface CopilotScreenProps {
  session: SiftSession;
  onStartOver: () => void;
}

function SendIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d="M13 1L1 5.5l5 1.5L7.5 13 13 1z" strokeLinejoin="round" />
    </svg>
  );
}

function OutlinePanel({ slides }: { slides: OutlineSlide[] }) {
  return (
    <div className="outline-panel" aria-label="Pitch deck outline">
      <div className="outline-panel-header">
        <span className="outline-panel-title">Pitch Outline</span>
        <button
          type="button"
          className="nav-link"
          style={{ fontSize: 11 }}
          onClick={() => {
            const text = slides
              .map((s) => `Slide ${s.slideNumber}: ${s.title}\n${s.notes}`)
              .join("\n\n");
            navigator.clipboard?.writeText(text).catch(() => null);
          }}
          aria-label="Copy outline to clipboard"
        >
          Copy
        </button>
      </div>
      {slides.map((slide) => (
        <div key={slide.slideNumber} className="outline-slide">
          <span className="outline-slide-num">{String(slide.slideNumber).padStart(2, "0")}</span>
          <div className="outline-slide-body">
            <span className="outline-slide-title">{slide.title}</span>
            <span className="outline-slide-note">{slide.notes}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.structured) {
    return (
      <div className={`message ${msg.role}`} aria-live="polite">
        <span className="message-role">{msg.role === "sift" ? "Sift" : "You"}</span>
        <div className="message-structured">
          <div className="message-structured-header">Analysis</div>
          <div className="message-structured-body">{msg.content}</div>
        </div>
      </div>
    );
  }
  return (
    <div className={`message ${msg.role}`} aria-live={msg.role === "sift" ? "polite" : undefined}>
      <span className="message-role">{msg.role === "sift" ? "Sift" : "You"}</span>
      <div className="message-bubble">{msg.content}</div>
    </div>
  );
}

export function CopilotScreen({ session, onStartOver }: CopilotScreenProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [outline, setOutline] = useState<OutlineSlide[] | null>(null);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const greeting: ChatMessage = {
      role: "sift",
      content: session.report
        ? `I reviewed ${session.sourceName ? `"${session.sourceName}"` : "your submission"} and found ${session.report.issues.length} issue${session.report.issues.length !== 1 ? "s" : ""}. Let us work through them. Which finding do you want to address first?`
        : "What are you working on? Walk me through your startup.",
      structured: false,
    };
    setMessages([greeting]);
  }, [session]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  const sendMessage = useCallback(async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || streaming) return;

    setInputValue("");
    setError("");

    const userMsg: ChatMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);

    let siftContent = "";
    const siftMsgId = Date.now();

    setMessages((prev) => [
      ...prev,
      { role: "sift", content: "", structured: false } as ChatMessage,
    ]);

    const ctrl = createChatAbortController();
    abortRef.current = ctrl;

    await sendChatMessage(
      session.sessionId,
      trimmed,
      ctrl.signal,
      {
        onDelta: (delta) => {
          siftContent += delta;
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "sift") {
              next[next.length - 1] = { ...last, content: siftContent };
            }
            return next;
          });
        },
        onDone: (data) => {
          setStreaming(false);
          abortRef.current = null;

          if (data.outline && Array.isArray(data.outline)) {
            setOutline(data.outline as OutlineSlide[]);
          }

          if (siftContent === "") {
            setMessages((prev) => prev.filter((_, i) => i !== prev.length - 1));
          }
        },
        onError: (err) => {
          setStreaming(false);
          abortRef.current = null;
          setError(err);
          setMessages((prev) => prev.filter((_, i) => i !== prev.length - 1));
        },
      },
      session.apiKey,
    );

    void siftMsgId;
  }, [inputValue, streaming, session]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  }

  function stopStreaming() {
    abortRef.current?.abort();
    setStreaming(false);
    abortRef.current = null;
  }

  return (
    <main className="page copilot-page">
      <div className="copilot-context-bar">
        <span className="copilot-context-label">
          {session.sourceName ? session.sourceName : "Co-Pilot"}
        </span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {session.report && (
            <span className="copilot-score-badge" aria-label={`Score: ${session.report.readinessScore}`}>
              {session.report.readinessScore} / 100
            </span>
          )}
          <button
            type="button"
            className="nav-link"
            onClick={onStartOver}
            aria-label="Start a new evaluation"
          >
            New
          </button>
        </div>
      </div>

      <div className="messages-list" aria-label="Conversation" aria-live="polite">
        {messages.map((msg, idx) => (
          <MessageBubble key={idx} msg={msg} />
        ))}

        {streaming && (
          <div className="message sift" aria-live="polite">
            <span className="message-role">Sift</span>
            <div className="message-bubble" aria-busy="true">
              <span className="streaming-cursor" aria-label="Sift is typing" />
            </div>
          </div>
        )}

        {outline && <OutlinePanel slides={outline} />}

        {error && (
          <div className="error-bar" role="alert">
            {error}
          </div>
        )}

        <div ref={endRef} aria-hidden="true" />
      </div>

      <div className="chat-input-bar">
        <textarea
          ref={inputRef}
          id="chat-input"
          className="chat-input"
          placeholder="Reply to Sift..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={streaming}
          aria-label="Your message"
        />
        {streaming ? (
          <button
            type="button"
            className="chat-send-btn"
            onClick={stopStreaming}
            aria-label="Stop generating"
          >
            Stop
          </button>
        ) : (
          <button
            id="chat-send-btn"
            type="button"
            className="chat-send-btn"
            onClick={() => void sendMessage()}
            disabled={!inputValue.trim()}
            aria-label="Send message"
          >
            <SendIcon />
          </button>
        )}
      </div>
    </main>
  );
}
