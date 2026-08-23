"""Coarse soil-water estimate for the advanced fertilizer-timing model.

GeoDataFarm only collects clay% and organic-matter (humus) % per field (see
``soil.manual`` in database_scripts/create_new_farm.py), not sand% or bulk
density, so this uses a simple texture-class interpolation rather than a full
pedotransfer function such as Saxton & Rawls (2006), which needs sand%.
Treat the result as a rough planning estimate, not a lab-measured value -
swap in a proper pedotransfer function or a SoilGrids lookup if/when that
data becomes available.
"""

__author__ = 'Axel Horteborn'

# (clay_pct, field_capacity_fraction, wilting_point_fraction) reference
# points, adapted from commonly cited approximate volumetric water contents
# by texture class (coarse -> fine).
_CLAY_BREAKPOINTS = [
    (5.0, 0.10, 0.03),
    (10.0, 0.15, 0.05),
    (20.0, 0.22, 0.08),
    (30.0, 0.28, 0.12),
    (40.0, 0.34, 0.18),
    (60.0, 0.38, 0.22),
]

# Each 1% organic matter adds a little water-holding capacity, capped so a
# very peaty sample doesn't dominate the estimate.
_OM_FC_BONUS_PER_PCT = 0.007
_OM_FC_BONUS_CAP = 0.03


def field_capacity_and_wilting_point(clay_pct, organic_matter_pct=0.0):
    """Estimates field capacity and wilting point from clay% (+ organic matter%).

    Parameters
    ----------
    clay_pct: float
        Percent clay, 0-100.
    organic_matter_pct: float, optional
        Percent organic matter/humus, 0-100.

    Returns
    -------
    tuple[float, float]
        ``(field_capacity, wilting_point)`` as volumetric water fractions
        (mm water held per mm of soil depth).
    """
    clay_pct = max(0.0, min(100.0, clay_pct))
    points = _CLAY_BREAKPOINTS
    if clay_pct <= points[0][0]:
        fc, wp = points[0][1], points[0][2]
    elif clay_pct >= points[-1][0]:
        fc, wp = points[-1][1], points[-1][2]
    else:
        fc, wp = points[-1][1], points[-1][2]
        for (c0, fc0, wp0), (c1, fc1, wp1) in zip(points, points[1:]):
            if c0 <= clay_pct <= c1:
                frac = (clay_pct - c0) / (c1 - c0)
                fc = fc0 + frac * (fc1 - fc0)
                wp = wp0 + frac * (wp1 - wp0)
                break
    om_bonus = min(_OM_FC_BONUS_CAP,
                   max(0.0, organic_matter_pct) * _OM_FC_BONUS_PER_PCT)
    return fc + om_bonus, wp


def available_water_capacity(clay_pct, organic_matter_pct=0.0):
    """Plant-available water per mm of soil depth (field capacity minus
    wilting point), floored just above zero so callers never divide by zero."""
    fc, wp = field_capacity_and_wilting_point(clay_pct, organic_matter_pct)
    return max(0.01, fc - wp)
