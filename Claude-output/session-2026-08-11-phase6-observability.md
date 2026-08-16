# Session Notes — 2026-08-11 (Phase 6, Observability — verified end-to-end, then torn down for cost)

**Goal:** close the Phase 6 exit criteria — "a Grafana dashboard shows request/latency" — for the `kubernetes-assistant-staging` namespace on the shared `aks-devopswithai` cluster.

**Status: verified working end-to-end. Not left running** — dashboard/panels were built in Grafana Explore but deliberately not saved, and the underlying add-ons/cluster are being torn down same session to control cost. This file is the record needed to recreate everything from scratch next time.

---

## Starting state found (untracked from a prior session)

A commit from 2026-07-29 (`724837a`, same evening as the Phase 3 CD-debug session but not documented) had already added:
- `prometheus_client` instrumentation to `app.py`: `REQUEST_COUNT = Counter('ask_requests_total', ..., ['status'])` and `REQUEST_LATENCY = Histogram('ask_request_latency_seconds', ...)`, plus a `/metrics` route.
- `k8s/podmonitor-staging.yml` — a `PodMonitor` (`azmonitoring.coreos.com/v1`) targeting `app: k8s-assistant` on port 5000.

Neither had been verified as actually working before this session.

## Infra verification chain (all confirmed live via CLI, Rahul-driven)

