from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QPushButton, QSizePolicy, QSlider, QSpinBox,
    QTableWidget, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget)

from .spinner_widget import SpinnerWidget

__author__ = 'Axel Horteborn'

ABOUT_TEXT = (
    "<b>How this simulation works</b><br>"
    "Every fertilizer application on the selected field is analysed with "
    "one of two tiers, chosen automatically per application:<br><br>"

    "<b>Advanced model - soil water &amp; nitrogen balance</b><br>"
    "Simulates the field's soil water and nitrogen day-by-day for about 30 "
    "days after the application, to estimate how much of the applied "
    "nitrogen was likely lost to leaching by rain. Loosely based on the "
    "NLEAP nitrate-leaching approach and FAO-56 crop-coefficient method.<br>"
    "<i>Needs:</i> a numeric N rate (kg N/ha) for the application, the "
    "field's clay% and organic matter% (from a soil sample), and daily "
    "rainfall + reference evapotranspiration (ET0) + mean temperature for "
    "the following weeks (fetched live from Open-Meteo).<br><br>"

    "<b>Simple model - rainfall risk index</b><br>"
    "A lighter fallback: flags an application low/moderate/high risk purely "
    "from how much rain fell in the 3 days afterwards, scaled by how "
    "leaching-prone that crop typically is.<br>"
    "<i>Used automatically</i> whenever the advanced model's inputs aren't "
    "available - no numeric rate found, or no soil sample on file.<br><br>"

    "<b>Field stress map (the date slider)</b><br>"
    "The field is split into a grid (2m x 2m cells, coarsened automatically "
    "only for a very large field - the same construction \"Create "
    "irrigation year\" already uses on the Irrigation card). Each cell's "
    "crop, variety and soil are read from whatever imported data already "
    "covers that spot - every imported planting/fertilizer/soil point "
    "already has a \"closest sample wins\" coverage polygon of its own "
    "(see import_data/handle_text_data.py's create_polygons), the same way "
    "database_scripts/mean_analyse.py already relates one schema's points "
    "to another's polygons - falling back to the field-wide manual record "
    "where nothing overlaps a cell, and to the field-wide crop where a "
    "cell has variety data but no crop of its own (see \"Varieties\" "
    "below). Each cell's water balance uses that cell's own saved crop/ "
    "variety settings, not just the built-in default. Irrigation is "
    "matched the same way, "
    "using each logged operation's own real flight-path geometry (see "
    "\"Irrigation and this simulation\" below), so only the cells actually "
    "passed over get watered. A day-by-day soil water balance then runs "
    "<i>per cell</i>, using the same weather as the rest of this page "
    "(weather doesn't vary meaningfully within one field, so it's fetched "
    "once). Dragging the slider recolours the map with each cell's water "
    "content that day - dark/red means drier and more stressed, "
    "blue/green means well-watered. There is no separate \"draw a zone\" "
    "step; this only reads data you've already imported or logged.<br><br>"

    "<b>Season yield estimate</b><br>"
    "A separate, season-length version of the same water balance (field-"
    "wide, using the field's overall crop/soil) estimates how many "
    "<i>additional</i> mm of irrigation would have kept the crop above a "
    "standard 50% management-allowed-depletion threshold - on top of any "
    "irrigation you've already logged - and applies FAO Irrigation &amp; "
    "Drainage Paper 33's yield-response-factor (Ky) method to turn "
    "evapotranspiration deficit into a rough yield estimate against a "
    "literature baseline for the crop - separately for each of the four "
    "FAO-56 growth stages (see \"Reading the curve chart against a "
    "calendar\" above), not one lump seasonal figure, since a shortfall "
    "during flowering/tuber initiation (mid-season) costs far more yield "
    "than the same shortfall during establishment or ripening; the four "
    "stages' relative yields are then multiplied together (FAO-33's own "
    "multi-period model), not averaged - see \"Sources\" below. In "
    "parallel, a nitrogen "
    "balance tracks a running available-N pool fed by every logged/planned "
    "fertilizer application and drawn down by the crop's day-by-day uptake "
    "curve - and drained by leaching whenever rain/irrigation exceeds the "
    "soil's capacity that day, see \"Timing matters\" below - giving a "
    "second, independent relative-yield estimate driven by nitrogen "
    "deficit instead of water. Potassium gets the identical day-by-day "
    "pool/uptake/leaching treatment, as its own third factor - see "
    "\"Potassium, phosphorus &amp; magnesium\" below for why potassium "
    "gets this and phosphorus/magnesium don't. A further, optional factor "
    "(see \"Heat stress\" below) works the same way for the fraction of "
    "days that exceeded a heat-stress threshold. All of these that are "
    "actually switched on are combined with <b>Liebig's law of the "
    "minimum</b> - "
    "final yield is capped by whichever was more limiting over the "
    "season, not an average of them - and the summary reports which one "
    "it was. Nitrogen/potassium only count in if you know a rate for each "
    "date; "
    "heat only counts in once you've set a non-zero sensitivity. The "
    "short line on the main page says which factor is limiting, and the "
    "full breakdown - irrigation logged/needed, nitrogen/potassium "
    "applied/needed, phosphorus/magnesium supply status, "
    "heat-stress days, and what the estimate would have been on water "
    "alone - lives in the \"⚙ Crop model settings\" popup, next to the "
    "settings that drive it. Separately (see \"Planting density\" below), "
    "actual planting spacing can scale the yield <i>ceiling</i> itself "
    "before any of this is applied to it - it isn't a limiting factor the "
    "way water/nitrogen/potassium/heat are, since density doesn't run out "
    "over a season.<br><br>"

    "<b>Potassium, phosphorus &amp; magnesium</b><br>"
    "Potassium (K) gets the exact same day-by-day treatment as nitrogen "
    "above - its own running pool, drawn down by a crop-specific uptake "
    "curve and leached by drainage the same way (see \"Timing matters\" "
    "below) - and takes part in the same Liebig's-law combination as "
    "water/nitrogen/heat, so a real potassium shortfall can cap the yield "
    "estimate just like a nitrogen shortfall can. Phosphorus (P) and "
    "magnesium (Mg), by contrast, are only ever compared as a season "
    "total: applied vs. this crop's season demand, reported as under/"
    "adequate/over in the settings popup - never tracked day by "
    "day, and never capping the yield estimate. This isn't an oversight: "
    "potassium genuinely leaches on light/sandy, low-clay soils much like "
    "nitrate does, while phosphorus binds tightly to soil particles (its "
    "main loss route is surface runoff/erosion, which this model doesn't "
    "simulate) and magnesium is held on soil cation exchange sites - "
    "neither moves through the soil profile the way nitrate or potassium "
    "can, so a day-by-day balance for them wouldn't reflect anything "
    "real. Add a P, K and/or Mg rate alongside nitrogen on a planned "
    "application (the \"Also (optional, same date/application)\" row "
    "below the main N field) to feed all of this - any subset can be "
    "left blank, and whichever ones you never give a rate for simply "
    "aren't modelled at all (not the same as \"modelled and found "
    "under\").<br><br>"

    "<b>Timing matters</b><br>"
    "The water/nitrogen/potassium balances above run day by day, not as "
    "one-time "
    "seasonal totals - so <i>when</i> you irrigate or fertilize genuinely "
    "changes the estimate, not just how much. Every day, the soil can only "
    "hold up to its field capacity; whatever rain/irrigation lands on top "
    "of that drains away unused. A single large dose landing on soil "
    "that's already wet wastes far more of it this way than the same "
    "total spread across drier days - the popup's live results will say "
    "how many mm drained away when this happens. Nitrogen and potassium "
    "each behave the "
    "same way, with one more twist: whatever is still sitting "
    "unapplied-for-uptake in either pool on a drainage day leaches away "
    "with "
    "it, proportional to how concentrated it is in the soil water right "
    "then (already-taken-up nutrient is safe). So the exact "
    "same total nitrogen or potassium applied as one lump dose ahead of a "
    "heavy rain "
    "can lose almost all of it to leaching, while splitting it into "
    "smaller doses timed around the rain keeps most of it available for "
    "the crop - the popup shows the kg/ha and % lost this way whenever "
    "it's non-trivial, for each of the two separately. This uses the same "
    "concentration x drainage "
    "mechanic as the per-application leaching-risk analysis above (which "
    "only ever looks at nitrogen), just "
    "run continuously across the whole season instead of a ~30-day window "
    "per application. Phosphorus and magnesium don't use this mechanic at "
    "all - see \"Potassium, phosphorus &amp; magnesium\" above.<br><br>"

    "<b>Planting date &amp; growth stop</b><br>"
    "Every water/nitrogen curve on this page is driven by accumulated "
    "growing-degree-days (GDD) since some day-zero - by default, whatever "
    "\"From\" date is picked above, <i>not</i> necessarily the crop's real "
    "planting date. If this field has a logged planting record on or after "
    "\"From\", its date is used as day-zero instead, and the crop label "
    "says so (\"planted ...\"); if the logged date is earlier than \"From\", "
    "the clock still can't start any earlier than \"From\" (the weather "
    "fetch isn't widened to cover it), and a warning says by how much this "
    "could throw off early-season values - move \"From\" back to fix it. "
    "Separately, \"Growth stopped early on\" lets a run say the crop "
    "stopped actively growing on a specific date instead of following its "
    "natural end-of-season decline - water/nitrogen demand drops to zero "
    "from that date on, the same as before planting. This matters for a "
    "crop like potato, where the foliage is deliberately killed (chemically "
    "or mechanically) well before the tubers are actually lifted, to let "
    "the skin set - the natural decline curve alone doesn't know about "
    "that deliberate cutoff, and the logged harvest date (the eventual "
    "lift/pick) is usually too late to stand in for it, which is why it "
    "isn't auto-filled.<br><br>"

    "<b>Crop duration (a known limitation)</b><br>"
    "There's no separate concept of \"how many calendar days this variety "
    "takes\" here - each crop has one built-in GDD curve (see "
    "support_scripts/crop_models.py's CROP_MODELS), so an early potato and "
    "a main-crop potato use the exact same season length by default. If "
    "your imported planting data tags cells with variety/cultivar names "
    "(see \"Varieties\" below), you can already give a faster-maturing one "
    "its own, shorter season in \"⚙ Crop model settings\" - open it with "
    "that variety picked, then lower all four \"Stage ends at\" GDD values "
    "in the \"Advanced\" section (proportionally, so initial/development/"
    "mid-season/season keep roughly the same shape) to match how much "
    "earlier it actually finishes. There's also no calendar-"
    "anchored/vernalization mechanic for a crop like winter wheat, planted "
    "in autumn and harvested the following summer largely regardless of "
    "the exact planting date - the GDD clock does naturally slow to a near-"
    "stop over a cold winter (wheat/barley/oats all use a 0°C GDD base), "
    "which gets the broad shape right, but winter and spring wheat "
    "currently share one crop-coefficient (Kc) curve, with no dormancy-"
    "specific behaviour of its own.<br><br>"

    "<b>Reading the curve chart against a calendar</b><br>"
    "The \"Advanced\" section's chart is plotted against cumulative GDD "
    "(what the model actually runs on) along the bottom - once you've run "
    "a simulation, a second axis along the top shows the calendar date "
    "(month-day) each GDD point actually fell on in that run's real "
    "weather. This is deliberately tied to that one run, not a fixed/"
    "universal calendar - the same GDD threshold lands on a different "
    "date depending on the year's actual temperatures, which is exactly "
    "why the model is driven by GDD rather than the calendar in the first "
    "place. No calendar axis shows until a run has weather to compute it "
    "from.<br><br>"

    "<b>Crop model settings popup</b><br>"
    "Opens with \"⚙ Crop model settings\" above. Its \"Crop model\" section "
    "- potential yield, water sensitivity (Ky), nitrogen sensitivity "
    "(Ky-N), season nitrogen demand, potassium sensitivity (Ky-K), season "
    "potassium/phosphorus/magnesium demand, reference spacing/sensitivity, "
    "and "
    "heat-stress threshold/sensitivity (Ky-heat) - is saved per crop name "
    "to this farm's own database once you press \"Save for this crop\", and from "
    "then on applies to every field/run using that crop (\"Reset to "
    "default\" clears it back to the plugin's built-in literature value). "
    "The Variety picker at the top lists whatever varieties the last run's "
    "imported planting data actually named (see \"Varieties\" below) - "
    "picking one lets you save settings just for it, starting from its "
    "crop's own settings and only overriding what's actually different "
    "(a variety with nothing of its own saved simply uses its crop's "
    "settings). Its \"This run's field\" section is a per-run what-if only "
    "- it never changes the field's real soil/planting records. Every "
    "value in the popup recomputes the estimate live, with no new network "
    "or database call, against the weather and events already fetched by "
    "the last \"Run simulation\" click - for a variety this previews \"if "
    "every cell used this variety's settings\", since the one season-"
    "estimate number stays field-wide/single-crop (see \"Varieties\" below "
    "for what actually is per-cell).<br><br>"

    "<b>Varieties</b><br>"
    "A cell's variety comes from whatever your imported planting data "
    "names for that spot - a 'variety' column is read completely "
    "separately from a 'crop' column, so a planting pass that only knows "
    "the product it planted (e.g. \"Arsenal\", not \"Potato - Arsenal\") "
    "never gets mistaken for the crop itself; the crop still comes from "
    "the field-wide crop record or the \"Use crop\" override above. Only "
    "the per-cell stress map (the date slider) is variety-aware - each "
    "cell's water balance uses its own variety's saved settings where one "
    "exists. The single season-estimate number stays field-wide, using "
    "just the crop's own settings, even on a field with several "
    "varieties zoned across it.<br><br>"

    "<b>Planting density</b><br>"
    "\"Reference spacing\" and \"Spacing sensitivity\" in the settings "
    "popup let actual in-row planting spacing scale the yield ceiling "
    "(\"Potential yield\") itself, before water/nitrogen stress is applied "
    "to it - both too close and too wide a spacing than the reference "
    "reduce it, roughly symmetrically. This is <i>off by default for "
    "every crop</i> (reference spacing 0 = disabled): unlike the other "
    "defaults here, there's no reliable universal literature spacing to "
    "start from - it varies by end-use (e.g. seed vs. ware potatoes) far "
    "more than by crop, so it only takes effect once you set a reference "
    "spacing and sensitivity yourself. The actual spacing used each run "
    "comes from your imported planting data field-wide (\"This run's "
    "field\" in the popup lets you override it as a what-if) - unlike "
    "crop/variety/soil, this isn't matched per cell, since it only feeds "
    "the single season-estimate number, not the stress map.<br><br>"

    "<b>Heat stress</b><br>"
    "\"Heat-stress threshold\" and \"Heat sensitivity\" (Ky-heat) in the "
    "settings popup add a third Liebig's-law factor alongside water and "
    "nitrogen: any day whose mean temperature exceeds the threshold counts "
    "as a heat-stress day, and the <i>fraction</i> of the season's days "
    "that were heat-stress days is scaled by Ky-heat the same way the "
    "water/nitrogen deficits are - whichever of the three ends up most "
    "limiting caps the yield. This is also <i>off by default for every "
    "crop</i> (Ky-heat 0 = disabled): of the three it's the least "
    "literature-standardised - a single daily-mean-temperature threshold "
    "is a real simplification of what's usually a day/night-temperature "
    "and growth-stage-dependent effect (e.g. potato tuber set) - so it "
    "only takes effect once you opt in. The per-cell stress map (the date "
    "slider) doesn't show heat, the same way it doesn't show nitrogen.<br><br>"

    "<b>Irrigation and this simulation</b><br>"
    "Dated irrigation only ever comes from \"Add from raindancer\" on the "
    "Irrigation card - there's no manual whole-field entry, since no real "
    "irrigation pass covers a whole field in one go. Each Raindancer "
    "operation logs its own real date <i>and</i> its own real flight-path "
    "geometry, so it only waters the cells it actually passed over. The "
    "older, undated whole-farm irrigation grid (\"Create irrigation year\") "
    "can't be placed on a calendar at all, so it's not used here - if "
    "that's the only irrigation data a field has, this page will tell you "
    "to re-run \"Add from raindancer\" for that period instead.<br><br>"

    "<b>What affects the numbers here</b><br>"
    "More/earlier fertilizer raises the season's nitrogen/potassium input "
    "(and, if "
    "poorly timed against rain, its leaching risk); when a numeric N or K "
    "rate is "
    "given it also feeds the matching balance above, so it can raise the "
    "estimated yield if that nutrient was the limiting factor. Logging a P "
    "or Mg rate instead only moves that nutrient's season supply-vs-demand "
    "status (under/adequate/over) in the settings popup - it "
    "never changes the estimated yield number itself. More logged "
    "irrigation reduces water stress and raises the estimated yield the "
    "same way if water was limiting. A hotter forecast/history only "
    "matters once you've set a Ky-heat above 0 for the crop, in which case "
    "more days over the threshold lower the estimate if heat is what's "
    "limiting - either way, the ceiling is the crop's potential yield "
    "(itself possibly reduced by planting density, see above). Try adding "
    "a planned application below and re-running to see its effect on both "
    "the timing risk and the season estimate.<br><br>"

    "<b>Limitations</b><br>"
    "This is a planning aid grounded in real agronomic mechanisms, not a "
    "certified nutrient balance, irrigation schedule or yield forecast - "
    "nitrogen mineralisation isn't modelled, and the yield estimate only "
    "accounts for water, nitrogen, potassium, heat (if configured) and "
    "planting "
    "density (if configured) stress (no pests, disease or frost; a "
    "variety's own settings only feed the per-cell stress map, not the "
    "single season-estimate number - see \"Varieties\" above). Phosphorus "
    "and magnesium are checked against season demand but never affect the "
    "yield number at all - see \"Potassium, phosphorus &amp; magnesium\" "
    "above. Baseline "
    "yields, Ky/Ky-N/Ky-K and leaching parameters are generic literature "
    "defaults, not calibrated to this field, though the yield-driving "
    "ones can be adjusted per crop (or variety) in \"⚙ Crop model "
    "settings\" - planting density and heat stress are the two exceptions "
    "left disabled by default (see \"Planting density\"/\"Heat stress\" "
    "above), since neither has a reliable universal literature default "
    "the way Ky/Ky-N/Ky-K do. Season potassium/phosphorus/magnesium demand "
    "figures themselves are wider-ranging, less precisely sourced planning "
    "estimates than the nitrogen/water figures - see \"Sources\" below. "
    "The field stress map (the date slider) still "
    "only shows water content, not nitrogen, potassium, heat or density. "
    "Treat every "
    "number here as a directional planning figure, not an exact one. See "
    "support_scripts/fertilizer_timing_model.py, "
    "support_scripts/season_water_model.py, "
    "support_scripts/crop_model_settings.py and "
    "support_scripts/field_grid.py in the plugin source for the full "
    "method and every threshold used. For the citations behind every "
    "number, see \"📚 Sources\" next to this button - the same list is "
    "also repeated at the end of this text.<br><br>"
)

