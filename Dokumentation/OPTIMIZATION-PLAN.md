# Ragflow/Embedder System Optimization Plan

## TL;DR

> **Quick Summary**: Fix 502 Bad Gateway failures (4 of 21 docs failed) by implementing retry logic and optimizing Embedder/Ragflow config for stability and throughput.
>
> **Root Cause**: Embedder pods crashed at 22:24 UTC (health probe 403 → restart), causing 502 errors for 8 minutes. Ragflow had no retry logic, marking all concurrent tasks as FAILED.
>
> **Deliverables**:
> - Embedder config: NUM_STREAMS=4, PERFORMANCE_HINT=THROUGHPUT (stability + throughput)
> - Ragflow config: EMBEDDING_BATCH_SIZE=32, MAX_CONCURRENT_CHUNK_BUILDERS=2
> - Embedder health probe fix (prevent 403 → restart cycle)
> - Ragflow retry logic for embedding failures (exponential backoff)
> - Verified: 0 failed tasks on verification run
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Embedder config → Health probe fix → Ragflow config → Retry logic → Verify

---

## Context

### Original Request
"ja, bitte erarbeite ein kozept und einen plan um unser system perfekt auszubalancieren"

### Interview Summary
**Key Discussions**:
- User wants system perfectly balanced for embedding performance
- Batch job: 21 documents, 4 failed (olares_docs.txt, Miele WCR 860, Lüneburger Lakritznase, Leica-Q3)
- All failures caused by 502 Bad Gateway at 22:24-22:32 UTC (8 minutes)
- Embedder pods crashed due to health probe 403 → restart cycle
- Ragflow had NO retry logic – every task marked FAILED immediately on 502

**Research Findings**:
- Ragflow `MAX_CONCURRENT_CHUNK_BUILDERS=1` → only 1 doc parsed at a time
- Ragflow `EMBEDDING_BATCH_SIZE=16` → small batches, many roundtrips
- Embedder `NUM_STREAMS=1` → wastes 7 of 8 CPU cores per pod
- Embedder `PERFORMANCE_HINT=LATENCY` → wrong for batch workloads
- Embedder health probe returns 403 on `/health` (needs auth fix)
- Cluster has 2×24 CPU / 95GB RAM, currently ~50% underutilized
- Embedder code has NO batch size limit - can handle larger batches
- **Critical**: Ragflow `task_executor.py` has NO retry logic for embedding failures

### Metis Review
Metis timed out. Self-review applied with conservative defaults.

---

## Work Objectives

### Core Objective
Optimize Ragflow/Embedder pipeline for maximum throughput on existing hardware without adding new nodes.

### Concrete Deliverables
- Modified Embedder deployment with optimized OpenVINO config
- Modified Ragflow deployment with optimized concurrency settings
- Scaled Embedder to 3 replicas
- Performance verification report (before/after comparison)

### Definition of Done
- [ ] Embedding job completes 5x faster than baseline (4h → <48min)
- [ ] Zero failed tasks during verification run (was: 4 of 21 failed)
- [ ] Zero OOMKilled events on Embedder pods
- [ ] All pods healthy, no restarts
- [ ] Rollback plan documented and tested

### Must Have
- All changes via environment variables or kubectl (no code rebuilds where possible)
- Each change applied and verified individually (no big-bang deployment)
- Performance metrics captured before and after each change
- Embedder memory limit increased to prevent OOMKilled (24Gi minimum)

### Must NOT Have (Guardrails)
- NO changes to Embedder inference logic (server.py stays as-is)
- NO changes to Ragflow source code (only env vars)
- NO chunk size changes in this plan (separate decision, affects retrieval quality)
- NO Raptor/GraphRAG changes (separate decision, affects features)
- NO node additions or infrastructure changes
- NO Embedder replica scaling (current 2 replicas are sufficient – Embedder is NOT the bottleneck)

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO (no test framework for this infra change)
- **Automated tests**: None
- **Framework**: N/A
- **Agent-Executed QA**: ALWAYS (mandatory for all tasks)

### QA Policy
Every task MUST include agent-executed QA scenarios:
- **Deployment changes**: kubectl verify pod status, env vars, resource allocation
- **Performance**: Monitor heartbeats, set_progress rates, compare before/after
- **Stability**: Check for pod restarts, error logs, failed tasks

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - baseline + Embedder config):
├── Task 1: Capture baseline metrics [quick]
├── Task 2: Update Embedder env vars (NUM_STREAMS, THROUGHPUT) [quick]
├── Task 3: Increase Embedder memory limit (16Gi → 24Gi) [quick]
├── Task 4: Fix Embedder health probe config (prevent restarts) [quick]
└── Task 5: Verify Embedder deployment [quick]

Wave 2 (After Wave 1 - Ragflow config + retry logic):
├── Task 6: Update Ragflow env vars (BATCH_SIZE, CHUNK_BUILDERS) [quick]
├── Task 7: Implement retry logic in task_executor.py [deep]
├── Task 8: Verify Ragflow deployment [quick]
└── Task 9: Run verification embedding job [deep]

