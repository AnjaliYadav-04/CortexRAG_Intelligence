"""Text2SQL pipeline nodes: generator → validator → executor → formatter."""

from __future__ import annotations
import os
import re
import asyncpg
from app.core.state import RAGState
from app.utils.llm import chat_completion

# ── DB Schema hint for GPT-4o ────────────────────────────────────────────────
_SCHEMA_HINT = """
Tables (PostgreSQL 16):
  clusters(id, name, region, version, status, created_at)
  nodes(id, cluster_id, name, status, cpu_total, mem_total_gb, created_at)
  pods(id, node_id, namespace, name, status, restart_count, created_at)
  incidents(id, cluster_id, severity, title, opened_at, closed_at)
  deployments(id, cluster_id, namespace, name, replicas, ready_replicas, created_at)
"""

_SQL_GEN_PROMPT = """\
You are an expert SQL generator for a Kubernetes ops database.
Generate a single safe READ-ONLY PostgreSQL SELECT query.
Return ONLY the SQL — no explanation, no markdown.

Schema:
{schema}

Question: {query}
"""

# ── Blocklist ─────────────────────────────────────────────────────────────────
_BLOCKLIST = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|EXEC)\b",
    re.IGNORECASE,
)


# ── Generator ─────────────────────────────────────────────────────────────────

async def generate_sql(state: RAGState) -> RAGState:
    sql = await chat_completion(
        prompt=_SQL_GEN_PROMPT.format(schema=_SCHEMA_HINT, query=state.query),
        max_tokens=300,
        temperature=0,
    )
    # Strip accidental markdown fences
    sql = re.sub(r"```sql|```", "", sql).strip()
    state.generated_sql = sql
    state.requires_human_approval = True   # triggers HITL interrupt
    return state


# ── Validator ─────────────────────────────────────────────────────────────────

async def validate_sql(state: RAGState) -> RAGState:
    sql = state.generated_sql or ""

    if _BLOCKLIST.search(sql):
        state.generated_sql = None
        state.error = "SQL validation failed: non-SELECT statement detected."
        state.sql_approved = False
        return state

    if not re.search(r"\bSELECT\b", sql, re.IGNORECASE):
        state.generated_sql = None
        state.error = "SQL validation failed: no SELECT keyword found."
        state.sql_approved = False
        return state

    state.sql_validated = True
    # sql_approved remains None → HITL interrupt fires
    return state


# ── Executor ──────────────────────────────────────────────────────────────────

async def execute_sql(state: RAGState) -> RAGState:
    if not state.sql_approved:
        return state

    dsn = os.getenv("POSTGRES_DSN", "postgresql://rag:rag@localhost:5432/ragdb")
    try:
        conn = await asyncpg.connect(dsn)
        rows = await conn.fetch(state.generated_sql)
        await conn.close()
        state.sql_result_rows = [dict(r) for r in rows[:100]]   # cap at 100 rows
    except Exception as exc:
        state.error = f"SQL execution error: {exc}"
    return state


async def format_results(state: RAGState) -> RAGState:
    rows = state.sql_result_rows
    if not rows:
        state.sql_formatted = "No results returned."
        return state

    headers = list(rows[0].keys())
    lines = [" | ".join(headers)]
    lines.append("-" * len(lines[0]))
    for row in rows:
        lines.append(" | ".join(str(row[h]) for h in headers))

    state.sql_formatted = "\n".join(lines)
    return state
