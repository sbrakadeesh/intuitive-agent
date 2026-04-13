import type { AlertPayload, IncidentRecord } from "../types/incident";
import type { ApprovalMessage } from "../types/events";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function listIncidents(status?: string): Promise<IncidentRecord[]> {
  const url = new URL("/api/incidents", window.location.origin);
  if (status) url.searchParams.set("status", status);
  return request<IncidentRecord[]>(url.pathname + url.search);
}

export async function getIncident(id: string): Promise<IncidentRecord> {
  return request<IncidentRecord>(`/api/incidents/${encodeURIComponent(id)}`);
}

export async function createIncident(alert: AlertPayload): Promise<IncidentRecord> {
  return request<IncidentRecord>("/api/incidents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alert }),
  });
}

export async function submitDecision(
  id: string,
  decision: ApprovalMessage,
): Promise<{ status: string }> {
  return request<{ status: string }>(
    `/api/incidents/${encodeURIComponent(id)}/approve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    },
  );
}
