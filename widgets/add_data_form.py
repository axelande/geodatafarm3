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
        schema="ferti", import_columns=["Variety", "Nutrient", "Rate", "Depth"],
        file_types=[TEXT, ISO, SHP, DBF, RAS],
        fields=[("Variety", "variety", None), ("Nutrient", "nutrient", None),
                ("Rate", "rate", "kg/ha"), ("Sowing depth", "saw_depth", "cm")]),
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
    # Weather: clicking the card opens the free Open-Meteo import window
    # (plus the Pro license key section) - see import_data/handle_weather.py.
    "opWeather": dict(title="🌦️  Weather", op="weather", needs_crop=False,
                      picker_action=True, file_types=[], fields=[]),
}

# db_column -> fixed choice list, for manual fields that render as a
# QComboBox instead of free text. Currently just fertilizing's nutrient type
# (see ferti.manual.nutrient, database_scripts.db.ensure_ferti_nutrient_column).
# Only used for the static OPERATIONS fallback below - a field list coming
# from the database carries its own choices.
FIELD_CHOICES = {"nutrient": ["N", "P", "K", "Mg", "S", "Na"]}

# Field types this form knows how to render. Same spellings as
# support_scripts.journal_fields, but repeated rather than imported: that
# module pulls in psycopg2, and this widget has to stay runnable on its own
# (see _main() at the bottom, and the standalone tests that build the form
# without a database).
TEXT, NUMBER, CHOICE, DATE, BOOL = "text", "number", "choice", "date", "bool"

# The sentinel a DATE field uses for "not filled in". A QDateEdit always
# holds *some* date, so an empty journal field needs a value that means
# blank; pairing the minimum date with an empty specialValueText makes the
# widget render it as an empty box, the way the paper form does.
_EMPTY_DATE = QtCore.QDate(1900, 1, 1)


class FieldSpec:
    """One manual field to render: what a journal field looks like to this
    widget.

    Deliberately not support_scripts.journal_fields.JournalField - the form
    needs a label, a key, a unit, a type and a choice list, and nothing
    about where the value is stored or whether it came from a template.
    Keeping the widget's own tiny type here is what lets it run without a
    database connection.
    """

    __slots__ = ("label", "key", "unit", "field_type", "choices", "required",
                 "suggestions")

    def __init__(self, label, key, unit=None, field_type=TEXT, choices=(),
                 required=False, suggestions=()):
        self.label = label
        self.key = key
        self.unit = unit or None
        self.field_type = field_type
        self.choices = tuple(choices)
        self.required = bool(required)
        # What has been entered in this field before, most recent first.
        # Unlike `choices` these are a shortcut, not a restriction - the
        # widget stays typeable, so a one-off value is never blocked by
        # what the history happens to hold.
        self.suggestions = tuple(suggestions)


def _normalise_number(text):
    """Turns a decimal comma into a decimal point on NUMBER fields.

    Everything here is stored as text, and a Swedish keyboard produces
    "2,5" - which every downstream ``float()`` (the crop simulation, the
    fertilizer-timing model, the journal report) then chokes on. Only
    applied when the result actually parses as a number, so free-form
    entries like "2,5 l/ha per pass" are left exactly as typed.
    """
    swapped = text.replace(",", ".")
    try:
        float(swapped)
    except ValueError:
        return text
    return swapped


def specs_from_config(fields):
    """Turns OPERATIONS' ``(label, db_column, unit)`` tuples into
    :class:`FieldSpec`s - the fallback used when no field provider is set
    (standalone runs, and any farm whose database isn't reachable)."""
    specs = []
    for label, key, unit in fields:
        if key in FIELD_CHOICES:
            specs.append(FieldSpec(label, key, unit, CHOICE, FIELD_CHOICES[key]))
        else:
            specs.append(FieldSpec(label, key, unit))
    return specs


