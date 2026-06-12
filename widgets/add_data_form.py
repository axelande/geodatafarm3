# -*- coding: utf-8 -*-
"""
Shared, config-driven "Add data" form.

One form replaces the nine per-operation panels in the old Import-data tabs.
The structure lives in ``add_data_form.ui``; this controller fills the manual
fields per operation and exposes a small values API (keyed by DB column name).

It is UI-only: the actual save and file-import are handled by callbacks that
GeoDataFarm sets (``save_callback`` / ``import_callback``), reading this form's
``config`` and ``values()``. That keeps all DB logic in one place.

Designed to be embedded as a page in the dock, or run standalone for review.
"""
import os

from qgis.PyQt import QtCore, QtWidgets, uic

UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "add_data_form.ui")

# File-type entries are (stable_key, display_label). Dispatch is on the key, so
# it never depends on the (possibly translated) label.
TEXT = ("text", "Text file (.csv; .txt)")
ISO = ("iso", "ISO BIN/XML (.xml + .bin)")
SHP = ("shp", "Shape file (.shp)")
DBF = ("db", "Database file (.db)")
RAS = ("raster", "Georeferenced raster (.tif; .geotif)")

# Per-operation config.
#   key           : the picker button's objectName
#   op            : short operation id
#   needs_crop    : whether the Crop selector is shown / saved
#   table         : target table for the manual INSERT
#   table_none    : append a literal table_='None' column (matches old SQL)
#   schema        : schema id passed to the file importers
#   shp_schema    : override schema id for shapefile import (else `schema`)
#   import_columns: expected column labels handed to the importers
#   file_types    : list of (key, label); empty => manual entry only
#   fields        : (label, db_column, unit_or_None) - db_column is the values() key
#   special       : handled elsewhere for now (Other/Irrigation)
OPERATIONS = {
    "opPlanting": dict(
        title="🌱  Planting", op="plant", needs_crop=True,
        table="plant.manual", table_none=True,
        schema="plant", shp_schema="planting", import_columns=["Variety"],
        file_types=[TEXT, ISO, SHP, DBF, RAS],
        fields=[("Variety", "variety", None), ("Seed rate", "seed_rate", "kg/ha"),
                ("Spacing", "spacing", "cm"), ("Sowing depth", "saw_depth", "cm")]),
    "opFertilizing": dict(
        title="🧪  Fertilizing", op="ferti", needs_crop=True,
        table="ferti.manual", table_none=True,
        schema="ferti", import_columns=["Variety", "Rate", "Depth"],
        file_types=[TEXT, ISO, SHP, DBF, RAS],
        fields=[("Variety", "variety", None), ("Rate", "rate", "kg/ha"),
                ("Sowing depth", "saw_depth", "cm")]),
    "opSpraying": dict(
        title="💧  Spraying", op="spray", needs_crop=True,
        table="spray.manual", table_none=True,
        schema="spray", shp_schema="spraying", import_columns=["Variety", "Rate", "Depth"],
        file_types=[TEXT, ISO, SHP, DBF, RAS],
        fields=[("Variety", "variety", None), ("Rate", "rate", "kg/ha"),
                ("Wind speed", "wind_speed", "m/s"), ("Wind direction", "wind_dir", "deg")]),
    "opHarvest": dict(
        title="🌾  Harvest", op="harvest", needs_crop=True,
        table="harvest.manual", table_none=True,
        schema="harvest", import_columns=["Yield", "Total yield"],
        file_types=[TEXT, ISO, SHP, DBF],
        fields=[("Yield", "yield", "kg/ha"), ("Total yield", "total_yield", "tonnes")]),
    "opPlowing": dict(
        title="🚜  Plowing", op="plowing", needs_crop=False,
        table="other.plowing_manual", table_none=False,
        file_types=[],
        fields=[("Depth", "depth", "cm")]),
    "opHarrowing": dict(
        title="🌿  Harrowing", op="harrowing", needs_crop=False,
        table="other.harrowing_manual", table_none=False,
        file_types=[],
        fields=[("Depth", "depth", "cm")]),
    "opSoil": dict(
        title="🪨  Soil sample", op="soil", needs_crop=False,
        table="soil.manual", table_none=True,
        schema="soil", import_columns=["Clay", "Humus", "pH", "rx"],
        file_types=[TEXT, SHP, DBF, RAS],
        fields=[("Clay", "clay", "%"), ("Humus", "humus", "%"),
                ("pH (0-14)", "ph", None), ("Average Rx", "rx", None)]),
    # Other: custom dynamic-table save (GeoDataFarm._save_other_from_form).
    "opOther": dict(
        title="➕  Other", op="other", needs_crop=True, custom_save="other",
        file_types=[],
        fields=[("Name", "other_name", None),
                ("Option 1", "opt1", None), ("Unit 1", "unit1", None), ("Value 1", "val1", None),
                ("Option 2", "opt2", None), ("Unit 2", "unit2", None), ("Value 2", "val2", None),
                ("Option 3", "opt3", None), ("Unit 3", "unit3", None), ("Value 3", "val3", None),
                ("Option 4", "opt4", None), ("Unit 4", "unit4", None), ("Value 4", "val4", None)]),
    # Irrigation: clicking the card opens the Raindancer window (no manual form yet).
    "opIrrigation": dict(title="💦  Irrigation", op="irrigation", needs_crop=False,
                         picker_action=True, file_types=[], fields=[]),
}


