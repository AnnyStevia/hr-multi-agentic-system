export interface KnowledgeCitation {
  citation_id: number;
  document_name: string | null;
  page_start: number;
  page_end: number;
  company_document_id: number;
}

export interface RecruitmentConfirmPayload {
  confirmation_token: string;
}

export interface RecruitmentUsage {
  input_tokens: number | null;
  output_tokens: number | null;
  thinking_tokens: number | null;
  total_tokens: number | null;
}

export interface RecruitmentPendingConfirmation {
  token: string;
  tool_name: string;
  summary: string;
  expires_at: number;
}

export interface RecruitmentAskResponse {
  answer: string;
  model: string;
  tool_names_called: string[];
  usage: RecruitmentUsage | null;
  pending_confirmation?: RecruitmentPendingConfirmation | null;
}

export interface LeaveUsage {
  input_tokens: number | null;
  output_tokens: number | null;
  thinking_tokens: number | null;
  total_tokens: number | null;
}

export interface LeaveAskResponse {
  answer: string;
  model: string;
  tool_names_called: string[];
  usage: LeaveUsage | null;
  pending_confirmation?: RecruitmentPendingConfirmation | null;
}

export interface OnboardingAskResponse {
  answer: string;
  model: string;
  tool_names_called: string[];
  usage: LeaveUsage | null;
  pending_confirmation?: RecruitmentPendingConfirmation | null;
}

export interface TrainingAskResponse {
  answer: string;
  model: string;
  tool_names_called: string[];
  usage: LeaveUsage | null;
  pending_confirmation?: RecruitmentPendingConfirmation | null;
}

export interface OffboardingAskResponse {
  answer: string;
  agent_id: "offboarding";
  model: string;
  tool_names_called: string[];
  usage: LeaveUsage | null;
  pending_confirmation?: RecruitmentPendingConfirmation | null;
}

/** Document Understanding source types (standalone Documents Agent). */
export type DocumentSourceType = "company" | "employee" | "private";

export interface DocumentCitation {
  page_number: number;
  excerpt: string | null;
}

export interface DocumentSummary {
  title: string;
  summary: string;
  key_points: string[];
  important_dates: string[];
  action_items: string[];
  document_id: number | null;
  document_type: string | null;
  truncated: boolean;
}

export interface DocumentAnswer {
  answer: string;
  citations: DocumentCitation[];
  document_id: number | null;
  document_type: string | null;
  truncated: boolean;
}

export interface DocumentsAskPayload {
  message: string;
}

export interface DocumentsAskResponse {
  answer: string;
  agent_id: "documents";
  model: string;
  tool_names_called: string[];
  usage: LeaveUsage | null;
  pending_confirmation: null;
  document_summary: DocumentSummary | null;
  document_answer: DocumentAnswer | null;
}

/** Agent that handled a unified assistant ask (backend-selected). */
export type AssistantAgentId =
  | "knowledge"
  | "leave"
  | "recruitment"
  | "onboarding"
  | "training"
  | "documents"
  | "offboarding";

export type AssistantAskStatus =
  | "completed"
  | "clarification_required"
  | "unavailable";

export interface AssistantAskPayload {
  message: string;
  conversation_id?: number | null;
}

export interface AssistantUsage {
  input_tokens: number | null;
  output_tokens: number | null;
  thinking_tokens: number | null;
  total_tokens: number | null;
}

/** Normalized Phase 8.2 unified ask envelope. */
export interface AssistantAskResponse {
  agent_id: AssistantAgentId | null;
  answer: string;
  citations: KnowledgeCitation[];
  pending_confirmation: RecruitmentPendingConfirmation | null;
  status: AssistantAskStatus;
  model?: string | null;
  tool_names_called?: string[];
  usage?: AssistantUsage | null;
  conversation_id?: number | null;
  message_id?: number | null;
}

export type AIChatRole = "user" | "assistant";

export interface ConversationSummary {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface HistoryPendingState {
  tool_name: string | null;
  summary: string | null;
  expires_at: number | null;
  resolved: boolean | null;
}

export interface ConversationMessage {
  id: number;
  role: AIChatRole;
  content: string;
  sequence: number;
  agent_id: AssistantAgentId | null;
  status: string | null;
  tool_names_called: string[];
  citations: KnowledgeCitation[];
  pending: HistoryPendingState | null;
  model: string | null;
  created_at: string;
}

export interface ConversationDetail {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

export interface AIChatMessage {
  id: string;
  role: AIChatRole;
  content: string;
  /** Backend agent that produced this assistant turn (for confirm routing). */
  agentId?: AssistantAgentId;
  citations?: KnowledgeCitation[];
  has_context?: boolean;
  pendingConfirmation?: RecruitmentPendingConfirmation | null;
  /** Hydrated historical pending — show summary only, never Confirm. */
  pendingHistorical?: HistoryPendingState | null;
  confirmationResolved?: "confirmed" | "cancelled";
  /** Server-side message id when persisted. */
  serverMessageId?: number;
}
