import re
import socket
import webbrowser
import time
from collections import Counter
from datetime import datetime, timedelta

from psycopg2 import sql as pgsql
import matplotlib as mpl
from matplotlib import pyplot as _plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas)
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
from shapely import wkt as shapely_wkt
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox, QHBoxLayout, QPushButton, QTableWidgetItem, QWidget)
from qgis.core import QgsApplication, QgsTask

from dataclasses import dataclass, field
from dataclasses import replace as dataclasses_replace

from ..widgets.crop_simulation_page import CropSimulationPage
from ..widgets.crop_settings_dialog import CropSettingsDialog
from ..support_scripts.__init__ import check_text, db_rows, TR, isfloat
from ..support_scripts.notifier import report_warning, report_error, report_success
from ..support_scripts.notifier import log as gdf_log
from ..support_scripts.license_client import LicenseClient, LicenseError
from ..support_scripts.open_meteo_client import OpenMeteoClient, OpenMeteoError
from ..support_scripts.fertilizer_timing_model import (
    ADVANCED_HORIZON_DAYS, DailyWeather, FertilizerEvent, analyse_events,
    summarize)
from ..support_scripts.season_water_model import (
    daily_trace_with_relative_yield, estimate_season)
from ..support_scripts import crop_model_settings
from ..support_scripts import crop_models
from ..support_scripts import field_grid
from .db import ensure_ferti_nutrient_column

__author__ = 'Axel Horteborn'

# This module never calls pyplot itself (_render_heatmap/_render_curve_
# chart below both use a bare Figure(), never plt.figure()/subplots()),
# but pyplot's *interactive mode* is process-wide global state - if
# anything else already loaded into this QGIS session imports pyplot and
# leaves interactive mode on (database_scripts/mean_analyse.py does, via
# plt.subplots()), a freshly created Figure/FigureCanvas can still end up
# auto-shown as its own top-level window instead of staying embedded,
# purely because interactive mode happened to be on when it was drawn -
# not something this module's own (pyplot-free) code controls otherwise.
# ioff() just flips that one global flag back off; it doesn't create or
# track a figure, so it doesn't reintroduce the leak pyplot.figure()/
# subplots() would.
_plt.ioff()

# Where the Pro license key/activation instance id are stored in QSettings.
LICENSE_KEY_SETTING = "geodatafarm/pro_license_key"
LICENSE_INSTANCE_SETTING = "geodatafarm/pro_license_instance_id"
LICENSE_LAST_VALIDATED_SETTING = "geodatafarm/pro_license_last_validated"
LICENSE_OFFLINE_GRACE_SECONDS = 14 * 24 * 60 * 60
# Manual developer escape hatch - see is_licensed()'s docstring.
DEV_BYPASS_LICENSE_SETTING = "geodatafarm/dev_bypass_license"
PRO_LICENSE_CHECKOUT_URL = "https://geodatafarm.lemonsqueezy.com/checkout/buy/d4ac5d92-d55b-4798-b764-8faff5493c69?media=0&logo=0&discount=0"

_RISK_COLORS = {'low': 'green', 'moderate': 'orange', 'high': 'red',
                'unknown': 'gray'}
_SELECT_CROP = '--- Select crop ---'
# Trailing item in CBCrop - picking it reveals page.CBCropOther (a plain
# QLineEdit) for typing a crop name that isn't otherwise listed, instead
# of making the combo box itself editable (which loses the dropdown
# arrow/list-only click behaviour and makes every entry, known or
# farm-logged, look the same - see widgets/crop_simulation_page.py).
_OTHER_CROP = 'Other (type below)…'

# (settings_dlg spin box attribute name, crop_models.CropModel field name)
# for every field the settings popup's "Crop model" section can save - see
# crop_model_settings.BIG_LEVER_FIELDS/CURVE_SHAPE_FIELDS, which this must
# stay in sync with (a mismatch would silently drop a field from saving).
# Centralised here rather than repeated per field at each of the four call
# sites that touch all of them (_load_settings_for_current_variety,
# _dialog_crop_model, _save_crop_settings, set_widget_connections).
_BIG_LEVER_SPIN_FIELDS = (
    ('SBPotentialYield', 'potential_yield_t_ha'),
    ('SBKyInitial', 'ky_initial'),
    ('SBKyDevelopment', 'ky_development'),
    ('SBKyMidSeason', 'ky_mid_season'),
    ('SBKyLateSeason', 'ky_late_season'),
    ('SBKyNitrogen', 'ky_nitrogen'),
    ('SBMinYieldNitrogen', 'min_relative_yield_nitrogen'),
    ('SBNDemand', 'season_n_demand_kg_ha'),
    ('SBKyPotassium', 'ky_potassium'),
    ('SBMinYieldPotassium', 'min_relative_yield_potassium'),
    ('SBKDemand', 'season_k_demand_kg_ha'),
    ('SBPDemand', 'season_p_demand_kg_ha'),
    ('SBMgDemand', 'season_mg_demand_kg_ha'),
    ('SBReferenceSpacing', 'reference_spacing_mm'),
    ('SBSpacingSensitivity', 'spacing_sensitivity'),
    ('SBHeatThreshold', 'heat_stress_threshold_c'),
    ('SBKyHeat', 'ky_heat'),
)
_CURVE_SHAPE_SPIN_FIELDS = (
    ('SBGddBase', 'gdd_base_c'),
    ('SBRootDepthMin', 'root_depth_min_cm'),
    ('SBRootDepthMax', 'root_depth_max_cm'),
    ('SBRootDepthFullGdd', 'root_depth_full_gdd'),
    ('SBKcIni', 'kc_ini'),
    ('SBKcMid', 'kc_mid'),
    ('SBKcEnd', 'kc_end'),
    ('SBKcIniEndGdd', 'kc_ini_end_gdd'),
    ('SBKcMidEndGdd', 'kc_mid_end_gdd'),
    ('SBKcLateStartGdd', 'kc_late_start_gdd'),
    ('SBSeasonEndGdd', 'season_end_gdd'),
    ('SBNUptakeMidpoint', 'n_uptake_midpoint_gdd'),
    ('SBNUptakeSteepness', 'n_uptake_steepness'),
    ('SBKUptakeMidpoint', 'k_uptake_midpoint_gdd'),
    ('SBKUptakeSteepness', 'k_uptake_steepness'),
)
_MODEL_SPIN_FIELDS = _BIG_LEVER_SPIN_FIELDS + _CURVE_SHAPE_SPIN_FIELDS


@dataclass
class _SimulationInputs:
    """Everything :meth:`CropSimulation._compute_simulation` needs, read
    from the page's widgets on the main thread by run_simulation() before
    handing off to a background _RunSimulationTask - the widgets
    themselves can't be touched from the task's worker thread, so nothing
    past this point may read self.page directly."""
    field_name: str
    date_from: str
    date_to: str
    override_crop: str
    # A snapshot, not a live reference to CropSimulation._planned_events -
    # the list could otherwise be mutated (e.g. "Add" clicked again) while
    # the task is still reading it on another thread.
    planned_events: list = field(default_factory=list)
    # Optional per-run "growth stopped early" override (YYYY-MM-DD) - see
    # CBGrowthStopEnabled/DEGrowthStop on the page and
    # season_water_model.estimate_season's harvest_date parameter. None
    # (the default, checkbox unticked) means "no override": the crop's
    # natural end-of-season decline runs its full course, as before this
    # existed.
    growth_stop_date: str = None


@dataclass
class _SimulationResult:
    """Everything :meth:`CropSimulation._apply_simulation_result` needs to
    render onto the page/settings dialog, back on the main thread - the
    return value of :meth:`CropSimulation._compute_simulation`, which must
    not touch self.page/self.settings_dlg itself (see that method's
    docstring). ``warnings`` collects messages that would normally have
    been shown immediately via report_warning, deferred here for the same
    reason - the message bar is a Qt widget too."""
    field_name: str
    date_from: str
    date_to: str
    auto_crop: object
    override_crop: str
    crop_for_model: str
    results: list
    season: object
    weather: list
    irrigation_by_date: dict
    fertilizer_kg_n_by_date: dict
    fertilizer_kg_k_by_date: dict
    phosphorus_applied_kg_ha: object
    magnesium_applied_kg_ha: object
    spacing_mm: object
    clay_pct: object
    organic_matter_pct: object
    legacy_warning_text: str
    cell_polygons: dict
    cell_traces: dict
    cell_varieties: dict
    trace_dates: list
    # The logged planting date actually used to anchor the GDD clock (None
    # if none was on file, or it fell outside the analysed period - see
    # _compute_simulation) and the run's "growth stopped early" override,
    # if any - both echoed back so _apply_simulation_result can show them
    # and cache them into _last_run for the settings popup's live preview.
    planting_date: object = None
    growth_stop_date: object = None
    warnings: list = field(default_factory=list)
    # Real harvested yield (t/ha) for this field/date range, if any
    # harvest.* import overlaps it - see _load_actual_yield_t_ha. None
    # means no matching harvest data was found (e.g. a future/unharvested
    # season), not that the field has never been harvested at all.
    actual_yield_t_ha: object = None
    # Field-wide rain/irrigation totals for date_from..date_to (mm) - see
    # _render_rain_irrigation. 0.0 (not None) when a run has weather but
    # nothing fell/was logged - unlike actual_yield_t_ha there's no "not
    # found" case, every run has a rain figure.
    total_rain_mm: float = 0.0
    total_irrigation_mm: float = 0.0
    # cell_id -> {date_str: cumulative rain+irrigation mm} - see
    # _compute_cell_traces and _render_heatmap's "rain + irrigation" mode.
    cell_water_totals: dict = field(default_factory=dict)
    # cell_id -> predicted yield (t/ha) at the end of the run.
    cell_yields: dict = field(default_factory=dict)
    # cell_id -> {date_str: predicted yield through that date}.
    cell_yields_by_date: dict = field(default_factory=dict)
    # The field-wide variety _load_variety resolved (None if none is on
    # file) - shown alongside auto_crop the same way regardless of
    # override_crop, see _set_crop_label. The variety actually applied to
    # effective_crop_model for this run is None whenever override_crop is
    # set instead (a variety tied to whatever crop is on file has no
    # business driving a run for a different, manually-picked crop) - see
    # _compute_simulation.
    auto_variety: object = None


class _RunSimulationTask(QgsTask):
    """Runs :meth:`CropSimulation._compute_simulation` - the slow part of
    "Run simulation" (Open-Meteo fetch, per-application analysis, season
    balance, per-cell stress map) - on a background thread via QGIS's task
    manager, so the UI doesn't freeze while it works. See
    CropSimulation.run_simulation for what builds and launches this, and
    CropSimulation._on_simulation_task_finished for how the result gets
    applied afterward, back on the main thread (QgsTask.finished() is
    always called on the main thread, even though run() runs on a worker
    thread - that split is exactly why the compute/apply methods either
    side of this are kept so strictly separate).

    self.db (database_scripts/db.py's DB) is backed by a real
    psycopg2.pool.ThreadedConnectionPool(1, 20, ...) - every execute_sql/
    execute_and_return call borrows a connection with pool.getconn() and
    returns it with pool.putconn() around that one call, so this task's
    (many, sequential) DB calls on the worker thread and anything the main
    thread does concurrently each get their own real connection rather
    than racing on one shared connection or on each other. A single
    connection is set to ISOLATION_LEVEL_AUTOCOMMIT (see DB._connect), so
    there's no lingering open transaction left holding locks between
    calls either.
    """

    def __init__(self, description, controller, inputs):
        super().__init__(description, QgsTask.Flag.CanCancel)
        self._controller = controller
        self._inputs = inputs
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self._controller._compute_simulation(self._inputs, self)
        except Exception as e:  # noqa: BLE001 - reported to the user, see finished()
            self.error = e
            return False
        # _compute_cell_traces checks isCanceled() periodically and can
        # return an incomplete result rather than raising - treat that as
        # failure too, so finished() never renders a partial run as if it
        # were the real, complete result.
        return not self.isCanceled()

    def finished(self, success):
        self._controller._on_simulation_task_finished(self, success)


# ----------------------------------------------------------------------
# "Teach your model": farm-wide accuracy scan + per-crop parameter fitting
# ----------------------------------------------------------------------

# _estimate_season_date_range's fallback when no logged planting date is
# on file for a harvest year - a rough stand-in, not a real anchor (see
# that method's docstring and TrainingExample.planting_date_logged).
_FALLBACK_SEASON_DAYS = 150
# See CropSimulation._load_actual_yield_t_ha's docstring - well below any
# crop this codebase models could plausibly average to for real (the
# lowest potential_yield_t_ha in crop_models.CROP_MODELS is oats' 6.5),
# so this only ever catches near-zero yield-monitor artifacts, never a
# genuinely poor but real harvest.
_MIN_USABLE_YIELD_T_HA = 0.1
# FertilizerEvent's nutrient-specific rate slot for each ferti.manual.
# nutrient code - shared by _load_events (ferti.manual rows) and
# _load_imported_ferti_events (a raw imported table's own 'nutrient'
# column, if set - see handle_iso11783.py's per-import nutrient prompt).
# 'S'/'Na' aren't modeled (no rate_text_s/rate_text_na slot on
# FertilizerEvent) and are simply not picked up, same as before this
# mapping existed.
_FERTI_RATE_KEYS = {'N': 'rate_text', 'P': 'rate_text_p',
                    'K': 'rate_text_k', 'Mg': 'rate_text_mg'}

# _find_column prefixes for a soil sample's clay%/organic-matter% columns
# (see _load_soil/_soil_available/_resolve_soil_by_cell) - a real Swedish
# soil lab report has neither an English "clay" nor "humus" substring
# anywhere in it, using 'total_lerhalt' ("total clay content") and
# 'mullhalt' ("humus content") instead; without these, a table with real,
# usable soil data on file was silently treated as having none at all.
# 'total_lerhalt' is tried before the bare 'lerhalt' fallback so a table
# that also has a separate 'fin_lerhalt' ("fine clay", a narrower
# fraction) reliably prefers the total figure regardless of which column
# happens to come first in the table.
_CLAY_COLUMN_PREFIXES = ('clay', 'total_lerhalt', 'lerhalt')
_HUMUS_COLUMN_PREFIXES = ('humus', 'mullhalt')

# _fit_crop_model's search grid: 6 steps per dimension keeps a coarse pass
# (6**3 = 216 candidates) and a fine pass around its best point both cheap
# - see that function's docstring for why a plain grid search is enough
# here (three parameters, no new dependency, every candidate's error is
# transparent arithmetic).
_GRID_STEPS = 6
# potential_yield_t_ha's search range is relative to the crop's current
# value, not a fixed absolute one - a fixed range would be meaningless
# across e.g. potato (tens of t/ha) vs wheat (single digits).
_POTENTIAL_YIELD_RANGE_FACTOR = (0.4, 2.5)
# Matches the settings dialog's own SBKyNitrogen/SBMinYieldNitrogen spin
# box ranges (widgets/crop_settings_dialog.py) - a fitted value the dialog
# itself couldn't represent wouldn't be usable once saved.
_KY_NITROGEN_RANGE = (0.0, 3.0)
_MIN_YIELD_FLOOR_RANGE = (0.0, 1.0)


@dataclass
class TrainingExample:
    """One field+year's worth of "Teach your model" training data - see the
    "Teach your model" plan. Built independently for every (field, year)
    combination that has real harvest data on file
    (:meth:`CropSimulation._compute_teach_scan`): its own weather slice,
    events, soil, irrigation and crop, with no state shared across
    examples, so a bad or missing year for one field never affects
    another's. ``field_name``/``year`` are kept on every example (not just
    used to build it and discarded) so the checklist UI, the fitting step
    and the fitted-result display can all keep referring back to exactly
    which field/years contributed - never an anonymous "trained on N
    examples" count.
    """
    field_name: str
    year: int
    crop: str
    # The date range estimate_season was (and, when re-fit, will be)
    # run against - season_from doubles as the planting-date anchor
    # passed to estimate_season (see _estimate_season_date_range).
    season_from: str
    season_to: str
    # False when season_from is the _FALLBACK_SEASON_DAYS guess, not a
    # real logged planting date - shown in the checklist so a user can
    # judge how much to trust that row before checking it for training.
    planting_date_logged: bool
    weather: list  # DailyWeather, already sliced to [season_from, season_to]
    clay: float
    organic_matter: float
    irrigation_by_date: dict
    fertilizer_kg_n_by_date: dict
    fertilizer_kg_k_by_date: dict
    predicted_yield_t_ha: float  # using today's effective_crop_model
    actual_yield_t_ha: float
    # Not in the original sketch, but _load_spacing is cheap and
    # spacing_yield_multiplier can genuinely move predicted_yield_t_ha
    # for any crop/field with a reference spacing configured - omitting
    # it would make the fit target a number the main Simulation tab
    # wouldn't actually reproduce for that same field/year.
    spacing_mm: float = None
    # The field-wide variety _load_variety resolved for this year (None
    # if none is on file) - predicted_yield_t_ha already used it (via
    # effective_crop_model) to pick this example's base model, and
    # _train_selected groups checked examples by (crop, variety) instead
    # of crop alone so a fit can learn a variety's own parameters
    # separately from its crop's, when there's enough data on file to
    # support that - see _compute_teach_scan.
    variety: str = None
    # SeasonEstimate.limiting_factor ('water'/'nitrogen'/'heat'/
    # 'potassium'/'none'/a '+'-joined tie) - the single-run tab already
    # shows this per run (see _set_crop_label's season.limiting_factor
    # branches); surfacing it per row here too is what makes an
    # unexpectedly identical predicted_yield_t_ha across many different
    # fields/years diagnosable at all, instead of a bare number with no
    # way to tell whether every one of them is genuinely water-limited by
    # similar weather, or all pinned at the same crop-level floor for an
    # entirely different (and unfitted) resource.
    limiting_factor: str = None


def _linspace(lo, hi, steps):
    """``steps`` evenly-spaced values from ``lo`` to ``hi`` inclusive - a
    single-point list when the range has collapsed to nothing (``hi <=
    lo``) or ``steps`` isn't enough to spread out."""
    if steps <= 1 or hi <= lo:
        return [lo]
    return [lo + (hi - lo) * i / (steps - 1) for i in range(steps)]


def _training_sse(model, examples):
    """Sum of squared predicted-vs-actual t/ha error across ``examples``
    (all one crop) with ``model`` - the objective :func:`_fit_crop_model`
    minimises. A pure function of each example's already-cached inputs -
    no DB/network call - which is what keeps a few hundred grid-search
    candidates per crop cheap."""
    total = 0.0
    for ex in examples:
        season = estimate_season(
            ex.weather, ex.crop, ex.clay, ex.organic_matter, ex.irrigation_by_date,
            fertilizer_kg_n_by_date=ex.fertilizer_kg_n_by_date,
            fertilizer_kg_k_by_date=ex.fertilizer_kg_k_by_date,
            crop_model=model, spacing_mm=ex.spacing_mm,
            planting_date=ex.season_from if ex.planting_date_logged else None)
        predicted = season.estimated_yield_t_ha or 0.0
        total += (predicted - ex.actual_yield_t_ha) ** 2
    return total


def _fit_crop_model(base_model, examples):
    """Coarse-to-fine grid search over ``(potential_yield_t_ha,
    ky_nitrogen, min_relative_yield_nitrogen)`` minimising
    :func:`_training_sse` against ``examples`` (all one crop) - see the
    "Teach your model" plan for why a plain grid search rather than a real
    optimiser/scipy dependency: three parameters and a handful of
    examples keeps this cheap and transparent (every candidate's error is
    plain arithmetic, not a black box).

    Returns
    -------
    (fitted_model, sse_before, sse_after)
        ``sse_before`` is ``base_model``'s own error against ``examples`` -
        the baseline the fit is judged against; ``sse_after`` is the
        fitted model's.
    """
    sse_before = _training_sse(base_model, examples)
    py0 = base_model.potential_yield_t_ha

    def search(py_range, kyn_range, floor_range):
        best_params, best_sse = None, None
        for py in _linspace(*py_range, _GRID_STEPS):
            for kyn in _linspace(*kyn_range, _GRID_STEPS):
                for floor in _linspace(*floor_range, _GRID_STEPS):
                    candidate = dataclasses_replace(
                        base_model, potential_yield_t_ha=py, ky_nitrogen=kyn,
                        min_relative_yield_nitrogen=floor)
                    sse = _training_sse(candidate, examples)
                    if best_sse is None or sse < best_sse:
                        best_sse, best_params = sse, (py, kyn, floor)
        return best_params, best_sse

    coarse_py_range = (py0 * _POTENTIAL_YIELD_RANGE_FACTOR[0],
                       py0 * _POTENTIAL_YIELD_RANGE_FACTOR[1])
    (py, kyn, floor), _coarse_sse = search(
        coarse_py_range, _KY_NITROGEN_RANGE, _MIN_YIELD_FLOOR_RANGE)

    # Fine pass: one coarse grid-step's width on either side of the
    # coarse winner, clamped back into the same overall ranges.
    py_step = (coarse_py_range[1] - coarse_py_range[0]) / (_GRID_STEPS - 1)
    kyn_step = (_KY_NITROGEN_RANGE[1] - _KY_NITROGEN_RANGE[0]) / (_GRID_STEPS - 1)
    floor_step = (_MIN_YIELD_FLOOR_RANGE[1] - _MIN_YIELD_FLOOR_RANGE[0]) / (_GRID_STEPS - 1)
    fine_py_range = (max(coarse_py_range[0], py - py_step),
                     min(coarse_py_range[1], py + py_step))
    fine_kyn_range = (max(_KY_NITROGEN_RANGE[0], kyn - kyn_step),
                      min(_KY_NITROGEN_RANGE[1], kyn + kyn_step))
    fine_floor_range = (max(_MIN_YIELD_FLOOR_RANGE[0], floor - floor_step),
                        min(_MIN_YIELD_FLOOR_RANGE[1], floor + floor_step))
    (py, kyn, floor), sse_after = search(fine_py_range, fine_kyn_range, fine_floor_range)

    fitted = dataclasses_replace(
        base_model, potential_yield_t_ha=round(py, 1), ky_nitrogen=round(kyn, 2),
        min_relative_yield_nitrogen=round(floor, 2))
    return fitted, sse_before, sse_after


