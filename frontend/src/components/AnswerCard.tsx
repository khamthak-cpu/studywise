import { BookOpenText, Copy, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import type { AskResponse } from "../types";
import ConfidenceBadge from "./ConfidenceBadge";
import SourceCitation from "./SourceCitation";

export default function AnswerCard({ response }: { response: AskResponse }) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(response.answer);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="answer-stack">
      <div className="answer-topline">
        <div className="answer-brand"><span className="assistant-avatar small-avatar"><BookOpenText size={16} /></span><strong>Studywise</strong><span className="answer-label">AI response</span></div>
        <ConfidenceBadge confidence={response.confidence} />
      </div>
      <div className="answer-content">{response.answer}</div>
      {response.sources?.length > 0 && (
        <section className="sources-section">
          <div className="section-label"><BookOpenText size={15} /> Sources used <span>{response.sources.length}</span></div>
          <div className="source-list">{response.sources.map((source, index) => <SourceCitation key={`${source.title}-${source.page ?? index}`} source={source} index={index} />)}</div>
        </section>
      )}
      <div className="answer-actions">
        <button className="text-action" onClick={copyAnswer}><Copy size={14} />{copied ? "Copied" : "Copy answer"}</button>
        <div className="feedback-actions" aria-label="Answer feedback">
          <button className={`icon-action ${feedback === "up" ? "selected" : ""}`} onClick={() => setFeedback(feedback === "up" ? null : "up")} aria-label="Helpful answer"><ThumbsUp size={15} /></button>
          <button className={`icon-action ${feedback === "down" ? "selected" : ""}`} onClick={() => setFeedback(feedback === "down" ? null : "down")} aria-label="Unhelpful answer"><ThumbsDown size={15} /></button>
        </div>
      </div>
      {response.mode === "offline" && <p className="source-disclaimer">Answers should be checked against the cited material. Demo responses and citations may be illustrative until the backend is connected.</p>}
    </div>
  );
}