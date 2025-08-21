# Logging Stack (Loki + Promtail + Grafana)

This example lets you stand up a basic log pipeline for local/dev:

- Promtail tails host/docker logs and ships to Loki
- Loki stores and indexes logs
- Grafana queries Loki to visualize and filter logs

## Compose (local) quickstart

1) Start the logging stack

```bash
docker compose -f monitoring/docker-compose.logging.yml up -d
```

2) Configure Grafana Loki datasource (UI) or provisioning

- UI: Grafana -> Connections -> Data sources -> Add Loki
  - URL: http://loki:3100
- Or place a provisioning file under monitoring/grafana/provisioning/datasources

3) Explore logs

- Grafana -> Explore -> select Loki
- Example LogQL:
  - `{job="gas"}` (Docker container logs)
  - `{job="gas"} |= "ERROR"`
  - `{job="varlogs"} |~ ".*exception.*"`

## Kubernetes hints

- Use the official Loki Helm chart (grafana/loki-stack) or loki-distributed
- Use promtail as DaemonSet; add label selectors to capture app logs
- Add labels to app pods for better filtering (app, env, version)

## App structured logs (recommend)

- Log JSON lines and include fields such as:
  - level, msg, ts
  - endpoint, method, status, latency_ms
  - user_id, role
  - export_task_id, export_status
- Then use promtail json stage to parse fields for querying in Grafana

