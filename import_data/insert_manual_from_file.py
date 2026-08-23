from typing import TYPE_CHECKING, Self
if TYPE_CHECKING:
    import geodatafarm.database_scripts.db
    import geodatafarm.widgets.import_text_dialog

from qgis.PyQt.QtWidgets import QLabel, QLineEdit, QComboBox, QCheckBox
from ..database_scripts.db import ensure_ferti_nutrient_column
from ..support_scripts import check_text
from ..support_scripts.__init__ import TR

# Spec columns whose value is always one fixed choice for the *whole*
# import, never a per-row source column - rendered as a plain QComboBox
# instead of the generic column-reference/typed-value/not-applicable
# widget set _resolve builds for the rest. Nutrient is the only one so
# far (see ferti.manual.nutrient, database_scripts.db.
# ensure_ferti_nutrient_column): unlike Variety/Rate, a ferti import's
# nutrient doesn't vary row to row - one product goes in the spreader
# per pass - so "point me at a column" doesn't make sense for it, and
# routing it through the same check_text() sanitiser _resolve's combo
# path uses for a column-name reference would lowercase it ('N' ->
# 'n'), breaking the exact-case match rate_keys.get(nutrient) needs.
FIXED_CHOICE_COLUMNS = {'Nutrient': ['N', 'P', 'K', 'Mg', 'S', 'Na']}


