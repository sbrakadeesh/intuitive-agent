import { useIncidentList } from "../../hooks/useIncidentList";
import { useIncidentStore } from "../../store/incidentStore";
import { createIncident } from "../../api/incidents";
import { IncidentCard } from "./IncidentCard";

const SAMPLE_ALERTS = [
  {
    service: "payment-service",
    namespace: "production",
    pod_name: "payment-service-7d9f6c8b4-xk9p2",
    severity: "critical" as const,
    title: "OOMKilled: payment-service restarting repeatedly",
    description: "payment-service has been OOMKilled 5 times in the last 10 minutes. Memory usage peaked at 512Mi against a 512Mi limit.",
    labels: { team: "payments", env: "production", alert_name: "OOMKillDetected" },
    started_at: new Date().toISOString(),
  },
  {
    service: "auth-service",
    namespace: "production",
    pod_name: "auth-service-6bf8d9c5f-m2pq7",
    severity: "critical" as const,
    title: "CrashLoopBackOff: auth-service failing liveness probe",
    description: "auth-service is in CrashLoopBackOff with 8 restarts. Liveness probe returning 503; database connection errors observed.",
    labels: { team: "platform", env: "production", alert_name: "CrashLoopBackOff" },
    started_at: new Date().toISOString(),
  },
  {
    service: "recommendation-service",
    namespace: "staging",
    pod_name: "recommendation-service-5c7b4d6f9-zt3n8",
    severity: "warning" as const,
    title: "High latency: recommendation-service p99 exceeds SLO",
    description: "recommendation-service p99 latency is 3200ms, breaching the 500ms SLO. Connection pool exhausted and circuit breaker is OPEN.",
    labels: { team: "discovery", env: "staging", alert_name: "HighP99Latency" },
    started_at: new Date().toISOString(),
  },
];

let _alertIndex = 0;

export function IncidentList() {
  const { loading, error } = useIncidentList();
  const incidents = useIncidentStore((s) => s.incidents);
  const activeId = useIncidentStore((s) => s.activeIncidentId);
  const setActive = useIncidentStore((s) => s.setActive);
  const upsertIncident = useIncidentStore((s) => s.upsertIncident);

  const sorted = Object.values(incidents).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  async function handleTrigger() {
    try {
      const alert = SAMPLE_ALERTS[_alertIndex % SAMPLE_ALERTS.length];
      _alertIndex += 1;
      const record = await createIncident({ ...alert, started_at: new Date().toISOString() });
      upsertIncident(record);
      setActive(record.incident_id);
    } catch (err) {
      console.error("Failed to create incident:", err);
    }
  }

  return (
    <aside className="flex flex-col h-full border-r border-gray-800">
      <div className="px-4 py-4 border-b border-gray-800 flex items-center justify-between gap-2">
        <h1 className="text-sm font-semibold text-gray-200 uppercase tracking-widest">
          Incidents
        </h1>
        <button
          onClick={handleTrigger}
          className="px-2 py-1 rounded bg-blue-700 hover:bg-blue-600 text-xs font-medium text-white transition-colors shrink-0"
        >
          + Trigger
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {loading && sorted.length === 0 && (
          <p className="text-xs text-gray-500 px-2 py-4 text-center">Loading…</p>
        )}
        {error && (
          <p className="text-xs text-red-400 px-2 py-2">{error}</p>
        )}
        {!loading && sorted.length === 0 && !error && (
          <p className="text-xs text-gray-500 px-2 py-4 text-center">
            No incidents yet. Click + Trigger to start one.
          </p>
        )}
        {sorted.map((record) => (
          <IncidentCard
            key={record.incident_id}
            record={record}
            active={record.incident_id === activeId}
            onClick={() => setActive(record.incident_id)}
          />
        ))}
      </div>
    </aside>
  );
}
