"""Sample alert payloads for local development and manual testing."""
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


SAMPLE_ALERTS = [
    {
        "service":     "payment-service",
        "namespace":   "production",
        "pod_name":    "payment-service-7d9f6c8b4-xk9p2",
        "severity":    "critical",
        "title":       "OOMKilled: payment-service restarting repeatedly",
        "description": "payment-service has been OOMKilled 5 times in the last 10 minutes. "
                       "Memory usage peaked at 512Mi against a 512Mi limit.",
        "labels": {
            "team":        "payments",
            "env":         "production",
            "alert_name":  "OOMKillDetected",
            "k8s_cluster": "prod-us-east-1",
        },
        "started_at": _now(),
    },
    {
        "service":     "auth-service",
        "namespace":   "production",
        "pod_name":    "auth-service-6bf8d9c5f-m2pq7",
        "severity":    "critical",
        "title":       "CrashLoopBackOff: auth-service failing liveness probe",
        "description": "auth-service is in CrashLoopBackOff with 8 restarts. "
                       "Liveness probe returning 503; database connection errors observed in logs.",
        "labels": {
            "team":        "platform",
            "env":         "production",
            "alert_name":  "CrashLoopBackOff",
            "k8s_cluster": "prod-us-east-1",
        },
        "started_at": _now(),
    },
    {
        "service":     "recommendation-service",
        "namespace":   "staging",
        "pod_name":    "recommendation-service-5c7b4d6f9-zt3n8",
        "severity":    "warning",
        "title":       "High latency: recommendation-service p99 exceeds SLO",
        "description": "recommendation-service p99 latency is 3200ms, breaching the 500ms SLO. "
                       "Connection pool exhausted and circuit breaker is OPEN toward upstream.",
        "labels": {
            "team":        "discovery",
            "env":         "staging",
            "alert_name":  "HighP99Latency",
            "k8s_cluster": "staging-us-east-1",
        },
        "started_at": _now(),
    },
]
