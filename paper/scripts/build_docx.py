"""Assemble paper/manuscript.md, the tables and the figures into a Word
document, paper/manuscript.docx, with python-docx.

Markdown handled: '#'/'##'/'###' headings, paragraphs, '- ' bullet lists,
'|' pipe tables, '**bold**' and '*italic*' inline, X_{sub} and X^{sup} for
true sub- and superscripts, and display equations written as
``$$ latex $$ (n)`` on their own line.

Figures and main-text tables are placed directly after the paragraph that
first refers to them ("Figure 3", "Table 2"); supplementary tables and
figures go in sections at the end. Equations are written as plain
UnicodeMath text with the marker "EQ::"; running
``word_postprocess.ps1`` afterwards lets Word itself build them into native
equations and export an image of each for checking. Square-bracket
placeholders are highlighted.

Plain Python (python-docx), no QGIS needed:
    python paper/scripts/build_docx.py
    powershell -ExecutionPolicy Bypass -File paper/scripts/word_postprocess.ps1
"""
import os
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

import omml

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(HERE)
MANUSCRIPT = os.path.join(PAPER, 'manuscript.md')
TABLES = os.path.join(PAPER, 'tables')
FIGURES = os.path.join(PAPER, 'figures')
OUT = os.path.join(PAPER, 'manuscript.docx')

TABLE_FILES = {'1': 'table1_parameters.md', '2': 'table2_inventory.md',
               '3': 'table3_cv_metrics.md', '4': 'table4_fertility.md',
               '5': 'table5_reproducibility.md'}
SUPP_TABLE_FILES = ['tableS3_cv_detail.md', 'tableS4_sensitivity.md', 'tableS5_fertility_detail.md']
SUPP_NOTES = os.path.join(PAPER, 'supplementary_notes.md')
# Figure number -> (file, caption); the file names keep their historical
# numbers, the keys are the numbers used in the text.
FIGURE_FILES = {
    '1': ('fig1_dataflow.png',
          'Figure 1. Schematic representation of data processing in GeoDataFarm, linking field '
          'observations to the two analyses examined in this study.'),
    '2': ('fig_percentile_schematic.png',
          'Figure 2. How the productivity index is built, on a nine-cell field. (a) Three sources '
          'in different units: two yield maps and a clay map; one cell has no 2024 value. (b) Each '
          'source converted to inclusive percentile ranks (Eq. 5): the best cell scores 100 and the '
          'worst 0, tied cells share a rank. (c) The index as the equal-weight mean of the ranks '
          'available in each cell, and its five classes at the default boundaries. The numbers '
          "are computed by the plugin's own functions."),
    '3': ('fig_evaluation_workflow.png',
          'Figure 3. Evaluation workflow. Top: the records that entered and the units of analysis. '
          'Left: objectives O1 and O2, the leave-one-field-year-out cross-validation, the model '
          'variants and baselines predicted for the same held-out field-years, the resampling '
          'analyses and the scores. Right: objective O3, the consecutive-year pairs, the index '
          'variants and their scores. Analyses marked post hoc were added after the first results '
          'had been seen.'),
    '4': ('fig2_data_inventory.png',
          'Figure 4. Data inventory of the study farm. (a) Potato field-years with a usable '
          'training example by harvest year; 2022 had none. (b) Field-years excluded, by reason. '
          '(c) Observed yield of the 48 variety observations by field-year (dots), with the '
          'field-year mean (orange mark) and the mean of all observations (dashed line); '
          'field-years are ordered by harvest year.'),
    '5': ('fig3_predicted_vs_observed.png',
          'Figure 5. Predicted against observed potato yield for held-out field-years, post hoc '
          'variant, one point per field-year (mean over its variety observations). (a) Literature '
          'defaults, that is the model run with the default parameters of Table 1 and no fitting. '
          '(b) Farm-calibrated, three crop-level parameters. (c) Farm-calibrated with '
          'potential yield refitted per variety. (d) Training-set same-variety mean. Dashed line '
          'is 1:1. The variety-observation level is Figure S2.'),
    '6': ('fig4_learning_curve.png',
          'Figure 6. Learning curve. (a) Median typical error (RMSE) on the remaining field-years '
          'against the number of training field-years for the three-parameter fit, the '
          'potential-yield-only fit, the per-variety fit, and the farm-mean and variety-mean '
          'baselines computed from the same training field-years; bands are interquartile ranges '
          'across random training sets; the dashed line is the literature defaults. (b) Fitted '
          'potential yield against training field-years, median and interquartile range.'),
    '7': ('fig5_parameter_stability.png',
          'Figure 7. Fitted parameters across the 22 leave-one-field-year-out folds and 50 '
          'bootstrap resamples of field-years, unlogged nutrients not modelled.'),
    '8': ('fig6_limiting_factors.png',
          'Figure 8. (a) Model-attributed limiting factor per variety observation by harvest year, '
          'defined as the modelled term with the lowest relative yield when below 0.95; not an '
          'agronomically verified limitation. (b) Water relative '
          'yield of the calibrated model against logged irrigation, one point per field-year; '
          'orange points are 2015 to 2017, for which no irrigation record exists.'),
    '9': ('fig7_pairs_matrix.png',
          'Figure 9. The 15 fields with at least one scored consecutive-year pair: harvest years '
          'with a yield map covering at least 300 grid cells, the crop inferred from yield '
          'magnitude, the pairs scored for the productivity index, and the fields with a soil layer '
          '(EM38 conductivity or laboratory sampling). All 36 fields are shown in Figure S3.'),
    '10': ('fig8_example_field.png',
           "Figure 10. The field-year pair at the median rank correlation among pairs with a soil "
           "map: the previous season's yield map, the index built from it alone, its five "
           "classes, and the following season's yield map. The crop of each yield map, inferred "
           "from yield magnitude as in Figure 9, is given in the panel title; the two seasons grew "
           "different crops, so the yield ranges differ. Each panel is colour-scaled independently "
           "between its own 2nd and 98th percentile, and the analysis is rank-based. Shown with the "
           "farmer's consent."),
    '11': ('fig9_index_performance.png',
           "Figure 11. Spearman rank correlation between each index variant and the following "
           "season's cell yield on the 13 field-year pairs with a soil map; grey lines join "
           "the same pair, orange bars are medians."),
    'S2': ('figS2_predicted_vs_observed_examples.png',
           'Figure S2. As Figure 5 but at the level of the 48 variety observations; grey lines '
           'join the varieties of one field-year.'),
    'S3': ('figS3_pairs_matrix_all.png',
           'Figure S3. Field-by-year matrix of yield maps for all 36 fields, as Figure 9.'),
    'S1': ('figS1_objective_surfaces.png',
           'Figure S1. Sum of squared error at the all-data fit. (a) Over potential yield and '
           'nitrogen floor and (b) over the nitrogen factor and floor, unlogged nutrients not '
           'modelled. (c) Over potential yield and floor with unlogged nutrients at their floor. '
           'The white marker is the minimum.'),
}

