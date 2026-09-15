export type InterviewStatus = "proposed" | "scheduled" | "completed" | "cancelled";

export type InterviewOutcome = "rejected" | "another_interview" | "hired";

export interface InterviewSlot {
  id: number;
  starts_at: string;
  ends_at: string;
  is_selected: boolean;
  is_available: boolean;
}

export interface InterviewSummary {
  id: number;
  application_id: number;
  status: InterviewStatus;
  status_label: string;
  message: string;
  created_at: string;
  job_title: string;
  candidate_name: string;
  interviewer_name: string | null;
  selected_slot: InterviewSlot | null;
  feedback?: string | null;
  completed_at?: string | null;
  outcome?: InterviewOutcome | null;
  outcome_label?: string | null;
  hired_employee_id?: number | null;
}

export interface InterviewDetail {
  id: number;
  application_id: number;
  status: InterviewStatus;
  message: string;
  created_at: string;
  updated_at: string;
  job_title: string;
  candidate_name: string;
  interviewer_name: string | null;
  slots: InterviewSlot[];
  selected_slot: InterviewSlot | null;
  feedback?: string | null;
  completed_at?: string | null;
  outcome?: InterviewOutcome | null;
  outcome_label?: string | null;
  hired_employee_id?: number | null;
}

export interface InterviewSlotInput {
  starts_at: string;
  ends_at: string;
}

export interface InterviewCreatePayload {
  message: string;
  slots: InterviewSlotInput[];
}

export interface InterviewConfirmPayload {
  slot_id: number;
}

export interface InterviewCompletePayload {
  feedback: string;
}

export interface InterviewOutcomePayload {
  outcome: InterviewOutcome;
}
