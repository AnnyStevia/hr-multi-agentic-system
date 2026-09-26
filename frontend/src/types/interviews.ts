export type InterviewStatus = "proposed" | "scheduled" | "completed" | "cancelled";

export type InterviewOutcome = "rejected" | "another_interview" | "hired";

export type InterviewerRecommendation = "proceed" | "additional_interview" | "do_not_proceed";

export interface InterviewSlot {
  id: number;
  starts_at: string;
  ends_at: string;
  is_selected: boolean;
  is_available: boolean;
}

export interface InterviewerSummary {
  employee_id: number;
  full_name: string;
  position?: string | null;
  is_primary?: boolean;
}

export interface InterviewEvaluation {
  tech_knowledge?: number | null;
  communication?: number | null;
  problem_solving?: number | null;
  relevant_experience?: number | null;
  strengths?: string | null;
  weaknesses?: string | null;
  additional_comments?: string | null;
  recommendation?: InterviewerRecommendation | null;
  recommendation_label?: string | null;
}

export interface InterviewSummary {
  id: number;
  application_id: number;
  status: InterviewStatus;
  status_label: string;
  message: string | null;
  created_at: string;
  job_title: string;
  candidate_name: string;
  interviewer_name: string | null;
  interviewers?: InterviewerSummary[];
  selected_slot: InterviewSlot | null;
  slot_count?: number;
  feedback?: string | null;
  evaluation?: InterviewEvaluation | null;
  completed_at?: string | null;
  outcome?: InterviewOutcome | null;
  outcome_label?: string | null;
  hired_employee_id?: number | null;
  meeting_url?: string | null;
  my_role?: "primary" | "panel" | null;
  can_propose_slots?: boolean;
  can_complete?: boolean;
}

export interface InterviewDetail {
  id: number;
  application_id: number;
  status: InterviewStatus;
  status_label?: string | null;
  message: string | null;
  created_at: string;
  updated_at: string;
  job_title: string;
  candidate_name: string;
  interviewer_name: string | null;
  interviewers?: InterviewerSummary[];
  slots: InterviewSlot[];
  selected_slot: InterviewSlot | null;
  slot_count?: number;
  feedback?: string | null;
  evaluation?: InterviewEvaluation | null;
  completed_at?: string | null;
  outcome?: InterviewOutcome | null;
  outcome_label?: string | null;
  hired_employee_id?: number | null;
  meeting_url?: string | null;
  my_role?: "primary" | "panel" | null;
  can_propose_slots?: boolean;
  can_complete?: boolean;
}

export interface InterviewSlotInput {
  starts_at: string;
  ends_at: string;
}

export interface InterviewCreatePayload {
  primary_employee_id: number;
  additional_employee_ids?: number[];
  message?: string | null;
}

export interface InterviewProposeSlotsPayload {
  slots: InterviewSlotInput[];
}

export interface InterviewConfirmPayload {
  slot_id: number;
}

export interface InterviewCompletePayload {
  tech_knowledge: number;
  communication: number;
  problem_solving: number;
  relevant_experience: number;
  strengths: string;
  weaknesses: string;
  additional_comments?: string | null;
  recommendation: InterviewerRecommendation;
}

export interface InterviewOutcomePayload {
  outcome: InterviewOutcome;
}
