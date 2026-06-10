# Kubernetes Common Errors — Knowledge Base

---

## OOMKilled

**What it means:** The container exceeded its memory limit. The Linux kernel OOM killer terminated the process.

**Symptoms:**
- `kubectl get pods` shows `OOMKilled` in the REASON column
- `kubectl describe pod <name>` shows `Last State: Terminated` with reason `OOMKilled`
- Exit code is 137 (128 + signal 9)

**Common causes:**
- Memory limit set too low for the workload
- Memory leak in application code
- Sudden spike in traffic causing higher memory usage than expected

**How to fix:**
1. Check current usage: `kubectl top pod <name>`
2. Increase the memory limit in the pod spec: `resources.limits.memory`
3. If a leak is suspected, profile the application — increasing limits masks the root cause
4. Set requests equal to limits for predictable scheduling

```yaml
resources:
  requests:
    memory: "256Mi"
  limits:
    memory: "512Mi"
```

---

## CrashLoopBackOff

**What it means:** The container starts, crashes, and Kubernetes keeps restarting it with exponential backoff. The backoff period doubles each time (10s, 20s, 40s, up to 5 minutes).

**Symptoms:**
- `kubectl get pods` shows `CrashLoopBackOff` status
- Restart count keeps increasing
- `kubectl describe pod <name>` shows repeated `Back-off restarting failed container`

**Common causes:**
- Application fails to start (missing config, bad env vars, missing dependency)
- Application crashes immediately after start (unhandled exception, port already in use)
- Liveness probe killing the container before it finishes starting up
- OOMKilled on startup

**How to diagnose:**
1. `kubectl logs <pod-name>` — check current logs
2. `kubectl logs <pod-name> --previous` — check logs from the previous crashed container
3. `kubectl describe pod <pod-name>` — check events and exit code

**How to fix:** Fix the underlying crash cause found in logs. If the app needs more startup time, increase `initialDelaySeconds` on the liveness probe.

---

## ImagePullBackOff / ErrImagePull

**What it means:** Kubernetes cannot pull the container image from the registry.

**Symptoms:**
- `kubectl get pods` shows `ImagePullBackOff` or `ErrImagePull`
- `kubectl describe pod <name>` shows `Failed to pull image` in events

**Common causes:**
- Image name or tag is wrong (typo, wrong registry, image does not exist)
- Image tag `:latest` was overwritten and the cached version is stale
- Private registry requires credentials not provided to the cluster
- Network issue between node and registry

**How to fix:**
1. Verify the image exists: `docker pull <image-name>:<tag>` from your local machine
2. Check the exact image name: `kubectl describe pod <name> | grep Image:`
3. For private registries, create an `imagePullSecret`:
   ```bash
   kubectl create secret docker-registry regcred \
     --docker-server=<registry> \
     --docker-username=<user> \
     --docker-password=<token>
   ```
4. Reference the secret in the pod spec under `spec.imagePullSecrets`

---

## Pending Pod — Insufficient Resources

**What it means:** The pod cannot be scheduled because no node has enough CPU or memory to satisfy the pod's resource requests.

**Symptoms:**
- `kubectl get pods` shows `Pending` status (not `Running`)
- `kubectl describe pod <name>` shows `Insufficient cpu` or `Insufficient memory` in events

**Common causes:**
- Resource requests are set too high
- All nodes are fully occupied
- Node selector or affinity rules prevent scheduling on available nodes
- Taints on nodes that the pod does not tolerate

**How to diagnose:**
1. `kubectl describe pod <name>` — read the `Events` section at the bottom
2. `kubectl describe nodes` — check `Allocatable` vs `Requests` for each node

**How to fix:**
- Lower resource requests if they are over-provisioned
- Add nodes to the cluster or scale up existing node pools
- Review node selectors, affinity, and taints

---

## Evicted Pod

**What it means:** The kubelet evicted the pod because the node ran low on resources (disk, memory, or inodes).

**Symptoms:**
- `kubectl get pods` shows `Evicted` status
- `kubectl describe pod <name>` shows eviction reason (e.g., `The node was low on resource: memory`)

**Common causes:**
- Node disk pressure: logs or container images consuming too much disk
- Node memory pressure: too many pods on the node consuming memory
- No resource limits set, allowing a single pod to consume all node resources

**How to fix:**
1. `kubectl describe node <node-name>` — check `Conditions` for `MemoryPressure` or `DiskPressure`
2. Clean up unused images: `docker image prune` on the node
3. Always set resource `requests` and `limits` to prevent unbounded consumption
4. Use `LimitRange` to enforce defaults at namespace level

---

## Readiness Probe Failing

**What it means:** The container is running but the readiness probe reports it is not ready to serve traffic. The pod is removed from Service endpoints until the probe passes.

**Symptoms:**
- Pod status shows `Running` but `READY` column shows `0/1`
- `kubectl describe pod <name>` shows `Readiness probe failed` in events
- Service returns connection refused or 503 for requests routed to this pod

**Common causes:**
- Application takes longer to start than `initialDelaySeconds` allows
- Application is genuinely unhealthy (database connection failed, dependency unavailable)
- Wrong port or path configured in the probe
- The probe endpoint returns a non-2xx status code

