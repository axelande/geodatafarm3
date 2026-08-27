"""The "Journal fields" popup: what a farm's own operation journal has to
contain.

Opened from the ⚙ button on the Add-data form (see
widgets/add_data_form.py), and edits exactly one thing - the field list
support_scripts/journal_fields.py keeps in ``public.journal_fields`` for
the operation the user had open. That list drives three places at once:
the manual form's inputs, what the manual save writes, and what the
spray-journal report prints. Editing it here is therefore the only place
a grower needs to go when their documentation requirements change,
whether because a regulator changed them (the template picker) or
because their own sprayer needs something the regulator never asked for
(Add field).

Built directly in Python/Qt rather than a .ui file, same as
widgets/crop_settings_dialog.py.

Structural edits (move, add, remove) re-render the whole table from an
internal list rather than shuffling rows in place: the Type column is a
cell widget, and swapping those around by hand is exactly the sort of
thing that silently leaves a combo box attached to the wrong row.
"""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout)

from ..support_scripts.__init__ import TR
from ..support_scripts import journal_fields as jf

__author__ = 'Axel Horteborn'

_CAPTION_STYLE = 'color: #666666; font-size: 11px;'

# Operations that have a configurable journal, in the order the Add-data
# picker shows them. "Other" is absent on purpose - it builds a fresh
# table per row (GeoDataFarm._save_other_from_form) and has no fixed
# field list to configure.
_OPERATIONS = (
    ('spray', 'Spraying'),
    ('ferti', 'Fertilizing'),
    ('plant', 'Planting'),
    ('harvest', 'Harvest'),
    ('soil', 'Soil sample'),
    ('plowing', 'Plowing'),
    ('harrowing', 'Harrowing'),
)

(_COL_USE, _COL_LABEL, _COL_KEY, _COL_UNIT, _COL_TYPE, _COL_CHOICES,
 _COL_REQ, _COL_REMEMBER) = range(8)


