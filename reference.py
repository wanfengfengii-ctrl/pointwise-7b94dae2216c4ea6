from copy import deepcopy
from functools import lru_cache
from protocol import domain, accept, delta


def materialize(vertices, records):
    index = {v: i for i, v in enumerate(vertices)}
    adjacency = [[] for _ in vertices]
    for row in records.values():
        if not row[5]:
            a, b = index[row[2]], index[row[3]]
            adjacency[a].append((b, row[0], row[4]))
            adjacency[b].append((a, row[0], row[4]))

    @lru_cache(None)
    def solve(mask):
        if not mask:
            return (0, 0)
        bit = mask & -mask
        i = bit.bit_length() - 1
        rest = mask ^ bit
        best = solve(rest)  # leave this vertex unmatched
        for j, ident, cost in adjacency[i]:
            if rest & (1 << j):
                count, total = solve(rest ^ (1 << j))
                candidate = (count - 1, total + cost)
                if candidate < best:
                    best = candidate
        return best

    full = (1 << len(vertices)) - 1
    best = solve(full)
    support, unmatched, seen = set(), set(), set()
    pending = [full]
    # Visit optimal states, never enumerate complete matchings.
    while pending:
        mask = pending.pop()
        if not mask or mask in seen:
            continue
        seen.add(mask)
        bit = mask & -mask
        i = bit.bit_length() - 1
        rest = mask ^ bit
        value = solve(mask)
        if solve(rest) == value:
            unmatched.add(vertices[i])
            pending.append(rest)
        for j, ident, cost in adjacency[i]:
            if rest & (1 << j):
                child = rest ^ (1 << j)
                count, total = solve(child)
                if (count - 1, total + cost) == value:
                    support.add(ident)
                    pending.append(child)
    return {"objective": [-best[0], best[1]], "support": sorted(support),
            "unmatched": sorted(unmatched)}


class Reference:
    def __init__(self, vertices, rows=None):
        self.vertices = domain(vertices)
        self.records = accept({}, [] if rows is None else rows, set(self.vertices))
        self.result = materialize(self.vertices, self.records)

    def read(self):
        return deepcopy(self.result)

    def apply(self, rows):
        staged = accept(self.records, rows, set(self.vertices))
        result = materialize(self.vertices, staged)
        change = delta(self.result, result)
        self.records, self.result = staged, result
        return change
