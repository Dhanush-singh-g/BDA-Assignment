#!/usr/bin/env python3
"""Nutrient totals by food type and nutrient ID. Input: prepared nutrient TSV."""
import math
import sys


def map_rows(source, destination):
    for number, line in enumerate(source, 1):
        fields = line.rstrip("\n").split("\t")
        if len(fields) != 7:
            raise ValueError(f"Expected 7 fields at line {number}")
        _, kind, _, nutrient_id, _, _, amount = fields
        value = float(amount)
        int(nutrient_id)
        if not math.isfinite(value):
            raise ValueError(f"Nonfinite amount at line {number}")
        if value < 0:
            print("reporter:counter:FoodData,NegativeAmountsFiltered,1", file=sys.stderr)
            continue
        print(f"{kind}|{nutrient_id}\t{value!r}\t1", file=destination)


if __name__ == "__main__":
    map_rows(sys.stdin, sys.stdout)