**How to fix:**
1. `kubectl logs <pod-name>` — check if the app logged a startup error
2. Test the probe endpoint manually: `kubectl exec <pod> -- curl -s http://localhost:<port><path>`
3. Increase `initialDelaySeconds` if the app needs more time to warm up
4. Fix the underlying health issue (database connectivity, missing config)

---

## Liveness Probe Failing

**What it means:** The liveness probe reports the container is unhealthy. Kubernetes kills and restarts the container.

**Symptoms:**
- Pod shows high restart count
- `kubectl describe pod <name>` shows `Liveness probe failed` followed by `Killing container`
- Often leads to `CrashLoopBackOff` if the probe keeps failing

**Common causes:**
- Application is deadlocked or unresponsive
- Probe timeout too short for a slow health endpoint
- Probe is checking a path that the application deleted or changed
- Application needs more time to start before the probe begins

**How to fix:**
1. Increase `timeoutSeconds` if the health endpoint is slow
2. Increase `initialDelaySeconds` to give the app more startup time
3. Increase `failureThreshold` to tolerate transient failures before killing
4. Verify the health endpoint is correct: `kubectl exec <pod> -- curl http://localhost:<port>/health`

---

## DNS Resolution Failure

**What it means:** A pod cannot resolve the hostname of another service or external address. Kubernetes uses CoreDNS for internal service discovery.

**Symptoms:**
- Application logs show `no such host`, `could not resolve`, or `dial tcp: lookup <name>`
- `nslookup` or `curl` inside the pod returns `NXDOMAIN`

**Common causes:**
- Wrong service name used (must match `metadata.name` of the Service exactly)
- Pod in a different namespace without the fully qualified name (`service.namespace.svc.cluster.local`)
- CoreDNS pod is crashing or overloaded
- NetworkPolicy blocking DNS traffic to port 53

**How to diagnose:**
1. Test DNS from inside the pod: `kubectl exec <pod> -- nslookup <service-name>`
2. Use the FQDN: `kubectl exec <pod> -- nslookup <service>.<namespace>.svc.cluster.local`
3. Check CoreDNS: `kubectl get pods -n kube-system -l k8s-app=kube-dns`

**How to fix:**
- Correct the service name in the application config
- Use the fully qualified domain name when crossing namespaces
- Restart CoreDNS pods if they are in a bad state: `kubectl rollout restart deployment coredns -n kube-system`

---

## PersistentVolumeClaim Not Bound

**What it means:** A PVC has been created but no PersistentVolume has been bound to it. Pods that reference the PVC stay `Pending`.

**Symptoms:**
- `kubectl get pvc` shows `STATUS: Pending`
- `kubectl describe pvc <name>` shows `waiting for first consumer` or `no persistent volumes available`

**Common causes:**
- No PV matches the PVC's storage class, access mode, or size request
- Dynamic provisioner (StorageClass) is not configured or unavailable
- Requested storage size exceeds what any available PV offers

**How to fix:**
1. `kubectl describe pvc <name>` — check events for specific mismatch reason
2. `kubectl get storageclass` — verify a default StorageClass exists
3. For manual provisioning: create a PV that matches the PVC's `storageClassName`, `accessModes`, and `storage` request
4. For dynamic provisioning: ensure the cloud provider's CSI driver is running

---

## Node NotReady

**What it means:** A node has stopped communicating with the control plane. All pods on that node are marked `Unknown` and eventually evicted.

**Symptoms:**
- `kubectl get nodes` shows `NotReady` for a node
- Pods on that node show `Unknown` status after the node heartbeat timeout (~40 seconds)

**Common causes:**
- Node VM crashed or was shut down
- kubelet process stopped on the node
- Node ran out of disk or memory, causing the OS to become unresponsive
- Network partition between the node and the control plane

**How to diagnose:**
1. `kubectl describe node <name>` — check `Conditions` section for `MemoryPressure`, `DiskPressure`, `NetworkUnavailable`
2. SSH to the node (if accessible) and check: `systemctl status kubelet`
3. Check kubelet logs: `journalctl -u kubelet -n 100`

**How to fix:**
- Restart kubelet: `systemctl restart kubelet`
- If the node is unrecoverable, drain and delete it: `kubectl drain <node> --ignore-daemonsets && kubectl delete node <node>`
- For cloud VMs: reboot the instance from the cloud console

---

## CreateContainerConfigError

**What it means:** Kubernetes created the container but could not configure it before starting, usually due to a missing or invalid reference in the pod spec.

**Symptoms:**
- Pod shows `CreateContainerConfigError` status
- `kubectl describe pod <name>` shows `Error: secret <name> not found` or `configmap <name> not found`

**Common causes:**
- A referenced Secret or ConfigMap does not exist in the same namespace
- Environment variable references a key that does not exist in the Secret/ConfigMap
- Volume mount references a non-existent Secret or ConfigMap

**How to fix:**
1. `kubectl describe pod <name>` — read the exact error in events
2. Verify the Secret or ConfigMap exists: `kubectl get secret <name>` or `kubectl get configmap <name>`
3. Create the missing resource before deploying the pod
4. Check for namespace mismatch — Secrets and ConfigMaps are namespace-scoped
