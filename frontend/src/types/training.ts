export type OnboardingTrainingStatus = "pending" | "completed";

export interface Training {
  id: number;
  title: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface TrainingPayload {
  title: string;
  description?: string | null;
}

export interface OnboardingTrainingAssignment {
  id: number;
  onboarding_id: number;
  training_id: number;
  status: OnboardingTrainingStatus;
  assigned_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  title: string;
  description: string | null;
}
