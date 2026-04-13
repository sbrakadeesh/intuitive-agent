import { useState } from "react";
import type { ApprovalMessage } from "../../types/events";

type InterruptType = "interrupt1" | "interrupt2" | "interrupt3";

interface Props {
  interruptType: InterruptType;
  onDecision: (msg: ApprovalMessage) => void;
}

export function ApprovalActions({ interruptType, onDecision }: Props) {
  const [editOpen, setEditOpen] = useState(false);
  const [editJson, setEditJson] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");

  function submit(decision: ApprovalMessage["decision"], withEdit = false) {
    let operator_edit: Record<string, unknown> | undefined;

    if (withEdit && editJson.trim()) {
      try {
        operator_edit = JSON.parse(editJson) as Record<string, unknown>;
        setJsonError(null);
      } catch {
        setJsonError("Invalid JSON");
        return;
      }
    }

    onDecision({
      decision,
      operator_edit,
      operator_notes: notes.trim() || undefined,
    });
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs text-gray-400 mb-1">Notes (optional)</label>
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Add operator notes…"
          className="w-full rounded bg-gray-800 border border-gray-700 px-3 py-1.5 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Interrupt 1 — root cause review */}
      {interruptType === "interrupt1" && (
        <div className="flex gap-2">
          <button
            onClick={() => submit("approved")}
            className="px-3 py-1.5 rounded bg-green-700 hover:bg-green-600 text-xs font-semibold text-white"
          >
            Confirm Root Cause
          </button>
          <button
            onClick={() => submit("abort")}
            className="px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-xs font-semibold text-white"
          >
            Abort
          </button>
        </div>
      )}

      {/* Interrupt 2 — remediation review */}
      {interruptType === "interrupt2" && (
        <div className="space-y-2">
          {editOpen && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">
                Override params (JSON)
              </label>
              <textarea
                rows={3}
                value={editJson}
                onChange={(e) => setEditJson(e.target.value)}
                placeholder='{"namespace": "staging"}'
                className="w-full rounded bg-gray-800 border border-gray-700 px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono resize-none"
              />
              {jsonError && <p className="text-xs text-red-400 mt-1">{jsonError}</p>}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => submit("approved")}
              className="px-3 py-1.5 rounded bg-green-700 hover:bg-green-600 text-xs font-semibold text-white"
            >
              Approve
            </button>
            <button
              onClick={() => submit("rejected")}
              className="px-3 py-1.5 rounded bg-red-700 hover:bg-red-600 text-xs font-semibold text-white"
            >
              Reject
            </button>
            <button
              onClick={() => {
                setEditOpen((v) => !v);
              }}
              className="px-3 py-1.5 rounded bg-yellow-700 hover:bg-yellow-600 text-xs font-semibold text-white"
            >
              {editOpen ? "Cancel Edit" : "Edit & Approve"}
            </button>
            {editOpen && (
              <button
                onClick={() => submit("edited", true)}
                className="px-3 py-1.5 rounded bg-yellow-600 hover:bg-yellow-500 text-xs font-semibold text-white"
              >
                Submit Edit
              </button>
            )}
          </div>
        </div>
      )}

      {/* Interrupt 3 — post-verification */}
      {interruptType === "interrupt3" && (
        <div className="flex gap-2">
          <button
            onClick={() => submit("close")}
            className="px-3 py-1.5 rounded bg-green-700 hover:bg-green-600 text-xs font-semibold text-white"
          >
            Close Incident
          </button>
          <button
            onClick={() => submit("escalate")}
            className="px-3 py-1.5 rounded bg-orange-700 hover:bg-orange-600 text-xs font-semibold text-white"
          >
            Escalate
          </button>
        </div>
      )}
    </div>
  );
}
