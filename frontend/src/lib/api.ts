import type {
  Account,
  ApiError,
  ApiErrorDetail,
  CandidateRegisterPayload,
  CreateHRPayload,
  LoginResponse,
  User,
} from "@/types/auth";
import type { Job, JobPayload } from "@/types/jobs";
import type { ApplicationDetail, ApplicationListItem, ApplicationStatus, PresignedDocument } from "@/types/applications";
import type { Department } from "@/types/departments";
import type { Employee, EmployeeListResponse, EmployeePayload, EmployeeUpdatePayload, EmploymentStatus } from "@/types/employees";
import type { MarkAllReadResponse, Notification, UnreadCountResponse } from "@/types/notifications";
import type {
  InterviewCompletePayload,
  InterviewConfirmPayload,
  InterviewCreatePayload,
  InterviewDetail,
  InterviewOutcomePayload,
  InterviewSummary,
} from "@/types/interviews";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function formatApiDetail(detail: ApiErrorDetail | undefined): string {
  if (!detail) {
    return "An unexpected error occurred";
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (typeof item === "string") return item;
      if (item?.msg) return item.msg;
      return "Invalid request";
    });
    return messages.join(". ");
  }
  if (detail.msg) {
    return detail.msg;
  }
  return "An unexpected error occurred";
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  setToken(token: string): void {
    localStorage.setItem("access_token", token);
  }

  clearToken(): void {
    localStorage.removeItem("access_token");
  }

  hasToken(): boolean {
    return !!this.getToken();
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
    const headers: Record<string, string> = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers,
      });
    } catch {
      throw new Error("Cannot reach the server. Is the backend running?");
    }

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: "An unexpected error occurred",
      }));
      throw new Error(formatApiDetail(error.detail));
    }

    return response.json();
  }

  async login(email: string, password: string): Promise<LoginResponse> {
    const data = await this.request<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async register(payload: CandidateRegisterPayload): Promise<LoginResponse> {
    const data = await this.request<LoginResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    this.setToken(data.access_token);
    return data;
  }

  async getMe(): Promise<User> {
    return this.request<User>("/api/v1/auth/me");
  }

  async createHR(payload: CreateHRPayload): Promise<User> {
    return this.request<User>("/api/v1/users/hr", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listAccounts(): Promise<Account[]> {
    return this.request<Account[]>("/api/v1/users");
  }

  async downloadAccountsExcel(): Promise<void> {
    const token = this.getToken();
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}/api/v1/users/export`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch {
      throw new Error("Cannot reach the server. Is the backend running?");
    }

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: "Failed to download Excel file",
      }));
      throw new Error(formatApiDetail(error.detail));
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "hr-platform-accounts.xlsx";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async listJobs(): Promise<Job[]> {
    return this.request<Job[]>("/api/v1/jobs");
  }

  async listDepartments(status = "all"): Promise<Department[]> {
    return this.request<Department[]>(`/api/v1/departments?status=${encodeURIComponent(status)}`);
  }

  async createDepartment(name: string): Promise<Department> {
    return this.request<Department>("/api/v1/departments", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  }

  async deactivateDepartment(id: number): Promise<Department> {
    return this.request<Department>(`/api/v1/departments/${id}/deactivate`, { method: "PATCH" });
  }

  async listEmployees(params?: {
    status?: EmploymentStatus | "all";
    department_id?: number;
    q?: string;
  }): Promise<EmployeeListResponse> {
    const query = new URLSearchParams();
    query.set("status", params?.status || "active");
    if (params?.department_id) query.set("department_id", String(params.department_id));
    if (params?.q) query.set("q", params.q);
    return this.request<EmployeeListResponse>(`/api/v1/employees?${query.toString()}`);
  }

  async getEmployee(id: number): Promise<Employee> {
    return this.request<Employee>(`/api/v1/employees/${id}`);
  }

  async createEmployee(payload: EmployeePayload): Promise<Employee> {
    return this.request<Employee>("/api/v1/employees", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateEmployee(id: number, payload: EmployeeUpdatePayload): Promise<Employee> {
    return this.request<Employee>(`/api/v1/employees/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deactivateEmployee(id: number): Promise<Employee> {
    return this.request<Employee>(`/api/v1/employees/${id}/deactivate`, { method: "PATCH" });
  }

  async getJob(id: number): Promise<Job> {
    return this.request<Job>(`/api/v1/jobs/${id}`);
  }

  async createJob(payload: JobPayload): Promise<Job> {
    return this.request<Job>("/api/v1/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async publishJob(id: number): Promise<Job> {
    return this.request<Job>(`/api/v1/jobs/${id}/publish`, { method: "POST" });
  }

  async closeJob(id: number): Promise<Job> {
    return this.request<Job>(`/api/v1/jobs/${id}/close`, { method: "POST" });
  }

  async listCareerJobs(): Promise<Job[]> {
    return this.request<Job[]>("/api/v1/careers/jobs");
  }

  async getCareerJob(id: number): Promise<Job> {
    return this.request<Job>(`/api/v1/careers/jobs/${id}`);
  }

  async getMyJobApplication(jobId: number): Promise<ApplicationDetail> {
    return this.request<ApplicationDetail>(`/api/v1/careers/jobs/${jobId}/application`);
  }

  async applyToJob(jobId: number, formData: FormData): Promise<ApplicationDetail> {
    return this.request<ApplicationDetail>(`/api/v1/careers/jobs/${jobId}/applications`, {
      method: "POST",
      body: formData,
    });
  }

  async getMyApplication(id: number): Promise<ApplicationDetail> {
    return this.request<ApplicationDetail>(`/api/v1/careers/applications/${id}`);
  }

  async listJobApplications(jobId: number): Promise<ApplicationListItem[]> {
    return this.request<ApplicationListItem[]>(`/api/v1/jobs/${jobId}/applications`);
  }

  async getApplication(id: number): Promise<ApplicationDetail> {
    return this.request<ApplicationDetail>(`/api/v1/applications/${id}`);
  }

  async updateApplicationStatus(id: number, status: ApplicationStatus): Promise<ApplicationDetail> {
    return this.request<ApplicationDetail>(`/api/v1/applications/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  }

  async getApplicationDocumentUrl(
    applicationId: number,
    documentId: number,
    download = false,
  ): Promise<PresignedDocument> {
    const query = download ? "?download=true" : "";
    return this.request<PresignedDocument>(
      `/api/v1/applications/${applicationId}/documents/${documentId}/url${query}`,
    );
  }

  async listNotifications(): Promise<Notification[]> {
    return this.request<Notification[]>("/api/v1/notifications");
  }

  async getUnreadNotificationCount(): Promise<UnreadCountResponse> {
    return this.request<UnreadCountResponse>("/api/v1/notifications/unread-count");
  }

  async markNotificationRead(id: number): Promise<Notification> {
    return this.request<Notification>(`/api/v1/notifications/${id}/read`, { method: "PATCH" });
  }

  async markAllNotificationsRead(): Promise<MarkAllReadResponse> {
    return this.request<MarkAllReadResponse>("/api/v1/notifications/read-all", { method: "PATCH" });
  }

  async listApplicationInterviews(applicationId: number): Promise<InterviewSummary[]> {
    return this.request<InterviewSummary[]>(`/api/v1/interviews/applications/${applicationId}`);
  }

  async createInterviewInvitation(
    applicationId: number,
    payload: InterviewCreatePayload,
  ): Promise<InterviewDetail> {
    return this.request<InterviewDetail>(`/api/v1/interviews/applications/${applicationId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getInterview(id: number): Promise<InterviewDetail> {
    return this.request<InterviewDetail>(`/api/v1/interviews/${id}`);
  }

  async getCareerInterview(id: number): Promise<InterviewDetail> {
    return this.request<InterviewDetail>(`/api/v1/careers/interviews/${id}`);
  }

  async confirmInterviewSlot(id: number, payload: InterviewConfirmPayload): Promise<InterviewDetail> {
    return this.request<InterviewDetail>(`/api/v1/careers/interviews/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async completeInterview(id: number, payload: InterviewCompletePayload): Promise<InterviewDetail> {
    return this.request<InterviewDetail>(`/api/v1/interviews/${id}/complete`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async recordInterviewOutcome(id: number, payload: InterviewOutcomePayload): Promise<InterviewDetail> {
    return this.request<InterviewDetail>(`/api/v1/interviews/${id}/outcome`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  logout(): void {
    this.clearToken();
  }
}

export const api = new ApiClient(API_URL);