class JournalFieldsDialog(QDialog):
    """Editor for one farm's per-operation journal field list."""

    def __init__(self, db, operation='spray', parent=None):
        super().__init__(parent)
        translate = TR('JournalFieldsDialog')
        self.tr_ = translate.tr
        self.db = db
        self._fields = []
        self._loading = False
        # operation -> edited-but-not-yet-saved field list. Switching
        # operation in the picker parks the current table here rather than
        # writing it, so Save commits every operation the user touched and
        # Cancel really does discard all of it.
        self._pending = {}
        self._current_op = None

        self.setWindowTitle(self.tr_('Journal fields'))
        self.resize(940, 620)
        layout = QVBoxLayout(self)

        intro = QLabel(self.tr_(
            'These are the fields the manual form asks for and the journal '
            'report prints, for this farm. Start from a template that matches '
            'your national requirements, then switch off what you do not need '
            'and add what your own sprayer does.'))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        top = QHBoxLayout()
        top.addWidget(QLabel(self.tr_('Operation:')))
        self.cbOperation = QComboBox()
        for op, label in _OPERATIONS:
            self.cbOperation.addItem(self.tr_(label), op)
        top.addWidget(self.cbOperation)
        top.addSpacing(20)
        top.addWidget(QLabel(self.tr_('Template:')))
        self.cbTemplate = QComboBox()
        for key, label in jf.TEMPLATE_LABELS:
            self.cbTemplate.addItem(self.tr_(label), key)
        top.addWidget(self.cbTemplate, 1)
        self.PBApplyTemplate = QPushButton(self.tr_('Reset to template'))
        top.addWidget(self.PBApplyTemplate)
        layout.addLayout(top)

        template_note = QLabel(self.tr_(
            'Resetting restores that template\'s own fields and ordering. '
            'Fields you added yourself are kept and moved to the end.'))
        template_note.setWordWrap(True)
        template_note.setStyleSheet(_CAPTION_STYLE)
        layout.addWidget(template_note)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            self.tr_('Use'), self.tr_('Field'), self.tr_('Stored as'),
            self.tr_('Unit'), self.tr_('Type'), self.tr_('Choices'),
            self.tr_('Required'), self.tr_('Remember')])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_COL_LABEL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_CHOICES, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        table_note = QLabel(self.tr_(
            'Choices are separated by commas, and an empty one (a leading '
            'comma) is the "not answered yet" entry. "Remember" offers what '
            'you entered before as a drop-down you can still type over. '
            '"Stored as" is the database key - it is fixed once a field has '
            'been used, so renaming a field keeps its history.'))
        table_note.setWordWrap(True)
        table_note.setStyleSheet(_CAPTION_STYLE)
        layout.addWidget(table_note)

        row_btns = QHBoxLayout()
        self.PBUp = QPushButton(self.tr_('▲ Move up'))
        self.PBDown = QPushButton(self.tr_('▼ Move down'))
        self.PBAdd = QPushButton(self.tr_('+ Add field'))
        self.PBRemove = QPushButton(self.tr_('− Remove field'))
        for btn in (self.PBUp, self.PBDown, self.PBAdd, self.PBRemove):
            row_btns.addWidget(btn)
        row_btns.addStretch(1)
        layout.addLayout(row_btns)

        operator_row = QHBoxLayout()
        operator_row.addWidget(QLabel(self.tr_('Default operator:')))
        self.LEOperator = QLineEdit()
        self.LEOperator.setPlaceholderText(self.tr_('Name of whoever usually sprays'))
        operator_row.addWidget(self.LEOperator, 1)
        layout.addLayout(operator_row)

        operator_note = QLabel(self.tr_(
            'Filled in automatically on new entries, together with the place '
            'of application and the treated area, which are both read from '
            'the selected field. You can always type over them.'))
        operator_note.setWordWrap(True)
        operator_note.setStyleSheet(_CAPTION_STYLE)
        layout.addWidget(operator_note)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.PBCancel = QPushButton(self.tr_('Cancel'))
        self.PBSave = QPushButton(self.tr_('Save'))
        self.PBSave.setDefault(True)
        buttons.addWidget(self.PBCancel)
        buttons.addWidget(self.PBSave)
        layout.addLayout(buttons)

        self.cbOperation.currentIndexChanged.connect(self._operation_changed)
        self.PBApplyTemplate.clicked.connect(self._apply_template)
        self.PBUp.clicked.connect(lambda: self._move(-1))
        self.PBDown.clicked.connect(lambda: self._move(1))
        self.PBAdd.clicked.connect(self._add_field)
        self.PBRemove.clicked.connect(self._remove_field)
        self.PBCancel.clicked.connect(self.reject)
        self.PBSave.clicked.connect(self._save)

        idx = self.cbOperation.findData(operation)
        if idx != -1:
            self.cbOperation.setCurrentIndex(idx)
        self.LEOperator.setText(
            jf.get_setting(self.db, jf.DEFAULT_OPERATOR_KEY, '') or '')
        self._load()

    # ---- state -----------------------------------------------------------
    @property
    def operation(self):
        return self.cbOperation.currentData()

    def _operation_changed(self):
        """Switching operation parks the current table in :attr:`_pending`
        instead of dropping it - a user who tidies up spraying, glances at
        fertilizing and then hits Save expects both to have been saved, and
        expects Cancel to have saved neither."""
        if self._loading:
            return
        self._park()
        self._load()

    def _park(self):
        if self._current_op is not None:
            self._pending[self._current_op] = self._read_table()

    def _load(self):
        self._loading = True
        try:
            operation = self.operation
            self._fields = self._pending.get(operation)
            if self._fields is None:
                self._fields = jf.get_fields(self.db, operation, enabled_only=False)
            idx = self.cbTemplate.findData(jf.active_template(self.db, operation))
            if idx != -1:
                self.cbTemplate.setCurrentIndex(idx)
            self._current_op = operation
            self._render()
        finally:
            self._loading = False

    def _apply_template(self):
        template = self.cbTemplate.currentData()
        answer = QMessageBox.question(
            self, self.tr_('Reset to template'),
            self.tr_('Replace the built-in fields for this operation with the '
                     'template\'s? Fields you added yourself are kept.'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        # Written straight through rather than staged in the table: a reset
        # is the one edit where "what you had" is deliberately being thrown
        # away, so leaving it pending until Save would only be confusing.
        self._fields = jf.apply_template(self.db, self.operation, template)
        self._pending.pop(self.operation, None)
        self._render()

    # ---- table -----------------------------------------------------------
    def _render(self):
        self._loading = True
        try:
            self.table.setRowCount(len(self._fields))
            for row, field in enumerate(self._fields):
                self._render_row(row, field)
            self.table.resizeColumnsToContents()
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(_COL_LABEL, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(_COL_CHOICES, QHeaderView.ResizeMode.Stretch)
        finally:
            self._loading = False

    def _render_row(self, row, field):
        self.table.setItem(row, _COL_USE, _check_item(field.enabled))
        self.table.setItem(row, _COL_LABEL, QTableWidgetItem(field.label))
        key_item = QTableWidgetItem(field.key or '')
        key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        key_item.setToolTip(self.tr_(
            'Stored in its own column on the operation table.')
            if field.storage == 'column' else self.tr_(
            'Stored in the row\'s "extra" JSON column.'))
        self.table.setItem(row, _COL_KEY, key_item)
        self.table.setItem(row, _COL_UNIT, QTableWidgetItem(field.unit or ''))
        combo = QComboBox()
        combo.addItems(list(jf.FIELD_TYPES))
        combo.setCurrentText(field.field_type)
        self.table.setCellWidget(row, _COL_TYPE, combo)
        self.table.setItem(row, _COL_CHOICES,
                           QTableWidgetItem(', '.join(field.choices)))
        self.table.setItem(row, _COL_REQ, _check_item(field.required))
        remember = _check_item(field.remember)
        remember.setToolTip(self.tr_(
            'Offer what was entered here before, as a drop-down you can '
            'still type over. Ignored on dates and fixed choice lists, '
            'which already are a shortlist.'))
        self.table.setItem(row, _COL_REMEMBER, remember)

    def _read_table(self):
        """Pulls the table back into :class:`JournalField`s.

        A row the user added has no key yet, so one is derived from its
        label here (:func:`journal_fields.make_key`) - and only here, so
        that renaming an existing field never changes where its values are
        stored and never orphans what has already been recorded under it.

        Tagged with :attr:`_current_op`, not the picker's current value:
        ``_park`` reads the table *after* the picker has already moved on
        to the next operation, and stamping those rows with the new
        operation would file spraying's fields under fertilizing.

        Every row comes back, including one whose label the user has
        blanked - the result is indexed by row number by ``_move`` and
        ``_remove_field``, so dropping rows here would quietly move or
        delete the wrong field. Blank rows are discarded in :meth:`_save`
        instead, which is the only place it matters.
        """
        operation = self._current_op or self.operation
        fields = []
        taken = {f.key for f in self._fields if f.key}
        for row in range(self.table.rowCount()):
            label = _text(self.table.item(row, _COL_LABEL)).strip()
            key = _text(self.table.item(row, _COL_KEY)).strip()
            existing = next((f for f in self._fields if f.key and f.key == key), None)
            if not key:
                key = jf.make_key(label, taken)
                taken.add(key)
            combo = self.table.cellWidget(row, _COL_TYPE)
            choices = [c.strip() for c in _text(self.table.item(row, _COL_CHOICES)).split(',')] \
                if _text(self.table.item(row, _COL_CHOICES)) else []
            fields.append(jf.JournalField(
                operation=operation, key=key, label=label,
                unit=_text(self.table.item(row, _COL_UNIT)).strip() or None,
                field_type=combo.currentText() if combo else jf.TEXT,
                choices=tuple(choices),
                required=_checked(self.table.item(row, _COL_REQ)),
                sort_order=row * 10,
                enabled=_checked(self.table.item(row, _COL_USE)),
                remember=_checked(self.table.item(row, _COL_REMEMBER)),
                builtin=existing.builtin if existing is not None else False))
        return fields

    def _move(self, offset):
        row = self.table.currentRow()
        target = row + offset
        if row < 0 or not 0 <= target < self.table.rowCount():
            return
        self._fields = self._read_table()
        self._fields[row], self._fields[target] = self._fields[target], self._fields[row]
        self._render()
        self.table.setCurrentCell(target, _COL_LABEL)

    def _add_field(self):
        self._fields = self._read_table()
        # No key: _read_table derives one from whatever label the user types.
        self._fields.append(jf.JournalField(
            operation=self.operation, key='', label=self.tr_('New field'),
            builtin=False))
        self._render()
        self.table.setCurrentCell(self.table.rowCount() - 1, _COL_LABEL)
        self.table.editItem(self.table.item(self.table.rowCount() - 1, _COL_LABEL))

    def _remove_field(self):
        row = self.table.currentRow()
        if row < 0:
            return
        field = self._read_table()[row]
        if field.builtin:
            # Removing a built-in field outright would make it come back on
            # the next template reset and, worse, hide values already stored
            # under it. Switching it off leaves both intact.
            QMessageBox.information(
                self, self.tr_('Journal fields'),
                self.tr_('This field comes from the template. Clear its "Use" '
                         'box to hide it instead - that keeps anything already '
                         'recorded in it.'))
            return
        self._fields = self._read_table()
        del self._fields[row]
        self._render()

    # ---- save ------------------------------------------------------------
    def _save(self):
        self._park()
        # A row left without a label is the user abandoning an "Add field"
        # they started - drop it rather than storing a nameless field.
        self._pending = {op: [f for f in fields if f.label.strip()]
                         for op, fields in self._pending.items()}
        for operation, fields in self._pending.items():
            keys = [f.key for f in fields]
            duplicates = {k for k in keys if keys.count(k) > 1}
            if duplicates:
                QMessageBox.warning(
                    self, self.tr_('Journal fields'),
                    self.tr_('Two fields on {op} would be stored under the same '
                             'name: {keys}. Rename one of them.').format(
                                 op=operation, keys=', '.join(sorted(duplicates))))
                return
        for operation, fields in self._pending.items():
            jf.save_fields(self.db, operation, fields)
        jf.set_setting(self.db, jf.DEFAULT_OPERATOR_KEY,
                       self.LEOperator.text().strip() or None)
        self._fields = self._pending.get(self.operation, self._fields)
        self.accept()


def _check_item(checked):
    item = QTableWidgetItem()
    item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                  | Qt.ItemFlag.ItemIsSelectable)
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    return item


def _checked(item):
    return item is not None and item.checkState() == Qt.CheckState.Checked


def _text(item):
    return item.text() if item is not None else ''
