from __future__ import annotations

import re
from pathlib import Path


TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


class ManualSearcher:
    def __init__(self, manual_dir: str | Path):
        self.manual_dir = Path(manual_dir)
        self.chunks = self._load_chunks()

    def _load_chunks(self) -> list[dict[str, str]]:
        chunks: list[dict[str, str]] = []
        for manual_path in sorted(self.manual_dir.glob("manual_*.txt")):
            lines = [line.strip() for line in manual_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            for index, line in enumerate(lines, start=1):
                chunks.append(
                    {
                        "source": manual_path.stem,
                        "citation": f"[manual:{manual_path.stem}:chunk{index}]",
                        "text": line,
                    }
                )
        return chunks

    def search(self, query: str, device_type: str | None = None, top_k: int = 3) -> list[dict[str, str]]:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []

        source_alias = {
            "robot_vacuum": "manual_vacuum",
            "washing_machine": "manual_washer",
            "air_conditioner": "manual_air_conditioner",
            "remote_hub": "manual_remote",
        }
        expected_source = source_alias.get(device_type or "")

        scored: list[tuple[int, dict[str, str]]] = []
        for chunk in self.chunks:
            source = chunk["source"]
            if expected_source and source != expected_source:
                continue
            text_tokens = set(_tokenize(chunk["text"]))
            score = len(query_tokens & text_tokens)
            if expected_source and expected_source == source:
                score += 1
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: (-item[0], item[1]["citation"]))
        return [chunk for _, chunk in scored[:top_k]]