1. `az aks show ... --query "azureMonitorProfile.metrics.enabled"` → `true` — managed Prometheus add-on confirmed on.
2. Metrics land in a separate resource type from Log Analytics: an **Azure Monitor Workspace (AMW)**, not the Log Analytics workspace used for container logs — found via `az resource list --resource-type "Microsoft.Monitor/accounts"` → `DefaultAzureMonitorWorkspace-westus2`, auto-created by Azure in its own `DefaultResourceGroup-westus2` (same pattern as AKS's node resource group — a managed dependency gets its own Azure-owned RG).
3. Azure Managed Grafana already existed (`grafana-k8s-assistant`, `rg-devopswithai`) and was already linked to that exact AMW — confirmed via `az grafana show --query "properties.grafanaIntegrations"`.
4. `/metrics` endpoint itself confirmed healthy via direct `curl` against the real AKS pod (not local) — valid Prometheus exposition format, both default process metrics and the custom `ask_requests_total`/`ask_request_latency_seconds` present.
5. PodMonitor spec confirmed correctly formed — label selector (`app: k8s-assistant`) and port (`5000`) both matched the Deployment exactly. No repeat of this project's usual exact-string-match bug class this time.

## The real bug: wrong collector pod, not a config problem

First check of `127.0.0.1:9090/targets` (after `kubectl port-forward` to an `ama-metrics` pod) showed **zero targets at all** — not even default ones. Nearly went down a wrong path chasing a `ama-metrics-settings-configmap` namespace-opt-in theory (flagged at ~65% confidence, and disproved by pulling actual Microsoft Learn docs — plain PodMonitor/ServiceMonitor scraping needs no such opt-in; that setting is only for basic-auth secrets access).

Real root cause: **Azure's managed-Prometheus add-on runs multiple pod types in `kube-system`, and only one of them handles custom PodMonitor/ServiceMonitor targets.**
- `ama-metrics-<hash>` (replica, 2 pods) — scrapes `kube-state-metrics` **and all custom PodMonitor/ServiceMonitor targets**. This is the one to port-forward to.
- `ama-metrics-node-*` (DaemonSet, one per node) — only `kubelet`/`cAdvisor`/`node-exporter` on its own node.
- `ama-metrics-ksm-*`, `ama-metrics-operator-targets-*` — kube-state-metrics itself and config/target-allocation, not where you check discovered targets.

First port-forward almost certainly hit a `-node-` or `-ksm-` pod. Re-forwarding to the actual `ama-metrics-<hash>-<hash>` replica pod immediately showed the PodMonitor job **1/1 up**.

**Diagnostic order that worked, worth reusing:** `/config` (is the job even in scrape config) → `/service-discovery` (was the target discovered pre-relabel) → `/targets` (actual scrape result) — jumping straight to `/targets` on the wrong pod produced a misleading "nothing works" signal.

Sources pulled for this (Microsoft Learn, current as of this session):
- [Create custom Prometheus scrape job using CRDs](https://learn.microsoft.com/en-us/azure/azure-monitor/containers/prometheus-metrics-scrape-crd)
- [Troubleshoot collection of Prometheus metrics](https://learn.microsoft.com/en-us/azure/azure-monitor/containers/prometheus-metrics-troubleshoot)

## Mental model correction: labeled vs. unlabeled metrics, not Counter vs. Histogram

`REQUEST_COUNT` (`Counter`, has a `['status']` label) showed **zero sample lines** on `/metrics` before any traffic — only `# HELP`/`# TYPE` comments. `REQUEST_LATENCY` (`Histogram`, no labels) showed full bucket/sum/count output at `0` immediately at pod startup, before any real request.

Initially mis-attributed this to "Counter vs. Histogram" as types. The actual mechanism in `prometheus_client`: an **unlabeled** metric (either type) is instantiated immediately with its zero-state exposed; a **labeled** metric doesn't materialize as a concrete series until `.labels(x).inc()`/`.observe()` is called for that specific label combination for the first time. It's coincidental in this code that Counter=labeled and Histogram=unlabeled — swap the label and the behavior would swap too.

Practical consequence: a `0` reading on an unlabeled metric is not evidence traffic occurred — it may just be the startup default. Confirmed real traffic separately by round-tripping actual `/ask` calls and watching the labeled counter's series count go from 0 → 2 (`status="200"`, `status="400"`).

## PromQL gotchas hit live

- `count(ask_requests_total{...})` returned `2` — **counts time series, not request volume.** With two status-label series, `count()` will always show `2` regardless of how many requests actually happened. `sum(ask_requests_total{...})` is the correct aggregation for total request volume across label values.
- Querying a raw Counter or `_sum` value directly is close to useless for dashboards — Counters only increase, and `_sum` alone (without `_count`) can't distinguish "many fast requests" from "few slow ones." Used `rate()` for the request-rate panel and `histogram_quantile()` over the `_bucket` series for latency, not the mean — same p95/tail-latency reasoning as the System Design track's SLA discussions, applied here in a real dashboard instead of a whiteboard answer.

## Final dashboard (built in Grafana Explore, verified, not persisted)

**Panel 1 — request rate by status:**
```promql
sum(rate(ask_requests_total{namespace="kubernetes-assistant-staging"}[5m])) by (status)
```
Result after 4 valid + 1 malformed (`{}` body, no `question` field) request: `status="200"` ≈ 0.0149 req/s, `status="400"` ≈ 0.0037 req/s.

**Panel 2 — p95 latency:**
```promql
histogram_quantile(0.95, sum(rate(ask_request_latency_seconds_bucket{namespace="kubernetes-assistant-staging"}[5m])) by (le))
```
Result: **4.75 seconds.**

## Real finding worth digging into next time

**p95 latency of 4.75s is slow for a user-facing endpoint.** Almost certainly the embed → AI Search → chat-completion chain in `04_rag_pipeline.py` running fully serially, each leg paying its own network round-trip plus (for the chat completion) real LLM generation time. Not investigated further this session — logged as a carried-forward item, not a mystery to re-discover from scratch.

## Why nothing was left running

Managed Prometheus ingestion bills continuously while the add-on is enabled and pods are scraped (independent of whether a dashboard is saved), and Azure Managed Grafana has its own resource-level cost. Given this is a shared cluster whose cost is already being actively managed via stop/start between sessions, decided to tear down this session's add-ons rather than leave them accumulating charges for an exercise that's already proven itself. Teardown scope (what specifically gets deleted vs. what's shared cluster-wide infra) handled as a separate step — see session's live conversation for the actual commands run.

## To recreate from scratch next time

1. Confirm `azureMonitorProfile.metrics.enabled` is still `true` (or re-enable — see teardown step for what was actually removed).
2. `kubectl apply -f k8s/podmonitor-staging.yml`.
3. Port-forward the **replica** `ama-metrics-<hash>` pod (not `-node-`/`-ksm-`), confirm `1/1 up` on `/targets`.
4. Send real `/ask` traffic (curl loop through `kubectl port-forward svc/k8s-assistant-service -n kubernetes-assistant-staging 5000:5000`).
5. Rebuild the two panels above in Grafana (`grafana-k8s-assistant`, already linked to the AMW — confirm that link is still intact first) and **save the dashboard this time** if keeping it running long-term is the goal.

## Carried forward / logged this session

- **Production (`master`) CD path** — designed in Phase 3, still never tested end-to-end. Next session should start here per the last roadmap update.
- **p95 4.75s latency** — real, unexplained-so-far finding on the RAG pipeline's serial call chain.
- **GitHub Actions CI/CD (Phase 4)** — explicit reminder requested, already a planned phase, re-flagged as a priority.
- **RAG evaluation harness + CI/CD gate** — new backlog item: write evaluations for retrieval/answer quality, wire into the pipeline as a gate before deploy.
- **Python unit tests for the RAG app** — new backlog item, also connects to the already-carried-forward "pytest/coverage-publish stages still commented out in `azure-pipelines.yml`" from the Phase 3 close-out session.
- **Spec-Driven Development (SDD) for writing those unit tests** — new backlog item: apply SDD methodology specifically to the unit-test-writing process above, rather than writing tests ad hoc.

Added as a new backlog section (not a strict numbered phase) in `AKS-AI-Deployment-Roadmap/04_Progress_Tracker.md`.
