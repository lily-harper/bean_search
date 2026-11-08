"""Persist built graphs to disk.

Pickle is used (not GraphML) because the graph mixes int road-node ids with
string goal-node ids, which GraphML round-trips poorly.
"""

import pickle
from pathlib import Path

import networkx as nx

DATA_DIR = Path("data")


def default_path(region: str) -> Path:
    return DATA_DIR / f"{region}_bean_graph.pkl"


def save_graph(G: nx.MultiDiGraph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_graph(path: Path) -> nx.MultiDiGraph:
    with path.open("rb") as f:
        return pickle.load(f)
