export type JobStatus = "draft" | "published" | "closed";
export type EmploymentType = "full_time" | "part_time" | "contract" | "internship";
export type QuestionType = "short_text" | "long_text" | "number" | "yes_no";

export interface JobQuestion {
  id: number;
  prompt: string;
  question_type: QuestionType;
  required: boolean;
  display_order: number;
}

export interface JobQuestionInput {
  prompt: string;
  question_type: QuestionType;
  required: boolean;
  display_order?: number;
}

export interface Job {
  id: number;
  title: string;
  description: string;
  department: string | null;
  department_id?: number | null;
  position: string | null;
  location: string | null;
  employment_type: EmploymentType;
  requirements: string | null;
  status: JobStatus;
  published_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
  created_by_user_id: number;
  questions: JobQuestion[];
}

export interface JobPayload {
  title: string;
  description: string;
  department_id?: number;
  position?: string;
  location?: string;
  employment_type: EmploymentType;
  requirements?: string;
  questions?: JobQuestionInput[];
}
