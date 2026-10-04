"""One-off patch for the author's second comment round (2026-10-03).
Applies reference-list repairs, the author's own v2 text edits, the comment
edits, and the figure renumbering (new Figure 7 = pairs matrix)."""
import os

PAPER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(PAPER, 'manuscript.md')
s = open(p, encoding='utf-8').read()
missing = []


def rep(old, new, count=1):
    global s
    if old not in s:
        missing.append(old[:80])
        return
    s = s.replace(old, new, count)


# --- reference list repair: Kruskal spliced into Fridgen
rep("Fridgen, J.J., Kruskal, W.H., Wallis, W.A., 1952. Use of ranks in one-criterion variance analysis. Journal of the American Statistical Association 47, 583-621.\n\nKitchen, N.R., Sudduth, K.A., Drummond, S.T., Wiebold, W.J., Fraisse, C.W., 2004. Management zone analyst (MZA): software for subfield management zone delineation. Agronomy Journal 96, 100-108.",
    "Fridgen, J.J., Kitchen, N.R., Sudduth, K.A., Drummond, S.T., Wiebold, W.J., Fraisse, C.W., 2004. Management zone analyst (MZA): software for subfield management zone delineation. Agronomy Journal 96, 100-108. https://doi.org/10.2134/agronj2004.1000")
rep("Kitchen, N.R., Sudduth, K.A., Myers, D.B., Drummond, S.T., Hong, S.Y., 2005.",
    "Kruskal, W.H., Wallis, W.A., 1952. Use of ranks in one-criterion variance analysis. Journal of the American Statistical Association 47, 583-621. https://doi.org/10.1080/01621459.1952.10483441\n\nKitchen, N.R., Sudduth, K.A., Myers, D.B., Drummond, S.T., Hong, S.Y., 2005.")
rep("Steduto, P., Hsiao, T.C., Raes, D., Fereres, E., 2009. AquaCrop: the FAO crop model to simulate yield response to water. Agronomy Journal 101, 426-437.",
    "Steduto, P., Hsiao, T.C., Raes, D., Fereres, E., 2009. AquaCrop: the FAO crop model to simulate yield response to water: I. Concepts and underlying principles. Agronomy Journal 101, 426-437. https://doi.org/10.2134/agronj2008.0139s")
rep("Czymmek, K.J., Ketterings, Q.M., van Es, H.M., DeGloria, S.D., 2003. The New York nitrate leaching index. Cornell University Extension.",
    "van Es, H.M., Czymmek, K.J., Ketterings, Q.M., 2002. Management effects on nitrogen leaching and guidelines for a nitrogen leaching index in New York. Journal of Soil and Water Conservation 57, 499-504.")
rep("(Czymmek et al., 2003; De Jong et al., 2007)", "(van Es et al., 2002; De Jong et al., 2007)")
rep("Wallach, D., Palosuo, T., Thorburn, P., Mielenz, H., Buis, S., Hochman, Z., et al., 2023. Proposal and extensive test of a calibration protocol for crop phenology models. Agronomy for Sustainable Development 43 [verify article number].",
    "Wallach, D., Palosuo, T., Thorburn, P., Mielenz, H., Buis, S., Hochman, Z., et al., 2023. Proposal and extensive test of a calibration protocol for crop phenology models. Agronomy for Sustainable Development 43, 46.")
