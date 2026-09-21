export interface OrgPosition {
  id: number;
  title: string;
  description: string | null;
  department_id: number | null;
  department: string | null;
  created_at: string;
  updated_at: string;
}

export interface PositionPayload {
  title: string;
  description?: string | null;
  department_id?: number | null;
}

export interface OrgPersonSummary {
  employee_id: number;
  full_name: string;
  position: string | null;
  department: string | null;
  has_profile_picture: boolean;
}

export interface EmployeeOrganization {
  employee: OrgPersonSummary;
  position: OrgPosition | null;
  department: {
    id: number;
    name: string;
    status: string;
    created_at: string;
    updated_at: string;
  } | null;
  manager: OrgPersonSummary | null;
}

export interface HierarchyNode {
  employee_id: number;
  name: string;
  position: string | null;
  department: string | null;
  children: HierarchyNode[];
}

export interface HierarchyResponse {
  employees: HierarchyNode[];
}

export interface DirectoryEntry {
  employee_id: number;
  full_name: string;
  position: string | null;
  department: string | null;
  manager: string | null;
  has_profile_picture: boolean;
  profile_picture_url: string | null;
}

export interface DirectoryResponse {
  items: DirectoryEntry[];
  total: number;
}
