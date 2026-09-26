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

export interface RecruitmentUsage {
  input_tokens: number | null;
  output_tokens: number | null;
  thinking_tokens: number | null;
  total_tokens: number | null;
}

export interface RecruitmentAskResponse {
  answer: string;
  model: string;
  tool_names_called: string[];
  usage: RecruitmentUsage | null;
}

export type AIChatRole = "user" | "assistant";

export interface AIChatMessage {
  id: string;
  role: AIChatRole;
  content: string;
  citations?: KnowledgeCitation[];
  has_context?: boolean;
}