# DOIs confirmed by Crossref for older entries
for key, doi in (("Jones, J.W., Hoogenboom, G., Porter, C.H., Boote, K.J., Batchelor, W.D., Hunt, L.A., et al., 2003. The DSSAT cropping system model. European Journal of Agronomy 18, 235-265.", "10.1016/S1161-0301(02)00107-7"),
                 ("Holzworth, D.P., Huth, N.I., deVoil, P.G., Zurcher, E.J., Herrmann, N.I., McLean, G., et al., 2014. APSIM: evolution towards a new generation of agricultural systems simulation. Environmental Modelling and Software 62, 327-350.", "10.1016/j.envsoft.2014.07.009"),
                 ("Zhao, C., Liu, B., Xiao, L., Hoogenboom, G., Boote, K.J., Kassie, B.T., et al., 2019. A SIMPLE crop model. European Journal of Agronomy 104, 97-106.", "10.1016/j.eja.2019.01.009"),
                 ("de Wit, A., Boogaard, H., Fumagalli, D., Janssen, S., Knapen, R., van Kraalingen, D., et al., 2019. 25 years of the WOFOST cropping systems model. Agricultural Systems 168, 154-167.", "10.1016/j.agsy.2018.06.018"),
                 ("Saxton, K.E., Rawls, W.J., 2006. Soil water characteristic estimates by texture and organic matter for hydrologic solutions. Soil Science Society of America Journal 70, 1569-1578.", "10.2136/sssaj2005.0117"),
                 ("Maestrini, B., Basso, B., 2018. Drivers of within-field spatial and temporal variability of crop yield across the US Midwest. Scientific Reports 8, 14833.", "10.1038/s41598-018-32779-3"),
                 ("Kitchen, N.R., Sudduth, K.A., Myers, D.B., Drummond, S.T., Hong, S.Y., 2005. Delineating productivity zones on claypan soil fields using apparent soil electrical conductivity. Computers and Electronics in Agriculture 46, 285-308.", "10.1016/j.compag.2004.11.012"),
                 ("Blackmore, S., Godwin, R.J., Fountas, S., 2003. The analysis of spatial and temporal trends in yield map data over six years. Biosystems Engineering 84, 455-466.", "10.1016/S1537-5110(03)00038-2"),
                 ("Blackmore, S., 2000. The interpretation of trends from multiple yield maps. Computers and Electronics in Agriculture 26, 37-51.", "10.1016/S0168-1699(99)00075-7"),
                 ("Basso, B., Ritchie, J.T., Pierce, F.J., Braga, R.P., Jones, J.W., 2001. Spatial validation of crop models for precision agriculture. Agricultural Systems 68, 97-112.", "10.1016/S0308-521X(00)00063-9"),
                 ("Batchelor, W.D., Basso, B., Paz, J.O., 2002. Examples of strategies to analyze spatial and temporal yield variability using crop models. European Journal of Agronomy 18, 141-158.", "10.1016/S1161-0301(02)00101-6"),
                 ("van Klompenburg, T., Kassahun, A., Catal, C., 2020. Crop yield prediction using machine learning: a systematic literature review. Computers and Electronics in Agriculture 177, 105709.", "10.1016/j.compag.2020.105709"),
                 ("Fountas, S., Carli, G., Sørensen, C.G., Tsiropoulos, Z., Cavalaris, C., Vatsanidou, A., et al., 2015. Farm management information systems: current situation and future perspectives. Computers and Electronics in Agriculture 115, 40-50.", "10.1016/j.compag.2015.05.011"),
                 ("Seidel, S.J., Palosuo, T., Thorburn, P., Wallach, D., 2018. Towards improved calibration of crop models: where are we now and where should we go? European Journal of Agronomy 94, 25-35.", "10.1016/j.eja.2018.01.006"),
                 ("Confalonieri, R., Orlando, F., Paleari, L., Stella, T., Gilardelli, C., Movedi, E., et al., 2016. Uncertainty in crop model predictions: what is the role of users? Environmental Modelling and Software 81, 165-173.", "10.1016/j.envsoft.2016.04.009"),
                 ("van der Ploeg, R.R., Böhm, W., Kirkham, M.B., 1999. On the origin of the theory of mineral nutrition of plants and the law of the minimum. Soil Science Society of America Journal 63, 1055-1062.", "10.2136/sssaj1999.6351055x"),
                 ("Spitters, C.J.T., Schapendonk, A.H.C.M., 1990. Evaluation of breeding strategies for drought tolerance in potato by means of crop growth simulation. Plant and Soil 123, 193-203.", "10.1007/BF00011268"),
                 ("Wilcoxon, F., 1945. Individual comparisons by ranking methods. Biometrics Bulletin 1, 80-83.", "10.2307/3001968"),
                 ("Spearman, C., 1904. The proof and measurement of association between two things. American Journal of Psychology 15, 72-101.", "10.2307/1412159")):
    rep(key, key + " https://doi.org/" + doi)

# --- author's own edits from v2
rep("The importer matches units by column name, removes implausible points with an outlier filter, optionally corrects the time lag between a sensor reading and its logged position, and reconstructs harvester passes as row polygons. Every imported point receives a Voronoi polygon clipped to the field boundary, so that later spatial joins can ask which sample is nearest to any location. Manual operations, such as planting, fertiliser application, spraying and irrigation, are entered through journal forms whose fields are configurable per farm. Weather",
    "The importer matches units by column name, removes implausible points with an outlier filter, and optionally corrects the time lag between a sensor reading and its logged position. Every imported point, except those related to harvest, receives a Voronoi polygon clipped to the field boundary, so that later spatial joins can ask which sample is nearest to any location. Weather")
