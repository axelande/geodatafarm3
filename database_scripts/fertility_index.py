"""Bördighetsindex built from spatially matched source values.

The calculation is deliberately independent of QGIS and the database. A
caller supplies one value per source and cell, and receives an index on a
0-100 scale plus user-adjustable classes.
"""
from math import isfinite


def _finite_values(values):
    return [float(value) for value in values
            if value is not None and isfinite(float(value))]


def percentile_ranks(values):
    """Return values on a 0-100 scale using inclusive percentile ranks."""
    clean = _finite_values(values)
    if not clean:
        return [None for _ in values]
    ordered = sorted(clean)
    if len(ordered) == 1:
        return [0.0 if value is not None else None for value in values]
    result = []
    for value in clean:
        lower = sum(item < value for item in ordered)
        equal = sum(item == value for item in ordered)
        result.append(100.0 * (lower + (equal - 1) / 2) / (len(ordered) - 1))
    ranked = iter(result)
    return [next(ranked) if value is not None and isfinite(float(value))
            else None for value in values]


def combine_sources(source_values, weights=None):
    """Combine aligned source arrays into one fertility index.

    Missing sources are ignored per cell and the remaining weights are
    renormalized. ``source_values`` maps a source name to values aligned by
    cell index. Sources are percentile-ranked before combining so yield and
    laboratory measurements can be used together.
    """
    if not source_values:
        return []
    names = list(source_values)
    lengths = {len(source_values[name]) for name in names}
    if len(lengths) != 1:
        raise ValueError('All source arrays must have the same length.')
    size = lengths.pop()
    weights = weights or {}
    ranked = {name: percentile_ranks(source_values[name]) for name in names}
    result = []
    for index in range(size):
        weighted_sum = 0.0
        weight_sum = 0.0
        for name in names:
            value = source_values[name][index]
            if value is None or not isfinite(float(value)):
                continue
            weight = float(weights.get(name, 1.0))
            if weight <= 0:
                continue
            weighted_sum += ranked[name][index] * weight
            weight_sum += weight
        result.append(weighted_sum / weight_sum if weight_sum else None)
    return result


def default_class_boundaries(class_count=5):
    """Return equal-area starting boundaries for ``class_count`` classes."""
    if not isinstance(class_count, int) or class_count < 2:
        raise ValueError('class_count must be an integer greater than 1.')
    return [100.0 * index / class_count for index in range(1, class_count)]


def classify_index(index_values, boundaries=None, class_count=5):
    """Assign classes starting at 1 using ascending index boundaries."""
    if boundaries is None:
        boundaries = default_class_boundaries(class_count)
    boundaries = [float(value) for value in boundaries]
    if any(left >= right for left, right in zip(boundaries, boundaries[1:])):
        raise ValueError('Class boundaries must be strictly increasing.')
    if any(value <= 0 or value >= 100 for value in boundaries):
        raise ValueError('Class boundaries must be between 0 and 100.')
    classes = []
    for value in index_values:
        if value is None:
            classes.append(None)
            continue
        class_number = 1
        while class_number <= len(boundaries) and value >= boundaries[class_number - 1]:
            class_number += 1
        classes.append(class_number)
    return classes