export type LeaveRequestStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface LeaveType {
  id: number;
  name: string;
  description: string | null;
  is_paid: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LeaveTypePayload {
  name: string;
  description?: string | null;
  is_paid?: boolean;
  is_active?: boolean;
}

export interface LeaveTypeUpdatePayload {
  name?: string;
  description?: string | null;
  is_paid?: boolean;
  is_active?: boolean;
}

export interface LeavePolicy {
  id: number;
  leave_type_id: number;
  leave_type_name: string;
  year: number;
  days_allowed: number;
  created_at: string;
  updated_at: string;
}

export interface LeavePolicyPayload {
  leave_type_id: number;
  year: number;
  days_allowed: number;
}

export interface LeavePolicyUpdatePayload {
  year?: number;
  days_allowed?: number;
}

export interface LeaveBalance {
  employee_id: number;
  leave_type_id: number;
  leave_type_name: string;
  year: number;
  days_allowed: number;
  days_used: number;
  days_pending: number;
  days_available: number;
}

export interface LeaveRequest {
  id: number;
  employee_id: number;
  employee_name?: string | null;
  leave_type_id: number;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  requested_days: number;
  reason: string | null;
  rejection_reason: string | null;
  status: LeaveRequestStatus;
  approved_at: string | null;
  rejected_at: string | null;
  reviewed_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface LeaveRequestCreatePayload {
  leave_type_id: number;
  start_date: string;
  end_date: string;
  reason?: string | null;
}

export const LEAVE_REQUEST_STATUS_LABELS: Record<LeaveRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

/** Inclusive calendar days — keep in sync with backend leave.days.calculate_requested_days */
export function estimateLeaveDays(startDate: string, endDate: string): number | null {
  if (!startDate || !endDate) return null;
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return null;
  return Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1;
}
