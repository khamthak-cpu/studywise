
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type MouseEvent,
} from "react";

import {
  BookOpen,
  Bot,
  GraduationCap,
  Send,
  User,
  LoaderCircle,
  AlertCircle,
  Plus,
  ChartNoAxesCombined,
  MessageSquare,
  Trash2,
  Paperclip,
  X,
} from "lucide-react";

import ProductivityDashboard from "./components/ProductivityDashboard";

// --------------------------------------------------
// TYPES
// --------------------------------------------------

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
};

type Conversation = {
  id: number;
  title: string;
  updated_at: string;
  message_count: number;
};

type Attachment = {
  id: string;
  filename: string;
  kind: string;
};

type Page = "chat" | "productivity";

// --------------------------------------------------
// CONFIGURATION
// --------------------------------------------------

const API_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const STUDENT_ID = "demo-student";

const MAX_FILE_SIZE = 15 * 1024 * 1024;
const MAX_ATTACHMENTS = 5;

const ALLOWED_EXTENSIONS = [
  ".pdf",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".docx",
  ".txt",
];

// --------------------------------------------------
// API HELPER
// --------------------------------------------------

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text();

    let detail = `Request failed (${response.status})`;

    try {
      const parsed = JSON.parse(body);

      if (typeof parsed.detail === "string") {
        detail = parsed.detail;
      }
    } catch {
      if (body) detail = body;
    }

    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// --------------------------------------------------
// ANSWER HELPER
// --------------------------------------------------

function getAnswer(data: unknown): string {
  if (typeof data === "string") {
    return data;
  }

  if (data && typeof data === "object") {
    const result = data as Record<string, unknown>;

    for (const key of [
      "answer",
      "response",
      "message",
      "output",
      "content",
    ]) {
      if (typeof result[key] === "string") {
        return result[key] as string;
      }
    }
  }

  return "The server responded, but I couldn't identify the answer field.";
}

// --------------------------------------------------
// MAIN APP
// --------------------------------------------------

