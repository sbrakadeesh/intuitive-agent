from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

from triage_agent.agent import nodes
from triage_agent.agent.constants import (
    INGEST_ALERT,
    FETCH_CONTEXT,
    ANALYZE_ROOT_CAUSE,
    PROPOSE_REMEDIATION,
    EXECUTE_REMEDIATION,
    VERIFY_RESOLUTION,
    END_REVIEW,
)
from triage_agent.agent.state import TriageState


ALL_NODES = [
    INGEST_ALERT,
    FETCH_CONTEXT,
    ANALYZE_ROOT_CAUSE,
    PROPOSE_REMEDIATION,
    EXECUTE_REMEDIATION,
    VERIFY_RESOLUTION,
    END_REVIEW,
]

def build_graph(checkpointer: AsyncSqliteSaver):
    """Build and compile the incident triage StateGraph.

    Graph flow:
        START
          - ingest_alert
          - fetch_context
          - analyze_root_cause
          - [error? -> END]
          - [INTERRUPT 1] operator reviews root cause
          - propose_remediation
          - [INTERRUPT 2] operator reviews remediation plan
          - execute_remediation
          - verify_resolution
          - [INTERRUPT 3] operator reviews verification result
          - end_review
          - END

    Three human-in-the-loop interrupts:
        1. Before propose_remediation  — operator confirms/corrects root cause
        2. Before execute_remediation  — operator approves/rejects/edits plan
        3. Before end_review           — operator closes or escalates incident
    """
    builder = StateGraph(TriageState)

    # Register nodes
    builder.add_node(INGEST_ALERT, nodes.ingest_alert)
    builder.add_node(FETCH_CONTEXT, nodes.fetch_context)
    builder.add_node(ANALYZE_ROOT_CAUSE, nodes.analyze_root_cause)
    builder.add_node(PROPOSE_REMEDIATION, nodes.propose_remediation)
    builder.add_node(EXECUTE_REMEDIATION, nodes.execute_remediation)
    builder.add_node(VERIFY_RESOLUTION, nodes.verify_resolution)
    builder.add_node(END_REVIEW, nodes.end_review)

    # Wire edges
    builder.set_entry_point(INGEST_ALERT)
    builder.add_edge(INGEST_ALERT, FETCH_CONTEXT)
    builder.add_edge(FETCH_CONTEXT, ANALYZE_ROOT_CAUSE)

    # After analysis: proceed or abort on LLM error
    builder.add_conditional_edges(
        ANALYZE_ROOT_CAUSE,
        nodes.route_after_analysis,
        {"continue": PROPOSE_REMEDIATION, "error": END},
    )

    builder.add_edge(PROPOSE_REMEDIATION, EXECUTE_REMEDIATION)
    builder.add_edge(EXECUTE_REMEDIATION, VERIFY_RESOLUTION)
    builder.add_edge(VERIFY_RESOLUTION, END_REVIEW)
    builder.add_edge(END_REVIEW, END)

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=[
            PROPOSE_REMEDIATION,   #  after root cause analysis
            EXECUTE_REMEDIATION,   #  after remediation proposal
            END_REVIEW,            #  after verification
        ],
    )