Wave 3 (After Wave 2 - validation + documentation):
├── Task 10: Compare before/after metrics [quick]
├── Task 11: Document rollback procedures [quick]
└── Task 12: Final stability check [quick]

Wave FINAL (After ALL tasks — 2 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
└── Task F2: Manual QA verification (unspecified-high)
-> Present results -> Get explicit user okay

Critical Path: Task 1 → Task 2 → Task 3 → Task 6 → Task 7 → Task 9 → Task 10
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix

- **1**: - → 2, 9, 10
- **2**: 1 → 3, 6
- **3**: 2 → 4
- **4**: 3 → 5
- **5**: 4 → 6
- **6**: 5 → 7, 8
- **7**: 6 → 9
- **8**: 6 → 9
- **9**: 7, 8 → 10
- **10**: 1, 9 → 11, 12
- **11**: 10 → F1, F2
- **12**: 10 → F1, F2

### Agent Dispatch Summary

- **Wave 1**: **5** - T1 → `quick`, T2 → `quick`, T3 → `quick`, T4 → `quick`, T5 → `quick`
- **Wave 2**: **4** - T6 → `quick`, T7 → `deep`, T8 → `quick`, T9 → `deep`
- **Wave 3**: **3** - T10 → `quick`, T11 → `quick`, T12 → `quick`
- **FINAL**: **2** - F1 → `oracle`, F2 → `unspecified-high`

---

## TODOs

- [ ] 1. Capture Baseline Metrics

  **What to do**:
  - SSH to olares cluster
  - Record current deployment state: replicas, resource limits, env vars
  - Capture current embedding job progress rate (set_progress frequency)
  - Record Embedder request rate (requests/min from logs)
  - Save baseline to `.sisyphus/evidence/baseline-metrics.md`

  **Must NOT do**:
  - Make any changes to the system
  - Restart any pods

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple data collection via SSH/kubectl commands
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `git-master`: No git operations needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 8 (needs baseline for comparison)
  - **Blocked By**: None

  **References**:
  - Current Embedder pods: `kubectl get pods -n embedding-aimighty`
  - Current Ragflow pod: `kubectl get pods -n ragflow-aimighty`
  - Embedder logs: `kubectl logs -n embedding-aimighty -l app=embedding --tail=100`
  - Ragflow logs: `kubectl logs -n ragflow-aimighty ragflow-5cbcdff88b-lsm9k --tail=100`
  - Deployment configs: `kubectl get deployment -n embedding-aimighty -o yaml`, `kubectl get deployment -n ragflow-aimighty -o yaml`

  **Acceptance Criteria**:
  - [ ] Baseline file created at `.sisyphus/evidence/baseline-metrics.md`
  - [ ] Contains: replica count, resource limits, env vars for both Embedder and Ragflow
  - [ ] Contains: current embedding progress rate (set_progress events per minute)
  - [ ] Contains: Embedder request rate (POST /v1/embeddings per minute)

  **QA Scenarios**:

  ```
  Scenario: Baseline file exists and has required sections
    Tool: Bash
    Preconditions: SSH connection to olares@172.20.0.4
    Steps:
      1. Test -f .sisyphus/evidence/baseline-metrics.md && echo "EXISTS" || echo "MISSING"
      2. grep -c "Replica Count\|Resource Limits\|Environment Variables\|Progress Rate\|Request Rate" .sisyphus/evidence/baseline-metrics.md
    Expected Result: File exists, grep returns >= 5 matches
    Evidence: .sisyphus/evidence/task-1-baseline-file-check.txt
  ```

  **Commit**: NO (part of Wave 1 group)

- [ ] 2. Update Embedder Environment Variables

  **What to do**:
  - Patch Embedder deployment to set optimized env vars:
    - `NUM_STREAMS`: "4" (from "1" – uses 4 of 8 CPU cores for parallel inference)
    - `PERFORMANCE_HINT`: "THROUGHPUT" (from "LATENCY" – optimized for batch processing)
  - Use `kubectl set env` or `kubectl patch` to update deployment
  - Verify rolling update completes successfully

  **Must NOT do**:
  - Modify server.py source code
  - Change MODEL_DIR, MODEL_NAME, or PORT
  - Change resource limits (CPU/RAM)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single kubectl patch command with verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 1)
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Task 3, Task 4
  - **Blocked By**: Task 1 (baseline must be captured first)

  **References**:
  - Embedder deployment: `kubectl get deployment -n embedding-aimighty embedding -o yaml`
  - Current env vars: `kubectl exec -n embedding-aimighty embedding-7f9b4cc86b-kqttp -- env | grep -E 'NUM_STREAMS|PERFORMANCE_HINT'`
  - server.py lines 22-25: env var defaults for NUM_STREAMS, PERFORMANCE_HINT
  - OpenVINO docs: https://docs.openvino.ai/2024/performance-tuning.html (NUM_STREAMS=AUTO recommended for CPU)

  **Acceptance Criteria**:
  - [ ] `kubectl get deployment -n embedding-aimighty embedding -o jsonpath='{.spec.template.spec.containers[0].env}'` shows NUM_STREAMS=4 and PERFORMANCE_HINT=THROUGHPUT
  - [ ] All Embedder pods restarted and Running
  - [ ] Embedder health endpoint returns 200 OK

  **QA Scenarios**:

  ```
  Scenario: Embedder env vars updated correctly
    Tool: Bash (SSH)
    Preconditions: SSH to olares@172.20.0.4, Task 2 changes applied
    Steps:
      1. ssh olares@172.20.0.4 "kubectl get deployment -n embedding-aimighty embedding -o jsonpath='{range .spec.template.spec.containers[0].env[*]}{.name}={.value}{"\n"}{end}'" | grep -E 'NUM_STREAMS|PERFORMANCE_HINT'
    Expected Result: Output shows "NUM_STREAMS=4" and "PERFORMANCE_HINT=THROUGHPUT"
    Evidence: .sisyphus/evidence/task-2-env-vars-check.txt

  Scenario: Embedder pods healthy after rolling update
    Tool: Bash (SSH)
    Preconditions: Rolling update completed
    Steps:
      1. ssh olares@172.20.0.4 "kubectl get pods -n embedding-aimighty -l app=embedding"
      2. ssh olares@172.20.0.4 "kubectl rollout status deployment/embedding -n embedding-aimighty --timeout=120s"
    Expected Result: All pods show "Running" status, rollout status returns success
    Evidence: .sisyphus/evidence/task-2-pod-health.txt

  Scenario: Embedder health endpoint responds
    Tool: Bash (SSH)
    Preconditions: Embedder pods running
    Steps:
      1. ssh olares@172.20.0.4 "kubectl exec -n embedding-aimighty $(kubectl get pods -n embedding-aimighty -l app=embedding -o jsonpath='{.items[0].metadata.name}') -- curl -s http://localhost:9997/health"
    Expected Result: Response contains "ready" and returns HTTP 200
    Evidence: .sisyphus/evidence/task-2-health-check.txt
  ```

  **Commit**: NO (part of Wave 1 group)

