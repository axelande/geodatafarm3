"""Minimal statistics for the paper scripts when scipy is not installed in
the QGIS Python (it is not, as of OSGeo4W 2026-09). Each function returns
the same (statistic, pvalue) shape as its scipy.stats counterpart, and the
scripts use scipy when it is importable.

Spearman: Pearson correlation of average ranks; p-value from the t
approximation. Kruskal-Wallis: H with tie correction; p-value from the
chi-square survival function via the regularised upper incomplete gamma.
Wilcoxon signed-rank: normal approximation with tie correction, two-sided.
"""
import math
from collections import namedtuple

Result = namedtuple('Result', ['statistic', 'pvalue'])


def _average_ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _tie_groups(values):
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return [c for c in counts.values() if c > 1]


def _regularized_gamma_q(a, x):
    """Q(a, x) = 1 - P(a, x), Numerical Recipes series / continued fraction."""
    if x <= 0:
        return 1.0
    if x < a + 1:
        # series for P
        term = 1.0 / a
        total = term
        n = a
        for _ in range(500):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-14:
                break
        p = total * math.exp(-x + a * math.log(x) - math.lgamma(a))
        return max(0.0, 1.0 - p)
    # continued fraction for Q
    b = x + 1 - a
    c = 1e300
    d = 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-14:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(x, df):
    return _regularized_gamma_q(df / 2.0, x / 2.0)


def _norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def _t_sf(t, df):
    """Two-sided p for Student t via the regularised incomplete beta
    (continued fraction); adequate for df >= 3."""
    x = df / (df + t * t)
    a, b = df / 2.0, 0.5
    # Lentz continued fraction for I_x(a, b)
    def betacf(a, b, x):
        qab, qap, qam = a + b, a + 1, a - 1
        c, d = 1.0, 1 - qab * x / qap
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        h = d
        for m in range(1, 300):
            m2 = 2 * m
            aa = m * (b - m) * x / ((qam + m2) * (a + m2))
            d = 1 + aa * d
            d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
            c = 1 + aa / (c if abs(c) > 1e-300 else 1e-300)
            h *= d * c
            aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
            d = 1 + aa * d
            d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
            c = 1 + aa / (c if abs(c) > 1e-300 else 1e-300)
            delta = d * c
            h *= delta
            if abs(delta - 1) < 1e-14:
                break
        return h
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta)
    if x < (a + 1) / (a + b + 2):
        ib = front * betacf(a, b, x) / a
    else:
        ib = 1 - front * betacf(b, a, 1 - x) / b
    return ib  # already two-sided for the t distribution


def spearmanr(x, y):
    rx, ry = _average_ranks(list(x)), _average_ranks(list(y))
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return Result(float('nan'), float('nan'))
    rho = sxy / math.sqrt(sxx * syy)
    if n < 4 or abs(rho) >= 1:
        return Result(rho, 0.0 if abs(rho) >= 1 else float('nan'))
    t = rho * math.sqrt((n - 2) / (1 - rho * rho))
    return Result(rho, _t_sf(t, n - 2))


def kruskal(*groups):
    data = [v for g in groups for v in g]
    n = len(data)
    ranks = _average_ranks(data)
    h, start = 0.0, 0
    for g in groups:
        k = len(g)
        rsum = sum(ranks[start:start + k])
        h += rsum * rsum / k
        start += k
    h = 12.0 / (n * (n + 1)) * h - 3 * (n + 1)
    ties = _tie_groups(data)
    correction = 1 - sum(t ** 3 - t for t in ties) / (n ** 3 - n)
    if correction > 0:
        h /= correction
    return Result(h, chi2_sf(h, len(groups) - 1))


def wilcoxon(x, y):
    diffs = [a - b for a, b in zip(x, y) if a != b]
    n = len(diffs)
    if n == 0:
        return Result(0.0, 1.0)
    ranks = _average_ranks([abs(d) for d in diffs])
    w_plus = sum(r for r, d in zip(ranks, diffs) if d > 0)
    w_minus = sum(r for r, d in zip(ranks, diffs) if d < 0)
    w = min(w_plus, w_minus)
    mean = n * (n + 1) / 4
    ties = _tie_groups([abs(d) for d in diffs])
    var = n * (n + 1) * (2 * n + 1) / 24 - sum(t ** 3 - t for t in ties) / 48
    if var <= 0:
        return Result(w, 1.0)
    z = (w - mean) / math.sqrt(var)
    return Result(w, min(1.0, 2 * _norm_sf(abs(z))))