# Kept as its own constant (and appended into ABOUT_TEXT below, not
# duplicated by hand) so "📚 Sources" can show just this - the citations
# are otherwise the very last section of a very long About text, easy to
# give up scrolling to before reaching them.
SOURCES_TEXT = (
    "<b>Sources</b><br>"
    "The water-demand curve (Kc) and its stage timing come from FAO "
    "Irrigation &amp; Drainage Paper 56 - Allen, Pereira, Raes &amp; Smith "
    "(1998), <i>Crop evapotranspiration - Guidelines for computing crop "
    "water requirements</i>: "
    "<a href=\"https://www.fao.org/4/x0490e/x0490e00.htm\">"
    "fao.org/4/x0490e/x0490e00.htm</a> (Table 12 for Kc ini/mid/end, Table "
    "11 for the stage-length proportions the growing-degree-day (GDD) "
    "thresholds are split with, chapter 6 for the four-stage curve shape "
    "itself - initial flat, development ramping up, a genuine mid-season "
    "<i>plateau</i> flat at Kc-mid rather than an instantaneous peak, then "
    "late-season ramping down - GDD is accumulated heat above a crop-"
    "specific base temperature, the standard way to track crop development "
    "by weather instead of the calendar). The yield-response factor (Ky) "
    "is FAO Irrigation &amp; "
    "Drainage Paper 33 - Doorenbos &amp; Kassam (1979), <i>Yield response "
    "to water</i> (Table 24 for the seasonal Ky figures each crop's four "
    "stage-specific values are calibrated from - exact table matches for "
    "potato and wheat, see support_scripts/crop_models.py's module "
    "docstring for which crops' figures are and aren't table citations); "
    "splitting Ky by growth stage and combining the stages' relative "
    "yields multiplicatively rather than by one seasonal figure follows "
    "Jensen, M.E. (1968), <i>Water consumption by agricultural plants</i> "
    "- the multi-period model FAO-33 itself documents alongside the "
    "simpler single-seasonal-value method this plugin used before. Growing-degree-day base temperatures: potato ~4.4°C "
    "(40°F), the common North American extension convention (reported "
    "range across studies is 2-5°C), e.g. "
    "<a href=\"https://www.potatogrower.com/2023/06/calculating-growing-degree-days\">"
    "potatogrower.com/2023/06/calculating-growing-degree-days</a>; "
    "wheat/barley/oats 0°C, the standard cereal GDD convention, e.g. NDSU "
    "NDAWN's "
    "<a href=\"https://ndawn.ndsu.nodak.edu/help-wheat-growing-degree-days.html\">"
    "wheat</a> and "
    "<a href=\"https://ndawn.ndsu.nodak.edu/help-barley-growing-degree-days.html\">"
    "barley</a> GDD guidance. The nitrogen-uptake curve's S-shape (slow at "
    "emergence, fastest during vegetative growth, plateauing near "
    "maturity) follows the pattern described in UC Davis/CDFA-FREP's "
    "nitrogen uptake and partitioning guidelines for "
    "<a href=\"https://www.cdfa.ca.gov/is/ffldrs/frep/FertilizationGuidelines/N_Potato.html\">"
    "potato</a> and "
    "<a href=\"https://www.cdfa.ca.gov/is/ffldrs/frep/FertilizationGuidelines/N_Wheat.html\">"
    "wheat</a> - its exact midpoint/steepness numbers are a reasonable "
    "placement consistent with that shape, not read off one paper's "
    "table. Season potassium/phosphorus/magnesium demand figures are PDA "
    "(Potash Development Association) and FAO nutrient offtake/removal "
    "figures, converted from the oxide forms those are conventionally "
    "published in to elemental kg/ha (K2O to K x0.83, P2O5 to P x0.436, "
    "MgO to Mg x0.603) - see "
    "<a href=\"https://www.pda.org.uk/potassium-uptake-requirements-of-some-crops/\">"
    "pda.org.uk/potassium-uptake-requirements-of-some-crops</a> and "
    "<a href=\"https://www.pda.org.uk/nutrient-considerations-for-potatoes/\">"
    "pda.org.uk/nutrient-considerations-for-potatoes</a>. Reported ranges "
    "are wide (e.g. potato K2O recommendations span 60-300 kg/ha "
    "depending on soil/yield level across sources), so these are "
    "reasonable mid-range planning figures, not a single precise table "
    "citation the way potato/wheat's Ky figures are - magnesium "
    "especially: PDA itself notes MgO offtake figures are \"based on very "
    "limited data, for guidance only\", so treat season magnesium demand "
    "as the roughest of the nutrient figures here. Potassium's uptake-"
    "curve timing (later and gentler than nitrogen's for potato, "
    "reflecting continued uptake through tuber bulking) is a shape-"
    "consistent estimate in the same spirit as the nitrogen curve above, "
    "not a table citation either. See "
    "support_scripts/crop_models.py's module docstring for the "
    "full source list, including exactly which field each source backs "
    "and which numbers are precisely sourced vs. shape-consistent "
    "estimates - that distinction is spelled out there deliberately, "
    "since not everything here carries the same level of evidence."
)

