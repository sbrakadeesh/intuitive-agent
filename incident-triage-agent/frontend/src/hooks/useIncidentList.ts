import { useCallback, useEffect, useRef, useState } from "react";
import { listIncidents } from "../api/incidents";
import { useIncidentStore } from "../store/incidentStore";

export function useIncidentList() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const upsertIncident = useIncidentStore((s) => s.upsertIncident);

  const fetchAll = useCallback(async () => {
    try {
      const records = await listIncidents();
      records.forEach(upsertIncident);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch incidents");
    } finally {
      setLoading(false);
    }
  }, [upsertIncident]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 5_000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  return { loading, error };
}
