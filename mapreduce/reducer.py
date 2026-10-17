#!/usr/bin/env python3
"""Input sorted by key; emit count, sum and mean without buffering a group."""
import itertools
import math
import sys


def reduce_rows(source, destination):
    records = (line.rstrip("\n").split("\t") for line in source)
    for key, group in itertools.groupby(records, key=lambda record: record[0]):
        count = 0

        def values():
            nonlocal count
            for record in group:
                if len(record) != 3:
                    raise ValueError("Expected key, sum, count")
                value, n = float(record[1]), int(record[2])
                if not math.isfinite(value) or n < 1:
                    raise ValueError("Invalid partial aggregate")
                count += n
                yield value

        total = math.fsum(values())
        print(f"{key}\t{count}\t{total!r}\t{total / count!r}", file=destination)


if __name__ == "__main__":
    reduce_rows(sys.stdin, sys.stdout)
