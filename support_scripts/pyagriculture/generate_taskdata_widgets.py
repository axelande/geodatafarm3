import os
import struct
import json
import xml.etree.ElementTree as ET

import geopandas as gpd
import geopy.distance
from qgis.PyQt.QtWidgets import (QLabel, QWidget, QPushButton, QVBoxLayout, QComboBox,
                                 QLineEdit, QHBoxLayout, QCheckBox, QFrame, QScrollArea, QFileDialog,
                                 QGridLayout, QDoubleSpinBox, QSpinBox, QMessageBox,
                                 QTabWidget, QTableWidget, QTableWidgetItem)
from qgis.PyQt.QtCore import Qt
from qgis.core import (QgsProject, QgsCoordinateTransform, QgsCoordinateReferenceSystem,
                       QgsVectorLayer, QgsFeature, QgsGeometry, QgsMapLayer, QgsWkbTypes)

# Qt5/Qt6 compatibility
if hasattr(QFrame, 'Shape'):
    # Qt6
    QFrameStyledPanel = QFrame.Shape.StyledPanel
    QTableWidgetSelectRows = QTableWidget.SelectionBehavior.SelectRows
    QTableWidgetSingleSelection = QTableWidget.SelectionMode.SingleSelection
else:
    # Qt5
    QFrameStyledPanel = QFrame.StyledPanel
    QTableWidgetSelectRows = QTableWidget.SelectRows
    QTableWidgetSingleSelection = QTableWidget.SingleSelection

from .create_recipe import CreateRecipe
from .meta_data_widgets import MetaData
from .generate_taskdata_commands import GenerateTaskCommands
from .sorting_utils import etree_to_dict
from .errors import MsgError
from ..qt_data import _scroll_bar_policy, _check_state, _alignment, _match_flag, _size_policy
__version__ = 0.1


def distance(p1, p2):
    x = p1.y, p1.x
    y = p2.y, p2.x
    return geopy.distance.geodesic(x, y).m


