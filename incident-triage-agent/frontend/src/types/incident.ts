export type Severity = "critical" | "high" | "medium" | "low" | "warning";

export type IncidentStatus =
  | "pending"
  | "running"
  | "awaiting_approval"
  | "executing"
  | "resolved"
  | "failed"
  | "rejected"
  | "aborted"
  | "escalated"
  | "completed";

export interface AlertPayload {
  service: string;
  namespace: string;
  pod_name?: string;
  severity: Severity;
  title: string;
  description: string;
  labels: Record<string, string>;
  started_at?: string;
}

export interface RemediationPlan {
  action: string;
  target: string;
  params: Record<string, unknown>;
  risk_level: "low" | "medium" | "high";
  rationale: string;
}

export interface IncidentRecord {
  incident_id: string;
  alert: AlertPayload;
  status: IncidentStatus;
  current_step?: string;
  root_cause?: string;
  root_cause_confidence?: number;
  proposed_remediation?: RemediationPlan;
  execution_result?: Record<string, unknown>;
  verification_result?: string;
  error?: string;
  created_at: string;
  updated_at: string;
}
