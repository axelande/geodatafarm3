from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget)

__author__ = 'Axel Horteborn'

_CAPTION_STYLE = 'color: #666666; font-size: 11px;'


def _caption(text):
    """A small, always-visible explanation line under a settings row -
    not a hover tooltip, since those are easy to never discover. Tooltips
    are still set too, for anyone hovering the spin box itself."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(_CAPTION_STYLE)
    return label


class CropSettingsDialog(QDialog):
    """"Crop model settings" popup (Pro feature) - see
    database_scripts/crop_simulation.py for the controller that fills it in
    and reacts to its buttons, and support_scripts/crop_model_settings.py
    for where the persistent (per-crop, saved) values live.

    Built directly in Python/Qt rather than loaded from a .ui file (same
    reasoning as widgets/crop_simulation_page.py). Two kinds of input live
    here, kept visually separate since they behave differently:

    * "Crop model" - saved per crop name (see PBSaveSettings/PBReset),
      applies to every field that uses that crop from then on. Its
      "Advanced" toggle (collapsed by default, PBToggleAdvanced) reveals
      the curve-*shape* parameters (GDD base temperature, root depth
      ramp, Kc stage thresholds, nitrogen-uptake curve) behind a live
      chart, saved the same way as everything else in this section -
      unlike the fields above it, these are validated together on save
      (crop_models.validate_shape, via crop_model_settings.save_overrides)
      since an inconsistent combination breaks the curve outright.
    * "This run's field" - per-run what-if overrides (soil, spacing), never
      saved; pre-filled from the field's actual readings each time the
      dialog opens.

    Every field has a small grey caption directly under it (see
    :func:`_caption`) explaining what it means and how it actually feeds
    the yield estimate - not left to a hover tooltip alone, since a user
    otherwise has no way to know what e.g. "Heat-stress threshold" does
    without already knowing the model. The live results text (see
    "Estimate with these settings" below) is the other half of that
    visibility: its note explicitly narrates things like leaching/
    drainage losses, not just a final blended number - see
    support_scripts/season_water_model.py's module docstring. All of this
    makes for a lot of content, so everything except the Close button
    lives inside a scroll area rather than trying to fit on one screen.

    Both settings sections feed that live results text, recomputed from
    the last "Run simulation" click's cached weather/events (no new
    network call - see CropSimulation._recompute_settings_preview) every
    time a value here changes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Crop model settings'))
        self.resize(600, 780)
        outer_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        self.LCropName = QLabel(self.tr('Crop: -'))
        self.LCropName.setStyleSheet('font-size: 13px; font-weight: 700;')
        layout.addWidget(self.LCropName)

        variety_row = QHBoxLayout()
        variety_row.addWidget(QLabel(self.tr('Variety:')))
        self.CBVariety = QComboBox()
        self.CBVariety.setToolTip(self.tr(
            'Varieties found in the last run\'s imported planting data for '
            'this crop (see database_scripts/crop_simulation.py\'s per-cell '
            'crop/variety resolution). A variety\'s settings start from its '
            'crop\'s settings below and only need to override what\'s '
            'actually different for it.'))
        variety_row.addWidget(self.CBVariety)
        variety_row.addStretch(1)
        layout.addLayout(variety_row)
        layout.addWidget(_caption(self.tr(
            'Pick a variety to save settings just for it (e.g. a different '
            'potential yield for "Arsenal" than for "Solist"). Only cells '
            'whose imported planting data names that variety use it; '
            'everything else uses the crop-level settings below.')))

        # ---- Crop model (persisted per crop/variety) ------------------------
        model_frame = QFrame()
        model_frame.setFrameShape(QFrame.Shape.StyledPanel)
        model_box = QVBoxLayout(model_frame)
        self.LModelHeading = QLabel(self.tr(
            '<b>Crop model</b> - saved for this crop name, used for every '
            'field/run from now on:'))
        model_box.addWidget(self.LModelHeading)

        yield_row = QHBoxLayout()
        yield_row.addWidget(QLabel(self.tr('Potential yield (well-managed, no stress):')))
        self.SBPotentialYield = QDoubleSpinBox()
        self.SBPotentialYield.setRange(0.0, 200.0)
        self.SBPotentialYield.setDecimals(1)
        self.SBPotentialYield.setSuffix(' t/ha')
        yield_row.addWidget(self.SBPotentialYield)
        yield_row.addStretch(1)
        model_box.addLayout(yield_row)
        model_box.addWidget(_caption(self.tr(
            'The ceiling: what this crop would yield in a season with no '
            'water, nitrogen, heat or spacing stress at all. Every other '
            'setting below only ever takes a fraction *of* this number - '
            'raising it raises every estimate proportionally, it doesn\'t '
            'change how stressed the crop was.')))

        ky_water_row = QHBoxLayout()
        ky_water_row.addWidget(QLabel(self.tr('Water sensitivity (Ky), by growth stage:')))

        def _ky_stage_spinbox(tooltip):
            sb = QDoubleSpinBox()
            sb.setRange(0.0, 3.0)
            sb.setSingleStep(0.05)
            sb.setDecimals(2)
            sb.setToolTip(tooltip)
            return sb

        ky_water_row.addWidget(QLabel(self.tr('initial')))
        self.SBKyInitial = _ky_stage_spinbox(self.tr(
            'Ky for the initial (establishment) stage - a water shortfall '
            'here is usually the most forgivable of the four.'))
        ky_water_row.addWidget(self.SBKyInitial)
        ky_water_row.addWidget(QLabel(self.tr('development')))
        self.SBKyDevelopment = _ky_stage_spinbox(self.tr(
            'Ky for the development stage (ramping up to full canopy/Kc-mid).'))
        ky_water_row.addWidget(self.SBKyDevelopment)
        ky_water_row.addWidget(QLabel(self.tr('mid-season')))
        self.SBKyMidSeason = _ky_stage_spinbox(self.tr(
            'Ky for the mid-season stage (flowering/tuber initiation and '
            'bulking for potato) - usually by far the most sensitive of '
            'the four; a shortfall here costs the most yield.'))
        ky_water_row.addWidget(self.SBKyMidSeason)
        ky_water_row.addWidget(QLabel(self.tr('late')))
        self.SBKyLateSeason = _ky_stage_spinbox(self.tr(
            'Ky for the late-season (ripening) stage - usually forgivable, '
            'similar to the initial stage.'))
        ky_water_row.addWidget(self.SBKyLateSeason)
        ky_water_row.addStretch(1)
        model_box.addLayout(ky_water_row)
        model_box.addWidget(_caption(self.tr(
            'Ky, the FAO-33 yield-response factor - but one value per '
            'growth stage (see the four "Stage ends at" GDD values in '
            '"Advanced" below for where each stage actually falls this '
            'run) rather than a single seasonal figure, since a water '
            'shortfall during flowering/tuber initiation (mid-season) '
            'costs far more yield than the same shortfall during '
            'establishment or ripening. Each stage\'s relative yield loss '
            '= its own Ky x (fraction of that stage\'s potential '
            'evapotranspiration the crop missed out on); the four stages '
            'are then combined by multiplying their relative yields '
            'together (FAO-33\'s own multi-period model), not averaged.')))

        ky_n_row = QHBoxLayout()
        ky_n_row.addWidget(QLabel(self.tr('Nitrogen sensitivity (Ky-N):')))
        self.SBKyNitrogen = QDoubleSpinBox()
        self.SBKyNitrogen.setRange(0.0, 3.0)
        self.SBKyNitrogen.setSingleStep(0.05)
        self.SBKyNitrogen.setDecimals(2)
        self.SBKyNitrogen.setToolTip(self.tr(
            'Same idea as water sensitivity, applied to relative nitrogen '
            'uptake deficit instead. Higher = more sensitive to under-'
            'fertilizing.'))
        ky_n_row.addWidget(self.SBKyNitrogen)
        ky_n_row.addWidget(QLabel(self.tr('Minimum yield from soil nitrogen:')))
        self.SBMinYieldNitrogen = QDoubleSpinBox()
        self.SBMinYieldNitrogen.setRange(0.0, 1.0)
        self.SBMinYieldNitrogen.setSingleStep(0.05)
        self.SBMinYieldNitrogen.setDecimals(2)
        self.SBMinYieldNitrogen.setToolTip(self.tr(
            'A floor on the nitrogen factor above, so a total logged '
            'deficit (nothing applied, or nothing on record) never drops '
            'the estimate to exactly zero - a real zero-fertilizer plot '
            'still yields something from soil-supplied nitrogen. 0.3 '
            '(the default) means at least 30% of potential yield from '
            'nitrogen\'s side, however severe the logged deficit.'))
        ky_n_row.addWidget(self.SBMinYieldNitrogen)
        ky_n_row.addStretch(1)
        model_box.addLayout(ky_n_row)
        model_box.addWidget(_caption(self.tr(
            'Same idea, for nitrogen: relative yield loss = Ky-N x '
            '(fraction of season nitrogen demand, below, that the crop '
            'couldn\'t take up - whether because too little was applied, '
            'or because it leached away before the crop could use it, see '
            'the live results below) - but never below "Minimum yield from '
            'soil nitrogen", since even an unfertilized crop draws some '
            'nitrogen from the soil itself.')))

        n_demand_row = QHBoxLayout()
        n_demand_row.addWidget(QLabel(self.tr('Season nitrogen demand:')))
        self.SBNDemand = QDoubleSpinBox()
        self.SBNDemand.setRange(0.0, 500.0)
        self.SBNDemand.setDecimals(0)
        self.SBNDemand.setSuffix(' kg N/ha')
        n_demand_row.addWidget(self.SBNDemand)
        n_demand_row.addStretch(1)
        model_box.addLayout(n_demand_row)
        model_box.addWidget(_caption(self.tr(
            'Total nitrogen this crop needs across the whole season to hit '
            'its potential yield - the denominator Ky-N\'s deficit is '
            'measured against. Uptake follows a day-by-day curve (slow '
            'early, fastest mid-season), not a flat rate - see "Nitrogen '
            'timing and leaching" further down.')))

        ky_k_row = QHBoxLayout()
        ky_k_row.addWidget(QLabel(self.tr('Potassium sensitivity (Ky-K):')))
        self.SBKyPotassium = QDoubleSpinBox()
        self.SBKyPotassium.setRange(0.0, 3.0)
        self.SBKyPotassium.setSingleStep(0.05)
        self.SBKyPotassium.setDecimals(2)
        self.SBKyPotassium.setToolTip(self.tr(
            'Same idea as nitrogen sensitivity, applied to relative '
            'potassium uptake deficit instead. Higher = more sensitive to '
            'under-applying potassium.'))
        ky_k_row.addWidget(self.SBKyPotassium)
        ky_k_row.addWidget(QLabel(self.tr('Minimum yield from soil potassium:')))
        self.SBMinYieldPotassium = QDoubleSpinBox()
        self.SBMinYieldPotassium.setRange(0.0, 1.0)
        self.SBMinYieldPotassium.setSingleStep(0.05)
        self.SBMinYieldPotassium.setDecimals(2)
        self.SBMinYieldPotassium.setToolTip(self.tr(
            'Same idea as "Minimum yield from soil nitrogen" above, for '
            'potassium: a floor so a total logged deficit (nothing applied, '
            'or nothing on record) never drops the estimate to exactly '
            'zero - a real zero-potassium plot still yields something from '
            'soil-supplied potassium. 0.3 (the default) means at least 30% '
            'of potential yield from potassium\'s side, however severe the '
            'logged deficit.'))
        ky_k_row.addWidget(self.SBMinYieldPotassium)
        ky_k_row.addStretch(1)
        model_box.addLayout(ky_k_row)
        model_box.addWidget(_caption(self.tr(
            'Same idea as nitrogen: relative yield loss = Ky-K x (fraction '
            'of season potassium demand, below, that the crop couldn\'t '
            'take up) - but never below "Minimum yield from soil '
            'potassium", since even an unfertilized crop draws some '
            'potassium from the soil itself. Potassium gets the same '
            'day-by-day pool/leaching treatment as nitrogen (see '
            '"Potassium (K) uptake curve" in "Advanced" below) - unlike '
            'phosphorus/magnesium further down, which are only ever '
            'checked as a season total. Potassium genuinely leaches on '
            'light/sandy, low-clay soils the way nitrate does; phosphorus '
            'and magnesium mostly stay put in the soil once applied, so a '
            'day-by-day balance wouldn\'t mean '
            'much for them.')))

        k_demand_row = QHBoxLayout()
        k_demand_row.addWidget(QLabel(self.tr('Season potassium demand:')))
        self.SBKDemand = QDoubleSpinBox()
        self.SBKDemand.setRange(0.0, 500.0)
        self.SBKDemand.setDecimals(0)
        self.SBKDemand.setSuffix(' kg K/ha')
        k_demand_row.addWidget(self.SBKDemand)
        k_demand_row.addStretch(1)
        model_box.addLayout(k_demand_row)
        model_box.addWidget(_caption(self.tr(
            'Total potassium this crop needs across the whole season - the '
            'denominator Ky-K\'s deficit is measured against, same as '
            'nitrogen demand above.')))

        pmg_demand_row = QHBoxLayout()
        pmg_demand_row.addWidget(QLabel(self.tr('Season phosphorus demand:')))
        self.SBPDemand = QDoubleSpinBox()
        self.SBPDemand.setRange(0.0, 200.0)
        self.SBPDemand.setDecimals(0)
        self.SBPDemand.setSuffix(' kg P/ha')
        pmg_demand_row.addWidget(self.SBPDemand)
        pmg_demand_row.addWidget(QLabel(self.tr('Season magnesium demand:')))
        self.SBMgDemand = QDoubleSpinBox()
        self.SBMgDemand.setRange(0.0, 100.0)
        self.SBMgDemand.setDecimals(0)
        self.SBMgDemand.setSuffix(' kg Mg/ha')
        pmg_demand_row.addWidget(self.SBMgDemand)
        pmg_demand_row.addStretch(1)
        model_box.addLayout(pmg_demand_row)
        model_box.addWidget(_caption(self.tr(
            'Phosphorus and magnesium are only ever compared against what '
            'was applied as a season total (under/adequate/over, shown in '
            'the results below) - not tracked day by '
            'day, and they never cap the yield estimate the way water/'
            'nitrogen/potassium/heat do. Phosphorus barely moves once it\'s '
            'in the soil (it binds to soil particles rather than leaching '
            'with drainage water, and this model has no runoff/erosion '
            'component to lose it through instead); magnesium is held '
            'similarly, on soil cation exchange sites. Treat these two as a '
            'supply check, not a yield model.')))

        spacing_row = QHBoxLayout()
        spacing_row.addWidget(QLabel(self.tr('Reference spacing:')))
        self.SBReferenceSpacing = QDoubleSpinBox()
        self.SBReferenceSpacing.setRange(0.0, 1000.0)
        self.SBReferenceSpacing.setDecimals(0)
        self.SBReferenceSpacing.setSuffix(' mm')
        self.SBReferenceSpacing.setToolTip(self.tr(
            'The in-row planting spacing at which "Potential yield" above is '
            'actually achieved. 0 (the default) disables the effect entirely '
            '- there\'s no reliable universal default for this, it varies by '
            'end-use (e.g. seed vs. ware potatoes) far more than by crop.'))
        spacing_row.addWidget(self.SBReferenceSpacing)
        spacing_row.addWidget(QLabel(self.tr('Spacing sensitivity:')))
        self.SBSpacingSensitivity = QDoubleSpinBox()
        self.SBSpacingSensitivity.setRange(0.0, 5.0)
        self.SBSpacingSensitivity.setSingleStep(0.1)
        self.SBSpacingSensitivity.setDecimals(2)
        self.SBSpacingSensitivity.setToolTip(self.tr(
            'How sharply the yield ceiling falls off as actual spacing '
            'departs (either wider or narrower) from the reference above. '
            '0 also disables the effect.'))
        spacing_row.addWidget(self.SBSpacingSensitivity)
        spacing_row.addStretch(1)
        model_box.addLayout(spacing_row)
        model_box.addWidget(_caption(self.tr(
            'Unlike water/nitrogen, spacing doesn\'t run out over a season '
            '- it just scales "Potential yield" above up front (both too '
            'close and too wide a spacing than the reference lower it), '
            'before Ky/Ky-N/Ky-heat are applied to what\'s left. Reference '
            '0 (the default) or sensitivity 0 both fully disable this - '
            'there\'s no universal correct spacing to assume.')))

        heat_row = QHBoxLayout()
        heat_row.addWidget(QLabel(self.tr('Heat-stress threshold:')))
        self.SBHeatThreshold = QDoubleSpinBox()
        self.SBHeatThreshold.setRange(0.0, 50.0)
        self.SBHeatThreshold.setDecimals(1)
        self.SBHeatThreshold.setSuffix(' °C')
        self.SBHeatThreshold.setToolTip(self.tr(
            'A day\'s mean temperature above which it counts toward heat '
            'stress. Only has an effect once "Heat sensitivity" (Ky-heat) '
            'below is set above 0.'))
        heat_row.addWidget(self.SBHeatThreshold)
        heat_row.addWidget(QLabel(self.tr('Heat sensitivity (Ky-heat):')))
        self.SBKyHeat = QDoubleSpinBox()
        self.SBKyHeat.setRange(0.0, 5.0)
        self.SBKyHeat.setSingleStep(0.1)
        self.SBKyHeat.setDecimals(2)
        self.SBKyHeat.setToolTip(self.tr(
            'Same idea as water/nitrogen sensitivity, applied to the '
            'fraction of this season\'s days that exceeded the heat-stress '
            'threshold. 0 (the default for every crop) disables the effect '
            'entirely - of the three stress factors this is the least '
            'literature-standardised, so it stays off until you opt in.'))
        heat_row.addWidget(self.SBKyHeat)
        heat_row.addStretch(1)
        model_box.addLayout(heat_row)
        model_box.addWidget(_caption(self.tr(
            'Any day whose mean temperature goes above the threshold '
            'counts as one "heat-stress day". At season end, relative '
            'yield loss = Ky-heat x (heat-stress days / total days) - e.g. '
            '10 hot days out of a 40-day window (25%) at Ky-heat=1.0 costs '
            '25% of the yield left after water/nitrogen. Ky-heat=0 (every '
            'crop\'s default) means the threshold is ignored entirely - '
            'this is the least literature-grounded of the three factors, '
            'so it only counts once you deliberately turn it on.')))

        # ---- Advanced: curve shape (collapsed by default) -------------------
        self.PBToggleAdvanced = QPushButton(self.tr(
            '▸ Show advanced curve settings (water/nitrogen timing)'))
        self.PBToggleAdvanced.setCheckable(True)
        self.PBToggleAdvanced.toggled.connect(self._toggle_advanced_section)
        model_box.addWidget(self.PBToggleAdvanced)

        self.advanced_frame = QFrame()
        self.advanced_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.advanced_frame.setVisible(False)
        advanced_box = QVBoxLayout(self.advanced_frame)
        advanced_box.addWidget(_caption(self.tr(
            'These control *when* during the season water/nitrogen demand '
            'ramps up and down, not how much overall - saved the same way '
            'as the settings above, by crop or variety. Getting a '
            'combination wrong (e.g. stages out of order) breaks the curve '
            'outright, so it\'s validated on save, not just clamped to a '
            'range. See "About this simulation" → "Sources" for where '
            'these numbers come from.')))

        self.curve_chart_widget = QWidget()
        # Tall enough for the optional top calendar-date axis (see
        # database_scripts/crop_simulation.py's _render_curve_chart) on top
        # of the normal GDD axis/legend, not just the GDD-only case.
        self.curve_chart_widget.setMinimumHeight(260)
        self.curve_chart_layout = QVBoxLayout(self.curve_chart_widget)
        self.curve_chart_layout.setContentsMargins(0, 0, 0, 0)
        self.curve_canvas = None
        advanced_box.addWidget(self.curve_chart_widget)

        gdd_base_row = QHBoxLayout()
        gdd_base_row.addWidget(QLabel(
            self.tr('Growing-degree-day (GDD) base temperature:')))
        self.SBGddBase = QDoubleSpinBox()
        self.SBGddBase.setRange(-5.0, 20.0)
        self.SBGddBase.setDecimals(1)
        self.SBGddBase.setSuffix(' °C')
        self.SBGddBase.setToolTip(self.tr(
            'The daily mean temperature below which no development happens. '
            'Every GDD value on this page is accumulated above this base.'))
        gdd_base_row.addWidget(self.SBGddBase)
        gdd_base_row.addStretch(1)
        advanced_box.addLayout(gdd_base_row)
        advanced_box.addWidget(_caption(self.tr(
            'A growing degree day (GDD) is one degree of daily mean '
            'temperature above this base, accumulated day by day - the '
            'standard way to track crop development by accumulated heat '
            'instead of the calendar, since the same crop develops faster '
            'in a warm season than a cool one. A day only counts once its '
            'mean temperature exceeds this base. Lower the base and the '
            'season "runs" faster (in real days) for the same weather, '
            'since more GDD accrue per day; raise it and development '
            'slows. Every other GDD value on this page (root/Kc/nitrogen '
            'thresholds below) is measured on this same accumulating scale.')))

        root_row = QHBoxLayout()
        root_row.addWidget(QLabel(self.tr('Root depth: emergence')))
        self.SBRootDepthMin = QDoubleSpinBox()
        self.SBRootDepthMin.setRange(0.0, 300.0)
        self.SBRootDepthMin.setDecimals(0)
        self.SBRootDepthMin.setSuffix(' cm')
        root_row.addWidget(self.SBRootDepthMin)
        root_row.addWidget(QLabel(self.tr('→ full development')))
        self.SBRootDepthMax = QDoubleSpinBox()
        self.SBRootDepthMax.setRange(0.0, 300.0)
        self.SBRootDepthMax.setDecimals(0)
        self.SBRootDepthMax.setSuffix(' cm')
        root_row.addWidget(self.SBRootDepthMax)
        root_row.addWidget(QLabel(self.tr('by')))
        self.SBRootDepthFullGdd = QDoubleSpinBox()
        self.SBRootDepthFullGdd.setRange(1.0, 5000.0)
        self.SBRootDepthFullGdd.setDecimals(0)
        self.SBRootDepthFullGdd.setSuffix(' GDD')
        root_row.addWidget(self.SBRootDepthFullGdd)
        root_row.addStretch(1)
        advanced_box.addLayout(root_row)
        advanced_box.addWidget(_caption(self.tr(
            'Roots ramp linearly from the first depth to the second as GDD '
            'accumulates, reaching the second by the GDD value given - '
            'deeper roots mean more soil water the crop can actually reach '
            '(see "This run\'s field" below for the soil itself).')))

        kc_values_row = QHBoxLayout()
        kc_values_row.addWidget(QLabel(self.tr('Kc:  initial')))
        self.SBKcIni = QDoubleSpinBox()
        self.SBKcIni.setRange(0.0, 2.0)
        self.SBKcIni.setSingleStep(0.05)
        self.SBKcIni.setDecimals(2)
        kc_values_row.addWidget(self.SBKcIni)
        kc_values_row.addWidget(QLabel(self.tr('mid')))
        self.SBKcMid = QDoubleSpinBox()
        self.SBKcMid.setRange(0.0, 2.0)
        self.SBKcMid.setSingleStep(0.05)
        self.SBKcMid.setDecimals(2)
        kc_values_row.addWidget(self.SBKcMid)
        kc_values_row.addWidget(QLabel(self.tr('end')))
        self.SBKcEnd = QDoubleSpinBox()
        self.SBKcEnd.setRange(0.0, 2.0)
        self.SBKcEnd.setSingleStep(0.05)
        self.SBKcEnd.setDecimals(2)
        kc_values_row.addWidget(self.SBKcEnd)
        kc_values_row.addStretch(1)
        advanced_box.addLayout(kc_values_row)
        advanced_box.addWidget(_caption(self.tr(
            'The crop coefficient (Kc) multiplies reference evapotranspiration '
            '(ET0, from the weather forecast) to get this crop\'s actual '
            'water demand that day - low early (bare soil, small canopy), '
            'peaking mid-season (full canopy), lower late (senescence).')))

        kc_stage_row = QHBoxLayout()
        kc_stage_row.addWidget(QLabel(self.tr('Stage ends at:  initial')))
        self.SBKcIniEndGdd = QDoubleSpinBox()
        self.SBKcIniEndGdd.setRange(1.0, 5000.0)
        self.SBKcIniEndGdd.setDecimals(0)
        self.SBKcIniEndGdd.setSuffix(' GDD')
        kc_stage_row.addWidget(self.SBKcIniEndGdd)
        kc_stage_row.addWidget(QLabel(self.tr('development')))
        self.SBKcMidEndGdd = QDoubleSpinBox()
        self.SBKcMidEndGdd.setRange(1.0, 5000.0)
        self.SBKcMidEndGdd.setDecimals(0)
        self.SBKcMidEndGdd.setSuffix(' GDD')
        kc_stage_row.addWidget(self.SBKcMidEndGdd)
        kc_stage_row.addWidget(QLabel(self.tr('mid-season')))
        self.SBKcLateStartGdd = QDoubleSpinBox()
        self.SBKcLateStartGdd.setRange(1.0, 5000.0)
        self.SBKcLateStartGdd.setDecimals(0)
        self.SBKcLateStartGdd.setSuffix(' GDD')
        kc_stage_row.addWidget(self.SBKcLateStartGdd)
        kc_stage_row.addWidget(QLabel(self.tr('season')))
        self.SBSeasonEndGdd = QDoubleSpinBox()
        self.SBSeasonEndGdd.setRange(1.0, 5000.0)
        self.SBSeasonEndGdd.setDecimals(0)
        self.SBSeasonEndGdd.setSuffix(' GDD')
        kc_stage_row.addWidget(self.SBSeasonEndGdd)
        kc_stage_row.addStretch(1)
        advanced_box.addLayout(kc_stage_row)
        advanced_box.addWidget(_caption(self.tr(
            'Cumulative GDD marking the end of each of the four FAO-56 '
            'stages - must increase left to right (initial < development '
            '< mid-season < season end) or saving will be rejected. Kc '
            'ramps from Kc-ini to Kc-mid across "development", then holds '
            'flat at Kc-mid across "mid-season" (a genuine plateau, not '
            'just a peak) before ramping down to Kc-end across the late '
            'season. These four plus the three Kc values above draw the '
            'blue curve in the chart, and the same four stages are what '
            'the Water sensitivity (Ky) values above apply to.')))

        n_uptake_row = QHBoxLayout()
        n_uptake_row.addWidget(QLabel(self.tr('Nitrogen (N) uptake curve midpoint:')))
        self.SBNUptakeMidpoint = QDoubleSpinBox()
        self.SBNUptakeMidpoint.setRange(1.0, 5000.0)
        self.SBNUptakeMidpoint.setDecimals(0)
        self.SBNUptakeMidpoint.setSuffix(' GDD')
        n_uptake_row.addWidget(self.SBNUptakeMidpoint)
        n_uptake_row.addWidget(QLabel(self.tr('steepness:')))
        self.SBNUptakeSteepness = QDoubleSpinBox()
        self.SBNUptakeSteepness.setRange(0.001, 1.0)
        self.SBNUptakeSteepness.setSingleStep(0.001)
        self.SBNUptakeSteepness.setDecimals(4)
        n_uptake_row.addWidget(self.SBNUptakeSteepness)
        n_uptake_row.addStretch(1)
        advanced_box.addLayout(n_uptake_row)
        advanced_box.addWidget(_caption(self.tr(
            'Where the nitrogen-uptake S-curve (the green line in the '
            'chart) is centred, and how sharply it rises there - a lower '
            'midpoint means the crop wants most of its nitrogen earlier; a '
            'higher steepness means a shorter, more concentrated uptake '
            'window instead of a gradual ramp.')))

        k_uptake_row = QHBoxLayout()
        k_uptake_row.addWidget(QLabel(self.tr('Potassium (K) uptake curve midpoint:')))
        self.SBKUptakeMidpoint = QDoubleSpinBox()
        self.SBKUptakeMidpoint.setRange(1.0, 5000.0)
        self.SBKUptakeMidpoint.setDecimals(0)
        self.SBKUptakeMidpoint.setSuffix(' GDD')
        k_uptake_row.addWidget(self.SBKUptakeMidpoint)
        k_uptake_row.addWidget(QLabel(self.tr('steepness:')))
        self.SBKUptakeSteepness = QDoubleSpinBox()
        self.SBKUptakeSteepness.setRange(0.001, 1.0)
        self.SBKUptakeSteepness.setSingleStep(0.001)
        self.SBKUptakeSteepness.setDecimals(4)
        k_uptake_row.addWidget(self.SBKUptakeSteepness)
        k_uptake_row.addStretch(1)
        advanced_box.addLayout(k_uptake_row)
        advanced_box.addWidget(_caption(self.tr(
            'Same idea as the nitrogen curve above, for potassium (the '
            'purple line in the chart). Potato\'s default is centred later '
            'and rises more gently than nitrogen\'s, since tuber bulking '
            'keeps drawing potassium later into the season than nitrogen '
            'uptake, which peaks earlier around canopy development.')))

        model_box.addWidget(self.advanced_frame)

        model_btn_row = QHBoxLayout()
        self.PBSaveSettings = QPushButton(self.tr('Save for this crop'))
        model_btn_row.addWidget(self.PBSaveSettings)
        self.PBResetSettings = QPushButton(self.tr('Reset to default'))
        model_btn_row.addWidget(self.PBResetSettings)
        model_btn_row.addStretch(1)
        model_box.addLayout(model_btn_row)
        self.LSettingsStatus = QLabel('')
        self.LSettingsStatus.setWordWrap(True)
        model_box.addWidget(self.LSettingsStatus)
        layout.addWidget(model_frame)

        # ---- This run's soil/spacing (per-run what-if, not saved) -----------
        soil_frame = QFrame()
        soil_frame.setFrameShape(QFrame.Shape.StyledPanel)
        soil_box = QVBoxLayout(soil_frame)
        soil_box.addWidget(QLabel(self.tr(
            '<b>This run\'s field</b> - explore "what if the soil or '
            'planting spacing were different", without changing the '
            'field\'s real records:')))
        soil_row = QHBoxLayout()
        soil_row.addWidget(QLabel(self.tr('Clay:')))
        self.SBClay = QDoubleSpinBox()
        self.SBClay.setRange(0.0, 100.0)
        self.SBClay.setDecimals(1)
        self.SBClay.setSuffix(' %')
        soil_row.addWidget(self.SBClay)
        soil_row.addWidget(QLabel(self.tr('Organic matter:')))
        self.SBOrganicMatter = QDoubleSpinBox()
        self.SBOrganicMatter.setRange(0.0, 20.0)
        self.SBOrganicMatter.setDecimals(1)
        self.SBOrganicMatter.setSuffix(' %')
        soil_row.addWidget(self.SBOrganicMatter)
        soil_row.addWidget(QLabel(self.tr('Spacing:')))
        self.SBSpacing = QDoubleSpinBox()
        self.SBSpacing.setRange(0.0, 1000.0)
        self.SBSpacing.setDecimals(0)
        self.SBSpacing.setSuffix(' mm')
        self.SBSpacing.setToolTip(self.tr(
            'This run\'s actual in-row planting spacing, pre-filled from '
            'imported planting data where available. Only has an effect if '
            'the crop model above has a non-zero reference spacing set.'))
        soil_row.addWidget(self.SBSpacing)
        soil_row.addStretch(1)
        soil_box.addLayout(soil_row)
        soil_box.addWidget(_caption(self.tr(
            'Clay/organic matter set how much water the soil can hold '
            'between field capacity and wilting point (more clay/organic '
            'matter = a bigger buffer against a dry spell). Spacing only '
            'matters if "Reference spacing" above is non-zero.')))
        layout.addWidget(soil_frame)

        # ---- Live results ---------------------------------------------------
        layout.addWidget(QLabel(self.tr('<b>Estimate with these settings:</b>')))
        layout.addWidget(_caption(self.tr(
            'This text explicitly narrates what actually happened this '
            'season - including whether irrigation or nitrogen was wasted '
            'to drainage/leaching - not just the final yield number. See '
            '"Nitrogen timing and leaching" below for why clustering '
            'applications together (vs. spreading them out) changes this.')))
        self.TEResults = QTextEdit()
        self.TEResults.setReadOnly(True)
        self.TEResults.setMinimumHeight(180)
        layout.addWidget(self.TEResults)

        layout.addWidget(_caption(self.tr(
            'Nitrogen/potassium timing and leaching: applied nitrogen and '
            'potassium each sit in their own running pool until the '
            'crop\'s day-by-day uptake curve draws them down. Any day rain/'
            'irrigation exceeds the soil\'s water capacity, whatever is '
            'still waiting in either pool partly washes away with the '
            'drainage - already-taken-up nutrient is safe, unused nutrient '
            'is not. So the same total applied as one big dose ahead of '
            'heavy rain can leach away almost entirely, while splitting it '
            'into smaller, better-timed doses keeps most of it available - '
            'the estimate above reflects this difference, it isn\'t just a '
            'seasonal total. Phosphorus and magnesium aren\'t part of this '
            '- see "Season phosphorus/magnesium demand" above for why.')))

        scroll.setWidget(content)
        outer_layout.addWidget(scroll, 1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self.PBClose = QPushButton(self.tr('Close'))
        self.PBClose.clicked.connect(self.accept)
        close_row.addWidget(self.PBClose)
        outer_layout.addLayout(close_row)

    def _toggle_advanced_section(self, checked):
        self.advanced_frame.setVisible(checked)
        self.PBToggleAdvanced.setText(
            self.tr('▾ Hide advanced curve settings') if checked
            else self.tr('▸ Show advanced curve settings (water/nitrogen timing)'))
