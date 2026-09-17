export type DocumentType =
  | "id_document"
  | "contract"
  | "diploma"
  | "certificate"
  | "other";

export interface EmployeeDocument {
  id: number;
  employee_id: number;
  document_type: DocumentType;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
  created_at: string;
  updated_at: string;
}

export interface PresignedDocumentUrl {
  url: string;
  filename: string;
  content_type: string;
  expires_in: number;
  download: boolean;
}

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  id_document: "ID document",
  contract: "Contract",
  diploma: "Diploma",
  certificate: "Certificate",
  other: "Other",
};
