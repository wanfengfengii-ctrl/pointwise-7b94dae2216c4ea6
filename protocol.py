def domain(vertices):
    vertices = tuple(vertices)
    if (any(type(x) is not str or not x for x in vertices)
            or len(set(vertices)) != len(vertices)):
        raise ValueError("DOMAIN")
    return vertices


def accept(old, rows, vertices):
    if type(rows) is not list:
        raise ValueError("ROWS")
    staged, seen = dict(old), set()
    for row in rows:
        if type(row) is not list or len(row) != 6:
            raise ValueError("ROW")
        ident, rev, a, b, cost, deleted = row
        if (type(ident) is not str or not ident or type(rev) is not int
                or rev < 1 or type(a) is not str or a not in vertices
                or type(b) is not str or b not in vertices or a == b
                or type(cost) is not int or type(deleted) is not bool):
            raise ValueError("ROW")
        if ident in seen:
            raise ValueError("DUPLICATE")
        seen.add(ident)
        value = tuple(row)
        previous = old.get(ident)
        if previous is not None and rev == previous[1] and value != previous:
            raise ValueError("REVISION_CONFLICT")
        if previous is None or rev > previous[1]:
            staged[ident] = value
    return staged


def delta(before, after):
    out = {"before": list(before["objective"]), "after": list(after["objective"])}
    for field, add, remove in (("support", "add", "remove"),
                               ("unmatched", "unmatched_add", "unmatched_remove")):
        out[add] = sorted(set(after[field]) - set(before[field]))
        out[remove] = sorted(set(before[field]) - set(after[field]))
    return out
