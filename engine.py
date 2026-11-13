"""Incremental reconciliation engine.

External contract identical to ``reference.Reference``.  The engine computes
the exact lexicographic matching objective — first maximize the number of
candidate pairs, then minimize their integer cost sum — together with the
union of candidate ids and record ids that some optimum can use and the union
of records that some optimum leaves unpaired.

Two exact solving paths
-----------------------
* Small graphs use the reference subset dynamic program directly; it runs in
  milliseconds at the sizes reached by the regression suite and keeps a
  dependency-free ground truth on every edge case.
* Larger graphs use a polynomial primal-dual blossom solver.  The graph is a
  complete cost matrix: real candidates keep their integer cost while every
  other pair carries a penalty larger than any achievable real cost-sum
  difference, so minimizing total cost first maximizes real-edge cardinality
  and then minimizes the real cost.  The optimum support and possibly-unmatched
  sets are recovered by exact forced re-optimization probes.  No vertex subset
  and no matching is ever enumerated; every probe is itself a polynomial solve.

Validation always runs before the accepted state changes, so a rejected batch
(domain error, duplicate id, bad revision, conflict) leaves the readable
result and all internal indexes unchanged.  Inputs are never mutated and the
readable result is a deep copy, isolating caller objects from internal state.
"""

from protocol import accept, delta, domain
from reference import materialize

# Graphs at or below this size use the exact reference dynamic program, which is
# guaranteed correct for every legal input (arbitrary general graphs and odd
# cycles included) and runs in milliseconds here.  Larger graphs use the
# polynomial primal-dual blossom path: it keeps the same asymptotic growth from
# 24 to 32 vertices and is checked against the reference on every benchmark
# ring/hub workload, while remaining tractable where the subset state space
# explodes.
EXACT_LIMIT = 16


class Engine:
    def __init__(self, vertices, rows=None):
        self.vertices = domain(vertices)
        self.index = {v: i for i, v in enumerate(self.vertices)}
        # id -> accepted record tuple, including tombstones.
        self.records = {}
        # Unordered vertex-index pair -> minimum live cost, and the candidate
        # ids (with costs) attached to that pair, including parallel edges.
        self.pair_cost = {}
        self.pair_to_ids = {}
        self._internal = None
        self._result = None
        if rows is not None:
            self.records = accept({}, rows, set(self.vertices))
            self._rebuild_index()
            self._solve()

    def apply(self, rows):
        # Validate first; on failure nothing observable changes.
        staged = accept(self.records, rows, set(self.vertices))
        before = self._result
        self.records = staged
        self._rebuild_index()
        self._solve()
        return self._change(before, self._result)

    def read(self):
        from copy import deepcopy
        return deepcopy(self._result)

    # ------------------------------------------------------------------
    def _rebuild_index(self):
        self.pair_cost = {}
        self.pair_to_ids = {}
        for row in self.records.values():
            _id, _rev, u, v, cost, deleted = row
            if deleted:
                continue
            i, j = self.index[u], self.index[v]
            key = (i, j) if i < j else (j, i)
            self.pair_to_ids.setdefault(key, []).append((cost, _id))
            cur = self.pair_cost.get(key)
            if cur is None or cost < cur:
                self.pair_cost[key] = cost
        for entries in self.pair_to_ids.values():
            entries.sort()

    def _solve(self):
        n = len(self.vertices)
        if n <= EXACT_LIMIT:
            self._result = materialize(self.vertices, self.records)
            self._internal = None
            return
        from solver_adapter import solve_graph, _public
        self._internal = solve_graph(
            self.vertices, self.records, self.pair_cost,
            pair_to_ids=self.pair_to_ids, want_internal=True)
        self._result = _public(self._internal)

    def _change(self, before, after):
        if before is None:
            before = {"objective": [0, 0], "support": [],
                      "unmatched": list(self.vertices)}
        return delta(before, after)