class AddDataForm(QtWidgets.QWidget):
    """Embeddable widget: operation picker -> one reusable form."""

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(UI_PATH, self)

        self.config = None            # config dict of the open operation
        self.operation = None         # op id of the open operation, e.g. "plant"
        self._edits = {}              # db_column -> QLineEdit
        self._notes = None            # QPlainTextEdit for the "other" column
        self.save_callback = None     # set by GeoDataFarm: called on Save
        self.import_callback = None   # set by GeoDataFarm: called on Choose file
        self.picker_action_callback = None  # for ops that act on card click (Irrigation)

        self._wire()
        self.show_picker()

    # ---- wiring -----------------------------------------------------------
    def _wire(self):
        for obj_name in OPERATIONS:
            getattr(self, obj_name).clicked.connect(
                lambda _=False, n=obj_name: self._open(n))
        self.backBtn.clicked.connect(self.show_picker)

        group = QtWidgets.QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.segFile)
        group.addButton(self.segManual)
        self.segFile.clicked.connect(lambda: self.inputStack.setCurrentIndex(0))
        self.segManual.clicked.connect(lambda: self.inputStack.setCurrentIndex(1))

        self.btnSave.clicked.connect(
            lambda: self.save_callback() if self.save_callback else None)

    # ---- navigation -------------------------------------------------------
    def show_picker(self):
        self.addStack.setCurrentIndex(0)

    def _open(self, obj_name):
        cfg = OPERATIONS[obj_name]
        if cfg.get("picker_action"):
            # No form - the card itself triggers an action (e.g. open Raindancer).
            if self.picker_action_callback:
                self.picker_action_callback(cfg["op"])
            return
        self.config = cfg
        self.operation = cfg["op"]
        self.formTitle.setText(cfg["title"])
        self.lblCrop.setVisible(cfg["needs_crop"])
        self.cbCrop.setVisible(cfg["needs_crop"])

        file_types = cfg.get("file_types", [])
        self._build_file_buttons(file_types)
        has_file = bool(file_types)
        self.howLabel.setVisible(has_file)
        self.segFile.setVisible(has_file)
        self.segManual.setVisible(has_file)

        self.dateWhen.setDate(QtCore.QDate.currentDate())
        self._build_manual_fields(cfg["fields"])
        # Pin a min height that fits whichever panel (manual is usually taller).
        self.inputStack.setMinimumHeight(
            max(260 + len(cfg["fields"]) * 42, 80 + len(file_types) * 42))

        if has_file:
            self.segFile.setChecked(True)
            self.inputStack.setCurrentIndex(0)
        else:
            self.segManual.setChecked(True)
            self.inputStack.setCurrentIndex(1)
        self.addStack.setCurrentIndex(1)

    def _build_manual_fields(self, fields):
        form = self.manualForm
        form.setVerticalSpacing(10)
        while form.rowCount():
            form.removeRow(0)
        self._edits = {}
        for label, db_col, unit in fields:
            edit = QtWidgets.QLineEdit()
            edit.setMinimumHeight(30)
            self._edits[db_col] = edit
            if unit:
                cell = QtWidgets.QWidget()
                row = QtWidgets.QHBoxLayout(cell)
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(edit, 1)
                row.addWidget(QtWidgets.QLabel(unit))
                form.addRow(f"{label}:", cell)
            else:
                form.addRow(f"{label}:", edit)
        self._notes = QtWidgets.QPlainTextEdit()
        self._notes.setPlaceholderText("Other comments…")
        self._notes.setMaximumHeight(70)
        form.addRow("Notes:", self._notes)

    def _build_file_buttons(self, file_types):
        """Populate the file panel with one labelled button per file type."""
        self._clear_layout(self.fileButtonsLayout)
        for key, label in file_types:
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(label))
            row.addStretch(1)
            btn = QtWidgets.QPushButton("Choose file…")
            btn.clicked.connect(lambda _=False, k=key: self._do_import(k))
            row.addWidget(btn)
            self.fileButtonsLayout.addLayout(row)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _do_import(self, key):
        if self.import_callback:
            self.import_callback(key)

    # ---- values API (consumed by the save callback) ----------------------
    def values(self):
        """Return the current form values keyed by DB column name.

        Empty text fields come back as ``None`` (matches the old handlers).
        """
        vals = {
            "field": self.cbField.currentText(),
            "date": self.dateWhen.date().toString("yyyy-MM-dd"),
            "other": self._notes.toPlainText() if self._notes else "",
        }
        vals["other"] = vals["other"] or None
        if self.config and self.config["needs_crop"]:
            vals["crop"] = self.cbCrop.currentText()
        for db_col, edit in self._edits.items():
            vals[db_col] = edit.text() or None
        return vals

    def clear(self):
        if self.cbField.count():
            self.cbField.setCurrentIndex(0)
        if self.cbCrop.count():
            self.cbCrop.setCurrentIndex(0)
        for edit in self._edits.values():
            edit.setText("")
        if self._notes:
            self._notes.setPlainText("")


def _main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = AddDataForm()
    w.resize(820, 640)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _main()
