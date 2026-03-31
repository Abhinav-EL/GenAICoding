"""
GPT 4o AI Prompts:

***** FIRST Prompt -
Lets implement a Traveling Salesman Problem implementation where our Travel Agency needs to find the shortest route that 
allows costumers to visit all countries and return back to the starting country. Continue with the same role and standard 
of code as the previous implementation.

The method call will look this --
def optimize_world_tour(graph_json, start_node):  Returns: list of nodes representing the tour (including return to start) 
Example: [0, 1, 2, 11, 12, 9, ..., 0]

***** SECOND Prompt -
Let's simplify this implementation for maintainability and efficiency. The size of graph will be about 15 countries

- Have only one implementation: greedy algorithm called Nearest Neighbor.
- Remove main function. Instead only provide the implementation and a Test Case that tests it.
- Use clearer variable names. Also, visit countries only once.
"""

"""
Simplified TSP (Nearest Neighbor) for a travel-agency use case.

- Single algorithm: greedy Nearest Neighbor on the metric closure (shortest-path distances).
- Target graph size: ~15 nodes (countries). Efficient and easy to maintain.
- Visits each country exactly once and returns to the start.

Function:
    optimize_world_tour(graph_json, start_node) -> List[node_ids]

Test cases: pytest-style functions at the bottom. They check correctness properties
(runs, visits all nodes exactly once, returns to start) and unreachable-node behavior.
"""

import heapq
import math
import time
from typing import Any, Dict, List, Tuple


# ----------------------------
# Helpers
# ----------------------------
def _build_adjacency(graph_json: Dict[str, Any]) -> Dict[Any, List[Tuple[Any, float]]]:
    """
    Build adjacency list from graph_json. Validates weights are numeric and non-negative.
    Undirected by default (adds reverse edges).
    """
    nodes_iter = graph_json.get("nodes", None)
    edges = graph_json.get("edges", [])
    directed = bool(graph_json.get("directed", False))

    # Initialize node set (allow nodes introduced by edges)
    node_set = set(nodes_iter) if nodes_iter is not None else set()
    for edge in edges:
        if not isinstance(edge, dict) or "from" not in edge or "to" not in edge or "weight" not in edge:
            raise ValueError(f"Invalid edge entry (expected dict with from/to/weight): {edge!r}")
        node_set.add(edge["from"])
        node_set.add(edge["to"])

    # Build adjacency lists
    adjacency = {node: [] for node in node_set}
    for edge in edges:
        frm = edge["from"]
        to = edge["to"]
        try:
            weight = float(edge["weight"])
        except Exception:
            raise ValueError(f"Edge weight not numeric: {edge!r}")
        if weight < 0:
            raise ValueError("Negative edge weights are not supported")
        adjacency[frm].append((to, weight))
        if not directed:
            adjacency[to].append((frm, weight))

    return adjacency


def _dijkstra(adj: Dict[Any, List[Tuple[Any, float]]], source: Any) -> Dict[Any, float]:
    """
    Simple Dijkstra single-source. Returns mapping node -> shortest distance from source.
    Assumes non-negative edge weights.
    """
    distances = {node: math.inf for node in adj}
    distances[source] = 0.0
    heap: List[Tuple[float, Any]] = [(0.0, source)]
    while heap:
        current_distance, node = heapq.heappop(heap)
        # Skip stale entry
        if current_distance != distances[node]:
            continue
        for neighbor, weight in adj[node]:
            candidate = current_distance + weight
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                heapq.heappush(heap, (candidate, neighbor))
    return distances


