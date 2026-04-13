import type { Severity } from "../../types/incident";

const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "bg-red-700 text-red-200",
  high:     "bg-orange-700 text-orange-200",
  medium:   "bg-yellow-700 text-yellow-200",
  low:      "bg-green-700 text-green-200",
  warning:  "bg-yellow-700 text-yellow-200",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${SEVERITY_STYLES[severity]}`}>
      {severity}
    </span>
  );
}
