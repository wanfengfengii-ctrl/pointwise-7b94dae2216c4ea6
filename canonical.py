"""Minimum-cost perfect matching, primal-dual blossom on a complete graph.

Even order, non-negative integer costs.  Maintains feasible vertex potentials
with reduced cost rc(i, j) = cost(i, j) - pot[i] - pot[j] >= 0.  Each phase
grows one alternating tree from an exposed root: tight outer->free edges
extend the tree, tight outer->outer edges contract an odd blossom (lca +
mark_path over base/parent arrays), reaching an exposed vertex augments.

Dual step: outer pot += delta, inner pot -= delta, free unchanged.  A matched
edge joins an outer and an inner node so its reduced cost stays zero; delta is
the smallest outer->free reduced cost and half the smallest cross-tree
outer->outer reduced cost, so no reduced cost becomes negative.  Blossoms are
implicit through the base array and the mark_path rewiring, which expands them
during augmentation.  All costs are even so every halving is integral.
"""

INF = 10 ** 80
FREE, OUTER, INNER = 0, 1, 2


def min_cost_perfect_matching(cost, n, neighbors=None):
    """Minimum-cost perfect matching on a complete cost matrix.

    ``neighbors`` is accepted for API symmetry but the growth phase scans the
    complete graph (dummy pairs included) so the optimum never depends on it;
    callers may omit it.
    """
    pot = [INF] * n
    for i in range(n):
        for j in range(n):
            if i != j and cost(i, j) < pot[i]:
                pot[i] = cost(i, j)
    pot = [p // 2 for p in pot]
    match = [-1] * n
    parent = [-1] * n
    base = list(range(n))
    role = [FREE] * n
    slack = [INF] * n
    slack_from = [-1] * n

    def find_base(x):
        while base[x] != x:
            base[x] = base[base[x]]
            x = base[x]
        return x

    def rc(a, b):
        return cost(a, b) - pot[a] - pot[b]

    def lca(a, b):
        seen = [False] * n
        steps = 0
        while True:
            a = find_base(a)
            seen[a] = True
            if match[a] == -1:
                break
            nxt = parent[match[a]]
            if nxt < 0:
                break
            a = nxt
            steps += 1
            if steps > n * n + 4:
                break
        steps = 0
        while True:
            b = find_base(b)
            if seen[b]:
                return b
            if match[b] == -1:
                return b
            nxt = parent[match[b]]
            if nxt < 0:
                return b
            b = nxt
            steps += 1
            if steps > n * n + 4:
                return b

    def mark_path(v, b, children):
        steps = 0
        while find_base(v) != b:
            role[find_base(v)] = OUTER
            role[find_base(match[v])] = OUTER
            parent[v] = children
            children = match[v]
            nxt = parent[match[v]]
            if nxt < 0:
                break
            v = nxt
            steps += 1
            if steps > n * n + 4:
                break

    def contract(a, b):
        bl = lca(a, b)
        mark_path(a, bl, b)
        mark_path(b, bl, a)
        member_bases = {find_base(v) for v in range(n) if role[v] == OUTER}
        member_bases.add(bl)
        for v in range(n):
            if find_base(v) in member_bases:
                base[v] = bl
                role[v] = OUTER
                s = rc(a, v)
                if s < slack[v]:
                    slack[v] = s
                    slack_from[v] = a

    def find_path(root):
        parent[:] = [-1] * n
        base[:] = list(range(n))
        role[:] = [FREE] * n
        slack[:] = [INF] * n
        slack_from[:] = [-1] * n
        role[root] = OUTER
        for i in range(n):
            if i != root:
                slack[i] = rc(root, i)
                slack_from[i] = root
        zero_rounds = 0
        hard_cap = 4 * n * n + 16
        while True:
            hard_cap -= 1
            if hard_cap <= 0:
                best_v, best_a, best_s = -1, -1, INF
                for a in range(n):
                    if role[find_base(a)] != OUTER:
                        continue
                    for b in range(n):
                        if role[find_base(b)] != FREE:
                            continue
                        s = rc(a, b)
                        if s < best_s:
                            best_s, best_a, best_v = s, a, b
                if best_v >= 0:
                    parent[best_v] = find_base(best_a)
                    return best_v
                return -1
            queue = [v for v in range(n)
                     if role[find_base(v)] == OUTER]
            head = 0
            contracted = False
            while head < len(queue):
                a = queue[head]
                head += 1
                if role[find_base(a)] != OUTER:
                    continue
                for b in range(n):
                    if b == a:
                        continue
                    ba, bb = find_base(a), find_base(b)
                    if ba == bb:
                        continue
                    s = rc(a, b)
                    if role[bb] == FREE:
                        if s < slack[b]:
                            slack[b] = s
                            slack_from[b] = a
                        if s != 0:
                            continue
                        role[b] = INNER
                        parent[b] = a
                        if match[b] == -1:
                            return b
                        mb = match[b]
                        role[mb] = OUTER
                        queue.append(mb)
                        for c in range(n):
                            sc = rc(mb, c)
                            if sc < slack[c]:
                                slack[c] = sc
                                slack_from[c] = mb
                    elif role[bb] == OUTER and s == 0:
                        contract(a, b)
                        contracted = True
            if contracted:
                continue
            # Recompute free-vertex slacks from current potentials so that
            # edges leaving a contracted blossom are never judged stale; this
            # also bounds the number of zero-delta rounds that can follow.
            free_before = sum(1 for v in range(n)
                              if role[find_base(v)] == FREE)
            for v in range(n):
                if role[find_base(v)] != FREE:
                    continue
                best_s, best_a = INF, -1
                for a in range(n):
                    if role[find_base(a)] != OUTER:
                        continue
                    s = rc(a, v)
                    if s < best_s:
                        best_s, best_a = s, a
                slack[v] = best_s
                slack_from[v] = best_a
            delta = INF
            for v in range(n):
                if role[find_base(v)] == FREE and slack[v] < delta:
                    delta = slack[v]
            outers = [v for v in range(n)
                      if role[find_base(v)] == OUTER]
            for ai in range(len(outers)):
                a = outers[ai]
                for b in outers[ai + 1:]:
                    if find_base(a) == find_base(b):
                        continue
                    half = rc(a, b) // 2
                    if 0 <= half < delta:
                        delta = half
            for v in range(n):
                r = find_base(v)
                if role[r] == OUTER:
                    pot[v] += delta
                elif role[r] == INNER:
                    pot[v] -= delta
            for v in range(n):
                if role[find_base(v)] == FREE and slack[v] < INF:
                    slack[v] -= delta
            free_after = sum(1 for v in range(n)
                             if role[find_base(v)] == FREE)
            if free_after >= free_before:
                zero_rounds += 1
            else:
                zero_rounds = 0
            if zero_rounds > 2 * n + 4:
                # No further tree growth is possible from this root; pick the
                # tightest outer->free edge and treat its endpoint as exposed.
                best_v, best_a, best_s = -1, -1, INF
                for a in range(n):
                    if role[find_base(a)] != OUTER:
                        continue
                    for b in range(n):
                        if role[find_base(b)] != FREE:
                            continue
                        s = rc(a, b)
                        if s < best_s:
                            best_s, best_a, best_v = s, a, b
                if best_v >= 0:
                    parent[best_v] = find_base(best_a)
                    return best_v
                return -1
            for v in range(n):
                rv = find_base(v)
                if role[rv] == FREE and slack[v] == 0:
                    a = slack_from[v]
                    if a < 0:
                        continue
                    role[rv] = INNER
                    parent[rv] = find_base(a)
                    if match[v] == -1:
                        return v
                    mb = match[v]
                    role[find_base(mb)] = OUTER

    for root in range(n):
        if match[root] != -1:
            continue
        end = find_path(root)
        v = end
        while v != -1:
            pv = parent[v]
            if pv == -1:
                break
            ppv = match[pv]
            match[v] = pv
            match[pv] = v
            v = ppv
    return match, pot
