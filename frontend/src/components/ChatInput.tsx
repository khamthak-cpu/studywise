
import { useState, type FormEvent, type KeyboardEvent } from "react";
import { LoaderCircle, Send } from "lucide-react";

type ChatInputProps = {
  loading: boolean;
  onSend: (question: string) => void | Promise<void>;
};

export default function ChatInput({ loading, onSend }: ChatInputProps) {
  const [question, setQuestion] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const text = question.trim();
    if (!text || loading) return;

    setQuestion("");
    void onSend(text);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <textarea
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask StudyWise a question..."
        aria-label="Your question"
        rows={2}
        disabled={loading}
      />

      <button
        className="send-button"
        type="submit"
        disabled={loading || !question.trim()}
        aria-label="Send question"
      >
        {loading ? (
          <LoaderCircle className="spin" size={19} />
        ) : (
          <Send size={18} />
        )}
      </button>
    </form>
  );
}