class TaskDataMixin:
    """Mixin class containing shared logic for ISOXML taskdata generation.

    This mixin provides common functionality used by both GenerateTaskDataWidget
    and GenerateIsoxmlController, including schema loading, widget creation,
    metadata handling, and grid generation.
    """

    # Map meta_type to (xml_file, attr_keys)
    META_CONFIG = {
        'Farm': ('FRMs.xml', ['tag', 'B', 'F', 'I']),
        'Customer': ('CTRs.xml', ['tag', 'B', 'C', 'G']),
        'Worker': ('WRKs.xml', ['tag', 'B', 'C', 'J']),
        'Device': ('DVCs.xml', ['tag', 'B', 'E']),
        'Product': ('PDTs.xml', ['tag', 'B', 'C', 'F']),
        'ProductGroup': ('PGPs.xml', ['tag', 'B', 'C']),
        'ValuePresentation': ('VPNs.xml', ['tag', 'B', 'C', 'D', 'E']),
        'CulturalPractice': ('CPCs.xml', ['tag', 'B']),
        'OperationTechnique': ('OTQs.xml', ['tag', 'B']),
        'CropType': ('CTPs.xml', ['tag', 'B', 'C']),
        'CodedCommentGroup': ('CCGs.xml', ['tag', 'B']),
    }

    SCHEMA_KEYS = {
        'Farm': 'FRM', 'Customer': 'CTR', 'Worker': 'WKR', 'Device': 'DVC',
        'Product': 'PDT', 'ProductGroup': 'PGP', 'ValuePresentation': 'VPN',
        'CulturalPractice': 'CPC', 'OperationTechnique': 'OTQ',
        'CropType': 'CTP', 'CodedCommentGroup': 'CCG'
    }

    FILE_MAP = {
        'FRM': 'FRMs.xml', 'CTR': 'CTRs.xml', 'WKR': 'WRKs.xml',
        'DVC': 'DVCs.xml', 'PDT': 'PDTs.xml', 'PGP': 'PGPs.xml',
        'VPN': 'VPNs.xml', 'CPC': 'CPCs.xml', 'OTQ': 'OTQs.xml',
        'CTP': 'CTPs.xml', 'CCG': 'CCGs.xml', 'TZN': None, 'PFD': None,
    }

    def _init_taskdata_state(self):
        """Initialize common state variables."""
        self.schemas = {}
        self.added_rows = {}
        self.id_list = {}
        self.idref_widgets = {}
        self.save_temp = {}
        self.frame_stack = {}
        self.q_layout = None

    def _load_schemas(self, schemas_dir: str = None):
        """Load all schemas from the schemas folder."""
        if schemas_dir is None:
            this_folder = os.path.dirname(os.path.abspath(__file__))
            schemas_folder = os.path.normpath(os.path.join(this_folder, '..', 'schemas'))
        else:
            schemas_folder = os.path.abspath(schemas_dir)
        if not os.path.isdir(schemas_folder):
            return
        for schema in os.listdir(schemas_folder):
            if '.schema' not in schema:
                continue
            self.schemas[schema.split('.')[0]] = json.load(open(os.path.join(schemas_folder, schema)))

    def _get_parent_widget(self):
        """Get the parent widget for creating child widgets."""
        if hasattr(self, 'dock_widget') and self.dock_widget is not None:
            return self.dock_widget
        return self

    def _get_lw_fields(self):
        """Get the LWFields list widget from dock_widget."""
        lw = None
        try:
            if hasattr(self, 'dock_widget') and self.dock_widget is not None:
                lw = getattr(self.dock_widget, 'LWFields', None)
        except Exception:
            pass
        if lw is None:
            try:
                if hasattr(self, 'parent_gdf') and self.parent_gdf is not None:
                    dock = getattr(self.parent_gdf, 'dock_widget', None)
                    if dock is not None:
                        lw = getattr(dock, 'LWFields', None)
            except Exception:
                pass
        return lw

    def _get_existing_metadata_items(self, schema_key: str) -> list:
        """Load existing metadata items from XML files."""
        if schema_key not in self.FILE_MAP or self.FILE_MAP[schema_key] is None:
            return []
        xml_file = self.FILE_MAP[schema_key]
        xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', xml_file)
        items = []
        try:
            tree = ET.parse(xml_path)
            for child in tree.getroot():
                display_name = child.attrib.get('B', '')
                items.append((child.tag, display_name))
        except Exception:
            pass
        return items

    def _find_layer_for_field(self, field_name: str):
        """Find a map layer whose name matches the given field name."""
        try:
            for layer in QgsProject.instance().mapLayers().values():
                try:
                    if layer.name().startswith(field_name) or layer.name() == field_name:
                        return layer
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback: try fetching from database
        db = self._get_database_connection()
        if db is None:
            return None

        try:
            safe_name = field_name.replace("'", "''")
            sql = f"select ST_AsText(polygon) from fields where field_name = '{safe_name}' limit 1"
            res = db.execute_and_return(sql, return_failure=True)

            wkt = None
            if isinstance(res, list) and res:
                if res[0] is True and len(res) > 1:
                    data = res[1]
                    if data and data[0] and data[0][0]:
                        wkt = data[0][0]
                elif res[0] and isinstance(res[0], (list, tuple)):
                    wkt = res[0][0]

            if not wkt:
                return None

            vlayer = QgsVectorLayer('Polygon?crs=EPSG:4326', field_name, 'memory')
            prov = vlayer.dataProvider()
            feat = QgsFeature()
            try:
                geom = QgsGeometry.fromWkt(wkt)
            except Exception:
                geom = None
            if geom is None or geom.isEmpty():
                return None
            feat.setGeometry(geom)
            prov.addFeatures([feat])
            vlayer.updateExtents()
            return vlayer
        except Exception:
            return None

    def _get_database_connection(self):
        """Get database connection from various sources."""
        db = None
        try:
            if getattr(self, 'parent_gdf', None) is not None:
                db = getattr(self.parent_gdf, 'db', None)
                if db is None:
                    populate = getattr(self.parent_gdf, 'populate', None)
                    if populate is not None:
                        db = getattr(populate, 'db', None)
        except Exception:
            pass

        if db is None:
            db = getattr(self, 'db', None)

        if db is None:
            try:
                if hasattr(self, 'dock_widget') and self.dock_widget is not None:
                    parent = self.dock_widget.parent()
                    while parent is not None:
                        if hasattr(parent, 'db'):
                            db = parent.db
                            break
                        if hasattr(parent, 'parent_gdf') and hasattr(parent.parent_gdf, 'db'):
                            db = parent.parent_gdf.db
                            break
                        try:
                            parent = parent.parent()
                        except Exception:
                            break
            except Exception:
                pass

        if db is None:
            try:
                if hasattr(self, 'dock_widget') and self.dock_widget is not None:
                    gdf = getattr(self.dock_widget, 'gdf', None)
                    if gdf is not None:
                        db = getattr(gdf, 'db', None)
            except Exception:
                pass

        return db

    def _copy_geometry(self, geom):
        """Return a safe copy of a QgsGeometry across QGIS versions."""
        try:
            return geom.clone()
        except Exception:
            try:
                return QgsGeometry.fromWkt(geom.asWkt())
            except Exception:
                try:
                    return QgsGeometry(geom)
                except Exception:
                    return geom

    def _walk_dict(self, d_in, key, parent_layout: QGridLayout, parent_frame: QFrame):
        """Walk through recipe dict and create UI elements."""
        if isinstance(d_in, list):
            for sub in d_in:
                self._walk_dict(sub, key, parent_layout, parent_frame)
            return
        if d_in is None:
            d_in = {}
        key_frame = QFrame()
        key_layout = QGridLayout()
        key_layout.__setattr__("key", key)
        key_layout.setSpacing(2)
        key_layout.setContentsMargins(5, 2, 5, 2)
        key_frame.setLayout(key_layout)

        extra_id = self._find_extra_id(d_in, key)
        self._add_schema_checkbox(key, key_frame, parent_layout, parent_frame, key_layout, d_in, str(extra_id))
        if d_in and 'attr' in d_in.keys():
            height = self._set_widget(d_in, key, key_layout, extra_id)
        else:
            height = 50
        parent_layout.addWidget(key_frame, parent_layout.rowCount(), 0, 1, 3)
        self.frame_stack[key_frame] = {'parent_frame': parent_frame, 'height': height, 'key': key}

        for key_d in d_in.keys():
            if key_d == 'attr':
                continue
            else:
                self._walk_dict(d_in[key_d], key_d, key_layout, key_frame)

    def _find_extra_id(self, d_in, key) -> object:
        """Find extra ID for a schema element."""
        extra_id = ''
        if d_in is None:
            return extra_id
        if 'attr' in d_in.keys():
            for attr_name in d_in['attr']:
                item = self.schemas[key][attr_name]
                if ('xs:id' in item["Type"].lower() and 'xs:idref' not in item["Type"].lower()) or item["Type"] == 'xs:ref_code_parent':
                    if key not in self.id_list.keys():
                        self.id_list[key] = []
                    self.id_list[key].append(len(self.id_list[key]))
                    extra_id = len(self.id_list[key])
        return extra_id

    def _update_ref_ids(self):
        """Update reference ID widgets."""
        for widget, ref in self.idref_widgets.items():
            items = []
            widget.clear()
            for i in self.id_list[ref]:
                items.append(ref + str(i + 1))
            existing_items = self._get_existing_metadata_items(ref)
            for existing_id, display_name in existing_items:
                if existing_id not in items:
                    items.append(f'{existing_id} - {display_name}')
            widget.addItems(items)

    def _set_widget(self, d_in: dict, key: str, key_layout: QGridLayout, extra_id: int) -> int:
        """Set up input widgets for a schema key."""
        parent_widget = self._get_parent_widget()
        size = 65
        if key in ['GRD']:
            self._add_file_input(key, d_in['attr'][6], 'G', key_layout, extra_id)
            size += 50  # GRD adds two rows
        if key in ['CTR', 'DVC', 'FRM']:
            self._add_metadata_selector(key, key_layout)
            size += 25
        if key == 'PFD':
            self._add_pfd_field_selector(key_layout)
            size += 25
        for attr_name in d_in['attr']:
            item = self.schemas[key][attr_name]
            type_ = item["Type"].lower()
            name = ''.join(' ' + char if char.isupper() else char.strip() for char in item['Attribute_name']).strip()
            if type_ in ['xs:id', 'xs:ref_code_parent']:
                continue
            elif 'string' in type_ or 'hexbinary' in type_:
                widget = QLineEdit(parent_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=200)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'unsignedbyte' in type_:
                widget = QSpinBox(parent_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=80)
                widget.setMinimum(0)
                widget.setMaximum(255)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'unsignedshort' in type_:
                widget = QSpinBox(parent_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=80)
                widget.setMinimum(0)
                widget.setMaximum(65535)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'unsignedlong' in type_:
                widget = QSpinBox(parent_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=120)
                widget.setMinimum(0)
                widget.setMaximum(2147483647)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'long' in type_:
                widget = QSpinBox(parent_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=120)
                widget.setMinimum(-2147483648)
                widget.setMaximum(2147483647)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'short' in type_:
                widget = QSpinBox(parent_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=80)
                widget.setMinimum(-32768)
                widget.setMaximum(32767)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'byte' in type_:
                widget = QSpinBox(parent_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=80)
                widget.setMinimum(-128)
                widget.setMaximum(127)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'decimal' in type_ or 'double' in type_:
                widget = QDoubleSpinBox(parent_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=150)
                # Use more decimals for GRD coordinates (A, B, C, D are in degrees)
                if key == 'GRD' and attr_name in ['A', 'B', 'C', 'D']:
                    widget.setDecimals(9)
                    widget.setMinimum(-180.0)
                    widget.setMaximum(180.0)
                else:
                    widget.setDecimals(2)
                    widget.setMinimum(-999999999.99)
                    widget.setMaximum(999999999.99)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'xs:idref' in type_ or 'xs:ref_code_child' in type_:
                if item['Ref_id'] == 'CTR':
                    md = MetaData()
                    widget = md.get_ctr_widgets(schema='CTR')
                else:
                    widget = QComboBox(parent_widget, minimumHeight=20, maximumWidth=200)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
                self.idref_widgets[widget] = item['Ref_id']
                if item['Ref_id'] not in self.id_list.keys():
                    self.id_list[item['Ref_id']] = [0]
            elif 'nmtoken' in type_:
                widget = QComboBox(parent_widget, minimumHeight=20, maximumWidth=200)
                if 'nm_list' in item:
                    widget.addItems(item['nm_list'])
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            else:
                print(f"Unhandled type: {item['Type']} for {key}.{attr_name}")
            size += 21
        return size

    def _add_input_widget(self, key, name, attr, layout: QGridLayout = None, widget=None):
        """Add an input widget to the layout."""
        parent_widget = self._get_parent_widget()
        field_name_label = QLabel(parent_widget, text=name + ': ')
        widget.__setattr__("schema", {key: attr})
        widget.__setattr__("attr_name", attr)
        field_name_layout = QHBoxLayout()
        field_name_layout.setAlignment(_alignment('AlignLeft'))
        field_name_layout.setContentsMargins(0, 0, 0, 0)
        field_name_layout.addWidget(field_name_label)
        field_name_layout.addWidget(widget)
        rows = layout.rowCount()
        layout.addLayout(field_name_layout, rows, 0, 1, 3)

    def _add_schema_checkbox(self, name: str, frame: QFrame, layout, parent_frame: QFrame, key_layout,
                             d_in: dict, extra_id: str = ''):
        """Add checkbox and +/- buttons for a schema element."""
        parent_widget = self._get_parent_widget()
        check_box = QCheckBox(text=name + extra_id)
        check_box.__setattr__("frame", frame)
        check_box.setCheckState(_check_state('Checked'))
        check_box.toggled.connect(self._show_frame)
        add_line_push_button = QPushButton(parent_widget, text='+', maximumWidth=25)
        remove_line_push_button = QPushButton(parent_widget, text='-', maximumWidth=25)
        add_line_push_button.__setattr__("layout", key_layout)
        add_line_push_button.__setattr__("parent_layout", layout)
        add_line_push_button.__setattr__("parent_frame", parent_frame)
        add_line_push_button.__setattr__("key", name)
        add_line_push_button.__setattr__("d_in", d_in)
        remove_line_push_button.__setattr__("parent_layout", layout)

        remove_line_push_button.clicked.connect(self._remove_extra_row)
        add_line_push_button.clicked.connect(self._add_extra_row)

        current_row = layout.rowCount()
        layout.addWidget(check_box, current_row, 0, 1, 1)
        layout.addWidget(add_line_push_button, current_row, 1, 1, 1)
        layout.addWidget(remove_line_push_button, current_row, 2, 1, 1)

        # LSG special handling for polygon type selection
        if name == 'LSG':
            self._add_lsg_polygon_type_selector(layout, frame)

    def _add_lsg_polygon_type_selector(self, layout, frame):
        """Add polygon type selector for LSG elements."""
        try:
            poly_type_cb = QComboBox()
            poly_type_cb.addItems(['', 'Partfield Boundary', 'PolygonExterior', 'PolygonInterior'])
            poly_type_cb.__setattr__('is_polygon_type', True)
            field_selector = QComboBox()
            field_selector.__setattr__('is_field_selector', True)
            field_selector.setVisible(False)

            lw = self._get_lw_fields()
            if lw is not None:
                try:
                    items = [lw.item(j).text() for j in range(lw.count())]
                    field_selector.addItems(items)
                except Exception:
                    pass

            def _on_poly_type_changed(idx, cb=poly_type_cb, fs=field_selector):
                try:
                    text = cb.currentText()
                    fs.setVisible(text == 'Partfield Boundary')
                except Exception:
                    pass

            def _on_poly_type_changed_set_frame(idx, cb=poly_type_cb, fr=frame):
                try:
                    fr.__setattr__('polygon_type', cb.currentText())
                except Exception:
                    pass

            poly_type_cb.currentIndexChanged.connect(_on_poly_type_changed)
            poly_type_cb.currentIndexChanged.connect(_on_poly_type_changed_set_frame)

            def _on_field_selected(idx, fs=field_selector, fr=frame):
                try:
                    fr.__setattr__('selected_field', fs.currentText())
                except Exception:
                    pass

            field_selector.currentIndexChanged.connect(_on_field_selected)

            layout.addWidget(poly_type_cb, layout.rowCount() - 1, 3, 1, 1)
            layout.addWidget(field_selector, layout.rowCount() - 1, 4, 1, 1)
        except Exception:
            pass

    def _show_frame(self):
        """Toggle frame visibility."""
        sender = self._get_sender()
        frame = sender.frame
        if frame.isHidden():
            frame.show()
        else:
            frame.hide()

    def _get_sender(self):
        """Get the sender of the signal."""
        if hasattr(self, 'dock_widget') and self.dock_widget is not None:
            return self.dock_widget.sender()
        return self.sender()

    def _add_extra_row(self):
        """Add an extra row for a schema element."""
        sender = self._get_sender()
        key = sender.key
        d_in = sender.d_in
        parent_layout = sender.parent_layout
        parent_frame = sender.parent_frame
        row_count_before = parent_layout.rowCount()
        self._walk_dict(d_in, key, parent_layout, parent_frame)
        if parent_layout not in self.added_rows.keys():
            self.added_rows[parent_layout] = []
        now_added = []
        for i in range(row_count_before, parent_layout.rowCount()):
            now_added.append(i)
        self.added_rows[parent_layout].append(now_added)
        self._update_ref_ids()

    def _remove_extra_row(self):
        """Remove an extra row."""
        sender = self._get_sender()
        parent_layout: QGridLayout = sender.parent_layout
        if parent_layout not in self.added_rows.keys():
            return
        if len(self.added_rows[parent_layout]) == 0:
            return
        for i in reversed(self.added_rows[parent_layout][-1]):
            for column in range(parent_layout.columnCount()):
                try:
                    item = parent_layout.itemAtPosition(i, column)
                    if item is not None:
                        item.widget().close()
                        parent_layout.removeItem(item)
                        del item
                except Exception:
                    pass
        self.added_rows[parent_layout] = self.added_rows[parent_layout][:-1]

    def _add_metadata_selector(self, key: str, layout: QGridLayout):
        """Add a combobox to select from existing metadata and populate fields."""
        parent_widget = self._get_parent_widget()
        label = QLabel(parent_widget, text=f'Select existing {key}:')
        selector = QComboBox(parent_widget)
        selector.setMinimumWidth(150)
        selector.__setattr__('is_metadata_selector', True)
        selector.__setattr__('schema_key', key)

        file_map = {'CTR': 'CTRs.xml', 'DVC': 'DVCs.xml', 'FRM': 'FRMs.xml'}
        selector.addItem('')
        if key in file_map:
            xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', file_map[key])
            try:
                tree = ET.parse(xml_path)
                for child in tree.getroot():
                    display_name = child.attrib.get('B', '')
                    selector.addItem(f'{child.tag} - {display_name}')
            except Exception:
                pass

        populate_button = QPushButton(parent_widget, text='Populate', minimumHeight=20)
        populate_button.__setattr__('layout', layout)
        populate_button.__setattr__('schema_key', key)
        populate_button.__setattr__('selector', selector)
        populate_button.clicked.connect(self._populate_from_metadata)

        rows = layout.rowCount()
        layout.addWidget(label, rows, 0)
        layout.addWidget(selector, rows, 1)
        layout.addWidget(populate_button, rows, 2)

    def _add_pfd_field_selector(self, layout: QGridLayout):
        """Add a field selector for PFD that reads from dock_widget.LWFields."""
        parent_widget = self._get_parent_widget()
        label = QLabel(parent_widget, text='Select field:')
        field_selector = QComboBox(parent_widget)
        field_selector.setMinimumWidth(150)
        field_selector.__setattr__('is_pfd_field_selector', True)

        lw = self._get_lw_fields()
        field_selector.addItem('')
        if lw is not None:
            try:
                items = [lw.item(j).text() for j in range(lw.count())]
                field_selector.addItems(items)
            except Exception:
                pass

        populate_button = QPushButton(parent_widget, text='Populate from field', minimumHeight=20)
        populate_button.__setattr__('layout', layout)
        populate_button.__setattr__('field_selector', field_selector)
        populate_button.clicked.connect(self._populate_pfd_from_field)

        rows = layout.rowCount()
        layout.addWidget(label, rows, 0)
        layout.addWidget(field_selector, rows, 1)
        layout.addWidget(populate_button, rows, 2)

    def _populate_from_metadata(self):
        """Populate form fields from selected metadata item."""
        sender = self._get_sender()
        layout = getattr(sender, 'layout', None)
        schema_key = getattr(sender, 'schema_key', None)
        selector = getattr(sender, 'selector', None)

        if layout is None or schema_key is None or selector is None:
            return

        selected_text = selector.currentText()
        if not selected_text or ' - ' not in selected_text:
            return

        item_id = selected_text.split(' - ')[0]
        file_map = {'CTR': 'CTRs.xml', 'DVC': 'DVCs.xml', 'FRM': 'FRMs.xml'}
        if schema_key not in file_map:
            return

        xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', file_map[schema_key])
        try:
            tree = ET.parse(xml_path)
            xml_item = None
            for child in tree.getroot():
                if child.tag == item_id:
                    xml_item = child
                    break
            if xml_item is None:
                return

            for r in range(layout.rowCount()):
                for c in range(layout.columnCount()):
                    item = layout.itemAtPosition(r, c)
                    if item is None:
                        continue
                    widget = item.widget()
                    if widget is None:
                        sub_layout = item.layout()
                        if sub_layout is not None:
                            for idx in range(sub_layout.count()):
                                sub_widget = sub_layout.itemAt(idx).widget()
                                self._set_widget_from_xml(sub_widget, xml_item)
                    else:
                        self._set_widget_from_xml(widget, xml_item)
        except Exception as e:
            QMessageBox.warning(self._get_parent_widget(), 'Error', f'Failed to populate from metadata: {e}')

    def _set_widget_from_xml(self, widget, xml_item):
        """Set widget value from XML element attribute."""
        if widget is None:
            return
        attr_key = getattr(widget, 'attr_name', None)
        if attr_key is None:
            return
        attr_value = xml_item.attrib.get(attr_key, '')
        if isinstance(widget, QLineEdit):
            widget.setText(attr_value)
        elif isinstance(widget, QSpinBox):
            try:
                widget.setValue(int(attr_value) if attr_value else 0)
            except ValueError:
                widget.setValue(0)
        elif isinstance(widget, QDoubleSpinBox):
            try:
                widget.setValue(float(attr_value) if attr_value else 0.0)
            except ValueError:
                widget.setValue(0.0)
        elif isinstance(widget, QComboBox):
            idx = widget.findText(attr_value, _match_flag('MatchStartsWith'))
            if idx >= 0:
                widget.setCurrentIndex(idx)

    def _populate_pfd_from_field(self):
        """Populate PFD fields from selected field layer."""
        sender = self._get_sender()
        layout = getattr(sender, 'layout', None)
        field_selector = getattr(sender, 'field_selector', None)

        if layout is None or field_selector is None:
            return

        field_name = field_selector.currentText()
        if not field_name:
            QMessageBox.warning(self._get_parent_widget(), 'Warning', 'Please select a field')
            return

        try:
            layer = self._find_layer_for_field(field_name)
            if layer is None:
                QMessageBox.warning(self._get_parent_widget(), 'Warning', f'Field "{field_name}" not found')
                return

            if layer.featureCount() == 0:
                QMessageBox.warning(self._get_parent_widget(), 'Warning', f'Field "{field_name}" has no features')
                return

            feature = next(layer.getFeatures())
            geom = feature.geometry()

            source_crs = layer.crs()
            dest_crs = QgsCoordinateReferenceSystem('EPSG:3857')
            transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
            geom_copy = self._copy_geometry(geom)
            geom_copy.transform(transform)
            area_m2 = int(geom_copy.area())

            crs_wgs = QgsCoordinateReferenceSystem('EPSG:4326')
            transform_wgs = QgsCoordinateTransform(source_crs, crs_wgs, QgsProject.instance())
            geom_wgs = self._copy_geometry(geom)
            geom_wgs.transform(transform_wgs)

            for r in range(layout.rowCount()):
                for c in range(layout.columnCount()):
                    item = layout.itemAtPosition(r, c)
                    if item is None:
                        continue
                    widget = item.widget()
                    if widget is None:
                        sub_layout = item.layout()
                        if sub_layout is not None:
                            for idx in range(sub_layout.count()):
                                sub_widget = sub_layout.itemAt(idx).widget()
                                self._set_pfd_widget_value(sub_widget, field_name, area_m2)
                    else:
                        self._set_pfd_widget_value(widget, field_name, area_m2)

            self._populate_polygon_from_geometry(layout, geom_wgs, area_m2)

        except Exception as e:
            QMessageBox.warning(self._get_parent_widget(), 'Error', f'Failed to populate from field: {e}')

    def _set_pfd_widget_value(self, widget, field_name: str, area_m2: int):
        """Set PFD widget value based on attribute key."""
        if widget is None:
            return
        attr_key = getattr(widget, 'attr_name', None)
        if attr_key is None:
            return
        if attr_key == 'C' and isinstance(widget, QLineEdit):
            widget.setText(field_name)
        elif attr_key == 'D' and isinstance(widget, QSpinBox):
            widget.setValue(area_m2)

    def _populate_polygon_from_geometry(self, pfd_layout, geom_wgs, area_m2: int):
        """Populate PLN, LSG, and PNT widgets from a WGS84 geometry."""
        if geom_wgs.isMultipart():
            polygons = geom_wgs.asMultiPolygon()
            if not polygons:
                return
            rings = polygons[0]
        else:
            rings = geom_wgs.asPolygon()

        if not rings:
            return

        exterior_ring = rings[0]
        interior_rings = rings[1:] if len(rings) > 1 else []

        pln_frame = self._find_child_frame_by_key(pfd_layout, 'PLN')
        if pln_frame is None:
            return

        pln_layout = pln_frame.layout()
        if pln_layout is None:
            return

        self._set_widget_by_attr(pln_layout, 'A', 'Partfield Boundary')
        self._set_widget_by_attr(pln_layout, 'C', area_m2)

        lsg_frame = self._find_child_frame_by_key(pln_layout, 'LSG')
        if lsg_frame is None:
            return

        lsg_layout = lsg_frame.layout()
        if lsg_layout is None:
            return

        self._set_widget_by_attr(lsg_layout, 'A', 'PolygonExterior')
        self._populate_points_in_lsg(lsg_layout, exterior_ring)

        for hole_ring in interior_rings:
            add_button = self._find_add_button_for_key(pln_layout, 'LSG')
            if add_button is not None:
                add_button.click()
                new_lsg_frame = self._find_last_child_frame_by_key(pln_layout, 'LSG')
                if new_lsg_frame is not None and new_lsg_frame != lsg_frame:
                    new_lsg_layout = new_lsg_frame.layout()
                    if new_lsg_layout is not None:
                        self._set_widget_by_attr(new_lsg_layout, 'A', 'PolygonInterior')
                        self._populate_points_in_lsg(new_lsg_layout, hole_ring)

    def _populate_points_in_lsg(self, lsg_layout, ring_coords):
        """Populate PNT entries in an LSG frame from ring coordinates."""
        if not ring_coords:
            return

        pnt_frame = self._find_child_frame_by_key(lsg_layout, 'PNT')
        if pnt_frame is None:
            return

        first_coord = ring_coords[0]
        pnt_layout = pnt_frame.layout()
        if pnt_layout is not None:
            self._set_widget_by_attr(pnt_layout, 'C', round(first_coord.y(), 9))
            self._set_widget_by_attr(pnt_layout, 'D', round(first_coord.x(), 9))

        add_button = self._find_add_button_for_key(lsg_layout, 'PNT')
        for coord in ring_coords[1:]:
            if add_button is not None:
                add_button.click()
                new_pnt_frame = self._find_last_child_frame_by_key(lsg_layout, 'PNT')
                if new_pnt_frame is not None:
                    new_pnt_layout = new_pnt_frame.layout()
                    if new_pnt_layout is not None:
                        self._set_widget_by_attr(new_pnt_layout, 'C', round(coord.y(), 9))
                        self._set_widget_by_attr(new_pnt_layout, 'D', round(coord.x(), 9))

    def _find_child_frame_by_key(self, layout, key: str):
        """Find a child QFrame whose layout has the given key attribute."""
        for r in range(layout.rowCount()):
            for c in range(layout.columnCount()):
                item = layout.itemAtPosition(r, c)
                if item is None:
                    continue
                widget = item.widget()
                if isinstance(widget, QFrame):
                    child_layout = widget.layout()
                    if child_layout is not None and getattr(child_layout, 'key', None) == key:
                        return widget
        return None

    def _find_last_child_frame_by_key(self, layout, key: str):
        """Find the last child QFrame whose layout has the given key attribute."""
        last_frame = None
        for r in range(layout.rowCount()):
            for c in range(layout.columnCount()):
                item = layout.itemAtPosition(r, c)
                if item is None:
                    continue
                widget = item.widget()
                if isinstance(widget, QFrame):
                    child_layout = widget.layout()
                    if child_layout is not None and getattr(child_layout, 'key', None) == key:
                        last_frame = widget
        return last_frame

    def _find_add_button_for_key(self, layout, key: str):
        """Find the + button for adding a new element of the given key type."""
        for r in range(layout.rowCount()):
            for c in range(layout.columnCount()):
                item = layout.itemAtPosition(r, c)
                if item is None:
                    continue
                widget = item.widget()
                if isinstance(widget, QPushButton) and widget.text() == '+':
                    if getattr(widget, 'key', None) == key:
                        return widget
        return None

    def _set_widget_by_attr(self, layout, attr_key: str, value):
        """Set a widget's value by its attr_name attribute."""
        for r in range(layout.rowCount()):
            for c in range(layout.columnCount()):
                item = layout.itemAtPosition(r, c)
                if item is None:
                    continue
                widget = item.widget()
                if widget is not None:
                    if getattr(widget, 'attr_name', None) == attr_key:
                        self._set_widget_value(widget, value)
                        return
                sub_layout = item.layout()
                if sub_layout is not None:
                    for idx in range(sub_layout.count()):
                        sub_item = sub_layout.itemAt(idx)
                        if sub_item is not None:
                            sub_widget = sub_item.widget()
                            if sub_widget is not None and getattr(sub_widget, 'attr_name', None) == attr_key:
                                self._set_widget_value(sub_widget, value)
                                return

    def _set_widget_value(self, widget, value):
        """Set a widget's value based on its type."""
        if isinstance(widget, QComboBox):
            if isinstance(value, str):
                idx = widget.findText(value, _match_flag('MatchStartsWith'))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))

    def _add_file_input(self, key, item, attr_name, layout: QGridLayout, extra_id: int):
        """Add file input widget (GRD selector with rate layer support)."""
        parent_widget = self._get_parent_widget()
        file_input_label = QLabel(parent_widget, text=f'{key}: ')
        layout.__setattr__('id', extra_id)

        if key == 'GRD':
            field_selector = QComboBox()
            field_selector.__setattr__('is_field_selector', True)
            cell_size = QDoubleSpinBox()
            cell_size.setDecimals(2)
            cell_size.setMaximum(10000000.0)
            cell_size.setMinimum(0.01)
            cell_size.setValue(10.0)
            cell_size.setSingleStep(1.0)
            try:
                cell_size.setSuffix(' m')
            except Exception:
                pass
            cell_size.__setattr__('is_cell_size', True)

            lw = self._get_lw_fields()
            if lw is not None:
                try:
                    items = [lw.item(j).text() for j in range(lw.count())]
                    field_selector.addItems(items)
                except Exception:
                    pass

            update_button = QPushButton(text='Update information', minimumHeight=20)
            update_button.__setattr__("layout", layout)
            update_button.__setattr__("schema", {key: attr_name})
            update_button.clicked.connect(
                lambda checked, lay=layout, fs=field_selector, cs=cell_size:
                    self._update_grid_information(lay, fs, cs)
            )

            grid_label = QLabel(parent_widget, text='grid size:')

            # Rate layer selector
            rate_layer_label = QLabel(parent_widget, text='Rate layer:')
            rate_layer_selector = QComboBox()
            rate_layer_selector.__setattr__('is_rate_layer_selector', True)
            rate_layer_selector.addItem('')
            try:
                for layer in QgsProject.instance().mapLayers().values():
                    if layer.type() == QgsMapLayer.VectorLayer:
                        if layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                            rate_layer_selector.addItem(layer.name())
            except Exception:
                pass

            rate_attr_label = QLabel(parent_widget, text='Rate attribute:')
            rate_attr_selector = QComboBox()
            rate_attr_selector.__setattr__('is_rate_attr_selector', True)
            rate_attr_selector.setMinimumWidth(100)

            def on_rate_layer_changed(_idx, layer_sel=rate_layer_selector, attr_sel=rate_attr_selector):
                attr_sel.clear()
                layer_name = layer_sel.currentText()
                if not layer_name:
                    return
                try:
                    layers = QgsProject.instance().mapLayersByName(layer_name)
                    if layers:
                        layer = layers[0]
                        for field in layer.fields():
                            if field.isNumeric():
                                attr_sel.addItem(field.name())
                except Exception:
                    pass

            rate_layer_selector.currentIndexChanged.connect(on_rate_layer_changed)

            layout.__setattr__('rate_layer_selector', rate_layer_selector)
            layout.__setattr__('rate_attr_selector', rate_attr_selector)
            layout.__setattr__('field_selector', field_selector)
            layout.__setattr__('cell_size', cell_size)

            input_layout = QHBoxLayout()
            input_layout.setAlignment(_alignment('AlignLeft'))
            input_layout.setContentsMargins(0, 0, 0, 0)
            input_layout.addWidget(file_input_label)
            input_layout.addWidget(field_selector)
            input_layout.addWidget(grid_label)
            input_layout.addWidget(cell_size)
            input_layout.addWidget(update_button)

            rate_layout = QHBoxLayout()
            rate_layout.setAlignment(_alignment('AlignLeft'))
            rate_layout.setContentsMargins(0, 0, 0, 0)
            rate_layout.addWidget(rate_layer_label)
            rate_layout.addWidget(rate_layer_selector)
            rate_layout.addWidget(rate_attr_label)
            rate_layout.addWidget(rate_attr_selector)

            rows = layout.rowCount()
            layout.addLayout(input_layout, rows, 0, 1, 3)
            layout.addLayout(rate_layout, rows + 1, 0, 1, 3)
            return
        else:
            file_input_button = QPushButton(text='Get files', minimumHeight=20)
            file_input_button.__setattr__("layout", layout)
            file_input_button.__setattr__("schema", {key: attr_name})
            input_layout = QHBoxLayout()
            input_layout.setAlignment(_alignment('AlignLeft'))
            input_layout.setContentsMargins(0, 0, 0, 0)
            input_layout.addWidget(file_input_label)
            input_layout.addWidget(file_input_button)

        rows = layout.rowCount()
        layout.addLayout(input_layout, rows, 0, 1, 3)

    def _update_grid_information(self, layout, field_selector, cell_size_widget):
        """Update GRD widgets from selected field and provided cell size."""
        try:
            field_name = field_selector.currentText()
        except Exception:
            field_name = None
        try:
            cell_size_m = float(cell_size_widget.value())
        except Exception:
            cell_size_m = None

        if not field_name or not cell_size_m:
            return

        field_layer = self._find_layer_for_field(field_name)
        if field_layer is None:
            return

        # Refresh rate layer and attribute selectors
        rate_layer_selector = getattr(layout, 'rate_layer_selector', None)
        rate_attr_selector = getattr(layout, 'rate_attr_selector', None)

        if rate_layer_selector is not None:
            current_rate_layer = rate_layer_selector.currentText()
            rate_layer_selector.blockSignals(True)
            rate_layer_selector.clear()
            rate_layer_selector.addItem('')
            try:
                for layer in QgsProject.instance().mapLayers().values():
                    if layer.type() == QgsMapLayer.VectorLayer:
                        if layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                            rate_layer_selector.addItem(layer.name())
            except Exception:
                pass
            idx = rate_layer_selector.findText(current_rate_layer)
            if idx >= 0:
                rate_layer_selector.setCurrentIndex(idx)
            rate_layer_selector.blockSignals(False)

            if rate_attr_selector is not None:
                current_rate_attr = rate_attr_selector.currentText()
                rate_attr_selector.clear()
                rate_layer_name = rate_layer_selector.currentText()
                if rate_layer_name:
                    try:
                        layers = QgsProject.instance().mapLayersByName(rate_layer_name)
                        if layers:
                            layer = layers[0]
                            for field in layer.fields():
                                if field.isNumeric():
                                    rate_attr_selector.addItem(field.name())
                    except Exception:
                        pass
                    idx = rate_attr_selector.findText(current_rate_attr)
                    if idx >= 0:
                        rate_attr_selector.setCurrentIndex(idx)

        rate_layer_name = rate_layer_selector.currentText() if rate_layer_selector else ''
        rate_attr = rate_attr_selector.currentText() if rate_attr_selector else ''

        if rate_layer_name and rate_attr:
            try:
                rate_layers = QgsProject.instance().mapLayersByName(rate_layer_name)
                if rate_layers:
                    rate_layer = rate_layers[0]
                    grd_id = 1
                    if 'GRD' in self.save_temp:
                        grd_id = max(self.save_temp['GRD'].keys()) + 1 if self.save_temp['GRD'] else 1
                    grd_attrs = self._generate_grid_binary_from_rate_layer(
                        field_layer, rate_layer, rate_attr, cell_size_m, grd_id
                    )
                else:
                    grd_attrs = self._compute_grid_attrs_from_layer(field_layer, cell_size_m)
            except Exception as e:
                QMessageBox.warning(self._get_parent_widget(), 'Warning',
                                    f'Could not generate rate grid: {e}\nUsing basic grid instead.')
                grd_attrs = self._compute_grid_attrs_from_layer(field_layer, cell_size_m)
        else:
            grd_attrs = self._compute_grid_attrs_from_layer(field_layer, cell_size_m)

        widgets = self._get_grid_widgets(layout)

        for k, v in grd_attrs.items():
            if k in widgets:
                try:
                    w = widgets[k]
                    if type(w) in [QDoubleSpinBox]:
                        w.setValue(float(v))
                    if type(w) in [QSpinBox]:
                        w.setValue(int(v))
                    elif type(w) == QLineEdit:
                        w.setText(str(v))
                except Exception:
                    pass

    def _compute_grid_attrs_from_layer(self, layer, cell_size_m: float, generate_binary: bool = True) -> dict:
        """Compute GRD attributes from a polygon layer and desired cell size in meters.

        Args:
            layer: QgsVectorLayer with field boundary polygon
            cell_size_m: Cell size in meters
            generate_binary: If True, generate a binary file with zeros (Type 1 grid)
        """
        attrs = {}
        try:
            feat = next(layer.getFeatures())
            geom = feat.geometry()
            crs_src = layer.crs()
            crs_wgs = QgsCoordinateReferenceSystem('EPSG:4326')
            xform_to_wgs = QgsCoordinateTransform(crs_src, crs_wgs, QgsProject.instance())
            geom_wgs = self._copy_geometry(geom)
            try:
                geom_wgs.transform(xform_to_wgs)
            except Exception:
                pass
            centroid = geom_wgs.centroid().asPoint()
            lon = centroid.x()
            lat = centroid.y()
            zone = int((lon + 180) / 6) + 1
            if lat >= 0:
                epsg_utm = 32600 + zone
            else:
                epsg_utm = 32700 + zone

            crs_utm = QgsCoordinateReferenceSystem(f'EPSG:{epsg_utm}')
            xform_to_utm = QgsCoordinateTransform(crs_src, crs_utm, QgsProject.instance())
            geom_utm = self._copy_geometry(geom)
            try:
                geom_utm.transform(xform_to_utm)
            except Exception:
                pass

            bbox = geom_utm.boundingBox()
            minx = bbox.xMinimum()
            miny = bbox.yMinimum()
            maxx = bbox.xMaximum()
            maxy = bbox.yMaximum()
            width_m = maxx - minx
            height_m = maxy - miny

            ncols = max(1, int(round(width_m / cell_size_m)))
            nrows = max(1, int(round(height_m / cell_size_m)))

            xform_utm_to_wgs = QgsCoordinateTransform(crs_utm, crs_wgs, QgsProject.instance())
            try:
                from qgis.core import QgsPointXY
                pt_utm = QgsGeometry.fromPointXY(QgsPointXY(minx, miny))
                pt_utm.transform(xform_utm_to_wgs)
                p = pt_utm.asPoint()
                lat_min = p.y()
                lon_min = p.x()
            except Exception:
                lat_min = lat
                lon_min = lon

            try:
                from qgis.core import QgsPointXY
                pt_east_utm = QgsGeometry.fromPointXY(QgsPointXY(minx + cell_size_m, miny))
                pt_east_utm.transform(xform_utm_to_wgs)
                p_e = pt_east_utm.asPoint()
                cell_e_deg = abs(p_e.x() - lon_min)

                pt_north_utm = QgsGeometry.fromPointXY(QgsPointXY(minx, miny + cell_size_m))
                pt_north_utm.transform(xform_utm_to_wgs)
                p_n = pt_north_utm.asPoint()
                cell_n_deg = abs(p_n.y() - lat_min)
            except Exception:
                cell_e_deg = 0.0
                cell_n_deg = 0.0

            # Generate binary file with zeros if requested
            grd_id = 1
            if generate_binary:
                import pandas as pd
                if 'GRD' in self.save_temp:
                    grd_id = max(self.save_temp['GRD'].keys()) + 1 if self.save_temp['GRD'] else 1
                # Create grid of zeros (Type 2 grid with direct values)
                grid_values = [0] * (nrows * ncols)
                df = pd.DataFrame({'value': grid_values})
                if 'GRD' not in self.save_temp:
                    self.save_temp['GRD'] = {}
                self.save_temp['GRD'][grd_id] = df
                file_length = nrows * ncols * 4  # 4 bytes per cell
                grid_type = '2'  # Type 2 = direct values
            else:
                file_length = 0
                grid_type = '1'  # Type 1 = treatment zone based

            attrs['A'] = f'{lat_min:.9f}'
            attrs['B'] = f'{lon_min:.9f}'
            attrs['C'] = f'{cell_n_deg:.9f}'
            attrs['D'] = f'{cell_e_deg:.9f}'
            attrs['E'] = str(ncols)
            attrs['F'] = str(nrows)
            attrs['G'] = f'GRD{grd_id:05d}'
            attrs['H'] = str(file_length)
            attrs['I'] = grid_type
            attrs['J'] = '0'
        except Exception:
            pass
        return attrs

    def _generate_grid_binary_from_rate_layer(self, field_layer, rate_layer, rate_attr: str,
                                               cell_size_m: float, grd_id: int = 1) -> dict:
        """Generate GRD binary data by rasterizing a rate layer onto a grid."""
        import pandas as pd
        from shapely.geometry import Point
        from shapely import wkt

        try:
            feat = next(field_layer.getFeatures())
            geom = feat.geometry()
            crs_src = field_layer.crs()
            crs_wgs = QgsCoordinateReferenceSystem('EPSG:4326')

            xform_to_wgs = QgsCoordinateTransform(crs_src, crs_wgs, QgsProject.instance())
            geom_wgs = self._copy_geometry(geom)
            geom_wgs.transform(xform_to_wgs)
            centroid = geom_wgs.centroid().asPoint()
            lon, lat = centroid.x(), centroid.y()
            zone = int((lon + 180) / 6) + 1
            epsg_utm = 32600 + zone if lat >= 0 else 32700 + zone
            crs_utm = QgsCoordinateReferenceSystem(f'EPSG:{epsg_utm}')

            xform_to_utm = QgsCoordinateTransform(crs_src, crs_utm, QgsProject.instance())
            geom_utm = self._copy_geometry(geom)
            geom_utm.transform(xform_to_utm)

            bbox = geom_utm.boundingBox()
            minx, miny = bbox.xMinimum(), bbox.yMinimum()
            maxx, maxy = bbox.xMaximum(), bbox.yMaximum()

            ncols = max(1, int(round((maxx - minx) / cell_size_m)))
            nrows = max(1, int(round((maxy - miny) / cell_size_m)))

            rate_crs = rate_layer.crs()
            xform_rate_to_utm = QgsCoordinateTransform(rate_crs, crs_utm, QgsProject.instance())

            rate_polygons = []
            for rate_feat in rate_layer.getFeatures():
                rate_geom = rate_feat.geometry()
                rate_geom_utm = self._copy_geometry(rate_geom)
                rate_geom_utm.transform(xform_rate_to_utm)
                rate_value = rate_feat[rate_attr]
                try:
                    rate_value = float(rate_value)
                except (TypeError, ValueError):
                    rate_value = 0.0
                wkt_str = rate_geom_utm.asWkt()
                shapely_geom = wkt.loads(wkt_str)
                rate_polygons.append((shapely_geom, rate_value))

            field_wkt = geom_utm.asWkt()
            field_shapely = wkt.loads(field_wkt)

            grid_values = []
            for row in range(nrows):
                for col in range(ncols):
                    cx = minx + (col + 0.5) * cell_size_m
                    cy = miny + (row + 0.5) * cell_size_m
                    cell_center = Point(cx, cy)

                    if not field_shapely.contains(cell_center):
                        grid_values.append(0)
                        continue

                    cell_value = 0
                    for poly, rate_val in rate_polygons:
                        if poly.contains(cell_center):
                            cell_value = int(rate_val)
                            break
                    grid_values.append(cell_value)

            df = pd.DataFrame({'value': grid_values})
            if 'GRD' not in self.save_temp:
                self.save_temp['GRD'] = {}
            self.save_temp['GRD'][grd_id] = df

            xform_utm_to_wgs = QgsCoordinateTransform(crs_utm, crs_wgs, QgsProject.instance())
            from qgis.core import QgsPointXY
            pt_min = QgsGeometry.fromPointXY(QgsPointXY(minx, miny))
            pt_min.transform(xform_utm_to_wgs)
            p = pt_min.asPoint()
            lat_min, lon_min = p.y(), p.x()

            pt_east = QgsGeometry.fromPointXY(QgsPointXY(minx + cell_size_m, miny))
            pt_east.transform(xform_utm_to_wgs)
            cell_e_deg = abs(pt_east.asPoint().x() - lon_min)

            pt_north = QgsGeometry.fromPointXY(QgsPointXY(minx, miny + cell_size_m))
            pt_north.transform(xform_utm_to_wgs)
            cell_n_deg = abs(pt_north.asPoint().y() - lat_min)

            attrs = {
                'A': f'{lat_min:.9f}',
                'B': f'{lon_min:.9f}',
                'C': f'{cell_n_deg:.9f}',
                'D': f'{cell_e_deg:.9f}',
                'E': str(ncols),
                'F': str(nrows),
                'G': f'GRD{grd_id:05d}',
                'H': str(nrows * ncols * 4),
                'I': '2',
                'J': '0'
            }
            return attrs

        except Exception as e:
            QMessageBox.warning(self._get_parent_widget(), 'Error', f'Failed to generate grid binary: {e}')
            return {}

    @staticmethod
    def _get_grid_widgets(layout) -> dict:
        """Get all GRD widgets from the layout."""
        widgets = {}
        for row in range(layout.rowCount()):
            item = layout.itemAtPosition(row, 0)
            if item is None:
                continue
            sub_layout = None
            try:
                sub_layout = item.layout()
            except Exception:
                sub_layout = item
            if sub_layout is None:
                continue
            try:
                child = sub_layout.itemAt(1)
                if child is not None:
                    w = child.widget()
                    if w is not None:
                        schema = getattr(w, 'schema', None)
                        if isinstance(schema, dict) and 'GRD' in schema:
                            widgets[schema['GRD']] = w
                            continue
            except Exception:
                pass
            try:
                for idx in range(sub_layout.count()):
                    child = sub_layout.itemAt(idx)
                    if child is None:
                        continue
                    w = child.widget()
                    if w is None:
                        continue
                    schema = getattr(w, 'schema', None)
                    if isinstance(schema, dict):
                        for k, v in schema.items():
                            if k == 'GRD':
                                widgets[v] = w
            except Exception:
                pass
        return widgets

    def _get_value_from_widget(self, widget) -> str:
        """Get value from a widget."""
        if type(widget) in [QSpinBox, QDoubleSpinBox]:
            value = str(widget.value())
        elif type(widget) == QLineEdit:
            value = widget.text()
        elif type(widget) == QComboBox:
            if widget in self.idref_widgets:
                text = widget.currentText()
                if ' - ' in text:
                    value = text.split(' - ')[0]
                else:
                    value = text
            else:
                value = widget.currentIndex()
        elif type(widget) == QPushButton:
            value = widget.value
        else:
            raise MsgError('Could not find the widget type')
        return value

    def _set_xml_children(self, layout: QGridLayout, parent: ET.Element):
        """Set XML children from layout."""
        key = layout.key
        xml_sub = ET.SubElement(parent, key)
        for i in range(layout.rowCount()):
            item = layout.itemAtPosition(i, 0)
            if item is not None:
                if type(item) == QHBoxLayout:
                    widget = item.itemAt(1).widget()
                    # Skip widgets without schema (e.g., metadata selectors, field selectors)
                    if widget is None or not hasattr(widget, 'schema'):
                        continue
                    schema = widget.schema
                    if not isinstance(schema, dict) or key not in schema:
                        continue
                    attr = schema[key]
                    value = self._get_value_from_widget(widget)
                    xml_sub.set(attr, str(value))
                else:
                    if type(item.widget()) == QFrame:
                        self._set_xml_children(item.widget().layout(), xml_sub)

        # Special handling for GRD: add G (filename) and H (file length) from save_temp
        if key == 'GRD' and 'GRD' in self.save_temp and self.save_temp['GRD']:
            # Get the GRD id from the layout
            grd_id = getattr(layout, 'id', 1)
            if grd_id in self.save_temp['GRD']:
                df = self.save_temp['GRD'][grd_id]
                file_length = len(df) * 4  # 4 bytes per cell (int32)
                xml_sub.set('G', f'GRD{grd_id:05d}')
                xml_sub.set('H', str(file_length))

    def _save_temp_files(self, path):
        """Save temporary binary files."""
        for key in self.save_temp.keys():
            for id_ in self.save_temp[key]:
                df = self.save_temp[key][id_]
                if key == 'GRD':
                    filename = f'{path}/{key}{id_:05d}.bin'
                    with open(filename, 'wb') as f:
                        for _index, row in df.iterrows():
                            for col in df.columns:
                                f.write(struct.pack('<i', int(row[col])))
                else:
                    filename = f'{path}/{key}{id_:04d}.bin'
                    with open(filename, 'wb') as f:
                        for _index, row in df.iterrows():
                            for col in df.columns:
                                f.write(struct.pack('<I', int(row[col])))


