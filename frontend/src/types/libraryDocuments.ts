export type CompanyDocumentStatus = "active" | "archived";

export type CompanyDocumentRagIndexStatus =
  | "pending"
  | "processing"
  | "ready"
  | "failed";

export interface CompanyDocumentCategory {
  id: number;
  slug: string;
  label: string;
  sort_order: number;
  is_active: boolean;
}

export interface CompanyDocument {
  id: number;
  title: string;
  description: string | null;
  category_id: number;
  category_slug: string;
  category_label: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  version: number;
  uploaded_by_user_id: number;
  uploaded_by_name: string;
  status: CompanyDocumentStatus;
  rag_index_status: CompanyDocumentRagIndexStatus;
  rag_indexed_at: string | null;
  rag_indexing_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompanyDocumentUpdatePayload {
  title?: string;
  description?: string | null;
  category_id?: number;
  status?: CompanyDocumentStatus;
}

export interface PrivateDocument {
  id: number;
  owner_employee_id: number;
  title: string;
  description: string | null;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_by_user_id: number;
  created_at: string;
  updated_at: string;
}

export interface PrivateDocumentUpdatePayload {
  title?: string;
  description?: string | null;
}
