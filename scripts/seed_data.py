#!/usr/bin/env python3
"""Seed Kubernetes documentation into Qdrant (dense + sparse vectors).

Usage:
    python scripts/seed_data.py [--source web|local] [--limit 200]
"""

from __future__ import annotations
import argparse
import asyncio
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
)

from app.config import settings

# ── Sample K8s docs (used if --source local) ──────────────────────────────────

SAMPLE_DOCS = [
    {
        "source": "k8s-docs/pods",
        "text": (
            "A Pod is the smallest deployable unit in Kubernetes. "
            "It represents a single instance of a running process in your cluster. "
            "Pods contain one or more containers that share storage, network, "
            "and a specification for how to run the containers. "
            "CrashLoopBackOff indicates a container repeatedly crashing after restart."
        ),
    },
    {
        "source": "k8s-docs/nodes",
        "text": (
            "A Node is a worker machine in Kubernetes. "
            "Each Node is managed by the control plane and contains the services "
            "necessary to run Pods. Node conditions include Ready, MemoryPressure, "
            "DiskPressure, PIDPressure, and NetworkUnavailable."
        ),
    },
    {
        "source": "k8s-docs/deployments",
        "text": (
            "A Deployment provides declarative updates for Pods and ReplicaSets. "
            "You describe a desired state in a Deployment, and the Deployment Controller "
            "changes the actual state to the desired state at a controlled rate. "
            "Rollout history is maintained for rollback capabilities."
        ),
    },
    {
        "source": "k8s-docs/services",
        "text": (
            "A Service is an abstract way to expose an application running on a set of Pods. "
            "Service types include ClusterIP, NodePort, LoadBalancer, and ExternalName. "
            "Services use label selectors to route traffic to the appropriate pods."
        ),
    },
    {
        "source": "k8s-docs/hpa",
        "text": (
            "Horizontal Pod Autoscaler (HPA) automatically scales the number of Pod replicas "
            "based on observed CPU utilization or custom metrics. "
            "HPA queries metrics every 15 seconds by default and uses the formula: "
            "desiredReplicas = ceil(currentReplicas * (currentMetric / desiredMetric))."
        ),
    },
    {
        "source": "k8s-docs/rbac",
        "text": (
            "Role-Based Access Control (RBAC) regulates access to Kubernetes resources. "
            "Core components: Role (namespace-scoped), ClusterRole (cluster-scoped), "
            "RoleBinding, and ClusterRoleBinding. "
            "The principle of least privilege should always be applied."
        ),
    },
    {
        "source": "k8s-docs/networking",
        "text": (
            "Kubernetes networking follows these requirements: all pods can communicate "
            "with each other without NAT, all nodes can communicate with all pods without NAT. "
            "CNI plugins (Calico, Flannel, Cilium) implement the network model. "
            "NetworkPolicy resources control traffic flow between pods."
        ),
    },
    {
        "source": "k8s-docs/storage",
        "text": (
            "PersistentVolumes (PV) and PersistentVolumeClaims (PVC) provide durable storage. "
            "StorageClasses enable dynamic provisioning. "
            "Access modes: ReadWriteOnce, ReadOnlyMany, ReadWriteMany. "
            "StatefulSets use volumeClaimTemplates for per-pod storage."
        ),
    },
    {
        "source": "k8s-docs/troubleshooting",
        "text": (
            "Common troubleshooting commands: kubectl describe pod <name> for events, "
            "kubectl logs <pod> --previous for crash logs, "
            "kubectl get events --sort-by=.metadata.creationTimestamp, "
            "kubectl top nodes/pods for resource usage. "
            "ImagePullBackOff means the container image cannot be pulled."
        ),
    },
    {
        "source": "k8s-docs/resource-management",
        "text": (
            "Resource requests and limits control CPU and memory allocation. "
            "Requests are used for scheduling; limits enforce runtime constraints. "
            "QoS classes: Guaranteed (req==limit), Burstable (req<limit), BestEffort (no req/limit). "
            "OOMKilled status indicates memory limit exceeded."
        ),
    },
]


async def seed(source: str = "local", limit: int = 200) -> None:
    print(f"[seed] Starting data ingestion | source={source} limit={limit}")

    # Lazy import to allow running without all deps installed
    from openai import AsyncOpenAI
    from rank_bm25 import BM25Okapi

    openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    qdrant = QdrantClient(url=settings.QDRANT_URL)

    docs = SAMPLE_DOCS[:limit]

    if source == "web":
        # In a real project, fetch from https://kubernetes.io/docs/
        print("[seed] Web crawling not implemented in skeleton — using sample docs.")

    # ── Recreate collection ───────────────────────────────────────────────────
    collection = settings.QDRANT_COLLECTION
    try:
        qdrant.delete_collection(collection)
    except Exception:
        pass

    qdrant.create_collection(
        collection_name=collection,
        vectors_config={"dense": VectorParams(size=settings.EMBED_DIM, distance=Distance.COSINE)},
        sparse_vectors_config={
            "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
        },
    )
    print(f"[seed] Created collection '{collection}'")

    # ── BM25 sparse index (over all docs) ─────────────────────────────────────
    tokenized = [doc["text"].lower().split() for doc in docs]
    bm25 = BM25Okapi(tokenized)

    # ── Embed + upload ────────────────────────────────────────────────────────
    batch_size = 20
    points: list[PointStruct] = []

    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        texts = [d["text"] for d in batch]

        # Dense embeddings
        resp = await openai.embeddings.create(model=settings.EMBED_MODEL, input=texts)
        dense_vecs = [r.embedding for r in resp.data]

        for j, (doc, dense) in enumerate(zip(batch, dense_vecs)):
            doc_idx = i + j
            # BM25 sparse vector
            bm25_scores = bm25.get_scores(doc["text"].lower().split())
            indices = [k for k, s in enumerate(bm25_scores) if s > 0]
            values  = [float(bm25_scores[k]) for k in indices]

            doc_id = int(hashlib.md5(doc["source"].encode()).hexdigest()[:8], 16)

            points.append(PointStruct(
                id=doc_idx,
                vector={
                    "dense": dense,
                    "sparse": SparseVector(indices=indices, values=values),
                },
                payload={"text": doc["text"], "source": doc["source"]},
            ))

        print(f"[seed] Embedded batch {i // batch_size + 1} / {len(docs) // batch_size + 1}")

    qdrant.upsert(collection_name=collection, points=points)
    print(f"[seed] ✅ Inserted {len(points)} documents into '{collection}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed K8s docs into Qdrant")
    parser.add_argument("--source", choices=["local", "web"], default="local")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    asyncio.run(seed(args.source, args.limit))
