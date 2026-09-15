export type DepartmentStatus = "active" | "inactive";

export interface Department {
  id: number;
  name: string;
  status: DepartmentStatus;
  created_at: string;
  updated_at: string;
}
