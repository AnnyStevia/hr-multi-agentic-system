import type { JobStatus, QuestionType } from "@/types/jobs";

export type ApplicationStatus = "submitted" | "screening" | "shortlisted" | "rejected" | "hired";

export type DocumentKind = "cv" | "cover_letter";

export interface CandidateSummary {
  id: number;
  user_id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone?: string | null;
}

export interface JobSummary {
  id: number;
  title: string;
  department: string | null;
  status: JobStatus;
}

export interface EducationEntry {
  institution: string;
  degree?: string;
  field_of_study?: string;
  start_year?: number | null;
  end_year?: number | null;
}

export interface ExperienceEntry {
  company: string;
  title: string;
  start_year?: number | null;
  end_year?: number | null;
  description?: string;
}

export interface ApplicationAnswer {
  question_id: number;
  prompt: string;
  question_type: QuestionType;
  required: boolean;
  value: string;
}

export interface ApplicationDocument {
  id: number;
  kind: DocumentKind;
  original_filename: string;
  content_type: string;
  size_bytes: number;
}

export interface ApplicationListItem {
  id: number;
  status: ApplicationStatus;
  submitted_at: string;
  candidate: CandidateSummary;
  has_cv: boolean;
  has_cover_letter: boolean;
}

export interface ApplicationDetail {
  id: number;
  status: ApplicationStatus;
  submitted_at: string;
  created_at: string;
  updated_at: string;
  candidate: CandidateSummary;
  job: JobSummary;
  education: Array<EducationEntry & { id: number }>;
  experience: Array<ExperienceEntry & { id: number }>;
  answers: ApplicationAnswer[];
  documents: ApplicationDocument[];
}

export interface CandidateApplicationSummary {
  id: number;
  job_id: number;
  status: ApplicationStatus;
  submitted_at: string;
  job_title: string;
}

export interface PresignedDocument {
  url: string;
  filename: string;
  content_type: string;
  expires_in: number;
  download: boolean;
}
