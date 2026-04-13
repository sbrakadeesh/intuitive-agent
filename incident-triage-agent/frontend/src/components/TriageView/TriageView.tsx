import { useIncidentStore } from "../../store/incidentStore";
import { useIncidentWebSocket } from "../../hooks/useIncidentWebSocket";
import { StatusBadge } from "../common/StatusBadge";
import { StepTimeline } from "./StepTimeline";
import { AgentTrace } from "./AgentTrace";
import { ApprovalPanel } from "../ApprovalPanel/ApprovalPanel";

export function TriageView({ incidentId }: { incidentId: string }) {
  const { sendDecision } = useIncidentWebSocket(incidentId);
  const record = useIncidentStore((s) => s.incidents[incidentId]);

  if (!record) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        Loading incident…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Top bar */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between gap-4 shrink-0">
        <div className="min-w-0">
          <p className="text-xs text-gray-500 mb-0.5">{record.alert.service}</p>
          <h2 className="text-sm font-semibold text-gray-100 truncate">{record.alert.title}</h2>
        </div>
        <StatusBadge status={record.status} />
      </div>

      {/* Body: timeline + trace */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <div className="border-r border-gray-800 shrink-0 overflow-y-auto">
          <StepTimeline record={record} />
        </div>
        <div className="flex-1 overflow-y-auto">
          <AgentTrace incidentId={incidentId} />
        </div>
      </div>

      {/* Approval panel — only renders when awaiting_approval */}
      <ApprovalPanel incidentId={incidentId} sendDecision={sendDecision} />
    </div>
  );
}
