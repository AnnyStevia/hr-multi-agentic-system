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

/** Agent that handled a unified assistant ask (backend-selected). */
export type AssistantAgentId = "knowledge" | "leave" | "recruitment" | "onboarding";

export type AssistantAskStatus =
  | "completed"
  | "clarification_required"
  | "unavailable";

export interface AssistantAskPayload {
  message: string;
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
}

export type AIChatRole = "user" | "assistant";

export interface AIChatMessage {
  id: string;
  role: AIChatRole;
  content: string;
  /** Backend agent that produced this assistant turn (for confirm routing). */
  agentId?: AssistantAgentId;
  citations?: KnowledgeCitation[];
  has_context?: boolean;
  pendingConfirmation?: RecruitmentPendingConfirmation | null;
  confirmationResolved?: "confirmed" | "cancelled";
}
