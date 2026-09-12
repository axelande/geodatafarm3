"""The "Find product" popup behind the journal's plant-protection product
field.

Opened from a button beside that field on the Add-data form, and it
fills in two boxes at once: the product name and its registration
number. Those belong together - the number is what identifies the
approval and the name is what is printed on the can - and typing either
by hand is how a transposed digit gets into a journal nobody re-reads
until an inspection.

Built directly in Python/Qt rather than a .ui file, same as
widgets/journal_fields_dialog.py.

Why it is a search box rather than a drop-down: the Swedish register
holds around 1700 registrations under 1900 names. The form's own
``purpose`` answer - already given, a few fields up - cuts that to a few
hundred before the user types anything, and a couple of letters does the
rest. A list that long is not something to scroll.
"""
from html import escape

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QTextBrowser, QVBoxLayout)

from ..support_scripts.__init__ import TR
from ..support_scripts import pesticide_client as pc

__author__ = 'Axel Horteborn'

_CAPTION_STYLE = 'color: #666666; font-size: 11px;'

# How long to wait after the last keystroke before searching. Long enough
# that typing a product name is one request rather than eight, short
# enough that the list feels like it is following along.
_DEBOUNCE_MS = 300

# Statuses offered in the picker, as (wire value, label). '' means the
# server's own default - what may still be sprayed today - which is the
# right default for a form being filled in now. Everything else has to be
# asked for, because a withdrawn product is usually a mistake and
# occasionally exactly what you are looking for.
_STATUS_CHOICES = (
    ('', 'Usable today'),
    ('any', 'Including withdrawn'),
)