export default function App() {
  // Navigation
  const [activePage, setActivePage] = useState<Page>("chat");

  // Chat
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Conversation history
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] =
    useState<number | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Attachments
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ------------------------------------------------
  // REFRESH CHAT HISTORY
  // ------------------------------------------------

  async function refreshHistory() {
    const result = await apiRequest<{ items: Conversation[] }>(
      `/history/conversations?student_id=${encodeURIComponent(STUDENT_ID)}`,
    );

    setConversations(result.items);
  }

  // ------------------------------------------------
  // LOAD CHAT HISTORY ON STARTUP
  // ------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      try {
        const result = await apiRequest<{ items: Conversation[] }>(
          `/history/conversations?student_id=${encodeURIComponent(STUDENT_ID)}`,
        );

        if (!cancelled) {
          setConversations(result.items);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            `Couldn't load chat history: ${
              err instanceof Error ? err.message : "Unknown error"
            }`,
          );
        }
      } finally {
        if (!cancelled) {
          setHistoryLoading(false);
        }
      }
    }

    void loadHistory();

    return () => {
      cancelled = true;
    };
  }, []);

  // ------------------------------------------------
  // CREATE NEW CHAT
  // ------------------------------------------------

  function startNewChat() {
    setActiveConversationId(null);
    setMessages([]);
    setQuestion("");
    setAttachments([]);
    setError("");
    setActivePage("chat");
  }

  // ------------------------------------------------
  // OPEN EXISTING CONVERSATION
  // ------------------------------------------------

  async function openConversation(conversationId: number) {
    if (loading || uploading) return;

    setError("");
    setActivePage("chat");

    try {
      const conversation = await apiRequest<{
        id: number;
        messages: Message[];
      }>(
        `/history/conversations/${conversationId}?student_id=${encodeURIComponent(
          STUDENT_ID,
        )}`,
      );

      setActiveConversationId(conversation.id);
      setMessages(conversation.messages);
      setQuestion("");

      // Attachments from an older conversation are not
      // loaded into the current attachment selection.
      setAttachments([]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Couldn't open this conversation.",
      );
    }
  }

  // ------------------------------------------------
  // DELETE CONVERSATION
  // ------------------------------------------------

  async function deleteConversation(
    event: MouseEvent<HTMLButtonElement>,
    conversationId: number,
  ) {
    event.stopPropagation();

    if (loading || uploading) return;

    const confirmed = window.confirm(
      "Delete this conversation permanently?",
    );

    if (!confirmed) return;

    try {
      await apiRequest<void>(
        `/history/conversations/${conversationId}?student_id=${encodeURIComponent(
          STUDENT_ID,
        )}`,
        {
          method: "DELETE",
        },
      );

      setConversations((current) =>
        current.filter(
          (conversation) => conversation.id !== conversationId,
        ),
      );

      if (activeConversationId === conversationId) {
        startNewChat();
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Couldn't delete this conversation.",
      );
    }
  }

  // ------------------------------------------------
  // CREATE CONVERSATION IF NEEDED
  // ------------------------------------------------

  async function ensureConversation(): Promise<number> {
    if (activeConversationId !== null) {
      return activeConversationId;
    }

    const created = await apiRequest<{ id: number }>(
      "/history/conversations",
      {
        method: "POST",
        body: JSON.stringify({
          student_id: STUDENT_ID,
          title: "New chat",
        }),
      },
    );

    setActiveConversationId(created.id);

    await refreshHistory();

    return created.id;
  }

  // ------------------------------------------------
  // UPLOAD FILE
  // ------------------------------------------------

  async function uploadFile(file: File) {
    if (loading || uploading) return;

    const extension = file.name
      .slice(file.name.lastIndexOf("."))
      .toLowerCase();

    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      setError(
        "Unsupported file type. Please upload a PDF, image, DOCX, or TXT file.",
      );
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setError("File size must be 15 MB or less.");
      return;
    }

    if (attachments.length >= MAX_ATTACHMENTS) {
      setError("You can attach a maximum of 5 files.");
      return;
    }

    setError("");
    setUploading(true);

    try {
      // The upload endpoint requires an existing conversation.
      const conversationId = await ensureConversation();

      const formData = new FormData();

      formData.append("file", file);
      formData.append("student_id", STUDENT_ID);
      formData.append("conversation_id", String(conversationId));

      // Do not manually set Content-Type for FormData.
      const response = await fetch(`${API_URL}/uploads`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const body = await response.text();

        let detail = "File upload failed.";

        try {
          const parsed = JSON.parse(body);

          if (typeof parsed.detail === "string") {
            detail = parsed.detail;
          }
        } catch {
          if (body) detail = body;
        }

        throw new Error(detail);
      }

      const uploaded = await response.json();

      const newAttachment: Attachment = {
        id: uploaded.id,
        filename: uploaded.filename,
        kind: uploaded.kind,
      };

      setAttachments((current) => [
        ...current,
        newAttachment,
      ]);

      await refreshHistory();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Couldn't upload the file.",
      );
    } finally {
      setUploading(false);
    }
  }

  // ------------------------------------------------
  // REMOVE ATTACHMENT FROM CURRENT SELECTION
  // ------------------------------------------------

  function removeAttachment(attachmentId: string) {
    setAttachments((current) =>
      current.filter((file) => file.id !== attachmentId),
    );
  }

  // ------------------------------------------------
  // SEND QUESTION
  // ------------------------------------------------

  async function sendQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const text = question.trim();

    if (!text || loading || uploading) return;

    setError("");
    setQuestion("");
    setActivePage("chat");
    setLoading(true);

    let conversationId: number | null = activeConversationId;

    try {
      // Create a conversation if this is the first question.
      conversationId = await ensureConversation();

      // Send the question and selected attachments to the
      // existing backend /ask endpoint.
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: text,
          student_id: STUDENT_ID,
          conversation_id: conversationId,
          attachment_ids: attachments.map((file) => file.id),
        }),
      });

      const raw = await response.text();

      let data: unknown;

      try {
        data = raw ? JSON.parse(raw) : {};
      } catch {
        data = raw;
      }

      if (!response.ok) {
        const detail =
          data &&
          typeof data === "object" &&
          "detail" in data &&
          typeof data.detail === "string"
            ? data.detail
            : `Request failed (${response.status})`;

        throw new Error(detail);
      }

      // The backend already saves the user question and
      // assistant answer. Reload the conversation instead
      // of saving the messages a second time.
      const answer = getAnswer(data);

      if (!answer) {
        throw new Error("StudyWise returned an empty answer.");
      }

      const conversation = await apiRequest<{
        id: number;
        messages: Message[];
      }>(
        `/history/conversations/${conversationId}?student_id=${encodeURIComponent(
          STUDENT_ID,
        )}`,
      );

      setMessages(conversation.messages);

      await refreshHistory();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Couldn't complete your request. Check the backend connection.",
      );

      // If the backend saved the question before an error,
      // reload the conversation so the UI stays in sync.
      try {
        if (conversationId !== null) {
          const conversation = await apiRequest<{
            id: number;
            messages: Message[];
          }>(
            `/history/conversations/${conversationId}?student_id=${encodeURIComponent(
              STUDENT_ID,
            )}`,
          );

          setMessages(conversation.messages);
        }

        await refreshHistory();
      } catch {
        // Preserve the original error.
      }
    } finally {
      setLoading(false);
    }
  }

  // ------------------------------------------------
  // UI
  // ------------------------------------------------

  return (
    <div className="app-shell">
      {/* SIDEBAR */}

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <GraduationCap size={25} />
          </div>

          <div>
            <h1>StudyWise</h1>
            <p>Your learning companion</p>
          </div>
        </div>

        <button
          className="new-chat-button"
          onClick={startNewChat}
          type="button"
        >
          <Plus size={18} />
          New conversation
        </button>

        <div className="sidebar-label">
          YOUR STUDY SPACE
        </div>

        <button
          type="button"
          className={`sidebar-item ${
            activePage === "chat" ? "active" : ""
          }`}
          onClick={() => setActivePage("chat")}
        >
          <BookOpen size={18} />
          <span>Study assistant</span>
        </button>

        <button
          type="button"
          className={`sidebar-item ${
            activePage === "productivity" ? "active" : ""
          }`}
          onClick={() => setActivePage("productivity")}
        >
          <ChartNoAxesCombined size={18} />
          <span>Productivity</span>
        </button>

        {/* CHAT HISTORY */}

        <div className="history-heading">
          <span>RECENT CHATS</span>
          <MessageSquare size={15} />
        </div>

        <div className="history-list">
          {historyLoading ? (
            <p className="history-empty">
              Loading chats...
            </p>
          ) : conversations.length === 0 ? (
            <p className="history-empty">
              Your conversations will appear here.
            </p>
          ) : (
            conversations.map((conversation) => (
              <div
                className={`history-row ${
                  activeConversationId === conversation.id
                    ? "selected"
                    : ""
                }`}
                key={conversation.id}
              >
                <button
                  type="button"
                  className="history-chat-button"
                  onClick={() =>
                    void openConversation(conversation.id)
                  }
                  disabled={loading || uploading}
                  title={conversation.title}
                >
                  <MessageSquare size={15} />

                  <span>{conversation.title}</span>
                </button>

                <button
                  type="button"
                  className="history-delete-button"
                  aria-label={`Delete ${conversation.title}`}
                  title="Delete conversation"
                  onClick={(event) =>
                    void deleteConversation(
                      event,
                      conversation.id,
                    )
                  }
                  disabled={loading || uploading}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>

        <div className="sidebar-footer">
          <div className="status-dot" />
          <span>StudyWise workspace</span>
        </div>
      </aside>

      {/* MAIN PANEL */}

      <main className="main-panel">
        <header className="topbar">
          <div className="mobile-brand">
            <GraduationCap size={22} />
            <strong>StudyWise</strong>
          </div>

          <div className="topbar-title">
            {activePage === "chat"
              ? "Study assistant"
              : "Productivity"}
          </div>

          <div className="connection-label">
            <span className="status-dot" />
            Local workspace
          </div>
        </header>

        {/* PRODUCTIVITY PAGE */}

        {activePage === "productivity" ? (
          <ProductivityDashboard />
        ) : (
          <>
            {/* CHAT AREA */}

            <section className="chat-area">
              {messages.length === 0 ? (
                <div className="welcome">
                  <div className="welcome-icon">
                    <BookOpen size={30} />
                  </div>

                  <p className="eyebrow">
                    YOUR PERSONAL STUDY SPACE
                  </p>

                  <h2>
                    What would you like to learn today?
                  </h2>

                  <p className="welcome-description">
                    Ask a question, explore a topic, or get help
                    understanding something you're studying.
                  </p>

                  <div className="suggestion-grid">
                    {[
                      "Explain a difficult concept",
                      "Help me understand a topic",
                      "Give me a step-by-step explanation",
                    ].map((suggestion) => (
                      <button
                        type="button"
                        className="suggestion-card"
                        key={suggestion}
                        onClick={() => setQuestion(suggestion)}
                      >
                        <span>{suggestion}</span>
                        <span className="suggestion-arrow">
                          ↗
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="messages">
                  {messages.map((message) => (
                    <article
                      className={`message message-${message.role}`}
                      key={message.id}
                    >
                      <div className="avatar">
                        {message.role === "user" ? (
                          <User size={18} />
                        ) : (
                          <Bot size={19} />
                        )}
                      </div>

                      <div className="message-body">
                        <div className="message-author">
                          {message.role === "user"
                            ? "You"
                            : "StudyWise"}
                        </div>

                        <div className="message-content">
                          {message.content}
                        </div>
                      </div>
                    </article>
                  ))}

                  {loading && (
                    <div className="message message-assistant">
                      <div className="avatar">
                        <Bot size={19} />
                      </div>

                      <div className="message-body">
                        <div className="message-author">
                          StudyWise
                        </div>

                        <div className="loading-text">
                          <LoaderCircle
                            className="spin"
                            size={17}
                          />
                          Preparing your answer...
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </section>

            {/* COMPOSER */}

            <footer className="composer-area">
              {error && (
                <div className="error-message" role="alert">
                  <AlertCircle size={18} />
                  <span>{error}</span>
                </div>
              )}

              {/* ATTACHMENT PREVIEWS */}

              {attachments.length > 0 && (
                <div className="attachment-list">
                  {attachments.map((file) => (
                    <div
                      className="attachment-chip"
                      key={file.id}
                    >
                      <Paperclip size={14} />

                      <span title={file.filename}>
                        {file.filename}
                      </span>

                      <button
                        type="button"
                        onClick={() =>
                          removeAttachment(file.id)
                        }
                        aria-label={`Remove ${file.filename}`}
                        title="Remove attachment"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <form
                className="composer"
                onSubmit={sendQuestion}
              >
                {/* HIDDEN FILE INPUT */}

                <input
                  ref={fileInputRef}
                  type="file"
                  hidden
                  accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.txt"
                  onChange={(event) => {
                    const file = event.target.files?.[0];

                    if (file) {
                      void uploadFile(file);
                    }

                    // Allows selecting the same file again.
                    event.target.value = "";
                  }}
                />

                {/* ATTACH BUTTON */}

                <button
                  type="button"
                  className="attach-button"
                  onClick={() =>
                    fileInputRef.current?.click()
                  }
                  disabled={
                    loading ||
                    uploading ||
                    attachments.length >= MAX_ATTACHMENTS
                  }
                  title="Attach a file"
                  aria-label="Attach a file"
                >
                  {uploading ? (
                    <LoaderCircle
                      className="spin"
                      size={19}
                    />
                  ) : (
                    <Paperclip size={19} />
                  )}
                </button>

                {/* QUESTION INPUT */}

                <textarea
                  value={question}
                  onChange={(event) =>
                    setQuestion(event.target.value)
                  }
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  placeholder="Ask StudyWise a question..."
                  aria-label="Your question"
                  rows={2}
                  disabled={loading || uploading}
                />

                {/* SEND BUTTON */}

                <button
                  className="send-button"
                  type="submit"
                  disabled={
                    loading ||
                    uploading ||
                    !question.trim()
                  }
                  aria-label="Send question"
                >
                  {loading ? (
                    <LoaderCircle
                      className="spin"
                      size={19}
                    />
                  ) : (
                    <Send size={18} />
                  )}
                </button>
              </form>

              <p className="composer-note">
                {uploading
                  ? "Uploading your file..."
                  : "StudyWise can make mistakes. Verify important information."}
              </p>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
