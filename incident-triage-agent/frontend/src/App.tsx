import { useIncidentStore } from "./store/incidentStore";
import { IncidentList } from "./components/IncidentList/IncidentList";
import { TriageView } from "./components/TriageView/TriageView";

export default function App() {
  const activeId = useIncidentStore((s) => s.activeIncidentId);

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* Left sidebar */}
      <div className="w-80 shrink-0 h-full overflow-hidden">
        <IncidentList />
      </div>

      {/* Right pane */}
      <main className="flex-1 flex flex-col min-w-0 h-full">
        {activeId ? (
          <TriageView incidentId={activeId} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            Select an incident to begin triage
          </div>
        )}
      </main>
    </div>
  );
}
