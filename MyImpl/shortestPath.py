"""
GPT 4o AI Prompts: 


***** First Prompt - Let't implement Dijktra's algorithm in Python for the following data structure as an experienced developer. 
Include comments and handle edge cases (like self loops or others). 
{ "nodes": [0, 1, 2, 3, 4], "edges": [ {"from": 0, "to": 1, "weight": 10}, {"from": 1, "to": 3, "weight": 12}, # ... ], 
"directed": False # Optional, defaults to False }

***** Second Prompt -
Please update the code with more clear comments (stay concise and clear) and rename variables like "u" and "v" 
into more explcit names.

***** Third Prompt -
Let's update code from a SRE's perspective to handle production load and edge cases. Code maintainability 
is still important.

"""
"""
Production-ready Dijkstra implementation with SRE-minded safeguards and observability.

Design goals:
- Correctness for non-negative-weight graphs (Dijkstra precondition).
- Defensive input validation with configurable strictness.
- Safety against resource exhaustion (node/heap/loop limits and timeout).
- Observability: optional logging and returned runtime stats.
- Maintainability: clear structure, concise comments, and typed config.

Usage:
- Call dijkstra(graph, source, target=None, config=Config(...))
- graph: same structure as before:
    {
        "nodes": [ ... ]           # optional
        "edges": [ {"from": u, "to": v, "weight": w}, ... ]
        "directed": False          # optional
    }
- Returns (distances, predecessor, stats)
"""

from dataclasses import dataclass
import heapq
import logging
import math
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

# --- Exceptions --------------------------------------------------------------


class DijkstraError(Exception):
    """Base error for Dijkstra-related failures."""


class NegativeWeightError(DijkstraError):
    """Raised when a negative edge weight is detected and validation is enabled."""


class TimeoutError(DijkstraError):
    """Raised when search exceeds configured timeout."""


class CapacityError(DijkstraError):
    """Raised when search exceeds configured safety limits (nodes/heap ops)."""


# --- Configuration dataclass -------------------------------------------------


@dataclass(frozen=True)
class DijkstraConfig:
    """
    Configuration for dijkstra() behavior.
    - timeout_seconds: abort search after this many seconds (None = no timeout)
    - max_visited_nodes: safety limit for number of finalized nodes (None = no limit)
    - max_heap_operations: safety limit for number of heap pushes/pops (None = no limit)
    - validate_non_negative_weights: if True, scan edges and raise on negative weights (default True)
    - weight_key: the key name in edge dicts that holds the numeric weight
    - logger: optional logger; if None the module logger is used
    - warn_if_large_graph: log a warning if node/edge counts exceed this threshold (None to disable)
    """

    timeout_seconds: Optional[float] = 5.0
    max_visited_nodes: Optional[int] = 1_000_000
    max_heap_operations: Optional[int] = 5_000_000
    validate_non_negative_weights: bool = True
    weight_key: str = "weight"
    logger: Optional[logging.Logger] = None
    warn_if_large_graph: Optional[int] = 100_000  # warn when nodes or edges exceed this


# --- Dijkstra implementation ------------------------------------------------