rep(" Field-years whose most recent planting record is from an earlier calendar year are excluded by default to avoid stale planting dates.", "")
rep("All participating farmers gave written consent for the use of their logged data, anonymised publication of aggregate results and no publication of raw yield maps.",
    "The participating farmer gave consent for the use of the logged data, anonymised publication of aggregate results and no publication of raw yield-monitor data.")

# --- abstract (comments 0-3)
rep("Calibration reduced the typical error from 58 % to 31 % of mean yield and removed a 31 t/ha bias, but did not beat the farm mean at 27 %, so the pre-registered criterion was not met. The mean yield of the same variety in other seasons was the best predictor, at 22 %; refitting potential yield per variety only brought the model level with the farm mean.",
    "Calibration reduced the typical prediction error from 58 % to 31 % of the mean yield and removed a 31 t/ha bias, but the farm's own mean yield, used as a prediction, had a typical error of 27 %, so the pre-registered criterion of beating it was not met. The mean yield of the same variety in other seasons was the best predictor, with a typical error of 22 % of the mean yield; refitting potential yield per variety only brought the model level with the farm mean.")
rep("The previous season's yield map ranked the next crop's yield with a median Spearman rho of 0.18; equal-weight combination with soil sources removed that signal in 12 of 13 pairs, and sign-aware weights recovered it. Two data-handling defects found by the protocol were fixed in the software. The records supported a yield-level correction and little more; the study's value is in showing which missing records prevented more.",
    "The previous season's yield map alone ranked the cells of a field by their yield in the following season with a median Spearman correlation of 0.18. Adding the soil maps to it with equal weights, the plugin's default, destroyed that ranking in 12 of 13 field pairs, because the soil maps were related to yield in different directions on different fields; weighting each map by its own relation to the previous yield map kept the ranking. A farm's own records can correct a crop model's yield level, and on this farm the choice of variety explained more of the yield than weather, water or nutrients as logged. Unless a farm management system captures irrigation, fertiliser rates and soil texture when the operation happens, and treats a missing record as unknown rather than zero, a calibrated crop model will not outperform the farmer's own averages.")

# --- 1.2 AquaCrop (comment 4)
rep("Process-based crop simulators such as DSSAT, APSIM, WOFOST and AquaCrop are the scientific standard for yield prediction and scenario analysis (Jones et al., 2003; Holzworth et al., 2014; de Wit et al., 2019; Steduto et al., 2009).",
    "Process-based crop simulators such as DSSAT, APSIM and WOFOST are the scientific standard for yield prediction and scenario analysis (Jones et al., 2003; Holzworth et al., 2014; de Wit et al., 2019).")
rep("Between these extremes sit deliberately small process models: AquaCrop itself is built to need few parameters, the SIMPLE model",
    "Between these extremes sit deliberately small process models: AquaCrop is built around a water-driven canopy with few parameters (Steduto et al., 2009), the SIMPLE model")

# --- 1.3 opening (comment 5)
rep("Studies that calibrate crop models with yield-monitor data have mostly used research-grade simulators and have been carried out by researchers with access to the raw data (Basso et al., 2001; Batchelor et al., 2002). Calibration itself is a statistical problem with known pitfalls:",
    "Calibrating a crop model against yield-monitor data is now a routine research task, from yield-only calibration of cultivar coefficients at scale (Machado et al., 2026) to data collection designed around identifiability analysis (Coudron et al., 2021), but in every case it is done by researchers on data they have assembled, not by the farmer who generated the records. Calibration itself is a statistical problem with known pitfalls:")
rep("can be assessed before data are even collected (Coudron et al., 2021) and is arguably", "can be assessed before data are even collected and is arguably")

# --- 2.2 potential yield definition (comment 26)
rep("where Y_{pot} is the potential yield in t/ha and m_{spacing} an optional planting-spacing multiplier: the most limiting factor alone sets the yield,",
    "where Y_{pot} is the potential yield in t/ha and m_{spacing} an optional planting-spacing multiplier. Potential yield is the yield the crop would give in that field with no water or nutrient limitation; it is a property of the crop, the variety and the farm, not of the season. The season's weather enters through the relative-yield terms, which scale the potential yield down by the water deficit and the nutrient shortfall that the weather and the management produced. The most limiting factor alone sets the yield,")

