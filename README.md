# Enterprise Advanced RAG — Kubernetes SRE Copilot :CorexRAG

> LangGraph · Hybrid Search · CRAG · Self-RAG · Text2SQL (HITL) · 5-Tier Cache · 9-Layer Guardrails

A production-grade RAG system for Kubernetes IT operations built with FastAPI, LangGraph, Qdrant, PostgreSQL, Redis, and Streamlit.

## Architecture

```
SRE/User → FastAPI → 9-Layer Input Security → LangGraph State Machine
                                                   ├── RAG Pipeline (HyDE → Hybrid Retrieval → RRF → Rerank → CRAG → Self-RAG)
                                                   └── Text2SQL Pipeline (GPT-4o → Validate → HITL → Execute)
                                               → 5-Tier Redis Cache → Response
```
# 🔄 Workflow Diagram

```mermaid
flowchart TD

%% Nodes Styling
classDef user fill:#0ea5e9,color:#fff,stroke:#0369a1,stroke-width:2px;
classDef api fill:#6366f1,color:#fff,stroke:#4338ca,stroke-width:2px;
classDef input fill:#f97316,color:#fff,stroke:#c2410c,stroke-width:2px;
classDef rag fill:#3b82f6,color:#fff,stroke:#1d4ed8,stroke-width:2px;
classDef sql fill:#10b981,color:#fff,stroke:#047857,stroke-width:2px;
classDef llm fill:#ec4899,color:#fff,stroke:#be185d,stroke-width:2px;
classDef cache fill:#ef4444,color:#fff,stroke:#b91c1c,stroke-width:2px;
classDef output fill:#dc2626,color:#fff,stroke:#991b1b,stroke-width:2px;
classDef db fill:#14b8a6,color:#fff,stroke:#0f766e,stroke-width:2px;
classDef decision fill:#8b5cf6,color:#fff,stroke:#6d28d9,stroke-width:2px;

%% Main Nodes
U[SRE / User]
F[FastAPI Service]

%% Input Security
subgraph INPUT["🛡️ Input Security Pipeline"]
    I1[Pydantic + Regex]
    I2[JWT Auth]
    I3[Rate Limit]
    I4[Token Budget]
    I5[Input Restructure]
    I6[LLM Guard Scan]
    I7[Content Moderation]
end

%% Cache Layer
subgraph CACHE["⚡ 5-Tier Redis Cache"]
    C1[Embedding]
    C2[Intent Router]
    C3[SQL Gen]
    C4[SQL Result]
    C5[RAG Answer]
end

%% LangGraph
subgraph LANGGRAPH["🧠 LangGraph State Machine"]

    R{Intent Router}

    subgraph RAG["📘 RAG Pipeline"]
        H[HyDE]
        E[Embed Query]
        HR[Hybrid Retrieval]
        RF[RRF Fusion]
        RR[Cross-Encoder Rerank]
        CG[CRAG Grader]
        SP[Spotlighting]
        TV[Tavily Fallback]
    end

    subgraph SQL["🗄️ Text2SQL Pipeline"]
        GS[Generate SQL]
        VS[Validate SQL]
        HITL[Human Approval]
        EX[Execute SQL]
        FR[Format Results]
    end

    LG[LLM Answer Generation]
    SR[Self-RAG Reflect]
    FN[Finalize + Metadata]
end

%% Output Security
subgraph OUTPUT["🚨 Output Security"]
    O1[Output Moderation]
    O2[PII Redaction]
    O3[Schema Validation]
end

%% Data Stores
subgraph STORES["💾 Persistent Data Stores"]
    Q[Qdrant]
    P[PostgreSQL]
    S[S3 / Local FS]
    OA[OpenAI API]
    T[Tavily API]
end

%% Main Flow
U --> F
F --> I1
I1 --> I2 --> I3 --> I4 --> I5 --> I6 --> I7
I7 --> R

%% Cache Connection
F --> C1
F --> C2
F --> C3
F --> C4
F --> C5

%% Intent Routing
R -->|rag / hybrid| H
R -->|sql / hybrid| GS

%% RAG Flow
H --> E --> HR --> RF --> RR --> CG --> SP
CG -->|low relevance| TV
TV --> SP
SP --> LG

%% SQL Flow
GS --> VS --> HITL --> EX --> FR --> LG

%% Self Reflection
LG --> SR
SR -->|score < 0.8| LG
LG --> FN

%% Output Security
FN --> O1 --> O2 --> O3 --> U

%% Store Connections
HR --> Q
EX --> P
SP --> S
H --> OA
GS --> OA
TV --> T

%% Apply Styles
class U user;
class F api;

class I1,I2,I3,I4,I5,I6,I7 input;
class H,E,HR,RF,RR,CG,SP,TV rag;
class GS,VS,HITL,EX,FR sql;
class LG,SR,FN llm;
class C1,C2,C3,C4,C5 cache;
class O1,O2,O3 output;
class Q,P,S,OA,T db;
class R decision;
```
## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill environment variables
cp .env.example .env

