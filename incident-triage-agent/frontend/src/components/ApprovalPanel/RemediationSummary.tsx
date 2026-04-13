import { JsonViewer } from "../common/JsonViewer";
import type { RemediationPlan } from "../../types/incident";

const RISK_STYLES: Record<string, string> = {
  low:    "bg-green-800 text-green-200",
  medium: "bg-yellow-800 text-yellow-200",
  high:   "bg-red-800 text-red-200",
};

export function RemediationSummary({ plan }: { plan: RemediationPlan }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs text-gray-400 mb-0.5">Action</p>
          <p className="text-sm text-gray-100 font-medium">{plan.action}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-0.5">Target</p>
          <p className="text-sm text-gray-100 font-medium">{plan.target}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-0.5">Risk</p>
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${RISK_STYLES[plan.risk_level] ?? "bg-gray-700 text-gray-300"}`}>
            {plan.risk_level}
          </span>
        </div>
      </div>
      <div>
        <p className="text-xs text-gray-400 mb-0.5">Rationale</p>
        <p className="text-sm text-gray-300">{plan.rationale}</p>
      </div>
      {Object.keys(plan.params).length > 0 && (
        <div>
          <p className="text-xs text-gray-400 mb-1">Params</p>
          <JsonViewer data={plan.params} />
        </div>
      )}
    </div>
  );
}
