import type { CurrentLeaveSummary, CurrentWorkStatus } from "@/types/leave";
import type { EmploymentType } from "@/types/jobs";

export type EmploymentStatus = "active" | "inactive" | "on_leave";

export const EMPLOYMENT_TYPE_LABELS: Record<EmploymentType, string> = {
  full_time: "Full time",
  part_time: "Part time",
  contract: "Contract",
  internship: "Internship",
};

export interface Employee {
  id: number;
  employee_number: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  department_id: number;
  department: string;
  position: string;
  position_id: number | null;
  manager_id: number | null;
  hire_date: string;
  employment_type: EmploymentType;
  employment_end_date: string | null;
  employment_status: EmploymentStatus;
  current_work_status?: CurrentWorkStatus;
  current_leave?: CurrentLeaveSummary | null;
  user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface EmployeeListResponse {
  items: Employee[];
  total: number;
}

export interface EmployeePayload {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  department_id: number;
  position?: string;
  position_id?: number | null;
  manager_id?: number | null;
  hire_date: string;
  employment_type?: EmploymentType;
  employment_end_date?: string | null;
}

export interface EmployeeUpdatePayload {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
  department_id?: number;
  position?: string;
  position_id?: number | null;
  manager_id?: number | null;
  hire_date?: string;
  employment_type?: EmploymentType;
  employment_end_date?: string | null;
}
