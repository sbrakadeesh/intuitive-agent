import { useCallback, useEffect, useRef } from "react";
import { useIncidentStore } from "../store/incidentStore";
import type { ApprovalMessage, WSEvent } from "../types/events";

export function useIncidentWebSocket(incidentId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const appendEvent = useIncidentStore((s) => s.appendEvent);
  const applyEventPatch = useIncidentStore((s) => s.applyEventPatch);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/incidents/${encodeURIComponent(incidentId)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (messageEvent) => {
      try {
        const event = JSON.parse(messageEvent.data as string) as WSEvent;
        appendEvent(incidentId, event);
        applyEventPatch(event);
      } catch {
        console.warn("useIncidentWebSocket: failed to parse message", messageEvent.data);
      }
    };

    ws.onerror = (err) => {
      console.error("useIncidentWebSocket: error for incident", incidentId, err);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [incidentId, appendEvent, applyEventPatch]);

  const sendDecision = useCallback((msg: ApprovalMessage) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    } else {
      console.warn("useIncidentWebSocket: socket not open, decision not sent", msg);
    }
  }, []);

  return { sendDecision };
}
