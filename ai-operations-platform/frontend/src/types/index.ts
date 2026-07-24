// Shared frontend types. Mirrors the backend response schemas.

export interface DatasetManifest {
  ticket_count: number;
  comment_count: number;
  metric_events: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  by_type: Record<string, number>;
  by_locale: Record<string, number>;
  [key: string]: unknown;
}