- [ ] 3. Increase Embedder Memory Limit (CRITICAL - OOMKilled Fix)

  **What to do**:
  - **Root Cause**: Both Embedder pods were OOMKilled (Exit Code 137) at 22:24 UTC
  - **Why**: Qwen3-Embedding-4B INT8 model needs ~4.5GB base + 2-4GB inference buffers + KV cache
  - **Peak memory**: Can exceed 16GB with large batches (16 chunks × up to 8192 tokens)
  - **Current limit**: 16Gi (too low for peak usage)
  - **New limit**: 24Gi (50% headroom above estimated peak)
  - Patch the Embedder deployment:
    - `kubectl set resources deployment/embedding -n embedding-aimighty -c embedder --limits=memory=24Gi --requests=memory=12Gi`
  - Verify rolling update completes successfully
  - Monitor memory usage during verification job

  **Must NOT do**:
  - Set limit below 20Gi (still risky)
  - Change CPU limits
  - Modify server.py source code

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single kubectl command with verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 3)
  - **Parallel Group**: Wave 1 (sequential within wave)
  - **Blocks**: Task 5
  - **Blocked By**: Task 3

  **References**:
  - Current limits: `kubectl get deployment -n embedding-aimighty embedding -o jsonpath='{.spec.template.spec.containers[0].resources}'`
  - Model size: 3.8GB on disk, ~4.5GB in RAM (INT8)
  - KV cache: 144KB per token, up to 18GB for worst-case batch
  - OOMKilled evidence: `kubectl get pods -n embedding-aimighty -o json | grep -A5 OOMKilled`

  **Acceptance Criteria**:
  - [ ] Memory limit set to 24Gi, request set to 12Gi
  - [ ] All Embedder pods restarted and Running
  - [ ] No OOMKilled events during verification job

  **QA Scenarios**:

  ```
  Scenario: Memory limits updated correctly
    Tool: Bash (SSH)
    Preconditions: SSH to olares@172.20.0.4, Task 3 changes applied
    Steps:
      1. ssh olares@172.20.0.4 "kubectl get deployment -n embedding-aimighty embedding -o jsonpath='{.spec.template.spec.containers[0].resources}'"
    Expected Result: Output shows limits.memory=24Gi, requests.memory=12Gi
    Evidence: .sisyphus/evidence/task-3-memory-limits.txt

  Scenario: Embedder pods healthy after memory increase
    Tool: Bash (SSH)
    Preconditions: Rolling update completed
    Steps:
      1. ssh olares@172.20.0.4 "kubectl get pods -n embedding-aimighty -l app=embedding"
      2. ssh olares@172.20.0.4 "kubectl rollout status deployment/embedding -n embedding-aimighty --timeout=120s"
    Expected Result: All pods show "Running" status, rollout status returns success
    Evidence: .sisyphus/evidence/task-3-pod-health.txt
  ```

  **Commit**: NO (part of Wave 1 group)

