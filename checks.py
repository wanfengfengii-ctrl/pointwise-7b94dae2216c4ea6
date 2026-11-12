import gc
import json
import random
import statistics
import sys
import time
import tracemalloc
from engine import Engine
from reference import Reference
from samples import example, workload


def brute(vertices, rows):
    edges = [e for e in rows if not e[5]]
    best, solutions = None, []

    def walk(i, used, selected, cost):
        nonlocal best, solutions
        if i == len(edges):
            rank = (-len(selected), cost)
            if best is None or rank < best:
                best, solutions = rank, [tuple(selected)]
            elif rank == best:
                solutions.append(tuple(selected))
            return
        walk(i + 1, used, selected, cost)
        e = edges[i]
        if e[2] not in used and e[3] not in used:
            walk(i + 1, used | {e[2], e[3]}, selected + [e], cost + e[4])

    walk(0, set(), [], 0)
    return {"objective": [-best[0], best[1]],
            "support": sorted({e[0] for s in solutions for e in s}),
            "unmatched": sorted({v for s in solutions for v in vertices
                                 if not any(v in e[2:4] for e in s)})}


def expected_delta(a, b):
    out = {"before": a["objective"], "after": b["objective"]}
    for name, p, q in (("support", "add", "remove"),
                       ("unmatched", "unmatched_add", "unmatched_remove")):
        out[p] = sorted(set(b[name]) - set(a[name]))
        out[q] = sorted(set(a[name]) - set(b[name]))
    return out


def normal():
    vertices, rows = example()
    obj = Engine(vertices, rows)
    assert obj.read() == {"objective": [1, 0], "support": ["ab", "ac", "bc"],
                         "unmatched": ["a", "b", "c", "isolated"]}
    change = [["ab", 2, "a", "b", -1, False]]
    assert obj.apply(change)["remove"] == ["ac", "bc"]
    assert obj.read()["unmatched"] == ["c", "isolated"]
    zero = obj.apply(change)
    assert not zero["add"] and not zero["remove"]
    copy = obj.read()
    copy["support"].clear()
    assert obj.read()["support"] == ["ab"]
    before = obj.read()
    try:
        obj.apply([["bc", 2, "b", "c", -9, False],
                   ["ab", 2, "a", "b", 7, False]])
    except ValueError as exc:
        assert str(exc) == "REVISION_CONFLICT"
    else:
        raise AssertionError("accepted conflict")
    assert obj.read() == before
    assert obj.apply([rows[0]])["after"] == before["objective"]
    for invalid in ([["x", True, "a", "b", 0, False]],
                    [["x", 1, "a", "b", True, False]],
                    [["x", 1, "bad", "b", 0, False]],
                    [["x", 1, "a", "a", 0, False]],
                    [["x", 1, "a", "b", 0, 0]],
                    [["x", 1, "a", "b", 0, False]] * 2):
        try:
            obj.apply(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted invalid row")
        assert obj.read() == before
    # Overlapping odd cycles, parallel provenance and a cardinality-changing bridge.
    vertices = ["n%d" % i for i in range(9)]
    pairs = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 0),
             (4, 5), (5, 6), (6, 1), (6, 7), (0, 1)]
    rows = [["p%d" % i, 1, vertices[a], vertices[b], 0, False]
            for i, (a, b) in enumerate(pairs)]
    records = {e[0]: e for e in rows}
    obj = Engine(vertices, rows)
    assert obj.read() == brute(vertices, rows)
    for batch in ([["p0", 2, "n0", "n1", -(2 ** 90), False]],
                  [["p9", 2, "n6", "n7", 0, True]],
                  [["p9", 3, "n7", "n8", 2 ** 90, False]],
                  [["p0", 3, "n0", "n1", 0, False],
                   ["p10", 2, "n3", "n8", -1, False]]):
        old = brute(vertices, list(records.values()))
        for row in batch:
            records[row[0]] = row
        new = brute(vertices, list(records.values()))
        assert obj.apply(batch) == expected_delta(old, new)
        assert obj.read() == new
    rng = random.Random(719)
    vertices = ["a", "b", "c", "d", "e", "isolated"]
    objects = [Reference(vertices), Engine(vertices)]
    records = {}
    for step in range(90):
        batch = []
        for ident in rng.sample(["e%d" % i for i in range(9)], rng.randint(1, 3)):
            previous = records.get(ident)
            rev = previous[1] + 1 if previous else 1
            a, b = rng.sample(vertices[:-1], 2)
            batch.append([ident, rev, a, b, rng.randint(-7, 7), rng.random() < .25])
        old = brute(vertices, list(records.values()))
        for row in batch:
            records[row[0]] = row
        new = brute(vertices, list(records.values()))
        for obj in objects:
            assert obj.apply(batch) == expected_delta(old, new), (step, batch)
            assert obj.read() == new, (step, batch)
    print("NORMAL_REGRESSION_OK")


def run_timed(cls, data):
    vertices, rows, batches = data
    obj = cls(vertices, rows)
    elapsed, results = [], []
    for batch in batches:
        gc.collect()
        start = time.perf_counter()
        value = obj.apply(batch)
        elapsed.append(time.perf_counter() - start)
        results.append((value, obj.read()))
    return elapsed, results


def bench(target=False):
    reports, passed = [], True
    for family in ("ring", "hub"):
        medians = {}
        for n in (24, 32):
            data = workload(family, n)
            ref_times, eng_times = [], []
            for trial in range(3):
                classes = (Reference, Engine) if trial % 2 == 0 else (Engine, Reference)
                measured = {cls: run_timed(cls, data) for cls in classes}
                rt, rr = measured[Reference]
                et, er = measured[Engine]
                assert rr == er, (family, n, trial)
                ref_times.append(rt)
                eng_times.append(et)
            rm = [statistics.median(x) for x in zip(*ref_times)]
            em = [statistics.median(x) for x in zip(*eng_times)]
            ratio = [e / max(r, 1e-12) for e, r in zip(em, rm)]
            medians[n] = em
            tracemalloc.start()
            vertices, rows, batches = data
            obj = Engine(vertices, rows)
            for batch in batches:
                obj.apply(batch)
            peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            reports.append({"family": family, "n": n, "reference_seconds": rm,
                            "engine_seconds": em, "ratios": ratio, "peak_bytes": peak})
            passed = passed and max(ratio) <= 1 / 12 and peak <= 64 * 1024 * 1024
        growth = [b / max(a, 1e-12) for a, b in zip(medians[24], medians[32])]
        reports.append({"family": family, "growth_ratios": growth})
        passed = passed and max(growth) <= 6
    print(json.dumps(reports, sort_keys=True))
    if target and not passed:
        print("OPTIMIZATION_TARGET_MISSED")
        return 1
    print("PERFORMANCE_BASELINE_OK" if not target else "OPTIMIZATION_TARGET_OK")
    return 0


def demo():
    vertices, rows = example()
    obj = Engine(vertices, rows)
    print(json.dumps({"initial": obj.read()}, ensure_ascii=False))
    change = obj.apply([["ab", 2, "a", "b", -1, False]])
    print(json.dumps({"change": change, "final": obj.read()}, ensure_ascii=False))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "normal"
    if mode == "normal":
        normal()
    elif mode in ("bench", "target"):
        if mode == "target":
            normal()
        sys.exit(bench(mode == "target"))
    elif mode == "demo":
        demo()
    else:
        raise SystemExit("unknown mode")
