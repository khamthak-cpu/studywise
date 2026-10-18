export interface AskRequest {
  question: string;
  mode: "normal" | "simplify";
  language: "en" | "hi";
}

export interface Source {
  title: string;
  chapter?: string;
  section?: string;
  page?: number;
  excerpt?: string;
  snippet?: string;
  url?: string;
}

export interface AskResponse {
  answer: string;
  confidence: "grounded" | "uncertain" | string;
  confidenceScore?: number;
  sources: Source[];
  mode: "offline" | "online" | string;
  answeredFrom?: "notes" | "web" | "fallback";
  language?: "en" | "hi";
  latencyMs?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: AskResponse;
  createdAt: Date;
}
