import { useState } from "react";
import { JsonViewer } from "../common/JsonViewer";
import type { WSEvent } from "../../types/events";

export function ToolCallCard({ event }: { event: WSEvent }) {
  const [open, setOpen] = useState(false);
  const data = event.data as Record<string, unknown> | null | undefined;

  return (
    <div className="rounded border border-gray-700 bg-gray-800 text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-gray-750 transition-colors"
      >
        <span className="font-medium text-blue-300">
          {event.event_type === "tool_call" ? "⚙ " : "↩ "}
          {event.step_name ?? event.event_type}
        </span>
        <span className="text-gray-500 ml-2">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          {data?.input !== undefined && (
            <div>
              <p className="text-gray-400 mb-1">Input</p>
              <JsonViewer data={data.input} />
            </div>
          )}
          {data?.output !== undefined && (
            <div>
              <p className="text-gray-400 mb-1">Output</p>
              <JsonViewer data={data.output} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
