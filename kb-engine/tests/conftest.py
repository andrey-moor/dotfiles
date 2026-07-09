import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class RealVectors:
    """~58 real jina-v3 note vectors copied from the live KB (see scripts/
    generate_real_vectors.py). Tests select by GROUP label, never by path."""

    matrix: np.ndarray
    entries: tuple

    def by_group(self, prefix: str) -> list[tuple[str, np.ndarray]]:
        return [
            (e["path"], self.matrix[i])
            for i, e in enumerate(self.entries)
            if e["group"].startswith(prefix)
        ]


@pytest.fixture(scope="session")
def real_vectors() -> RealVectors:
    matrix = np.load(_FIXTURE_DIR / "real_vectors.npy")
    entries = json.loads((_FIXTURE_DIR / "real_vectors.json").read_text())
    return RealVectors(matrix=matrix, entries=tuple(entries))
