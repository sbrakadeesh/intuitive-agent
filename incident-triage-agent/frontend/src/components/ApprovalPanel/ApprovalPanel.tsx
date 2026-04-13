import { useIncidentStore } from "../../store/incidentStore";
import { RemediationSummary } from "./RemediationSummary";
import { ApprovalActions } from "./ApprovalActions";
import type { ApprovalMessage, WSEvent } from "../../types/events";

const INTERRUPT_STEPS: Record<string, "interrupt1" | "interrupt2" | "interrupt3"> = {
  propose_remediation: "interrupt1",
  execute_remediation: "interrupt2",
  end_review:          "interrupt3",
};

function getInterruptType(events: WSEvent[]): "interrupt1" | "interrupt2" | "interrupt3" | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.event_type === "interrupt" && e.step_name) {
      return INTERRUPT_STEPS[e.step_name] ?? null;
    }
  }
  return null;
}

export function ApprovalPanel({ incidentId, sendDecision }: { incidentId: string; sendDecision: (msg: ApprovalMessage) => void }) {
  const record = useIncidentStore((s) => s.incidents[incidentId]);
  const events = useIncidentStore((s) => s.eventLog[incidentId]);

  const safeEvents = events ?? [];

  if (!record || record.status !== "awaiting_approval") return null;

  const interruptType = getInterruptType(safeEvents);
  if (!interruptType) return null;

  function handleDecision(msg: ApprovalMessage) {
    sendDecision(msg);
  }

  return (
    <div className="shrink-0 border-t border-gray-800 bg-gray-900 px-6 py-4">
      <div className="flex items-center gap-2 mb-4">
        <span className="inline-block h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
        <h3 className="text-xs font-semibold text-yellow-400 uppercase tracking-widest">
          Awaiting Approval
          {record.current_step && (
            <span className="normal-case font-normal text-yellow-300 ml-2">
              — {record.current_step.replace(/_/g, " ")}
            </span>
          )}
        </h3>
      </div>

      {/* Interrupt 1: show root cause for confirmation */}
      {interruptType === "interrupt1" && record.root_cause && (
        <div className="mb-4 p-3 rounded bg-gray-800 border border-gray-700">
          <p className="text-xs text-gray-400 mb-1">Root Cause</p>
          <p className="text-sm text-gray-100">{record.root_cause}</p>
          {record.root_cause_confidence !== undefined && (
            <p className="text-xs text-gray-500 mt-1">
              Confidence: {(record.root_cause_confidence * 100).toFixed(0)}%
            </p>
          )}
        </div>
      )}

      {/* Interrupt 2: show remediation plan */}
      {interruptType === "interrupt2" && record.proposed_remediation && (
        <div className="mb-4 p-3 rounded bg-gray-800 border border-gray-700">
          <RemediationSummary plan={record.proposed_remediation} />
        </div>
      )}

      {/* Interrupt 3: show verification result */}
      {interruptType === "interrupt3" && record.verification_result && (
        <div className="mb-4 p-3 rounded bg-gray-800 border border-gray-700">
          <p className="text-xs text-gray-400 mb-1">Verification</p>
          <p className="text-sm text-gray-100">{record.verification_result}</p>
        </div>
      )}

      <ApprovalActions interruptType={interruptType} onDecision={handleDecision} />
    </div>
  );
}