# 3. Start infrastructure
docker-compose up -d

# 4. Seed data (K8s docs)
python scripts/seed_data.py

# 5. Run API
uvicorn app.main:app --reload

# 6. Open Streamlit UI
streamlit run app/ui/streamlit_app.py
```

## Project Structure

```
enterprise-rag/
├── app/
│   ├── main.py                  # FastAPI entrypoint
│   ├── api/
│   │   ├── routes.py            # REST endpoints
│   │   └── models.py            # Pydantic request/response models
│   ├── core/
│   │   ├── graph.py             # LangGraph state machine
│   │   ├── intent_router.py     # rag / sql / hybrid routing
│   │   └── state.py             # Graph state schema
│   ├── pipelines/
│   │   ├── rag/
│   │   │   ├── hyde.py          # Hypothetical Document Embeddings
│   │   │   ├── retrieval.py     # Hybrid retrieval (Dense + BM25)
│   │   │   ├── rerank.py        # Cross-encoder reranking
│   │   │   ├── crag.py          # CRAG grader + web fallback
│   │   │   ├── self_rag.py      # Self-RAG reflection loop
│   │   │   └── spotlighting.py  # XML-delimited context
│   │   └── sql/
│   │       ├── generator.py     # Text2SQL with GPT-4o
│   │       ├── validator.py     # SELECT-only + blocklist
│   │       └── executor.py      # Postgres execution
│   ├── cache/
│   │   └── redis_cache.py       # 5-tier TTL cache (Upstash)
│   ├── guardrails/
│   │   ├── input_pipeline.py    # 9-layer input security
│   │   └── output_pipeline.py   # Output moderation + PII redaction
│   └── utils/
│       ├── embeddings.py        # text-embedding-3-small wrapper
│       └── llm.py               # GPT-4o wrapper
├── scripts/
│   ├── seed_data.py             # Ingest K8s docs into Qdrant
│   └── run_evals.py             # Ragas evaluation suite
├── tests/
│   └── test_pipeline.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Sections Covered

| # | Topic | Key Techniques |
|---|-------|----------------|
| 1 | Project Intro | Architecture overview |
| 2 | Skeleton + Evals | UV, Docker, Ragas |
| 3 | Basic RAG | Qdrant, embeddings |
| 4 | Hybrid Search | Dense + BM25, RRF |
| 5 | ReRanking | BGE / Voyage AI cross-encoder |
| 6 | HyDE | 3 hypothetical answers |
| 7 | CRAG | Relevance grading, web fallback |
| 8 | Self-RAG | Score-based regeneration |
| 9 | Text2SQL | GPT-4o, HITL approval |
| 10 | Caching | 5-tier Redis TTL |
| 11 | Guardrails | 9-layer security pipeline |