class AddDataForm(QtWidgets.QWidget):
    """Embeddable widget: operation picker -> one reusable form."""

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(UI_PATH, self)

        self.config = None            # config dict of the open operation
        self.operation = None         # op id of the open operation, e.g. "plant"
        self._edits = {}              # field key -> the widget holding its value
        self._specs = {}              # field key -> FieldSpec, for values()/clear()
        self._notes = None            # QPlainTextEdit for the "other" column
        self.save_callback = None     # set by GeoDataFarm: called on Save
        self.import_callback = None   # set by GeoDataFarm: called on Choose file
        self.picker_action_callback = None  # for ops that act on card click (Irrigation)
        # Returns the configured FieldSpec list for an operation, or None to
        # fall back to OPERATIONS' static list. Set by GeoDataFarm, which
        # reads it from support_scripts.journal_fields.
        self.field_provider = None
        # Opens the journal-field settings dialog. The ⚙ button stays hidden
        # until this is set, so a standalone form has no dead button.
        self.journal_settings_callback = None
        # Called with the selected field name whenever it changes, so derived
        # journal values (place of application, treated area) can be filled
        # in - see GeoDataFarm._autofill_add_data_form.
        self.field_changed_callback = None
        # field key -> (button text, callback). Puts a button beside that
        # field's input, for a value that can be worked out rather than
        # typed - the Hjälpredan's adapted buffer distance being the case
        # this exists for. Kept as a plain dict so the widget knows nothing
        # about what any particular button does.
        self.field_actions = {}
        # Called with (field key, value) whenever a choice or checkbox
        # changes, so one journal field can fill in another - picking the
        # object behind a fixed buffer zone fixes its distance in law.
        self.value_changed_callback = None

        self._add_settings_button()
        self._wire()
        self.show_picker()

    def _add_settings_button(self):
        """Adds the ⚙ button next to the form title. Built here rather than
        in add_data_form.ui for the same reason the Add-data page itself is
        dropped into an empty .ui placeholder (see GeoDataFarm.set_buttons):
        it keeps the hand-edited .ui free of widgets whose visibility depends
        on runtime wiring."""
        self.btnJournalFields = QtWidgets.QPushButton("⚙  Journal fields")
        self.btnJournalFields.setVisible(False)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.btnJournalFields)
        row.addStretch(1)
        layout = getattr(self, "formLayout", None) or self.findChild(
            QtWidgets.QVBoxLayout, "formLayout")
        # Index 2 == straight below formTitle (backBtn, formTitle, ...).
        layout.insertLayout(2, row)

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
        self.btnJournalFields.clicked.connect(self._open_journal_settings)
        self.cbField.currentTextChanged.connect(self._field_changed)

    def _open_journal_settings(self):
        if not self.journal_settings_callback:
            return
        self.journal_settings_callback(self.operation)
        # The dialog may have changed the very field list on screen, so
        # rebuild it - otherwise the user has to leave the operation and come
        # back to see the fields they just configured.
        self.refresh_fields()

    def refresh_fields(self):
        """Rebuilds the manual inputs from the current configuration.

        Called after the settings dialog closes and after a save: the
        history lists are read when the fields are built (see FieldSpec.
        suggestions), so without this the operator you just entered would
        not be offered until you left the operation and came back.

        The panel height goes with it - a national template runs to
        twenty-odd fields where the built-in list had four, and a height
        pinned for the old list leaves the new fields below the fold.
        """
        if self.config is None:
            return
        specs = self._field_specs(self.config)
        self._build_manual_fields(specs)
        self.inputStack.setMinimumHeight(
            max(260 + len(specs) * 42,
                80 + len(self.config.get("file_types", [])) * 42))

    def _field_changed(self, field_name):
        if self.field_changed_callback and self.operation:
            self.field_changed_callback(self.operation, field_name)

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
        specs = self._field_specs(cfg)
        self._build_manual_fields(specs)
        # The ⚙ button configures the journal field list, which only the
        # table-backed operations have; "Other" builds its own table per row
        # (GeoDataFarm._save_other_from_form) and has nothing to configure.
        self.btnJournalFields.setVisible(
            bool(self.journal_settings_callback) and not cfg.get("custom_save"))
        # Pin a min height that fits whichever panel (manual is usually taller).
        self.inputStack.setMinimumHeight(
            max(260 + len(specs) * 42, 80 + len(file_types) * 42))

        if has_file:
            self.segFile.setChecked(True)
            self.inputStack.setCurrentIndex(0)
        else:
            self.segManual.setChecked(True)
            self.inputStack.setCurrentIndex(1)
        self.addStack.setCurrentIndex(1)

    def _field_specs(self, cfg):
        """The field list to render for ``cfg``'s operation: the farm's own
        configured journal fields when a provider is set, otherwise the
        static OPERATIONS list.

        The fallback is not just for standalone runs - if the journal-field
        lookup fails for any reason, showing the fields this form has always
        shown is far better than showing none at all."""
        if self.field_provider:
            specs = self.field_provider(cfg["op"])
            if specs:
                return list(specs)
        return specs_from_config(cfg["fields"])

    def _build_manual_fields(self, specs):
        form = self.manualForm
        form.setVerticalSpacing(10)
        while form.rowCount():
            form.removeRow(0)
        self._edits = {}
        self._specs = {}
        for spec in specs:
            edit = self._widget_for(spec)
            edit.setMinimumHeight(30)
            self._edits[spec.key] = edit
            self._specs[spec.key] = spec
            # A required field is marked the way a paper form does, rather
            # than only complaining on Save - the point of a national
            # template is to show what the journal must contain up front.
            label = f"{spec.label} *:" if spec.required else f"{spec.label}:"
            action = self.field_actions.get(spec.key)
            if spec.unit or action:
                cell = QtWidgets.QWidget()
                row = QtWidgets.QHBoxLayout(cell)
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(edit, 1)
                if spec.unit:
                    row.addWidget(QtWidgets.QLabel(spec.unit))
                if action:
                    text, callback = action
                    button = QtWidgets.QPushButton(text)
                    button.clicked.connect(lambda _=False, cb=callback: cb())
                    row.addWidget(button)
                form.addRow(label, cell)
            else:
                form.addRow(label, edit)
            self._connect_value_changed(spec.key, edit)
        self._notes = QtWidgets.QPlainTextEdit()
        self._notes.setPlaceholderText("Other comments…")
        self._notes.setMaximumHeight(70)
        form.addRow("Notes:", self._notes)

    def _connect_value_changed(self, key, edit):
        """Reports a changed choice or checkbox to value_changed_callback.

        Only those two: a line edit fires on every keystroke, and a
        callback that reacts to a half-typed value would be filling other
        fields in from something the user has not finished writing.
        """
        if isinstance(edit, QtWidgets.QComboBox):
            edit.currentTextChanged.connect(
                lambda text, k=key: self._value_changed(k, text))
        elif isinstance(edit, QtWidgets.QCheckBox):
            edit.toggled.connect(
                lambda checked, k=key: self._value_changed(k, checked))

    def _value_changed(self, key, value):
        if self.value_changed_callback:
            self.value_changed_callback(key, value)

    @staticmethod
    def _widget_for(spec):
        """The input widget a field type gets. Unknown types fall back to a
        plain line edit: a field list comes from the database and may name a
        type this version of the plugin doesn't know, and free text can hold
        any of them."""
        if spec.field_type == CHOICE and spec.choices:
            edit = QtWidgets.QComboBox()
            edit.addItems(list(spec.choices))
            return edit
        if spec.suggestions:
            # Editable, so this offers past entries without ever becoming a
            # restriction - a new operator or an unusual pressure is typed
            # straight in. The blank leading item is what makes the field
            # start empty rather than silently pre-filled with the last
            # value, which would put a wrong entry in the journal for
            # anyone who tabbed past it.
            edit = QtWidgets.QComboBox()
            edit.setEditable(True)
            edit.addItem("")
            edit.addItems(list(spec.suggestions))
            edit.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
            completer = edit.completer()
            if completer is not None:
                completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
                completer.setCompletionMode(
                    QtWidgets.QCompleter.CompletionMode.PopupCompletion)
            return edit
        if spec.field_type == DATE:
            edit = QtWidgets.QDateEdit()
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
            edit.setMinimumDate(_EMPTY_DATE)
            edit.setSpecialValueText(" ")
            edit.setDate(_EMPTY_DATE)
            return edit
        if spec.field_type == BOOL:
            return QtWidgets.QCheckBox()
        return QtWidgets.QLineEdit()

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
        for key, edit in self._edits.items():
            vals[key] = self._value_of(key, edit)
        return vals

    def _value_of(self, key, edit):
        """One widget's value, normalised to text or None."""
        if isinstance(edit, QtWidgets.QDateEdit):
            date = edit.date()
            return None if date == _EMPTY_DATE else date.toString("yyyy-MM-dd")
        if isinstance(edit, QtWidgets.QCheckBox):
            return "Yes" if edit.isChecked() else None
        if isinstance(edit, QtWidgets.QComboBox):
            # Both the fixed CHOICE lists and the editable history ones. A
            # CHOICE list may start with an empty entry meaning "not
            # answered" (see journal_fields._YES_NO), and a history list
            # always does, so an empty selection has to read as blank or a
            # required check would pass on an unanswered field.
            text = edit.currentText().strip() or None
        else:
            text = edit.text() or None
        spec = self._specs.get(key)
        if text and spec is not None and spec.field_type == NUMBER:
            text = _normalise_number(text)
        return text

    def set_value(self, key, value, only_if_empty=True):
        """Fills one field in from outside the form (see
        GeoDataFarm._autofill_add_data_form).

        ``only_if_empty`` by default: a derived value is a convenience, and
        overwriting something the user typed - because they changed the
        field selection after filling the form in - would be worse than not
        filling it in at all.
        """
        edit = self._edits.get(key)
        if edit is None or value in ("", None):
            return
        if only_if_empty and self._value_of(key, edit) is not None:
            return
        if isinstance(edit, QtWidgets.QComboBox):
            idx = edit.findText(str(value))
            if idx != -1:
                edit.setCurrentIndex(idx)
            elif edit.isEditable():
                # A derived value the history has never seen - the treated
                # area of a field sprayed for the first time, say. An
                # editable list can still show it; a fixed one can't, and
                # silently picking the nearest entry would be worse than
                # leaving it blank.
                edit.setEditText(str(value))
        elif isinstance(edit, QtWidgets.QDateEdit):
            edit.setDate(QtCore.QDate.fromString(str(value), "yyyy-MM-dd"))
        elif isinstance(edit, QtWidgets.QCheckBox):
            edit.setChecked(str(value).lower() in ("yes", "true", "1"))
        else:
            edit.setText(str(value))

    def clear(self):
        if self.cbField.count():
            self.cbField.setCurrentIndex(0)
        if self.cbCrop.count():
            self.cbCrop.setCurrentIndex(0)
        for edit in self._edits.values():
            if isinstance(edit, QtWidgets.QComboBox):
                edit.setCurrentIndex(0)
            elif isinstance(edit, QtWidgets.QDateEdit):
                edit.setDate(_EMPTY_DATE)
            elif isinstance(edit, QtWidgets.QCheckBox):
                edit.setChecked(False)
            else:
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
