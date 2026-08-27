"""Small controller widget for building a field fertility-index preview."""
from psycopg2 import sql as pgsql
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtWidgets import (QComboBox, QFormLayout, QLabel, QLineEdit,
                                 QListWidget, QListWidgetItem, QPushButton,
                                 QSpinBox, QVBoxLayout, QWidget)
from qgis.core import (QgsFeature, QgsField, QgsGeometry, QgsProject,
                       QgsRendererCategory, QgsSymbol, QgsVectorLayer,
                       QgsCategorizedSymbolRenderer)
from qgis.PyQt.QtGui import QColor

from ..database_scripts.fertility_index_service import calculate_fertility_index


class FertilityIndexPage(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.field = QComboBox()
        self.harvest = QListWidget()
        self.harvest.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.soil = QComboBox()
        self.classes = QSpinBox()
        self.classes.setRange(2, 10)
        self.classes.setValue(5)
        self.boundaries = QLineEdit('20, 40, 60, 80')
        self.status = QLabel()
        self.result = None
        self.layer = None
        form = QFormLayout()
        form.addRow('Field', self.field)
        form.addRow('Harvest sources (select one or more)', self.harvest)
        form.addRow('Soil source', self.soil)
        form.addRow('Number of classes', self.classes)
        form.addRow('Class boundaries (0-100)', self.boundaries)
        self.calculate = QPushButton('Calculate fertility index')
        self.show_index = QPushButton('Show index')
        self.show_index.setEnabled(False)
        self.create_shape_guide = QPushButton('Create shape guide')
        self.create_shape_guide.setEnabled(False)
        self.create_isoxml = QPushButton('Create ISO-XML guide')
        self.create_isoxml.setEnabled(False)
        self.calculate.clicked.connect(self.calculate_index)
        self.show_index.clicked.connect(self.show_index_layer)
        self.create_shape_guide.clicked.connect(
            lambda: self.open_guide('shp'))
        self.create_isoxml.clicked.connect(
            lambda: self.open_guide('iso'))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('<h2>Fertility index</h2>'))
        layout.addWidget(QLabel('Combine yield and soil data into adjustable field zones.'))
        layout.addLayout(form)
        layout.addWidget(self.calculate)
        layout.addWidget(self.show_index)
        layout.addWidget(self.create_shape_guide)
        layout.addWidget(self.create_isoxml)
        layout.addWidget(self.status)
        self.field.currentIndexChanged.connect(self.reload_sources)
        self.reload()

    def reload(self):
        self.field.clear()
        fields = self.parent.db.execute_and_return(
            'SELECT field_name FROM fields ORDER BY field_name')
        self.field.addItems([row[0] for row in fields if row[0]])
        self.reload_sources()

    def _get_tables_for_field(self, schema, field_name):
        """Return imported tables linked to the selected field.

        The schema is composed with ``psycopg2.sql.Identifier`` rather than
        formatted into the string. Both call sites pass a literal
        ('harvest', 'soil'), so nothing untrusted reaches it today - but
        plugins.qgis.org's upload check flags any query built by string
        formatting (bandit B608) and rejects the package over it, and the
        rest of this codebase composes identifiers this way already (see
        support_scripts/journal_fields.py).
        """
        table = pgsql.SQL('.').join(
            (pgsql.Identifier(schema), pgsql.Identifier('manual')))
        try:
            rows = self.parent.db.execute_and_return(
                pgsql.SQL('SELECT table_ FROM {} WHERE field = %s').format(table),
                params=(field_name,))
        except Exception:
            return set()
        return {row[0] for row in rows if row and row[0]}

    def _numeric_sources(self, schema, field_name):
        tables = self._get_tables_for_field(schema, field_name)
        if not tables:
            return []
        sources = []
        for table in sorted(tables):
            if table not in self.parent.db.get_tables_in_db(schema):
                continue
            columns = self.parent.db.get_numeric_columns(
                table, schema, exclude="'cmax', 'cmin'")
            sources.extend((f'{schema}.{table}.{column}',
                            (schema, table, column)) for column in columns)
        return sources

    def reload_sources(self):
        field_name = self.field.currentText()
        self.harvest.clear()
        self.soil.clear()
        if not field_name:
            return
        for label, source in self._numeric_sources('harvest', field_name):
            item = QListWidgetItem(label, self.harvest)
            item.setData(Qt.ItemDataRole.UserRole, source)
            item.setCheckState(Qt.CheckState.Unchecked)
        for label, source in self._numeric_sources('soil', field_name):
            self.soil.addItem(label, source)

    def calculate_index(self):
        try:
            count = self.classes.value()
            boundaries = [float(value.strip()) for value in self.boundaries.text().split(',')
                          if value.strip()]
            if len(boundaries) != count - 1:
                raise ValueError(f'Enter exactly {count - 1} boundaries.')
            harvest_sources = [self.harvest.item(index).data(Qt.ItemDataRole.UserRole)
                               for index in range(self.harvest.count())
                               if self.harvest.item(index).checkState() == Qt.CheckState.Checked]
            if not harvest_sources:
                raise ValueError('Select at least one harvest source.')
            soil_source = self.soil.currentData()
            sources = harvest_sources + ([soil_source] if soil_source else [])
            result = calculate_fertility_index(
                self.parent.db, self.field.currentText(),
                sources,
                boundaries=boundaries, class_count=count)
            self.result = result
            self.show_index.setEnabled(bool(result))
            self.create_shape_guide.setEnabled(bool(result))
            self.create_isoxml.setEnabled(bool(result))
            self.status.setText(f'Calculated {len(result)} cells. Click Show index to add it to the map.')
        except (TypeError, ValueError, IndexError) as error:
            self.status.setText(f'Could not calculate index: {error}')

    def show_index_layer(self):
        if not self.result:
            return
        if self.layer is not None:
            QgsProject.instance().removeMapLayer(self.layer.id())
        self.layer = QgsVectorLayer(
            'Polygon?crs=EPSG:4326',
            f'Fertility index - {self.field.currentText()}', 'memory')
        provider = self.layer.dataProvider()
        provider.addAttributes([QgsField('index', QVariant.Double),
                                QgsField('class', QVariant.Int)])
        self.layer.updateFields()
        for cell, index, class_number in self.result:
            if index is None or class_number is None:
                continue
            feature = QgsFeature(self.layer.fields())
            feature.setGeometry(QgsGeometry.fromWkt(cell.polygon_wkt))
            feature.setAttributes([float(index), int(class_number)])
            provider.addFeature(feature)
        self.layer.updateExtents()
        categories = []
        colors = ['#e5f5e0', '#a1d99b', '#74c476', '#31a354', '#006d2c',
                  '#00441b', '#002d12', '#001f0c', '#001507']
        for class_number in range(1, self.classes.value() + 1):
            symbol = QgsSymbol.defaultSymbol(self.layer.geometryType())
            symbol.setColor(QColor(colors[min(class_number - 1, len(colors) - 1)]))
            categories.append(QgsRendererCategory(
                class_number, symbol, f'Class {class_number}'))
        self.layer.setRenderer(QgsCategorizedSymbolRenderer('class', categories))
        QgsProject.instance().addMapLayer(self.layer)
        self.status.setText(f'Showing {self.layer.featureCount()} cells in a green index gradient.')

    def open_guide(self, format_name):
        if not self.result:
            return
        self.parent.guide.open_for_fertility_index(
            format_name, self.field.currentText(), self.result,
            self.classes.value())