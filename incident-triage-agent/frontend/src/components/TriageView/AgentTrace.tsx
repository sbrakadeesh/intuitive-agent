import { useEffect, useRef } from "react";
import { useIncidentStore } from "../../store/incidentStore";
import { ToolCallCard } from "./ToolCallCard";
import type { WSEvent } from "../../types/events";

function TraceRow({ event }: { event: WSEvent }) {
  const isInterrupt = event.event_type === "interrupt";
  const isTool = event.event_type === "tool_call" || event.event_type === "tool_result";

  if (isTool) return <ToolCallCard event={event} />;

  return (
    <div
      className={`flex gap-3 text-xs px-3 py-1.5 rounded ${
        isInterrupt ? "bg-yellow-900/40 text-yellow-300" : "text-gray-400"
      }`}
    >
      <span className="shrink-0 text-gray-600">
        {new Date(event.timestamp).toLocaleTimeString()}
      </span>
      <span
        className={`shrink-0 font-medium ${
          event.event_type === "error"
            ? "text-red-400"
            : isInterrupt
            ? "text-yellow-400"
            : event.event_type === "complete"
            ? "text-green-400"
            : "text-gray-400"
        }`}
      >
        {event.event_type}
      </span>
      {event.step_name && (
        <span className="text-gray-300">{event.step_name}</span>
      )}
    </div>
  );
}

export function AgentTrace({ incidentId }: { incidentId: string }) {
  const events = useIncidentStore((s) => s.eventLog[incidentId]);
  const safeEvents = events || [];
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [safeEvents.length]);

  if (safeEvents.length === 0) {
    return (
      <p className="text-xs text-gray-600 px-4 py-6 text-center">
        Waiting for events…
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-1 px-2 py-2 overflow-y-auto">
      {safeEvents.map((e: WSEvent, i: number) => (
        <TraceRow key={i} event={e} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
