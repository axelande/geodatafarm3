"""Pre-submission corrections (2026-10-04, evening review)."""
import os

PAPER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(PAPER, 'manuscript.md')
s = open(p, encoding='utf-8').read()
missing = []


def rep(old, new, count=1):
    global s
    if old not in s:
        missing.append(old[:90])
        return
    s = s.replace(old, new, count)


# 1. Section 4.2 contradiction
rep("The three parameters were identifiable in the post hoc treatment and not in the plugin's default treatment, and the difference is entirely about what an absent record is taken to mean.",
    "The post hoc treatment removed the parameter-bound solution produced by the plugin's default, but it did not make all three parameters identifiable: potential yield became relatively stable under resampling, whereas the two nitrogen parameters remained weakly identified. The difference between the two treatments is entirely about what an absent record is taken to mean.")
rep("Excluding the unlogged nutrient lets potential yield settle near 90 t/ha and lets the nitrogen factor and floor be fitted from the eight field-years with a rate.",
    "Excluding the unlogged nutrient lets potential yield settle near 90 t/ha and allows numerical estimates of the nitrogen factor and floor to be obtained from the eight field-years with a recorded rate, although those estimates remain weakly identified.")

# 2. threshold of five
rep("The plugin should act on this rather than report it: offer the nitrogen parameters for calibration only when, say, five or more field-years carry a complete rate and otherwise fit potential yield alone; store and update potential yield per variety, which the farm's own records determine better than any crop-level value, falling back to the crop value for a variety with fewer than two seasons; exclude an unlogged nutrient",
    "The plugin should act on this rather than report it. It should offer the nitrogen parameters for calibration only after a minimum evidence criterion has been met; that criterion should be established on multi-farm data, since the present case shows that eight field-years with recorded rates were insufficient to identify two nitrogen parameters, and until it has been validated the interface should report the number and range of complete-rate field-years and warn when parameter estimates are weakly supported. It should store variety-specific yield histories and, where repeated seasons are available, evaluate whether a variety-specific potential yield improves prediction over a same-variety empirical mean. It should exclude an unlogged nutrient")

# 3. conclusion 3 and 'halving'
rep("A FMIS should fit potential yield per variety from the farm's records and offer the nitrogen parameters for calibration only when enough complete rates exist.",
    "A FMIS should preserve variety-specific yield histories and should not assume a common yield level across varieties; whether those histories are best represented by a same-variety empirical mean or by a fitted variety-specific potential yield requires more repeated seasons per variety than were available here. The nitrogen parameters should be offered for calibration only once a validated evidence criterion is met.")
rep("calibration corrected the farm's yield level, halving the error of the literature defaults to 31 % of the mean yield,",
    "calibration corrected the farm's yield level, reducing the error of the literature defaults from 58 % to 31 % of the mean yield,")

# consistency: single farm
rep("### 2.5 Study farms and data", "### 2.5 Study farm and data")
rep("- Table 2. Study farms and data inventory.", "- Table 2. Study farm and data inventory.")
rep(" [Further farms to be added after recruitment, one column each in Table 2.]", "")
rep("using data that the participating farmers logged for their own purposes", "using data that the participating farmer logged for the farm's own purposes")

# 'pre-specified' status of sensitivity runs
rep("Two pre-specified sensitivity runs repeated the cross-validation without the seasons 2015 to 2017, for which no irrigation record exists, and without the three field-years whose observed yields exceed 80 t/ha; the latter is reported as the quality-screened level of Section 2.8.",
    "Two sensitivity runs, specified after the first results had been seen and before the final analysis and so post hoc with respect to the protocol, repeated the cross-validation without the seasons 2015 to 2017, for which no irrigation record exists, and without the three field-years whose observed yields exceed 80 t/ha; the latter is reported as the quality-screened level of Section 2.8. Every non-primary analysis in this paper is one of three kinds, pre-registered, specified before the final analysis but after first results, or post hoc after inspecting results, and the supplementary protocol file dates each.")
rep("The pre-specified sensitivity runs confirm this:", "The sensitivity runs confirm this:")
rep("with learning curves, bootstrap resampling and pre-specified sensitivity runs;", "with learning curves, bootstrap resampling and sensitivity runs;")

# 80 t/ha threshold: source or softer phrasing
rep("Quality-screened records additionally excludes field-years whose field-mean potato yield exceeds 80 t/ha, above the crop's attainable yield in Sweden and so a probable monitor calibration or unit error; three field-years met that rule.",
    "Quality-screened records additionally excludes field-years whose field-mean potato yield exceeds 80 t/ha. The threshold was chosen after viewing this dataset: the grower and the author considered field means above it, which exceed the farm's other records and the yields reported for Swedish ware potato, sufficiently implausible to indicate a probable monitor-calibration or unit problem, and three field-years met the rule. Because the threshold affects a prominent result, both quality levels are reported throughout.")
rep("three field-years reported 80 to 100 t/ha of potato, which is above the crop's attainable yield in Sweden and points to a monitor or unit problem,",
    "three field-years reported 80 to 100 t/ha of potato, which the grower and author judged implausible and a probable monitor or unit problem,")

# nutrient pool semantics
rep("The soil water store starts the season at field capacity and the nitrogen and potassium pools at zero, so that only logged applications supply nutrients.",
    "The soil water store starts the season at field capacity and the nitrogen and potassium pools at zero, so that only logged applications supply the explicit pools. The nutrient floor of Eq. (3) is therefore not a mechanistic nutrient pool: it is an empirical yield safeguard representing all indigenous and unrecorded supply, while the explicit seasonal pool contains logged applications only.")

# internal notes
rep("Target journal: Computers and Electronics in Agriculture. Draft 0.4 after external review, 2026-10-04.\nText in square brackets marks placeholders that depend on the data analysis.\n\n---\n\n", "")
rep("[Every entry with a DOI was checked against Crossref on 2026-10-03 (authors, year, title, journal, volume, pages). Entries without a DOI are books, FAO papers, an extension report and a Zenodo record and were not machine-checked.]\n\n", "")

# figure 7 compact + S3 full; figure 8 caption independence handled in builder
rep("Figure 7 lays out which fields had a yield map in which year and which consecutive pairs could be scored.",
    "Figure 7 lays out, for the fields with consecutive harvest years, which years had a yield map and which pairs could be scored; the full field-by-year matrix for all 36 fields is Figure S3.")
rep("- Figure 7. Fields, harvest years and scored pairs for the productivity index.",
    "- Figure 7. Fields with consecutive harvest years: yield maps, inferred crop and scored pairs.\n- Figure S3. Full field-by-year matrix of yield maps for all 36 fields.")

open(p, 'w', encoding='utf-8').write(s)
print('patched; missing anchors:', len(missing))
for m in missing:
    print('  MISSING:', m)