class ManualFromFile:
    def __init__(self: Self, db: "geodatafarm.database_scripts.db.DB", widget: "geodatafarm.widgets.import_text_dialog.ImportTextDialog", spec_columns: list[str]) -> None:
        """Adds Manual data from file

        Parameters
        ----------
        db: database object
        tr: translation function
        widget: QtWidget, must contain following element: CBCrop, GLSpecific
        """
        self.db = db
        translate = TR('ManualFromFile')
        self.tr = translate.tr
        self.manual_values = {}
        self.spec_columns = spec_columns
        self.widget = widget
        self.add_specific_columns(widget, spec_columns)

    def prepare_data(self: Self, columns_to_add: list[str]) -> None:
        """Adds rows to the comboboxes

        Parameters
        ----------
        columns_to_add: list
        """
        for i, column in enumerate(self.spec_columns):
            if self.manual_values[i].get('fixed_choice'):
                continue  # already fully populated in add_specific_columns
            self.manual_values[i]['Combo'].setEnabled(True)
            self.manual_values[i]['Combo'].addItems(columns_to_add)
            self.manual_values[i]['line_edit'].setEnabled(True)
            self.manual_values[i]['checkbox'].setEnabled(True)

    def add_specific_columns(self: Self,
                             widget: "geodatafarm.widgets.import_text_dialog.ImportTextDialog",
                             spec_columns: list[str]) -> None:
        """Adds rows for the user to manual define which columns contains
        schema specific columns (or one single value / Not applicable) -
        or, for a column in :data:`FIXED_CHOICE_COLUMNS`, a plain combo
        of that column's fixed choices instead (see its docstring).

        Parameters
        ----------
        widget: QtWidget
            A widget with a layout named "GLSpecific" where data type specific
            data is loaded
        spec_columns: list
            Each column gets three choices, one of the rows, spec value or NA
        """
        self.manual_values = {}
        for i, column in enumerate(spec_columns):
            self.manual_values[i] = {}
            label = QLabel(column)
            widget.GLSpecific.addWidget(label, i, 0)
            if column in FIXED_CHOICE_COLUMNS:
                combo = QComboBox()
                combo.addItems(FIXED_CHOICE_COLUMNS[column])
                combo.setFixedWidth(220)
                self.manual_values[i]['Combo'] = combo
                self.manual_values[i]['fixed_choice'] = True
                widget.GLSpecific.addWidget(combo, i, 1)
                continue
            self.manual_values[i]['fixed_choice'] = False
            combo = QComboBox()
            combo.setEnabled(False)
            combo.setFixedWidth(220)
            self.manual_values[i]['Combo'] = combo
            widget.GLSpecific.addWidget(combo, i, 1)
            line = QLineEdit()
            line.setEnabled(False)
            line.setFixedWidth(220)
            self.manual_values[i]['line_edit'] = line
            widget.GLSpecific.addWidget(line, i, 2)
            check = QCheckBox(text=self.tr('Not Applicable'))
            check.setEnabled(False)
            check.setFixedWidth(220)
            self.manual_values[i]['checkbox'] = check
            widget.GLSpecific.addWidget(check, i, 3)

    def insert_manual_data(self: Self, date_: str, field: str, table: str, data_type: str) -> bool:
        """Inserts the manual data that is used to generate reports, rather long
        function since all schemas have separate attributes.

        Parameters
        ----------
        date_: str
            The column where the dates is listed or one date that is the same
            for all rows (than it starts with c/_)

        Returns
        -------
        bool
            If success or not
        """
        def _resolve(idx):
            if self.manual_values[idx].get('fixed_choice'):
                return self.manual_values[idx]['Combo'].currentText()
            if self.manual_values[idx]['checkbox'].isChecked():
                return 'None'
            combo_text = self.manual_values[idx]['Combo'].currentText()
            if combo_text != '':
                # combo_text names a column in the imported file whose
                # value varies row by row - storing the column's own name
                # here (rather than a value) is intentional:
                # generate_reports.py's retrieve_distinct/retrieve_avg
                # read it straight back as a column reference into this
                # row's `table_` to fetch the real per-row data for the
                # "advanced" report. Any *other* reader of this row (e.g.
                # CropSimulation._load_variety) must not treat it as a
                # literal value - see that method's own decoding of this
                # same three-way ('c_' prefix / 'None' / column name)
                # convention.
                return check_text(combo_text)
            return f"c_{self.manual_values[idx]['line_edit'].text()}"

        if data_type == 'soil':
            clay = _resolve(0)
            humus = _resolve(1)
            ph = _resolve(2)
            rx = _resolve(3)
            sql = ("INSERT INTO soil.manual"
                   " (date_text, field, clay, humus, ph, rx, table_)"
                   " VALUES (%s, %s, %s, %s, %s, %s, %s)")
            self.db.execute_sql(sql, params=(date_, field, clay, humus, ph, rx, table))
            return True
        crop = self.widget.CBCrop.currentText()
        if data_type == 'plant':
            variety = _resolve(0)
            sql = ("INSERT INTO plant.manual"
                   " (field, crop, date_text, table_, variety)"
                   " VALUES (%s, %s, %s, %s, %s)")
            self.db.execute_sql(sql, params=(field, crop, date_, table, variety))
        elif data_type == 'ferti':
            ensure_ferti_nutrient_column(self.db)
            variety = _resolve(0)
            nutrient = _resolve(1)
            rate = _resolve(2)
            sql = ("INSERT INTO ferti.manual"
                   " (field, crop, table_, date_text, variety, nutrient, rate)"
                   " VALUES (%s, %s, %s, %s, %s, %s, %s)")
            self.db.execute_sql(
                sql, params=(field, crop, table, date_, variety, nutrient, rate))
        elif data_type == 'spray':
            variety = _resolve(0)
            rate = _resolve(1)
            sql = ("INSERT INTO spray.manual"
                   " (field, crop, table_, date_text, variety, rate)"
                   " VALUES (%s, %s, %s, %s, %s, %s)")
            self.db.execute_sql(sql, params=(field, crop, table, date_, variety, rate))
        elif data_type == 'harvest':
            if 0 in self.manual_values.keys():
                yield_ = _resolve(0)
                total_yield = _resolve(1)
            else:
                yield_ = 'yield'
                total_yield = ''
            sql = ("INSERT INTO harvest.manual"
                   " (field, crop, table_, date_text, yield, total_yield)"
                   " VALUES (%s, %s, %s, %s, %s, %s)")
            self.db.execute_sql(sql, params=(field, crop, table, date_, yield_, total_yield))
        else:
            ## Should never happen!
            print('Unkown data source...')
            return False
        return True