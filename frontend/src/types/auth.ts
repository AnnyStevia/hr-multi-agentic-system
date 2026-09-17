export interface Role {
  id: number;
  name: string;
  description: string | null;
}

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  is_active: boolean;
  roles: Role[];
  permissions: string[];
  phone?: string | null;
  onboarding_status?: "in_progress" | "completed" | null;
}

export interface Account {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  is_active: boolean;
  roles: Role[];
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface CreateHRPayload {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  phone: string;
  department_id: number;
  position: string;
  hire_date: string;
}

export interface CandidateRegisterPayload {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
}

export type ApiErrorDetail =
  | string
  | { msg?: string; type?: string; loc?: unknown }
  | Array<{ msg?: string; type?: string; loc?: unknown } | string>;

export interface ApiError {
  detail?: ApiErrorDetail;
}
