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

// ==================================================
// TYPES
// ==================================================

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

type EducationLevel =
  | "primary"
  | "middle"
  | "secondary"
  | "higher_secondary"
  | "college";

type AnswerMeta = {
  confidence: number;
  answered_from: string;
  sources: {
    title: string;
    section?: string | null;
    page?: number | null;
    url?: string | null;
    score?: number | null;
  }[];
};

// ==================================================
// CONFIGURATION
// ==================================================

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

const CLASS_OPTIONS: Record<EducationLevel, number[]> = {
  primary: [1, 2, 3, 4, 5],
  middle: [6, 7, 8],
  secondary: [9, 10],
  higher_secondary: [11, 12],
  college: [],
};

// const EDUCATION_LABELS: Record<EducationLevel, string> = {
//   primary: "Primary School",
//   middle: "Middle School",
//   secondary: "Secondary School",
//   higher_secondary: "Higher Secondary",
//   college: "College / Undergraduate",
// };

const DEGREE_OPTIONS = [
  "B.A.",
  "B.Sc.",
  "B.Com.",
  "B.Tech.",
  "B.E.",
  "BCA",
  "BBA",
  "B.Pharm.",
  "Other",
];

const SUBJECT_OPTIONS: Record<string, string[]> = {
  primary: [
    "English",
    "Mathematics",
    "EVS",
    "Hindi",
  ],

  middle: [
    "English",
    "Mathematics",
    "Science",
    "Social Science",
    "Hindi",
    "Computer Science",
  ],

  secondary: [
    "English",
    "Mathematics",
    "Science",
    "Social Science",
    "Hindi",
    "Computer Science",
  ],

  higher_secondary: [
    "Physics",
    "Chemistry",
    "Biology",
    "Mathematics",
    "English",
    "Computer Science",
    "Accountancy",
    "Economics",
    "Business Studies",
    "History",
    "Geography",
    "Political Science",
  ],
};

const DEGREE_SUBJECTS: Record<string, string[]> = {
  "B.Sc.": [
    "Physics",
    "Chemistry",
    "Mathematics",
    "Botany",
    "Zoology",
    "Computer Science",
  ],

  "B.A.": [
    "English",
    "History",
    "Political Science",
    "Economics",
    "Geography",
    "Sociology",
    "Psychology",
  ],

  "B.Com.": [
    "Accountancy",
    "Economics",
    "Business Studies",
    "Finance",
  ],

  "B.Tech.": [
    "Programming",
    "Data Structures",
    "Engineering Mathematics",
    "Physics",
    "Electronics",
  ],

  "B.E.": [
    "Programming",
    "Data Structures",
    "Engineering Mathematics",
    "Physics",
    "Electronics",
  ],

  BCA: [
    "Programming",
    "Database Management",
    "Computer Networks",
    "Mathematics",
  ],

  BBA: [
    "Management",
    "Marketing",
    "Finance",
    "Economics",
    "Business Studies",
  ],

  "B.Pharm.": [
    "Pharmaceutics",
    "Pharmacology",
    "Pharmaceutical Chemistry",
    "Pharmacognosy",
  ],

  Other: [
    "General Studies",
    "Mathematics",
    "Science",
    "English",
  ],
};


// ==================================================
// API HELPER
// ==================================================

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

// ==================================================
// ANSWER HELPER
// ==================================================

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

  return "";
}

// ==================================================
// MAIN APP
// ==================================================

