export interface KnowledgeCitation {
  citation_id: number;
  document_name: string | null;
  page_start: number;
  page_end: number;
  company_document_id: number;
}

export interface KnowledgeUsage {
  input_tokens: number | null;
  output_tokens: number | null;
  thinking_tokens: number | null;
  total_tokens: number | null;
}

export interface KnowledgeAskResponse {
  query: string;
  answer: string;
  citations: KnowledgeCitation[];
  has_context: boolean;
  retrieval_count: number;
  selected_context_count: number;
  model: string;
  usage: KnowledgeUsage | null;
}

export interface KnowledgeAskPayload {
  question: string;
  top_k?: number | null;
}

export interface RecruitmentAskPayload {
  question: string;
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

export interface LeaveAskPayload {
  question: string;
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

export type AIAssistantAgentMode = "knowledge" | "recruitment" | "leave";

export type AIChatRole = "user" | "assistant";

export interface AIChatMessage {
  id: string;
  role: AIChatRole;
  content: string;
  citations?: KnowledgeCitation[];
  has_context?: boolean;
  pendingConfirmation?: RecruitmentPendingConfirmation | null;
  confirmationResolved?: "confirmed" | "cancelled";
}