class GenerateTaskDataWidget(TaskDataMixin, QWidget):
    """Widget for generating ISOXML taskdata with recipe and metadata tabs."""

    def __init__(self, parent=None, parent_gdf=None):
        parent_widget = parent if isinstance(parent, QWidget) else None
        QWidget.__init__(self, parent_widget)
        self.parent_gdf = parent_gdf
        self.commands = GenerateTaskCommands(self.parent_gdf if self.parent_gdf is not None else self)
        self._init_taskdata_state()
        self._load_schemas()
        self.middle_layout = None

        # Create top-level tab widget
        self.main_tabs = QTabWidget()

        # Tab 1: Recipe tab
        self.recipe_tab = self._create_recipe_tab()
        self.main_tabs.addTab(self.recipe_tab, 'Recipe')

        # Metadata tabs
        self.metadata_tables = {}
        for meta_type in ['Farm', 'Customer', 'Worker', 'Device', 'Product', 'ProductGroup',
                          'ValuePresentation', 'CulturalPractice', 'OperationTechnique', 'CropType', 'CodedCommentGroup']:
            tab = self._create_metadata_tab(meta_type)
            self.main_tabs.addTab(tab, meta_type)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.main_tabs)
        self.setLayout(layout)
        self.setSizePolicy(_size_policy('Expanding'), _size_policy('Expanding'))

    def _create_recipe_tab(self):
        """Create the Recipe tab with existing functionality."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        intro_text = QLabel(
            'Welcome to the GeoDataFarm ISOXML Taskdata Generator!\n\n'
            'This tool helps you create ISOXML taskdata files for precision agriculture equipment. '
            'You can create recipes to define your task structure, then generate taskdata files '
            'ready for use with compatible farm machinery.\n\n'
            'Note: This feature is experimental. If you encounter any issues or have suggestions '
            'for improvements, please send an email to geodatafarm@gmail.com'
        )
        intro_text.setWordWrap(True)

        action_layout = QHBoxLayout()
        self.btn_new_recipe = QPushButton('New Recipe')
        self.btn_load_recipe = QPushButton('Load Recipe')
        self.btn_reset = QPushButton('Reset')
        self.btn_new_recipe.clicked.connect(self.create_new_recipe)
        self.btn_load_recipe.clicked.connect(self.load_recipe)
        self.btn_reset.clicked.connect(self.reset_recipe)
        action_layout.addWidget(self.btn_new_recipe)
        action_layout.addWidget(self.btn_load_recipe)
        action_layout.addWidget(self.btn_reset)
        action_layout.addStretch()

        self.middle_layout = QVBoxLayout()
        self.middle_frame = QFrame()
        self.middle_frame.setFrameShape(QFrameStyledPanel)
        self.middle_frame.setLayout(self.middle_layout)

        self.run_create_file = QPushButton('Create file')
        self.run_create_file.clicked.connect(self.store_data)

        layout.addWidget(intro_text)
        layout.addLayout(action_layout)
        layout.addWidget(self.middle_frame, 1)
        layout.addWidget(self.run_create_file)

        return widget

    def _create_metadata_tab(self, meta_type):
        """Create a tab with table and buttons for a metadata type."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        columns = {
            'Farm': ['ID', 'Name', 'City', 'Customer'],
            'Customer': ['ID', 'Last Name', 'First Name', 'City'],
            'Worker': ['ID', 'Last Name', 'First Name', 'Phone'],
            'Device': ['ID', 'Designator', 'Serial Number'],
            'Product': ['ID', 'Name', 'Product Group', 'Type'],
            'ProductGroup': ['ID', 'Name', 'Type'],
            'ValuePresentation': ['ID', 'Offset', 'Scale', 'Decimals', 'Unit'],
            'CulturalPractice': ['ID', 'Name'],
            'OperationTechnique': ['ID', 'Name'],
            'CropType': ['ID', 'Name', 'Product Group'],
            'CodedCommentGroup': ['ID', 'Name']
        }
        attr_map = {
            'Farm': ['tag', 'B', 'F', 'I'],
            'Customer': ['tag', 'B', 'C', 'G'],
            'Worker': ['tag', 'B', 'C', 'J'],
            'Device': ['tag', 'B', 'E'],
            'Product': ['tag', 'B', 'C', 'F'],
            'ProductGroup': ['tag', 'B', 'C'],
            'ValuePresentation': ['tag', 'B', 'C', 'D', 'E'],
            'CulturalPractice': ['tag', 'B'],
            'OperationTechnique': ['tag', 'B'],
            'CropType': ['tag', 'B', 'C'],
            'CodedCommentGroup': ['tag', 'B']
        }

        table = QTableWidget()
        table.setColumnCount(len(columns[meta_type]))
        table.setHorizontalHeaderLabels(columns[meta_type])
        table.setSelectionBehavior(QTableWidgetSelectRows)
        table.setSelectionMode(QTableWidgetSingleSelection)
        table.horizontalHeader().setStretchLastSection(True)
        self.metadata_tables[meta_type] = {'table': table, 'attrs': attr_map[meta_type]}

        btn_layout = QHBoxLayout()
        btn_add = QPushButton('Add')
        btn_edit = QPushButton('Edit')
        btn_remove = QPushButton('Remove')
        btn_add.clicked.connect(lambda checked, t=meta_type: self._add_metadata(t))
        btn_edit.clicked.connect(lambda checked, t=meta_type: self._edit_metadata(t))
        btn_remove.clicked.connect(lambda checked, t=meta_type: self._remove_metadata(t))
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()

        layout.addWidget(table, 1)
        layout.addLayout(btn_layout)

        self._refresh_metadata_table(meta_type)
        return widget

    def _refresh_metadata_table(self, meta_type):
        """Reload table data from XML file."""
        table_info = self.metadata_tables.get(meta_type)
        if table_info is None:
            return
        table = table_info['table']
        attrs = table_info['attrs']

        xml_file, _ = self.META_CONFIG[meta_type]
        this_dir = os.path.dirname(__file__)
        xml_path = os.path.join(this_dir, 'meta_data', xml_file)

        table.setRowCount(0)
        try:
            tree = ET.parse(xml_path)
            for child in tree.getroot():
                row = table.rowCount()
                table.insertRow(row)
                for col, attr in enumerate(attrs):
                    value = child.tag if attr == 'tag' else child.attrib.get(attr, '')
                    table.setItem(row, col, QTableWidgetItem(value))
        except Exception:
            pass

    def _add_metadata(self, meta_type):
        """Open MetaData dialog to add new item."""
        schema_key = self.SCHEMA_KEYS.get(meta_type)
        dlg = MetaData(self, meta_type, self.schemas.get(schema_key))
        dlg.exec()
        self._refresh_metadata_table(meta_type)

    def _edit_metadata(self, meta_type):
        """Open MetaData dialog to edit selected item."""
        table = self.metadata_tables[meta_type]['table']
        if table.currentRow() < 0:
            return
        schema_key = self.SCHEMA_KEYS.get(meta_type)
        dlg = MetaData(self, meta_type, self.schemas.get(schema_key))
        item_id = table.item(table.currentRow(), 0).text()
        for i in range(dlg.available_items_table_widget.count()):
            if dlg.available_items_table_widget.item(i).text().startswith(item_id):
                dlg.available_items_table_widget.setCurrentRow(i)
                dlg.edit_item()
                break
        dlg.exec()
        self._refresh_metadata_table(meta_type)

    def _remove_metadata(self, meta_type):
        """Remove selected metadata item."""
        table = self.metadata_tables[meta_type]['table']
        if table.currentRow() < 0:
            return
        item_id = table.item(table.currentRow(), 0).text()
        try:
            yes_btn = QMessageBox.StandardButton.Yes
            no_btn = QMessageBox.StandardButton.No
        except AttributeError:
            yes_btn = QMessageBox.Yes
            no_btn = QMessageBox.No
        reply = QMessageBox.question(
            self, 'Confirm Delete',
            f'Remove {meta_type} "{item_id}"?',
            yes_btn | no_btn
        )
        if reply != yes_btn:
            return
        xml_file, _ = self.META_CONFIG[meta_type]
        xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', xml_file)
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for child in list(root):
                if child.tag == item_id:
                    root.remove(child)
                    break
            try:
                ET.indent(root, space='    ')
            except AttributeError:
                pass
            with open(xml_path, 'wb') as f:
                f.write(ET.tostring(root, encoding='unicode').encode('utf-8'))
        except Exception:
            pass
        self._refresh_metadata_table(meta_type)

    def create_new_recipe(self):
        self.commands.create_new_recipe(on_recipe_saved=self._load_recipe_from_path)

    def reset_recipe(self):
        self.added_rows = {}
        self.id_list = {}
        self.idref_widgets = {}
        self.save_temp = {}
        item = self.middle_layout.itemAt(0)
        if item is not None:
            item.widget().close()
            self.middle_layout.removeItem(item)
            del item
        self.frame_stack = {}

    def load_recipe(self):
        """Open a file dialog to select and load a recipe file."""
        opts = QFileDialog.Options()
        dont_native = getattr(QFileDialog, 'DontUseNativeDialog', None)
        if dont_native is not None:
            try:
                opts |= dont_native
            except Exception:
                pass
        file = QFileDialog.getOpenFileName(self, "Open Recipe", "", 'Recipes (*.recipe)', options=opts)[0]
        if not file:
            return
        self._load_recipe_from_path(file)

    def _load_recipe_from_path(self, file_path: str):
        """Load a recipe from the given file path."""
        try:
            tree = ET.parse(file_path)
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Failed to open recipe:\n{e}')
            return
        parent_dict = etree_to_dict(tree.getroot())['ISO11783_TaskData']
        scroll_area = QScrollArea()
        scroll_area.setVerticalScrollBarPolicy(_scroll_bar_policy('ScrollBarAlwaysOn'))
        scroll_area.setHorizontalScrollBarPolicy(_scroll_bar_policy('ScrollBarAlwaysOff'))
        scroll_area.setWidgetResizable(True)

        self.q_layout = QGridLayout()
        widget = QFrame()
        widget.setLayout(self.q_layout)
        self.reset_recipe()
        for key, item in parent_dict.items():
            if item is None:
                continue
            self._walk_dict(item, key, self.q_layout, widget)

        scroll_area.setWidget(widget)
        scroll_area.show()
        self.middle_layout.addWidget(scroll_area)

        self._update_ref_ids()

    def store_data(self):
        if not hasattr(self, 'q_layout') or self.q_layout is None:
            QMessageBox.information(self, 'Error', 'No recipe loaded to save')
            return
        path = QFileDialog.getSaveFileName(self, 'Save TaskData', filter='xml (*.xml)')[0]
        if not path:
            return
        schemas_layout = self.q_layout
        et_parents = ET.Element('ISO11783_TaskData')
        et_parents.set("VersionMajor", "2")
        et_parents.set("VersionMinor", "0")
        et_parents.set("ManagementSoftwareManufacturer", "GeoDataFarm")
        et_parents.set("ManagementSoftwareVersion", str(__version__))
        et_parents.set("TaskControllerManufacturer", "GeoDataFarm")
        et_parents.set("TaskControllerVersion", str(__version__))
        et_parents.set("DataTransferOrigin", "1")
        for row in range(schemas_layout.rowCount()):
            sub_layout = schemas_layout.itemAtPosition(row, 0)
            if sub_layout is None:
                continue
            if type(sub_layout.widget().layout()) == QGridLayout:
                inner_layout = sub_layout.widget().layout()
                key = sub_layout.widget().layout().key
                xml_sub = ET.SubElement(et_parents, key)
                for j in range(inner_layout.rowCount()):
                    if type(inner_layout.itemAtPosition(j, 0)) == QHBoxLayout:
                        widget = inner_layout.itemAtPosition(j, 0).itemAt(1).widget()
                        # Skip widgets without schema (e.g., metadata selectors, field selectors)
                        if widget is None or not hasattr(widget, 'schema'):
                            continue
                        schema = widget.schema
                        if not isinstance(schema, dict) or key not in schema:
                            continue
                        attr = schema[key]
                        value = self._get_value_from_widget(widget)
                        xml_sub.set(attr, str(value))
                    else:
                        if inner_layout.itemAtPosition(j, 0) is not None:
                            if type(inner_layout.itemAtPosition(j, 0).widget()) == QFrame:
                                self._set_xml_children(inner_layout.itemAtPosition(j, 0).widget().layout(), xml_sub)
                # Special handling for GRD: add G (filename) and H (file length) from save_temp
                if key == 'GRD' and 'GRD' in self.save_temp and self.save_temp['GRD']:
                    grd_id = getattr(inner_layout, 'id', 1)
                    if grd_id in self.save_temp['GRD']:
                        df = self.save_temp['GRD'][grd_id]
                        file_length = len(df) * 4  # 4 bytes per cell (int32)
                        xml_sub.set('G', f'GRD{grd_id:05d}')
                        xml_sub.set('H', str(file_length))
        try:
            ET.indent(et_parents, space='    ', level=0)
        except AttributeError:
            pass
        with open(path, 'w') as f:
            f.write(ET.tostring(et_parents, encoding='unicode'))
        self._save_temp_files(os.path.dirname(path))

    # Aliases for backwards compatibility with old method names
    def load_schemas(self, schemas_dir: str = None):
        return self._load_schemas(schemas_dir)

    def walk_dict(self, d_in, key, parent_layout, parent_frame):
        return self._walk_dict(d_in, key, parent_layout, parent_frame)

    def find_extra_id(self, d_in, key):
        return self._find_extra_id(d_in, key)

    def update_ref_ids(self):
        return self._update_ref_ids()

    def set_widget(self, d_in, key, key_layout, extra_id):
        return self._set_widget(d_in, key, key_layout, extra_id)

    def add_input_widget(self, key, name, attr, layout=None, widget=None):
        return self._add_input_widget(key, name, attr, layout, widget)

    def add_schema_checkbox(self, name, frame, layout, parent_frame, key_layout, d_in, extra_id=''):
        return self._add_schema_checkbox(name, frame, layout, parent_frame, key_layout, d_in, extra_id)

    def show_frame(self):
        return self._show_frame()

    def add_extra_row(self):
        return self._add_extra_row()

    def remove_extra_row(self):
        return self._remove_extra_row()

    def add_metadata_selector(self, key, layout):
        return self._add_metadata_selector(key, layout)

    def add_pfd_field_selector(self, layout):
        return self._add_pfd_field_selector(layout)

    def add_file_input(self, key, item, attr_name, layout, extra_id):
        return self._add_file_input(key, item, attr_name, layout, extra_id)

    def populate_from_metadata(self):
        return self._populate_from_metadata()

    def populate_pfd_from_field(self):
        return self._populate_pfd_from_field()

    def update_grid_information(self):
        # Legacy method that reads from sender
        layout = getattr(self.sender(), 'layout', None)
        if layout is None:
            return
        field_selector = getattr(layout, 'field_selector', None)
        cell_size = getattr(layout, 'cell_size', None)
        if field_selector and cell_size:
            self._update_grid_information(layout, field_selector, cell_size)

    def get_value_from_widget(self, widget):
        return self._get_value_from_widget(widget)

    def set_xml_children(self, layout, parent):
        return self._set_xml_children(layout, parent)

    @staticmethod
    def get_grid_widgets(layout):
        return TaskDataMixin._get_grid_widgets(layout)


