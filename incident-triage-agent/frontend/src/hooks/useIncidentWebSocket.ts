import { useCallback, useEffect, useRef } from "react";
import { useIncidentStore } from "../store/incidentStore";
import type { ApprovalMessage, WSEvent } from "../types/events";

export function useIncidentWebSocket(incidentId: string) {
  const wsRef = useRef<WebSocket | null>(null);


  const appendEvent = useIncidentStore((s) => s.appendEvent);
  const applyEventPatch = useIncidentStore((s) => s.applyEventPatch);
  const appendEventRef = useRef(appendEvent);
  const applyEventPatchRef = useRef(applyEventPatch);
  appendEventRef.current = appendEvent;
  applyEventPatchRef.current = applyEventPatch;

  useEffect(() => {
    let ws: WebSocket;
    let retryTimer: ReturnType<typeof setTimeout>;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${protocol}//${window.location.host}/ws/incidents/${encodeURIComponent(incidentId)}`;
      ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (messageEvent) => {
        try {
          const event = JSON.parse(messageEvent.data as string) as WSEvent;
          appendEventRef.current(incidentId, event);
          applyEventPatchRef.current(event);
        } catch {
          console.warn("useIncidentWebSocket: failed to parse message", messageEvent.data);
        }
      };

      ws.onerror = () => {
        // Retry after 500ms if connection fails
        retryTimer = setTimeout(connect, 500);
      };

      ws.onclose = () => {
        wsRef.current = null;
      };
    }

    connect();

    return () => {
      clearTimeout(retryTimer);
      ws?.close();
      wsRef.current = null;
    };
  }, [incidentId]);

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
