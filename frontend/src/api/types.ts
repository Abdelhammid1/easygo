export type Role = "admin" | "supervisor" | "agent";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  permissions: string[];
}

export type ConversationState = "open" | "needs_human" | "pending" | "resolved";
export type AIMode = "active" | "suggest" | "off";

export interface Tag {
  id: number;
  name: string;
  color: string | null;
}

export interface ContactBrief {
  id: number;
  name: string | null;
  phone?: string | null;
  address?: string | null;
  is_blocked?: boolean;
  created_at?: string | null;
}

export interface Conversation {
  id: number;
  channel: string | null;
  contact: ContactBrief | null;
  state: ConversationState;
  ai_mode: AIMode;
  escalation_reason: string | null;
  assignee_id: number | null;
  assignee?: { id: number; name: string } | null;
  tags?: Tag[];
  unread_count: number;
  last_message_preview: string | null;
  last_message_at: string | null;
  reply_window_expires_at: string | null;
  reply_window_open: boolean;
  order_confirmed?: boolean;
}

export type SenderType = "customer" | "agent" | "ai" | "system";

export interface Attachment {
  id: number;
  type: "image" | "audio" | "file";
  url: string;
  mime_type: string | null;
  transcript: string | null;
  image_description: string | null;
}

export interface Message {
  id: number;
  direction: "inbound" | "outbound";
  sender_type: SenderType;
  sender_user_id: number | null;
  type: string;
  body: string | null;
  send_status: string | null;
  created_at: string | null;
  ai_confidence: number | null;
  ai_sources: string[];
  attachments: Attachment[];
}

export interface Order {
  id: number;
  status: string;
  stops: { shop?: string; items?: string[] }[];
  delivery_landmark: string | null;
  phones: string[];
  payment_method: string | null;
  invoice_required: boolean;
  at: string | null;
}

export interface PromptVersion {
  id: number;
  version: number;
  tone: string | null;
  notes: string | null;
  system_prompt: string;
  is_active: boolean;
  created_at: string | null;
}

export interface MessageEvent {
  id: number;
  conversation_id: number;
  direction: "inbound" | "outbound";
  sender_type: SenderType;
  type: string;
  body: string | null;
  created_at: string | null;
  ai_confidence?: number | null;
  ai_sources?: string[];
}

export type ConversationPatch = Partial<Conversation> & { id: number };

export interface Copilot {
  confidence: number | null;
  escalated: boolean;
  escalation_reason: string | null;
  suggested_reply: string | null;
  sources: string[];
  cost_usd: number | null;
  at: string | null;
}

export interface Note {
  id: number;
  body: string;
  author: string | null;
  at: string | null;
}

export interface AssignableUser {
  id: number;
  name: string;
  role: string;
}