class GenerateIsoxmlController(TaskDataMixin):
    """Controller for static UI-based Generate ISOXML tabs."""

    def __init__(self, dock_widget, parent_gdf=None):
        self.dock_widget = dock_widget
        self.parent_gdf = parent_gdf
        self.commands = GenerateTaskCommands(self.parent_gdf if self.parent_gdf is not None else self)
        self._init_taskdata_state()
        self._load_schemas()
        self.middle_layout = None

        self._connect_recipe_tab()
        self._connect_metadata_tabs()
        self._refresh_all_metadata_tables()

    def _connect_recipe_tab(self):
        """Wire up the Recipe tab buttons to handlers."""
        dw = self.dock_widget

        if hasattr(dw, 'layoutRecipeContent'):
            self.middle_layout = dw.layoutRecipeContent

        if hasattr(dw, 'tableRecipe'):
            self.recipe_table = dw.tableRecipe
            self.recipe_table.horizontalHeader().setStretchLastSection(True)
            self._refresh_recipe_table()

        if hasattr(dw, 'btnNewRecipe'):
            dw.btnNewRecipe.clicked.connect(self.create_new_recipe)
        if hasattr(dw, 'btnLoadRecipe'):
            dw.btnLoadRecipe.clicked.connect(self.load_recipe)
        if hasattr(dw, 'btnLoadSelected'):
            dw.btnLoadSelected.clicked.connect(self._load_selected_recipe)
        if hasattr(dw, 'btnResetRecipe'):
            dw.btnResetRecipe.clicked.connect(self.reset_recipe)
        if hasattr(dw, 'btnRefreshRecipes'):
            dw.btnRefreshRecipes.clicked.connect(self._refresh_recipe_table)
        if hasattr(dw, 'btnCreateFile'):
            dw.btnCreateFile.clicked.connect(self.store_data)

    def _refresh_recipe_table(self):
        """Refresh the recipe table with .recipe files from the recipes folder."""
        if not hasattr(self, 'recipe_table') or self.recipe_table is None:
            return
        self.recipe_table.setRowCount(0)
        recipes_dir = os.path.join(os.path.dirname(__file__), 'recipes')
        if not os.path.isdir(recipes_dir):
            return
        for filename in os.listdir(recipes_dir):
            if filename.endswith('.recipe'):
                row = self.recipe_table.rowCount()
                self.recipe_table.insertRow(row)
                name_item = QTableWidgetItem(filename.replace('.recipe', ''))
                path_item = QTableWidgetItem(os.path.join(recipes_dir, filename))
                self.recipe_table.setItem(row, 0, name_item)
                self.recipe_table.setItem(row, 1, path_item)

    def _load_selected_recipe(self):
        """Load the recipe selected in the recipe table."""
        if not hasattr(self, 'recipe_table') or self.recipe_table is None:
            return
        if self.recipe_table.currentRow() < 0:
            QMessageBox.information(self.dock_widget, 'No Selection', 'Please select a recipe from the table.')
            return
        path_item = self.recipe_table.item(self.recipe_table.currentRow(), 1)
        if path_item is None:
            return
        file_path = path_item.text()
        self._load_recipe_from_path(file_path)

    def _connect_metadata_tabs(self):
        """Wire up the metadata tab buttons to handlers."""
        dw = self.dock_widget

        for meta_type in self.META_CONFIG.keys():
            btn_add = getattr(dw, f'btnAdd{meta_type}', None)
            if btn_add:
                btn_add.clicked.connect(lambda checked, t=meta_type: self._add_metadata(t))

            btn_edit = getattr(dw, f'btnEdit{meta_type}', None)
            if btn_edit:
                btn_edit.clicked.connect(lambda checked, t=meta_type: self._edit_metadata(t))

            btn_remove = getattr(dw, f'btnRemove{meta_type}', None)
            if btn_remove:
                btn_remove.clicked.connect(lambda checked, t=meta_type: self._remove_metadata(t))

    def _get_table(self, meta_type):
        """Get the QTableWidget for a metadata type."""
        return getattr(self.dock_widget, f'table{meta_type}', None)

    def _refresh_all_metadata_tables(self):
        """Refresh all metadata tables."""
        for meta_type in self.META_CONFIG.keys():
            self._refresh_metadata_table(meta_type)

    def _refresh_metadata_table(self, meta_type):
        """Reload table data from XML file."""
        table = self._get_table(meta_type)
        if table is None:
            return

        xml_file, attrs = self.META_CONFIG[meta_type]
        this_dir = os.path.dirname(__file__)
        xml_path = os.path.join(this_dir, 'meta_data', xml_file)

        table.setRowCount(0)
        try:
            tree = ET.parse(xml_path)
            for child in tree.getroot():
                row = table.rowCount()
                table.insertRow(row)
                for col, attr in enumerate(attrs):
                    value = child.tag if attr == 'tag' else child.attrib.get(attr, '')
                    table.setItem(row, col, QTableWidgetItem(value))
        except Exception:
            pass

    def _add_metadata(self, meta_type):
        """Open MetaData dialog to add new item."""
        schema_key = self.SCHEMA_KEYS.get(meta_type)
        dlg = MetaData(self.dock_widget, meta_type, self.schemas.get(schema_key))
        dlg.exec()
        self._refresh_metadata_table(meta_type)

    def _edit_metadata(self, meta_type):
        """Open MetaData dialog to edit selected item."""
        table = self._get_table(meta_type)
        if table is None or table.currentRow() < 0:
            return
        schema_key = self.SCHEMA_KEYS.get(meta_type)
        dlg = MetaData(self.dock_widget, meta_type, self.schemas.get(schema_key))
        item_id = table.item(table.currentRow(), 0).text()
        for i in range(dlg.available_items_table_widget.count()):
            if dlg.available_items_table_widget.item(i).text().startswith(item_id):
                dlg.available_items_table_widget.setCurrentRow(i)
                dlg.edit_item()
                break
        dlg.exec()
        self._refresh_metadata_table(meta_type)

    def _remove_metadata(self, meta_type):
        """Remove selected metadata item."""
        table = self._get_table(meta_type)
        if table is None or table.currentRow() < 0:
            return
        item_id = table.item(table.currentRow(), 0).text()

        try:
            yes_btn = QMessageBox.StandardButton.Yes
            no_btn = QMessageBox.StandardButton.No
        except AttributeError:
            yes_btn = QMessageBox.Yes
            no_btn = QMessageBox.No

        reply = QMessageBox.question(
            self.dock_widget, 'Confirm Delete',
            f'Remove {meta_type} "{item_id}"?',
            yes_btn | no_btn
        )
        if reply != yes_btn:
            return

        xml_file, _ = self.META_CONFIG[meta_type]
        xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', xml_file)
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for child in list(root):
                if child.tag == item_id:
                    root.remove(child)
                    break
            try:
                ET.indent(root, space='    ')
            except AttributeError:
                pass
            with open(xml_path, 'wb') as f:
                f.write(ET.tostring(root, encoding='unicode').encode('utf-8'))
        except Exception:
            pass
        self._refresh_metadata_table(meta_type)

    def create_new_recipe(self):
        """Create a new recipe."""
        self.commands.create_new_recipe(on_recipe_saved=self._load_recipe_from_path)

    def reset_recipe(self):
        """Reset the current recipe."""
        self.added_rows = {}
        self.id_list = {}
        self.idref_widgets = {}
        self.save_temp = {}
        if self.middle_layout is not None:
            item = self.middle_layout.itemAt(0)
            if item is not None:
                widget = item.widget()
                if widget:
                    widget.close()
                self.middle_layout.removeItem(item)
                del item
        self.frame_stack = {}

    def load_recipe(self):
        """Load a recipe from file dialog."""
        opts = QFileDialog.Options()
        dont_native = getattr(QFileDialog, 'DontUseNativeDialog', None)
        if dont_native is not None:
            try:
                opts |= dont_native
            except Exception:
                pass
        file = QFileDialog.getOpenFileName(self.dock_widget, "Open Recipe", "", 'Recipes (*.recipe)', options=opts)[0]
        if not file:
            return
        self._load_recipe_from_path(file)

    def _load_recipe_from_path(self, file_path: str):
        """Load a recipe from the given file path."""
        try:
            tree = ET.parse(file_path)
        except Exception as e:
            QMessageBox.information(self.dock_widget, 'Error', f'Failed to open recipe:\n{e}')
            return
        parent_dict = etree_to_dict(tree.getroot())['ISO11783_TaskData']
        scroll_area = QScrollArea()
        scroll_area.setVerticalScrollBarPolicy(_scroll_bar_policy('ScrollBarAlwaysOn'))
        scroll_area.setHorizontalScrollBarPolicy(_scroll_bar_policy('ScrollBarAlwaysOff'))
        scroll_area.setWidgetResizable(True)

        self.q_layout = QGridLayout()
        widget = QFrame()
        widget.setLayout(self.q_layout)
        self.reset_recipe()
        for key, item in parent_dict.items():
            if item is None:
                continue
            self._walk_dict(item, key, self.q_layout, widget)

        scroll_area.setWidget(widget)
        scroll_area.show()
        if self.middle_layout is not None:
            self.middle_layout.addWidget(scroll_area)

        self._update_ref_ids()

    def store_data(self):
        """Store the recipe data to file."""
        if self.q_layout is None:
            QMessageBox.information(self.dock_widget, 'Error', 'No recipe loaded to save')
            return
        path = QFileDialog.getSaveFileName(self.dock_widget, 'Save TaskData', filter='xml (*.xml)')[0]
        if not path:
            return
        schemas_layout = self.q_layout
        et_parents = ET.Element('ISO11783_TaskData')
        et_parents.set("VersionMajor", "2")
        et_parents.set("VersionMinor", "0")
        et_parents.set("ManagementSoftwareManufacturer", "GeoDataFarm")
        et_parents.set("ManagementSoftwareVersion", str(__version__))
        et_parents.set("TaskControllerManufacturer", "GeoDataFarm")
        et_parents.set("TaskControllerVersion", str(__version__))
        et_parents.set("DataTransferOrigin", "1")
        for row in range(schemas_layout.rowCount()):
            sub_layout = schemas_layout.itemAtPosition(row, 0)
            if sub_layout is None:
                continue
            if type(sub_layout.widget().layout()) == QGridLayout:
                inner_layout = sub_layout.widget().layout()
                key = sub_layout.widget().layout().key
                xml_sub = ET.SubElement(et_parents, key)
                for j in range(inner_layout.rowCount()):
                    if type(inner_layout.itemAtPosition(j, 0)) == QHBoxLayout:
                        widget = inner_layout.itemAtPosition(j, 0).itemAt(1).widget()
                        # Skip widgets without schema (e.g., metadata selectors, field selectors)
                        if widget is None or not hasattr(widget, 'schema'):
                            continue
                        schema = widget.schema
                        if not isinstance(schema, dict) or key not in schema:
                            continue
                        attr = schema[key]
                        value = self._get_value_from_widget(widget)
                        xml_sub.set(attr, str(value))
                    else:
                        if inner_layout.itemAtPosition(j, 0) is not None:
                            if type(inner_layout.itemAtPosition(j, 0).widget()) == QFrame:
                                self._set_xml_children(inner_layout.itemAtPosition(j, 0).widget().layout(), xml_sub)
                # Special handling for GRD: add G (filename) and H (file length) from save_temp
                if key == 'GRD' and 'GRD' in self.save_temp and self.save_temp['GRD']:
                    grd_id = getattr(inner_layout, 'id', 1)
                    if grd_id in self.save_temp['GRD']:
                        df = self.save_temp['GRD'][grd_id]
                        file_length = len(df) * 4  # 4 bytes per cell (int32)
                        xml_sub.set('G', f'GRD{grd_id:05d}')
                        xml_sub.set('H', str(file_length))
        try:
            ET.indent(et_parents, space='    ', level=0)
        except AttributeError:
            pass
        with open(path, 'w') as f:
            f.write(ET.tostring(et_parents, encoding='unicode'))
        self._save_temp_files(os.path.dirname(path))
