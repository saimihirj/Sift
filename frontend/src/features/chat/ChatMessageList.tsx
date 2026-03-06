import { useEffect, useRef } from "react";

import type { ChatTurn } from "../../app/types";

type Props = {
  history: ChatTurn[];
  streamingAssistant: string;
};

export function ChatMessageList({ history, streamingAssistant }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [history, streamingAssistant]);

  return (
    <div className="message-list">
      {history.map((turn, index) => (
        <article key={`${turn.role}-${index}-${turn.content.slice(0, 16)}`} className={`message ${turn.role}`}>
          <span className="message-role">{turn.role === "assistant" ? "Mentor" : "You"}</span>
          <p>{turn.content}</p>
        </article>
      ))}
      {streamingAssistant && (
        <article className="message assistant streaming">
          <span className="message-role">Mentor</span>
          <p>{streamingAssistant}</p>
        </article>
      )}
      <div ref={endRef} />
    </div>
  );
}