- [ ] 4. Fix Embedder Health Probe Configuration

  **What to do**:
  - The Embedder's `/health` endpoint was returning 403, causing Kubernetes to restart pods
  - Patch the Embedder deployment's liveness/readiness probes:
    - Increase `failureThreshold` from 3 to 10 (tolerate more failures before restart)
    - Increase `periodSeconds` from 10 to 30 (less frequent checks)
    - Increase `initialDelaySeconds` from 5 to 60 (give model more time to load)
  - Use `kubectl patch` to update the deployment probe config
  - Verify rolling update completes successfully

  **Must NOT do**:
  - Modify server.py source code
  - Change the `/health` endpoint implementation
  - Change resource limits (CPU/RAM)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: kubectl patch command with verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 2)
  - **Parallel Group**: Wave 1 (sequential within wave)
  - **Blocks**: Task 4
  - **Blocked By**: Task 2

  **References**:
  - Current probe config: `kubectl get deployment -n embedding-aimighty embedding -o jsonpath='{.spec.template.spec.containers[0].livenessProbe}'`
  - server.py `/health` endpoint: returns `{"status": "ready"}` with 200 OK
  - Olares sidecar may intercept probes – check envoy config if 403 persists

  **Acceptance Criteria**:
  - [ ] Liveness probe: failureThreshold=10, periodSeconds=30, initialDelaySeconds=60
  - [ ] Readiness probe: failureThreshold=10, periodSeconds=30, initialDelaySeconds=60
  - [ ] All Embedder pods Running with no restarts
  - [ ] Health endpoint returns 200 OK consistently for 5 minutes

  **QA Scenarios**:

  ```
  Scenario: Health probes updated correctly
    Tool: Bash (SSH)
    Preconditions: SSH to olares@172.20.0.4, Task 3 changes applied
    Steps:
      1. ssh olares@172.20.0.4 "kubectl get deployment -n embedding-aimighty embedding -o jsonpath='{.spec.template.spec.containers[0].livenessProbe}' | python3 -m json.tool"
    Expected Result: Output shows failureThreshold=10, periodSeconds=30, initialDelaySeconds=60
    Evidence: .sisyphus/evidence/task-3-probe-config.txt

  Scenario: Health endpoint stable for 5 minutes
    Tool: Bash (SSH)
    Preconditions: Embedder pods running with new probe config
    Steps:
      1. ssh olares@172.20.0.4 "for i in \$(seq 1 10); do kubectl exec -n embedding-aimighty \$(kubectl get pods -n embedding-aimighty -l app=embedding -o jsonpath='{.items[0].metadata.name}') -- curl -s -o /dev/null -w '%{http_code}' http://localhost:9997/health; echo; sleep 30; done"
    Expected Result: All 10 checks return HTTP 200
    Evidence: .sisyphus/evidence/task-3-health-stability.txt
  ```

  **Commit**: NO (part of Wave 1 group)

- [ ] 4. Verify Embedder Performance After Config Changes

  **What to do**:
  - Wait for rolling update to complete
  - Check Embedder logs for successful model load with new config
  - Send test embedding request to verify inference works with NUM_STREAMS=4
  - Measure single-batch inference time (compare to baseline if available)

  **Must NOT do**:
  - Start a full embedding job yet (that's Task 6)
  - Modify any configs

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Verification via logs and single test request
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 2)
  - **Parallel Group**: Wave 1 (sequential within wave)
  - **Blocks**: Task 4
  - **Blocked By**: Task 2

  **References**:
  - Embedder logs: `kubectl logs -n embedding-aimighty -l app=embedding --tail=50`
  - Test request: `curl -X POST http://localhost:9997/v1/embeddings -H 'Content-Type: application/json' -d '{"input": ["test text 1", "test text 2"], "model": "aimighty-embedding-4b"}'`
  - server.py lines 30-35: _build_ov_config() function

  **Acceptance Criteria**:
  - [ ] Embedder logs show model loaded successfully with new config
  - [ ] Test embedding request returns 200 with valid embeddings
  - [ ] No errors in Embedder logs

  **QA Scenarios**:

  ```
  Scenario: Embedder loads with new OpenVINO config
    Tool: Bash (SSH)
    Preconditions: Embedder pods restarted with new env vars
    Steps:
      1. ssh olares@172.20.0.4 "kubectl logs -n embedding-aimighty -l app=embedding --tail=50 | grep -E 'OpenVINO config|NUM_STREAMS|PERFORMANCE_HINT|Model loaded'"
    Expected Result: Logs show config with NUM_STREAMS=4 and PERFORMANCE_HINT=THROUGHPUT, and "Model loaded" message
    Evidence: .sisyphus/evidence/task-4-config-load.txt

  Scenario: Test embedding request succeeds
    Tool: Bash (SSH)
    Preconditions: Embedder pods ready
    Steps:
      1. ssh olares@172.20.0.4 "kubectl exec -n embedding-aimighty $(kubectl get pods -n embedding-aimighty -l app=embedding -o jsonpath='{.items[0].metadata.name}') -- curl -s -w '\nHTTP_CODE:%{http_code}\nTIME:%{time_total}s\n' -X POST http://localhost:9997/v1/embeddings -H 'Content-Type: application/json' -d '{\"input\": [\"test text 1\", \"test text 2\", \"test text 3\"], \"model\": \"aimighty-embedding-4b\"}'"
    Expected Result: HTTP_CODE:200, response contains "embedding" array with 3 items, TIME recorded
    Evidence: .sisyphus/evidence/task-4-test-embedding.txt
  ```

  **Commit**: NO (part of Wave 1 group)

