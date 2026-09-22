export type LeaveRequestStatus = "pending" | "approved" | "rejected" | "cancelled";

export type LeaveApprovalStatus = "pending" | "approved" | "rejected";

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
  manager_approval: LeaveApprovalStatus;
  manager_approved_by: number | null;
  manager_approved_at: string | null;
  hr_approval: LeaveApprovalStatus;
  hr_approved_by: number | null;
  hr_approved_at: string | null;
  admin_override: LeaveApprovalStatus;
  admin_approved_by: number | null;
  admin_approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeaveRequestCreatePayload {
  leave_type_id: number;
  start_date: string;
  end_date: string;
  reason?: string | null;
}

export interface LeaveCalendarPeriod {
  request_id: number;
  leave_type_name: string;
  status: LeaveRequestStatus;
  start_date: string;
  end_date: string;
}

export interface LeaveCalendar {
  year: number;
  month: number;
  periods: LeaveCalendarPeriod[];
}

export type CurrentWorkStatus = "ACTIVE" | "ON_LEAVE";

export interface CurrentLeaveSummary {
  leave_type: string;
  start_date: string;
  end_date: string;
}

export const LEAVE_REQUEST_STATUS_LABELS: Record<LeaveRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export const LEAVE_APPROVAL_STATUS_LABELS: Record<LeaveApprovalStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

/** Inclusive calendar days — keep in sync with backend leave.days.calculate_requested_days */
export function estimateLeaveDays(startDate: string, endDate: string): number | null {
  if (!startDate || !endDate) return null;
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return null;
  return Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1;
}

export function eachDateInRange(startDate: string, endDate: string): string[] {
  const days = estimateLeaveDays(startDate, endDate);
  if (days == null) return [];
  const result: string[] = [];
  const cursor = new Date(`${startDate}T00:00:00`);
  for (let i = 0; i < days; i++) {
    const y = cursor.getFullYear();
    const m = String(cursor.getMonth() + 1).padStart(2, "0");
    const d = String(cursor.getDate()).padStart(2, "0");
    result.push(`${y}-${m}-${d}`);
    cursor.setDate(cursor.getDate() + 1);
  }
  return result;
}
