import { ArrowUp, Paperclip, Sparkles } from "lucide-react";
import { useRef, useState } from "react";

interface ChatInputProps {
  onSend: (question: string) => void;
  disabled?: boolean;
  onSimplify: () => void;
}

export default function ChatInput({ onSend, disabled, onSimplify }: ChatInputProps) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = value.trim();
    if (!question || disabled) return;
    onSend(question);
    setValue("");
    if (inputRef.current) inputRef.current.style.height = "auto";
  }

  function resize() {
    const element = inputRef.current;
    if (element) {
      element.style.height = "auto";
      element.style.height = `${Math.min(element.scrollHeight, 150)}px`;
    }
  }

  return (
    <div className="composer-wrap">
      <form className="composer" onSubmit={submit}>
        <textarea
          ref={inputRef}
          value={value}
          onChange={(event) => { setValue(event.target.value); resize(); }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
          placeholder="Ask anything from your textbooks…"
          rows={1}
          aria-label="Your question"
          disabled={disabled}
        />
        <div className="composer-bottom">
          <div className="composer-tools">
            <button type="button" className="composer-tool" title="PDF upload will be added with backend support" onClick={() => window.alert("Textbook upload is not connected yet. For this prototype, ask questions from the sample study context.")}><Paperclip size={16} /><span>Sources</span></button>
            <button type="button" className="composer-tool simplify-tool" onClick={onSimplify} disabled={disabled}><Sparkles size={15} /><span>Explain simpler</span></button>
          </div>
          <div className="composer-send-area"><span className="enter-hint">↵ to send</span><button type="submit" className="send-button" disabled={!value.trim() || disabled} aria-label="Send question"><ArrowUp size={19} /></button></div>
        </div>
      </form>
      <p className="composer-note">Studywise can make mistakes. Verify important answers with your course material.</p>
    </div>
  );
}