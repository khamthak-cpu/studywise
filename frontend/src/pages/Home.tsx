import { useEffect, useRef, useState } from "react";
import {
  BookOpen, BookOpenText, ChevronDown, CircleHelp, GraduationCap, TrendingUp,
  History, Library, Menu, MessageCircle, PanelLeftClose, Plus, Search, Settings2,
  ShieldCheck, Sparkles, X
} from "lucide-react";
import ChatInput from "../components/ChatInput";
import AnswerCard from "../components/AnswerCard";
import ModeToggle from "../components/ModeToggle";
import StatusBar from "../components/StatusBar";
import { askQuestion, checkHealth, createConversation, isMockMode, uploadAttachment } from "../api/ask";
import type { AskResponse, ChatMessage } from "../types";
import Productivity from "./Productivity";

const starterPrompts = [
  { icon: "book", title: "Explain a difficult concept", prompt: "Explain TCP and UDP in simple terms." },
  { icon: "sparkles", title: "Make revision easier", prompt: "How does retrieval-augmented generation work?" },
  { icon: "history", title: "Prepare for an exam", prompt: "Give me a quick revision summary of the transport layer." }
];

function createId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [mode, setMode] = useState<"normal" | "simplify">("normal");
  const [language, setLanguage] = useState<"en" | "hi">("en");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"offline" | "online" | "checking" | "unavailable">(isMockMode ? "offline" : "checking");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [productivityOpen, setProductivityOpen] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const [history, setHistory] = useState<string[]>(["TCP vs UDP", "RAG explained", "Transport layer revision"]);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (isMockMode) return;
    checkHealth()
      .then((health) => setStatus(health.status === "ok" ? (health.online ? "online" : "offline") : "unavailable"))
      .catch(() => setStatus("unavailable"));
  }, []);

  useEffect(() => {
    const container = chatScrollRef.current;
    if (!container) return;

    container.scrollTo({
      top: container.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function sendQuestion(rawQuestion: string, selectedMode = mode, files: File[] = []): Promise<boolean> {
    const trimmed = rawQuestion.trim();
    if ((!trimmed && files.length === 0) || loading) return false;
    if (isMockMode && files.length > 0) {
      setError("File uploads require the live FastAPI backend. Set VITE_USE_MOCK=false and start StudyWise to use uploads.");
      return false;
    }
    setError("");
    const userMessage: ChatMessage = { id: createId(), role: "user", content: trimmed, createdAt: new Date() };
    setMessages((current) => [...current, userMessage]);
    setLoading(true);
    setHistory((current) => [trimmed.length > 28 ? `${trimmed.slice(0, 28)}…` : trimmed, ...current].slice(0, 8));
    try {
      let activeConversationId = conversationId;
      if (!isMockMode && activeConversationId === null) {
        const created = await createConversation(trimmed.slice(0, 60) || "Study session");
        activeConversationId = created.id;
        setConversationId(created.id);
      }

      let attachmentIds: string[] = [];
      if (files.length > 0 && activeConversationId !== null) {
        const uploaded = [];
        for (const file of files) uploaded.push(await uploadAttachment(file, activeConversationId));
        attachmentIds = uploaded.map((item) => item.id);
      }

      const response: AskResponse = await askQuestion({
        question: trimmed,
        mode: selectedMode,
        language,
        conversationId: activeConversationId ?? 1,
        attachmentIds,
      });
      setMessages((current) => [...current, { id: createId(), role: "assistant", content: response.answer, response, createdAt: new Date() }]);
      if (!isMockMode) setStatus(response.mode === "online" ? "online" : "offline");
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      if (!isMockMode) setStatus("unavailable");
      return false;
    } finally {
      setLoading(false);
    }
  }

  function newChat() {
    setMessages([]);
    setConversationId(null);
    setError("");
    setHistoryOpen(false);
    setProductivityOpen(false);
  }

  const filteredHistory = history.filter((item) => item.toLowerCase().includes(searchValue.toLowerCase()));

  return (
    <div className={`app-shell ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
      {sidebarOpen && <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark"><BookOpenText size={21} strokeWidth={2.2} /></div>
          <div className="brand-name">studywise<span>.</span><small>YOUR AI STUDY PARTNER</small></div>
          <button className="sidebar-close icon-button" onClick={() => setSidebarOpen(false)} aria-label="Collapse sidebar"><PanelLeftClose size={18} /></button>
        </div>

        <button className="new-chat-button" onClick={newChat}><Plus size={17} /><span>New conversation</span><kbd>⌘ K</kbd></button>

        <div className="sidebar-section-label">YOUR WORKSPACE</div>
        <button className={`nav-item ${!historyOpen ? "nav-active" : ""}`} onClick={() => setHistoryOpen(false)}><MessageCircle size={17} /><span>Study assistant</span></button>
        <button className={`nav-item ${historyOpen ? "nav-active" : ""}`} onClick={() => { setHistoryOpen(true); setProductivityOpen(false); }}><History size={17} /><span>Recent conversations</span><span className="nav-count">{history.length}</span></button>
        <button className={`nav-item ${productivityOpen ? "nav-active" : ""}`} onClick={() => { setProductivityOpen(true); setHistoryOpen(false); }}><TrendingUp size={17} /><span>Productivity</span></button>
        <button className="nav-item" onClick={() => window.alert("Your textbook library will be connected when upload and ingestion endpoints are ready.")}><Library size={17} /><span>My library</span><span className="soon-label">SOON</span></button>

        <div className="sidebar-section-label subject-label">SUGGESTED SUBJECTS</div>
        <button className="subject-item" onClick={() => sendQuestion("Help me revise Computer Networks.")}><span className="subject-dot dot-blue" />Computer Networks</button>
        <button className="subject-item" onClick={() => sendQuestion("Help me revise Data Structures and Algorithms.")}><span className="subject-dot dot-violet" />Data Structures</button>
        <button className="subject-item" onClick={() => sendQuestion("Help me revise Operating Systems.")}><span className="subject-dot dot-orange" />Operating Systems</button>

        {historyOpen && <div className="history-panel">
          <label className="history-search"><Search size={15} /><input value={searchValue} onChange={(event) => setSearchValue(event.target.value)} placeholder="Search conversations" /></label>
          {filteredHistory.length ? filteredHistory.map((item, index) => <button className="history-row" key={`${item}-${index}`} onClick={() => { setMessages([]); setHistoryOpen(false); }}><MessageCircle size={14} />{item}</button>) : <p className="muted-small">No matching conversations.</p>}
        </div>}

        <div className="sidebar-spacer" />
        <div className="privacy-card"><div className="privacy-icon"><ShieldCheck size={17} /></div><div><strong>Your study space</strong><p>Designed for local-first learning. Your real privacy depends on your backend configuration.</p></div></div>
        <button className="profile-button" onClick={() => window.alert("Profile settings can be added later.")}><div className="profile-avatar">S</div><div className="profile-copy"><strong>Student workspace</strong><span>Personal study space</span></div><Settings2 size={17} /></button>
      </aside>}

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            {!sidebarOpen && <button className="icon-button reopen-sidebar" onClick={() => setSidebarOpen(true)} aria-label="Open sidebar"><Menu size={19} /></button>}
            <div className="breadcrumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>{productivityOpen ? "Productivity" : historyOpen ? "Conversations" : "Study assistant"}</strong><ChevronDown size={14} /></div>
          </div>
          <div className="topbar-right">
            <StatusBar mode={status} mockMode={isMockMode} />
            <button className="help-button" onClick={() => window.alert("Ask questions about your course material. Answers should include supporting sources when the backend is connected.")}><CircleHelp size={17} /><span>Help</span></button>
          </div>
        </header>

       <div
          className="workspace-content"
          ref={messages.length > 0 && !productivityOpen && !historyOpen
            ? chatScrollRef
            : undefined}
        >
          {productivityOpen ? <Productivity onBack={() => setProductivityOpen(false)} /> : historyOpen ? (
            <section className="history-view">
              <div className="eyebrow">YOUR LEARNING, IN ONE PLACE</div>
              <h1>Recent conversations</h1>
              <p className="hero-subtitle">Pick up where you left off.</p>
              <label className="history-search large-search"><Search size={17} /><input value={searchValue} onChange={(event) => setSearchValue(event.target.value)} placeholder="Search conversations" /></label>
              {filteredHistory.map((item, index) => <button className="conversation-card" key={`${item}-${index}`} onClick={() => { setHistoryOpen(false); setMessages([]); }}><div className="conversation-icon"><MessageCircle size={18} /></div><div><strong>{item}</strong><span>Study assistant · Recent</span></div><ChevronDown className="conversation-chevron" size={17} /></button>)}
            </section>
          ) : messages.length === 0 ? (
            <section className="welcome-view">
              <div className="welcome-chip"><span className="chip-sparkle"><Sparkles size={13} /></span> A little smarter, every study session</div>
              <div className="hero-icon"><div className="hero-icon-inner"><GraduationCap size={34} strokeWidth={1.6} /></div><span className="hero-orbit orbit-one" /><span className="hero-orbit orbit-two" /></div>
              <h1>Learning starts with<br /><span>a good question.</span></h1>
              <p className="hero-subtitle">Your personal study assistant, grounded in your textbooks.<br className="desktop-break" /> Understand more. Memorize less. Learn with confidence.</p>
              <div className="starter-grid">
                {starterPrompts.map((item) => <button className="starter-card" key={item.title} onClick={() => sendQuestion(item.prompt)}><span className={`starter-icon ${item.icon}`} >{item.icon === "book" ? <BookOpen size={17} /> : item.icon === "sparkles" ? <Sparkles size={17} /> : <History size={17} />}</span><span className="starter-copy"><strong>{item.title}</strong><small>{item.prompt}</small></span><span className="starter-arrow">↗</span></button>)}
              </div>
            </section>
          ) : (
            <section className="chat-view" aria-live="polite">
              <div className="chat-heading"><div><div className="eyebrow">YOUR STUDY SESSION</div><h1>Let's figure it out.</h1></div><button className="subtle-button" onClick={newChat}><Plus size={15} /> New chat</button></div>
              {messages.map((message) => message.role === "user" ? (
                <div className="user-message-row" key={message.id}><div className="user-message">{message.content}</div><div className="user-avatar">S</div></div>
              ) : (
                <div className="assistant-message-row" key={message.id}><AnswerCard response={message.response!} /></div>
              ))}
              {loading && <div className="assistant-message-row"><div className="loading-card"><div className="assistant-avatar small-avatar"><BookOpenText size={16} /></div><div><strong>Putting the pieces together…</strong><span><i /><i /><i /></span></div></div></div>}
              {error && <div className="error-banner" role="alert"><CircleHelp size={17} /><div><strong>Couldn't get an answer</strong><p>{error}</p></div><button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}
              <div ref={bottomRef} />
            </section>
          )}
        </div>

        {!productivityOpen && <footer className="composer-area">
          <div className="composer-inner">
            <ModeToggle mode={mode} onModeChange={setMode} language={language} onLanguageChange={setLanguage} />
            <ChatInput onSend={(value, files) => sendQuestion(value, mode, files)} disabled={loading} onSimplify={() => { setMode("simplify"); if (messages.length > 0) { const lastUser = [...messages].reverse().find((message) => message.role === "user"); if (lastUser) sendQuestion(lastUser.content, "simplify"); } }} />
          </div>
        </footer>}
      </main>
    </div>
  );
}