- [ ] 5. Update Ragflow Environment Variables

  **What to do**:
  - Patch Ragflow deployment to set optimized env vars:
    - `EMBEDDING_BATCH_SIZE`: "32" (from "16" – doubles batch size, halves roundtrips)
    - `MAX_CONCURRENT_CHUNK_BUILDERS`: "2" (from "1" – allows 2 docs to parse simultaneously)
  - Use `kubectl set env` to update deployment
  - Verify rolling update completes successfully

  **Must NOT do**:
  - Modify task_executor.py source code
  - Change MAX_CONCURRENT_TASKS (already at 5, sufficient)
  - Change MAX_CONCURRENT_MINIO (already at 10, sufficient)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: kubectl set env command with verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 4)
  - **Parallel Group**: Wave 2 (with Tasks 6, 7)
  - **Blocks**: Task 6, Task 7
  - **Blocked By**: Task 4

  **References**:
  - Ragflow deployment: `kubectl get deployment -n ragflow-aimighty ragflow -o yaml`
  - Current env vars: `kubectl exec -n ragflow-aimighty ragflow-5cbcdff88b-lsm9k -- env | grep -E 'EMBEDDING_BATCH_SIZE|MAX_CONCURRENT'`
  - task_executor.py line 335: `EMBEDDING_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", 16))`
  - task_executor.py line 116: `MAX_CONCURRENT_CHUNK_BUILDERS = int(os.environ.get('MAX_CONCURRENT_CHUNK_BUILDERS', "1"))`

  **Acceptance Criteria**:
  - [ ] `kubectl get deployment -n ragflow-aimighty ragflow -o jsonpath='{.spec.template.spec.containers[0].env}'` shows EMBEDDING_BATCH_SIZE=32 and MAX_CONCURRENT_CHUNK_BUILDERS=2
  - [ ] Ragflow pod restarted and Running
  - [ ] No errors in Ragflow logs after restart

  **QA Scenarios**:

  ```
  Scenario: Ragflow env vars updated correctly
    Tool: Bash (SSH)
    Preconditions: SSH to olares@172.20.0.4, Task 5 changes applied
    Steps:
      1. ssh olares@172.20.0.4 "kubectl get deployment -n ragflow-aimighty ragflow -o jsonpath='{range .spec.template.spec.containers[0].env[*]}{.name}={.value}{"\n"}{end}'" | grep -E 'EMBEDDING_BATCH_SIZE|MAX_CONCURRENT_CHUNK_BUILDERS'
    Expected Result: Output shows "EMBEDDING_BATCH_SIZE=32" and "MAX_CONCURRENT_CHUNK_BUILDERS=2"
    Evidence: .sisyphus/evidence/task-5-env-vars-check.txt

  Scenario: Ragflow pod healthy after restart
    Tool: Bash (SSH)
    Preconditions: Rolling update completed
    Steps:
      1. ssh olares@172.20.0.4 "kubectl get pods -n ragflow-aimighty"
      2. ssh olares@172.20.0.4 "kubectl logs -n ragflow-aimighty $(kubectl get pods -n ragflow-aimighty -o jsonpath='{.items[0].metadata.name}') --tail=20 | grep -i error"
    Expected Result: Pod shows "Running", no errors in recent logs
    Evidence: .sisyphus/evidence/task-5-pod-health.txt
  ```

  **Commit**: NO (part of Wave 2 group)

