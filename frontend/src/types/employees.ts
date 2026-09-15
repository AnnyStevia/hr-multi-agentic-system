export type EmploymentStatus = "active" | "inactive" | "on_leave";

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
  hire_date: string;
  employment_status: EmploymentStatus;
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
  position: string;
  hire_date: string;
}

export interface EmployeeUpdatePayload {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
  department_id?: number;
  position?: string;
  hire_date?: string;
}