INLINE = re.compile(r'(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]|[A-Za-z]+_\{[^}]+\}|[A-Za-z]+\^\{[^}]+\})')
EQUATION = re.compile(r'^\s*\$\$(.+?)\$\$\s*(?:\((\d+)\))?\s*$')
REFERENCE = re.compile(r'\b(Figure|Table) (S?\d+)')

placed = set()


def add_runs(paragraph, text):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            paragraph.add_run(part[2:-2]).bold = True
        elif part.startswith('*') and part.endswith('*'):
            paragraph.add_run(part[1:-1]).italic = True
        elif part.startswith('[') and part.endswith(']') and len(part) > 12:
            run = paragraph.add_run(part)
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
        elif re.fullmatch(r'[A-Za-z]+_\{[^}]+\}', part):
            base, sub = part.split('_{')
            paragraph.add_run(base)
            paragraph.add_run(sub[:-1]).font.subscript = True
        elif re.fullmatch(r'[A-Za-z]+\^\{[^}]+\}', part):
            base, sup = part.split('^{')
            paragraph.add_run(base)
            paragraph.add_run(sup[:-1]).font.superscript = True
        else:
            paragraph.add_run(part)


def add_equation(doc, expr, number):
    """A marker paragraph that word_postprocess.ps1 turns into a native
    equation. Readable as plain text if the post-processing is skipped."""
    linear = omml.latex_to_linear(expr.strip())
    doc.add_paragraph('EQ::{}::({})'.format(linear, number or ''))


def add_table(doc, lines):
    rows = [[c.strip() for c in line.strip().strip('|').split('|')] for line in lines
            if not re.match(r'^\|?\s*-{3,}', line.strip())]
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncols)
    table.style = 'Table Grid'
    for i, row in enumerate(rows):
        for j in range(ncols):
            cell = table.cell(i, j)
            cell.text = ''
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT  # not justified in narrow cells
            add_runs(paragraph, row[j] if j < len(row) else '')
            for run in paragraph.runs:
                run.font.size = Pt(8)
                if i == 0:
                    run.bold = True
    doc.add_paragraph()


def add_figure(doc, key):
    name, caption = FIGURE_FILES[key]
    path = os.path.join(FIGURES, name)
    if not os.path.exists(path):
        doc.add_paragraph('[{} missing]'.format(name))
        return
    # the two box diagrams use the full text width; the rest stay at 16 cm
    doc.add_picture(path, width=Cm(16.5 if key in ('1', '3') else 16))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
    add_runs(cap, caption)
    for run in cap.runs:
        run.font.size = Pt(9)
    doc.add_paragraph()


def add_table_file(doc, name):
    path = os.path.join(TABLES, name)
    if not os.path.exists(path):
        doc.add_paragraph('[{} missing]'.format(name))
        return
    with open(path, encoding='utf-8') as handle:
        lines = handle.read().splitlines()
    add_markdown_block(doc, lines, place_inline=False)