# --- 2.4 example without conductivity (comment 17)
rep("A source is any layer with one value per location: a harvest year's yield map, a laboratory soil attribute such as clay or K-AL, or a sensed one such as EM38 conductivity. Several harvest years enter as separate sources, so a field with yield maps from 2021, 2023 and 2024 and a conductivity survey has four sources. Because a yield map in kg/ha, one in t/ha, a percentage and a conductivity in mS/m cannot be averaged directly,",
    "A source is any layer with one value per location: a harvest year's yield map or a soil attribute such as clay content. Several harvest years enter as separate sources, so a field with yield maps from 2021, 2023 and 2024 and a clay map has four sources. Because a yield map in kg/ha, one in t/ha and a clay content in percent cannot be averaged directly,")
rep("A worked example: a cell ranked 80 on the 2023 map, 40 on the 2024 map and 60 on conductivity has an index of 60 at equal weights, or 64 if the yield maps are weighted 2 and conductivity 1.",
    "A worked example: a cell ranked 80 on the 2023 yield map, 40 on the 2024 map and 60 on clay has an index of 60 at equal weights, or 64 if the yield maps are weighted 2 and clay 1.")

# --- rotation (comment 23)
rep("the pre-registered previous-season baseline could not be computed because no field carried potato in two consecutive eligible years.",
    "the pre-registered previous-season baseline could not be computed because no field carried potato in two consecutive eligible years; potato is grown in rotation with cereals and oilseed rape to limit soil-borne disease and nematodes.")

# --- 2.6 learning curve purpose (comment 24)
rep("For the learning curve, the model was fitted on random subsets of k training field-years for k in 1, 2, 3, 4, 6, 8, 12, 16 and 20, at most 25 subsets per k, and scored on the remaining field-years against the mean of the same k training field-years as the k-matched baseline.",
    "The learning curve answers a practical question: how many seasons of records does a farm need before calibration pays off? The model was fitted on random subsets of k training field-years, for k from 1 to 20, and scored on the field-years left out; the baseline at each k is the mean of the same k training field-years, so that model and baseline always see the same records.")

# --- 2.6 O3 paragraph simplified (comment 25)
rep("Objective O3. For every field and pair of consecutive harvest years t - 1 and t, the index was built from the season t - 1 yield map plus every soil source with one weight per source and five classes, the plugin's default, together with a yield-only index, a soil-only index, and, post hoc, three alternatives: one weight per source group so that the conductivity depths count once, weights proportional to each source's absolute rank correlation with the season t - 1 yield map with the rank reversed for a negatively associated source, and a z-score average with grouped weights as a conventional comparator. Where t - 2 existed a two-year variant was also built. Each was scored against the season t cell yield by Spearman rank correlation on all cells, by a Kruskal-Wallis test across classes on a subsample thinned to the distance over which neighbouring cells of the season t yield map remain correlated, estimated from an empirical variogram and capped at 100 m, and by the mean yield difference between the top and bottom class on all cells as a percentage of the field mean. Variants were compared paired on the pairs that have a soil source with a two-sided sign test. Because pairs from the same field are not independent, results are also aggregated to one median per field. Harvest columns that mixed kilograms and tonnes per hectare within one year were harmonised to the majority unit before use. Sensitivity was assessed with soil weights of 0.5 and 2 and with three or seven classes.",
    "Objective O3 asks whether an index built from what was known before a season predicts where in the field that season yielded well. For every field with yield maps from two consecutive harvest years, t - 1 and t, the index was built from the t - 1 map and the field's soil maps and scored against the t map (Figure 7 shows which fields and years qualified). Six variants were built: the t - 1 yield map alone; the soil maps alone; yield plus soil with one weight per map, which is the plugin's default; the same with one weight per group of maps, so that two EM38 depths count once; weights set by how strongly each map was related to the t - 1 yield map, with the rank reversed for a map related in the wrong direction; and a z-score average as a conventional comparator. Each variant was scored in three ways: the Spearman rank correlation between index and t yield over all cells; whether yield differed between the five index classes, tested on a spatially thinned subsample so that neighbouring cells do not count as independent observations; and the yield difference between the top and bottom class as a percentage of the field mean. Variants were compared with the yield-only index pair by pair, and results were also summarised per field because pairs from the same field are not independent. Harvest maps that mixed kilograms and tonnes per hectare within one year were harmonised to the majority unit first. Soil weights of 0.5 and 2 and three or seven classes were tried as sensitivity checks.")