- [ ] 6. Implement Retry Logic in Ragflow task_executor.py

  **What to do**:
  - Add retry logic with exponential backoff to the `embedding()` function in `task_executor.py`
  - Target: Lines 546-600 (`async def embedding()`) and lines 656-668 (batch embedding loop)
  - Implementation:
    ```python
    import asyncio
    MAX_EMBEDDING_RETRIES = 3
    EMBEDDING_RETRY_DELAY = 5  # seconds, doubles each retry (5, 10, 20)

    async def embedding_with_retry(docs, mdl, parser_config=None, callback=None):
        for attempt in range(MAX_EMBEDDING_RETRIES + 1):
            try:
                return await embedding(docs, mdl, parser_config, callback)
            except Exception as e:
                error_msg = str(e).lower()
                if any(kw in error_msg for kw in ['502', 'bad gateway', 'connection reset', 'connection termination', 'upstream']):
                    if attempt < MAX_EMBEDDING_RETRIES:
                        delay = EMBEDDING_RETRY_DELAY * (2 ** attempt)
                        logging.warning(f"Embedding failed (attempt {attempt+1}/{MAX_EMBEDDING_RETRIES+1}), retrying in {delay}s: {e}")
                        await asyncio.sleep(delay)
                    else:
                        logging.error(f"Embedding failed after {MAX_EMBEDDING_RETRIES+1} attempts: {e}")
                        raise
                else:
                    raise  # Non-retryable error
    ```
  - Apply same retry pattern to `run_dataflow()` function (lines 656-668)
  - This is a CODE CHANGE – requires editing the file inside the pod or rebuilding the image

  **Must NOT do**:
  - Change the core embedding logic
  - Change batch size calculation
  - Add infinite retries (max 3)
  - Retry on non-transient errors (e.g., model errors, invalid input)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requires understanding of Ragflow's async embedding flow, error handling patterns, and careful code modification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 5)
  - **Parallel Group**: Wave 2 (sequential within wave)
  - **Blocks**: Task 7, Task 8
  - **Blocked By**: Task 5

  **References**:
  - `task_executor.py` line 546: `async def embedding()` – main embedding function
  - `task_executor.py` line 572-574: batch embedding loop with `settings.EMBEDDING_BATCH_SIZE`
  - `task_executor.py` line 656-668: `run_dataflow()` embedding section
  - `task_executor.py` line 115-122: concurrency limiter setup (semaphores)
  - server.py lines 155-170: Embedder's `/v1/embeddings` endpoint with 300s timeout

  **Acceptance Criteria**:
  - [ ] Retry logic wraps both `embedding()` and `run_dataflow()` embedding calls
  - [ ] Max 3 retries with exponential backoff (5s, 10s, 20s)
  - [ ] Only retries on transient errors (502, connection reset, connection termination)
  - [ ] Non-transient errors (model errors, invalid input) are NOT retried
  - [ ] Retry attempts logged with warning level
  - [ ] Final failure logged with error level after all retries exhausted

  **QA Scenarios**:

  ```
  Scenario: Retry logic handles 502 error correctly
    Tool: Bash (SSH)
    Preconditions: Retry logic implemented, Ragflow pod running
    Steps:
      1. ssh olares@172.20.0.4 "kubectl exec -n ragflow-aimighty ragflow-<pod> -c ragflow -- grep -A20 'embedding_with_retry\|MAX_EMBEDDING_RETRIES' /ragflow/rag/svr/task_executor.py"
    Expected Result: Code shows retry wrapper with MAX_EMBEDDING_RETRIES=3 and exponential backoff
    Evidence: .sisyphus/evidence/task-6-retry-code-check.txt

  Scenario: Retry logic does not retry on non-transient errors
    Tool: Bash (SSH)
    Preconditions: Retry logic implemented
    Steps:
      1. ssh olares@172.20.0.4 "kubectl exec -n ragflow-aimighty ragflow-<pod> -c ragflow -- grep -B5 -A10 'Non-retryable\|raise$' /ragflow/rag/svr/task_executor.py"
    Expected Result: Code shows that non-transient errors are raised immediately without retry
    Evidence: .sisyphus/evidence/task-6-non-retryable-check.txt
  ```

  **Commit**: NO (part of Wave 2 group)

- [ ] 7. Verify Ragflow Task Executor Configuration

  **What to do**:
  - Check Ragflow logs to confirm new settings are active
  - Verify task executor picks up new EMBEDDING_BATCH_SIZE and MAX_CONCURRENT_CHUNK_BUILDERS
  - Confirm no startup errors related to new config values or retry logic

  **Must NOT do**:
  - Start embedding job yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Log verification only
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 6)
  - **Parallel Group**: Wave 2 (sequential within wave)
  - **Blocks**: Task 8
  - **Blocked By**: Task 6

  **References**:
  - Ragflow logs: `kubectl logs -n ragflow-aimighty ragflow-<pod> --tail=100`
  - task_executor.py lines 115-117: env var parsing for concurrency settings
  - settings.py line 335: EMBEDDING_BATCH_SIZE default
  - task_executor.py retry logic: MAX_EMBEDDING_RETRIES, EMBEDDING_RETRY_DELAY

  **Acceptance Criteria**:
  - [ ] Ragflow logs show no errors after restart
  - [ ] Task executor heartbeat shows correct configuration
  - [ ] Retry logic code is present in task_executor.py

  **QA Scenarios**:

  ```
  Scenario: Ragflow task executor starts without errors
    Tool: Bash (SSH)
    Preconditions: Ragflow pod restarted with new env vars and retry logic
    Steps:
      1. ssh olares@172.20.0.4 "kubectl logs -n ragflow-aimighty $(kubectl get pods -n ragflow-aimighty -o jsonpath='{.items[0].metadata.name}') --tail=100 | grep -iE 'error|exception|fail'"
    Expected Result: No error/exception/fail messages in logs
    Evidence: .sisyphus/evidence/task-7-error-check.txt
  ```

  **Commit**: NO (part of Wave 2 group)

