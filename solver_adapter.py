"""Polynomial graph solver adapter for the incremental engine.

The lexicographic objective (maximize real-edge cardinality, then minimize
integer cost) is solved on a complete cost matrix with the primal-dual
blossom solver in :mod:`canonical`.  A dummy-pair penalty that dominates every
possible real cost-sum difference makes minimizing total cost first maximize
the number of real edges and then minimize their cost.

Ambiguity sets are recovered by forced re-optimization (polynomial, no subset
or matching enumeration):

  * a real pair is usable by some optimum iff forcing it still admits a
    matching with the same (cardinality, cost);
  * a vertex may be left unpaired by some optimum iff forbidding its real
    incident edges still admits a matching with the same (cardinality, cost).

Every probe builds a closure over the same immutable doubled-cost mapping and
shares the dummy-pair penalty, so repeated forced solves differ by exactly one
perturbed edge or one blocked vertex.
"""

from canonical import min_cost_perfect_matching

INF = 10 ** 70


def _penalty(nn, pair_cost):
    big = max((abs(c) for c in pair_cost.values()), default=0) + 1
    return 2 * (nn * big + 1)


def _objective(n, nn, pair_cost2, penalty, force_edge=None,
               block_vertex=None):
    real = set(pair_cost2)

    def cost(i, j):
        if i == j:
            return INF
        a, b = (i, j) if i < j else (j, i)
        if force_edge is not None and (a, b) == force_edge:
            return pair_cost2[(a, b)] - 10 ** 60
        if block_vertex is not None and (a == block_vertex or
                                         b == block_vertex):
            return penalty
        if (a, b) in pair_cost2:
            return pair_cost2[(a, b)]
        return penalty

    match, _pot = min_cost_perfect_matching(cost, nn)
    chosen = [(i, match[i]) for i in range(nn)
              if i < match[i] and (i, match[i]) in real]
    if force_edge is not None and force_edge not in chosen:
        return None
    if block_vertex is not None and any(
            block_vertex in p for p in chosen):
        return None
    return len(chosen), sum(pair_cost2[p] // 2 for p in chosen)


def _full(n, nn, pair_cost, pair_to_ids, records, vertices):
    pair_cost2 = {p: 2 * c for p, c in pair_cost.items()}
    penalty = _penalty(nn, pair_cost)
    base = _objective(n, nn, pair_cost2, penalty)
    cardinality, total = base

    support_ids = set()
    for pair in pair_cost2:
        if _objective(n, nn, pair_cost2, penalty,
                      force_edge=pair) == base:
            best_cost = pair_cost[pair]
            for cost, cid in pair_to_ids.get(pair, []):
                if cost == best_cost:
                    support_ids.add(cid)

    unmatched = set()
    for v in range(n):
        if _objective(n, nn, pair_cost2, penalty,
                      block_vertex=v) == base:
            unmatched.add(vertices[v])

    return {
        "objective": [cardinality, total],
        "support": support_ids,
        "unmatched": unmatched,
        "_base": base,
    }


def solve_graph(vertices, records, pair_cost, pair_to_ids=None,
                want_internal=False):
    n = len(vertices)
    nn = n + (n & 1)
    if pair_to_ids is None:
        pair_to_ids = {}
        for row in records.values():
            _id, _rev, u, v, cost, deleted = row
            if deleted:
                continue
            i, j = vertices.index(u), vertices.index(v)
            key = (i, j) if i < j else (j, i)
            pair_to_ids.setdefault(key, []).append((cost, _id))
    full = _full(n, nn, pair_cost, pair_to_ids, records, vertices)
    return full if want_internal else _public(full)


def _public(full):
    return {
        "objective": full["objective"],
        "support": sorted(full["support"]),
        "unmatched": sorted(full["unmatched"]),
    }