# --- 3.2 remove EC and field-mean sentences (comment 27)
rep(" A per-field offset of potential yield from the field's mean EM38 conductivity, the one way soil could be brought into the model with the data on file, was fitted to zero in 13 of 22 folds and made the model slightly worse where it was not. The field-mean baseline, available for the 10 field-years whose field has another potato year on file three to eight years apart, was worse than every other predictor and is not shown; the pre-registered previous-season baseline could not be computed because no field carried potato in two consecutive eligible years.", "")
rep("because the default potential yield of 45 t/ha is below this farm's attainable level.", "because the default potential yield of 45 t/ha is below what this farm harvests in a good year.")

# --- 3.4 plainer (comment 28)
rep("In the post hoc treatment potential yield was fitted to 89.8 t/ha in 21 of 22 leave-one-out folds and 97.4 t/ha in one; the nitrogen factor to 1.68 in 18 folds and otherwise 0.48, 1.80 and twice 1.92; the floor to 0.52 in 18 folds and otherwise 0.44 twice, 0.56 once and 0 once, the last at the edge of its range (Figure 5). These are grid values: the fine grid steps are 7.6 t/ha, 0.24 and 0.08, and any two leave-one-out training sets share 20 of 21 field-years, so agreement across folds is expected and says little. The 50 bootstrap resamples of field-years give the fairer picture: potential yield had a median of 89.8 t/ha with a 5th to 95th percentile range of 82 to 97 t/ha, the nitrogen factor 1.68 with an interquartile range of 1.08 to 1.92 and a 5th to 95th range of 0.48 to 2.04, and the floor 0.52 with an interquartile range of 0.44 to 0.56 and a 5th to 95th range of 0 to 0.64. Potential yield is thus determined to within about 10 %, the nitrogen factor and floor only to within their search ranges, which is what eight field-years with a rate allow.",
    "A parameter is well determined when fitting it to different subsets of the data gives nearly the same value. Two kinds of subset were used. In the 22 cross-validation folds, each of which leaves one field-year out, potential yield came out at 89.8 t/ha in 21 folds and 97.4 t/ha in one, the nitrogen factor at 1.68 in 18 folds, and the floor at 0.52 in 18 folds (Figure 5). That agreement is partly built in, however: any two folds share 20 of their 21 training field-years, and the fitted values can only fall on the grid the search uses, whose fine steps are 7.6 t/ha, 0.24 and 0.08. The 50 bootstrap samples, each drawing 22 field-years at random with replacement so that some field-years appear twice and others not at all, give the fairer picture. Across them potential yield stayed within 82 to 97 t/ha for 90 % of the samples, about 10 % either side of its median, whereas the nitrogen factor ranged from 0.48 to 2.04 and the floor from 0 to 0.64, most of their search ranges. Potential yield is thus the one parameter this farm's records determine; the two nitrogen parameters are not, which is what eight field-years with a fertiliser rate allow.")

# --- 3.6 opening with figure reference (comment 29); renumber figures 7->8, 8->9 first
rep("Figure 7 shows the pair at the median correlation.", "Figure 8 shows the pair at the median correlation.")
rep("(sign test p = 0.003; Figure 8)", "(sign test p = 0.003; Figure 9)")
rep("(Figure 7, first panel)", "(Figure 8, first panel)")
rep("Thirty pairs of consecutive harvest years on 19 fields were on file; 21 pairs on 15 fields met the coverage rules, and 13 of these, on 8 fields, had a soil source: EM38 conductivity at one or two depths on 7 fields and laboratory sampling on one. Eight harvest columns mixed kilograms and tonnes per hectare within one year and were harmonised before use, in one case for 466 of 1285 cells. Because the farm rotates potato with cereals and oilseed rape, 20 of the 21 pairs cross a crop boundary: 11 run from potato to a cereal or rape, 6 the other way, 3 from cereal to cereal, and one from potato to potato; the crop labels are inferred from yield magnitude, since the cereal seasons have no planting record.",
    "Figure 7 lays out which fields had a yield map in which year and which consecutive pairs could be scored. Thirty pairs of consecutive harvest years on 19 fields were on file; 21 pairs on 15 fields had enough cells with both maps to be scored, and 13 of these, on 8 fields, also had a soil map: EM38 conductivity at one or two depths on 7 fields and laboratory sampling on one. Eight harvest maps mixed kilograms and tonnes per hectare within one year and were harmonised before use, in one case for 466 of 1285 cells. Because the farm rotates potato with cereals and oilseed rape, 20 of the 21 pairs cross a crop boundary: 11 run from potato to a cereal or rape, 6 the other way, 3 from cereal to cereal, and one from potato to potato; the crop labels are inferred from yield magnitude, since the cereal seasons have no planting record.")

