
import { Bot, User } from "lucide-react";

export type ChatMessageData = {
  id: number;
  role: "user" | "assistant";
  content: string;
};

type ChatMessageProps = {
  message: ChatMessageData;
};

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <article className={`message message-${message.role}`}>
      <div className="avatar">
        {isUser ? <User size={18} /> : <Bot size={19} />}
      </div>

      <div className="message-body">
        <div className="message-author">
          {isUser ? "You" : "StudyWise"}
        </div>

        <div className="message-content">{message.content}</div>
      </div>
    </article>
  );
}
