export type NotificationType =
  | "application_status_changed"
  | "interview_invitation"
  | "interview_scheduled";

export interface Notification {
  id: number;
  type: NotificationType;
  title: string;
  message: string;
  related_entity_type: string | null;
  related_entity_id: number | null;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
}

export interface UnreadCountResponse {
  count: number;
}

export interface MarkAllReadResponse {
  updated: number;
}
