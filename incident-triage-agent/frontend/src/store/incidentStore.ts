import { create } from "zustand";
import type { IncidentRecord, IncidentStatus } from "../types/incident";
import type { WSEvent } from "../types/events";

interface IncidentState {
  incidents: Record<string, IncidentRecord>;
  eventLog: Record<string, WSEvent[]>;
  activeIncidentId: string | null;

  // Actions
  setActive: (id: string | null) => void;
  upsertIncident: (record: IncidentRecord) => void;
  appendEvent: (incidentId: string, event: WSEvent) => void;
  applyEventPatch: (event: WSEvent) => void;
}

function patchedStatus(event: WSEvent): IncidentStatus | null {
  switch (event.event_type) {
    case "interrupt":
      return "awaiting_approval";
    case "complete": {
      const data = event.data as Record<string, unknown> | null | undefined;
      return (data?.status as IncidentStatus | undefined) ?? "completed";
    }
    case "error":
      return "failed";
    default:
      return null;
  }
}

export const useIncidentStore = create<IncidentState>((set) => ({
  incidents: {},
  eventLog: {},
  activeIncidentId: null,

  setActive: (id) => set({ activeIncidentId: id }),

  upsertIncident: (record) =>
    set((state) => ({
      incidents: { ...state.incidents, [record.incident_id]: record },
    })),

  appendEvent: (incidentId, event) =>
    set((state) => ({
      eventLog: {
        ...state.eventLog,
        [incidentId]: [...(state.eventLog[incidentId] ?? []), event],
      },
    })),

  applyEventPatch: (event) =>
    set((state) => {
      const incident = state.incidents[event.incident_id];
      if (!incident) return state;

      const patch: Partial<IncidentRecord> = {};

      if (event.event_type === "step_complete") {
        const data = event.data as Record<string, unknown> | null | undefined;
        if (data?.current_step && typeof data.current_step === "string") {
          patch.current_step = data.current_step;
        }
      }

      const status = patchedStatus(event);
      if (status !== null) {
        patch.status = status;
      }

      if (Object.keys(patch).length === 0) return state;

      return {
        incidents: {
          ...state.incidents,
          [event.incident_id]: { ...incident, ...patch },
        },
      };
    }),
}));