- [ ] 8. Run Verification Embedding Job

  **What to do**:
  - Trigger a new embedding job in Ragflow with the same documents (or a representative subset)
  - Monitor progress via heartbeats and set_progress logs
  - Capture metrics: total time, set_progress rate, Embedder request rate
  - Compare to baseline metrics from Task 1
  - Specifically verify: 0 failed tasks (retry logic should handle transient errors)

  **Must NOT do**:
  - Change any configs during the job
  - Restart any pods during the job

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requires sustained monitoring, metric collection, and analysis over time
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 6 and 7)
  - **Parallel Group**: Wave 2 (sequential)
  - **Blocks**: Task 9
  - **Blocked By**: Task 6, Task 7

  **References**:
  - Baseline metrics: `.sisyphus/evidence/baseline-metrics.md`
  - Monitoring commands: `kubectl logs -n ragflow-aimighty <pod> --tail=5 | grep -oP 'done=\d+.*?pending=\d+.*?failed=\d+.*?lag=\d+s'`
  - Progress tracking: `kubectl logs -n ragflow-aimighty <pod> --since=1m | grep set_progress | wc -l`

  **Acceptance Criteria**:
  - [ ] Embedding job completes with 0 failed tasks
  - [ ] Total completion time recorded
  - [ ] set_progress rate measured (events per minute)
  - [ ] Results saved to `.sisyphus/evidence/verification-job-metrics.md`

  **QA Scenarios**:

  ```
  Scenario: Verification job completes successfully
    Tool: Bash (SSH)
    Preconditions: Embedding job triggered in Ragflow UI
    Steps:
      1. Monitor heartbeat every 60s: ssh olares@172.20.0.4 "kubectl logs -n ragflow-aimighty $(kubectl get pods -n ragflow-aimighty -o jsonpath='{.items[0].metadata.name}') --tail=5 2>/dev/null | grep -oP 'done=\d+.*?pending=\d+.*?failed=\d+'"
      2. Continue until pending=0
      3. Record final done/failed counts and timestamps
    Expected Result: pending=0, failed=0, done=N (all documents)
    Evidence: .sisyphus/evidence/task-8-job-completion.txt

  Scenario: Retry logic handles transient errors
    Tool: Bash (SSH)
    Preconditions: Job completed
    Steps:
      1. ssh olares@172.20.0.4 "kubectl logs -n ragflow-aimighty $(kubectl get pods -n ragflow-aimighty -o jsonpath='{.items[0].metadata.name}') --tail=500 | grep -iE 'retry|502|connection reset|embedding failed'"
    Expected Result: If any 502/connection errors occurred, they should be followed by retry success messages
    Evidence: .sisyphus/evidence/task-8-retry-verification.txt
  ```

  **Commit**: NO (part of Wave 2 group)