class PesticideSearchDialog(QDialog):
    """Search the plant-protection register and return one product."""

    def __init__(self, country, purpose='', language='en', parent=None,
                 client=None):
        super().__init__(parent)
        translate = TR('PesticideSearchDialog')
        self.tr_ = translate.tr
        self.country = country
        self.language = language
        self.client = client or pc.PesticideClient()
        self.selected = None
        self._results = []

        self.setWindowTitle(self.tr_('Find plant protection product'))
        self.resize(760, 520)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel(self.tr_('Search:')))
        self.LESearch = QLineEdit()
        self.LESearch.setPlaceholderText(
            self.tr_('Product name or registration number'))
        top.addWidget(self.LESearch, 1)
        top.addWidget(QLabel(self.tr_('Purpose:')))
        self.cbPurpose = QComboBox()
        top.addWidget(self.cbPurpose)
        top.addWidget(QLabel(self.tr_('Show:')))
        self.cbStatus = QComboBox()
        for value, label in _STATUS_CHOICES:
            self.cbStatus.addItem(self.tr_(label), value)
        top.addWidget(self.cbStatus)
        layout.addLayout(top)

        self.results = QListWidget()
        self.results.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.results, 2)

        # What the register knows about the highlighted product, shown
        # before it is committed to the journal. The list can only carry a
        # name and a date; the decision needs the approved uses, the
        # active substance and who is allowed to apply it.
        # A QTextBrowser rather than a QTextEdit so the decision attachment
        # is a link that opens: the conditions of use are read out of a PDF,
        # and the PDF is the thing that governs when a row is unclear.
        self.details = QTextBrowser()
        self.details.setReadOnly(True)
        self.details.setOpenExternalLinks(True)
        self.details.setPlaceholderText(
            self.tr_('Select a product to see what the register holds for it.'))
        layout.addWidget(self.details, 1)
        # Conditions already fetched this session, by registration number.
        # Selecting the same hit twice, or two names of one registration,
        # must not cost two requests.
        self._conditions = {}

        self.LStatus = QLabel()
        self.LStatus.setWordWrap(True)
        self.LStatus.setStyleSheet(_CAPTION_STYLE)
        layout.addWidget(self.LStatus)

        # The register's own words, carrying the export date and the fact
        # that the label on the package governs. From the server, so the
        # date is the one actually searched.
        self.LDisclosure = QLabel()
        self.LDisclosure.setWordWrap(True)
        self.LDisclosure.setStyleSheet(_CAPTION_STYLE)
        layout.addWidget(self.LDisclosure)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.PBCancel = QPushButton(self.tr_('Cancel'))
        self.PBUse = QPushButton(self.tr_('Use this product'))
        self.PBUse.setDefault(True)
        self.PBUse.setEnabled(False)
        buttons.addWidget(self.PBCancel)
        buttons.addWidget(self.PBUse)
        layout.addLayout(buttons)

        # One timer restarted on every keystroke, so a burst of typing
        # costs one request.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_DEBOUNCE_MS)
        self._timer.timeout.connect(self.search)

        self.LESearch.textChanged.connect(lambda _: self._timer.start())
        self.cbPurpose.currentIndexChanged.connect(self.search)
        self.cbStatus.currentIndexChanged.connect(self.search)
        self.results.itemSelectionChanged.connect(self._selection_changed)
        self.results.itemDoubleClicked.connect(lambda _: self._use())
        self.PBCancel.clicked.connect(self.reject)
        self.PBUse.clicked.connect(self._use)

        self._fill_purposes(purpose)
        self.search()

    # ---- setup -----------------------------------------------------------
    def _fill_purposes(self, purpose):
        """Purposes come from the server, not from this build.

        The journal's own choices and the register's are the same
        vocabulary today, but a build offering one the server has stopped
        honouring would silently return nothing - the same reason
        /api/hjalpredan exists.
        """
        self.cbPurpose.addItem(self.tr_('Any'), '')
        try:
            options = self.client.options()
        except pc.PesticideUnavailable:
            # Not fatal, and not worth a message here: the search itself
            # is about to fail too and will say so once.
            options = {}
        for value in options.get('purposes') or []:
            self.cbPurpose.addItem(self.tr_(value), value)
        if purpose and purpose not in pc.UNFILTERED_PURPOSES:
            index = self.cbPurpose.findData(purpose)
            if index != -1:
                self.cbPurpose.setCurrentIndex(index)

    # ---- searching -------------------------------------------------------
    def search(self):
        self._timer.stop()
        try:
            payload = self.client.search(
                self.country,
                query=self.LESearch.text().strip(),
                purpose=self.cbPurpose.currentData() or '',
                status=self.cbStatus.currentData() or '')
        except pc.PesticideUnavailable as e:
            self._results = []
            self.results.clear()
            self.LStatus.setText(str(e))
            self.PBUse.setEnabled(False)
            return
        self._show(payload)

    def _show(self, payload):
        self._results = payload.get('products') or []
        self.results.clear()
        for product in self._results:
            item = QListWidgetItem(self._line(product))
            if not product.get('usable', True):
                # Greyed rather than hidden: a journal entry being read
                # back may name a product withdrawn years ago, and that
                # entry was correct when it was written.
                item.setForeground(Qt.GlobalColor.gray)
            self.results.addItem(item)
        self.LDisclosure.setText(pc.disclosure_line(payload, self.language))
        self.LStatus.setText(self._summary(payload))
        self.PBUse.setEnabled(False)
        # A stale panel under a fresh list would describe a product that is
        # no longer in it.
        self.details.setHtml('')

    def _line(self, product):
        parts = [pc.describe(product)]
        validity = pc.validity(product)
        if validity:
            parts.append(self.tr_(validity))
        others = product.get('other_names') or []
        if others:
            # The same approval is sold under as many as seven names, and
            # the one in the shed may not be the one listed first.
            names = ', '.join(entry.get('name', '') for entry in others)
            parts.append(self.tr_('also sold as {}').format(names))
        return '  ·  '.join(part for part in parts if part)

    def _summary(self, payload):
        count = payload.get('count', 0)
        if not payload.get('supported', True):
            return self.tr_('No product register for this country yet.')
        if not count:
            return self.tr_('Nothing matched. Try fewer letters, or allow '
                            'withdrawn products.')
        if payload.get('truncated'):
            return self.tr_('{} shown - narrow the search to see the rest.').format(count)
        return self.tr_('{} found.').format(count)

    # ---- choosing --------------------------------------------------------
    def _selection_changed(self):
        product = self.current_product()
        self.PBUse.setEnabled(product is not None)
        self.details.setHtml(
            self._details_html(product, self._conditions_for(product)))

    def _conditions_for(self, product):
        """The conditions of use behind the highlighted product, or None.

        None on any failure, and quietly: the register lookup this sits
        under has already succeeded, and a product without a fetched
        decision is still the right product to pick. Cached per
        registration number for the life of the dialog.
        """
        if product is None:
            return None
        number = product.get('registration_number')
        if not number:
            return None
        if number not in self._conditions:
            try:
                self._conditions[number] = self.client.conditions(number)
            except pc.PesticideUnavailable:
                self._conditions[number] = None
        return self._conditions[number]

    def _details_html(self, product, conditions=None):
        """The record as a small table, the decision's approved uses under
        it. Escaped, because every value here is a product name or a use
        description from an external register, and one containing an
        ampersand should not become markup. The one link is the decision
        attachment, and it is the only value rendered as one."""
        rows = pc.details(product) + pc.conditions_rows(conditions, self.language)
        if not rows:
            return ''
        cells = []
        for label, value in rows:
            if value.startswith('https://'):
                shown = f'<a href="{escape(value)}">{escape(value)}</a>'
            else:
                shown = escape(value).replace(chr(10), '<br>')
            cells.append(
                '<tr>'
                f'<td style="color:#666;padding-right:10px;vertical-align:top;'
                f'white-space:nowrap;">{escape(self.tr_(label))}</td>'
                f'<td>{shown}</td>'
                '</tr>')
        return f'<table>{"".join(cells)}</table>'

    def current_product(self):
        row = self.results.currentRow()
        return self._results[row] if 0 <= row < len(self._results) else None

    def _use(self):
        product = self.current_product()
        if product is None:
            return
        self.selected = product
        self.accept()
