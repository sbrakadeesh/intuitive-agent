export type EventType =
  | "step_start"
  | "step_complete"
  | "interrupt"
  | "tool_call"
  | "tool_result"
  | "complete"
  | "error"
  | "status_update";

export type HumanDecision =
  | "approved"
  | "rejected"
  | "edited"
  | "abort"
  | "escalate"
  | "close";

export interface WSEvent {
  event_type: EventType;
  incident_id: string;
  step_name?: string;
  data?: unknown;
  timestamp: string;
}

export interface ApprovalMessage {
  decision: HumanDecision;
  operator_edit?: Record<string, unknown>;
  operator_notes?: string;
}