- [ ] 9. Compare Before/After Metrics

  **What to do**:
  - Read baseline metrics (Task 1) and verification metrics (Task 8)
  - Create comparison report with:
    - Embedding batch size: 16 → 32
    - NUM_STREAMS: 1 → 4
    - PERFORMANCE_HINT: LATENCY → THROUGHPUT
    - Health probe config: default → resilient (failureThreshold=10)
    - MAX_CONCURRENT_CHUNK_BUILDERS: 1 → 2
    - Retry logic: none → 3 retries with exponential backoff
    - Total job time: X → Y
    - Failed tasks: 4 → 0
    - Speedup factor: Zx
  - Save to `.sisyphus/evidence/performance-report.md`

  **Must NOT do**:
  - Make any system changes

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Data analysis and report generation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Tasks 1 and 8)
  - **Parallel Group**: Wave 3 (with Tasks 10, 11)
  - **Blocks**: Task 10, Task 11
  - **Blocked By**: Task 1, Task 8

  **References**:
  - Baseline: `.sisyphus/evidence/baseline-metrics.md`
  - Verification: `.sisyphus/evidence/verification-job-metrics.md`

  **Acceptance Criteria**:
  - [ ] Performance report created at `.sisyphus/evidence/performance-report.md`
  - [ ] Contains before/after comparison for all config changes
  - [ ] Contains speedup factor calculation
  - [ ] Contains failed task count (before: 4, after: 0)

  **QA Scenarios**:

  ```
  Scenario: Performance report exists with required sections
    Tool: Bash
    Preconditions: Task 9 completed
    Steps:
      1. Test -f .sisyphus/evidence/performance-report.md && echo "EXISTS" || echo "MISSING"
      2. grep -c "Before\|After\|Speedup\|NUM_STREAMS\|BATCH_SIZE\|Retry\|Failed" .sisyphus/evidence/performance-report.md
    Expected Result: File exists, grep returns >= 7 matches
    Evidence: .sisyphus/evidence/task-9-report-check.txt
  ```
  Scenario: Performance report exists with required sections
    Tool: Bash
    Preconditions: Task 8 completed
    Steps:
      1. Test -f .sisyphus/evidence/performance-report.md && echo "EXISTS" || echo "MISSING"
      2. grep -c "Before\|After\|Speedup\|NUM_STREAMS\|BATCH_SIZE\|Replicas" .sisyphus/evidence/performance-report.md
    Expected Result: File exists, grep returns >= 6 matches
    Evidence: .sisyphus/evidence/task-8-report-check.txt
  ```

  **Commit**: NO (part of Wave 3 group)

- [ ] 10. Document Rollback Procedures

  **What to do**:
  - Create rollback commands for each change:
    - Embedder env vars: `kubectl set env deployment/embedding NUM_STREAMS=1 PERFORMANCE_HINT=LATENCY -n embedding-aimighty`
    - Embedder health probes: `kubectl patch deployment embedding -n embedding-aimighty --type=json -p='[{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe","value":{...}}]'`
    - Ragflow env vars: `kubectl set env deployment/ragflow EMBEDDING_BATCH_SIZE=16 MAX_CONCURRENT_CHUNK_BUILDERS=1 -n ragflow-aimighty`
    - Ragflow retry logic: Revert task_executor.py to original (no retry wrapper)
  - Save to `.sisyphus/evidence/rollback-procedures.md`

  **Must NOT do**:
  - Execute rollback commands (only document them)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Documentation task
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 9)
  - **Parallel Group**: Wave 3 (with Tasks 9, 11)
  - **Blocks**: None
  - **Blocked By**: Task 9

  **References**:
  - Current deployment names: `kubectl get deployment -n embedding-aimighty`, `kubectl get deployment -n ragflow-aimighty`
  - Original values from baseline: `.sisyphus/evidence/baseline-metrics.md`
  - Original task_executor.py: git history or backup copy

  **Acceptance Criteria**:
  - [ ] Rollback document created at `.sisyphus/evidence/rollback-procedures.md`
  - [ ] Contains exact kubectl commands for each change
  - [ ] Contains commands to verify rollback success
  - [ ] Contains instructions to revert retry logic code change

  **QA Scenarios**:

  ```
  Scenario: Rollback document exists with all procedures
    Tool: Bash
    Preconditions: Task 10 completed
    Steps:
      1. Test -f .sisyphus/evidence/rollback-procedures.md && echo "EXISTS" || echo "MISSING"
      2. grep -c "kubectl" .sisyphus/evidence/rollback-procedures.md
    Expected Result: File exists, contains >= 3 kubectl commands
    Evidence: .sisyphus/evidence/task-9-rollback-check.txt
  ```

  **Commit**: NO (part of Wave 3 group)

- [ ] 11. Final Stability Check

  **What to do**:
  - Verify all pods are Running and healthy
  - Check for any pod restarts since optimization
  - Verify no errors in Embedder or Ragflow logs
  - Confirm system is stable for continued use

  **Must NOT do**:
  - Make any changes

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Health check verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 9)
  - **Parallel Group**: Wave 3 (with Tasks 9, 10)
  - **Blocks**: None
  - **Blocked By**: Task 9

  **References**:
  - Pod status: `kubectl get pods -n embedding-aimighty -n ragflow-aimighty`
  - Restart count: `kubectl get pods -n embedding-aimighty -n ragflow-aimighty -o custom-columns='NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount'`

  **Acceptance Criteria**:
  - [ ] All pods Running with 0 restarts
  - [ ] No errors in recent logs
  - [ ] Stability report saved to `.sisyphus/evidence/stability-report.md`

  **QA Scenarios**:

  ```
  Scenario: All pods healthy with no restarts
    Tool: Bash (SSH)
    Preconditions: All optimizations applied
    Steps:
      1. ssh olares@172.20.0.4 "kubectl get pods -n embedding-aimighty -n ragflow-aimighty -o custom-columns='NAME:.metadata.name,STATUS:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount'"
    Expected Result: All pods show "Running" status with RESTARTS=0
    Evidence: .sisyphus/evidence/task-11-stability-check.txt
  ```

  **Commit**: NO (part of Wave 3 group)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 2 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Manual QA Verification** — `unspecified-high`
  Start from clean state. Execute key QA scenarios from Tasks 2, 4, 5, 7. Verify Embedder config, Ragflow config, and performance improvement. Save evidence to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | VERDICT: APPROVE/REJECT`

---

## Commit Strategy

- **Wave 1-3**: NO commits during execution (infrastructure changes)
- **Final**: YES — single commit documenting all changes
  - Message: `perf(ragflow-embedder): optimize embedding pipeline for 8x throughput`
  - Files: `.sisyphus/evidence/*.md`
  - Pre-commit: All QA scenarios pass

---

## Success Criteria

### Verification Commands
```bash
# Embedder config
kubectl get deployment -n embedding-aimighty embedding -o jsonpath='{.spec.template.spec.containers[0].env}' | grep -E 'NUM_STREAMS=4|PERFORMANCE_HINT=THROUGHPUT'

# Ragflow config
kubectl get deployment -n ragflow-aimighty ragflow -o jsonpath='{.spec.template.spec.containers[0].env}' | grep -E 'EMBEDDING_BATCH_SIZE=32|MAX_CONCURRENT_CHUNK_BUILDERS=2'

# Replica count
kubectl get deployment -n embedding-aimighty embedding -o jsonpath='{.spec.replicas}'  # Expected: 3

# Pod health
kubectl get pods -n embedding-aimighty -n ragflow-aimighty  # All Running, 0 restarts
```

### Final Checklist
- [ ] NUM_STREAMS=4, PERFORMANCE_HINT=THROUGHPUT on Embedder
- [ ] EMBEDDING_BATCH_SIZE=32, MAX_CONCURRENT_CHUNK_BUILDERS=2 on Ragflow
- [ ] Embedder scaled to 3 replicas
- [ ] Embedding job completes with 0 failures
- [ ] Performance improvement >= 2x (conservative) / 5x (target) / 8x (optimal)
- [ ] Rollback procedures documented
- [ ] All pods healthy, no restarts
