import type {
  KnowledgeAskPayload,
  KnowledgeAskResponse,
} from "@/types/ai";
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
import type { ApplicationDetail, ApplicationListItem, ApplicationStatus, CandidateApplicationSummary, CvExtractionResponse, PresignedDocument } from "@/types/applications";
import type { Department } from "@/types/departments";
import type { HrDashboard } from "@/types/dashboard";
import type { Employee, EmployeeListResponse, EmployeePayload, EmployeeUpdatePayload, EmploymentStatus } from "@/types/employees";
import type { MarkAllReadResponse, Notification, UnreadCountResponse } from "@/types/notifications";
import type {
  InterviewCompletePayload,
  InterviewConfirmPayload,
  InterviewCreatePayload,
  InterviewDetail,
  InterviewOutcomePayload,
  InterviewProposeSlotsPayload,
  InterviewSummary,
} from "@/types/interviews";
import type {
  Onboarding,
  OnboardingListItem,
  OnboardingProgress,
  OnboardingTask,
  OnboardingTaskCreatePayload,
  OnboardingTaskTemplate,
  OnboardingTaskTemplatePayload,
  OnboardingTaskUpdatePayload,
} from "@/types/onboarding";
import type { DocumentType, EmployeeDocument, PresignedDocumentUrl } from "@/types/documents";
import type {
  CompanyDocument,
  CompanyDocumentCategory,
  CompanyDocumentStatus,
  CompanyDocumentUpdatePayload,
  PrivateDocument,
  PrivateDocumentUpdatePayload,
} from "@/types/libraryDocuments";
import type {
  LeaveBalance,
  LeaveCalendar,
  LeavePolicy,
  LeavePolicyPayload,
  LeavePolicyUpdatePayload,
  LeaveRequest,
  LeaveRequestCreatePayload,
  LeaveRequestStatus,
  LeaveCancellationStatus,
  LeaveType,
  LeaveTypePayload,
  LeaveTypeUpdatePayload,
} from "@/types/leave";
import type {
  EducationPayload,
  EmployeeEducation,
  EmployeeExperience,
  EmployeeProfile,
  ExperiencePayload,
  PresignedProfilePictureUrl,
  ProfileUpdatePayload,
} from "@/types/profile";
import type {
  OnboardingTrainingAssignment,
  Training,
  TrainingPayload,
} from "@/types/training";
import type {
  DirectoryResponse,
  EmployeeOrganization,
  HierarchyResponse,
  OrgPosition,
  PositionPayload,
} from "@/types/organization";

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

  private async requestVoid(path: string, options: RequestInit = {}): Promise<void> {
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

  async getHrDashboard(): Promise<HrDashboard> {
    return this.request<HrDashboard>("/api/v1/hr/dashboard");
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

  async listPositions(params?: { department_id?: number; q?: string }): Promise<OrgPosition[]> {
    const query = new URLSearchParams();
    if (params?.department_id) query.set("department_id", String(params.department_id));
    if (params?.q) query.set("q", params.q);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return this.request<OrgPosition[]>(`/api/v1/positions${suffix}`);
  }

  async createPosition(payload: PositionPayload): Promise<OrgPosition> {
    return this.request<OrgPosition>("/api/v1/positions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updatePosition(id: number, payload: Partial<PositionPayload>): Promise<OrgPosition> {
    return this.request<OrgPosition>(`/api/v1/positions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deletePosition(id: number): Promise<void> {
    return this.requestVoid(`/api/v1/positions/${id}`, { method: "DELETE" });
  }

  async getMyOrganization(): Promise<EmployeeOrganization> {
    return this.request<EmployeeOrganization>("/api/v1/me/organization");
  }

  async getEmployeeOrganization(id: number): Promise<EmployeeOrganization> {
    return this.request<EmployeeOrganization>(`/api/v1/employees/${id}/organization`);
  }

  async getOrganizationHierarchy(): Promise<HierarchyResponse> {
    return this.request<HierarchyResponse>("/api/v1/organization/hierarchy");
  }

  async getOrganizationDirectory(q?: string): Promise<DirectoryResponse> {
    const suffix = q ? `?q=${encodeURIComponent(q)}` : "";
    return this.request<DirectoryResponse>(`/api/v1/organization/directory${suffix}`);
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

  async convertInternToEmployee(id: number): Promise<Employee> {
    return this.request<Employee>(`/api/v1/employees/${id}/convert-to-employee`, {
      method: "POST",
    });
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

  async extractCvFromUpload(file: File): Promise<CvExtractionResponse> {
    const formData = new FormData();
    formData.append("cv", file);
    return this.request<CvExtractionResponse>("/api/v1/careers/cv/extract", {
      method: "POST",
      body: formData,
    });
  }

  async getMyApplication(id: number): Promise<ApplicationDetail> {
    return this.request<ApplicationDetail>(`/api/v1/careers/applications/${id}`);
  }

  async listMyApplications(): Promise<CandidateApplicationSummary[]> {
    return this.request<CandidateApplicationSummary[]>("/api/v1/careers/my-applications");
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
    return this.request<InterviewDetail>(`/api/v1/me/interviews/${id}/complete`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listMyInterviews(): Promise<InterviewSummary[]> {
    return this.request<InterviewSummary[]>("/api/v1/me/interviews");
  }

  async getMyInterview(id: number): Promise<InterviewDetail> {
    return this.request<InterviewDetail>(`/api/v1/me/interviews/${id}`);
  }

  async proposeMyInterviewSlots(
    id: number,
    payload: InterviewProposeSlotsPayload,
  ): Promise<InterviewDetail> {
    return this.request<InterviewDetail>(`/api/v1/me/interviews/${id}/slots`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async recordInterviewOutcome(id: number, payload: InterviewOutcomePayload): Promise<InterviewDetail> {
    return this.request<InterviewDetail>(`/api/v1/interviews/${id}/outcome`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listOnboardings(): Promise<OnboardingListItem[]> {
    return this.request<OnboardingListItem[]>("/api/v1/onboarding");
  }

  async getOnboarding(id: number): Promise<Onboarding> {
    return this.request<Onboarding>(`/api/v1/onboarding/${id}`);
  }

  async listOnboardingTasks(onboardingId: number): Promise<OnboardingTask[]> {
    return this.request<OnboardingTask[]>(`/api/v1/onboarding/${onboardingId}/tasks`);
  }

  async listOnboardingTaskTemplates(activeOnly = false): Promise<OnboardingTaskTemplate[]> {
    const query = activeOnly ? "?active_only=true" : "";
    return this.request<OnboardingTaskTemplate[]>(`/api/v1/onboarding/task-templates${query}`);
  }

  async createOnboardingTaskTemplate(
    payload: OnboardingTaskTemplatePayload,
  ): Promise<OnboardingTaskTemplate> {
    return this.request<OnboardingTaskTemplate>("/api/v1/onboarding/task-templates", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateOnboardingTaskTemplate(
    id: number,
    payload: Partial<OnboardingTaskTemplatePayload>,
  ): Promise<OnboardingTaskTemplate> {
    return this.request<OnboardingTaskTemplate>(`/api/v1/onboarding/task-templates/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteOnboardingTaskTemplate(id: number): Promise<OnboardingTaskTemplate | void> {
    const token = this.getToken();
    const response = await fetch(`${this.baseUrl}/api/v1/onboarding/task-templates/${id}`, {
      method: "DELETE",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (response.status === 204) return;
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(formatApiDetail(data.detail) || "Request failed");
    }
    return response.json();
  }

  async createOnboardingTask(
    onboardingId: number,
    payload: OnboardingTaskCreatePayload,
  ): Promise<OnboardingTask> {
    return this.request<OnboardingTask>(`/api/v1/onboarding/${onboardingId}/tasks`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateOnboardingTask(
    taskId: number,
    payload: OnboardingTaskUpdatePayload,
  ): Promise<OnboardingTask> {
    return this.request<OnboardingTask>(`/api/v1/onboarding/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteOnboardingTask(taskId: number): Promise<void> {
    return this.requestVoid(`/api/v1/onboarding/tasks/${taskId}`, { method: "DELETE" });
  }

  async getMyOnboarding(): Promise<Onboarding> {
    return this.request<Onboarding>("/api/v1/me/onboarding");
  }

  async getMyOnboardingProgress(): Promise<OnboardingProgress> {
    return this.request<OnboardingProgress>("/api/v1/me/onboarding/progress");
  }

  async getOnboardingProgress(onboardingId: number): Promise<OnboardingProgress> {
    return this.request<OnboardingProgress>(`/api/v1/onboarding/${onboardingId}/progress`);
  }

  async listMyOnboardingTasks(): Promise<OnboardingTask[]> {
    return this.request<OnboardingTask[]>("/api/v1/me/onboarding/tasks");
  }

  async completeMyOnboardingTask(taskId: number): Promise<OnboardingTask> {
    return this.request<OnboardingTask>(`/api/v1/me/onboarding/tasks/${taskId}/complete`, {
      method: "PATCH",
    });
  }

  async acknowledgeMyOnboardingTask(taskId: number): Promise<OnboardingTask> {
    return this.request<OnboardingTask>(`/api/v1/me/onboarding/tasks/${taskId}/acknowledge`, {
      method: "PATCH",
    });
  }

  async completeManualOnboardingTask(taskId: number): Promise<OnboardingTask> {
    return this.request<OnboardingTask>(`/api/v1/onboarding/tasks/${taskId}/complete`, {
      method: "PATCH",
    });
  }

  async completeOnboarding(onboardingId: number): Promise<Onboarding> {
    return this.request<Onboarding>(`/api/v1/onboarding/${onboardingId}/complete`, {
      method: "POST",
    });
  }

  async listMyDocuments(): Promise<EmployeeDocument[]> {
    return this.request<EmployeeDocument[]>("/api/v1/me/documents");
  }

  async uploadMyDocument(documentType: DocumentType, file: File): Promise<EmployeeDocument> {
    const form = new FormData();
    form.append("document_type", documentType);
    form.append("file", file);
    return this.request<EmployeeDocument>("/api/v1/me/documents", {
      method: "POST",
      body: form,
    });
  }

  async getMyDocumentUrl(documentId: number, download = false): Promise<PresignedDocumentUrl> {
    const query = download ? "?download=true" : "";
    return this.request<PresignedDocumentUrl>(`/api/v1/me/documents/${documentId}/url${query}`);
  }

  async listEmployeeDocuments(employeeId: number): Promise<EmployeeDocument[]> {
    return this.request<EmployeeDocument[]>(`/api/v1/employees/${employeeId}/documents`);
  }

  async uploadEmployeeDocument(
    employeeId: number,
    documentType: DocumentType,
    file: File,
  ): Promise<EmployeeDocument> {
    const form = new FormData();
    form.append("document_type", documentType);
    form.append("file", file);
    return this.request<EmployeeDocument>(`/api/v1/employees/${employeeId}/documents`, {
      method: "POST",
      body: form,
    });
  }

  async getEmployeeDocumentUrl(
    employeeId: number,
    documentId: number,
    download = false,
  ): Promise<PresignedDocumentUrl> {
    const query = download ? "?download=true" : "";
    return this.request<PresignedDocumentUrl>(
      `/api/v1/employees/${employeeId}/documents/${documentId}/url${query}`,
    );
  }

  async deleteEmployeeDocument(employeeId: number, documentId: number): Promise<void> {
    return this.requestVoid(`/api/v1/employees/${employeeId}/documents/${documentId}`, {
      method: "DELETE",
    });
  }

  async listCompanyDocumentCategories(): Promise<CompanyDocumentCategory[]> {
    return this.request<CompanyDocumentCategory[]>("/api/v1/company-documents/categories");
  }

  async listCompanyDocuments(params?: {
    q?: string;
    category_id?: number;
    status?: CompanyDocumentStatus;
  }): Promise<CompanyDocument[]> {
    const search = new URLSearchParams();
    if (params?.q) search.set("q", params.q);
    if (params?.category_id != null) search.set("category_id", String(params.category_id));
    if (params?.status) search.set("status", params.status);
    const query = search.toString();
    return this.request<CompanyDocument[]>(
      `/api/v1/company-documents${query ? `?${query}` : ""}`,
    );
  }

  async uploadCompanyDocument(payload: {
    title: string;
    description?: string;
    category_id: number;
    file: File;
  }): Promise<CompanyDocument> {
    const form = new FormData();
    form.append("title", payload.title);
    form.append("category_id", String(payload.category_id));
    if (payload.description) form.append("description", payload.description);
    form.append("file", payload.file);
    return this.request<CompanyDocument>("/api/v1/company-documents", {
      method: "POST",
      body: form,
    });
  }

  async updateCompanyDocument(
    documentId: number,
    payload: CompanyDocumentUpdatePayload,
  ): Promise<CompanyDocument> {
    return this.request<CompanyDocument>(`/api/v1/company-documents/${documentId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteCompanyDocument(documentId: number): Promise<void> {
    return this.requestVoid(`/api/v1/company-documents/${documentId}`, {
      method: "DELETE",
    });
  }

  async reindexCompanyDocument(documentId: number): Promise<CompanyDocument> {
    return this.request<CompanyDocument>(
      `/api/v1/company-documents/${documentId}/rag-index`,
      { method: "POST" },
    );
  }

  async getCompanyDocumentUrl(
    documentId: number,
    download = false,
  ): Promise<PresignedDocumentUrl> {
    const query = download ? "?download=true" : "";
    return this.request<PresignedDocumentUrl>(
      `/api/v1/company-documents/${documentId}/url${query}`,
    );
  }

  async listMyPrivateDocuments(): Promise<PrivateDocument[]> {
    return this.request<PrivateDocument[]>("/api/v1/me/private-documents");
  }

  async uploadMyPrivateDocument(payload: {
    title: string;
    description?: string;
    file: File;
  }): Promise<PrivateDocument> {
    const form = new FormData();
    form.append("title", payload.title);
    if (payload.description) form.append("description", payload.description);
    form.append("file", payload.file);
    return this.request<PrivateDocument>("/api/v1/me/private-documents", {
      method: "POST",
      body: form,
    });
  }

  async updateMyPrivateDocument(
    documentId: number,
    payload: PrivateDocumentUpdatePayload,
  ): Promise<PrivateDocument> {
    return this.request<PrivateDocument>(`/api/v1/me/private-documents/${documentId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteMyPrivateDocument(documentId: number): Promise<void> {
    return this.requestVoid(`/api/v1/me/private-documents/${documentId}`, {
      method: "DELETE",
    });
  }

  async getMyPrivateDocumentUrl(
    documentId: number,
    download = false,
  ): Promise<PresignedDocumentUrl> {
    const query = download ? "?download=true" : "";
    return this.request<PresignedDocumentUrl>(
      `/api/v1/me/private-documents/${documentId}/url${query}`,
    );
  }

  async listTrainings(): Promise<Training[]> {
    return this.request<Training[]>("/api/v1/trainings");
  }

  async createTraining(payload: TrainingPayload): Promise<Training> {
    return this.request<Training>("/api/v1/trainings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listOnboardingTrainings(onboardingId: number): Promise<OnboardingTrainingAssignment[]> {
    return this.request<OnboardingTrainingAssignment[]>(
      `/api/v1/onboarding/${onboardingId}/trainings`,
    );
  }

  async assignOnboardingTraining(
    onboardingId: number,
    trainingId: number,
  ): Promise<OnboardingTrainingAssignment> {
    return this.request<OnboardingTrainingAssignment>(
      `/api/v1/onboarding/${onboardingId}/trainings`,
      {
        method: "POST",
        body: JSON.stringify({ training_id: trainingId }),
      },
    );
  }

  async removeOnboardingTraining(onboardingId: number, assignmentId: number): Promise<void> {
    return this.requestVoid(`/api/v1/onboarding/${onboardingId}/trainings/${assignmentId}`, {
      method: "DELETE",
    });
  }

  async listMyOnboardingTrainings(): Promise<OnboardingTrainingAssignment[]> {
    return this.request<OnboardingTrainingAssignment[]>("/api/v1/me/onboarding/trainings");
  }

  async completeMyOnboardingTraining(assignmentId: number): Promise<OnboardingTrainingAssignment> {
    return this.request<OnboardingTrainingAssignment>(
      `/api/v1/me/onboarding/trainings/${assignmentId}/complete`,
      { method: "PATCH" },
    );
  }

  async getMyProfile(): Promise<EmployeeProfile> {
    return this.request<EmployeeProfile>("/api/v1/me/profile");
  }

  async updateMyProfile(payload: ProfileUpdatePayload): Promise<EmployeeProfile> {
    return this.request<EmployeeProfile>("/api/v1/me/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async uploadMyProfilePicture(file: File): Promise<EmployeeProfile> {
    const form = new FormData();
    form.append("file", file);
    return this.request<EmployeeProfile>("/api/v1/me/profile/picture", {
      method: "POST",
      body: form,
    });
  }

  async getMyProfilePictureUrl(): Promise<PresignedProfilePictureUrl> {
    return this.request<PresignedProfilePictureUrl>("/api/v1/me/profile/picture/url");
  }

  async deleteMyProfilePicture(): Promise<void> {
    return this.requestVoid("/api/v1/me/profile/picture", { method: "DELETE" });
  }

  async listMyEducation(): Promise<EmployeeEducation[]> {
    return this.request<EmployeeEducation[]>("/api/v1/me/profile/education");
  }

  async createMyEducation(payload: EducationPayload): Promise<EmployeeEducation> {
    return this.request<EmployeeEducation>("/api/v1/me/profile/education", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateMyEducation(
    educationId: number,
    payload: Partial<EducationPayload>,
  ): Promise<EmployeeEducation> {
    return this.request<EmployeeEducation>(`/api/v1/me/profile/education/${educationId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteMyEducation(educationId: number): Promise<void> {
    return this.requestVoid(`/api/v1/me/profile/education/${educationId}`, { method: "DELETE" });
  }

  async listMyExperience(): Promise<EmployeeExperience[]> {
    return this.request<EmployeeExperience[]>("/api/v1/me/profile/experience");
  }

  async createMyExperience(payload: ExperiencePayload): Promise<EmployeeExperience> {
    return this.request<EmployeeExperience>("/api/v1/me/profile/experience", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateMyExperience(
    experienceId: number,
    payload: Partial<ExperiencePayload>,
  ): Promise<EmployeeExperience> {
    return this.request<EmployeeExperience>(`/api/v1/me/profile/experience/${experienceId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteMyExperience(experienceId: number): Promise<void> {
    return this.requestVoid(`/api/v1/me/profile/experience/${experienceId}`, { method: "DELETE" });
  }

  async getEmployeeProfile(employeeId: number): Promise<EmployeeProfile> {
    return this.request<EmployeeProfile>(`/api/v1/employees/${employeeId}/profile`);
  }

  async listEmployeeEducation(employeeId: number): Promise<EmployeeEducation[]> {
    return this.request<EmployeeEducation[]>(`/api/v1/employees/${employeeId}/profile/education`);
  }

  async listEmployeeExperience(employeeId: number): Promise<EmployeeExperience[]> {
    return this.request<EmployeeExperience[]>(
      `/api/v1/employees/${employeeId}/profile/experience`,
    );
  }

  async getEmployeeProfilePictureUrl(employeeId: number): Promise<PresignedProfilePictureUrl> {
    return this.request<PresignedProfilePictureUrl>(
      `/api/v1/employees/${employeeId}/profile/picture/url`,
    );
  }

  // --- Leave ---

  async listLeaveTypes(activeOnly = false): Promise<LeaveType[]> {
    const query = activeOnly ? "?active_only=true" : "";
    return this.request<LeaveType[]>(`/api/v1/leave/types${query}`);
  }

  async listMyLeaveTypes(): Promise<LeaveType[]> {
    return this.request<LeaveType[]>("/api/v1/me/leave/types");
  }

  async createLeaveType(payload: LeaveTypePayload): Promise<LeaveType> {
    return this.request<LeaveType>("/api/v1/leave/types", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateLeaveType(id: number, payload: LeaveTypeUpdatePayload): Promise<LeaveType> {
    return this.request<LeaveType>(`/api/v1/leave/types/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteLeaveType(id: number): Promise<LeaveType> {
    return this.request<LeaveType>(`/api/v1/leave/types/${id}`, { method: "DELETE" });
  }

  async listLeavePolicies(params?: { leave_type_id?: number; year?: number }): Promise<LeavePolicy[]> {
    const search = new URLSearchParams();
    if (params?.leave_type_id != null) search.set("leave_type_id", String(params.leave_type_id));
    if (params?.year != null) search.set("year", String(params.year));
    const query = search.toString() ? `?${search.toString()}` : "";
    return this.request<LeavePolicy[]>(`/api/v1/leave/policies${query}`);
  }

  async createLeavePolicy(payload: LeavePolicyPayload): Promise<LeavePolicy> {
    return this.request<LeavePolicy>("/api/v1/leave/policies", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateLeavePolicy(id: number, payload: LeavePolicyUpdatePayload): Promise<LeavePolicy> {
    return this.request<LeavePolicy>(`/api/v1/leave/policies/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteLeavePolicy(id: number): Promise<void> {
    return this.requestVoid(`/api/v1/leave/policies/${id}`, { method: "DELETE" });
  }

  async listMyLeaveBalances(year?: number): Promise<LeaveBalance[]> {
    const query = year != null ? `?year=${year}` : "";
    return this.request<LeaveBalance[]>(`/api/v1/me/leave/balances${query}`);
  }

  async listEmployeeLeaveBalances(employeeId: number, year?: number): Promise<LeaveBalance[]> {
    const query = year != null ? `?year=${year}` : "";
    return this.request<LeaveBalance[]>(`/api/v1/employees/${employeeId}/leave/balances${query}`);
  }

  async getMyLeaveCalendar(year: number, month: number): Promise<LeaveCalendar> {
    return this.request<LeaveCalendar>(`/api/v1/me/leave/calendar?year=${year}&month=${month}`);
  }

  async getEmployeeLeaveCalendar(
    employeeId: number,
    year: number,
    month: number
  ): Promise<LeaveCalendar> {
    return this.request<LeaveCalendar>(
      `/api/v1/employees/${employeeId}/leave/calendar?year=${year}&month=${month}`
    );
  }

  async listMyTeamLeaveRequests(
    status: LeaveRequestStatus | "" = "pending",
    cancellationStatus?: LeaveCancellationStatus
  ): Promise<LeaveRequest[]> {
    const search = new URLSearchParams();
    search.set("status", status);
    if (cancellationStatus) search.set("cancellation_status", cancellationStatus);
    return this.request<LeaveRequest[]>(
      `/api/v1/me/leave/team-requests?${search.toString()}`
    );
  }

  async listMyLeaveRequests(): Promise<LeaveRequest[]> {
    return this.request<LeaveRequest[]>("/api/v1/me/leave/requests");
  }

  async createMyLeaveRequest(payload: LeaveRequestCreatePayload): Promise<LeaveRequest> {
    return this.request<LeaveRequest>("/api/v1/me/leave/requests", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async cancelMyLeaveRequest(requestId: number): Promise<LeaveRequest> {
    return this.request<LeaveRequest>(`/api/v1/me/leave/requests/${requestId}/cancel`, {
      method: "PATCH",
    });
  }

  async requestMyLeaveCancellation(requestId: number, reason: string): Promise<LeaveRequest> {
    return this.request<LeaveRequest>(
      `/api/v1/me/leave/requests/${requestId}/cancellation`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    );
  }

  async listLeaveRequests(params?: {
    employee_id?: number;
    leave_type_id?: number;
    status?: LeaveRequestStatus;
    cancellation_status?: LeaveCancellationStatus;
  }): Promise<LeaveRequest[]> {
    const search = new URLSearchParams();
    if (params?.employee_id != null) search.set("employee_id", String(params.employee_id));
    if (params?.leave_type_id != null) search.set("leave_type_id", String(params.leave_type_id));
    if (params?.status) search.set("status", params.status);
    if (params?.cancellation_status) {
      search.set("cancellation_status", params.cancellation_status);
    }
    const query = search.toString() ? `?${search.toString()}` : "";
    return this.request<LeaveRequest[]>(`/api/v1/leave/requests${query}`);
  }

  async approveLeaveRequest(requestId: number): Promise<LeaveRequest> {
    return this.request<LeaveRequest>(`/api/v1/leave/requests/${requestId}/approve`, {
      method: "PATCH",
    });
  }

  async rejectLeaveRequest(requestId: number, rejectionReason: string): Promise<LeaveRequest> {
    return this.request<LeaveRequest>(`/api/v1/leave/requests/${requestId}/reject`, {
      method: "PATCH",
      body: JSON.stringify({ rejection_reason: rejectionReason }),
    });
  }

  async approveLeaveCancellation(requestId: number): Promise<LeaveRequest> {
    return this.request<LeaveRequest>(
      `/api/v1/leave/requests/${requestId}/cancellation/approve`,
      { method: "POST" }
    );
  }

  async rejectLeaveCancellation(requestId: number, reason: string): Promise<LeaveRequest> {
    return this.request<LeaveRequest>(
      `/api/v1/leave/requests/${requestId}/cancellation/reject`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    );
  }

  async askKnowledgeAgent(payload: KnowledgeAskPayload): Promise<KnowledgeAskResponse> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}/api/v1/ai/knowledge/ask`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
    } catch {
      throw new ApiClientError("Cannot reach the server. Is the backend running?", 0);
    }

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: "An unexpected error occurred",
      }));
      throw new ApiClientError(formatApiDetail(error.detail), response.status);
    }

    return response.json();
  }

  logout(): void {
    this.clearToken();
  }
}

export class ApiClientError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
  }
}

export const api = new ApiClient(API_URL);