ABOUT_TEXT += SOURCES_TEXT


class CropSimulationPage(QWidget):
    """The "Crop simulation" main tab (Pro feature) - see
    database_scripts/crop_simulation.py for the controller that fills it in
    and reacts to its buttons.

    Built directly in Python/Qt and dropped into the dockwidget's
    ``layoutCropSimulation`` placeholder at runtime (see
    GeoDataFarm.set_buttons), the same pattern already used for
    widgets/add_data_form.py's AddDataForm - a full page is easier to keep
    correct built this way than by hand-editing
    GeoDataFarm_dockwidget_base.ui's already-large XML.

    Hosts the Pro license section directly (moved here from the "Farm & "
    Fields" page, since this is the feature it gates).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ---- License section ------------------------------------------------
        license_frame = QFrame()
        license_frame.setFrameShape(QFrame.Shape.StyledPanel)
        license_box = QVBoxLayout(license_frame)
        license_row = QHBoxLayout()
        self.LProHeading = QLabel(self.tr('🔓  GeoDataFarm Pro'))
        self.LProHeading.setStyleSheet('font-size: 13px; font-weight: 700;')
        license_row.addWidget(self.LProHeading)
        self.PBGetLicense = QPushButton(self.tr('🛒 Get a Pro license'))
        self.PBGetLicense.setToolTip(self.tr(
            'Opens the Pro license checkout in your browser. Purchasing is '
            "handled entirely by Lemon Squeezy - GeoDataFarm never sees your "
            "payment details. After checkout, your license key arrives by "
            "email within a few minutes - paste it below and press Activate."))
        license_row.addWidget(self.PBGetLicense)
        license_row.addStretch(1)
        license_box.addLayout(license_row)
        key_row = QHBoxLayout()
        self.LELicenseKey = QLineEdit()
        self.LELicenseKey.setPlaceholderText(self.tr('Paste your license key here'))
        key_row.addWidget(self.LELicenseKey)
        self.PBActivateLicense = QPushButton(self.tr('Activate'))
        key_row.addWidget(self.PBActivateLicense)
        license_box.addLayout(key_row)
        self.LLicenseStatus = QLabel(self.tr(
            'Not licensed. Click "Get a Pro license" to purchase one, then '
            'paste the key you receive by email above and press Activate to '
            'unlock the crop simulation.'))
        self.LLicenseStatus.setWordWrap(True)
        license_box.addWidget(self.LLicenseStatus)
        layout.addWidget(license_frame)

        # ---- Tabs: Simulation / Data inventory -------------------------------
        # License section stays outside the tabs, shared by both (one Pro
        # license gates this whole page, not each tab separately). See
        # database_scripts/crop_simulation.py's set_widget_connections/
        # is_licensed for how both tabs' actions check it.
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        sim_tab = QWidget()
        sim_layout = QVBoxLayout(sim_tab)
        self.tabs.addTab(sim_tab, self.tr('Simulation'))

        # ---- Field / date / run ----------------------------------------------
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel(self.tr('Field:')))
        self.CBField = QComboBox()
        top_row.addWidget(self.CBField)
        top_row.addWidget(QLabel(self.tr('From:')))
        self.DEFrom = QDateEdit()
        self.DEFrom.setCalendarPopup(True)
        self.DEFrom.setDate(QDate.currentDate())
        top_row.addWidget(self.DEFrom)
        top_row.addWidget(QLabel(self.tr('To:')))
        self.DETo = QDateEdit()
        self.DETo.setCalendarPopup(True)
        # A month out, not the same day as DEFrom - "From" >= "To" is
        # rejected by run_simulation() outright, so leaving both at
        # today's date would make the very first click fail validation.
        self.DETo.setDate(QDate.currentDate().addMonths(1))
        top_row.addWidget(self.DETo)
        self.PBRun = QPushButton(self.tr('Run simulation'))
        top_row.addWidget(self.PBRun)
        self.PBAbout = QPushButton(self.tr('ℹ️ About this simulation'))
        self.PBAbout.clicked.connect(self._show_about)
        top_row.addWidget(self.PBAbout)
        self.PBSources = QPushButton(self.tr('📚 Sources'))
        self.PBSources.setToolTip(self.tr(
            'Just the citations behind every number in this simulation - '
            'the same list is also at the end of "About this simulation", '
            'shown here on its own so you don\'t have to scroll to find it.'))
        self.PBSources.clicked.connect(self._show_sources)
        top_row.addWidget(self.PBSources)
        self.PBCropSettings = QPushButton(self.tr('⚙ Crop model settings'))
        top_row.addWidget(self.PBCropSettings)
        top_row.addStretch(1)
        sim_layout.addLayout(top_row)

        # ---- Crop override -----------------------------------------------
        crop_row = QHBoxLayout()
        self.LCrop = QLabel(self.tr('Crop: -'))
        crop_row.addWidget(self.LCrop)
        crop_row.addWidget(QLabel(self.tr('Use crop:')))
        self.CBCrop = QComboBox()
        # Not editable - lists the crops this model has a tuned profile
        # for, then whatever this farm has used before, then a trailing
        # "Other" entry that reveals CBCropOther below for typing any
        # other name (falls back to a generic default profile - see
        # support_scripts/crop_models.get_crop_model). An editable combo
        # box was tried here first and reverted - on top of losing the
        # dropdown arrow/list-only click behaviour, it made the crop
        # names and the farm's own logged ones visually indistinguishable
        # from each other.
        self.CBCrop.setToolTip(self.tr(
            'Overrides the field-wide crop used by the model - set this if '
            'no crop is logged for the field, or to try a different one. '
            'Cells with their own imported planting data still use that.'))
        crop_row.addWidget(self.CBCrop)
        self.CBCropOther = QLineEdit()
        self.CBCropOther.setPlaceholderText(self.tr('Crop name'))
        self.CBCropOther.setVisible(False)
        crop_row.addWidget(self.CBCropOther)
        crop_row.addStretch(1)
        sim_layout.addLayout(crop_row)

        # ---- Growth stopped early (optional, per-run) -----------------------
        stop_row = QHBoxLayout()
        self.CBGrowthStopEnabled = QCheckBox(self.tr('Growth stopped early on:'))
        self.CBGrowthStopEnabled.setToolTip(self.tr(
            'Optional, off by default. Without this, the model assumes the '
            'crop keeps growing until its natural end-of-season decline is '
            'reached. Check this to instead say it stopped actively using '
            'water/nitrogen on a specific date - e.g. potatoes are commonly '
            'haulm-killed (foliage desiccated, chemically or mechanically) '
            'weeks before they are actually lifted, to let the skin set; a '
            'cereal stops the moment it is combined. From this date '
            'onward, water/nitrogen demand is treated as zero, the same as '
            'before planting. Not auto-filled from a logged harvest date - '
            'for a crop like potato the true growth-stop date (haulm-kill) '
            'is usually well before the logged pick date, so guessing it '
            'from that would be misleading.'))
        stop_row.addWidget(self.CBGrowthStopEnabled)
        self.DEGrowthStop = QDateEdit()
        self.DEGrowthStop.setCalendarPopup(True)
        self.DEGrowthStop.setDate(QDate.currentDate())
        self.DEGrowthStop.setEnabled(False)
        self.CBGrowthStopEnabled.toggled.connect(self.DEGrowthStop.setEnabled)
        stop_row.addWidget(self.DEGrowthStop)
        stop_row.addStretch(1)
        sim_layout.addLayout(stop_row)

        # ---- Planned applications ------------------------------------------
        planned_row = QHBoxLayout()
        planned_row.addWidget(QLabel(
            self.tr('Add a planned application (this run only, never saved):')))
        planned_row.addWidget(QLabel(self.tr('Date:')))
        self.DEPlannedDate = QDateEdit()
        self.DEPlannedDate.setCalendarPopup(True)
        self.DEPlannedDate.setDate(QDate.currentDate())
        planned_row.addWidget(self.DEPlannedDate)
        planned_row.addWidget(QLabel(self.tr('N:')))
        self.LEPlannedRate = QLineEdit()
        self.LEPlannedRate.setPlaceholderText(self.tr('e.g. 150 kg N/ha'))
        planned_row.addWidget(self.LEPlannedRate)
        self.PBAddPlanned = QPushButton(self.tr('Add'))
        planned_row.addWidget(self.PBAddPlanned)
        self.PBRemovePlanned = QPushButton(self.tr('Remove selected'))
        planned_row.addWidget(self.PBRemovePlanned)
        sim_layout.addLayout(planned_row)

        # A single application (e.g. a compound NPK+Mg product) can carry
        # more than one nutrient at once - these three are independently
        # optional, added to the same event N above is (or left blank for
        # an N-only application, unchanged from before these existed).
        planned_row2 = QHBoxLayout()
        planned_row2.addWidget(QLabel(
            self.tr('Also (optional, same date/application):')))
        planned_row2.addWidget(QLabel(self.tr('P:')))
        self.LEPlannedRateP = QLineEdit()
        self.LEPlannedRateP.setPlaceholderText(self.tr('e.g. 30 kg P/ha'))
        planned_row2.addWidget(self.LEPlannedRateP)
        planned_row2.addWidget(QLabel(self.tr('K:')))
        self.LEPlannedRateK = QLineEdit()
        self.LEPlannedRateK.setPlaceholderText(self.tr('e.g. 200 kg K/ha'))
        planned_row2.addWidget(self.LEPlannedRateK)
        planned_row2.addWidget(QLabel(self.tr('Mg:')))
        self.LEPlannedRateMg = QLineEdit()
        self.LEPlannedRateMg.setPlaceholderText(self.tr('e.g. 15 kg Mg/ha'))
        planned_row2.addWidget(self.LEPlannedRateMg)
        planned_row2.addStretch(1)
        sim_layout.addLayout(planned_row2)

        self.LWPlannedEvents = QListWidget()
        self.LWPlannedEvents.setMaximumHeight(60)
        sim_layout.addWidget(self.LWPlannedEvents)

        # ---- Status / season summary ---------------------------------------
        self.LStatus = QLabel('')
        self.LStatus.setWordWrap(True)
        sim_layout.addWidget(self.LStatus)

        # Short one-line pointer only - the full breakdown (irrigation
        # logged, water/nitrogen deficits, limiting factor, ...) lives in
        # the "Crop model settings" popup instead, alongside the controls
        # that actually change those numbers - see
        # database_scripts/crop_simulation.py's open_crop_settings.
        self.LSeasonEstimate = QLabel('')
        self.LSeasonEstimate.setWordWrap(True)
        sim_layout.addWidget(self.LSeasonEstimate)

        # Real harvested yield for the run's field/date range, shown next to
        # the estimate above when a harvest import happens to overlap it -
        # see CropSimulation._render_actual_yield. Hidden otherwise (e.g. a
        # future/unharvested season), so it doesn't add an empty line.
        self.LActualYield = QLabel('')
        self.LActualYield.setWordWrap(True)
        self.LActualYield.hide()
        sim_layout.addWidget(self.LActualYield)

        # Which reading the heatmap below shows - also switches in a
        # field-wide rain + irrigation total for the run's date range when
        # that mode is picked (see
        # CropSimulation._render_rain_irrigation/_render_heatmap).
        rain_row = QHBoxLayout()
        rain_row.addWidget(QLabel(self.tr('Field map:')))
        self.CBMapMode = QComboBox()
        self.CBMapMode.addItem(self.tr('Water stress'), 'stress')
        self.CBMapMode.addItem(self.tr('Total rain + irrigation'), 'rain_irrigation')
        self.CBMapMode.addItem(self.tr('Predicted yield'), 'yield')
        rain_row.addWidget(self.CBMapMode)
        rain_row.addStretch(1)
        sim_layout.addLayout(rain_row)
        self.LRainIrrigation = QLabel('')
        self.LRainIrrigation.setWordWrap(True)
        self.LRainIrrigation.hide()
        sim_layout.addWidget(self.LRainIrrigation)

        self.LLegacyIrrigationWarning = QLabel('')
        self.LLegacyIrrigationWarning.setWordWrap(True)
        self.LLegacyIrrigationWarning.setStyleSheet('color: #a15c00;')
        sim_layout.addWidget(self.LLegacyIrrigationWarning)

        # ---- Date slider (stress map) --------------------------------------
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel(self.tr('Field stress on:')))
        self.SLDate = QSlider(Qt.Orientation.Horizontal)
        self.SLDate.setEnabled(False)
        slider_row.addWidget(self.SLDate, 1)
        self.LSliderDate = QLabel('-')
        self.LSliderDate.setMinimumWidth(90)
        slider_row.addWidget(self.LSliderDate)
        sim_layout.addLayout(slider_row)

        legend_row = QHBoxLayout()
        self.LMapLegend = QLabel()
        self.LMapLegend.setTextFormat(Qt.TextFormat.RichText)
        legend_row.addWidget(self.LMapLegend)
        # Literal self.tr(...) calls here (not a module-level table looked
        # up by key) so pylupdate can actually find and extract these four
        # labels - it only recognises a translatable string when it's a
        # string literal passed directly to tr(), not a runtime variable.
        self.LMapLegend.setText(self.tr('Timing-risk markers / stress map legend:'))
        sim_layout.addLayout(legend_row)

        chart_widget = QWidget()
        self.mplvl = QVBoxLayout(chart_widget)
        self.mplvl.setContentsMargins(0, 0, 0, 0)
        sim_layout.addWidget(chart_widget, 3)

        # Shown in mplvl (in place of the heatmap canvas - see
        # database_scripts/crop_simulation.py's _show_simulation_spinner)
        # while "Run simulation" is working in the background, so there's
        # something visibly alive in the exact spot the field will later
        # be drawn. Not added to the layout yet - CropSimulation adds/
        # removes it the same way it already juggles the canvas itself.
        self.spinner = SpinnerWidget()



        sim_layout.addWidget(QLabel(self.tr('Per-application detail (field-wide):')))
        self.TEDetails = QTextEdit()
        self.TEDetails.setReadOnly(True)
        sim_layout.addWidget(self.TEDetails, 2)

        # ---- Data inventory tab ----------------------------------------------
        # What does field X have on file for year Y, of the categories the
        # model actually consumes - and a way to fix a gap right from here.
        # See database_scripts/crop_simulation.py's _field_year_inventory/
        # _check_field_year_data. A separate field combo from the
        # Simulation tab's CBField above (not shared) - deliberately, to
        # avoid touching that tab's already-tested wiring.
        inventory_tab = QWidget()
        inventory_layout = QVBoxLayout(inventory_tab)
        self.tabs.addTab(inventory_tab, self.tr('Data inventory'))

        inventory_intro = QLabel(self.tr(
            'Pick a field and a year to see which of the data categories the '
            'crop model actually uses are on file for it, and fix any gaps '
            'without leaving this tab.'))
        inventory_intro.setWordWrap(True)
        inventory_layout.addWidget(inventory_intro)

        inv_row = QHBoxLayout()
        inv_row.addWidget(QLabel(self.tr('Field:')))
        self.CBInventoryField = QComboBox()
        inv_row.addWidget(self.CBInventoryField)
        inv_row.addWidget(QLabel(self.tr('Year:')))
        self.SBInventoryYear = QSpinBox()
        self.SBInventoryYear.setRange(2000, 2100)
        self.SBInventoryYear.setValue(QDate.currentDate().year())
        inv_row.addWidget(self.SBInventoryYear)
        self.PBCheckData = QPushButton(self.tr('Check data'))
        inv_row.addWidget(self.PBCheckData)
        inv_row.addStretch(1)
        inventory_layout.addLayout(inv_row)

        self.TWDataInventory = QTableWidget(0, 4)
        self.TWDataInventory.setHorizontalHeaderLabels(
            [self.tr('Category'), self.tr('Status'), self.tr('Records'), ''])
        self.TWDataInventory.horizontalHeader().setStretchLastSection(True)
        self.TWDataInventory.verticalHeader().setVisible(False)
        self.TWDataInventory.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        inventory_layout.addWidget(self.TWDataInventory)

        # ---- Teach your model tab ---------------------------------------------
        # A farm-wide checklist of every field/year with real harvest data
        # on file, predicted vs. actual side by side - check the rows you
        # trust and fit potential_yield_t_ha/ky_nitrogen/
        # min_relative_yield_nitrogen per crop against just those. See
        # database_scripts/crop_simulation.py's _compute_teach_scan/
        # _fit_crop_model/TrainingExample.
        teach_tab = QWidget()
        teach_layout = QVBoxLayout(teach_tab)
        self.tabs.addTab(teach_tab, self.tr('Teach your model'))

        teach_intro = QLabel(self.tr(
            'Scans every field for years with real harvest data on file, comparing '
            'the model\'s prediction (using today\'s settings) against what was '
            'actually harvested. Check the field/year rows you trust, then "Train '
            'selected" to fit potential yield, nitrogen sensitivity (Ky-N) and the '
            'nitrogen floor to just that data, grouped per crop.'))
        teach_intro.setWordWrap(True)
        teach_layout.addWidget(teach_intro)

        teach_scan_row = QHBoxLayout()
        self.PBScanFarm = QPushButton(self.tr('Scan farm'))
        teach_scan_row.addWidget(self.PBScanFarm)
        self.CBAllowMultiyearCrops = QCheckBox(self.tr('Allow multi-year crops'))
        self.CBAllowMultiyearCrops.setChecked(False)
        self.CBAllowMultiyearCrops.setToolTip(self.tr(
            'Off (default): a field/year is only included if its planting '
            'record is from the same calendar year as the harvest - most '
            'crops (potatoes included) are replanted every year, so a much '
            'older planting record being reused just means no fresher one '
            'was ever logged, not that the crop is genuinely still standing '
            'from back then. Turn this on only for crops that really can '
            'span several years between plantings (e.g. ley/grassland, '
            'asparagus) - otherwise those years are silently skipped.'))
        teach_scan_row.addWidget(self.CBAllowMultiyearCrops)
        teach_scan_row.addStretch(1)
        teach_layout.addLayout(teach_scan_row)

        self.LTeachStatus = QLabel('')
        self.LTeachStatus.setWordWrap(True)
        teach_layout.addWidget(self.LTeachStatus)

        self.TWTeachExamples = QTableWidget(0, 10)
        self.TWTeachExamples.setHorizontalHeaderLabels([
            '', self.tr('Field'), self.tr('Year'), self.tr('Crop'), self.tr('Variety'),
            self.tr('Predicted (t/ha)'), self.tr('Actual (t/ha)'), self.tr('Diff'),
            self.tr('Limiting factor'), self.tr('Planting date')])
        self.TWTeachExamples.verticalHeader().setVisible(False)
        self.TWTeachExamples.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # Click-to-sort is handled manually, not via setSortingEnabled -
        # see CropSimulation._sort_teach_examples's docstring for why
        # (a setCellWidget checkbox doesn't move with its row under Qt's
        # own sorting). This only shows the indicator arrow; the header's
        # sectionClicked signal (wired in set_widget_connections) does
        # the actual sorting.
        self.TWTeachExamples.horizontalHeader().setSortIndicatorShown(True)
        # Ignored (not the QTableWidget default of Expanding) so this
        # table's width - which can get wide once resizeColumnsToContents()
        # runs against a farm-wide scan with real data - doesn't set the
        # whole tab widget's (and so the whole dock panel's) minimum width;
        # QTabWidget's underlying QStackedWidget otherwise sizes itself to
        # the largest of *all* its pages, not just the visible one, so a
        # wide table here would widen the panel even while looking at the
        # Simulation tab. A horizontal scrollbar (the QTableWidget default)
        # keeps every column reachable within this tab regardless.
        self.TWTeachExamples.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        teach_layout.addWidget(self.TWTeachExamples, 2)

        self.PBTrainSelected = QPushButton(self.tr('Train selected'))
        teach_layout.addWidget(self.PBTrainSelected)

        self.TETeachResults = QTextEdit()
        self.TETeachResults.setReadOnly(True)
        teach_layout.addWidget(self.TETeachResults, 1)

        teach_save_row = QHBoxLayout()
        teach_save_row.addWidget(QLabel(self.tr('Save fitted settings for:')))
        self.CBTeachSaveCrop = QComboBox()
        teach_save_row.addWidget(self.CBTeachSaveCrop)
        self.PBTeachSaveCrop = QPushButton(self.tr('Save this fit'))
        teach_save_row.addWidget(self.PBTeachSaveCrop)
        teach_save_row.addStretch(1)
        teach_layout.addLayout(teach_save_row)

        self.LTeachSaveStatus = QLabel('')
        self.LTeachSaveStatus.setWordWrap(True)
        teach_layout.addWidget(self.LTeachSaveStatus)

    def _show_about(self):
        self._show_rich_text_box(self.tr('About this simulation'), ABOUT_TEXT)

    def _show_sources(self):
        self._show_rich_text_box(self.tr('Sources'), SOURCES_TEXT)

    def _show_rich_text_box(self, title, html):
        # A plain QDialog + QTextBrowser, not QMessageBox - QMessageBox is
        # built for short alerts: its size is effectively fixed (the user
        # can't drag it wider) and it has no scrolling of its own, both
        # fatal for content this long. QTextBrowser gives proper
        # scrolling, wrapping and (via setOpenExternalLinks) working
        # clickable links for free, and a plain QDialog is resizable by
        # default.
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(700, 600)
        dlg_layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(html)
        dlg_layout.addWidget(browser)
        close_button = QPushButton(self.tr('Close'))
        close_button.clicked.connect(dlg.accept)
        dlg_layout.addWidget(close_button)
        dlg.exec()
