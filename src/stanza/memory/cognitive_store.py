import math
import sqlite3
import time
import json
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class MemoryRecord:
    record_id: int
    tier: str  # EPISODIC, SEMANTIC, PROCEDURAL
    content: str
    tags: List[str]
    importance: float
    created_at: float
    score: float = 0.0


class HybridCognitiveMemory:
    """
    3-Tier Hierarchical Memory Architecture (Episodic, Semantic, Procedural)
    backed by SQLite with Hybrid BM25 + Cosine Vector Similarity + Temporal Decay.
    """

    def __init__(self, db_path: str = ":memory:", k1: float = 1.5, b: float = 0.75):
        self.db_path = db_path
        self.k1 = k1
        self.b = b
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cognitive_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tier TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT NOT NULL,
                importance REAL NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9_]+", text.lower())

    def store(
        self,
        content: str,
        tier: str = "SEMANTIC",
        tags: Optional[List[str]] = None,
        importance: float = 0.75,
    ) -> int:
        tier_clean = tier.upper()
        if tier_clean not in {"EPISODIC", "SEMANTIC", "PROCEDURAL"}:
            tier_clean = "SEMANTIC"
        tags_json = json.dumps(tags or [])
        now = time.time()
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO cognitive_memory (tier, content, tags, importance, created_at) VALUES (?, ?, ?, ?, ?)",
            (tier_clean, content, tags_json, float(importance), now),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def _compute_cosine_similarity(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        if not query_tokens or not doc_tokens:
            return 0.0
        vocab = list(set(query_tokens + doc_tokens))
        q_vec = [query_tokens.count(w) for w in vocab]
        d_vec = [doc_tokens.count(w) for w in vocab]
        dot = sum(q * d for q, d in zip(q_vec, d_vec))
        norm_q = math.sqrt(sum(q * q for q in q_vec))
        norm_d = math.sqrt(sum(d * d for d in d_vec))
        if norm_q == 0.0 or norm_d == 0.0:
            return 0.0
        return dot / (norm_q * norm_d)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        tier_filter: Optional[str] = None,
    ) -> List[MemoryRecord]:
        cursor = self._conn.cursor()
        if tier_filter:
            cursor.execute(
                "SELECT id, tier, content, tags, importance, created_at FROM cognitive_memory WHERE tier = ?",
                (tier_filter.upper(),),
            )
        else:
            cursor.execute("SELECT id, tier, content, tags, importance, created_at FROM cognitive_memory")
        rows = cursor.fetchall()
        if not rows:
            return []

        query_tokens = self._tokenize(query)
        docs_tokens = [self._tokenize(row[2]) for row in rows]
        total_docs = len(rows)
        avg_dl = sum(len(dt) for dt in docs_tokens) / max(1, total_docs)

        # Compute IDF for query tokens
        idf: Dict[str, float] = {}
        for qt in set(query_tokens):
            df = sum(1 for dt in docs_tokens if qt in dt)
            idf[qt] = math.log(1.0 + (total_docs - df + 0.5) / (df + 0.5))

        now = time.time()
        scored_records: List[MemoryRecord] = []

        for idx, row in enumerate(rows):
            rec_id, tier, content, tags_str, importance, created_at = row
            doc_t = docs_tokens[idx]
            dl = len(doc_t)

            # BM25 Score
            bm25_score = 0.0
            for qt in query_tokens:
                tf = doc_t.count(qt)
                if tf > 0:
                    num = tf * (self.k1 + 1.0)
                    den = tf + self.k1 * (1.0 - self.b + self.b * (dl / max(1e-6, avg_dl)))
                    bm25_score += idf.get(qt, 0.0) * (num / den)

            # Cosine Similarity
            cosine = self._compute_cosine_similarity(query_tokens, doc_t)

            # Temporal Recency Decay
            age_hours = max(0.0, (now - created_at) / 3600.0)
            recency_factor = math.exp(-0.01 * age_hours)

            hybrid_score = (bm25_score * 0.55) + (cosine * 0.30) + (importance * recency_factor * 0.15)

            scored_records.append(
                MemoryRecord(
                    record_id=rec_id,
                    tier=tier,
                    content=content,
                    tags=json.loads(tags_str),
                    importance=importance,
                    created_at=created_at,
                    score=round(hybrid_score, 5),
                )
            )

        scored_records.sort(key=lambda r: r.score, reverse=True)
        return scored_records[:top_k]

    def stats(self) -> Dict[str, Any]:
        cursor = self._conn.cursor()
        cursor.execute("SELECT tier, COUNT(*) FROM cognitive_memory GROUP BY tier")
        counts = dict(cursor.fetchall())
        return {
            "total_records": sum(counts.values()),
            "by_tier": counts,
        }
