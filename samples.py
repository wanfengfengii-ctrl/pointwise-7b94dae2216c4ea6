def example():
    return (["a", "b", "c", "isolated"],
            [["ab", 1, "a", "b", 0, False],
             ["ac", 1, "a", "c", 0, False],
             ["bc", 1, "b", "c", 0, False]])


def workload(family, n):
    names = ["v%03d" % i for i in range(n)]
    # Vertex identity order is not graph order: a realistic mixed-source export.
    vertices = names[::2] + names[1::2]
    rows = [["e%d" % i, 1, names[i], names[(i + 1) % n], 0, False]
            for i in range(n)]
    if family == "hub":
        rows += [["h%d" % i, 1, names[0], names[i], 0, False]
                 for i in range(2, n - 1)]
    else:
        rows += [["chord", 1, names[0], names[2], 0, False],
                 ["parallel", 1, names[0], names[1], 0, False]]
    batches = [
        [["e0", 2, names[0], names[1], -1, False]],
        [["e0", 3, names[0], names[1], 0, False]],
        [["e0", 4, names[0], names[1], 0, True]],
        [["e0", 5, names[0], names[1], 0, False]],
        [["e0", 6, names[0], names[n // 2], -2, False],
         ["e1", 2, names[1], names[3], -1, False]],
        [["e0", 7, names[0], names[1], 0, False],
         ["e1", 3, names[1], names[2], 0, False]],
    ]
    return vertices, rows, batches
