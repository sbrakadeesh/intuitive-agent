import { Spinner } from "../common/Spinner";
import type { IncidentRecord } from "../../types/incident";

const STEPS = [
  { key: "ingest_alert",        label: "Ingest Alert" },
  { key: "fetch_context",       label: "Fetch Context" },
  { key: "analyze_root_cause",  label: "Analyze Root Cause" },
  { key: "propose_remediation", label: "Propose Remediation" },
  { key: "execute_remediation", label: "Execute Remediation" },
  { key: "verify_resolution",   label: "Verify Resolution" },
  { key: "end_review",          label: "End Review" },
];

type StepState = "pending" | "running" | "done" | "awaiting" | "failed";

function getStepState(
  stepKey: string,
  record: IncidentRecord,
  orderedKeys: string[],
): StepState {
  const currentIdx = orderedKeys.indexOf(record.current_step ?? "");
  const stepIdx = orderedKeys.indexOf(stepKey);

  // All steps done when incident is fully complete
  if (record.status === "completed" || record.status === "resolved") return "done";

  if (record.status === "failed" && record.current_step === stepKey) return "failed";
  if (record.status === "awaiting_approval" && record.current_step === stepKey) return "awaiting";
  if (stepIdx < currentIdx) return "done";
  if (stepIdx === currentIdx) return "running";
  return "pending";
}

function StepIcon({ state }: { state: StepState }) {
  if (state === "running") return <Spinner className="h-4 w-4" />;
  if (state === "done")
    return <div className="h-4 w-4 flex items-center justify-center text-green-400 text-xs leading-none">✓</div>;
  if (state === "awaiting")
    return <div className="h-4 w-4 flex items-center justify-center text-yellow-400 text-xs leading-none">II</div>;
  if (state === "failed")
    return <div className="h-4 w-4 flex items-center justify-center text-red-400 text-xs leading-none">X</div>;
  return <div className="h-4 w-4 rounded-full border border-gray-600 bg-gray-800 shrink-0"></div>;
}

export function StepTimeline({ record }: { record: IncidentRecord }) {
  const orderedKeys = STEPS.map((s) => s.key);

  return (
    <ol className="flex flex-col gap-0 py-4 px-3 min-w-[160px]">
      {STEPS.map((step, idx) => {
        const state = getStepState(step.key, record, orderedKeys);
        const isLast = idx === STEPS.length - 1;

        return (
          <li key={step.key} className="flex gap-3 items-start">
            <div className="flex flex-col items-center shrink-0">
              <StepIcon state={state} />
              {!isLast && <div className="w-px bg-gray-700 my-1" style={{ height: 16 }} />}
            </div>
            <span
              className={`text-xs pt-0.5 leading-tight ${
                state === "running"
                  ? "text-blue-300 font-medium"
                  : state === "done"
                  ? "text-gray-300"
                  : state === "awaiting"
                  ? "text-yellow-300"
                  : state === "failed"
                  ? "text-red-400"
                  : "text-gray-600"
              }`}
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
