import { useEffect, useMemo, useRef, useState } from "react";

import type { ChatTurn } from "../../app/types";

type Props = {
  history: ChatTurn[];
  streamingAssistant: string;
  assistantLabel?: string;
  sessionId?: string;
  maxVisibleTurns?: number;
};

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
          <p>{turn.content}</p>
        </article>
      ))}
      {streamingAssistant && (
        <article className="message assistant streaming">
          <span className="message-role">{assistantLabel}</span>
          <p>{streamingAssistant}</p>
        </article>
      )}
      <div ref={endRef} />
    </div>
  );
}