# ----------------------------
# Main function: Nearest Neighbor TSP
# ----------------------------
def optimize_world_tour(graph_json: Dict[str, Any], start_node: Any) -> List[Any]:
    """
    Find a tour visiting every node exactly once (greedy nearest-neighbor), and return to start.

    Parameters:
      - graph_json: {
            "nodes": [ ... ]             # optional
            "edges": [{"from": u, "to": v, "weight": w}, ...],
            "directed": False            # optional
        }
      - start_node: node id to start/end the tour (must exist in the graph)

    Returns:
      - tour: list of node ids including final return to start, e.g. [0, 2, 1, 3, 0]

    Raises:
      - ValueError: if input invalid or if the graph is not (strongly) connected so a full tour is impossible.
    """
    if not isinstance(graph_json, dict):
        raise ValueError("graph_json must be a dict")

    # Build adjacency and validate
    adjacency = _build_adjacency(graph_json)

    if start_node not in adjacency:
        raise ValueError(f"start_node {start_node!r} not found in graph")

    nodes = list(adjacency.keys())
    node_count = len(nodes)
    if node_count == 0:
        return []
    if node_count == 1:
        return [start_node, start_node]

    # Compute all-pairs shortest-path distances (metric closure)
    # For each node, run Dijkstra (acceptable for ~15 nodes)
    distances_map: Dict[Any, Dict[Any, float]] = {}
    for node in nodes:
        distances_map[node] = _dijkstra(adjacency, node)

    # Verify full connectivity: every pair must be reachable
    for a in nodes:
        for b in nodes:
            if a == b:
                continue
            d = distances_map[a].get(b, math.inf)
            if not math.isfinite(d):
                raise ValueError(f"No route from {a!r} to {b!r}; full tour impossible")

    # Map node ids to indices for deterministic tie-breaking (optional)
    node_to_index = {node: idx for idx, node in enumerate(sorted(nodes))}

    # Nearest Neighbor greedy tour (operates on metric closure)
    tour: List[Any] = [start_node]
    visited = {start_node}
    current_node = start_node

    while len(tour) < node_count:
        # Find nearest unvisited node by (distance, tie-breaker index)
        best_candidate = None
        best_distance = math.inf
        best_tiebreak = None
        for candidate in nodes:
            if candidate in visited:
                continue
            dist = distances_map[current_node][candidate]
            # tie-breaker: deterministic by node index (helps tests and reproducibility)
            tiebreak = node_to_index[candidate]
            if dist < best_distance or (dist == best_distance and (best_tiebreak is None or tiebreak < best_tiebreak)):
                best_distance = dist
                best_candidate = candidate
                best_tiebreak = tiebreak

        if best_candidate is None:
            # Shouldn't happen because we checked connectivity, but guard defensively
            raise ValueError("Failed to find next node in greedy selection; aborted")

        tour.append(best_candidate)
        visited.add(best_candidate)
        current_node = best_candidate

    # Return to start
    tour.append(start_node)

    # Final sanity checks
    assert len(tour) == node_count + 1
    assert tour[0] == tour[-1] == start_node
    assert set(tour[:-1]) == set(nodes)

    return tour


# ----------------------------
# Tests (pytest-style)
# ----------------------------
def test_optimize_world_tour_basic():
    """
    Simple 4-node complete graph. Verify tour visits each node exactly once and returns to start.
    """
    graph = {
        "nodes": [0, 1, 2, 3],
        "edges": [
            {"from": 0, "to": 1, "weight": 10},
            {"from": 0, "to": 2, "weight": 15},
            {"from": 0, "to": 3, "weight": 20},
            {"from": 1, "to": 2, "weight": 35},
            {"from": 1, "to": 3, "weight": 25},
            {"from": 2, "to": 3, "weight": 30},
        ],
        # undirected by default
    }
    start = 0
    tour = optimize_world_tour(graph, start)
    # Structural checks
    assert tour[0] == start and tour[-1] == start
    assert len(tour) == len(graph["nodes"]) + 1
    visited_once = tour[:-1]
    assert set(visited_once) == set(graph["nodes"])
    assert len(visited_once) == len(set(visited_once))


def test_optimize_world_tour_unreachable():
    """
    Graph where node 2 is isolated -> should raise ValueError because full tour impossible.
    """
    graph = {
        "nodes": [0, 1, 2],
        "edges": [
            {"from": 0, "to": 1, "weight": 5},
            # node 2 has no edges
        ],
    }
    start = 0
    try:
        optimize_world_tour(graph, start)
    except ValueError as exc:
        assert "full tour impossible" in str(exc) or "No route" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unreachable node")


# Note:
# - To run tests: save this file as tsp_nn.py and run `pytest tsp_nn.py` (or run the test functions manually).
