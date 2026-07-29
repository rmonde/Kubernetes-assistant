# Session Notes — 2026-07-29
**Project:** Kubernetes Assistant — AKS-AI-Deployment-Roadmap, Phase 3 (CI/CD via Azure Pipelines)
**Status:** CD to staging (`dev` branch → `kubernetes-assistant-staging` namespace) — first fully green, fully verified run. Production (`master` branch) path designed but not yet tested.

---

## What Was Built / Fixed

`azure-pipelines.yml` went from "CI works, CD throws errors" to a verified end-to-end deploy: build → Trivy scan → push (tagged by commit SHA) → apply manifest → `kubectl set image` to the new tag → wait for the real rollout → confirmed via `/health` and `/ask` against the live pod.

## Bugs Found and Fixed, in Order

| # | Symptom | Root Cause | Fix |
|---|---|---|---|
| 1 | `line 2: resourceGroup: command not found` | `resourceGroup`/`aksClusterName` declared under `parameters:`, referenced with `$(resourceGroup)` (variable macro syntax). Parameters aren't substituted that way, so bash saw literal `$(resourceGroup)` and tried to execute it as a command substitution. | Reference via `${{ parameters.resourceGroup }}` (compile-time template expansion). |
| 2 | `the path ".../deployment-staging.yml" does not exist` | Script referenced `$(Build.SourcesDirectory)/deployment-staging.yml`, but the file lives in `k8s/deployment-staging.yml`. | Fixed the path. |
| 2b | Same error persisted after the path fix, even though a debug `ls -R` step proved the file existed | The `ls -R` step ran inside the `BuildAndScan` stage's plain `job:`, which auto-checks-out the repo. The failing `kubectl apply` ran inside `DeployToDev`'s `deployment:` job — **deployment jobs do not auto-checkout source**, unlike regular jobs. `$(Build.SourcesDirectory)` was effectively empty on that agent. | Added `- checkout: self` as the first step in both `DeployToDev` and `DeployToProd`'s `deploy: steps:`. |
| 3 | `localhost:8080... connection refused` | Symptom of bug #1 — `az aks get-credentials` never succeeded (missing required `-g` arg), so no kubeconfig context existed and kubectl fell back to its default. Resolved itself once #1 was fixed. | — |
| 4 | `kubelogin is not installed which is required to connect to AAD enabled cluster` | `aks-devopswithai` is Entra/AAD-enabled; `az aks get-credentials` writes a kubeconfig using interactive `devicecode` auth, which a headless CI agent can't complete, and the `kubelogin` binary (needed to convert that to non-interactive Azure-CLI-token auth) isn't preinstalled on `ubuntu-latest`. | Added `KubeloginInstaller@0` task, then `kubelogin convert-kubeconfig -l azurecli` before any `kubectl` call. |
| 5 | Pipeline went green, but `deployment.apps/k8s-assistant unchanged` — nothing actually deployed | `deployment-staging.yml`/`deployment.yml` had a hardcoded image tag (leftover Phase 2 commit SHA) that never changed between runs, so `kubectl apply` was a genuine no-op every time. | Added `kubectl set image deployment/k8s-assistant k8s-assistant=$(acrLoginServer)/$(imageRepository):$(Build.SourceVersion) -n <namespace>` after `kubectl apply`, so each run deploys the image it just built and pushed. Considered committing the new tag back into the manifest (GitOps-style) instead, but rejected it — would require the pipeline to hold git-write credentials and would re-trigger itself on every push (Azure Pipelines' `***NO_CI***` marker could suppress that, but it's solving a problem `kubectl set image` avoids needing to create). |
| 6 | Production stage: `kubectl set image ... -n $(dev-namespace)` | Copy-paste from the dev stage's block — the production deploy step was silently updating the **staging** namespace's deployment instead of prod's. No error thrown; would have shipped an unchanged image to prod indefinitely. | Corrected to `-n $(prod-namespace)`. |
| 7 | `rollout status` reported success/timing before the real change | Step order was `apply` → `rollout status` → `set image`. Since `apply` was a no-op (per #5), `rollout status` was confirming nothing meaningful, and the actual change (`set image`) ran after the wait — so a broken new image would never be caught by this check. | Reordered to `apply` → `set image` → `rollout status`, so the wait/verify step tracks the change that actually matters. |
| 8 | `rollout status` hung then failed: `deployment "k8s-assistant" exceeded its progress deadline` | Confirmed via `kubectl get events`: `FailedCreate ... forbidden: exceeded quota`. Staging's `ResourceQuota` (deliberately capped at `pods: 1`, from Phase 3's staging setup) collided with the default `RollingUpdate` strategy, which tries `maxSurge: 25%` (rounds up to 1 extra pod) before removing the old one — i.e. it wanted 2 pods running simultaneously against a quota of 1. | Set `strategy.type: Recreate` on `deployment-staging.yml` — acceptable since staging is an explicitly non-production-parity smoke-test environment where brief downtime during deploy is fine. **Deliberately not applied to production** (`deployment.yml`) — prod has no such quota constraint, so `RollingUpdate` with `maxUnavailable: 25%` (once replica count is realistically >1) can keep at least one pod serving throughout the rollout, which staging's Recreate strategy gives up. |

## Verified, Not Assumed

After the full fix set, a real pipeline run against `dev`:
- `kubectl get rs` showed the old ReplicaSet scale to 0 before the new one scaled up (Recreate behavior working as intended, no quota violation).
- New pod pulled `rag-app:<latest commit SHA>`, started, and `kubectl rollout status` returned `successfully rolled out` — this time confirming the real change.
- `kubectl port-forward svc/k8s-assistant-service 5000:5000 -n kubernetes-assistant-staging`, then:
  - `GET /health` → `200`, confirms the Flask process is alive (but doesn't touch Azure).
  - `POST /ask` with an out-of-knowledge-base question ("What is a Kubernetes pod?") → `{"answer": "I do not know."}` — initially looked like a failure, but this is the pipeline's own designed fallback (`04_rag_pipeline.py` system prompt) for retrieval that found nothing relevant, not an error. Absence of a 500 already proved all three Azure calls (embed, search, chat completion) succeeded end-to-end via Workload Identity.
  - `POST /ask` with a knowledge-base-matched question ("crashloopbackoff") → full grounded answer, confirming the RAG pipeline is genuinely working in the new pod, not just "up."

## Key Lesson Worth Naming

Several of today's bugs (#1, #6) were **silent** — no error at the point of the mistake, only a downstream symptom (bash trying to execute a variable name; prod quietly never getting updated). This is the same silent-failure shape already seen twice in this project around Workload Identity namespace/subject-string mismatches (Phase 2, Phase 3 staging setup) — worth treating "did this actually change what I think it changed" as a standing question, not just "did the pipeline go green."

## Also Fixed This Session

`Claude-output/` was in `.gitignore`, which is why the Phase 0–2 and Phase 3-staging session write-ups referenced from memory no longer exist on disk — gitignored files leave no git history to recover from if the folder is ever recreated. Removed `Claude-output/` from `.gitignore` so this file, and all future ones, get committed going forward.

## Still Open, Carried Forward

- Production (`master` branch) path is designed (`RollingUpdate` at higher replica count instead of `Recreate`) but not yet tested end-to-end.
- Staging's replica count is still 1 — the `Recreate` strategy sidesteps the quota collision but real elasticity/HA testing would need a higher replica count and a raised quota to match.
- `pytest`/`PublishTestResults`/`PublishCodeCoverageResults` stages remain commented out in `azure-pipelines.yml`.
- `FLASK_ENV`/`FLASK_DEBUG` question from Phase 1 still open.