# --- 4.1 propagate
rep("The one cheap way to bring them in, a per-field potential-yield offset from mean conductivity, was fitted to zero in most folds, so a field's conductivity does not explain its yield level on this farm once variety is accounted for; a proper soil term would need the texture, water-holding and nutrient-supply data that the plugin can hold but this farm has sampled once.",
    "A per-field offset of potential yield from mean conductivity, tried as the one way to bring that data in, was fitted to zero in most folds (Table S3), so a field's conductivity does not explain its yield level on this farm once variety is accounted for; a proper soil term would need the texture, water-holding and nutrient-supply data that the plugin can hold but this farm has sampled once.")
rep("Studies that calibrate research-grade simulators with yield-monitor data report a related pattern, that the largest single improvement is in the cultivar or potential-yield coefficient and the remaining error lies in factors the model does not carry (Basso et al., 2001; Batchelor et al., 2002);",
    "Studies that calibrate research-grade simulators with yield-monitor data report a related pattern, that the largest single improvement is in the cultivar or potential-yield coefficient and the remaining error lies in factors the model does not carry (Basso et al., 2001; Batchelor et al., 2002; Machado et al., 2026);")

# --- conclusions propagate
rep("Variety explained more than any model term: the mean of the same variety in other seasons predicted at 22 % with the only positive efficiency, and refitting potential yield per variety brought the model level with the farm mean but not with that. Soil quality is effectively absent from the model on this farm, and a conductivity-based offset did not help.",
    "Variety explained more than any model term: the mean of the same variety in other seasons predicted with a typical error of 22 % of mean yield and the only positive efficiency, and refitting potential yield per variety brought the model level with the farm mean but not with that. Soil quality is effectively absent from the model on this farm.")

# --- figure list at the end
rep("- Figure 7. Example field: fertility index, classes and next-season yield.\n- Figure 8. Index performance across fields and variants.",
    "- Figure 7. Fields, harvest years and scored pairs for the fertility index.\n- Figure 8. Example field: fertility index, classes and next-season yield.\n- Figure 9. Index performance across fields and variants.")

# --- three references resolved by Crossref on 2026-10-03
rep("De Jong, R., Yang, J.Y., Drury, C.F., Huffman, E.C., Kirkwood, V., Yang, X.M., 2007. The indicator of risk of water contamination by nitrate-nitrogen. Canadian Journal of Soil Science 87, 179-188.",
    "De Jong, R., Yang, J.Y., Drury, C.F., Huffman, E.C., Kirkwood, V., Yang, X.M., 2007. The indicator of risk of water contamination by nitrate-nitrogen. Canadian Journal of Soil Science 87, 179-188. https://doi.org/10.4141/S06-060")
rep("Bouras, E.H., Olsson, P.-O., Thapa, S., Díaz, J.M., Albertsson, J., Eklundh, L., 2023. Wheat yield estimation at high spatial resolution through the assimilation of Sentinel-2 data into a crop growth model. Remote Sensing 15.",
    "Bouras, E.H., Olsson, P.-O., Thapa, S., Díaz, J.M., Albertsson, J., Eklundh, L., 2023. Wheat yield estimation at high spatial resolution through the assimilation of Sentinel-2 data into a crop growth model. Remote Sensing 15, 4425. https://doi.org/10.3390/rs15184425")
rep("Clarke, D.E., Stockdale, E.A., Hannam, J.A., Marchant, B.P., Hallett, S.H., 2024. Whole-farm yield map datasets: data validation for exploring spatiotemporal yield and economic stability. Agricultural Systems 218 [verify volume and article number].",
    "Clarke, D.E., Stockdale, E.A., Hannam, J.A., Marchant, B.P., Hallett, S.H., 2024. Whole-farm yield map datasets: data validation for exploring spatiotemporal yield and economic stability. Agricultural Systems 218, 103972. https://doi.org/10.1016/j.agsy.2024.103972")
rep("[All entries to be verified against the original sources before submission. Author-year keys as used in the text.]",
    "[Every entry with a DOI was checked against Crossref on 2026-10-03 (authors, year, title, journal, volume, pages). Entries without a DOI are books, FAO papers, an extension report and a Zenodo record and were not machine-checked.]")

open(p, 'w', encoding='utf-8').write(s)
print('patched; missing anchors:', len(missing))
for m in missing:
    print('  MISSING:', m)
