export interface DashboardKpis {
  total_employees: number;
  active_employees: number;
  on_leave: number;
  pending_leave: number;
  onboarding: number;
  open_jobs: number;
  pending_applications: number;
}

export interface WorkforceBreakdownItem {
  label: string;
  count: number;
}

export interface DashboardWorkforce {
  by_department: WorkforceBreakdownItem[];
  by_position: WorkforceBreakdownItem[];
  by_employment_status: WorkforceBreakdownItem[];
}

export interface DashboardHireItem {
  employee_id: number;
  employee_name: string;
  department: string | null;
  position: string | null;
  hire_date: string;
}

export interface DashboardLeaveItem {
  request_id: number;
  employee_id: number;
  employee_name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  status: string;
}

export interface DashboardOnboardingItem {
  onboarding_id: number;
  employee_id: number;
  employee_name: string;
  status: string;
  completed_tasks: number;
  total_tasks: number;
  progress_percent: number;
}

export interface DashboardInterviewItem {
  interview_id: number;
  application_id: number;
  candidate_name: string;
  job_id: number;
  job_title: string;
  starts_at: string;
  status: string;
}

export interface DashboardApplicationItem {
  application_id: number;
  job_id: number;
  candidate_name: string;
  job_title: string;
  status: string;
  submitted_at: string | null;
}

export interface DashboardDeadlineItem {
  onboarding_id: number;
  employee_name: string;
  task_title: string;
  due_date: string;
}

export interface DashboardActivity {
  recent_hires: DashboardHireItem[];
  on_leave: DashboardLeaveItem[];
  returning_soon: DashboardLeaveItem[];
  upcoming_interviews: DashboardInterviewItem[];
  onboarding: DashboardOnboardingItem[];
  upcoming_deadlines: DashboardDeadlineItem[];
}

export interface DashboardLeaveOverview {
  approved: number;
  pending: number;
  rejected: number;
}

export interface DashboardAttention {
  pending_leave: DashboardLeaveItem[];
  pending_applications: DashboardApplicationItem[];
  incomplete_onboarding: DashboardOnboardingItem[];
  upcoming_interviews: DashboardInterviewItem[];
}

export interface HrDashboard {
  kpis: DashboardKpis;
  workforce: DashboardWorkforce;
  leave_overview: DashboardLeaveOverview;
  activity: DashboardActivity;
  attention: DashboardAttention;
}