class _RunTeachScanTask(QgsTask):
    """Runs :meth:`CropSimulation._compute_teach_scan` - the slow farm-wide
    scan behind "Teach your model"'s "Scan farm" button - on a background
    thread, mirroring :class:`_RunSimulationTask` exactly (same run()/
    finished() split, same pooled-connection story - see that class's
    docstring)."""

    def __init__(self, description, controller, allow_multiyear_crops=False):
        super().__init__(description, QgsTask.Flag.CanCancel)
        self._controller = controller
        self._allow_multiyear_crops = allow_multiyear_crops
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self._controller._compute_teach_scan(
                self, allow_multiyear_crops=self._allow_multiyear_crops)
        except Exception as e:  # noqa: BLE001 - reported to the user, see finished()
            self.error = e
            return False
        return not self.isCanceled()

    def finished(self, success):
        self._controller._on_teach_scan_finished(self, success)


class CropSimulation:
    """Controller for the "Crop simulation" main tab (Pro feature) - see
    widgets/crop_simulation_page.py for the page this fills in and reacts
    to.

    Field-wide inputs (weather, the per-application fertilizer-timing
    detail, the season yield/irrigation estimate) work exactly like the
    fertilizer-timing analysis this replaces. What's new is the date-slider
    stress map: the field is split into a grid (support_scripts/
    field_grid.py - 2m cells, coarsened automatically only if that would be
    an unreasonable number of cells) and a day-by-day soil water balance
    (support_scripts/season_water_model.py's ``daily_trace_with_relative_yield``) runs once per
    cell, using that cell's own crop/soil/irrigation where imported/logged
    data covers it (falling back to the field-wide reading for
    crop/soil - not for irrigation, where "nothing logged" genuinely means
    zero - see :meth:`_resolve_crop_by_cell`/:meth:`_resolve_soil_by_cell`/
    :meth:`_resolve_irrigation_by_cell`). Only weather is shared field-wide
    outright: it doesn't vary meaningfully within one field, so it's
    fetched once for the whole run (see :meth:`_load_weather`).
    """

    def __init__(self, parent):
        self.parent = parent
        self.db = parent.db
        translate = TR('CropSimulation')
        self.tr = translate.tr
        self.qsettings = QSettings()
        self.license_client = LicenseClient()
        self.weather_client = OpenMeteoClient()
        self.page = CropSimulationPage()
        self.settings_dlg = CropSettingsDialog()
        # The license section lives directly on this page now (moved off
        # "Farm & Fields", since this is the feature it gates) - kept as a
        # separate name so it reads the same as the section it replaced.
        self.license_dlg = self.page
        self.canvas = None
        self.connect_buttons = False
        # Fertilizer applications added via "Add" in the page - used for
        # this run only, never written to the database.
        self._planned_events = []
        # Populated by run_simulation() for the date slider/heatmap.
        self._cell_polygons = {}   # cell_id -> polygon WKT
        self._cell_traces = {}     # cell_id -> {date_str: DailyStress}
        self._cell_varieties = {}  # cell_id -> variety name (only cells with one)
        self._trace_dates = []     # sorted date strings covered by the run
        self._cell_water_totals = {}  # cell_id -> {date_str: cumulative rain+irrigation mm}
        self._cell_yields = {}  # cell_id -> predicted yield t/ha at season end
        self._cell_yields_by_date = {}  # cell_id -> {date_str: predicted yield t/ha}
        # Cached inputs from the last successful run_simulation(), so the
        # Crop model settings popup can recompute a live preview without a
        # fresh Open-Meteo/DB round trip - see open_crop_settings and
        # _recompute_settings_preview.
        self._last_run = None
        # The crop/variety the settings popup is currently open for - see
        # _populate_settings_dialog/_load_settings_for_current_variety.
        # '' (not None) for _settings_variety means "crop-level, no variety".
        self._settings_crop_name = None
        self._settings_variety = ''
        # Spin-box values as of the last _load_settings_for_current_variety
        # call - see _save_crop_settings, which only saves a field whose
        # value has since diverged from this baseline.
        self._settings_starting_values = {}
        # The in-flight _RunSimulationTask or _RunTeachScanTask, if either
        # is currently working in the background - None otherwise. Shared
        # between both (not one flag per tab) since they'd otherwise race
        # on the same single shared self.db connection - see
        # _RunSimulationTask's docstring.
        self._running_task = None
        # Populated by run_teach_scan() - see _apply_teach_scan_result/
        # TrainingExample. _teach_fits is {crop_key: (crop_display,
        # fitted_model)}, filled in by _train_selected and read by
        # _save_teach_fit - both keyed the same way (crop_model_settings'
        # own case-insensitive normalisation) so a save always lands on
        # the crop it was actually fitted from.
        self._teach_examples = []
        self._teach_fits = {}
        self._teach_skip_reasons = None
        # Which column TWTeachExamples is currently sorted by (None until
        # the user clicks a header) and whether that sort is reversed -
        # see _sort_teach_examples for why this is a from-scratch rebuild
        # rather than QTableWidget's own setSortingEnabled.
        self._teach_sort_column = None
        self._teach_sort_reverse = False

    def set_widget_connections(self):
        """Wires the page's buttons - called once at startup (see
        GeoDataFarm.set_buttons), since this is a persistent tab rather
        than a dialog that gets freshly opened each time."""
        if self.connect_buttons:
            return
        self.page.PBActivateLicense.clicked.connect(self.activate_license)
        self.page.PBGetLicense.clicked.connect(
            lambda: webbrowser.open(PRO_LICENSE_CHECKOUT_URL))
        self.page.PBRun.clicked.connect(self.run_simulation)
        self.page.PBAddPlanned.clicked.connect(self.add_planned_event)
        self.page.PBRemovePlanned.clicked.connect(self.remove_planned_event)
        self.page.SLDate.valueChanged.connect(self._on_slider_changed)
        self.page.CBMapMode.currentIndexChanged.connect(self._change_map_mode)
        self._update_map_legend()
        self.page.PBCheckData.clicked.connect(self._check_field_year_data)
        self.page.PBScanFarm.clicked.connect(self.run_teach_scan)
        self.page.TWTeachExamples.horizontalHeader().sectionClicked.connect(
            self._sort_teach_examples)
        self.page.PBTrainSelected.clicked.connect(self._train_selected)
        self.page.PBTeachSaveCrop.clicked.connect(self._save_teach_fit)
        self.page.CBCrop.currentIndexChanged.connect(self._toggle_crop_other_field)
        self.page.PBCropSettings.clicked.connect(self.open_crop_settings)
        self.settings_dlg.PBSaveSettings.clicked.connect(self._save_crop_settings)
        self.settings_dlg.PBResetSettings.clicked.connect(self._reset_crop_settings)
        self.settings_dlg.CBVariety.currentIndexChanged.connect(
            self._load_settings_for_current_variety)
        for attr, _field in _MODEL_SPIN_FIELDS:
            getattr(self.settings_dlg, attr).valueChanged.connect(
                self._recompute_settings_preview)
        for spin_box in (self.settings_dlg.SBClay, self.settings_dlg.SBOrganicMatter,
                        self.settings_dlg.SBSpacing):
            spin_box.valueChanged.connect(self._recompute_settings_preview)
        key = self.qsettings.value(LICENSE_KEY_SETTING, '') or ''
        self.license_dlg.LELicenseKey.setText(key)
        self._refresh_license_status()
        self._populate_crop_combo()
        self.connect_buttons = True

    # ------------------------------------------------------------------
    # Licensing
    # ------------------------------------------------------------------

    def activate_license(self):
        """Activates the license key typed into the page."""
        key = self.license_dlg.LELicenseKey.text().strip()
        if not key:
            report_warning(self.tr('Please enter a license key.'))
            return
        try:
            payload = self.license_client.activate(key, socket.gethostname())
        except LicenseError as e:
            report_error(str(e))
            return
        if not payload.get('activated'):
            self.license_dlg.LLicenseStatus.setText(self.tr(
                'Not licensed: {error}').format(
                    error=payload.get('error') or self.tr('invalid license key.')))
            return
        instance_id = (payload.get('instance') or {}).get('id', '')
        self.qsettings.setValue(LICENSE_KEY_SETTING, key)
        self.qsettings.setValue(LICENSE_INSTANCE_SETTING, instance_id)
        self.license_dlg.LLicenseStatus.setText(self.tr(
            'Licensed. The crop simulation is unlocked.'))
        report_success(self.tr('GeoDataFarm Pro license activated.'))

    def _refresh_license_status(self):
        """Updates the status label from what's already saved, without a
        network round trip (used at startup so the tab is instant;
        :meth:`is_licensed` does the real, live check before running)."""
        key = self.qsettings.value(LICENSE_KEY_SETTING, '') or ''
        instance_id = self.qsettings.value(LICENSE_INSTANCE_SETTING, '') or ''
        if key and instance_id:
            self.license_dlg.LLicenseStatus.setText(self.tr(
                'Licensed. The crop simulation is unlocked.'))
        else:
            self.license_dlg.LLicenseStatus.setText(self.tr(
                'Not licensed. Click "Get a Pro license" to purchase one, '
                'then paste the key you receive by email above and press '
                'Activate to unlock the crop simulation.'))

    def is_licensed(self):
        """Live-validates the saved license key/instance with Lemon Squeezy.

        Returns
        -------
        bool
            True if licensed. A previously validated license gets a bounded
            offline grace period for network errors; rejected server responses
            always fail closed.

            In test mode only, the ``geodatafarm/dev_bypass_license`` QSettings
            flag can skip the live check. It is deliberately ignored by a
            production application.

                from qgis.PyQt.QtCore import QSettings
                QSettings().setValue('geodatafarm/dev_bypass_license', True)

            Set it back to False (or remove it) to test the real gate again.
        """
        if (getattr(self.parent, 'test_mode', False)
            and self.qsettings.value(DEV_BYPASS_LICENSE_SETTING, False, type=bool)):
            return True
        key = self.qsettings.value(LICENSE_KEY_SETTING, '') or ''
        instance_id = self.qsettings.value(LICENSE_INSTANCE_SETTING, '') or ''
        if not key or not instance_id:
            return False
        try:
            payload = self.license_client.validate(key, instance_id)
        except LicenseError:
            last_validated = self.qsettings.value(LICENSE_LAST_VALIDATED_SETTING, 0)
            try:
                last_validated = float(last_validated)
            except (TypeError, ValueError):
                last_validated = 0.0
            return (last_validated > 0
                    and time.time() - last_validated <= LICENSE_OFFLINE_GRACE_SECONDS)
        if payload.get('valid'):
            self.qsettings.setValue(LICENSE_LAST_VALIDATED_SETTING, time.time())
            return True
        self.qsettings.remove(LICENSE_LAST_VALIDATED_SETTING)
        return False

    def _populate_crop_combo(self):
        """Fills "Use crop" with the crops this model has a literature-
        tuned profile for (see support_scripts/crop_models.CROP_MODELS)
        first, a separator, then whatever else this farm has used (the
        ``crops`` table) that isn't already one of those, and finally
        :data:`_OTHER_CROP` - picking that reveals page.CBCropOther (see
        :meth:`_toggle_crop_other_field`) for typing any other name, which
        still works fine, just without a crop-specific profile behind it
        (crop_models.get_crop_model falls back to a generic default for
        an unrecognised name)."""
        self.page.CBCrop.clear()
        self.page.CBCrop.addItem(self.tr(_SELECT_CROP))
        known = sorted(crop_models.CROP_MODELS.keys())
        for crop_name in known:
            self.page.CBCrop.addItem(crop_name.capitalize())
        known_set = set(known)
        rows = db_rows(self.db.execute_and_return(
            "SELECT crop_name FROM crops ORDER BY crop_name"))
        farm_crops = [crop_name for (crop_name,) in rows
                     if crop_name and crop_name.strip().lower() not in known_set]
        if farm_crops:
            self.page.CBCrop.insertSeparator(self.page.CBCrop.count())
            for crop_name in farm_crops:
                self.page.CBCrop.addItem(crop_name)
        self.page.CBCrop.insertSeparator(self.page.CBCrop.count())
        self.page.CBCrop.addItem(self.tr(_OTHER_CROP))
        self.page.CBCropOther.clear()
        self.page.CBCropOther.setVisible(False)

    def _toggle_crop_other_field(self):
        self.page.CBCropOther.setVisible(
            self.page.CBCrop.currentText() == self.tr(_OTHER_CROP))

    def _current_crop_override(self):
        """The crop name "Use crop" is currently set to, or ``''`` if
        it's on the "not set" sentinel - :data:`_OTHER_CROP`'s own typed-in
        text from page.CBCropOther if that's what's selected, otherwise
        the combo box's own current text. Centralised here since every
        caller that used to read page.CBCrop.currentText() directly needs
        to go through this now (see :meth:`_toggle_crop_other_field`)."""
        current = self.page.CBCrop.currentText().strip()
        if current == self.tr(_SELECT_CROP):
            return ''
        if current == self.tr(_OTHER_CROP):
            return self.page.CBCropOther.text().strip()
        return current

    def add_planned_event(self):
        """Adds a fertilizer application typed into the page to this run's
        analysis only - never written to the database. One application can
        carry several nutrients at once (a real compound product, e.g. an
        NPK+Mg blend, delivers them together) - N is the only one that
        affects which per-application timing-risk tier this event can use
        (see fertilizer_timing_model.analyse_events), P/K/Mg are otherwise
        independent and any subset of the four may be left blank."""
        rate_text = self.page.LEPlannedRate.text().strip()
        rate_text_p = self.page.LEPlannedRateP.text().strip()
        rate_text_k = self.page.LEPlannedRateK.text().strip()
        rate_text_mg = self.page.LEPlannedRateMg.text().strip()
        if not (rate_text or rate_text_p or rate_text_k or rate_text_mg):
            report_warning(self.tr(
                'Enter at least one nutrient rate for the planned application first.'))
            return
        date_str = self.page.DEPlannedDate.date().toString('yyyy-MM-dd')
        crop = self._current_crop_override()
        event = FertilizerEvent(
            date=date_str, rate_text=rate_text, crop=crop, rate_text_p=rate_text_p,
            rate_text_k=rate_text_k, rate_text_mg=rate_text_mg)
        self._planned_events.append(event)
        summary_parts = []
        notes = ''
        if rate_text:
            summary_parts.append('N: {}'.format(rate_text))
            notes += self._rate_parse_note('N', event.rate_kg_n_ha,
                self.tr(' - won\'t count toward the nitrogen balance, and '
                        'can\'t use the advanced timing model'))
        if rate_text_p:
            summary_parts.append('P: {}'.format(rate_text_p))
            notes += self._rate_parse_note('P', event.rate_kg_p_ha)
        if rate_text_k:
            summary_parts.append('K: {}'.format(rate_text_k))
            notes += self._rate_parse_note('K', event.rate_kg_k_ha)
        if rate_text_mg:
            summary_parts.append('Mg: {}'.format(rate_text_mg))
            notes += self._rate_parse_note('Mg', event.rate_kg_mg_ha)
        self.page.LWPlannedEvents.addItem('{} - {}{}'.format(
            date_str, ', '.join(summary_parts), notes))
        self.page.LEPlannedRate.clear()
        self.page.LEPlannedRateP.clear()
        self.page.LEPlannedRateK.clear()
        self.page.LEPlannedRateMg.clear()

    def _rate_parse_note(self, nutrient_label, rate_kg_ha, not_understood_consequence=''):
        """" (N: read as X kg N/ha)", or a "not understood" warning if
        ``rate_kg_ha`` is None, for one nutrient - see
        FertilizerEvent's rate_kg_n_ha/rate_kg_p_ha/rate_kg_k_ha/
        rate_kg_mg_ha docstrings for the best-effort parse this confirms
        or flags. Without this, a typo or an unparseable rate silently
        contributes nothing to that nutrient's balance with no indication
        anywhere that that happened."""
        if rate_kg_ha is None:
            return self.tr(' ({label}: rate not understood as a number{consequence})').format(
                label=nutrient_label, consequence=not_understood_consequence)
        return self.tr(' ({label}: read as {rate:.0f} kg {label}/ha)').format(
            label=nutrient_label, rate=rate_kg_ha)

    def remove_planned_event(self):
        row = self.page.LWPlannedEvents.currentRow()
        if row < 0:
            report_warning(self.tr('Select a planned application to remove first.'))
            return
        self.page.LWPlannedEvents.takeItem(row)
        del self._planned_events[row]

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def run_simulation(self):
        """Gathers this run's inputs from the page's widgets - which must
        happen here, on the main thread, since a background task's worker
        thread can't safely touch them - and hands the slow work (Open-
        Meteo fetch, per-application analysis, season balance, per-cell
        stress map) off to a background _RunSimulationTask, so the UI
        doesn't freeze while it runs. See :meth:`_compute_simulation` for
        that work and :meth:`_on_simulation_task_finished`/
        :meth:`_apply_simulation_result` for how the result gets rendered
        once it's done."""
        if not self.is_licensed():
            report_warning(self.tr(
                'The crop simulation is a Pro feature. Please activate a '
                'license key above first.'))
            return
        if self._running_task is not None:
            report_warning(self.tr(
                'A simulation is already running - please wait for it to finish.'))
            return
        field_name = self.page.CBField.currentText()
        if not field_name or field_name == self.tr('--- Select field ---'):
            report_warning(self.tr('Please select a field first.'))
            return
        date_from = self.page.DEFrom.date().toString('yyyy-MM-dd')
        date_to = self.page.DETo.date().toString('yyyy-MM-dd')
        if date_from >= date_to:
            report_warning(self.tr(
                'The "to date" must be later than the "from date".'))
            return
        override_crop = self._current_crop_override()
        growth_stop_date = None
        if self.page.CBGrowthStopEnabled.isChecked():
            growth_stop_date = self.page.DEGrowthStop.date().toString('yyyy-MM-dd')
            if growth_stop_date < date_from:
                report_warning(self.tr(
                    'The "growth stopped early on" date must be on or after '
                    'the "from" date.'))
                return

        inputs = _SimulationInputs(
            field_name=field_name, date_from=date_from, date_to=date_to,
            override_crop=override_crop, planned_events=list(self._planned_events),
            growth_stop_date=growth_stop_date)
        task = _RunSimulationTask(self.tr('Crop simulation'), self, inputs)
        self._running_task = task
        self._set_running_state(True)
        if getattr(self.parent, 'test_mode', False):
            # Deterministic and synchronous in tests - no real thread pool
            # or Qt event loop pumping needed, so this still behaves like
            # a plain blocking call from a test's point of view, even
            # though it goes through the exact same run()/finished() split
            # production code uses via the real task manager.
            success = task.run()
            task.finished(success)
        else:
            QgsApplication.taskManager().addTask(task)

    def _compute_simulation(self, inputs, task=None):
        """All of run_simulation()'s slow work, with no Qt widget access -
        this is what actually runs on _RunSimulationTask's worker thread.
        Warnings that would normally show immediately are collected into
        the result's ``warnings`` list instead of calling report_warning
        directly here (that touches the message bar - a Qt widget, only
        safe from the main thread); :meth:`_apply_simulation_result` shows
        them once execution is back there.

        Returns
        -------
        _SimulationResult
        """
        field_name, date_from, date_to = inputs.field_name, inputs.date_from, inputs.date_to
        warnings = []

        weather, weather_warning = self._load_weather(field_name, date_from, date_to)
        if weather_warning:
            warnings.append(weather_warning)
        if not weather:
            return _SimulationResult(
                field_name=field_name, date_from=date_from, date_to=date_to,
                auto_crop=None, override_crop=inputs.override_crop, crop_for_model='',
                results=[], season=None, weather=[], irrigation_by_date={},
                fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date={},
                phosphorus_applied_kg_ha=None, magnesium_applied_kg_ha=None,
                spacing_mm=None, clay_pct=None,
                organic_matter_pct=None, legacy_warning_text='', cell_polygons={},
                cell_traces={}, cell_varieties={}, trace_dates=[],
                cell_yields_by_date={},
                growth_stop_date=inputs.growth_stop_date, warnings=warnings)

        auto_crop, auto_planting_date = self._load_crop(field_name, date_to)
        crop_for_model = inputs.override_crop or auto_crop or ''
        auto_variety, _variety_planting_date = self._load_variety(field_name, date_to)
        # Only feeds the model when the on-file crop is what's actually
        # running - a variety tied to that crop has no business driving a
        # different, manually-overridden one. Still shown in the label
        # either way (see _set_crop_label), same as auto_crop itself.
        variety_for_model = auto_variety if not inputs.override_crop else None

        # Anchor the growing-degree-day (GDD) clock to a real logged
        # planting date instead of blindly treating "From" as day one -
        # only when the crop itself came from that same planting record
        # (an override_crop has no reliable planting date to pair with)
        # and the date actually falls inside the analysed period; if it's
        # earlier than "From", the weather fetch (and hence the per-cell
        # stress map/irrigation window) isn't widened to cover it, so the
        # clock still can't start any earlier than "From" - flagged here
        # instead, so the user knows to adjust "From" for an accurate run.
        planting_date = None
        if not inputs.override_crop and auto_planting_date:
            if auto_planting_date >= date_from:
                planting_date = auto_planting_date
            else:
                warnings.append(self.tr(
                    'This field\'s crop was logged as planted on {planted} - '
                    'before the selected "From" date ({date_from}). The '
                    'water/nitrogen timing below will start counting from '
                    '{date_from} instead of the real planting date, so '
                    'early-season values may not match the crop\'s actual '
                    'stage. Set "From" to on/before {planted} for an '
                    'accurate season model.').format(
                        planted=auto_planting_date, date_from=date_from))

        events = self._load_events(field_name, date_from, date_to)
        events.extend(inputs.planned_events)
        if inputs.override_crop:
            for event in events:
                if not event.crop:
                    event.crop = inputs.override_crop
        events.sort(key=lambda e: e.date)

        clay_pct, organic_matter_pct = self._load_soil(field_name, date_to)

        if events:
            results = analyse_events(events, weather, clay_pct, organic_matter_pct)
        else:
            warnings.append(self.tr(
                'No fertilizer applications found for that field/period - '
                'add a planned application above to see its timing risk.'))
            results = []

        irrigation_by_date = self._load_irrigation(field_name, date_from, date_to)
        total_rain_mm = sum(w.precipitation_mm for w in weather if w.precipitation_mm is not None)
        total_irrigation_mm = sum(irrigation_by_date.values())
        fertilizer_kg_n_by_date = self._build_fertilizer_kg_n_by_date(events)
        fertilizer_kg_k_by_date = self._build_fertilizer_kg_k_by_date(events)
        phosphorus_applied_kg_ha = self._sum_nutrient_applied(events, 'rate_kg_p_ha')
        magnesium_applied_kg_ha = self._sum_nutrient_applied(events, 'rate_kg_mg_ha')
        spacing_mm = self._load_spacing(field_name)
        effective_model = crop_model_settings.effective_crop_model(
            self.db, crop_for_model, variety=variety_for_model)
        season = estimate_season(
            weather, crop_for_model, clay_pct, organic_matter_pct, irrigation_by_date,
            fertilizer_kg_n_by_date=fertilizer_kg_n_by_date,
            fertilizer_kg_k_by_date=fertilizer_kg_k_by_date,
            phosphorus_applied_kg_ha=phosphorus_applied_kg_ha,
            magnesium_applied_kg_ha=magnesium_applied_kg_ha, crop_model=effective_model,
            spacing_mm=spacing_mm, planting_date=planting_date,
            harvest_date=inputs.growth_stop_date)

        actual_yield_t_ha = None
        if season.estimated_yield_t_ha is not None:
            actual_yield_t_ha = self._load_actual_yield_t_ha(field_name, date_from, date_to)

        legacy_warning_text = self._compute_legacy_irrigation_warning(
            field_name, date_from, date_to, irrigation_by_date)

        (cell_polygons, cell_traces, cell_varieties, trace_dates, cell_water_totals,
         cell_yields, cell_yields_by_date) = (
            self._compute_cell_traces(
                field_name, date_from, date_to, weather, crop_for_model, clay_pct,
                organic_matter_pct, task=task, planting_date=planting_date,
                harvest_date=inputs.growth_stop_date, spacing_mm=spacing_mm,
                field_relative_yield_nitrogen=season.relative_yield_nitrogen,
                field_relative_yield_potassium=season.relative_yield_potassium,
                field_relative_yield_heat=season.relative_yield_heat,
                include_daily_yields=True))

        return _SimulationResult(
            field_name=field_name, date_from=date_from, date_to=date_to,
            auto_crop=auto_crop, override_crop=inputs.override_crop,
            crop_for_model=crop_for_model, results=results, season=season, weather=weather,
            irrigation_by_date=irrigation_by_date,
            fertilizer_kg_n_by_date=fertilizer_kg_n_by_date,
            fertilizer_kg_k_by_date=fertilizer_kg_k_by_date,
            phosphorus_applied_kg_ha=phosphorus_applied_kg_ha,
            magnesium_applied_kg_ha=magnesium_applied_kg_ha, spacing_mm=spacing_mm,
            clay_pct=clay_pct, organic_matter_pct=organic_matter_pct,
            legacy_warning_text=legacy_warning_text, cell_polygons=cell_polygons,
            cell_traces=cell_traces, cell_varieties=cell_varieties, trace_dates=trace_dates,
            planting_date=planting_date, growth_stop_date=inputs.growth_stop_date,
            warnings=warnings, actual_yield_t_ha=actual_yield_t_ha,
            total_rain_mm=total_rain_mm, total_irrigation_mm=total_irrigation_mm,
            cell_water_totals=cell_water_totals, cell_yields=cell_yields,
            cell_yields_by_date=cell_yields_by_date,
            auto_variety=auto_variety)

    def _on_simulation_task_finished(self, task, success):
        """QgsTask.finished()'s callback - always runs on the main thread
        (see :class:`_RunSimulationTask`'s docstring), even though the
        task's own run() ran on a worker thread, so this is where it's
        safe to touch self.page/self.settings_dlg again."""
        self._running_task = None
        self._set_running_state(False)
        if not success:
            if task.error is not None:
                report_error(self.tr('The simulation failed: {error}').format(
                    error=str(task.error)))
            elif not task.isCanceled():
                report_error(self.tr('The simulation failed for an unknown reason.'))
            return
        if task.result is not None:
            self._apply_simulation_result(task.result)

    def _apply_simulation_result(self, result):
        """Renders a _SimulationResult onto the page/settings dialog - the
        main-thread half of what run_simulation() used to do in one
        synchronous pass before it moved to a background task; see
        :meth:`_compute_simulation` for the other half."""
        for message in result.warnings:
            report_warning(message)
        if result.season is None:
            return  # weather failed to load - nothing else to render
        self._set_crop_label(result.auto_crop, result.override_crop, result.planting_date,
                            result.auto_variety)
        self._render_details(result.results)
        self._render_season(result.season)
        self._render_actual_yield(result.actual_yield_t_ha, result.season.estimated_yield_t_ha)
        self._render_rain_irrigation(result.total_rain_mm, result.total_irrigation_mm,
                                     result.date_from, result.date_to)
        self._render_legacy_irrigation_warning(result.legacy_warning_text)

        # Cached so the Crop model settings popup can recompute a live
        # preview from here without a fresh Open-Meteo/DB round trip.
        self._last_run = {
            'field_name': result.field_name, 'weather': result.weather,
            'clay_pct': result.clay_pct, 'organic_matter_pct': result.organic_matter_pct,
            'crop_for_model': result.crop_for_model,
            'irrigation_by_date': result.irrigation_by_date,
            'fertilizer_kg_n_by_date': result.fertilizer_kg_n_by_date,
            'fertilizer_kg_k_by_date': result.fertilizer_kg_k_by_date,
            'phosphorus_applied_kg_ha': result.phosphorus_applied_kg_ha,
            'magnesium_applied_kg_ha': result.magnesium_applied_kg_ha,
            'spacing_mm': result.spacing_mm,
            # Planting-date anchor/forced-stop override actually used this
            # run - carried into the popup's live preview so it keeps
            # matching the main page instead of silently reverting to
            # date_from-anchored timing on every settings tweak.
            'planting_date': result.planting_date,
            'growth_stop_date': result.growth_stop_date,
            # Varieties actually seen in this run's cells, plus the
            # field-wide one _load_variety resolved (a manual plant.manual
            # entry has no per-cell geometry of its own, so it would never
            # show up in cell_varieties otherwise, even though it's what
            # the season estimate above just used) - populates the Crop
            # model settings popup's variety picker (see
            # _populate_settings_dialog).
            'varieties': sorted(
                set(result.cell_varieties.values())
                | ({result.auto_variety} if result.auto_variety else set())),
        }
        self._cell_polygons = result.cell_polygons
        self._cell_traces = result.cell_traces
        self._cell_varieties = result.cell_varieties
        self._trace_dates = result.trace_dates
        self._cell_water_totals = result.cell_water_totals
        self._cell_yields = result.cell_yields
        self._cell_yields_by_date = result.cell_yields_by_date
        self._setup_slider()

    def _set_running_state(self, running):
        """Disables this tab's inputs and shows/hides the busy spinner
        while a _RunSimulationTask is in flight - see that class's
        docstring for why the disabled controls matter for more than just
        visual feedback."""
        for widget in (self.page.PBRun, self.page.CBField, self.page.CBCrop,
                      self.page.DEFrom, self.page.DETo, self.page.PBAddPlanned,
                      self.page.PBRemovePlanned, self.page.CBGrowthStopEnabled):
            widget.setEnabled(not running)
        # DEGrowthStop's own enabled state otherwise tracks
        # CBGrowthStopEnabled's checked state (see crop_simulation_page.py) -
        # re-enabling it unconditionally here would leave it editable even
        # while its checkbox is unticked. CBCropOther similarly tracks
        # whether CBCrop is currently on the "Other" sentinel (see
        # _toggle_crop_other_field).
        self.page.DEGrowthStop.setEnabled(
            not running and self.page.CBGrowthStopEnabled.isChecked())
        self.page.CBCropOther.setEnabled(
            not running and self.page.CBCropOther.isVisible())
        if running:
            self.page.LStatus.setText(self.tr('Running simulation…'))
            self._show_simulation_spinner()
        else:
            self._hide_simulation_spinner()

    def _show_simulation_spinner(self):
        """Shows the busy spinner in the exact slot the heatmap canvas
        occupies (see widgets/crop_simulation_page.py's mplvl/spinner) -
        juggled in and out of that layout the same way _render_heatmap
        already juggles the canvas itself."""
        if self.canvas is not None:
            self.page.mplvl.removeWidget(self.canvas)
            # hide() before setParent(None), not after - a widget that
            # was visible a moment ago (this one was, it's the live
            # heatmap) stays visible once detached from its parent unless
            # explicitly hidden first, and a visible *parentless* widget
            # is exactly what Qt renders as its own top-level window -
            # the stray popup this was doing on every slider drag.
            self.canvas.hide()
            self.canvas.setParent(None)
            self.canvas = None
        self.page.mplvl.addWidget(self.page.spinner, 0, Qt.AlignmentFlag.AlignCenter)
        self.page.spinner.start()

    def _hide_simulation_spinner(self):
        self.page.spinner.stop()
        self.page.mplvl.removeWidget(self.page.spinner)
        self.page.spinner.hide()
        self.page.spinner.setParent(None)

    @staticmethod
    def _build_fertilizer_kg_n_by_date(events):
        """{date_str: total_kg_n_ha} from a list of FertilizerEvent - the
        nitrogen-balance counterpart to _load_irrigation, built from
        whatever numeric rate could be parsed from each event (see
        FertilizerEvent.rate_kg_n_ha; events with no parseable rate simply
        don't contribute)."""
        totals = {}
        for event in events:
            rate = event.rate_kg_n_ha
            if rate is None:
                continue
            totals[event.date] = totals.get(event.date, 0.0) + rate
        return totals

    @staticmethod
    def _build_fertilizer_kg_k_by_date(events):
        """{date_str: total_kg_k_ha} - the potassium counterpart to
        _build_fertilizer_kg_n_by_date (see FertilizerEvent.rate_kg_k_ha),
        since potassium gets the same day-by-day leaching treatment as
        nitrogen; unlike N, events with no parseable K rate just don't
        contribute (most events have no K figure at all)."""
        totals = {}
        for event in events:
            rate = event.rate_kg_k_ha
            if rate is None:
                continue
            totals[event.date] = totals.get(event.date, 0.0) + rate
        return totals

    @staticmethod
    def _sum_nutrient_applied(events, rate_attr):
        """Season-total kg/ha for a nutrient that season_water_model only
        tracks as a single lump sum rather than a day-by-day balance
        (phosphorus/magnesium - see estimate_season's
        phosphorus_applied_kg_ha/magnesium_applied_kg_ha). Returns None if
        no event carries a parseable rate for it, so the caller can tell
        "not modelled" apart from "modelled, zero applied" the same way
        _build_fertilizer_kg_n_by_date's dicts do for nitrogen/potassium."""
        total = None
        for event in events:
            rate = getattr(event, rate_attr)
            if rate is None:
                continue
            total = (total or 0.0) + rate
        return total

    def _set_crop_label(self, auto_crop, override_crop, planting_date=None, variety=None):
        if auto_crop:
            if variety and planting_date:
                self.page.LCrop.setText(self.tr(
                    'Crop: {crop} - variety: {variety} (planted {planted}, from '
                    'the planting record)'
                ).format(crop=auto_crop, variety=variety, planted=planting_date))
            elif variety:
                self.page.LCrop.setText(self.tr(
                    'Crop: {crop} - variety: {variety} (from the planting record)'
                ).format(crop=auto_crop, variety=variety))
            elif planting_date:
                self.page.LCrop.setText(self.tr(
                    'Crop: {} (planted {}, from the planting record)'
                ).format(auto_crop, planting_date))
            else:
                self.page.LCrop.setText(
                    self.tr('Crop: {} (from the planting record)').format(auto_crop))
        elif override_crop:
            self.page.LCrop.setText(
                self.tr('Crop: {} (set manually)').format(override_crop))
        else:
            self.page.LCrop.setText(self.tr(
                'Crop: not set - using the default crop profile'))

    # ------------------------------------------------------------------
    # Crop model settings popup
    # ------------------------------------------------------------------

    def open_crop_settings(self):
        """Opens the Crop model settings popup for whichever crop the last
        run used (or the crop override combo, if no run has happened yet).
        See widgets/crop_settings_dialog.py and
        support_scripts/crop_model_settings.py."""
        crop_name = (self._last_run['crop_for_model'] if self._last_run
                    else self._current_crop_override())
        if not crop_name:
            report_warning(self.tr(
                'Run a simulation first, or pick a crop in "Use crop" above, '
                'so there\'s something to configure settings for.'))
            return
        self._populate_settings_dialog(crop_name)
        self.settings_dlg.show()
        self.settings_dlg.exec()

    def _populate_settings_dialog(self, crop_name):
        """Opens the popup for ``crop_name``: fills the variety picker
        from the last run's per-cell data (:attr:`_last_run`'s
        ``'varieties'`` - see :meth:`_apply_simulation_result`) and loads that
        crop's own (no-variety) settings, since a crop-level row is what
        applies to any cell without a more specific variety of its own."""
        self._settings_crop_name = crop_name
        dlg = self.settings_dlg
        varieties = self._last_run.get('varieties', []) if self._last_run else []
        dlg.CBVariety.blockSignals(True)
        dlg.CBVariety.clear()
        dlg.CBVariety.addItem(self.tr('(crop default - no variety)'))
        for variety in varieties:
            dlg.CBVariety.addItem(variety)
        dlg.CBVariety.setCurrentIndex(0)
        dlg.CBVariety.blockSignals(False)
        self._load_settings_for_current_variety()

    def _load_settings_for_current_variety(self):
        """(Re)loads the spin boxes and heading text for whichever crop/
        variety combination is currently selected in the popup - called
        once by :meth:`_populate_settings_dialog` and again every time
        CBVariety's selection changes."""
        dlg = self.settings_dlg
        crop_name = self._settings_crop_name
        variety = dlg.CBVariety.currentText().strip() if dlg.CBVariety.currentIndex() > 0 else ''
        self._settings_variety = variety
        model = crop_model_settings.effective_crop_model(
            self.db, crop_name, variety=variety or None)
        if variety:
            dlg.LCropName.setText(
                self.tr('Crop: {crop} - variety: {variety}').format(
                    crop=crop_name, variety=variety))
            dlg.LModelHeading.setText(self.tr(
                '<b>Crop model</b> - saved for "{crop}" variety "{variety}", used '
                'for every field/run using that variety from now on. A field '
                'left unchanged here is inherited from "{crop}"\'s own settings.'
            ).format(crop=crop_name, variety=variety))
        else:
            dlg.LCropName.setText(self.tr('Crop: {}').format(crop_name))
            dlg.LModelHeading.setText(self.tr(
                '<b>Crop model</b> - saved for this crop name, used for every '
                'field/run from now on:'))
        model_spin_boxes = [getattr(dlg, attr) for attr, _field in _MODEL_SPIN_FIELDS]
        soil_spin_boxes = [dlg.SBClay, dlg.SBOrganicMatter, dlg.SBSpacing]
        for spin_box in model_spin_boxes + soil_spin_boxes:
            spin_box.blockSignals(True)
        for attr, field_name in _MODEL_SPIN_FIELDS:
            getattr(dlg, attr).setValue(getattr(model, field_name))
        if self._last_run:
            dlg.SBClay.setValue(self._last_run['clay_pct'] or 0.0)
            dlg.SBOrganicMatter.setValue(self._last_run['organic_matter_pct'] or 0.0)
            dlg.SBSpacing.setValue(self._last_run.get('spacing_mm') or 0.0)
        for spin_box in model_spin_boxes + soil_spin_boxes:
            spin_box.blockSignals(False)
        # Read back (not just getattr(model, field)) so the baseline
        # _save_crop_settings diffs against has already been through each
        # spin box's own rounding (setDecimals varies per field, e.g.
        # SBNUptakeSteepness's 4 vs SBSeasonEndGdd's 0) - comparing against
        # the raw unrounded model value would flag an untouched field as
        # "changed" purely from that rounding and over-save it.
        self._settings_starting_values = {
            attr: getattr(dlg, attr).value() for attr, _field in _MODEL_SPIN_FIELDS}
        dlg.LSettingsStatus.setText('')
        self._recompute_settings_preview()

    def _dialog_crop_model(self):
        """The CropModel the settings dialog's current spin-box values
        describe - the base model for whichever crop/variety this popup
        is currently open for, with the dialog's editable "Crop model"
        fields (both the always-visible ones and the "Advanced" curve-
        shape ones) applied on top (not yet saved)."""
        base = crop_model_settings.effective_crop_model(
            self.db, self._settings_crop_name, variety=self._settings_variety or None)
        dlg = self.settings_dlg
        overrides = {field: getattr(dlg, attr).value() for attr, field in _MODEL_SPIN_FIELDS}
        return dataclasses_replace(base, **overrides)

    def _recompute_settings_preview(self):
        """Recomputes the season estimate using the settings dialog's
        current (possibly unsaved) values and the last run's cached
        weather/events - no network/DB round trip, so this is cheap enough
        to run on every spin-box change for a genuinely live preview.

        This always previews against the field-wide weather/irrigation/
        fertilizer of the last run, even for a variety - a "what if every
        cell used this variety's settings" sandbox, the same spirit as
        the "This run's soil" what-if section below it."""
        dlg = self.settings_dlg
        crop_name = self._settings_crop_name
        if not crop_name:
            dlg.TEResults.setPlainText(self.tr('No crop selected.'))
            return
        model = self._dialog_crop_model()
        # The curve chart is a pure function of model - draw it regardless
        # of whether a run has happened yet to preview the text below.
        self._render_curve_chart(model)
        if not self._last_run:
            dlg.TEResults.setPlainText(self.tr(
                'Run a simulation on the main page first to see a live estimate '
                'here - these settings will apply to it once you do.'))
            return
        season = estimate_season(
            self._last_run['weather'], crop_name,
            dlg.SBClay.value(), dlg.SBOrganicMatter.value(),
            self._last_run['irrigation_by_date'],
            fertilizer_kg_n_by_date=self._last_run['fertilizer_kg_n_by_date'],
            fertilizer_kg_k_by_date=self._last_run['fertilizer_kg_k_by_date'],
            phosphorus_applied_kg_ha=self._last_run['phosphorus_applied_kg_ha'],
            magnesium_applied_kg_ha=self._last_run['magnesium_applied_kg_ha'],
            crop_model=model, spacing_mm=dlg.SBSpacing.value(),
            planting_date=self._last_run.get('planting_date'),
            harvest_date=self._last_run.get('growth_stop_date'))
        dlg.TEResults.setPlainText(self._season_full_text(season))

    def _render_curve_chart(self, model):
        """Draws ``model``'s water-demand (Kc) and nitrogen/potassium-uptake
        curves in the settings popup's "Advanced" section (see
        widgets/crop_settings_dialog.py's ``curve_chart_widget``) - a pure
        function of the model, so it updates on every spin-box change with
        no DB/network round trip, the same as :meth:`_recompute_settings_preview`.

        The primary (bottom) x-axis is cumulative growing-degree-days (GDD)
        - what the model actually runs on, and the only axis available
        with no run yet (this is called on every spin-box change,
        regardless). When a run's weather is cached (:attr:`_last_run`),
        a second (top) x-axis is added showing the calendar date each GDD
        tick actually fell on in that run - see
        :meth:`_gdd_ticks_to_dates`. This is deliberately not a generic/
        universal calendar mapping: the same GDD threshold lands on a
        different date depending on the actual weather that year, which is
        the whole point of driving the model by GDD rather than the
        calendar in the first place (see widgets/crop_simulation_page.py's
        "Crop duration" ABOUT_TEXT section) - so it's explicitly labelled
        as coming from that one run, not treated as a fixed axis.

        A bare Figure(), not pyplot.subplots() - see _render_heatmap's
        comment for why: pyplot's global figure registry both leaks memory
        and can pop up a stray native window when a figure is rebuilt
        repeatedly, which this is (on every spin-box change)."""
        dlg = self.settings_dlg
        fig = Figure(figsize=(5.0, 3.0))
        ax = fig.add_subplot(111)
        span = max(1.0, model.season_end_gdd)
        gdd_values = [span * i / 200.0 for i in range(201)]
        kc_values = [crop_models.crop_coefficient(model, g) for g in gdd_values]
        n_values = [crop_models.n_uptake_fraction(model, g) for g in gdd_values]
        k_values = [crop_models.k_uptake_fraction(model, g) for g in gdd_values]
        ax.plot(gdd_values, kc_values, color='#2b6cb0', label=self.tr('Water demand (Kc)'))
        ax.set_xlabel(self.tr('Cumulative GDD'))
        ax.set_ylabel(self.tr('Kc'), color='#2b6cb0')
        ax.tick_params(axis='y', labelcolor='#2b6cb0')
        ax.set_xlim(0.0, span)
        ax2 = ax.twinx()
        ax2.plot(gdd_values, n_values, color='#2f855a', label=self.tr('N uptake (cumulative)'))
        ax2.plot(gdd_values, k_values, color='#805ad5',
                label=self.tr('K uptake (cumulative)'))
        ax2.set_ylabel(self.tr('Nutrient uptake fraction'), color='#2f855a')
        ax2.set_ylim(0.0, 1.05)
        ax2.tick_params(axis='y', labelcolor='#2f855a')
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='lower right', fontsize='small')

        weather = self._last_run['weather'] if self._last_run else None
        if weather:
            start_date = (self._last_run.get('planting_date')
                          or min(w.date for w in weather))
            # get_xticks() can hand back "nice round number" ticks that
            # overshoot the axis's actual [0, span] range (e.g. a tick at
            # -100 or one past season_end_gdd) - meaningless as a calendar
            # date, so drop those before mapping.
            gdd_ticks = [t for t in ax.get_xticks() if 0.0 <= t <= span]
            tick_dates = self._gdd_ticks_to_dates(
                weather, model.gdd_base_c, start_date, gdd_ticks)
            if any(tick_dates):
                ax_dates = ax.twiny()
                ax_dates.set_xlim(ax.get_xlim())
                ax_dates.set_xticks(gdd_ticks)
                ax_dates.set_xticklabels(
                    [d[5:] if d else '' for d in tick_dates],
                    rotation=45, fontsize=7, ha='left')
                ax_dates.set_xlabel(
                    self.tr('Calendar date (MM-DD) in the last run\'s weather, '
                            'from {start}').format(start=start_date), fontsize=8)
        fig.tight_layout()
        if dlg.curve_canvas is not None:
            dlg.curve_chart_layout.removeWidget(dlg.curve_canvas)
            dlg.curve_canvas.hide()  # see _show_simulation_spinner's comment
            dlg.curve_canvas.setParent(None)
        dlg.curve_canvas = FigureCanvas(fig)
        dlg.curve_canvas.setWindowFlags(Qt.WindowType.Widget)
        dlg.curve_chart_layout.addWidget(dlg.curve_canvas)
        dlg.curve_canvas.draw()

    @staticmethod
    def _gdd_ticks_to_dates(weather, gdd_base_c, start_date, gdd_ticks):
        """The calendar date (``YYYY-MM-DD``) each value in ``gdd_ticks``
        was first reached by, accumulating growing-degree-days (GDD) day
        by day from ``start_date`` through ``weather`` - the same
        accumulation season_water_model._daily_water_balance itself does
        (same :func:`crop_models.growing_degree_days` call, oldest day
        first), so what :meth:`_render_curve_chart` labels the calendar
        axis with matches what a real run against this weather would
        actually do. A tick beyond what ``weather`` covers (season runs
        longer than the analysed/fetched period) gets ``None``.

        Returns
        -------
        list
            Same length/order as ``gdd_ticks``.
        """
        daily = sorted(
            (w for w in weather if w.date >= start_date and w.temp_mean_c is not None),
            key=lambda w: w.date)
        order = sorted(range(len(gdd_ticks)), key=lambda i: gdd_ticks[i])
        dates = [None] * len(gdd_ticks)
        cumulative = 0.0
        pos = 0
        for w in daily:
            cumulative += crop_models.growing_degree_days(w.temp_mean_c, gdd_base_c)
            while pos < len(order) and cumulative >= gdd_ticks[order[pos]]:
                dates[order[pos]] = w.date
                pos += 1
            if pos >= len(order):
                break
        return dates

    def _save_crop_settings(self):
        dlg = self.settings_dlg
        crop_name = self._settings_crop_name
        if not crop_name:
            return
        variety = self._settings_variety
        # Only what's actually different from the dialog's starting values
        # (see _load_settings_for_current_variety) - not every field the
        # dialog has, since a variety with nothing of its own touched
        # should keep inheriting its crop's settings (see
        # crop_model_settings.effective_crop_model), not have all 20
        # fields frozen in at whatever the crop's current defaults happen
        # to be right now.
        overrides = {
            field: getattr(dlg, attr).value() for attr, field in _MODEL_SPIN_FIELDS
            if getattr(dlg, attr).value() != self._settings_starting_values.get(attr)}
        try:
            crop_model_settings.save_overrides(self.db, crop_name, variety, **overrides)
        except ValueError as e:
            # A curve-shape combination crop_models.validate_shape rejected
            # (e.g. stages out of order) - the user's fault, not a bug, so
            # this is a warning, not report_error, and nothing was saved.
            report_warning(self.tr(
                'Could not save - {error} Fix the "Advanced" values above '
                'and try again.').format(error=str(e)))
            return
        if variety:
            dlg.LSettingsStatus.setText(self.tr(
                'Saved - every field using "{crop}" variety "{variety}" will use '
                'these settings from now on. Re-run the simulation to see it '
                'reflected in the stress map.').format(crop=crop_name, variety=variety))
            report_success(self.tr('Crop model settings saved for {crop} / {variety}.').format(
                crop=crop_name, variety=variety))
        else:
            dlg.LSettingsStatus.setText(self.tr(
                'Saved - every field using "{crop}" will use these settings from '
                'now on.').format(crop=crop_name))
            report_success(self.tr('Crop model settings saved for {crop}.').format(crop=crop_name))
        if self._last_run and self._last_run['crop_for_model'] == crop_name and not variety:
            # Reflect the newly-saved crop-level settings in the main
            # page's summary without needing a full "Run simulation"
            # click again. A variety-level save never changes that
            # field-wide number - the season estimate stays single-crop/
            # field-wide by design (see module docstring); only the
            # per-cell stress map is variety-aware.
            season = estimate_season(
                self._last_run['weather'], crop_name,
                self._last_run['clay_pct'], self._last_run['organic_matter_pct'],
                self._last_run['irrigation_by_date'],
                fertilizer_kg_n_by_date=self._last_run['fertilizer_kg_n_by_date'],
                fertilizer_kg_k_by_date=self._last_run['fertilizer_kg_k_by_date'],
                phosphorus_applied_kg_ha=self._last_run['phosphorus_applied_kg_ha'],
                magnesium_applied_kg_ha=self._last_run['magnesium_applied_kg_ha'],
                crop_model=self._dialog_crop_model(),
                spacing_mm=self._last_run.get('spacing_mm'),
                planting_date=self._last_run.get('planting_date'),
                harvest_date=self._last_run.get('growth_stop_date'))
            self._render_season(season)

    def _reset_crop_settings(self):
        crop_name = self._settings_crop_name
        if not crop_name:
            return
        variety = self._settings_variety
        crop_model_settings.reset_overrides(self.db, crop_name, variety)
        # Reload in place (keeps the variety picker's current selection),
        # rather than _populate_settings_dialog which would rebuild the
        # picker and jump back to "crop default".
        self._load_settings_for_current_variety()
        if variety:
            self.settings_dlg.LSettingsStatus.setText(self.tr(
                'Reset - "{crop}" variety "{variety}" now inherits "{crop}"\'s '
                'own settings.').format(crop=crop_name, variety=variety))
            report_success(self.tr('Crop model settings for {crop} / {variety} reset.').format(
                crop=crop_name, variety=variety))
        else:
            self.settings_dlg.LSettingsStatus.setText(
                self.tr('Reset to the built-in default for {crop}.').format(crop=crop_name))
            report_success(self.tr('Crop model settings for {crop} reset to default.').format(
                crop=crop_name))

    # ------------------------------------------------------------------
    # Field-wide data loading (fertilizer/soil/crop/weather/irrigation)
    # ------------------------------------------------------------------

    def _load_irrigation(self, field_name, date_from, date_to):
        """Actually-logged, dated irrigation for the field/period, as
        ``{date_str: total_mm}`` - see import_data/handle_irrigation.py's
        ``_store_dated_operation``, which writes one
        ``weather.<field>_irrigation_events_<year>`` table per year from
        each Raindancer operation's own real date and flight-path geometry.

        This field-wide total is what the season summary uses; the
        per-cell stress map instead matches each row to whichever cells
        its own geometry actually covers - see
        :meth:`_resolve_irrigation_by_cell`. See
        :meth:`_render_legacy_irrigation_warning` for the older, spatially
        resolved but undated grid this can't use instead."""
        totals = {}
        for year in range(int(date_from[:4]), int(date_to[:4]) + 1):
            table = check_text('{}_irrigation_events_{}'.format(field_name, year))
            if not self.db.check_table_exists(table, 'weather', False):
                continue
            rows = db_rows(self.db.execute_and_return(
                pgsql.SQL(
                    "SELECT date_, irrigation_mm FROM weather.{tbl}"
                    " WHERE date_ >= %s AND date_ <= %s"
                ).format(tbl=pgsql.Identifier(table)),
                params=(date_from, date_to)))
            for date_value, mm in rows:
                if mm is None:
                    continue
                date_str = self._as_date_str(date_value)
                totals[date_str] = totals.get(date_str, 0.0) + float(mm)
        return totals

    def _compute_legacy_irrigation_warning(self, field_name, date_from, date_to,
                                           irrigation_by_date):
        """If the dated irrigation table came back empty, checks whether
        the field has data in the older, undated whole-farm grid
        (``weather.irrigation_<year>``, from "Create irrigation year" on
        the Irrigation card) for the same years - that data has real
        spatial resolution but no date, so it can't be placed on this
        simulation's calendar at all. Returns the warning text to show
        (see :meth:`_render_legacy_irrigation_warning`) telling the user
        how to get it in: re-running "Add from raindancer" logs each
        operation's own real date and flight path into the dated table
        this simulation reads (see import_data/handle_irrigation.py's
        ``_store_dated_operation``) - that's the only source of dated
        irrigation there is (no manual whole-field entry - see that
        module's docstring for why), so this only still applies to grid
        data that predates a re-fetch. Pure DB work, no widget access -
        safe to call from :meth:`_compute_simulation`'s background thread."""
        if irrigation_by_date:
            return ''
        for year in range(int(date_from[:4]), int(date_to[:4]) + 1):
            table = 'irrigation_{}'.format(year)
            if not self.db.check_table_exists(table, 'weather', False):
                continue
            rows = db_rows(self.db.execute_and_return(
                pgsql.SQL("SELECT sum(irrigation_mm) FROM weather.{tbl}")
                .format(tbl=pgsql.Identifier(table))))
            total = (rows[0][0] or 0.0) if rows and rows[0][0] is not None else 0.0
            if total > 0:
                return self.tr(
                    'This field has irrigation data in the old undated grid '
                    'for {year}, but it has no date so it can\'t be used '
                    'here - re-run "Add from raindancer" on the Irrigation '
                    'card for this period to log each operation with its '
                    'own real date.'
                ).format(year=year)
        return ''

    def _render_legacy_irrigation_warning(self, warning_text):
        """Sets the legacy-irrigation warning label to ``warning_text``
        (see :meth:`_compute_legacy_irrigation_warning`) - the widget-
        touching half, kept separate so the DB-checking half can safely
        run on a background thread (see :meth:`_compute_simulation`)."""
        self.page.LLegacyIrrigationWarning.setText(warning_text)

    def _load_crop(self, field_name, date_to):
        """The most recently planted crop on/before ``date_to``, and its
        logged planting date, from ``plant.manual`` or an imported
        ``plant.*`` table matched spatially (see :meth:`_candidate_tables`)
        - mirrors :meth:`_load_spacing`. Checking imported tables too (not
        just ``plant.manual``) matters: a field whose planting was only
        ever imported (never entered manually) would otherwise never
        resolve a crop at all here - silently breaking anything downstream
        that needs one, e.g. :meth:`_estimate_season_date_range` skips a
        field/year entirely once this returns no crop, which used to make
        "Teach your model"'s farm-wide scan report 0 matches for a farm that
        had real harvest data on file, just because its planting happened
        to be imported. The crop is shown as context and used as the
        field-wide fallback for cells with no imported planting data of
        their own (see :meth:`_resolve_crop_by_cell`); the date lets the
        season model anchor its growing-degree-day (GDD) clock to when the
        crop was actually planted instead of just the "From" date picked
        for the run (see :meth:`_compute_simulation`).

        A ``plant.manual`` row logged via the "same date for every row"
        import path (import_data/insert_manual_from_file.py) only ever
        sets ``date_text`` (e.g. ``'c_2023-04-15'``), never the real
        ``date_`` column - without reading that too, a field whose
        planting came in that way (a very common import route) would look
        exactly like one with no planting record at all, the same failure
        mode the imported-table check above already exists to avoid. Falls
        back to Jan 1 of whatever year can be read out of the text when no
        full date is found there either (mirrors
        :meth:`_harvest_years_for_field`'s Dec 31 fallback, but Jan 1 here
        instead - a synthetic planting date must sort on/before the same
        year's harvest date, whereas harvest's Dec 31 only ever needs to
        bucket by year).

        Returns
        -------
        (crop_or_None, planting_date_or_None)
        """
        candidates = []
        manual_rows = db_rows(self.db.execute_and_return(
            "SELECT date_, date_text, crop FROM plant.manual WHERE field = %s",
            params=(field_name,)))
        for date_value, date_text, crop in manual_rows:
            date_str = self._date_from_manual_row(date_value, date_text)
            if date_str:
                candidates.append((date_str, crop))
        for table in self._candidate_tables('plant', field_name):
            crop_col = self._find_column('plant', table, ('crop',))
            if not crop_col:
                continue
            # ORDER BY ... LIMIT 1 (not a bare WHERE date_ <= %s) - only the
            # single most recent row on/before date_to can ever win once
            # every candidate is sorted below, so there's no reason to pull
            # every one of a table's rows (tens of thousands, for a real
            # farm's imports) across the network and through Python's sort
            # just to throw all but one away. Was exactly this kind of
            # per-table full fetch, repeated once per harvest year, that
            # made a farm-wide scan slow even after every relevant table
            # got its GiST index.
            query = pgsql.SQL(
                "SELECT date_, {col} FROM plant.{tbl}"
                " WHERE date_ <= %s AND {col} IS NOT NULL AND {col} <> ''"
                " ORDER BY date_ DESC LIMIT 1"
            ).format(col=pgsql.Identifier(crop_col), tbl=pgsql.Identifier(table))
            rows = db_rows(self.db.execute_and_return(query, params=(date_to,)))
            candidates.extend((self._as_date_str(d), c) for d, c in rows)
        candidates = [(d, c) for d, c in candidates if d <= date_to]
        candidates.sort(key=lambda row: row[0], reverse=True)
        for planting_date, crop in candidates:
            # 'None' (the string) is import_data/insert_manual_from_file.py's
            # sentinel for "no value entered" - plant.manual stores it as
            # literal text rather than SQL NULL, so a bare truthiness check
            # would treat it as a real crop name.
            if crop and crop != 'None':
                return str(crop), planting_date
        return None, None

    @staticmethod
    def _resolve_manual_field(value, table_):
        """Decodes a schema-specific ``.manual`` column (``variety``,
        ``rate``, ...) written by :class:`import_data.
        insert_manual_from_file.ManualFromFile`, whose ``_resolve``
        stores one of three things depending on how the import UI's
        combo/checkbox/line-edit for that attribute was used:

        - ``'c_<value>'`` - a single fixed value typed for the whole
          import; strip the prefix.
        - ``'None'`` - explicitly "not applicable"; no value.
        - anything else - the *name* of a column in the linked
          ``table_`` whose value varies row by row (see
          :func:`support_scripts.generate_reports.retrieve_distinct`,
          which resolves this exact encoding for the "advanced" report
          by querying that column dynamically). It is not a value in
          its own right, so this returns ``None`` for it - callers that
          need a real value must get it from ``table_`` itself (e.g.
          via this class's own :meth:`_candidate_tables` scan of the
          raw imported table).

        This decoding only applies to rows ``insert_manual_from_file``
        created (``table_`` not ``'None'``/unset) - a row entered
        straight through a manual-entry form (e.g. import_data/
        save_planting_data.py, always ``table_ = 'None'``) holds a
        genuine typed literal with none of the above encoding, and must
        be returned as-is.
        """
        if value is None or value == 'None':
            return None
        if not table_ or table_ == 'None':
            return value
        if value.startswith('c_'):
            return value[2:]
        return None

    def _load_variety(self, field_name, date_to):
        """The most recently planted variety on/before ``date_to``, and
        its logged planting date - mirrors :meth:`_load_crop` exactly
        (same ``plant.manual`` + imported-table candidate pool, same
        ``date_text`` fallback via :meth:`_date_from_manual_row`), just
        for a ``variety`` column instead of ``crop``.

        A field/run's variety matters because :func:`crop_model_settings.
        effective_crop_model` layers a variety's own saved overrides
        (potential yield, Ky-N, ...) on top of its crop's - two varieties
        of the same crop can have a genuinely different realistic yield
        ceiling, which neither the single-run season estimate nor
        "Teach your model"'s predicted-vs-actual comparison could ever
        reflect while both only ever resolved a field-wide crop, never a
        variety (see :meth:`_compute_simulation`/:meth:`_compute_teach_scan`).

        A plant table naming only a variety (no ``crop`` column at all)
        must never let that variety masquerade as the crop, or vice versa
        - the same rule :meth:`_resolve_crop_and_variety_by_cell` applies
        per-cell - so an imported table's variety column is skipped
        whenever it's the exact same column :meth:`_find_column` would
        also match for crop (e.g. one literally named ``crop_variety``).

        Returns
        -------
        (variety_or_None, planting_date_or_None)
        """
        candidates = []
        manual_rows = db_rows(self.db.execute_and_return(
            "SELECT date_, date_text, variety, table_ FROM plant.manual WHERE field = %s",
            params=(field_name,)))
        for date_value, date_text, variety, table_ in manual_rows:
            date_str = self._date_from_manual_row(date_value, date_text)
            if date_str:
                candidates.append((date_str, self._resolve_manual_field(variety, table_)))
        for table in self._candidate_tables('plant', field_name):
            variety_col = self._find_column('plant', table, ('variety',))
            if not variety_col:
                continue
            crop_col = self._find_column('plant', table, ('crop',))
            if variety_col == crop_col:
                continue  # one ambiguous column: treat as crop only
            query = pgsql.SQL(
                "SELECT date_, {col} FROM plant.{tbl}"
                " WHERE date_ <= %s AND {col} IS NOT NULL AND {col} <> ''"
                " ORDER BY date_ DESC LIMIT 1"
            ).format(col=pgsql.Identifier(variety_col), tbl=pgsql.Identifier(table))
            rows = db_rows(self.db.execute_and_return(query, params=(date_to,)))
            candidates.extend((self._as_date_str(d), v) for d, v in rows)
        candidates = [(d, v) for d, v in candidates if d <= date_to]
        candidates.sort(key=lambda row: row[0], reverse=True)
        for planting_date, variety in candidates:
            if variety:
                return str(variety), planting_date
        return None, None

    def _load_variety_breakdown(self, field_name, date_to):
        """Every distinct variety in the field's most recent (on/before
        ``date_to``) planting event, each with how many rows logged it (a
        rough proxy for how much of the field it covers) - unlike
        :meth:`_load_variety`, which collapses this down to a single,
        essentially arbitrarily-chosen winner (whichever row happens to
        sort last among same-date ties in Postgres). Reproduces the real
        bug report: a field genuinely planted with two varieties in the
        same pass (e.g. one real farm's 2018 planting: variety A on
        16,491 rows, variety B on 9,876) showed only one of them, and not
        even reliably the more common one.

        ``plant.manual`` rows can't be split this way - one row is one
        crop-wide value with no per-row geometry to attribute a count
        to - so if the winning source is a manual row, this returns a
        single-item list exactly like :meth:`_load_variety` already
        would, with ``table``/``variety_col`` both ``None`` (nothing for
        :meth:`_load_actual_yield_by_variety_t_ha` to spatially join
        against - a multi-variety split without matching actual-yield
        detail would just be guessing).

        Ties between a manual row and a table row on the exact same date
        favour the manual row, matching :meth:`_load_variety`'s own
        stable-sort tie-break (manual candidates are gathered first
        there too).

        Returns
        -------
        (planting_date_or_None, table_or_None, variety_col_or_None,
         [(variety, row_count), ...])
            Empty list (with the other three ``None``) if nothing usable
            is on file at all. ``row_count`` is always 1 for a
            manual-sourced single variety.
        """
        manual_candidates = []
        manual_rows = db_rows(self.db.execute_and_return(
            "SELECT date_, date_text, variety, table_ FROM plant.manual WHERE field = %s",
            params=(field_name,)))
        for date_value, date_text, variety, table_ in manual_rows:
            date_str = self._date_from_manual_row(date_value, date_text)
            if date_str:
                manual_candidates.append((date_str, self._resolve_manual_field(variety, table_)))
        manual_candidates = [(d, v) for d, v in manual_candidates if d <= date_to and v]

        table_candidates = []  # (date_str, table, variety_col)
        for table in self._candidate_tables('plant', field_name):
            variety_col = self._find_column('plant', table, ('variety',))
            if not variety_col:
                continue
            crop_col = self._find_column('plant', table, ('crop',))
            if variety_col == crop_col:
                continue  # one ambiguous column: treat as crop only
            rows = db_rows(self.db.execute_and_return(pgsql.SQL(
                "SELECT max(date_) FROM plant.{tbl}"
                " WHERE date_ <= %s AND {col} IS NOT NULL AND {col} <> ''"
            ).format(col=pgsql.Identifier(variety_col), tbl=pgsql.Identifier(table)),
                params=(date_to,)))
            if rows and rows[0][0] is not None:
                table_candidates.append((self._as_date_str(rows[0][0]), table, variety_col))

        best_manual = max(manual_candidates, key=lambda row: row[0], default=None)
        best_table = max(table_candidates, key=lambda row: row[0], default=None)
        if not best_manual and not best_table:
            return None, None, None, []
        if best_table and (not best_manual or best_table[0] > best_manual[0]):
            winning_date, table, variety_col = best_table
            rows = db_rows(self.db.execute_and_return(pgsql.SQL(
                "SELECT {col}, count(*) FROM plant.{tbl}"
                " WHERE date_::date = %s::date AND {col} IS NOT NULL AND {col} <> ''"
                " GROUP BY {col} ORDER BY count(*) DESC"
            ).format(col=pgsql.Identifier(variety_col), tbl=pgsql.Identifier(table)),
                params=(winning_date,)))
            return winning_date, table, variety_col, [(str(v), int(c)) for v, c in rows]
        winning_date, variety = best_manual
        return winning_date, None, None, [(str(variety), 1)]

    def _load_actual_yield_by_variety_t_ha(self, field_name, plant_table, planting_date,
                                           variety_col, year):
        """Average actual yield (t/ha) per variety, for a field/year whose
        planting had more than one variety on file (see
        :meth:`_load_variety_breakdown`) - attributes each harvest point
        to whichever planting row's own logged swath (its ``polygon`` -
        one per GPS-referenced point, not the field's own boundary; see
        :meth:`_candidate_tables`) it physically falls within, then
        averages by that row's variety. A harvest point that happens to
        fall within more than one planting row's swath (overlapping
        passes, GPS jitter) counts toward more than one variety's
        average - an accepted approximation, not a precise per-hectare
        split.

        ``harvest.manual`` rows have no per-row geometry of their own to
        attribute this way and are intentionally not included here -
        only the field-wide :meth:`_load_actual_yield_t_ha` can use
        those. A result under :data:`_MIN_USABLE_YIELD_T_HA` is dropped
        the same way :meth:`_load_actual_yield_t_ha` drops one - see its
        docstring for why (yield-monitor artifacts, not real measurements).

        Returns
        -------
        dict[str, float]
            variety -> average yield (t/ha), only for varieties with at
            least one matched, usable harvest point.
        """
        values_by_variety = {}
        for table in self._candidate_harvest_tables(field_name):
            yield_col = self._find_column('harvest', table, ('yield',))
            if not yield_col:
                continue
            rows = db_rows(self.db.execute_and_return(pgsql.SQL(
                "SELECT p.{variety_col}, h.{yield_col} FROM harvest.{h_tbl} h, plant.{p_tbl} p"
                " WHERE p.date_::date = %s::date AND st_intersects(h.pos, p.polygon)"
                " AND extract(year FROM h.date_) = %s"
                " AND h.{yield_col}::text ~ '^-?[0-9]+(\\.[0-9]+)?$'"
            ).format(variety_col=pgsql.Identifier(variety_col), yield_col=pgsql.Identifier(yield_col),
                    h_tbl=pgsql.Identifier(table), p_tbl=pgsql.Identifier(plant_table)),
                params=(planting_date, year)))
            for variety, yield_value in rows:
                values_by_variety.setdefault(str(variety), []).append(float(yield_value) / 1000.0)
        averages = {variety: sum(values) / len(values) for variety, values in values_by_variety.items()}
        return {variety: avg for variety, avg in averages.items() if avg >= _MIN_USABLE_YIELD_T_HA}

    @staticmethod
    def _date_from_manual_row(date_value, date_text):
        """Normalises a ``plant.manual`` row's ``date_`` (preferred) or
        ``date_text`` fallback into a plain ``YYYY-MM-DD`` string, or
        ``None`` if neither yields one - the shared piece of
        :meth:`_load_crop`/:meth:`_load_variety`. A row logged via the
        "same date for every row" import path (import_data/
        insert_manual_from_file.py) only ever sets ``date_text`` (e.g.
        ``'c_2023-04-15'``), never the real ``date_`` column - without
        reading that too, a field whose planting came in that way (a very
        common import route) would look exactly like one with no planting
        record at all. Falls back to Jan 1 of whatever year can be read
        out of the text when no full date is found there either (mirrors
        :meth:`_harvest_years_for_field`'s Dec 31 fallback, but Jan 1 here
        instead - a synthetic planting date must sort on/before the same
        year's harvest date, whereas harvest's Dec 31 only ever needs to
        bucket by year)."""
        if date_value is not None:
            return CropSimulation._as_date_str(date_value)
        if not date_text:
            return None
        full_match = re.search(r'(19|20)\d{2}-\d{2}-\d{2}', date_text)
        if full_match:
            return full_match.group(0)
        year_match = re.search(r'(19|20)\d{2}', date_text)
        if year_match:
            return '{}-01-01'.format(year_match.group(0))
        return None

    @staticmethod
    def _as_date_str(value):
        """Normalises a DB date/datetime value to a plain ``YYYY-MM-DD``
        string. Imported ferti/soil/plant tables store ``date_`` as
        TIMESTAMP (see import_data/handle_text_data.py), unlike
        ``.manual``'s plain DATE column - datetime.isoformat() would
        otherwise leave a 'T00:00:00' suffix that breaks every
        exact-string date match in fertilizer_timing_model.py."""
        if hasattr(value, 'date') and callable(value.date):
            return value.date().isoformat()
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return str(value)[:10]

    def _load_events(self, field_name, date_from, date_to):
        """Fertilizer events from both ``ferti.manual`` (has a plain
        ``field`` column) and imported ``ferti.*`` tables (matched to the
        field spatially instead - see :meth:`_candidate_tables`).

        A single real application can span several ``ferti.manual`` rows
        sharing one date - one per nutrient it delivers (see
        ferti.manual.nutrient) - so rows are grouped by date into one
        FertilizerEvent per date rather than one event per row. 'S'/'Na'
        rows aren't modeled by FertilizerEvent (no rate_text_s/rate_text_na
        slot - see its docstring) and are simply not picked up here, same
        as before this column existed."""
        ensure_ferti_nutrient_column(self.db)
        rows = db_rows(self.db.execute_and_return(
            "SELECT date_, nutrient, rate, crop, table_ FROM ferti.manual WHERE field = %s"
            " AND date_ >= %s AND date_ <= %s ORDER BY date_",
            params=(field_name, date_from, date_to)))
        by_date = {}
        for date_value, nutrient, rate, crop, table_ in rows:
            date_str = self._as_date_str(date_value)
            day = by_date.setdefault(date_str, {'crop': ''})
            rate_key = _FERTI_RATE_KEYS.get(nutrient)
            if rate_key:
                # rate is a plain literal for a manually-entered row, but
                # for a file-imported one (table_ set) it can equally be a
                # column-name reference the import UI's combo recorded -
                # see _resolve_manual_field's docstring; the real per-row
                # rate for that case comes from _load_imported_ferti_events
                # scanning the raw table below instead.
                day[rate_key] = self._resolve_manual_field(rate, table_) or ''
            if not day['crop'] and crop:
                day['crop'] = crop
        events = [FertilizerEvent(date=date_str, **day) for date_str, day in by_date.items()]
        for table in self._candidate_tables('ferti', field_name):
            events.extend(self._load_imported_ferti_events(table, date_from, date_to))
        events.sort(key=lambda e: e.date)
        return events

    def _load_imported_ferti_events(self, table, date_from, date_to):
        """One :class:`FertilizerEvent` per *day* found in an imported ferti
        table, not one per row - a single day's spreading pass can log
        hundreds of GPS-referenced rows (see
        import_data/handle_text_data.py's ``create_table``); the day's rate
        is the mean of its (parseable) rows.

        Routed into the right nutrient slot (N/P/K/Mg - see
        :data:`_FERTI_RATE_KEYS`) via a constant ``nutrient`` column on
        ``table`` itself, if one exists - set once per import batch by
        handle_iso11783.py's ferti nutrient prompt (one product goes in
        the spreader per pass, so this is never a per-row value the way
        ``rate`` is). No such column at all (an older import predating
        that prompt, or one where it was never asked) keeps the original
        behaviour of assuming nitrogen - but a column that *does* exist
        and holds a nutrient this class doesn't model (S/Na - see
        :meth:`_load_events`) must not be silently misattributed to
        nitrogen just because it's unrecognised, so that case is dropped
        instead."""
        rate_col = self._find_column('ferti', table, ('rate',))
        crop_col = self._find_column('ferti', table, ('crop',))
        nutrient_col = self._find_column('ferti', table, ('nutrient',))
        if nutrient_col:
            nutrient_rows = db_rows(self.db.execute_and_return(pgsql.SQL(
                "SELECT {col} FROM ferti.{tbl} WHERE {col} IS NOT NULL LIMIT 1"
            ).format(col=pgsql.Identifier(nutrient_col), tbl=pgsql.Identifier(table))))
            nutrient = nutrient_rows[0][0] if nutrient_rows else None
            rate_key = _FERTI_RATE_KEYS.get(nutrient)
            if not rate_key:
                return []
        else:
            rate_key = 'rate_text'
        select = pgsql.SQL(', ').join([
            pgsql.Identifier(rate_col) if rate_col else pgsql.SQL('NULL'),
            pgsql.Identifier(crop_col) if crop_col else pgsql.SQL('NULL')])
        query = pgsql.SQL(
            "SELECT date_, {select} FROM ferti.{tbl}"
            " WHERE date_ >= %s AND date_ <= %s"
        ).format(select=select, tbl=pgsql.Identifier(table))
        rows = db_rows(self.db.execute_and_return(query, params=(date_from, date_to)))
        by_date = {}
        for date_value, rate_value, crop_value in rows:
            date_str = self._as_date_str(date_value)
            day = by_date.setdefault(date_str, {'rates': [], 'crop': ''})
            if rate_value is not None:
                try:
                    day['rates'].append(float(rate_value))
                except (TypeError, ValueError):
                    pass
            if not day['crop'] and crop_value:
                day['crop'] = str(crop_value)
        events = []
        for date_str, day in by_date.items():
            rate_text = ('{:.1f}'.format(sum(day['rates']) / len(day['rates']))
                        if day['rates'] else '')
            events.append(FertilizerEvent(date=date_str, crop=day['crop'],
                                          **{rate_key: rate_text}))
        return events

    def _candidate_tables(self, schema, field_name):
        """Tables in ``schema`` (excluding ``manual``) whose ``polygon``
        column overlaps the field - the only way to associate an imported
        ferti/soil/plant table with a field, since (unlike ``.manual``)
        those tables don't have a plain ``field`` text column."""
        rows = db_rows(self.db.execute_and_return(
            "SELECT DISTINCT table_name FROM information_schema.columns"
            " WHERE table_schema = %s AND table_name != 'manual'"
            " AND column_name = 'polygon'", params=(schema,)))
        matched = []
        for (table,) in rows:
            overlap = db_rows(self.db.execute_and_return(
                pgsql.SQL(
                    "SELECT EXISTS (SELECT 1 FROM {schema}.{tbl} t, fields f"
                    " WHERE f.field_name = %s AND t.polygon IS NOT NULL"
                    " AND st_intersects(t.polygon, f.polygon))"
                ).format(schema=pgsql.Identifier(schema), tbl=pgsql.Identifier(table)),
                params=(field_name,)))
            if overlap and overlap[0][0]:
                matched.append(table)
        return matched

    def _find_column(self, schema, table, prefixes):
        """Best-effort column lookup: the first column of ``table`` whose
        name *contains* one of ``prefixes`` as a substring - not just a
        strict prefix. Text-import mapped columns get a unit suffix (e.g.
        ``rate`` -> ``rate_kg_ha``, keyword first), but ISO-XML imports
        name columns straight from a machine/DDOP's free-text designator
        (see import_data/handle_iso11783.py, via
        support_scripts/pyagriculture/agriculture.py), where the keyword
        can land anywhere - e.g. a variety column literally named
        ``potato_variety`` (keyword last) or a spacing column named
        ``set_planting_distance_mm`` (keyword in the middle, and using a
        different word entirely - see callers for the synonym lists this
        makes necessary). None if no such column exists."""
        rows = db_rows(self.db.execute_and_return(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = %s AND table_name = %s", params=(schema, table)))
        columns = [row[0] for row in rows]
        for prefix in prefixes:
            for col in columns:
                if prefix in col:
                    return col
        return None

    def _candidate_harvest_tables(self, field_name):
        """Like :meth:`_candidate_tables`, but for ``harvest.*`` tables -
        those get a ``pos`` POINT column, never a ``polygon`` column (see
        import_data/handle_text_data.py's ``create_table``, which skips the
        polygon column specifically for schema == 'harvest'), so the match
        has to be st_intersects(pos, field's polygon) instead."""
        rows = db_rows(self.db.execute_and_return(
            "SELECT DISTINCT table_name FROM information_schema.columns"
            " WHERE table_schema = 'harvest' AND table_name != 'manual'"
            " AND column_name = 'pos'"))
        matched = []
        for (table,) in rows:
            overlap = db_rows(self.db.execute_and_return(
                pgsql.SQL(
                    "SELECT EXISTS (SELECT 1 FROM harvest.{tbl} t, fields f"
                    " WHERE f.field_name = %s AND t.pos IS NOT NULL"
                    " AND st_intersects(t.pos, f.polygon))"
                ).format(tbl=pgsql.Identifier(table)),
                params=(field_name,)))
            if overlap and overlap[0][0]:
                matched.append(table)
        return matched

    def _load_actual_yield_t_ha(self, field_name, date_from, date_to):
        """Average actual harvested yield (t/ha) for field_name in the same
        calendar year as date_to, from both harvest.manual (has a plain
        field column, like ferti.manual - see _load_events) and every
        harvest.* table spatially overlapping the field - None if neither
        has anything for that year.

        Matched by year, not the run's exact [date_from, date_to] - a real
        harvest/lift date routinely falls days-to-weeks after a growing
        -season "To" date (e.g. potatoes are haulm-killed, then actually
        lifted later - see CBGrowthStopEnabled's tooltip), so requiring it
        inside the run's own range would almost never find real harvest
        data at all.

        Harvest yield is stored in kg/ha by this codebase's own convention
        (see harvest.manual's "Yield (kg/ha)" report column and
        widgets/add_data_form.py's opHarvest field, both kg/ha) - divided
        by 1000 here to compare against SeasonEstimate.estimated_yield_t_ha.

        A result under :data:`_MIN_USABLE_YIELD_T_HA` is treated the same
        as "nothing found" (``None``) rather than returned as-is: a real
        yield-monitor pass logs plenty of near-zero readings of its own
        (headland turns, the header engaging/disengaging, calibration) -
        averaged in alongside genuine ones for a field/year with only a
        handful of intersecting points, these can drag the result down to
        a implausibly tiny fraction of a tonne no real harvest (of any
        crop this codebase models - see crop_models.CROP_MODELS' lowest
        potential_yield_t_ha) would ever genuinely average to. Silently
        keeping a result like that fed absurd percentages into "Teach the
        model"'s Diff column (predicted/near-zero-actual is enormous) and
        would have quietly corrupted any fit trained against it - the
        skip reason callers already show for ``None`` here
        ('no usable harvest yield for that year') describes this case
        just as accurately as a table with no rows at all.
        """
        year = int(date_to[:4])
        values = []
        # date_ is often NULL on a harvest.manual row created by the older
        # bulk-import mapping tool (import_data/insert_manual_from_file.py) -
        # only date_text is set there (e.g. 'c_2018-09-20') - so this falls
        # back to matching the year inside that text when date_ isn't set.
        manual_rows = db_rows(self.db.execute_and_return(
            "SELECT yield FROM harvest.manual WHERE field = %s"
            " AND (extract(year FROM date_) = %s OR date_text LIKE %s)",
            params=(field_name, year, f'%{year}%')))
        for (yield_value,) in manual_rows:
            try:
                values.append(float(yield_value) / 1000.0)
            except (TypeError, ValueError):
                continue  # e.g. blank, or a column-name reference like 'yield_kg_ha'
        for table in self._candidate_harvest_tables(field_name):
            yield_col = self._find_column('harvest', table, ('yield',))
            if not yield_col:
                continue
            # ('yield',) matches on substring, so this can just as easily
            # land on a diagnostic/status column that happens to contain
            # "yield" (e.g. a real report: a machine's "Yield Measurement
            # I/O" on/off flag, stored as text) as on the real numeric
            # yield value - avg() outright doesn't exist for text, so a
            # bare avg({col}) crashed instead of just finding this table's
            # "yield" data unusable, the same way an unparseable
            # harvest.manual row above is simply skipped. Casting to text
            # first works for every column type (already-numeric columns
            # included), so this doesn't need to know in advance which
            # kind of column it got.
            rows = db_rows(self.db.execute_and_return(
                pgsql.SQL(
                    "SELECT avg(CASE WHEN {col}::text ~ '^-?[0-9]+(\\.[0-9]+)?$'"
                    " THEN {col}::text::double precision END)"
                    " FROM harvest.{tbl} t, fields f"
                    " WHERE f.field_name = %s AND st_intersects(t.pos, f.polygon)"
                    " AND extract(year FROM t.date_) = %s"
                ).format(col=pgsql.Identifier(yield_col), tbl=pgsql.Identifier(table)),
                params=(field_name, year)))
            if rows and rows[0][0] is not None:
                values.append(float(rows[0][0]) / 1000.0)
        if not values:
            return None
        average = sum(values) / len(values)
        if average < _MIN_USABLE_YIELD_T_HA:
            return None
        return average

    def _manual_and_import_count(self, schema, field_name, year):
        """Row count in ``schema`` (``plant``/``ferti``/``soil``) for
        field_name in ``year`` - ``schema.manual`` (plain ``field`` column,
        ``date_``/``date_text`` year match, same NULL-``date_`` fallback
        :meth:`_load_actual_yield_t_ha` already uses for harvest) plus
        every ``schema.<table>`` import spatially matching the field (via
        :meth:`_candidate_tables`), counted with the same
        ``st_intersects`` join :meth:`_load_actual_yield_t_ha` uses for
        harvest tables. Answers "does field X have schema data for year
        Y" for the "Data inventory" tab - see :meth:`_field_year_inventory`.
        """
        count = 0
        manual_rows = db_rows(self.db.execute_and_return(
            pgsql.SQL(
                "SELECT count(*) FROM {schema}.manual WHERE field = %s"
                " AND (extract(year FROM date_) = %s OR date_text LIKE %s)"
            ).format(schema=pgsql.Identifier(schema)),
            params=(field_name, year, f'%{year}%')))
        if manual_rows:
            count += manual_rows[0][0]
        for table in self._candidate_tables(schema, field_name):
            date_col = self._find_column(schema, table, ('date',))
            if not date_col:
                continue
            rows = db_rows(self.db.execute_and_return(
                pgsql.SQL(
                    "SELECT count(*) FROM {schema}.{tbl} t, fields f"
                    " WHERE f.field_name = %s AND st_intersects(t.polygon, f.polygon)"
                    " AND extract(year FROM t.{col}) = %s"
                ).format(schema=pgsql.Identifier(schema), tbl=pgsql.Identifier(table),
                        col=pgsql.Identifier(date_col)),
                params=(field_name, year)))
            if rows:
                count += rows[0][0]
        return count

    def _soil_available(self, field_name):
        """``(found, count)`` of usable soil samples on file for
        field_name, from either source :meth:`_load_soil` itself reads -
        any year, unlike every other :meth:`_field_year_inventory`
        category. Soil composition is treated as stable rather than
        something that goes stale (see :meth:`_load_soil`'s docstring:
        the reading *closest* to a run's target date wins, however old),
        so checking it against the tab's currently-selected year the same
        way Planting/Fertilizing/Harvest are would show "Missing" for a
        field with a perfectly usable sample on file just because it was
        logged in a different year - misleading on a tab whose whole
        point is showing what the crop model actually has available."""
        count = 0
        manual_rows = db_rows(self.db.execute_and_return(
            "SELECT clay FROM soil.manual WHERE field = %s", params=(field_name,)))
        count += sum(1 for (clay,) in manual_rows if clay is not None and isfloat(clay))
        for table in self._candidate_tables('soil', field_name):
            clay_col = self._find_column('soil', table, _CLAY_COLUMN_PREFIXES)
            if not clay_col:
                continue
            rows = db_rows(self.db.execute_and_return(pgsql.SQL(
                "SELECT count(*) FROM soil.{tbl}"
                " WHERE {col} IS NOT NULL AND {col}::text ~ '^-?[0-9]+(\\.[0-9]+)?$'"
            ).format(tbl=pgsql.Identifier(table), col=pgsql.Identifier(clay_col))))
            if rows:
                count += rows[0][0]
        return count > 0, count

    def _harvest_count(self, field_name, year):
        """Row count of actual harvest data on file for field_name in
        ``year`` - the same two sources :meth:`_load_actual_yield_t_ha`
        averages a yield figure from, just counted instead (this doesn't
        care what the figure is, only whether harvest data exists at all
        for that year) - see :meth:`_field_year_inventory`."""
        count = 0
        manual_rows = db_rows(self.db.execute_and_return(
            "SELECT count(*) FROM harvest.manual WHERE field = %s"
            " AND (extract(year FROM date_) = %s OR date_text LIKE %s)",
            params=(field_name, year, f'%{year}%')))
        if manual_rows:
            count += manual_rows[0][0]
        for table in self._candidate_harvest_tables(field_name):
            rows = db_rows(self.db.execute_and_return(
                pgsql.SQL(
                    "SELECT count(*) FROM harvest.{tbl} t, fields f"
                    " WHERE f.field_name = %s AND st_intersects(t.pos, f.polygon)"
                    " AND extract(year FROM t.date_) = %s"
                ).format(tbl=pgsql.Identifier(table)),
                params=(field_name, year)))
            if rows:
                count += rows[0][0]
        return count

    def _dated_table_exists(self, field_name, year, suffix):
        """``(found, row_count)`` for ``weather.<field>_<suffix>_<year>`` -
        ``suffix`` is ``'irrigation_events'`` (see
        import_data/handle_irrigation.py's ``_store_dated_operation``) or
        ``'weather'`` (see import_data/handle_weather.py's
        ``_start_fetch_one``) - both are one table per field per year, no
        manual-entry alternative for either. Same ``check_table_exists``
        probe :meth:`_load_irrigation` already does for the irrigation
        case, generalised for weather too - see
        :meth:`_field_year_inventory`."""
        table = check_text(f'{field_name}_{suffix}_{year}')
        if not self.db.check_table_exists(table, 'weather', False):
            return False, 0
        rows = db_rows(self.db.execute_and_return(
            pgsql.SQL("SELECT count(*) FROM weather.{tbl}").format(tbl=pgsql.Identifier(table))))
        return True, (rows[0][0] if rows else 0)

    def _field_year_inventory(self, field_name, year):
        """Ordered ``(category_label, op_key, found, count, optional)``
        rows for the six data categories the crop model actually consumes,
        for field_name in ``year`` - drives the "Data inventory" tab (see
        widgets/crop_simulation_page.py). Spraying/"other" are
        deliberately excluded: neither feeds :func:`estimate_season`, and
        "other" can't be matched to a field reliably anyway - each save
        creates its own dynamically-named table
        (import_data/save_other_data.py) with the field embedded only as
        a string suffix, no queryable column.

        ``optional`` marks Soil, and only Soil: :func:`estimate_season`
        already falls back to a generic loam estimate when clay/organic-
        matter is unavailable (``SeasonEstimate.used_default_soil`` - see
        its docstring), so a field with only an EM38 conductivity survey
        on file (real, common soil data this codebase doesn't parse into
        clay%/humus% at all) isn't missing something the model actually
        needs to run, unlike a real gap in Planting/Harvest/Weather. The
        tab must not show that the same way it shows an actual gap."""
        rows = []
        planting = self._manual_and_import_count('plant', field_name, year)
        rows.append(('Planting', 'opPlanting', planting > 0, planting, False))
        ferti = self._manual_and_import_count('ferti', field_name, year)
        rows.append(('Fertilizing', 'opFertilizing', ferti > 0, ferti, False))
        harvest = self._harvest_count(field_name, year)
        rows.append(('Harvest', 'opHarvest', harvest > 0, harvest, False))
        soil_found, soil_count = self._soil_available(field_name)
        rows.append(('Soil', 'opSoil', soil_found, soil_count, True))
        irrigation_found, irrigation_count = self._dated_table_exists(
            field_name, year, 'irrigation_events')
        rows.append(('Irrigation', 'opIrrigation', irrigation_found, irrigation_count, False))
        weather_found, weather_count = self._dated_table_exists(field_name, year, 'weather')
        rows.append(('Weather', 'opWeather', weather_found, weather_count, False))
        return rows

    def _check_field_year_data(self):
        """PBCheckData.clicked - populates TWDataInventory with
        :meth:`_field_year_inventory`'s results for whatever field/year is
        currently selected on the Data inventory tab. Runs synchronously:
        six lightweight COUNT queries for one field/year, nowhere near the
        "needs a background task" territory :class:`_RunSimulationTask`'s
        work is."""
        field_name = self.page.CBInventoryField.currentText()
        if not field_name or field_name == self.tr('--- Select field ---'):
            report_warning(self.tr('Please select a field first.'))
            return
        year = self.page.SBInventoryYear.value()
        rows = self._field_year_inventory(field_name, year)
        table = self.page.TWDataInventory
        table.setRowCount(len(rows))
        for row_idx, (label, op_key, found, count, optional) in enumerate(rows):
            table.setItem(row_idx, 0, QTableWidgetItem(label))
            if found:
                status_text = self.tr('✓ Found')
            elif optional:
                status_text = self.tr('○ Optional (not on file)')
            else:
                status_text = self.tr('✗ Missing')
            table.setItem(row_idx, 1, QTableWidgetItem(status_text))
            table.setItem(row_idx, 2, QTableWidgetItem(str(count)))
            table.setCellWidget(
                row_idx, 3, self._build_inventory_action(op_key, found, field_name, year))

    def _build_inventory_action(self, op_key, found, field_name, year):
        """The Action-column button for one :meth:`_field_year_inventory`
        row - ``None`` (no button) when that category is already found.
        Weather fetches inline (reuses
        :meth:`import_data.handle_weather.WeatherData._start_fetch_one` -
        the exact background-task/overwrite-confirm flow "Add data ->
        Weather" already uses); every other missing category jumps to
        "Add data", pre-filled - Irrigation has no manual form at all, so
        that jump opens the Raindancer dialog directly (see
        ``AddDataForm._open``'s own ``picker_action`` branch), the rest
        open that operation's manual form with the field pre-selected."""
        if found:
            return None
        if op_key == 'opWeather':
            button = QPushButton(self.tr('Load weather'))
            button.clicked.connect(lambda: self._load_weather_for_gap(field_name, year))
            return button
        label = (self.tr('Import (Raindancer)') if op_key == 'opIrrigation'
                else self.tr('Add manual entry'))
        button = QPushButton(label)
        button.clicked.connect(lambda: self._open_add_data_for_gap(op_key, field_name))
        return button

    def _open_add_data_for_gap(self, op_key, field_name):
        """Switches the dock to "Add data" and opens ``op_key``'s card,
        pre-filled with field_name - see widgets/add_data_form.py's
        ``OPERATIONS``/``AddDataForm._open``. The sidebar highlight
        follows automatically (``GeoDataFarm_dockwidget.py``'s
        ``_sync_sidebar``, driven by ``tabWidget.currentChanged``) - no
        need to touch the sidebar list directly."""
        dock = self.parent.dock_widget
        dock.tabWidget.setCurrentWidget(dock.tabAddData)
        form = self.parent.add_data_form
        form._open(op_key)
        form.cbField.setCurrentText(field_name)

    def _load_weather_for_gap(self, field_name, year):
        """Fetches and stores a full calendar year of weather for
        field_name - the "Load weather" action for a missing Weather row,
        reusing ``WeatherData._start_fetch_one`` exactly as "Add data ->
        Weather"'s own "Fetch weather" button does (background task,
        overwrite-confirm, ``weather.<field>_weather_<year>`` - see
        :meth:`_dated_table_exists`)."""
        self.parent.weather_data._start_fetch_one(field_name, f'{year}-01-01', f'{year}-12-31')

    def _load_weather(self, field_name, date_from, date_to):
        """Returns ``(weather, warning)`` - ``warning`` is a ready-to-show
        message (or ``None`` on success) rather than being shown directly
        here, since this also runs from :meth:`_compute_simulation` on a
        background QgsTask's worker thread (see :class:`_RunSimulationTask`),
        where touching the message bar directly isn't safe - only the
        caller, back on the main thread, may actually call report_warning
        with it (see :meth:`_apply_simulation_result`).

        Prefers whatever's already stored in ``weather.<field>_weather_
        <year>`` (the free "Load weather" feature - see import_data/
        handle_weather.py) over a live Open-Meteo fetch, one calendar year
        at a time, live-fetching only the years that aren't already
        stored. Reproduces the real bug report: a farm-wide "Teach the
        model" scan fetches live weather for every field regardless of
        what's already on file, and a big farm's worth of sequential
        requests routinely tripped Open-Meteo's per-minute rate limit -
        "Minutely API request limit exceeded" - silently losing entire
        fields that had nothing actually missing. The stored table is
        missing solar_radiation_mj_m2/daylight_hours (see handle_weather.
        py's ``_store`` - it only ever persisted three of the five fields
        ``daily_weather`` fetches), but those two are never read by
        season_water_model.py's actual yield estimate (they're
        Optional[float] = None on DailyWeather for a reason - see that
        class's docstring), so this is a strictly safe substitution for
        what this method is actually used for, not a precision trade-off.
        """
        rows = db_rows(self.db.execute_and_return(
            "SELECT st_x(st_centroid(polygon)), st_y(st_centroid(polygon))"
            " FROM fields WHERE field_name = %s", params=(field_name,)))
        if not rows:
            return [], self.tr('Could not find the location of that field.')
        longitude, latitude = float(rows[0][0]), float(rows[0][1])
        # Fetch past the "to" date so events near it still have enough
        # forward-looking weather for the advanced tier's water/N balance -
        # but Open-Meteo's historical archive can't return data beyond
        # today, so cap the request there.
        today_str = datetime.now().strftime('%Y-%m-%d')
        horizon_to = min(
            (datetime.strptime(date_to, '%Y-%m-%d')
             + timedelta(days=ADVANCED_HORIZON_DAYS)).strftime('%Y-%m-%d'),
            today_str)
        api_start = min(date_from, horizon_to)

        start_year, end_year = int(api_start[:4]), int(horizon_to[:4])
        years = list(range(start_year, end_year + 1))
        year_bounds = {}
        for y in years:
            y_from = api_start if y == start_year else '{}-01-01'.format(y)
            y_to = horizon_to if y == end_year else '{}-12-31'.format(y)
            table = check_text('{}_weather_{}'.format(field_name, y))
            stored = self.db.check_table_exists(table, 'weather', False)
            year_bounds[y] = (y_from, y_to, stored, table)

        weather = []
        warnings = []
        gap_from = None
        for idx, y in enumerate(years):
            y_from, y_to, stored, table = year_bounds[y]
            if stored:
                if gap_from is not None:
                    prev_to = year_bounds[years[idx - 1]][1]
                    fetched, warning = self._fetch_live_weather(
                        latitude, longitude, gap_from, prev_to)
                    weather.extend(fetched)
                    if warning:
                        warnings.append(warning)
                    gap_from = None
                weather.extend(self._read_stored_weather(table, y_from, y_to))
            elif gap_from is None:
                gap_from = y_from
        if gap_from is not None:
            fetched, warning = self._fetch_live_weather(
                latitude, longitude, gap_from, horizon_to)
            weather.extend(fetched)
            if warning:
                warnings.append(warning)

        weather.sort(key=lambda w: w.date)
        if not weather:
            return [], '; '.join(warnings) if warnings else self.tr(
                'Open-Meteo returned no weather data for that field/period.')
        return weather, ('; '.join(warnings) if warnings else None)

    def _fetch_live_weather(self, latitude, longitude, date_from, date_to):
        """One live Open-Meteo call for ``[date_from, date_to]``, as
        :class:`DailyWeather` rows - the fallback :meth:`_load_weather`
        only reaches for a year with no stored table on file at all (see
        its own docstring)."""
        try:
            daily = self.weather_client.daily_weather(
                latitude, longitude, date_from, date_to)
        except OpenMeteoError as e:
            return [], self.tr(
                'Could not fetch weather for that field/period: {error}'
            ).format(error=str(e))
        if not daily:
            return [], self.tr(
                'Open-Meteo returned no weather data for that field/period.')
        return [DailyWeather(date=d['date'], precipitation_mm=d['precipitation_mm'],
                             et0_mm=d['et0_mm'], temp_mean_c=d['temp_mean_c'],
                             solar_radiation_mj_m2=d.get('solar_radiation_mj_m2'),
                             daylight_hours=d.get('daylight_hours'))
               for d in daily], None

    def _read_stored_weather(self, table, date_from, date_to):
        """:class:`DailyWeather` rows from a previously-fetched
        ``weather.<table>`` (see import_data/handle_weather.py), for the
        slice ``[date_from, date_to]`` - solar_radiation_mj_m2/
        daylight_hours are always None here (that table never stored
        them - see :meth:`_load_weather`'s docstring for why that's fine
        for this method's own purposes)."""
        rows = db_rows(self.db.execute_and_return(pgsql.SQL(
            "SELECT date_, precipitation_mm, temp_mean_c, et0_mm"
            " FROM weather.{tbl} WHERE date_ >= %s AND date_ <= %s"
        ).format(tbl=pgsql.Identifier(table)), params=(date_from, date_to)))
        return [DailyWeather(date=self._as_date_str(date_), precipitation_mm=precip,
                             temp_mean_c=temp, et0_mm=et0)
               for date_, precip, temp, et0 in rows]

    def _load_soil(self, field_name, target_date=None):
        """Usable clay%/organic-matter% for the field, from either
        ``soil.manual`` or an imported ``soil.*`` table matched spatially
        (see :meth:`_candidate_tables`) - also the field-wide fallback for
        cells with no imported soil sample of their own (see
        :meth:`_resolve_soil_by_cell`). Soil composition is treated as
        stable over time rather than something that goes stale, so unlike
        :meth:`_load_crop`/:meth:`_load_spacing` (which only look on/before
        their target date), the reading *closest* to ``target_date`` wins,
        whether it was taken earlier or later - e.g. with samples from 2016
        and 2026 on file, 2025 uses the 2026 sample and 2017 uses the 2016
        one. With no ``target_date`` the most recent reading on file is
        used (unchanged from before)."""
        candidates = list(db_rows(self.db.execute_and_return(
            "SELECT date_, clay, humus FROM soil.manual WHERE field = %s",
            params=(field_name,))))
        for table in self._candidate_tables('soil', field_name):
            clay_col = self._find_column('soil', table, _CLAY_COLUMN_PREFIXES)
            humus_col = self._find_column('soil', table, _HUMUS_COLUMN_PREFIXES)
            if not clay_col:
                continue
            select = pgsql.SQL(', ').join([
                pgsql.Identifier(clay_col),
                pgsql.Identifier(humus_col) if humus_col else pgsql.SQL('NULL')])
            query = pgsql.SQL(
                "SELECT date_, {select} FROM soil.{tbl}"
            ).format(select=select, tbl=pgsql.Identifier(table))
            candidates.extend(db_rows(self.db.execute_and_return(query)))
        usable = [(self._as_date_str(date_) if date_ else None, clay_text, humus_text)
                 for date_, clay_text, humus_text in candidates
                 if clay_text is not None and isfloat(clay_text)]
        if not usable:
            return None, None
        if target_date:
            target = datetime.strptime(target_date, '%Y-%m-%d')

            def distance(row):
                if not row[0]:
                    return timedelta.max
                return abs(datetime.strptime(row[0], '%Y-%m-%d') - target)

            usable.sort(key=distance)
        else:
            usable.sort(key=lambda row: row[0] or '', reverse=True)
        _date, clay_text, humus_text = usable[0]
        clay = float(clay_text)
        humus = float(humus_text) if humus_text is not None and isfloat(humus_text) else None
        return clay, humus

    def _load_spacing(self, field_name):
        """Most recent usable in-row planting spacing (mm) for the field,
        from either ``plant.manual`` or an imported ``plant.*`` table
        matched spatially (see :meth:`_candidate_tables`) - mirrors
        :meth:`_load_soil`. Field-wide only, unlike crop/variety/soil,
        since spacing only ever feeds the single season-estimate number
        (see support_scripts/crop_models.spacing_yield_multiplier) rather
        than the per-cell stress map. None if nothing usable is on file,
        which that function treats the same as "not modelled": no effect
        on the yield ceiling."""
        candidates = list(db_rows(self.db.execute_and_return(
            "SELECT date_, spacing FROM plant.manual WHERE field = %s",
            params=(field_name,))))
        for table in self._candidate_tables('plant', field_name):
            # 'distance' too - a real ISO-XML DDOP designator seen in the
            # field was "Set Planting Distance mm", not "spacing" at all.
            spacing_col = self._find_column('plant', table, ('spacing', 'distance'))
            if not spacing_col:
                continue
            query = pgsql.SQL(
                "SELECT date_, {col} FROM plant.{tbl}"
            ).format(col=pgsql.Identifier(spacing_col), tbl=pgsql.Identifier(table))
            candidates.extend(db_rows(self.db.execute_and_return(query)))
        candidates.sort(key=lambda row: self._as_date_str(row[0]) if row[0] else '',
                        reverse=True)
        for _date, spacing_text in candidates:
            if spacing_text is not None and isfloat(spacing_text):
                return float(spacing_text)
        return None

    # ------------------------------------------------------------------
    # Per-cell stress map
    # ------------------------------------------------------------------

    def _compute_cell_traces(self, field_name, date_from, date_to, weather,
                             field_crop, field_clay, field_organic_matter, task=None,
                             planting_date=None, harvest_date=None, spacing_mm=None,
                             field_relative_yield_nitrogen=1.0,
                             field_relative_yield_potassium=1.0,
                             field_relative_yield_heat=1.0,
                             include_daily_yields=False):
        """Runs the per-cell day-by-day water balance that drives the date
        slider's stress map - see :func:`support_scripts.season_water_model.
        daily_trace_with_relative_yield`. Each cell uses its own crop/variety/soil where
        imported data covers it
        (:meth:`_resolve_crop_and_variety_by_cell`/:meth:`_resolve_soil_by_cell`)
        and its own logged irrigation (:meth:`_resolve_irrigation_by_cell`),
        falling back to the field-wide crop/soil reading where nothing more
        specific is on file (a cell simply not being irrigated is left as
        zero, not backfilled from the field-wide total - see that method's
        docstring). Weather is shared field-wide - it doesn't vary
        meaningfully within one field, so it's fetched once for the whole
        run (see :meth:`_load_weather`). Every cell's saved crop/variety
        settings overrides (support_scripts/crop_model_settings.py) are
        looked up explicitly here, so the stress map - like the season
        estimate - reflects them, instead of relying on crop_models.
        get_crop_model's name-matching fallback.

        A pure computation - no widget access, and it *returns* what it
        found rather than assigning to ``self._cell_*`` directly, so it's
        safe to call from a background QgsTask's worker thread (see
        :meth:`_compute_simulation`); ``field_name`` is always passed
        explicitly for the same reason (see
        :meth:`_resolve_crop_and_variety_by_cell`'s docstring). ``task``,
        if given, is checked periodically so a cancelled task can stop
        early instead of grinding through every remaining cell.
        ``planting_date``/``harvest_date`` (field-wide - see
        :meth:`_compute_simulation`) are passed straight through to every
        cell's own :func:`season_water_model.daily_trace_with_relative_yield`
        call, so the stress map's GDD clock stays consistent with the
        season summary's even though each cell can still use its own
        crop/variety/soil. ``spacing_mm`` and the three
        ``field_relative_yield_*`` figures are also field-wide (nitrogen/
        potassium/heat aren't resolved per cell - see
        :func:`season_water_model.daily_trace_with_relative_yield`'s
        docstring) and are combined with each cell's own water-only
        relative yield via the same Liebig's-law-of-the-minimum rule as
        :func:`season_water_model.estimate_season`, to produce the yield
        map (see ``cell_yields`` below).

        Returns
        -------
        tuple
            ``(cell_polygons, cell_traces, cell_varieties, trace_dates,
            cell_water_totals, cell_yields)`` - ``cell_water_totals`` is
            ``cell_id -> {date_str: cumulative_mm}``, rain (field-wide,
            same running total for every cell) plus that cell's own
            irrigation, both accumulated up to and including each date;
            drives the heatmap's "rain + irrigation" mode (see
            :meth:`_render_heatmap`) - pure arithmetic on
            ``weather``/``irrigation_by_cell``, both already fetched for
            the stress trace below, so no second water-balance pass is
            needed. ``cell_yields`` is ``cell_id -> t/ha`` at season end,
            following that cell's own crop/variety potential and spacing.
            When ``include_daily_yields`` is true, a seventh return item
            contains ``cell_id -> {date: t/ha}`` projections.
        """
        cells = field_grid.build_grid(self.db, field_name)
        cell_polygons = {c.cell_id: c.polygon_wkt for c in cells}
        cell_traces = {}
        cell_varieties = {}
        cell_water_totals = {}
        cell_yields = {}
        cell_yields_by_date = {}
        trace_dates = sorted({w.date for w in weather})
        if not cells:
            field_grid.drop_grid(self.db)
            result = (cell_polygons, cell_traces, cell_varieties, trace_dates,
                      cell_water_totals, cell_yields)
            return result + (cell_yields_by_date,) if include_daily_yields else result
        crop_variety_by_cell = self._resolve_crop_and_variety_by_cell(field_name)
        soil_by_cell = self._resolve_soil_by_cell(field_name)
        irrigation_by_cell = self._resolve_irrigation_by_cell(
            field_name, date_from, date_to)
        rain_by_date = {w.date: (w.precipitation_mm or 0.0) for w in weather}
        cumulative_rain_by_date = {}
        running_rain = 0.0
        for d in trace_dates:
            running_rain += rain_by_date.get(d, 0.0)
            cumulative_rain_by_date[d] = running_rain
        # Most cells share a handful of (crop, variety) combinations (often
        # just one) - resolving settings is a DB round trip, so cache by
        # that pair instead of re-querying per cell (a large field can have
        # thousands - see support_scripts/field_grid.py's cell budget).
        model_cache = {}
        for cell in cells:
            if task is not None and task.isCanceled():
                break
            cell_crop, cell_variety = crop_variety_by_cell.get(cell.cell_id, (None, None))
            crop_name = cell_crop or field_crop
            clay, organic_matter = soil_by_cell.get(
                cell.cell_id, (field_clay, field_organic_matter))
            cell_irrigation = irrigation_by_cell.get(cell.cell_id, {})
            cache_key = (crop_name, cell_variety)
            cell_model = model_cache.get(cache_key)
            if cell_model is None:
                cell_model = crop_model_settings.effective_crop_model(
                    self.db, crop_name, variety=cell_variety)
                model_cache[cache_key] = cell_model
            trace_result = daily_trace_with_relative_yield(
                weather, crop_name, clay, organic_matter,
                cell_irrigation, crop_model=cell_model,
                planting_date=planting_date, harvest_date=harvest_date,
                include_daily_relative_yield=include_daily_yields)
            if include_daily_yields:
                trace, relative_yield_water, _water_limiting_stage, daily_relative_yield = trace_result
            else:
                trace, relative_yield_water, _water_limiting_stage = trace_result
            cell_traces[cell.cell_id] = {p.date: p for p in trace}
            if cell_variety:
                cell_varieties[cell.cell_id] = cell_variety
            relative_yield = min(relative_yield_water, field_relative_yield_nitrogen,
                                 field_relative_yield_potassium, field_relative_yield_heat)
            spacing_multiplier = crop_models.spacing_yield_multiplier(cell_model, spacing_mm)
            effective_potential_yield = cell_model.potential_yield_t_ha * spacing_multiplier
            cell_yields[cell.cell_id] = round(relative_yield * effective_potential_yield, 1)
            if include_daily_yields:
                cell_yields_by_date[cell.cell_id] = {
                    d: round(min(relative_yield, field_relative_yield_nitrogen,
                                 field_relative_yield_potassium, field_relative_yield_heat)
                             * effective_potential_yield, 1)
                    for d, relative_yield in daily_relative_yield.items()}
            running_irrigation = 0.0
            water_totals = {}
            for d in trace_dates:
                running_irrigation += cell_irrigation.get(d, 0.0)
                water_totals[d] = cumulative_rain_by_date[d] + running_irrigation
            cell_water_totals[cell.cell_id] = water_totals
        field_grid.drop_grid(self.db)
        result = (cell_polygons, cell_traces, cell_varieties, trace_dates,
              cell_water_totals, cell_yields)
        return result + (cell_yields_by_date,) if include_daily_yields else result

    def _resolve_irrigation_by_cell(self, field_name, date_from, date_to):
        """cell_id -> {date_str: total_mm}, matching each logged irrigation
        row (support_scripts/field_grid.py's grid must already be built -
        see :meth:`_compute_cell_traces`) to whichever cells its own real
        (buffered) flight-path geometry actually covers - see
        import_data/handle_irrigation.py's ``_store_dated_operation``. A
        pass that only crossed part of the field only contributes to the
        cells it actually passed over. A cell with nothing logged for it
        gets an empty dict - genuinely zero irrigation, not a field-wide
        fallback, since unlike crop/soil "not irrigated" is a normal,
        meaningful state for a cell to be in."""
        result = {}
        for year in range(int(date_from[:4]), int(date_to[:4]) + 1):
            table = check_text('{}_irrigation_events_{}'.format(field_name, year))
            if not self.db.check_table_exists(table, 'weather', False):
                continue
            for row in field_grid.join_grid_to_table(
                    self.db, 'weather', table, ['date_', 'irrigation_mm']):
                mm = row.get('irrigation_mm')
                date_value = row.get('date_')
                if mm is None or date_value is None:
                    continue
                date_str = self._as_date_str(date_value)
                if not (date_from <= date_str <= date_to):
                    continue
                cell_totals = result.setdefault(row['cell_id'], {})
                cell_totals[date_str] = cell_totals.get(date_str, 0.0) + float(mm)
        return result

    def _resolve_crop_and_variety_by_cell(self, field_name=None):
        """cell_id -> (crop_or_None, variety_or_None), the most recent per
        cell across every imported ``plant.*`` table matched to the
        field's current grid (:func:`field_grid.build_grid` must already
        have been called - see :meth:`_compute_cell_traces`).

        ``field_name`` defaults to the field combo's current value (for
        existing callers), but :meth:`_compute_cell_traces` always passes
        it explicitly - reading a Qt widget's value isn't safe from the
        background thread that method can run on (see
        :class:`_RunSimulationTask`).

        Crop and variety are tracked from separate columns and never
        conflated: a plant table naming only a variety (no ``crop``
        column - a common shape for a machine-logged planting pass, which
        knows what product it planted but not its botanical name, e.g. a
        "arsenal"/"fontane"/"solist" variety layer with no "potato"
        anywhere in it) must never let that variety name masquerade as
        the crop - see :meth:`_compute_cell_traces`'s fallback to the
        field-wide crop, and support_scripts/crop_model_settings.py's
        ``effective_crop_model`` for how crop- and variety-level settings
        combine. Cells with nothing imported are absent."""
        field_name = field_name or self._current_field_name()
        best = {}  # cell_id -> (date_str, crop_or_None, variety_or_None)
        for table in self._candidate_tables('plant', field_name):
            crop_col = self._find_column('plant', table, ('crop',))
            variety_col = self._find_column('plant', table, ('variety',))
            if variety_col == crop_col:
                variety_col = None  # one ambiguous column: treat as crop only
            columns = ['date_'] + [c for c in (crop_col, variety_col) if c]
            if len(columns) == 1:
                continue  # neither a crop nor a variety column on this table
            for row in field_grid.join_grid_to_table(self.db, 'plant', table, columns):
                crop_value = row.get(crop_col) if crop_col else None
                variety_value = row.get(variety_col) if variety_col else None
                if not crop_value and not variety_value:
                    continue
                date_str = self._as_date_str(row['date_']) if row['date_'] else ''
                prev = best.get(row['cell_id'])
                if prev is None or date_str >= prev[0]:
                    best[row['cell_id']] = (
                        date_str, str(crop_value) if crop_value else None,
                        str(variety_value) if variety_value else None)
        return {cid: (v[1], v[2]) for cid, v in best.items()}

    def _resolve_soil_by_cell(self, field_name=None):
        """cell_id -> (clay, organic_matter), the most recent per cell
        across every imported ``soil.*`` table matched to the field's
        current grid. Cells with nothing imported are absent; the caller
        falls back to the field-wide soil reading. ``field_name`` defaults
        to the field combo's current value - see
        :meth:`_resolve_crop_and_variety_by_cell`'s docstring for why
        :meth:`_compute_cell_traces` always passes it explicitly instead."""
        field_name = field_name or self._current_field_name()
        best = {}  # cell_id -> (date_str, clay, humus)
        for table in self._candidate_tables('soil', field_name):
            clay_col = self._find_column('soil', table, _CLAY_COLUMN_PREFIXES)
            humus_col = self._find_column('soil', table, _HUMUS_COLUMN_PREFIXES)
            if not clay_col:
                continue
            columns = ['date_', clay_col] + ([humus_col] if humus_col else [])
            for row in field_grid.join_grid_to_table(self.db, 'soil', table, columns):
                clay_text = row.get(clay_col)
                if clay_text is None or not isfloat(clay_text):
                    continue
                humus_text = row.get(humus_col) if humus_col else None
                date_str = self._as_date_str(row['date_']) if row['date_'] else ''
                prev = best.get(row['cell_id'])
                if prev is None or date_str >= prev[0]:
                    humus = (float(humus_text)
                            if humus_text is not None and isfloat(humus_text) else None)
                    best[row['cell_id']] = (date_str, float(clay_text), humus)
        return {cid: (v[1], v[2]) for cid, v in best.items()}

    def _current_field_name(self):
        return self.page.CBField.currentText()

    def _setup_slider(self):
        n = len(self._trace_dates)
        self.page.SLDate.blockSignals(True)
        self.page.SLDate.setEnabled(n > 0)
        self.page.SLDate.setMinimum(0)
        self.page.SLDate.setMaximum(max(0, n - 1))
        self.page.SLDate.setValue(max(0, n - 1))  # default: the latest date
        self.page.SLDate.blockSignals(False)
        self.page.LSliderDate.setText(self._trace_dates[-1] if n else '-')
        self._render_heatmap(self._trace_dates[-1] if n else None)

    def _on_slider_changed(self, index):
        if not self._trace_dates or not (0 <= index < len(self._trace_dates)):
            return
        date_str = self._trace_dates[index]
        self.page.LSliderDate.setText(date_str)
        self._render_heatmap(date_str)

    def _change_map_mode(self, _index):
        """CBMapMode.currentIndexChanged - shows/hides LRainIrrigation and
        re-renders the heatmap at the slider's current date so switching
        between the stress, rain+irrigation and yield views doesn't need a
        fresh run (see _render_heatmap's map_mode branches)."""
        self.page.LRainIrrigation.setVisible(self.page.CBMapMode.currentData() == 'rain_irrigation')
        current = (self._trace_dates[self.page.SLDate.value()]
                  if self._trace_dates else None)
        self._render_heatmap(current)

    def _update_map_legend(self, date_str=None):
        """Updates the legend for the active field-map mode. Yield colors
        use the same low-to-high range as the cells currently rendered."""
        if self.page.CBMapMode.currentData() != 'yield':
            self.page.LMapLegend.setText(
                self.tr('Timing-risk markers / stress map legend:')
                + ' <font color="green">●</font> ' + self.tr('Low risk')
                + ' <font color="orange">●</font> ' + self.tr('Moderate risk')
                + ' <font color="red">●</font> ' + self.tr('High risk')
                + ' <font color="gray">●</font> '
                + self.tr('Unknown (no weather data)'))
            return
        cell_values = {
            cid: self._cell_yields_by_date.get(cid, {}).get(
                date_str, self._cell_yields.get(cid))
            for cid in self._cell_polygons}
        values = [v for v in cell_values.values() if v is not None]
        minimum = min(values, default=0.0)
        maximum = max(values, default=0.0)
        self.page.LMapLegend.setText(
            self.tr('Predicted yield:')
            + ' <font color="#d73027">●</font> '
            + self.tr('Low ({minimum:.1f} t/ha)').format(minimum=minimum)
            + ' <font color="#fee08b">●</font> '
            + self.tr('Medium')
            + ' <font color="#1a9850">●</font> '
            + self.tr('High ({maximum:.1f} t/ha)').format(maximum=maximum)
            + ' <font color="gray">●</font> '
            + self.tr('No estimate'))

    def _render_heatmap(self, date_str):
        # A bare Figure(), not pyplot's plt.subplots(): pyplot keeps every
        # figure it creates registered in its own global state until
        # explicitly closed, which - for a figure rebuilt on every slider
        # tick - both leaks memory and can make a stray native window pop
        # up outside the embedded canvas (matplotlib's Qt/pyplot
        # interaction, not something this code controls once a figure is
        # pyplot-tracked). A plain Figure never enters that registry.
        fig = Figure()
        ax = fig.add_subplot(111)
        # CBMapMode also switches this map (see _change_map_mode) between
        # the day-of stress reading, a cumulative rain+irrigation-received
        # reading (self._cell_water_totals - see _compute_cell_traces) and
        # a season-end predicted-yield reading (self._cell_yields - not
        # date-dependent, so it doesn't need date_str), each with its own
        # colormap/title so none are ever mistaken for one another.
        map_mode = self.page.CBMapMode.currentData()
        self._update_map_legend(date_str)
        if map_mode == 'yield' and self._cell_polygons:
            cell_values = {
                cid: self._cell_yields_by_date.get(cid, {}).get(
                    date_str, self._cell_yields.get(cid))
                for cid in self._cell_polygons}
            values = [v for v in cell_values.values() if v is not None]
            value_min = min(values, default=0.0)
            max_value = max(
                (v for v in cell_values.values() if v is not None), default=0.0)
            cmap = mpl.colormaps['RdYlGn']
            patches, colors = [], []
            for cell_id, polygon_wkt in self._cell_polygons.items():
                value = cell_values.get(cell_id)
                geom = shapely_wkt.loads(polygon_wkt)
                patches.append(MplPolygon(list(geom.exterior.coords), closed=True))
                color_fraction = ((value - value_min) / (max_value - value_min)
                                  if value is not None and max_value > value_min
                                  else 0.5)
                colors.append(cmap(color_fraction) if value is not None
                              else (0.6, 0.6, 0.6, 1.0))
            ax.add_collection(PatchCollection(patches, facecolor=colors, edgecolor='none'))
            ax.autoscale_view()
            ax.set_title(self.tr(
                'Predicted yield (darkest green = {max:.1f} t/ha)').format(max=max_value))
        elif date_str is not None and self._cell_polygons:
            if map_mode == 'rain_irrigation':
                cell_values = {cid: self._cell_water_totals.get(cid, {}).get(date_str)
                              for cid in self._cell_polygons}
                max_value = max(
                    (v for v in cell_values.values() if v is not None), default=0.0)
                cmap = mpl.colormaps['Blues']
                patches, colors = [], []
                for cell_id, polygon_wkt in self._cell_polygons.items():
                    value = cell_values[cell_id]
                    geom = shapely_wkt.loads(polygon_wkt)
                    patches.append(MplPolygon(list(geom.exterior.coords), closed=True))
                    colors.append(cmap(value / max_value) if value is not None and max_value
                                  else (0.6, 0.6, 0.6, 1.0))
                ax.add_collection(PatchCollection(patches, facecolor=colors, edgecolor='none'))
                ax.autoscale_view()
                ax.set_title(self.tr(
                    'Cumulative rain + irrigation through {date} (darkest = {max:.0f} mm)'
                ).format(date=date_str, max=max_value))
            else:
                cmap = mpl.colormaps['RdYlGn']
                patches, colors = [], []
                for cell_id, polygon_wkt in self._cell_polygons.items():
                    point = self._cell_traces.get(cell_id, {}).get(date_str)
                    geom = shapely_wkt.loads(polygon_wkt)
                    patches.append(MplPolygon(list(geom.exterior.coords), closed=True))
                    colors.append(cmap(point.wetness_fraction) if point is not None
                                  else (0.6, 0.6, 0.6, 1.0))
                ax.add_collection(PatchCollection(patches, facecolor=colors, edgecolor='none'))
                ax.autoscale_view()
                ax.set_title(self.tr('Field water stress on {}').format(date_str))
        else:
            ax.text(0.5, 0.5, self.tr('Run a simulation to see the field stress map.'),
                    ha='center', va='center', transform=ax.transAxes)
        ax.set_aspect('equal')
        ax.set_xticks([])
        ax.set_yticks([])
        if self.canvas is not None:
            self.page.mplvl.removeWidget(self.canvas)
            # The actual cause of the stray popup on every slider drag:
            # this canvas was visible a moment ago (it's the previous
            # day's heatmap), and setParent(None) alone doesn't hide a
            # widget that was already visible - it just detaches it,
            # leaving Qt to render it as its own top-level window since
            # it's now both visible and parentless. hide() first closes
            # that gap. See _show_simulation_spinner's matching comment.
            self.canvas.hide()
            self.canvas.setParent(None)
        self.canvas = FigureCanvas(fig)
        # Belt-and-braces against the same stray-window risk _plt.ioff()
        # (module top) targets from a different angle: force this to
        # always be treated as a plain child widget, never its own
        # top-level window, regardless of what triggers it.
        self.canvas.setWindowFlags(Qt.WindowType.Widget)
        self.page.mplvl.addWidget(self.canvas)
        self.canvas.draw()

    # ------------------------------------------------------------------
    # Field-wide rendering (per-application detail, season estimate)
    # ------------------------------------------------------------------

    def _render_details(self, results):
        self.page.TEDetails.setPlainText('\n\n'.join(
            '{date} [{tier} model - {crop}, {risk} risk]: {detail}{rate_notes}'.format(
                date=r.date, tier=r.tier, crop=r.crop_model, risk=r.risk,
                detail=r.detail, rate_notes=self._event_result_rate_notes(r))
            for r in results))
        self.page.LStatus.setText(summarize(results))

    def _event_result_rate_notes(self, result):
        """N's note always shows (a rate_kg_n_ha of None is always
        meaningful - see _rate_parse_note - regardless of source), but
        P/K/Mg only show a *positive* confirmation when a rate was
        actually parsed. EventResult (unlike the FertilizerEvent
        add_planned_event works from) doesn't carry the raw rate_text, so
        None here can't be told apart from "no rate given for this
        nutrient at all" (true for essentially every logged/imported
        event today, since none of the ferti.manual/imported tables have
        P/K/Mg columns wired up yet) - staying silent for those three
        avoids flagging every ordinary N-only application as if its P/K/Mg
        were typoed."""
        notes = self._rate_parse_note('N', result.rate_kg_n_ha,
            self.tr(' - won\'t count toward the nitrogen balance, and '
                    'can\'t use the advanced timing model'))
        for label, rate in (('P', result.rate_kg_p_ha), ('K', result.rate_kg_k_ha),
                           ('Mg', result.rate_kg_mg_ha)):
            if rate is not None:
                notes += self._rate_parse_note(label, rate)
        return notes

    def _render_season(self, season):
        """Shows a one-line pointer on the main page - the full breakdown
        (see :meth:`_season_full_text`) lives in the Crop model settings
        popup instead, next to the controls that actually change it."""
        if season.estimated_yield_t_ha is None:
            self.page.LSeasonEstimate.setText(
                self.tr('Irrigation/yield estimate: {note}').format(note=season.note))
            return
        pct_of_potential = (
            season.estimated_yield_t_ha / season.potential_yield_t_ha * 100
            if season.potential_yield_t_ha else 0.0)
        self.page.LSeasonEstimate.setText(self.tr(
            'Estimated yield ({crop}): {yield_t:.1f} t/ha ({pct:.0f}% of the '
            '{potential:.1f} t/ha well-managed baseline) - open "Crop model '
            'settings" above for the full breakdown and to adjust these '
            'assumptions.'
        ).format(crop=season.crop_model, yield_t=season.estimated_yield_t_ha,
                pct=pct_of_potential, potential=season.potential_yield_t_ha))

    def _render_actual_yield(self, actual_t_ha, predicted_t_ha):
        """Shows how the run's predicted yield compares to what the field
        actually produced, right under _render_season's estimate - see
        _load_actual_yield_t_ha. Hidden (rather than blank) when there's
        nothing to compare, e.g. a future/not-yet-harvested season, so it
        doesn't leave an empty line."""
        if actual_t_ha is None:
            self.page.LActualYield.hide()
            return
        diff_pct = ((predicted_t_ha - actual_t_ha) / actual_t_ha * 100
                   if predicted_t_ha is not None and actual_t_ha else 0.0)
        direction = self.tr('over-estimated') if diff_pct >= 0 else self.tr('under-estimated')
        self.page.LActualYield.setText(self.tr(
            'Actual harvested yield: {actual:.1f} t/ha (model predicted {predicted:.1f} '
            't/ha - {diff:.0f}% {direction}).'
        ).format(actual=actual_t_ha, predicted=predicted_t_ha or 0.0,
                 diff=abs(diff_pct), direction=direction))
        self.page.LActualYield.show()

    def _render_rain_irrigation(self, total_rain_mm, total_irrigation_mm, date_from, date_to):
        """Sets LRainIrrigation's text - always computed (unlike
        _render_actual_yield, a run always has a rain figure, even if 0),
        visibility is purely CBMapMode's job (see _change_map_mode), not
        this method's."""
        self.page.LRainIrrigation.setText(self.tr(
            'Total rain: {rain:.0f} mm + irrigation: {irrigation:.0f} mm = {total:.0f} mm '
            '({date_from} - {date_to}).'
        ).format(rain=total_rain_mm, irrigation=total_irrigation_mm,
                 total=total_rain_mm + total_irrigation_mm,
                 date_from=date_from, date_to=date_to))

    def _season_full_text(self, season):
        """The detailed irrigation/water/nitrogen breakdown - shown in the
        Crop model settings popup's live-results area (see
        :meth:`_recompute_settings_preview`)."""
        if season.estimated_yield_t_ha is None:
            return self.tr('Irrigation/yield estimate: {note}').format(note=season.note)
        pct_of_potential = (
            season.estimated_yield_t_ha / season.potential_yield_t_ha * 100
            if season.potential_yield_t_ha else 0.0)
        if season.logged_irrigation_mm > 0:
            irrigation_line = self.tr(
                'You logged {logged:.0f} mm of irrigation for this period; an '
                'estimated {irrig:.0f} mm more would have avoided water stress '
                'on {days} day(s).'
            ).format(logged=season.logged_irrigation_mm,
                    irrig=season.irrigation_need_mm, days=season.water_stress_days)
        else:
            irrigation_line = self.tr(
                'No irrigation logged for this period - an estimated {irrig:.0f} '
                'mm would have avoided water stress on {days} day(s). Log '
                'irrigation from the "Irrigation" card on Add data to refine '
                'this estimate.'
            ).format(irrig=season.irrigation_need_mm, days=season.water_stress_days)
        text = self.tr(
            'Estimated yield ({crop}): {yield_t:.1f} t/ha ({pct:.0f}% of the '
            '{potential:.1f} t/ha well-managed baseline). {irrigation_line} {note}'
        ).format(crop=season.crop_model, yield_t=season.estimated_yield_t_ha,
                pct=pct_of_potential, potential=season.potential_yield_t_ha,
                irrigation_line=irrigation_line, note=season.note)
        if season.limiting_factor == 'nitrogen':
            text += self.tr(
                '\n\nWater alone would have allowed an estimated {water_only:.1f} '
                't/ha - nitrogen is what\'s holding this estimate back.'
            ).format(water_only=season.estimated_yield_water_only_t_ha)
        elif season.limiting_factor == 'heat':
            text += self.tr(
                '\n\nWater alone would have allowed an estimated {water_only:.1f} '
                't/ha - heat stress is what\'s holding this estimate back.'
            ).format(water_only=season.estimated_yield_water_only_t_ha)
        elif season.limiting_factor == 'potassium':
            text += self.tr(
                '\n\nWater alone would have allowed an estimated {water_only:.1f} '
                't/ha - potassium is what\'s holding this estimate back.'
            ).format(water_only=season.estimated_yield_water_only_t_ha)
        return text

    # ------------------------------------------------------------------
    # "Teach your model" - farm-wide accuracy scan + per-crop fitting
    # ------------------------------------------------------------------

    def _harvest_years_for_field(self, field_name):
        """``{year: harvest_date_str}`` for every calendar year field_name
        has real harvest data on file for - the same two sources
        :meth:`_load_actual_yield_t_ha` averages a yield figure from
        (``harvest.manual`` and every spatially-matched ``harvest.*``
        import table), just bucketed by year here instead. Each year's
        date is the latest ``date_`` actually on file for it; a
        ``harvest.manual`` row logged only via ``date_text`` (no ``date_``
        - see that method's docstring) falls back to December 31 of the
        year read out of that text, since there's no real date to read,
        only a year. Drives the farm-wide "Teach your model" scan (see
        :meth:`_compute_teach_scan`) - only years with real ground truth
        are worth scanning at all."""
        best_date = {}

        def _note(year, date_str):
            if year not in best_date or date_str > best_date[year]:
                best_date[year] = date_str

        manual_rows = db_rows(self.db.execute_and_return(
            "SELECT date_, date_text FROM harvest.manual WHERE field = %s",
            params=(field_name,)))
        for date_value, date_text in manual_rows:
            if date_value is not None:
                date_str = self._as_date_str(date_value)
                _note(int(date_str[:4]), date_str)
            elif date_text:
                match = re.search(r'(19|20)\d{2}', date_text)
                if match:
                    year = int(match.group(0))
                    _note(year, '{}-12-31'.format(year))
        for table in self._candidate_harvest_tables(field_name):
            # Aggregated server-side (one row per calendar year) rather
            # than fetching every matching date_ - a real farm's harvest
            # tables run into the hundreds of thousands of GPS-referenced
            # rows, and only the single latest date per year is ever kept
            # (see _note) - pulling all of them across the network just to
            # throw away everything but a handful of max()es in Python was
            # a major cost of a farm-wide scan.
            rows = db_rows(self.db.execute_and_return(
                pgsql.SQL(
                    "SELECT extract(year FROM t.date_)::int, max(t.date_)"
                    " FROM harvest.{tbl} t, fields f"
                    " WHERE f.field_name = %s AND st_intersects(t.pos, f.polygon)"
                    " AND t.date_ IS NOT NULL"
                    " GROUP BY extract(year FROM t.date_)"
                ).format(tbl=pgsql.Identifier(table)),
                params=(field_name,)))
            for year, date_value in rows:
                date_str = self._as_date_str(date_value)
                _note(int(year), date_str)
        return best_date

    def _estimate_season_date_range(self, field_name, harvest_date):
        """``(season_from, season_to, planting_date_logged, crop)`` for one
        field/harvest date. ``season_to`` is ``harvest_date`` itself (the
        anchor :meth:`_harvest_years_for_field` found for that year);
        ``season_from`` prefers a real logged planting date on/before it
        (:meth:`_load_crop`, the same lookup the main Simulation tab uses
        to anchor its own GDD clock), falling back to
        :data:`_FALLBACK_SEASON_DAYS` days before ``harvest_date`` when
        there's no real planting record to go on -
        ``planting_date_logged`` flags which one this is, so a caller can
        tell a real anchor apart from a rough guess (see
        :class:`TrainingExample`). ``crop`` is whatever :meth:`_load_crop`
        found alongside that planting date - ``''`` if nothing is on file,
        in which case the caller should skip this field/year rather than
        run the model against a made-up crop."""
        crop, planting_date = self._load_crop(field_name, harvest_date)
        if planting_date:
            return planting_date, harvest_date, True, (crop or '')
        season_from = (datetime.strptime(harvest_date, '%Y-%m-%d')
                      - timedelta(days=_FALLBACK_SEASON_DAYS)).strftime('%Y-%m-%d')
        return season_from, harvest_date, False, (crop or '')

    def _compute_teach_scan(self, task=None, allow_multiyear_crops=False):
        """All of :meth:`run_teach_scan`'s slow work - mirrors
        :meth:`_compute_simulation` (see its docstring): no widget access,
        safe to run on :class:`_RunTeachScanTask`'s worker thread. Scans
        every field's every harvest year, building one self-contained
        :class:`TrainingExample` per field+year - each is computed
        independently (its own weather slice, events, soil, irrigation,
        crop), so a bad or missing year for one field never affects
        another's; only the weather fetch is shared across a field's own
        years (one Open-Meteo call spanning its full detected range, then
        sliced per season locally), the same "fetch once, slice locally"
        approach :meth:`_load_weather` already uses for a single run.

        ``allow_multiyear_crops``: with a real planting record on file (see
        :meth:`_estimate_season_date_range`), :meth:`_load_crop`/
        :meth:`_load_variety` always resolve the most recent one *on or
        before* the harvest date - with nothing fresher on file, that can
        be years older than the harvest itself. For an annual crop (most
        of them, including potato) that's not a genuine multi-year
        planting, just a gap in what's been logged - reproduces the real
        bug report where a field harvested in e.g. 2015/2019/2021/2023
        with only a single 2016 planting record on file produced one
        implausible training example per extra year, all sharing that
        same stale planting/variety. False (the default) skips any
        field/year whose resolved planting date isn't in the harvest's
        own calendar year; True restores the unfiltered fallback
        behaviour, for farms with genuinely multi-year crops (ley/
        grassland, asparagus, ...) where that's expected and correct.

        Returns
        -------
        (list[TrainingExample], collections.Counter)
            The training examples, and a count of every field/year skipped
            along the way, keyed by *why* - shown in the "Scan farm" status
            text (see :meth:`_apply_teach_scan_result`) so a farm where
            nothing (or less than expected) turns up says specifically what
            was missing, instead of just a bare "found 0" that looks
            identical whether nothing was logged at all or every field/year
            individually failed a different, fixable check.
        """
        examples = []
        skip_reasons = Counter()
        field_rows = db_rows(self.db.execute_and_return(
            "SELECT field_name FROM fields ORDER BY field_name"))
        total_fields = len(field_rows)
        for field_idx, (field_name,) in enumerate(field_rows):
            if task is not None and task.isCanceled():
                return examples, skip_reasons
            # QgsTask.setProgress() is thread-safe - unlike touching self.page
            # (see this method's own docstring), so it's safe to call from
            # here on the worker thread. Without it the task manager's
            # progress bar just sits at 0% for as long as the scan takes,
            # which - on a farm with enough imported data - can look exactly
            # like QGIS itself has frozen rather than a slow-but-running task.
            if task is not None:
                task.setProgress(100 * field_idx / total_fields)
            harvest_years = self._harvest_years_for_field(field_name)
            if not harvest_years:
                skip_reasons[self.tr('no harvest data on file')] += 1
                gdf_log.log('[Teach your model] {field}: skipped entirely - '
                           'no harvest data on file'.format(field=field_name))
                continue
            season_ranges = {}  # year -> (season_from, season_to, planting_logged, crop)
            for year, harvest_date in harvest_years.items():
                season_ranges[year] = self._estimate_season_date_range(field_name, harvest_date)
            fetch_from = min(r[0] for r in season_ranges.values())
            fetch_to = max(r[1] for r in season_ranges.values())
            full_weather, warning = self._load_weather(field_name, fetch_from, fetch_to)
            if not full_weather:
                # The bare bucket this used to be ('no weather data
                # available', no detail) made a live Open-Meteo failure
                # indistinguishable from a genuine data gap - a field the
                # Data inventory tab shows nothing missing for could still
                # never appear here, with no way to tell why (see
                # handle_weather.py's docstring: the stored/"Load weather"
                # table that tab checks is a separate free feature this
                # never reads - this always re-fetches live). Surfacing
                # the actual reason (a rate limit, an unreachable API, a
                # field with no resolvable location, ...) makes that
                # diagnosable instead of a silent dead end.
                reason = self.tr('no weather data available ({reason})').format(
                    reason=warning or self.tr('unknown reason'))
                skip_reasons[reason] += len(season_ranges)
                gdf_log.log('[Teach your model] {field}: skipped years {years} - '
                           '{reason}'.format(field=field_name,
                                             years=sorted(season_ranges), reason=reason))
                continue
            spacing_mm = self._load_spacing(field_name)
            for year, (season_from, season_to, planting_logged, crop) in season_ranges.items():
                if task is not None and task.isCanceled():
                    return examples, skip_reasons
                if not crop:
                    skip_reasons[self.tr('no crop/planting record found for that year')] += 1
                    gdf_log.log('[Teach your model] {field} {year}: skipped - no crop/'
                               'planting record found for that year'.format(
                                   field=field_name, year=year))
                    continue
                if (planting_logged and not allow_multiyear_crops
                        and int(season_from[:4]) != year):
                    skip_reasons[self.tr(
                        "the planting record on file is from a different year "
                        "than the harvest (enable \"Allow multi-year crops\" to "
                        "include it)")] += 1
                    gdf_log.log('[Teach your model] {field} {year}: skipped - the '
                               'planting record on file ({planted}) is from a '
                               'different year than the harvest'.format(
                                   field=field_name, year=year, planted=season_from))
                    continue
                season_weather = [w for w in full_weather if season_from <= w.date <= season_to]
                if not season_weather:
                    skip_reasons[self.tr('no weather data covering that season')] += 1
                    gdf_log.log('[Teach your model] {field} {year}: skipped - no '
                               'weather data covering that season ({season_from} to '
                               '{season_to})'.format(field=field_name, year=year,
                                                     season_from=season_from, season_to=season_to))
                    continue
                clay_pct, organic_matter_pct = self._load_soil(field_name, season_to)
                events = self._load_events(field_name, season_from, season_to)
                events.sort(key=lambda e: e.date)
                irrigation_by_date = self._load_irrigation(field_name, season_from, season_to)
                fertilizer_kg_n_by_date = self._build_fertilizer_kg_n_by_date(events)
                fertilizer_kg_k_by_date = self._build_fertilizer_kg_k_by_date(events)
                # Resolved on/before season_to, same reference date crop
                # itself was resolved against (see _estimate_season_date_
                # range) - a variety can genuinely change potential yield
                # enough that fitting/predicting against crop-level
                # settings alone hides real, learnable per-variety signal.
                # More than one variety in the same planting event (see
                # _load_variety_breakdown) becomes one candidate per
                # variety below, each matched against only the actual
                # yield from its own part of the field - a single
                # blended field-wide average would compare each variety's
                # prediction against a number that isn't really its own.
                winning_date, variety_table, variety_col, varieties = (
                    self._load_variety_breakdown(field_name, season_to))
                if len(varieties) > 1:
                    actual_by_variety = self._load_actual_yield_by_variety_t_ha(
                        field_name, variety_table, winning_date, variety_col, year)
                    variety_candidates = [
                        (v, actual_by_variety.get(v)) for v, _count in varieties]
                else:
                    single_variety = varieties[0][0] if varieties else None
                    variety_candidates = [(single_variety, self._load_actual_yield_t_ha(
                        field_name, season_from, season_to))]
                for variety, actual_yield in variety_candidates:
                    if task is not None and task.isCanceled():
                        return examples, skip_reasons
                    if actual_yield is None:
                        skip_reasons[self.tr('no usable harvest yield for that year')] += 1
                        gdf_log.log('[Teach your model] {field} {year} ({variety}): '
                                   'skipped - no usable harvest yield for that '
                                   'year'.format(field=field_name, year=year,
                                                 variety=variety or 'no variety on file'))
                        continue
                    effective_model = crop_model_settings.effective_crop_model(
                        self.db, crop, variety=variety)
                    season = estimate_season(
                        season_weather, crop, clay_pct, organic_matter_pct, irrigation_by_date,
                        fertilizer_kg_n_by_date=fertilizer_kg_n_by_date,
                        fertilizer_kg_k_by_date=fertilizer_kg_k_by_date,
                        crop_model=effective_model, spacing_mm=spacing_mm,
                        planting_date=season_from if planting_logged else None)
                    if season.estimated_yield_t_ha is None:
                        skip_reasons[self.tr('the model could not produce a yield estimate')] += 1
                        gdf_log.log('[Teach your model] {field} {year} ({variety}): '
                                   'skipped - the model could not produce a yield '
                                   'estimate'.format(field=field_name, year=year,
                                                     variety=variety or 'no variety on file'))
                        continue
                    gdf_log.log('[Teach your model] {field} {year} ({variety}): included '
                               '(predicted {predicted:.1f} t/ha, actual {actual:.1f} '
                               't/ha)'.format(field=field_name, year=year,
                                             variety=variety or 'no variety on file',
                                             predicted=season.estimated_yield_t_ha,
                                             actual=actual_yield))
                    examples.append(TrainingExample(
                        field_name=field_name, year=year, crop=crop,
                        season_from=season_from, season_to=season_to,
                        planting_date_logged=planting_logged, weather=season_weather,
                        clay=clay_pct, organic_matter=organic_matter_pct,
                        irrigation_by_date=irrigation_by_date,
                        fertilizer_kg_n_by_date=fertilizer_kg_n_by_date,
                        fertilizer_kg_k_by_date=fertilizer_kg_k_by_date,
                        spacing_mm=spacing_mm, predicted_yield_t_ha=season.estimated_yield_t_ha,
                        actual_yield_t_ha=actual_yield, variety=variety,
                        limiting_factor=season.limiting_factor))
        if task is not None:
            task.setProgress(100)
        return examples, skip_reasons

    def run_teach_scan(self):
        """"Scan farm" - gathers every field's harvest years into training
        examples (see :meth:`_compute_teach_scan`/:class:`TrainingExample`)
        in the background, so the UI doesn't freeze during what can be a
        genuinely slow farm-wide scan (one Open-Meteo fetch per field, plus
        per-year event/soil/irrigation queries). Shares
        :attr:`_running_task`/:meth:`is_licensed` with "Run simulation" -
        see :class:`_RunTeachScanTask`'s docstring for why."""
        if not self.is_licensed():
            report_warning(self.tr(
                'The crop simulation is a Pro feature. Please activate a '
                'license key above first.'))
            return
        if self._running_task is not None:
            report_warning(self.tr(
                'A simulation is already running - please wait for it to finish.'))
            return
        # Read on the main thread here, not inside _compute_teach_scan
        # itself - that runs on the task's worker thread, where touching
        # self.page is unsafe (see that method's own docstring).
        allow_multiyear_crops = self.page.CBAllowMultiyearCrops.isChecked()
        task = _RunTeachScanTask(
            self.tr('Teach your model - scanning farm'), self, allow_multiyear_crops)
        self._running_task = task
        self.page.PBScanFarm.setEnabled(False)
        self.page.LTeachStatus.setText(self.tr('Scanning farm…'))
        if getattr(self.parent, 'test_mode', False):
            success = task.run()
            task.finished(success)
        else:
            QgsApplication.taskManager().addTask(task)

    def _on_teach_scan_finished(self, task, success):
        """QgsTask.finished()'s callback - always runs on the main thread
        (see :class:`_RunSimulationTask`'s docstring) - safe to touch
        self.page again here."""
        self._running_task = None
        self.page.PBScanFarm.setEnabled(True)
        if not success:
            if task.error is not None:
                report_error(self.tr('The scan failed: {error}').format(error=str(task.error)))
            elif not task.isCanceled():
                report_error(self.tr('The scan failed for an unknown reason.'))
            return
        if task.result is not None:
            examples, skip_reasons = task.result
            self._apply_teach_scan_result(examples, skip_reasons)

    def _apply_teach_scan_result(self, examples, skip_reasons=None, checked_ids=None):
        """Populates TWTeachExamples with one row per
        :class:`TrainingExample`, each pre-checked - a real checkbox
        widget per row (not a checkable QTableWidgetItem), matching the
        rest of this codebase's own checkbox-in-a-cell convention (see
        support_scripts/qt_data.py's _item_flag users elsewhere) closely
        enough while keeping the checkbox trivially readable back out via
        :meth:`_teach_checked_examples`. ``skip_reasons`` (see
        :meth:`_compute_teach_scan`) drives the status text's breakdown of
        what was skipped and why, so "found 0" doesn't read the same
        whether nothing was logged at all or every field/year individually
        failed a different, fixable check - optional (default: none to
        report) since callers that build examples directly, bypassing an
        actual scan, have no skip reasons to give. ``checked_ids`` (a set
        of ``id(example)`` values) is :meth:`_sort_teach_examples`'s own
        way of re-populating this same table in a new order without
        resetting every row back to checked - every other caller wants
        the normal "everything checked to start" behaviour, so it's
        ``None`` (meaning "check every row") everywhere else."""
        self._teach_examples = examples
        self._teach_skip_reasons = skip_reasons
        table = self.page.TWTeachExamples
        table.setRowCount(len(examples))
        for row, ex in enumerate(examples):
            checkbox = QCheckBox()
            checkbox.setChecked(True if checked_ids is None else id(ex) in checked_ids)
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.addWidget(checkbox)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            table.setCellWidget(row, 0, cell)
            table.setItem(row, 1, QTableWidgetItem(ex.field_name))
            table.setItem(row, 2, QTableWidgetItem(str(ex.year)))
            table.setItem(row, 3, QTableWidgetItem(ex.crop))
            table.setItem(row, 4, QTableWidgetItem(ex.variety or self.tr('(none on file)')))
            table.setItem(row, 5, QTableWidgetItem('{:.1f}'.format(ex.predicted_yield_t_ha)))
            table.setItem(row, 6, QTableWidgetItem('{:.1f}'.format(ex.actual_yield_t_ha)))
            diff_pct = (100.0 * (ex.predicted_yield_t_ha - ex.actual_yield_t_ha)
                       / ex.actual_yield_t_ha if ex.actual_yield_t_ha else 0.0)
            table.setItem(row, 7, QTableWidgetItem('{:+.0f}%'.format(diff_pct)))
            table.setItem(row, 8, QTableWidgetItem(
                ex.limiting_factor or self.tr('(unknown)')))
            planting_label = (ex.season_from if ex.planting_date_logged
                              else self.tr('{} (estimated)').format(ex.season_from))
            table.setItem(row, 9, QTableWidgetItem(planting_label))
        table.resizeColumnsToContents()
        # "Ready to train on" - not just "has harvest data", since that's
        # only the first of several things a field/year needs (a known
        # crop and weather too) - see _compute_teach_scan. The old wording
        # here said "found N with harvest data on file", which read as
        # self-contradictory once the skip breakdown below started showing
        # that most skipped field/years *did* have harvest data and failed
        # a later check instead.
        status = self.tr(
            '{n} field/year combination(s) ready to train on (harvest '
            'data, a known crop, and weather all on file).'
        ).format(n=len(examples))
        if skip_reasons:
            skipped_total = sum(skip_reasons.values())
            breakdown = ', '.join(
                self.tr('{count} with {reason}').format(count=count, reason=reason)
                for reason, count in skip_reasons.most_common())
            status += ' ' + self.tr(
                '{n} other field/year combination(s) not ready yet: {breakdown}.'
            ).format(n=skipped_total, breakdown=breakdown)
        self.page.LTeachStatus.setText(status)

    _TEACH_SORT_KEYS = {
        1: lambda ex: (ex.field_name or '').lower(),
        2: lambda ex: ex.year,
        3: lambda ex: (ex.crop or '').lower(),
        4: lambda ex: (ex.variety or '').lower(),
        5: lambda ex: ex.predicted_yield_t_ha,
        6: lambda ex: ex.actual_yield_t_ha,
        7: lambda ex: (100.0 * (ex.predicted_yield_t_ha - ex.actual_yield_t_ha)
                      / ex.actual_yield_t_ha if ex.actual_yield_t_ha else 0.0),
        8: lambda ex: (ex.limiting_factor or '').lower(),
        9: lambda ex: ex.season_from,
    }

    def _sort_teach_examples(self, column):
        """TWTeachExamples' header-click sort - clicking the same column
        again reverses direction, matching the usual table-sort
        convention. Rebuilds the table from :attr:`_teach_examples` in
        the new order via :meth:`_apply_teach_scan_result` rather than
        QTableWidget's own ``setSortingEnabled``: that only reorders
        ``QTableWidgetItem``s, not a ``setCellWidget`` checkbox like this
        table's own (see that method's docstring for why a real widget
        is used there) - so built-in sorting would silently leave every
        checkbox in its original row while the data moved out from under
        it. Column 0 (the checkbox itself) has no sort key and is
        ignored. Each row's checked state survives the rebuild by object
        identity (``id(example)``), not position, so re-sorting never
        changes what's checked."""
        key_func = self._TEACH_SORT_KEYS.get(column)
        if key_func is None or not self._teach_examples:
            return
        table = self.page.TWTeachExamples
        checked_ids = set()
        for row, ex in enumerate(self._teach_examples):
            cell = table.cellWidget(row, 0)
            checkbox = cell.findChild(QCheckBox) if cell else None
            if checkbox is not None and checkbox.isChecked():
                checked_ids.add(id(ex))

        if self._teach_sort_column == column:
            self._teach_sort_reverse = not self._teach_sort_reverse
        else:
            self._teach_sort_column = column
            self._teach_sort_reverse = False
        sorted_examples = sorted(
            self._teach_examples, key=key_func, reverse=self._teach_sort_reverse)

        self._apply_teach_scan_result(
            sorted_examples, self._teach_skip_reasons, checked_ids=checked_ids)
        table.horizontalHeader().setSortIndicator(
            column, Qt.SortOrder.DescendingOrder if self._teach_sort_reverse
            else Qt.SortOrder.AscendingOrder)

    def _teach_checked_examples(self):
        """The :class:`TrainingExample` for every currently-checked row in
        TWTeachExamples, in row order."""
        table = self.page.TWTeachExamples
        checked = []
        for row in range(table.rowCount()):
            cell = table.cellWidget(row, 0)
            checkbox = cell.findChild(QCheckBox) if cell else None
            if checkbox is not None and checkbox.isChecked():
                checked.append(self._teach_examples[row])
        return checked

    def _train_selected(self):
        """"Train selected" - fits ``potential_yield_t_ha``, ``ky_nitrogen``
        and ``min_relative_yield_nitrogen`` (see :func:`_fit_crop_model`)
        per (crop, variety) - not just per crop - using only the checked
        rows' :class:`TrainingExample`\\ s: a variety can genuinely yield
        enough differently from its crop's default that lumping every
        variety's examples into one crop-wide fit would wash out real,
        learnable signal (see :meth:`_load_variety`). Examples with no
        variety on file group under that crop's own crop-level entry
        (variety ``''``), exactly like :func:`crop_model_settings.
        effective_crop_model` already treats "no variety" as. A group with
        fewer than two checked examples is reported as "not enough" rather
        than silently fit to a single point. Every result line names the
        exact field/year rows that went into it - see the "Teach the
        model" plan and :class:`TrainingExample`'s docstring for why: an
        anonymous "trained on N examples" count would break the link back
        to which data actually produced a given fit."""
        checked = self._teach_checked_examples()
        if not checked:
            report_warning(self.tr(
                'Check at least one field/year row above before training.'))
            return
        by_crop_variety = {}
        for ex in checked:
            key = ((ex.crop or '').strip().lower(), (ex.variety or '').strip().lower())
            by_crop_variety.setdefault(key, []).append(ex)
        self._teach_fits = {}
        blocks = []
        self.page.CBTeachSaveCrop.clear()
        for (crop_key, variety_key), examples in sorted(by_crop_variety.items()):
            crop_display = examples[0].crop
            variety_display = examples[0].variety if variety_key else None
            label = (self.tr('{crop} - variety: {variety}').format(
                        crop=crop_display, variety=variety_display)
                     if variety_display else crop_display)
            if len(examples) < 2:
                blocks.append(self.tr(
                    '{label}: not enough selected examples to fit (need at least '
                    '2, got {n}).').format(label=label, n=len(examples)))
                continue
            base_model = crop_model_settings.effective_crop_model(
                self.db, crop_display, variety=variety_display)
            fitted_model, sse_before, sse_after = _fit_crop_model(base_model, examples)
            self._teach_fits[(crop_key, variety_key)] = (
                crop_display, variety_display, fitted_model)
            self.page.CBTeachSaveCrop.addItem(label, (crop_key, variety_key))
            used = ', '.join('{} {}'.format(ex.field_name, ex.year) for ex in examples)
            blocks.append(self.tr(
                '{label} - fitted from {n} field/year(s): {used}\n'
                '  Potential yield: {py0:.1f} -> {py1:.1f} t/ha\n'
                '  Ky-N: {kyn0:.2f} -> {kyn1:.2f}\n'
                '  Min relative yield (N floor): {floor0:.2f} -> {floor1:.2f}\n'
                '  Fit error (sum of squared t/ha): {sse0:.1f} -> {sse1:.1f}'
            ).format(label=label, n=len(examples), used=used,
                    py0=base_model.potential_yield_t_ha, py1=fitted_model.potential_yield_t_ha,
                    kyn0=base_model.ky_nitrogen, kyn1=fitted_model.ky_nitrogen,
                    floor0=base_model.min_relative_yield_nitrogen,
                    floor1=fitted_model.min_relative_yield_nitrogen,
                    sse0=sse_before, sse1=sse_after))
        self.page.TETeachResults.setPlainText('\n\n'.join(blocks))
        self.page.LTeachSaveStatus.setText('')

    def _save_teach_fit(self):
        """"Save this fit" - persists the currently-selected (crop,
        variety) fit (see CBTeachSaveCrop) via the existing
        support_scripts/crop_model_settings.save_overrides mechanism - the
        same crop- or variety-level save path "Crop model settings"'s own
        "Save" already uses, so a fitted value round-trips through that
        dialog exactly like a manually-typed one would."""
        key = self.page.CBTeachSaveCrop.currentData()
        if key is None or key not in self._teach_fits:
            report_warning(self.tr('Train at least one crop first.'))
            return
        crop_display, variety_display, fitted_model = self._teach_fits[key]
        crop_model_settings.save_overrides(
            self.db, crop_display, variety_display or '',
            potential_yield_t_ha=fitted_model.potential_yield_t_ha,
            ky_nitrogen=fitted_model.ky_nitrogen,
            min_relative_yield_nitrogen=fitted_model.min_relative_yield_nitrogen)
        if variety_display:
            self.page.LTeachSaveStatus.setText(self.tr(
                'Saved - every field using "{crop}" variety "{variety}" will use '
                'these fitted settings from now on.'
            ).format(crop=crop_display, variety=variety_display))
            report_success(self.tr(
                'Fitted crop model settings saved for {crop} / {variety}.'
            ).format(crop=crop_display, variety=variety_display))
        else:
            self.page.LTeachSaveStatus.setText(self.tr(
                'Saved - every field using "{crop}" will use these fitted settings from '
                'now on.').format(crop=crop_display))
            report_success(self.tr(
                'Fitted crop model settings saved for {crop}.').format(crop=crop_display))