def add_markdown_file(doc, path):
    """A standalone markdown file with '###'/'####' headings (the
    supplementary notes), rendered without inline figure placement."""
    if not os.path.exists(path):
        doc.add_paragraph('[{} missing]'.format(os.path.basename(path)))
        return
    with open(path, encoding='utf-8') as handle:
        lines = handle.read().splitlines()
    block = []
    for line in lines + ['# end']:
        heading = re.match(r'^(#{1,4})\s+(.*)', line)
        if heading:
            if block:
                add_markdown_block(doc, block, place_inline=False)
                block = []
            if heading.group(2).strip() != 'end':
                doc.add_heading(heading.group(2).strip(), level=min(len(heading.group(1)), 3))
        else:
            block.append(line)


def place_after(doc, text):
    """Insert any figure or main-text table first referred to in ``text``."""
    for kind, key in REFERENCE.findall(text):
        tag = (kind, key)
        if tag in placed or key.startswith('S'):
            continue
        if kind == 'Figure' and key in FIGURE_FILES:
            placed.add(tag)
            add_figure(doc, key)
        elif kind == 'Table' and key in TABLE_FILES:
            placed.add(tag)
            add_table_file(doc, TABLE_FILES[key])


def add_markdown_block(doc, lines, place_inline=True):
    """Render a list of markdown lines (no headings) into the document."""
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.lstrip().startswith('|'):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                block.append(lines[i])
                i += 1
            add_table(doc, block)
            continue
        if re.match(r'^\s*-\s+', line):
            while i < len(lines) and re.match(r'^\s*-\s+', lines[i]):
                text = re.sub(r'^\s*-\s+', '', lines[i])
                i += 1
                while i < len(lines) and lines[i].startswith('  ') and lines[i].strip() \
                        and not re.match(r'^\s*-\s+', lines[i]):
                    text += ' ' + lines[i].strip()
                    i += 1
                add_runs(doc.add_paragraph(style='List Bullet'), text)
            continue
        eq = EQUATION.match(line)
        if eq:
            add_equation(doc, eq.group(1), eq.group(2))
            i += 1
            continue
        if re.match(r'^\s*\d+\.\s+', line) or re.match(r'^\s*O\d\.\s', line):
            text = line.strip()
            i += 1
            while i < len(lines) and lines[i].startswith('  ') and lines[i].strip():
                text += ' ' + lines[i].strip()
                i += 1
            add_runs(doc.add_paragraph(style='List Bullet'), text)
            if place_inline:
                place_after(doc, text)
            continue
        text = line.strip()
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('|', '#', '$$')) \
                and not re.match(r'^\s*-\s+', lines[i]):
            text += ' ' + lines[i].strip()
            i += 1
        if text == '---':
            continue
        add_runs(doc.add_paragraph(), text)
        if place_inline:
            place_after(doc, text)


def main():
    with open(MANUSCRIPT, encoding='utf-8') as handle:
        lines = handle.read().splitlines()
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)
    # justified body text, proofing language British English (the headings,
    # lists, captions and table text inherit both from Normal)
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    rpr = style.element.get_or_add_rPr()
    for old in rpr.findall(qn('w:lang')):
        rpr.remove(old)
    lang = OxmlElement('w:lang')
    lang.set(qn('w:val'), 'en-GB')
    lang.set(qn('w:eastAsia'), 'en-GB')
    rpr.append(lang)
    theme_lang = OxmlElement('w:themeFontLang')
    theme_lang.set(qn('w:val'), 'en-GB')
    doc.settings.element.append(theme_lang)
    for section in doc.sections:
        section.left_margin = section.right_margin = Cm(2.5)
        section.top_margin = section.bottom_margin = Cm(2.5)

    block = []
    skipping = False
    in_front_matter = True  # title block, highlights and abstract: no inline placement

    def flush():
        if block:
            add_markdown_block(doc, block, place_inline=not in_front_matter)
            block.clear()

    for line in lines:
        heading = re.match(r'^(#{1,4})\s+(.*)', line)
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if title == 'Tables' or title.startswith('Figures and tables'):
                skipping = True  # the planning lists; everything is placed inline now
                continue
            skipping = False
            if title.startswith('1. Introduction'):
                in_front_matter = False
            if level == 1:
                p = doc.add_paragraph()
                run = p.add_run(title)
                run.bold = True
                run.font.size = Pt(16)
            else:
                doc.add_heading(title, level=level - 1)
            continue
        if skipping:
            continue
        block.append(line)
    flush()

    # anything referenced only in captions or never referenced
    for key in FIGURE_FILES:
        if not key.startswith('S') and ('Figure', key) not in placed:
            add_figure(doc, key)
    for key, name in TABLE_FILES.items():
        if ('Table', key) not in placed:
            add_table_file(doc, name)
    doc.add_heading('Supplementary material', level=1)
    add_markdown_file(doc, SUPP_NOTES)
    add_figure(doc, 'S1')
    add_figure(doc, 'S2')
    add_figure(doc, 'S3')
    for name in SUPP_TABLE_FILES:
        add_table_file(doc, name)
    doc.save(OUT)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
