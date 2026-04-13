import type { IncidentStatus } from "../../types/incident";

const STATUS_STYLES: Record<IncidentStatus, string> = {
  pending:           "bg-gray-700 text-gray-300",
  running:           "bg-blue-700 text-blue-200",
  awaiting_approval: "bg-yellow-700 text-yellow-200",
  executing:         "bg-blue-700 text-blue-200",
  resolved:          "bg-green-700 text-green-200",
  completed:         "bg-green-700 text-green-200",
  failed:            "bg-red-700 text-red-200",
  rejected:          "bg-orange-700 text-orange-200",
  aborted:           "bg-gray-700 text-gray-300",
  escalated:         "bg-purple-700 text-purple-200",
};

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[status] ?? "bg-gray-700 text-gray-300"}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
