import { useCallback, useEffect, useRef } from "react";
import { useIncidentStore } from "../store/incidentStore";
import type { ApprovalMessage, WSEvent } from "../types/events";

// ---------------------------------------------------------------------------
// Module-level singleton pool — one WebSocket per incidentId.
// ---------------------------------------------------------------------------

interface SocketEntry {
  ws: WebSocket;
  refCount: number;
  retryTimer: ReturnType<typeof setTimeout> | null;
  listeners: Set<(event: WSEvent) => void>;
}

const pool = new Map<string, SocketEntry>();

const NEXT_NODE: Record<string, string> = {
  analyze_root_cause: "propose_remediation",
  propose_remediation: "execute_remediation",
  verify_resolution: "end_review",
};

function dispatchSyntheticInterrupt(incidentId: string, entry: SocketEntry, record: Record<string, unknown>) {
  const stepName = NEXT_NODE[record.current_step as string];
  if (!stepName) return;
  const syntheticEvent: WSEvent = {
    event_type: "interrupt",
    incident_id: incidentId,
    step_name: stepName,
    data: { awaiting: stepName, context: {
      root_cause: record.root_cause,
      root_cause_confidence: record.root_cause_confidence,
      proposed_remediation: record.proposed_remediation,
      verification_result: record.verification_result,
    }},
    timestamp: new Date().toISOString(),
  };
  entry.listeners.forEach((fn) => fn(syntheticEvent));
}

// Poll until the incident reaches awaiting_approval, then dispatch a synthetic
// interrupt event. Stops when the pool entry is removed (incident navigated away).
function pollForInterrupts(incidentId: string, entry: SocketEntry, lastStep?: string) {
  fetch(`/api/incidents/${encodeURIComponent(incidentId)}`)
    .then((r) => r.json())
    .then((record) => {
      if (!pool.has(incidentId)) return;
      useIncidentStore.getState().upsertIncident(record);
      const currentStep = NEXT_NODE[record.current_step];

      if (record.status === "awaiting_approval") {
        // Only dispatch if we've moved to a new interrupt step.
        if (currentStep && currentStep !== lastStep) {
          dispatchSyntheticInterrupt(incidentId, entry, record);
        }
        setTimeout(() => {
          if (pool.has(incidentId)) pollForInterrupts(incidentId, entry, currentStep);
        }, 500);
      } else if (record.status === "running" || record.status === "pending") {
        setTimeout(() => {
          if (pool.has(incidentId)) pollForInterrupts(incidentId, entry, lastStep);
        }, 500);
      }
      // completed / failed — stop polling
    })
    .catch(() => {
      setTimeout(() => {
        if (pool.has(incidentId)) pollForInterrupts(incidentId, entry, lastStep);
      }, 1000);
    });
}

function openSocket(incidentId: string, entry: SocketEntry) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${window.location.hostname}:8000/ws/incidents/${encodeURIComponent(incidentId)}`;
  const ws = new WebSocket(url);
  entry.ws = ws;

  ws.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data as string) as WSEvent;
      entry.listeners.forEach((fn) => fn(event));
    } catch {
      console.warn("WS: failed to parse message", e.data);
    }
  };

  ws.onopen = () => {};

  ws.onclose = () => {
    if (!pool.has(incidentId)) return;
    entry.retryTimer = setTimeout(() => {
      if (pool.has(incidentId)) openSocket(incidentId, entry);
    }, 1500);
  };

  ws.onerror = () => {};
}

function getOrCreate(incidentId: string): SocketEntry {
  const existing = pool.get(incidentId);
  if (existing) {
    existing.refCount += 1;
    return existing;
  }
  const entry: SocketEntry = {
    ws: null!,
    refCount: 1,
    retryTimer: null,
    listeners: new Set(),
  };
  pool.set(incidentId, entry);
  openSocket(incidentId, entry);
  return entry;
}

function release(incidentId: string) {
  const entry = pool.get(incidentId);
  if (!entry) return;
  entry.refCount -= 1;
  if (entry.refCount <= 0) {
    pool.delete(incidentId);
    if (entry.retryTimer) clearTimeout(entry.retryTimer);
    const ws = entry.ws;
    if (ws) {
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
      ws.close();
    }
  }
}

// ---------------------------------------------------------------------------
// React hook
// ---------------------------------------------------------------------------

export function useIncidentWebSocket(incidentId: string) {
  const appendEvent = useIncidentStore((s) => s.appendEvent);
  const applyEventPatch = useIncidentStore((s) => s.applyEventPatch);
  const appendEventRef = useRef(appendEvent);
  const applyEventPatchRef = useRef(applyEventPatch);
  appendEventRef.current = appendEvent;
  applyEventPatchRef.current = applyEventPatch;

  const incidentIdRef = useRef(incidentId);
  incidentIdRef.current = incidentId;

  useEffect(() => {
    const entry = getOrCreate(incidentId);

    const onEvent = (event: WSEvent) => {
      appendEventRef.current(incidentId, event);
      applyEventPatchRef.current(event);
    };
    entry.listeners.add(onEvent);

    // Listener is now registered — poll until the graph pauses at an approval
    // point and dispatch a synthetic interrupt event when it does.
    pollForInterrupts(incidentId, entry);

    return () => {
      entry.listeners.delete(onEvent);
      release(incidentId);
    };
  }, [incidentId]);

  const sendDecision = useCallback((msg: ApprovalMessage) => {
    fetch(`/api/incidents/${encodeURIComponent(incidentIdRef.current)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg),
    }).catch((err) => console.warn("sendDecision: HTTP POST failed", err));
  }, []);

  return { sendDecision };
}
