"""Keep quote-derived filenames inside their configured private directories."""
from pathlib import Path


def private_child(root: Path, *parts: str) -> Path:
    root = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise ValueError("Invalid storage path.")
    return candidate
