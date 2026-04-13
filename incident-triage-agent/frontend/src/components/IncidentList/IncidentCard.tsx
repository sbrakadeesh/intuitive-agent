import { formatDistanceToNow } from "date-fns";
import { SeverityBadge } from "../common/SeverityBadge";
import { StatusBadge } from "../common/StatusBadge";
import type { IncidentRecord } from "../../types/incident";

export function IncidentCard({
  record,
  active,
  onClick,
}: {
  record: IncidentRecord;
  active: boolean;
  onClick: () => void;
}) {
  const timeAgo = formatDistanceToNow(new Date(record.created_at), { addSuffix: true });

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-3 rounded-lg transition-colors ${
        active ? "bg-gray-700 ring-1 ring-blue-500" : "hover:bg-gray-800"
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <SeverityBadge severity={record.alert.severity} />
        <StatusBadge status={record.status} />
      </div>
      <p className="text-sm font-medium text-gray-100 truncate">{record.alert.title}</p>
      <div className="flex items-center justify-between mt-1">
        <span className="text-xs text-gray-400 truncate">{record.alert.service}</span>
        <span className="text-xs text-gray-500 shrink-0 ml-2">{timeAgo}</span>
      </div>
    </button>
  );
}
