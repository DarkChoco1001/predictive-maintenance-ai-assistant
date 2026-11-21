"""Knowledge base: FMEA records plus a small BM25 search over the troubleshooting guide.

BM25 keeps the demo dependency-free. In production you would swap in a vector store
(FAISS, Milvus, pgvector) over the customer's manuals and work-order history.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

KB_DIR = Path(__file__).parent / "knowledge"
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    text: str


class KnowledgeBase:
    def __init__(self, kb_dir: Path = KB_DIR) -> None:
        self.fmea: list[dict] = json.loads((kb_dir / "fmea.json").read_text())["modes"]
        self.fmea_by_id = {m["id"]: m for m in self.fmea}
        self.chunks = self._split((kb_dir / "troubleshooting.md").read_text())
        self._docs = [_tokens(c.title + " " + c.text) for c in self.chunks]
        self._avg_len = sum(map(len, self._docs)) / max(1, len(self._docs))
        df = Counter(t for doc in self._docs for t in set(doc))
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    @staticmethod
    def _split(markdown: str) -> list[Chunk]:
        chunks = []
        for block in re.split(r"^## ", markdown, flags=re.M)[1:]:
            title, _, body = block.partition("\n")
            chunk_id = title.split(" ")[0] if title.startswith("TS-") else "PLAN"
            chunks.append(Chunk(chunk_id, title.strip(), body.strip()))
        return chunks

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        q = _tokens(query)
        k1, b = 1.5, 0.75
        scores = []
        for chunk, doc in zip(self.chunks, self._docs):
            tf = Counter(doc)
            s = sum(self._idf.get(t, 0) * tf[t] * (k1 + 1)
                    / (tf[t] + k1 * (1 - b + b * len(doc) / self._avg_len)) for t in q if t in tf)
            scores.append((s, chunk))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [c for s, c in scores[:k] if s > 0]

    def get_procedure(self, procedure_id: str) -> Chunk | None:
        return next((c for c in self.chunks if c.id == procedure_id), None)
