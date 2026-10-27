export interface AskRequest {
  question: string;
  mode: "normal" | "simplify";
  language: "en" | "hi";
  conversationId: number;
  attachmentIds?: string[];
  studentId?: string;
}

export interface UploadedAttachment {
  id: string;
  filename: string;
  content_type: string;
  size: number;
  kind: "image" | "document";
  text_extracted: boolean;
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