export default function App() {
  // ------------------------------------------------
  // NAVIGATION
  // ------------------------------------------------

  const [activePage, setActivePage] = useState<Page>("chat");

  // ------------------------------------------------
  // CHAT
  // ------------------------------------------------

  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");

  // ------------------------------------------------
  // EDUCATION SETTINGS
  // ------------------------------------------------

  const [educationLevel, setEducationLevel] =
    useState<EducationLevel>("secondary");

  const [classLevel, setClassLevel] = useState("9");

  const [collegeDegree, setCollegeDegree] = useState("B.Sc.");

  const [studyYear, setStudyYear] = useState("1");

  // ------------------------------------------------
  // STUDY SETTINGS
  // ------------------------------------------------

  const [subject, setSubject] = useState("English");

  const [studyMode, setStudyMode] = useState("auto");

  const [codingMode, setCodingMode] = useState(false);

  // ------------------------------------------------
  // APP STATE
  // ------------------------------------------------

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const [answerMeta, setAnswerMeta] =
    useState<AnswerMeta | null>(null);

  // ------------------------------------------------
  // CONVERSATION HISTORY
  // ------------------------------------------------

  const [conversations, setConversations] =
    useState<Conversation[]>([]);

  const [activeConversationId, setActiveConversationId] =
    useState<number | null>(null);

  const [historyLoading, setHistoryLoading] = useState(true);

  // ------------------------------------------------
  // ATTACHMENTS
  // ------------------------------------------------

  const [attachments, setAttachments] = useState<Attachment[]>([]);

  const [uploading, setUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ==================================================
  // REFRESH HISTORY
  // ==================================================

  async function refreshHistory() {
    const result = await apiRequest<{ items: Conversation[] }>(
      `/history/conversations?student_id=${encodeURIComponent(
        STUDENT_ID,
      )}`,
    );

    setConversations(result.items);
  }

  // ==================================================
  // LOAD HISTORY ON STARTUP
  // ==================================================

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      try {
        const result = await apiRequest<{ items: Conversation[] }>(
          `/history/conversations?student_id=${encodeURIComponent(
            STUDENT_ID,
          )}`,
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

  // ==================================================
  // CHANGE EDUCATION LEVEL
  // ==================================================

  function changeEducationLevel(value: EducationLevel) {
    setEducationLevel(value);

    const defaults: Record<EducationLevel, string> = {
      primary: "1",
      middle: "6",
      secondary: "9",
      higher_secondary: "11",
      college: "",
    };

    setClassLevel(defaults[value]);

   const availableSubjects =
    value === "college"
      ? DEGREE_SUBJECTS[collegeDegree] || []
      : SUBJECT_OPTIONS[value] || [];

  setSubject(availableSubjects[0] || "");
}

  // ==================================================
  // START NEW CHAT
  // ==================================================

  function startNewChat() {
    setActiveConversationId(null);
    setMessages([]);
    setAnswerMeta(null);
    setQuestion("");
    setAttachments([]);
    setError("");
    setActivePage("chat");
  }

  // ==================================================
  // OPEN EXISTING CONVERSATION
  // ==================================================

  async function openConversation(conversationId: number) {
    if (loading || uploading) return;

    setError("");
    setActivePage("chat");
    setAnswerMeta(null);

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
      setAttachments([]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Couldn't open this conversation.",
      );
    }
  }

  // ==================================================
  // DELETE CONVERSATION
  // ==================================================

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
        current.filter((item) => item.id !== conversationId),
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

  // ==================================================
  // CREATE CONVERSATION IF NEEDED
  // ==================================================

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

  // ==================================================
  // UPLOAD FILE
  // ==================================================

  async function uploadFile(file: File) {
    if (loading || uploading) return;

    const extension = file.name
      .slice(file.name.lastIndexOf("."))
      .toLowerCase();

    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      setError(
        "Unsupported file type. Upload PDF, image, DOCX or TXT.",
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
      const conversationId = await ensureConversation();

      const formData = new FormData();

      formData.append("file", file);
      formData.append("student_id", STUDENT_ID);
      formData.append("conversation_id", String(conversationId));

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

  // ==================================================
  // REMOVE ATTACHMENT
  // ==================================================

  function removeAttachment(attachmentId: string) {
    setAttachments((current) =>
      current.filter((file) => file.id !== attachmentId),
    );
  }

  // ==================================================
  // SEND QUESTION
  // ==================================================

  async function sendQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const text = question.trim();

    if (!text || loading || uploading) return;

    setError("");
    setQuestion("");
    setActivePage("chat");
    setLoading(true);
    setAnswerMeta(null);

    let conversationId: number | null = activeConversationId;

    try {
      conversationId = await ensureConversation();

      const requestBody = {
        question: text,

        student_id: STUDENT_ID,

        conversation_id: conversationId,

        attachment_ids: attachments.map((file) => file.id),

        education_level: educationLevel,

        class_level:
          educationLevel === "college"
            ? null
            : Number(classLevel),

        degree:
          educationLevel === "college"
            ? collegeDegree
            : null,

        study_year:
          educationLevel === "college"
            ? Number(studyYear)
            : null,

        subject: codingMode ? "coding" : subject,

        mode: studyMode,

        coding_mode: codingMode,
      };

      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
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

      const answer = getAnswer(data);

      if (data && typeof data === "object") {
        const result = data as Partial<AnswerMeta>;

        setAnswerMeta({
          confidence: Number(result.confidence || 0),
          answered_from: String(
            result.answered_from || "fallback",
          ),
          sources: Array.isArray(result.sources)
            ? result.sources
            : [],
        });
      }

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
          : "Couldn't complete your request. Check the backend.",
      );

      // Keep the UI synchronized if the server saved
      // the question before returning an error.

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

  // ==================================================
  // PROVENANCE LABEL
  // ==================================================

  function getOriginLabel(origin: string) {
    switch (origin) {
      case "notes":
        return "From textbook";

      case "web":
        return "From web";

      case "model":
        return "From model memory";

      case "mixed":
        return "Textbook + web";

      default:
        return "General answer (not textbook-grounded)";
    }
  }

  // ==================================================
  // UI
  // ==================================================

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

        {/* RECENT CHATS */}

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

        {/* PRODUCTIVITY */}

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

                  {/* ANSWER SOURCES */}

                  {answerMeta && !loading && (

                    <div
                      className="answer-provenance"
                      aria-label="Answer sources"
                    >

                      <div className="answer-provenance-heading">

                        <strong>
                          {getOriginLabel(
                            answerMeta.answered_from,
                          )}
                        </strong>

                        <span className="confidence-badge">
                          {answerMeta.sources.length > 0
                            ? `Confidence: ${Math.round(
                                answerMeta.confidence * 100,
                              )}%`
                            : "No supporting textbook match"}
                        </span>

                      </div>

                      {answerMeta.sources.map((source, index) => (

                        <div
                          className="answer-source"
                          key={`${source.title}-${index}`}
                        >

                          {source.url ? (
                            <a
                              href={source.url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {source.title}
                            </a>
                          ) : (
                            <span>{source.title}</span>
                          )}

                          {source.section
                            ? ` · ${source.section}`
                            : ""}

                          {source.page
                            ? ` · p. ${source.page}`
                            : ""}

                        </div>

                      ))}

                    </div>

                  )}

                  {/* LOADING */}

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

              {/* ERROR */}

              {error && (

                <div
                  className="error-message"
                  role="alert"
                >
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

              {/* ======================================
                  EDUCATION AND STUDY CONTROLS
              ====================================== */}

              <div
                className="study-controls"
                aria-label="Study settings"
              >

                {/* EDUCATION LEVEL */}

                <label>
                  Education

                  <select
                    value={educationLevel}
                    onChange={(e) =>
                      changeEducationLevel(
                        e.target.value as EducationLevel,
                      )
                    }
                    disabled={loading || uploading}
                  >

                    <option value="primary">
                      Primary School
                    </option>

                    <option value="middle">
                      Middle School
                    </option>

                    <option value="secondary">
                      Secondary School
                    </option>

                    <option value="higher_secondary">
                      Higher Secondary
                    </option>

                    <option value="college">
                      College / Undergraduate
                    </option>

                  </select>

                </label>

                {/* COLLEGE DEGREE AND YEAR */}

                {educationLevel === "college" ? (

                  <>

                    <label>
                      Degree

                     <select
                        value={collegeDegree}
                        onChange={(e) => {
                          const degree = e.target.value;
                          setCollegeDegree(degree);
                          setSubject(DEGREE_SUBJECTS[degree]?.[0] || "");
                        }}
                      >
                        {DEGREE_OPTIONS.map((degree) => (
                          <option key={degree} value={degree}>
                            {degree}
                          </option>
                        ))}
                      </select>

                    </label>

                    <label>
                      Year

                      <select
                        value={studyYear}
                        onChange={(e) =>
                          setStudyYear(e.target.value)
                        }
                        disabled={loading || uploading}
                      >

                        {[1, 2, 3, 4, 5, 6].map((year) => (

                          <option
                            key={year}
                            value={year}
                          >
                            {year}
                            {year === 1
                              ? "st"
                              : year === 2
                                ? "nd"
                                : year === 3
                                  ? "rd"
                                  : "th"}{" "}
                            year
                          </option>

                        ))}

                      </select>

                    </label>

                  </>

                ) : (

                  /* SCHOOL CLASS */

                  <label>
                    Class

                    <select
                      value={classLevel}
                      onChange={(e) =>
                        setClassLevel(e.target.value)
                      }
                      disabled={loading || uploading}
                    >

                      {CLASS_OPTIONS[educationLevel].map(
                        (classNumber) => (

                          <option
                            key={classNumber}
                            value={classNumber}
                          >
                            Class {classNumber}
                          </option>

                        ),
                      )}

                    </select>

                  </label>

                )}

                {/* SUBJECT */}

               <label>
                  Subject

                  <select
                    value={subject}
                    onChange={(e) => {
                      setSubject(e.target.value);
                    }}
                    disabled={loading || uploading || codingMode}
                  >
                    {(educationLevel === "college"
                      ? DEGREE_SUBJECTS[collegeDegree] || []
                      : SUBJECT_OPTIONS[educationLevel] || []
                    ).map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
                {/* MODE */}

                <label>
                  Mode

                  <select
                    value={studyMode}
                    onChange={(e) =>
                      setStudyMode(e.target.value)
                    }
                    disabled={loading || uploading}
                  >

                    <option value="auto">
                      Auto
                    </option>

                    <option value="offline">
                      Textbook only
                    </option>

                    <option value="online">
                      Web enabled
                    </option>

                  </select>

                </label>

                {/* CODING */}

                <label className="coding-toggle">

                  <input
                    type="checkbox"
                    checked={codingMode}
                    onChange={(e) =>
                      setCodingMode(e.target.checked)
                    }
                    disabled={loading || uploading}
                  />

                  Coding

                </label>

              </div>

              {/* ======================================
                  MESSAGE INPUT
              ====================================== */}

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

              {/* FOOTER NOTE */}

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