def dijkstra(
    graph: Dict[str, Any],
    source: Any,
    target: Optional[Any] = None,
    config: DijkstraConfig = DijkstraConfig(),
) -> Tuple[Dict[Any, float], Dict[Any, Optional[Any]], Dict[str, Any]]:
    """
    Compute shortest paths using Dijkstra's algorithm with production safeguards.

    Returns:
      - distances: node -> shortest distance (math.inf if unreachable)
      - predecessor: node -> previous node on a shortest path (None if unknown/source)
      - stats: dictionary with runtime metrics:
          { "nodes_total", "edges_total", "nodes_visited", "heap_ops", "duration_seconds" }

    Errors:
      - Raises ValueError for invalid input (missing source/target).
      - Raises NegativeWeightError if negative weights detected and validation enabled.
      - Raises TimeoutError or CapacityError if limits are exceeded.
    """

    logger = config.logger or logging.getLogger(__name__)
    edges = graph.get("edges", [])
    directed = bool(graph.get("directed", False))
    nodes_iterable: Optional[Iterable[Any]] = graph.get("nodes", None)

    # --- Build node set ----------------------------------------------------
    node_set: Set[Any] = set()
    if nodes_iterable is not None:
        node_set.update(nodes_iterable)
    for e in edges:
        # Defensive: edges must be mappings with 'from' and 'to'
        if not isinstance(e, dict) or "from" not in e or "to" not in e:
            raise ValueError(f"Invalid edge entry (expected dict with 'from' and 'to'): {e!r}")
        node_set.add(e["from"])
        node_set.add(e["to"])

    if source not in node_set:
        raise ValueError(f"Source node {source!r} not present in graph nodes/edges")
    if target is not None and target not in node_set:
        raise ValueError(f"Target node {target!r} not present in graph nodes/edges")

    nodes_total = len(node_set)
    edges_total = len(edges)
    if config.warn_if_large_graph:
        if nodes_total > config.warn_if_large_graph or edges_total > config.warn_if_large_graph:
            logger.warning(
                "Large graph detected: nodes=%d edges=%d; ensure limits/timeouts are appropriate",
                nodes_total,
                edges_total,
            )

    # --- Validate weights (optional) and build adjacency list --------------
    # adjacency: node -> list of (neighbor, weight)
    adjacency: Dict[Any, List[Tuple[Any, float]]] = {n: [] for n in node_set}

    if config.validate_non_negative_weights:
        # Full scan: ensure numeric & non-negative weights (Dijkstra precondition).
        for e in edges:
            w = e.get(config.weight_key)
            if not isinstance(w, (int, float)):
                raise ValueError(f"Edge weight must be numeric for edge {e!r}")
            if w < 0:
                raise NegativeWeightError(
                    f"Negative edge weight detected ({e['from']} -> {e['to']} weight={w}). "
                    "Dijkstra cannot handle negative weights."
                )
            # append after validation
            adjacency[e["from"]].append((e["to"], float(w)))
            if not directed:
                adjacency[e["to"]].append((e["from"], float(w)))
    else:
        # Skip validation to save time; still build adjacency but do minimal checks.
        for e in edges:
            w = e.get(config.weight_key)
            try:
                weight_f = float(w)
            except Exception as exc:
                raise ValueError(f"Edge weight conversion failed for edge {e!r}: {exc}") from exc
            adjacency[e["from"]].append((e["to"], weight_f))
            if not directed:
                adjacency[e["to"]].append((e["from"], weight_f))

    # --- Prepare algorithm structures --------------------------------------
    distances: Dict[Any, float] = {n: math.inf for n in node_set}
    predecessor: Dict[Any, Optional[Any]] = {n: None for n in node_set}

    distances[source] = 0.0
    heap: List[Tuple[float, Any]] = [(0.0, source)]  # min-heap of (distance, node)
    finalized: Set[Any] = set()

    start_time = time.monotonic()
    heap_ops = 0
    nodes_visited = 0

    # Local aliases for quick access
    max_heap_ops = config.max_heap_operations
    max_visited = config.max_visited_nodes
    timeout_seconds = config.timeout_seconds

    # --- Main loop with SRE safeguards ------------------------------------
    while heap:
        # Timeout check
        if timeout_seconds is not None and (time.monotonic() - start_time) > timeout_seconds:
            raise TimeoutError(
                f"Dijkstra search exceeded timeout of {timeout_seconds} seconds; "
                f"nodes_visited={nodes_visited} heap_ops={heap_ops}"
            )

        # Heap operation count (pop)
        heap_ops += 1
        if max_heap_ops is not None and heap_ops > max_heap_ops:
            raise CapacityError(f"Exceeded max_heap_operations={max_heap_ops}")

        current_distance, current_node = heapq.heappop(heap)

        # Skip stale entries: a better distance already found earlier
        if current_distance != distances[current_node]:
            continue

        # Defensive: skip if already finalized (should not normally happen)
        if current_node in finalized:
            continue

        # Finalize current_node
        finalized.add(current_node)
        nodes_visited += 1
        if max_visited is not None and nodes_visited > max_visited:
            raise CapacityError(f"Exceeded max_visited_nodes={max_visited}")

        # Early exit: target finalized => shortest path found
        if target is not None and current_node == target:
            break

        # Relax outgoing edges from current_node
        neighbors = adjacency.get(current_node, ())
        for neighbor, edge_weight in neighbors:
            # If neighbor already finalized, its shortest distance is known; skip relaxing.
            if neighbor in finalized:
                continue

            # Candidate distance if we go current_node -> neighbor
            candidate = current_distance + edge_weight

            # If we found better path to neighbor, update and push to heap
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                predecessor[neighbor] = current_node
                heapq.heappush(heap, (candidate, neighbor))
                heap_ops += 1
                if max_heap_ops is not None and heap_ops > max_heap_ops:
                    raise CapacityError(f"Exceeded max_heap_operations={max_heap_ops}")

    duration = time.monotonic() - start_time
    stats = {
        "nodes_total": nodes_total,
        "edges_total": edges_total,
        "nodes_visited": nodes_visited,
        "heap_ops": heap_ops,
        "duration_seconds": duration,
    }
    logger.debug("Dijkstra completed: %s", stats)

    return distances, predecessor, stats


# --- Utility: reconstruct path ------------------------------------------------


def reconstruct_path(predecessor: Dict[Any, Optional[Any]], source: Any, target: Any) -> List[Any]:
    """
    Reconstruct shortest path from source to target using predecessor map.
    Returns an empty list if the target is unreachable from source.
    """
    path: List[Any] = []
    node = target
    while node is not None:
        path.append(node)
        if node == source:
            break
        node = predecessor.get(node)
    path.reverse()
    if not path or path[0] != source:
        return []
    return path


# --- Example / basic self-test (executed when run directly) ------------------


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    cfg = DijkstraConfig(timeout_seconds=2.0, warn_if_large_graph=10, logger=logging.getLogger("dijkstra"))

    graph_example = {
        "nodes": [0, 1, 2, 3, 4],
        "edges": [
            {"from": 0, "to": 1, "weight": 10},
            {"from": 0, "to": 2, "weight": 3},
            {"from": 2, "to": 1, "weight": 4},
            {"from": 2, "to": 3, "weight": 2},
            {"from": 1, "to": 3, "weight": 12},
            {"from": 3, "to": 4, "weight": 7},
            {"from": 4, "to": 4, "weight": 5},  # self-loop; harmless with non-negative weight
        ],
        # "directed": True
    }

    try:
        dist_map, preds, stats = dijkstra(graph_example, source=0, target=4, config=cfg)
        print("Stats:", stats)
        print("Distances:", dist_map)
        path = reconstruct_path(preds, 0, 4)
        print("Path 0 -> 4:", path, "cost:", dist_map[4] if path else "unreachable")
    except DijkstraError as err:
        print("Search failed:", err)



