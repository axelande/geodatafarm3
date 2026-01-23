import os
import struct
import json
import xml.etree.ElementTree as ET

import geopandas as gpd
import geopy.distance
from qgis.PyQt.QtWidgets import (QLabel, QWidget, QPushButton, QVBoxLayout, QComboBox,
                                 QLineEdit, QHBoxLayout, QCheckBox, QFrame, QScrollArea, QFileDialog,
                                 QGridLayout, QDoubleSpinBox, QSpinBox, QMessageBox, QInputDialog,
                                 QTabWidget, QTableWidget, QTableWidgetItem, QSizePolicy)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsVectorLayer, QgsFeature, QgsGeometry

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
from..qt_data import _scroll_bar_policy, _check_state, _alignment, _match_flag
__version__ = 0.1


def distance(p1, p2):
    x = p1.y, p1.x
    y = p2.y, p2.x
    return geopy.distance.geodesic(x, y).m


class GenerateTaskDataWidget(QWidget):
    def __init__(self, parent=None, parent_gdf=None):
        # accept non-QWidget parents in tests (e.g., SimpleNamespace), only pass a QWidget to QWidget.__init__
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)
        self.parent_gdf = parent_gdf
        # command helpers (separate file). Prefer the plugin-level `parent_gdf`
        # when available so the commands helper can read `test_mode` and other
        # flags from the plugin instance. Fallback to the widget itself.
        self.commands = GenerateTaskCommands(self.parent_gdf if self.parent_gdf is not None else self)
        self.schemas = {}
        self.load_schemas()
        self.added_rows = {}
        self.id_list = {}
        self.idref_widgets = {}
        self.save_temp = {}
        self.frame_stack = {}

        self.file_version_input = 2.1
        self.software_version = __version__
        self.software_manufacture = 'GeoDataFarm'
        self.data_transfer_origin = 1

        # Create top-level tab widget with 5 tabs
        self.main_tabs = QTabWidget()

        # Tab 1: Recipe tab (contains existing functionality)
        self.recipe_tab = self._create_recipe_tab()
        self.main_tabs.addTab(self.recipe_tab, 'Recipe')

        # Tabs 2-11: Metadata tabs
        self.metadata_tables = {}
        for meta_type in ['Farm', 'Customer', 'Worker', 'Device', 'Product', 'ProductGroup',
                          'ValuePresentation', 'CulturalPractice', 'OperationTechnique', 'CropType', 'CodedCommentGroup']:
            tab = self._create_metadata_tab(meta_type)
            self.main_tabs.addTab(tab, meta_type)

        # Set the main_tabs as the only child by setting a layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # No margins
        layout.addWidget(self.main_tabs)
        self.setLayout(layout)

        # Set size policy to expand and fill available space
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def show_generate_menu(self, anchor_widget=None):
        # Legacy hook used by GeoDataFarm.open_generate_menu; kept as no-op
        return None

    def _create_recipe_tab(self):
        """Create the Recipe tab with existing functionality."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Intro text
        intro_text = QLabel('Welcome to GeoDataFarm Taskdata file generator')

        # Action buttons row
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

        # Middle frame (recipe content area)
        self.middle_layout = QVBoxLayout()
        self.middle_frame = QFrame()
        self.middle_frame.setFrameShape(QFrameStyledPanel)
        self.middle_frame.setLayout(self.middle_layout)

        # Create file button
        self.run_create_file = QPushButton('Create file')
        self.run_create_file.clicked.connect(self.store_data)

        layout.addWidget(intro_text)
        layout.addLayout(action_layout)
        layout.addWidget(self.middle_frame, 1)  # stretch factor 1 to expand
        layout.addWidget(self.run_create_file)

        return widget

    def _create_metadata_tab(self, meta_type):
        """Create a tab with table and buttons for a metadata type."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Define columns per type
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

        # Buttons row
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

        layout.addWidget(table, 1)  # stretch factor 1 to expand
        layout.addLayout(btn_layout)

        self._refresh_metadata_table(meta_type)
        return widget

    def _refresh_metadata_table(self, meta_type):
        """Reload table data from XML file."""
        file_map = {
            'Farm': 'FRMs.xml',
            'Customer': 'CTRs.xml',
            'Worker': 'WKRs.xml',
            'Device': 'DVCs.xml',
            'Product': 'PDTs.xml',
            'ProductGroup': 'PGPs.xml',
            'ValuePresentation': 'VPNs.xml',
            'CulturalPractice': 'CPCs.xml',
            'OperationTechnique': 'OTQs.xml',
            'CropType': 'CTPs.xml',
            'CodedCommentGroup': 'CCGs.xml'
        }
        table_info = self.metadata_tables[meta_type]
        table = table_info['table']
        attrs = table_info['attrs']

        this_dir = os.path.dirname(__file__)
        xml_path = os.path.join(this_dir, 'meta_data', file_map[meta_type])

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
        schema_key = {
            'Farm': 'FRM', 'Customer': 'CTR', 'Worker': 'WKR', 'Device': 'DVC',
            'Product': 'PDT', 'ProductGroup': 'PGP', 'ValuePresentation': 'VPN',
            'CulturalPractice': 'CPC', 'OperationTechnique': 'OTQ',
            'CropType': 'CTP', 'CodedCommentGroup': 'CCG'
        }[meta_type]
        dlg = MetaData(self, meta_type, self.schemas.get(schema_key))
        dlg.exec()
        self._refresh_metadata_table(meta_type)

    def _edit_metadata(self, meta_type):
        """Open MetaData dialog to edit selected item."""
        table = self.metadata_tables[meta_type]['table']
        if table.currentRow() < 0:
            return
        schema_key = {
            'Farm': 'FRM', 'Customer': 'CTR', 'Worker': 'WKR', 'Device': 'DVC',
            'Product': 'PDT', 'ProductGroup': 'PGP', 'ValuePresentation': 'VPN',
            'CulturalPractice': 'CPC', 'OperationTechnique': 'OTQ',
            'CropType': 'CTP', 'CodedCommentGroup': 'CCG'
        }[meta_type]
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
        # Qt5/Qt6 compatibility for QMessageBox buttons
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
        file_map = {
            'Farm': 'FRMs.xml',
            'Customer': 'CTRs.xml',
            'Worker': 'WKRs.xml',
            'Device': 'DVCs.xml',
            'Product': 'PDTs.xml',
            'ProductGroup': 'PGPs.xml',
            'ValuePresentation': 'VPNs.xml',
            'CulturalPractice': 'CPCs.xml',
            'OperationTechnique': 'OTQs.xml',
            'CropType': 'CTPs.xml',
            'CodedCommentGroup': 'CCGs.xml'
        }
        xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', file_map[meta_type])
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
        # Delegate to commands helper which opens the recipe dialog
        self.commands.create_new_recipe()

    def create_farm(self):
        self.commands.create_farm()

    def create_customer(self):
        self.commands.create_customer()

    def create_worker(self):
        self.commands.create_worker()

    def create_device(self):
        self.commands.create_device()

    def load_schemas(self, schemas_dir: str = None):
        """Store all schemas in the schemas folder as the self.schemas dict.

        Parameters
        ----------
        schemas_dir: Optional path to a directory with .schema files. If None,
                     defaults to the package's ../schemas directory.
        """
        if schemas_dir is None:
            this_folder = os.path.dirname(os.path.abspath(__file__))
            schemas_folder = os.path.normpath(os.path.join(this_folder, '..', 'schemas'))
        else:
            schemas_folder = os.path.abspath(schemas_dir)
        if not os.path.isdir(schemas_folder):
            return
        schemas = os.listdir(schemas_folder)
        for schema in schemas:
            if '.schema' not in schema:
                continue
            self.schemas[schema.split('.')[0]] = json.load(open(os.path.join(schemas_folder, schema)))

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
        # Prefer non-native dialog when available; some PyQt builds lack the flag
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
            self.walk_dict(item, key, self.q_layout, widget)

        scroll_area.setWidget(widget)
        scroll_area.show()
        self.middle_layout.addWidget(scroll_area)

        self.update_ref_ids()

    def walk_dict(self, d_in, key, parent_layout: QGridLayout, parent_frame: QFrame):
        # If multiple child elements with the same tag were parsed, they'll
        # be represented as a list. Handle that by iterating each item and
        # delegating back to this method so downstream code can assume a
        # single-dictionary structure.
        if isinstance(d_in, list):
            for sub in d_in:
                self.walk_dict(sub, key, parent_layout, parent_frame)
            return
        # Handle None or empty d_in
        if d_in is None:
            d_in = {}
        key_frame = QFrame()
        key_layout = QGridLayout()
        key_layout.__setattr__("key", key)
        # Set spacing to prevent widgets from overlapping
        key_layout.setSpacing(2)
        key_layout.setContentsMargins(5, 2, 5, 2)
        key_frame.setLayout(key_layout)

        extra_id = self.find_extra_id(d_in, key)
        # Add checkbox first - it will be added at the next available row
        self.add_schema_checkbox(key, key_frame, parent_layout, parent_frame, key_layout, d_in, str(extra_id))
        if d_in and 'attr' in d_in.keys():
            height = self.set_widget(d_in, key, key_layout, extra_id)
        else:
            height = 50
        # Don't set minimum height - let the layout manage sizing automatically
        # key_frame.setMinimumHeight(height)
        # Add frame at the next available row after checkbox, spanning 3 columns (matching attribute widgets)
        # Use rowCount() to get the current next available row (checkbox was just added)
        parent_layout.addWidget(key_frame, parent_layout.rowCount(), 0, 1, 3)
        self.frame_stack[key_frame] = {'parent_frame': parent_frame, 'height': height, 'key': key}
        # Don't set maximum height here - let update_ref_ids calculate total height including children

        for key_d in d_in.keys():
            if key_d == 'attr':
                continue
            else:
                self.walk_dict(d_in[key_d], key_d, key_layout, key_frame)

    def set_widget(self, d_in: dict, key: str, key_layout: QGridLayout, extra_id: int) -> int:
        size = 65  # Should include space for checkbox etc.
        if key in ['GRD']:
            self.add_file_input(key, d_in['attr'][6], 'G', key_layout, extra_id)
            size += 25
        # Add metadata selector for CTR, DVC, FRM schemas
        if key in ['CTR', 'DVC', 'FRM']:
            self.add_metadata_selector(key, key_layout)
            size += 25
        # Add field selector for PFD schema
        if key == 'PFD':
            self.add_pfd_field_selector(key_layout)
            size += 25
        for attr_name in d_in['attr']:
            item = self.schemas[key][attr_name]
            type_ = item["Type"].lower()
            name = ''.join(' ' + char if char.isupper() else char.strip() for char in item['Attribute_name']).strip()
            if type_ in ['xs:id', 'xs:ref_code_parent']:
                continue
            elif 'string' in type_ or 'hexbinary' in type_:
                widget = QLineEdit(self, toolTip=item['comment'], minimumHeight=20, maximumWidth=200)
                self.add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'long' in type_ or 'short' in type_ or 'byte' in type_:
                widget = QSpinBox(self, toolTip=item['comment'], minimumHeight=20, maximum=100000, maximumWidth=50)
                self.add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'decimal' in type_ or 'double' in type_:
                widget = QDoubleSpinBox(self, toolTip=item['comment'], decimals=6, maximum=100000, minimumHeight=20, maximumWidth=50)
                self.add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'xs:idref' in type_ or 'xs:ref_code_child' in type_:
                if item['Ref_id'] == 'CTR':
                    md = MetaData()
                    widget = md.get_ctr_widgets(schema='CTR')
                else:
                    widget = QComboBox(self, minimumHeight=20, maximumWidth=200)
                self.add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
                self.idref_widgets[widget] = item['Ref_id']
                if item['Ref_id'] not in self.id_list.keys():
                    self.id_list[item['Ref_id']] = [0]
            elif 'xs:nmtoken' in type_:
                widget = QComboBox(self, minimumHeight=20, maximumWidth=200)
                widget.addItems(item['nm_list'])
                self.add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            else:
                print(item["Type"], key, attr_name)
            size += 21
        return size

    def find_extra_id(self, d_in, key) -> object:
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

    def update_ref_ids(self):
        for widget, ref in self.idref_widgets.items():
            items = []
            widget.clear()
            # First add IDs from the current recipe
            for i in self.id_list[ref]:
                items.append(ref + str(i + 1))
            # Then add existing metadata from XML files
            existing_items = self._get_existing_metadata_items(ref)
            for existing_id, display_name in existing_items:
                if existing_id not in items:
                    items.append(f'{existing_id} - {display_name}')
            widget.addItems(items)

    def _get_existing_metadata_items(self, schema_key: str) -> list:
        """Load existing metadata items from XML files.

        Returns a list of tuples (id, display_name) for the given schema key.
        """
        file_map = {
            'FRM': 'FRMs.xml',
            'CTR': 'CTRs.xml',
            'WKR': 'WRKs.xml',
            'DVC': 'DVCs.xml',
            'PDT': 'PDTs.xml',
            'PGP': 'PGPs.xml',
            'VPN': 'VPNs.xml',
            'CPC': 'CPCs.xml',
            'OTQ': 'OTQs.xml',
            'CTP': 'CTPs.xml',
            'CCG': 'CCGs.xml',
            'TZN': None,  # TZN is task-specific, no global XML
            'PFD': None,  # PFD is task-specific
        }
        if schema_key not in file_map or file_map[schema_key] is None:
            return []
        xml_file = file_map[schema_key]
        xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', xml_file)
        items = []
        try:
            tree = ET.parse(xml_path)
            for child in tree.getroot():
                # Use attribute B as display name (usually the designator/name)
                display_name = child.attrib.get('B', '')
                items.append((child.tag, display_name))
        except Exception:
            pass
        return items
        # Don't set explicit heights - let Qt's layout system handle sizing automatically
        # The previous implementation was setting maximum heights that prevented frames from
        # expanding to show all their children, causing overlapping widgets
        # for parent_frame in reversed(self.frame_stack.keys()):
        #     self.frame_stack[parent_frame]['children_height'] = 0
        #     for frame in self.frame_stack.keys():
        #         if self.frame_stack[frame]['parent_frame'] == parent_frame:
        #             if 'children_height' not in self.frame_stack[frame]:
        #                 self.frame_stack[frame]['children_height'] = 0
        #             self.frame_stack[parent_frame]['children_height'] += self.frame_stack[frame]['height'] + self.frame_stack[frame]['children_height']
        #     total_height = self.frame_stack[parent_frame]['height'] + self.frame_stack[parent_frame]['children_height']
        #     parent_frame.setMinimumHeight(total_height)
        #     parent_frame.setMaximumHeight(total_height)

    def add_schema_checkbox(self, name: str, frame: QFrame, layout, parent_frame: QFrame, key_layout,
                            d_in: dict, extra_id: str = ''):
        check_box = QCheckBox(text=name + extra_id)
        check_box.__setattr__("frame", frame)
        check_box.setCheckState(_check_state('Checked'))
        check_box.toggled.connect(self.show_frame)
        add_line_push_button = QPushButton(self, text='+', maximumWidth=25)
        remove_line_push_button = QPushButton(self, text='-', maximumWidth=25)
        add_line_push_button.__setattr__("layout", key_layout)
        add_line_push_button.__setattr__("parent_layout", layout)
        add_line_push_button.__setattr__("parent_frame", parent_frame)
        add_line_push_button.__setattr__("key", name)
        add_line_push_button.__setattr__("d_in", d_in)
        remove_line_push_button.__setattr__("parent_layout", layout)

        remove_line_push_button.clicked.connect(self.remove_extra_row)
        add_line_push_button.clicked.connect(self.add_extra_row)

        # Add checkbox and buttons to a new row, spanning all available columns
        current_row = layout.rowCount()
        layout.addWidget(check_box, current_row, 0, 1, 1)
        layout.addWidget(add_line_push_button, current_row, 1, 1, 1)
        layout.addWidget(remove_line_push_button, current_row, 2, 1, 1)
        # If this is an LSG (line/string group) allow selecting polygon type
        # and optionally a field to use for population. The field selector is
        # hidden until 'Partfield Boundary' is chosen.
        if name == 'LSG':
            try:
                poly_type_cb = QComboBox()
                poly_type_cb.addItems(['', 'Partfield Boundary', 'PolygonExterior', 'PolygonInterior'])
                poly_type_cb.__setattr__('is_polygon_type', True)
                field_selector = QComboBox()
                field_selector.__setattr__('is_field_selector', True)
                field_selector.setVisible(False)
                # Populate fields from dock widget's LWFields
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
                if lw is not None:
                    try:
                        items = [lw.item(j).text() for j in range(lw.count())]
                        field_selector.addItems(items)
                    except Exception:
                        pass

                def _on_poly_type_changed(idx, cb=poly_type_cb, fs=field_selector):
                    try:
                        text = cb.currentText()
                        if text == 'Partfield Boundary':
                            fs.setVisible(True)
                        else:
                            fs.setVisible(False)
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

    def show_frame(self):
        frame = self.sender().frame
        if frame.isHidden():
            frame.show()
        else:
            frame.hide()

    def add_input_widget(self, key, name, attr, layout: QGridLayout = None, widget=None):
        field_name_label = QLabel(self, text=name + ': ')
        widget.__setattr__("schema", {key: attr})
        widget.__setattr__("attr_name", attr)
        field_name_layout = QHBoxLayout()
        field_name_layout.setAlignment(_alignment('AlignLeft'))
        field_name_layout.setContentsMargins(0, 0, 0, 0)
        field_name_layout.addWidget(field_name_label)
        field_name_layout.addWidget(widget)
        rows = layout.rowCount()
        # Span the input across three columns so widgets align to the left
        layout.addLayout(field_name_layout, rows, 0, 1, 3)

    def add_file_input(self, key, item, attr_name, layout: QGridLayout, extra_id: int):
        file_input_label = QLabel(self, text=f'{key}: ')
        layout.__setattr__('id', extra_id)
        # For GRD prefer selecting an existing field + cell size (meters),
        # with an 'Update information' button to compute grid attributes.
        # For other keys keep simple button.
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
            # Populate fields from dock widget's LWFields
            # First try self.dock_widget directly (if set)
            # Then try parent_gdf.dock_widget
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
            if lw is not None:
                try:
                    items = [lw.item(j).text() for j in range(lw.count())]
                    field_selector.addItems(items)
                except Exception:
                    pass

            update_button = QPushButton(text='Update information', minimumHeight=20)
            update_button.__setattr__("layout", layout)
            update_button.__setattr__("schema", {key: attr_name})
            update_button.clicked.connect(self.update_grid_information)

            grid_label = QLabel(self, text='grid size:')

            input_layout = QHBoxLayout()
            input_layout.setAlignment(_alignment('AlignLeft'))
            input_layout.setContentsMargins(0, 0, 0, 0)
            input_layout.addWidget(file_input_label)
            input_layout.addWidget(field_selector)
            input_layout.addWidget(grid_label)
            input_layout.addWidget(cell_size)
            input_layout.addWidget(update_button)
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
        # Span the file input across three columns to align with other rows
        layout.addLayout(input_layout, rows, 0, 1, 3)

    def add_metadata_selector(self, key: str, layout: QGridLayout):
        """Add a combobox to select from existing metadata and populate fields."""
        label = QLabel(self, text=f'Select existing {key}:')
        selector = QComboBox(self)
        selector.setMinimumWidth(150)
        selector.__setattr__('is_metadata_selector', True)
        selector.__setattr__('schema_key', key)

        # Map schema key to metadata file
        file_map = {
            'CTR': 'CTRs.xml',
            'DVC': 'DVCs.xml',
            'FRM': 'FRMs.xml',
        }
        # Populate from existing metadata
        selector.addItem('')  # Empty option for manual entry
        if key in file_map:
            xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', file_map[key])
            try:
                tree = ET.parse(xml_path)
                for child in tree.getroot():
                    display_name = child.attrib.get('B', '')
                    selector.addItem(f'{child.tag} - {display_name}')
            except Exception:
                pass

        populate_button = QPushButton(self, text='Populate', minimumHeight=20)
        populate_button.__setattr__('layout', layout)
        populate_button.__setattr__('schema_key', key)
        populate_button.__setattr__('selector', selector)
        populate_button.clicked.connect(self.populate_from_metadata)

        rows = layout.rowCount()
        layout.addWidget(label, rows, 0)
        layout.addWidget(selector, rows, 1)
        layout.addWidget(populate_button, rows, 2)

    def add_pfd_field_selector(self, layout: QGridLayout):
        """Add a field selector for PFD that reads from dock_widget.LWFields."""
        label = QLabel(self, text='Select field:')
        field_selector = QComboBox(self)
        field_selector.setMinimumWidth(150)
        field_selector.__setattr__('is_pfd_field_selector', True)

        # Populate fields from dock widget's LWFields
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
        field_selector.addItem('')  # Empty option
        if lw is not None:
            try:
                items = [lw.item(j).text() for j in range(lw.count())]
                field_selector.addItems(items)
            except Exception:
                pass

        populate_button = QPushButton(self, text='Populate from field', minimumHeight=20)
        populate_button.__setattr__('layout', layout)
        populate_button.__setattr__('field_selector', field_selector)
        populate_button.clicked.connect(self.populate_pfd_from_field)

        rows = layout.rowCount()
        layout.addWidget(label, rows, 0)
        layout.addWidget(field_selector, rows, 1)
        layout.addWidget(populate_button, rows, 2)

    def populate_from_metadata(self):
        """Populate form fields from selected metadata item."""
        sender = self.sender()
        layout = getattr(sender, 'layout', None)
        schema_key = getattr(sender, 'schema_key', None)
        selector = getattr(sender, 'selector', None)

        if layout is None or schema_key is None or selector is None:
            return

        selected_text = selector.currentText()
        if not selected_text or ' - ' not in selected_text:
            return

        item_id = selected_text.split(' - ')[0]

        # Map schema key to metadata file
        file_map = {
            'CTR': 'CTRs.xml',
            'DVC': 'DVCs.xml',
            'FRM': 'FRMs.xml',
        }
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

            # Find all input widgets in the layout and populate them
            for r in range(layout.rowCount()):
                for c in range(layout.columnCount()):
                    item = layout.itemAtPosition(r, c)
                    if item is None:
                        continue
                    widget = item.widget()
                    if widget is None:
                        # Check if it's a layout
                        sub_layout = item.layout()
                        if sub_layout is not None:
                            for idx in range(sub_layout.count()):
                                sub_widget = sub_layout.itemAt(idx).widget()
                                self._set_widget_from_xml(sub_widget, xml_item)
                    else:
                        self._set_widget_from_xml(widget, xml_item)
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to populate from metadata: {e}')

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
            # For IDREF comboboxes, try to find the matching item
            idx = widget.findText(attr_value, _match_flag('MatchStartsWith'))
            if idx >= 0:
                widget.setCurrentIndex(idx)

    def populate_pfd_from_field(self):
        """Populate PFD fields from selected field layer."""
        sender = self.sender()
        layout = getattr(sender, 'layout', None)
        field_selector = getattr(sender, 'field_selector', None)

        if layout is None or field_selector is None:
            return

        field_name = field_selector.currentText()
        if not field_name:
            QMessageBox.warning(self, 'Warning', 'Please select a field')
            return

        # Get the field layer from QGIS
        try:
            layers = QgsProject.instance().mapLayersByName(field_name)
            if not layers:
                QMessageBox.warning(self, 'Warning', f'Field layer "{field_name}" not found')
                return
            layer = layers[0]

            # Get field geometry and compute area
            if layer.featureCount() == 0:
                QMessageBox.warning(self, 'Warning', f'Field layer "{field_name}" has no features')
                return

            feature = next(layer.getFeatures())
            geom = feature.geometry()

            # Transform to a projected CRS for accurate area calculation
            source_crs = layer.crs()
            # Use UTM or a suitable projected CRS
            dest_crs = QgsCoordinateReferenceSystem('EPSG:3857')
            transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
            geom.transform(transform)
            area_m2 = int(geom.area())

            # Find and populate the widgets
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

        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to populate from field: {e}')

    def _set_pfd_widget_value(self, widget, field_name: str, area_m2: int):
        """Set PFD widget value based on attribute key."""
        if widget is None:
            return
        attr_key = getattr(widget, 'attr_name', None)
        if attr_key is None:
            return
        # C = PartfieldDesignator (name), D = PartfieldArea
        if attr_key == 'C' and isinstance(widget, QLineEdit):
            widget.setText(field_name)
        elif attr_key == 'D' and isinstance(widget, QSpinBox):
            widget.setValue(area_m2)

    def update_grid_information(self):
        """Update GRD widgets from selected field and provided cell size.

        Reads the `field_selector` and `is_cell_size` widgets from the
        layout attached to the sender button, computes grid attributes
        using `_compute_grid_attrs_from_layer` and writes values back to
        the visible attribute widgets.
        """
        layout = getattr(self.sender(), 'layout', None)
        if layout is None:
            return
        field_name = None
        cell_size_m = None
        for r in range(layout.rowCount()):
            sub_item = layout.itemAtPosition(r, 0)
            if sub_item is None:
                continue
            # `itemAtPosition` may return a QLayoutItem that wraps a layout,
            # or in some Qt versions the layout directly. Normalize to a
            # QLayout-like object so we can iterate child widgets.
            sub_layout = None
            try:
                # QLayoutItem has a layout() method
                sub_layout = sub_item.layout()
            except Exception:
                sub_layout = None
            if sub_layout is None:
                # maybe `sub_item` is already a layout
                sub_layout = sub_item
            try:
                count = sub_layout.count()
            except Exception:
                continue
            for idx in range(count):
                try:
                    child_item = sub_layout.itemAt(idx)
                    if child_item is None:
                        continue
                    w = child_item.widget()
                    if w is None:
                        continue
                except Exception:
                    continue
                if hasattr(w, 'is_field_selector'):
                    try:
                        field_name = w.currentText()
                    except Exception:
                        field_name = None
                if hasattr(w, 'is_cell_size'):
                    try:
                        cell_size_m = float(w.value())
                    except Exception:
                        cell_size_m = None
        if not field_name or not cell_size_m:
            return
        layer = self._find_layer_for_field(field_name)
        if layer is None:
            return
        grd_attrs = self._compute_grid_attrs_from_layer(layer, cell_size_m)
        widgets = self.get_grid_widgets(layout)
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

    def _save_temp_files(self, path):
        for key in self.save_temp.keys():
            for id_ in self.save_temp[key]:
                df = self.save_temp[key][id_]
                with open(f'{path}/{key}{id_:04d}.bin', 'wb') as f:
                    for index, row in df.iterrows():
                        for col in df.columns:
                            f.write(struct.pack('L', row[col]))

    @staticmethod
    def get_grid_widgets(layout) -> dict:
        widgets = {}
        for row in range(layout.rowCount()):
            item = layout.itemAtPosition(row, 0)
            if item is None:
                continue
            # Normalize to a layout object (some Qt versions return a QLayoutItem)
            sub_layout = None
            try:
                sub_layout = item.layout()
            except Exception:
                sub_layout = item
            if sub_layout is None:
                continue
            # Try the common case: second widget in the HBox is the input
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
            # Fallback: iterate all children looking for a widget with a schema
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

    def add_extra_row(self):
        key = self.sender().key
        d_in = self.sender().d_in
        parent_layout = self.sender().parent_layout
        parent_frame = self.sender().parent_frame
        row_count_before = parent_layout.rowCount()
        self.walk_dict(d_in, key, parent_layout, parent_frame)
        if parent_layout not in self.added_rows.keys():
            self.added_rows[parent_layout] = []
        now_added = []
        for i in range(row_count_before, parent_layout.rowCount()):
            now_added.append(i)
        self.added_rows[parent_layout].append(now_added)
        self.update_ref_ids()

    def remove_extra_row(self):
        parent_layout: QGridLayout = self.sender().parent_layout
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
                except Exception as e:
                    print(e)
                    pass
        self.added_rows[parent_layout] = self.added_rows[parent_layout][:-1]

    def store_data(self):
        # Ensure a recipe/layout is loaded before asking for a file path
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
        et_parents.set("TaskControllerManufacturer", "GeoDataFarm" )
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
                        attr = inner_layout.itemAtPosition(j, 0).itemAt(1).widget().schema[key]
                        value = self.get_value_from_widget(inner_layout.itemAtPosition(j, 0).itemAt(1).widget())
                        xml_sub.set(attr, str(value))
                    else:
                        if inner_layout.itemAtPosition(j, 0) is not None:
                            if type(inner_layout.itemAtPosition(j, 0).widget()) == QFrame:
                                self.set_xml_children(inner_layout.itemAtPosition(j, 0).widget().layout(), xml_sub)
        try:
            ET.indent(et_parents, space='    ', level=0)
        except AttributeError:
            pass
        with open(path, 'w') as f:
            f.write(ET.tostring(et_parents, encoding='unicode'))
        self._save_temp_files(os.path.dirname(path))

    def get_value_from_widget(self, widget) -> str:
        if type(widget) in [QSpinBox, QDoubleSpinBox]:
            value = str(widget.value())
        elif type(widget) == QLineEdit:
            value = widget.text()
        elif type(widget) == QComboBox:
            # Check if this is an IDREF widget (references another element)
            if widget in self.idref_widgets:
                # Extract the ID from the display text (e.g., "FRM1 - hörte" -> "FRM1")
                text = widget.currentText()
                if ' - ' in text:
                    value = text.split(' - ')[0]
                else:
                    value = text
            else:
                # For NMTOKEN, use the current index
                value = widget.currentIndex()
        elif type(widget) == QPushButton:
            value = widget.value
        else:
            raise MsgError('Could not find the widget type')
        return value

    def set_xml_children(self, layout: QGridLayout, parent: ET.Element):
        key = layout.key
        xml_sub = ET.SubElement(parent, key)
        for i in range(layout.rowCount()):
            item = layout.itemAtPosition(i, 0)
            if item is not None:
                if type(item) == QHBoxLayout:
                    attr = item.itemAt(1).widget().schema[key]
                    value = self.get_value_from_widget(item.itemAt(1).widget())
                    xml_sub.set(attr, str(value))
                else:
                    if type(item.widget()) == QFrame:
                        child_layout = item.widget().layout()

                        # Special handling for Partfield LSG -> PNT population
                        if getattr(child_layout, 'key', '') == 'LSG':
                            try:
                                # Prefer a selected field stored on the parent frame (set by the UI),
                                # otherwise fall back to prompting the user.
                                field_name = None
                                # find the owning frame for this child_layout
                                owner_frame = None
                                for fr in self.frame_stack.keys():
                                    try:
                                        if fr.layout() == child_layout:
                                            owner_frame = fr
                                            break
                                    except Exception:
                                        continue
                                if owner_frame is not None and hasattr(owner_frame, 'selected_field'):
                                    field_name = getattr(owner_frame, 'selected_field')
                                else:
                                    # try prompting
                                    try:
                                        if getattr(self, 'parent_gdf', None) is not None and hasattr(self.parent_gdf, 'dock_widget'):
                                            lw = getattr(self.parent_gdf.dock_widget, 'LWFields', None)
                                            if lw is not None and lw.count() > 0:
                                                items = [lw.item(j).text() for j in range(lw.count())]
                                                if items:
                                                    field_name, ok = QInputDialog.getItem(self, 'Select Partfield', 'Select field to use for Partfield points', items, 0, False)
                                                    if not ok:
                                                        field_name = None
                                    except Exception:
                                        field_name = None
                                if field_name:
                                    layer = self._find_layer_for_field(field_name)
                                    if layer is not None:
                                        ptns = self._generate_ptn_elements_from_layer(layer)
                                        for p in ptns:
                                            xml_sub.append(p)
                            except Exception:
                                pass

                        # Special handling for GRD: compute grid attributes from selected field
                        if getattr(child_layout, 'key', '') == 'GRD':
                            try:
                                # Try to read a field selector and cell size from the GRD input layout
                                field_name = None
                                cell_size_m = None
                                for r in range(child_layout.rowCount()):
                                    sub = child_layout.itemAtPosition(r, 0)
                                    if sub is None:
                                        continue
                                    if type(sub) == QHBoxLayout:
                                        # iterate widgets in HBox
                                        for idx in range(sub.count()):
                                            w = sub.itemAt(idx).widget()
                                            if w is None:
                                                continue
                                            if hasattr(w, 'is_field_selector'):
                                                try:
                                                    field_name = w.currentText()
                                                except Exception:
                                                    field_name = None
                                            if hasattr(w, 'is_cell_size'):
                                                try:
                                                    cell_size_m = float(w.value())
                                                except Exception:
                                                    cell_size_m = None

                                # If not found in UI, fall back to prompting
                                if not field_name:
                                    try:
                                        if getattr(self, 'parent_gdf', None) is not None and hasattr(self.parent_gdf, 'dock_widget'):
                                            lw = getattr(self.parent_gdf.dock_widget, 'LWFields', None)
                                            if lw is not None and lw.count() > 0:
                                                items = [lw.item(j).text() for j in range(lw.count())]
                                                if items:
                                                    field_name, ok = QInputDialog.getItem(self, 'Select Grid field', 'Select field to use for Grid generation', items, 0, False)
                                                    if ok:
                                                        cell_size_m, ok2 = QInputDialog.getDouble(self, 'Grid cell size', 'Cell size (meters):', 10.0, 0.01, 100000.0, 2)
                                                        if not ok2:
                                                            cell_size_m = None
                                    except Exception:
                                        field_name = None

                                if field_name and cell_size_m:
                                    layer = self._find_layer_for_field(field_name)
                                    if layer is not None:
                                        grd_attrs = self._compute_grid_attrs_from_layer(layer, cell_size_m)
                                        for k, v in grd_attrs.items():
                                            xml_sub.set(k, str(v))
                            except Exception:
                                pass

                        self.set_xml_children(item.widget().layout(), xml_sub)

    def run(self):
        self.show()

    def _find_layer_for_field(self, field_name: str):
        """Find a map layer whose name matches the given field name.

        Returns QgsVectorLayer or None.
        """
        try:
            # First try loaded map layers
            for layer in QgsProject.instance().mapLayers().values():
                try:
                    if layer.name().startswith(field_name) or layer.name() == field_name:
                        return layer
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback: try fetching the field polygon from the farm database
        try:
            db = None
            if getattr(self, 'parent_gdf', None) is not None:
                db = getattr(self.parent_gdf, 'db', None)
                if db is None:
                    populate = getattr(self.parent_gdf, 'populate', None)
                    if populate is not None:
                        db = getattr(populate, 'db', None)
            if db is None:
                return None

            # Query polygon as WKT
            safe_name = field_name.replace("'", "''")
            sql = f"select ST_AsText(polygon) from fields where field_name = '{safe_name}' limit 1"
            res = db.execute_and_return(sql, return_failure=True)
            if isinstance(res, list) and res and res[0] and res[1][0]:
                # Depending on execute_and_return return format when return_failure=True
                # res may be [True, data]
                if res[0] is True and len(res) > 1:
                    data = res[1]
                    if data and data[0] and data[0][0]:
                        wkt = data[0][0]
                    else:
                        return None
                else:
                    # normal return (without return_failure) yields rows directly
                    wkt = res[0][0]

                if not wkt:
                    return None

                # Create an in-memory polygon layer containing this geometry
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
        return None

    def _copy_geometry(self, geom):
        """Return a safe copy of a QgsGeometry across QGIS versions."""
        try:
            # Preferred if available
            return geom.clone()
        except Exception:
            try:
                # Fallback to WKT round-trip
                return QgsGeometry.fromWkt(geom.asWkt())
            except Exception:
                try:
                    # Last resort: construct via constructor
                    return QgsGeometry(geom)
                except Exception:
                    return geom

    def _generate_ptn_elements_from_layer(self, layer):
        """Generate a list of XML Elements <PNT> from the layer's first feature geometry."""
        elems = []
        try:
            feat = next(layer.getFeatures())
            geom = feat.geometry()
            # transform to WGS84
            crs_src = layer.crs()
            crs_wgs = QgsCoordinateReferenceSystem('EPSG:4326')
            if crs_src != crs_wgs:
                xform = QgsCoordinateTransform(crs_src, crs_wgs, QgsProject.instance())
                try:
                    geom_copy = self._copy_geometry(geom)
                    geom_copy.transform(xform)
                    geom = geom_copy
                except Exception:
                    pass
            # get coordinates (use exterior ring for polygons)
            try:
                pts = geom.asPolygon()[0]
            except Exception:
                try:
                    pts = geom.asPolyline()
                except Exception:
                    pts = []
            for p in pts:
                elem = ET.Element('PNT')
                # PNT attributes: C=PointNorth (lat), D=PointEast (lon)
                lat = p.y()
                lon = p.x()
                elem.set('C', str(lat))
                elem.set('D', str(lon))
                elems.append(elem)
        except Exception:
            pass
        return elems

    def _compute_grid_attrs_from_layer(self, layer, cell_size_m: float) -> dict:
        """Compute GRD attributes from a polygon layer and desired cell size in meters.

        Returns dict of attributes matching the GRD schema.
        """
        attrs = {}
        try:
            feat = next(layer.getFeatures())
            geom = feat.geometry()
            crs_src = layer.crs()
            crs_wgs = QgsCoordinateReferenceSystem('EPSG:4326')
            # transform to WGS84 for output A/B
            xform_to_wgs = QgsCoordinateTransform(crs_src, crs_wgs, QgsProject.instance())
            geom_wgs = self._copy_geometry(geom)
            try:
                geom_wgs.transform(xform_to_wgs)
            except Exception:
                pass
            # centroid lon -> UTM zone
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

            # bounding box in UTM (meters)
            bbox = geom_utm.boundingBox()
            minx = bbox.xMinimum()
            miny = bbox.yMinimum()
            maxx = bbox.xMaximum()
            maxy = bbox.yMaximum()
            width_m = maxx - minx
            height_m = maxy - miny

            # compute columns and rows
            ncols = max(1, int(round(width_m / cell_size_m)))
            nrows = max(1, int(round(height_m / cell_size_m)))

            # convert min corner back to WGS84 for A (north) and B (east):
            # note: A is north (lat), B is east (lon)
            # transform min corner from UTM to WGS84
            xform_utm_to_wgs = QgsCoordinateTransform(crs_utm, crs_wgs, QgsProject.instance())
            # use QgsPointXY
            from qgis.PyQt.QtCore import QVariant
            pmin = QgsProject.instance().instance() if False else None
            # Create a temporary point geometry
            try:
                from qgis.core import QgsPointXY, QgsGeometry
                pt_utm = QgsGeometry.fromPointXY(QgsPointXY(minx, miny))
                pt_utm.transform(xform_utm_to_wgs)
                p = pt_utm.asPoint()
                lat_min = p.y()
                lon_min = p.x()
            except Exception:
                lat_min = lat
                lon_min = lon

            # compute cell size in degrees by mapping a point cell_size_m eastwards in UTM
            try:
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

            attrs['A'] = str(lat_min)
            attrs['B'] = str(lon_min)
            attrs['C'] = str(cell_n_deg)
            attrs['D'] = str(cell_e_deg)
            attrs['E'] = str(ncols)
            attrs['F'] = str(nrows)
            attrs['G'] = 'GRD00001'
            attrs['H'] = '0'
            attrs['I'] = '1'
            attrs['J'] = '0'
        except Exception:
            pass
        return attrs


class GenerateIsoxmlController:
    """Controller for static UI-based Generate ISOXML tabs.

    This class wires up the static widgets defined in the .ui file to the
    existing logic from GenerateTaskDataWidget.
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

    def __init__(self, dock_widget, parent_gdf=None):
        """Initialize the controller with references to the dock widget's UI elements.

        Parameters
        ----------
        dock_widget : GeoDataFarmDockWidget
            The dock widget containing the static UI elements.
        parent_gdf : optional
            Reference to the main GeoDataFarm plugin instance.
        """
        self.dock_widget = dock_widget
        self.parent_gdf = parent_gdf
        self.commands = GenerateTaskCommands(self.parent_gdf if self.parent_gdf is not None else self)

        # Load schemas
        self.schemas = {}
        self._load_schemas()

        # Recipe state
        self.added_rows = {}
        self.id_list = {}
        self.idref_widgets = {}
        self.save_temp = {}
        self.frame_stack = {}
        self.q_layout = None
        self.middle_layout = None

        # Connect UI elements
        self._connect_recipe_tab()
        self._connect_metadata_tabs()

        # Initial data load for metadata tabs
        self._refresh_all_metadata_tables()

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

    def _connect_recipe_tab(self):
        """Wire up the Recipe tab buttons to handlers."""
        dw = self.dock_widget

        # Store reference to the middle layout for recipe content
        if hasattr(dw, 'layoutRecipeContent'):
            self.middle_layout = dw.layoutRecipeContent

        # Store reference to the recipe table
        if hasattr(dw, 'tableRecipe'):
            self.recipe_table = dw.tableRecipe
            self.recipe_table.horizontalHeader().setStretchLastSection(True)
            self._refresh_recipe_table()

        # Connect buttons
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
        print(f'Loading recipe from {file_path}')
        self._load_recipe_from_path(file_path)

    def _connect_metadata_tabs(self):
        """Wire up the metadata tab buttons to handlers."""
        dw = self.dock_widget

        for meta_type in self.META_CONFIG.keys():
            # Connect Add button
            btn_add = getattr(dw, f'btnAdd{meta_type}', None)
            if btn_add:
                btn_add.clicked.connect(lambda checked, t=meta_type: self._add_metadata(t))

            # Connect Edit button
            btn_edit = getattr(dw, f'btnEdit{meta_type}', None)
            if btn_edit:
                btn_edit.clicked.connect(lambda checked, t=meta_type: self._edit_metadata(t))

            # Connect Remove button
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

        # Qt5/Qt6 compatibility for QMessageBox buttons
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

    # Recipe tab methods - delegate to commands helper or implement inline
    def create_new_recipe(self):
        """Create a new recipe."""
        self.commands.create_new_recipe()

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

    def _walk_dict(self, d_in, key, parent_layout: QGridLayout, parent_frame: QFrame):
        """Walk through recipe dict and create UI elements."""
        if isinstance(d_in, list):
            for sub in d_in:
                self._walk_dict(sub, key, parent_layout, parent_frame)
            return
        key_frame = QFrame()
        key_layout = QGridLayout()
        key_layout.__setattr__("key", key)
        key_layout.setSpacing(2)
        key_layout.setContentsMargins(5, 2, 5, 2)
        key_frame.setLayout(key_layout)

        extra_id = self._find_extra_id(d_in, key)
        self._add_schema_checkbox(key, key_frame, parent_layout, parent_frame, key_layout, d_in, str(extra_id))
        if 'attr' in d_in.keys():
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

    def _set_widget(self, d_in: dict, key: str, key_layout: QGridLayout, extra_id: int) -> int:
        """Set up input widgets for a schema key."""
        size = 65
        if key in ['GRD']:
            self._add_file_input(key, d_in['attr'][6], 'G', key_layout, extra_id)
            size += 25
        # Add metadata selector for CTR, DVC, FRM schemas
        if key in ['CTR', 'DVC', 'FRM']:
            self._add_metadata_selector(key, key_layout)
            size += 25
        # Add field selector for PFD schema
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
                widget = QLineEdit(self.dock_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=200)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'unsignedbyte' in type_:
                # unsignedByte: 0-255
                widget = QSpinBox(self.dock_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=80)
                widget.setMinimum(0)
                widget.setMaximum(255)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'unsignedshort' in type_:
                # unsignedShort: 0-65535
                widget = QSpinBox(self.dock_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=80)
                widget.setMinimum(0)
                widget.setMaximum(65535)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'unsignedlong' in type_:
                # unsignedLong: 0 to 4294967295 (but QSpinBox limited to int max)
                widget = QSpinBox(self.dock_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=120)
                widget.setMinimum(0)
                widget.setMaximum(2147483647)  # QSpinBox max
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'long' in type_:
                # xs:long (signed): -2147483648 to 2147483647
                widget = QSpinBox(self.dock_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=120)
                widget.setMinimum(-2147483648)
                widget.setMaximum(2147483647)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'short' in type_:
                # xs:short (signed): -32768 to 32767
                widget = QSpinBox(self.dock_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=80)
                widget.setMinimum(-32768)
                widget.setMaximum(32767)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'byte' in type_:
                # xs:byte (signed): -128 to 127
                widget = QSpinBox(self.dock_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=80)
                widget.setMinimum(-128)
                widget.setMaximum(127)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'decimal' in type_ or 'double' in type_:
                # Decimal/double with 2 decimal places by default
                widget = QDoubleSpinBox(self.dock_widget, toolTip=item['comment'], minimumHeight=20, maximumWidth=120)
                widget.setDecimals(2)
                widget.setMinimum(-999999999.99)
                widget.setMaximum(999999999.99)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            elif 'xs:idref' in type_ or 'xs:ref_code_child' in type_:
                if item['Ref_id'] == 'CTR':
                    md = MetaData()
                    widget = md.get_ctr_widgets(schema='CTR')
                else:
                    widget = QComboBox(self.dock_widget, minimumHeight=20, maximumWidth=200)
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
                self.idref_widgets[widget] = item['Ref_id']
                if item['Ref_id'] not in self.id_list.keys():
                    self.id_list[item['Ref_id']] = [0]
            elif 'nmtoken' in type_:
                # NMTOKEN - use combobox with predefined values from nm_list
                widget = QComboBox(self.dock_widget, minimumHeight=20, maximumWidth=200)
                if 'nm_list' in item:
                    widget.addItems(item['nm_list'])
                self._add_input_widget(key, name, attr_name, layout=key_layout, widget=widget)
            else:
                print(f"Unhandled type: {item['Type']} for {key}.{attr_name}")
            size += 21
        return size

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
            # First add IDs from the current recipe
            for i in self.id_list[ref]:
                items.append(ref + str(i + 1))
            # Then add existing metadata from XML files
            existing_items = self._get_existing_metadata_items(ref)
            for existing_id, display_name in existing_items:
                if existing_id not in items:
                    items.append(f'{existing_id} - {display_name}')
            widget.addItems(items)

    def _get_existing_metadata_items(self, schema_key: str) -> list:
        """Load existing metadata items from XML files.

        Returns a list of tuples (id, display_name) for the given schema key.
        """
        file_map = {
            'FRM': 'FRMs.xml',
            'CTR': 'CTRs.xml',
            'WKR': 'WRKs.xml',
            'DVC': 'DVCs.xml',
            'PDT': 'PDTs.xml',
            'PGP': 'PGPs.xml',
            'VPN': 'VPNs.xml',
            'CPC': 'CPCs.xml',
            'OTQ': 'OTQs.xml',
            'CTP': 'CTPs.xml',
            'CCG': 'CCGs.xml',
            'TZN': None,  # TZN is task-specific, no global XML
            'PFD': None,  # PFD is task-specific
        }
        if schema_key not in file_map or file_map[schema_key] is None:
            return []
        xml_file = file_map[schema_key]
        xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', xml_file)
        items = []
        try:
            tree = ET.parse(xml_path)
            for child in tree.getroot():
                # Use attribute B as display name (usually the designator/name)
                display_name = child.attrib.get('B', '')
                items.append((child.tag, display_name))
        except Exception:
            pass
        return items

    def _add_metadata_selector(self, key: str, layout: QGridLayout):
        """Add a combobox to select from existing metadata and populate fields."""
        label = QLabel(self.dock_widget, text=f'Select existing {key}:')
        selector = QComboBox(self.dock_widget)
        selector.setMinimumWidth(150)
        selector.__setattr__('is_metadata_selector', True)
        selector.__setattr__('schema_key', key)

        # Map schema key to metadata file
        file_map = {
            'CTR': 'CTRs.xml',
            'DVC': 'DVCs.xml',
            'FRM': 'FRMs.xml',
        }
        # Populate from existing metadata
        selector.addItem('')  # Empty option for manual entry
        if key in file_map:
            xml_path = os.path.join(os.path.dirname(__file__), 'meta_data', file_map[key])
            try:
                tree = ET.parse(xml_path)
                for child in tree.getroot():
                    display_name = child.attrib.get('B', '')
                    selector.addItem(f'{child.tag} - {display_name}')
            except Exception as e:
                print(f'Error loading metadata for {key}: {e}')

        populate_button = QPushButton(self.dock_widget, text='Populate', minimumHeight=20)
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
        label = QLabel(self.dock_widget, text='Select field:')
        field_selector = QComboBox(self.dock_widget)
        field_selector.setMinimumWidth(150)
        field_selector.__setattr__('is_pfd_field_selector', True)

        # Populate fields from dock widget's LWFields
        lw = getattr(self.dock_widget, 'LWFields', None)
        field_selector.addItem('')  # Empty option
        if lw is not None:
            try:
                items = [lw.item(j).text() for j in range(lw.count())]
                field_selector.addItems(items)
            except Exception:
                pass

        populate_button = QPushButton(self.dock_widget, text='Populate from field', minimumHeight=20)
        populate_button.__setattr__('layout', layout)
        populate_button.__setattr__('field_selector', field_selector)
        populate_button.clicked.connect(self._populate_pfd_from_field)

        rows = layout.rowCount()
        layout.addWidget(label, rows, 0)
        layout.addWidget(field_selector, rows, 1)
        layout.addWidget(populate_button, rows, 2)

    def _populate_from_metadata(self):
        """Populate form fields from selected metadata item."""
        sender = self.dock_widget.sender()
        layout = getattr(sender, 'layout', None)
        schema_key = getattr(sender, 'schema_key', None)
        selector = getattr(sender, 'selector', None)

        if layout is None or schema_key is None or selector is None:
            return

        selected_text = selector.currentText()
        if not selected_text or ' - ' not in selected_text:
            return

        item_id = selected_text.split(' - ')[0]

        # Map schema key to metadata file
        file_map = {
            'CTR': 'CTRs.xml',
            'DVC': 'DVCs.xml',
            'FRM': 'FRMs.xml',
        }
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

            # Find all input widgets in the layout and populate them
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
            QMessageBox.warning(self.dock_widget, 'Error', f'Failed to populate from metadata: {e}')

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
            # For IDREF comboboxes, try to find the matching item
            idx = widget.findText(attr_value, _match_flag('MatchStartsWith'))
            if idx >= 0:
                widget.setCurrentIndex(idx)

    def _populate_pfd_from_field(self):
        """Populate PFD fields from selected field layer."""
        sender = self.dock_widget.sender()
        layout = getattr(sender, 'layout', None)
        field_selector = getattr(sender, 'field_selector', None)

        if layout is None or field_selector is None:
            return

        field_name = field_selector.currentText()
        if not field_name:
            QMessageBox.warning(self.dock_widget, 'Warning', 'Please select a field')
            return

        # Get the field layer from QGIS
        try:
            layers = QgsProject.instance().mapLayersByName(field_name)
            if not layers:
                QMessageBox.warning(self.dock_widget, 'Warning', f'Field layer "{field_name}" not found')
                return
            layer = layers[0]

            # Get field geometry and compute area
            if layer.featureCount() == 0:
                QMessageBox.warning(self.dock_widget, 'Warning', f'Field layer "{field_name}" has no features')
                return

            feature = next(layer.getFeatures())
            geom = feature.geometry()

            # Transform to a projected CRS for accurate area calculation
            source_crs = layer.crs()
            dest_crs = QgsCoordinateReferenceSystem('EPSG:3857')
            transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
            geom.transform(transform)
            area_m2 = int(geom.area())

            # Find and populate the widgets
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

        except Exception as e:
            QMessageBox.warning(self.dock_widget, 'Error', f'Failed to populate from field: {e}')

    def _set_pfd_widget_value(self, widget, field_name: str, area_m2: int):
        """Set PFD widget value based on attribute key."""
        if widget is None:
            return
        attr_key = getattr(widget, 'attr_name', None)
        if attr_key is None:
            return
        # C = PartfieldDesignator (name), D = PartfieldArea
        if attr_key == 'C' and isinstance(widget, QLineEdit):
            widget.setText(field_name)
        elif attr_key == 'D' and isinstance(widget, QSpinBox):
            widget.setValue(area_m2)

    def _add_schema_checkbox(self, name: str, frame: QFrame, layout, parent_frame: QFrame, key_layout,
                             d_in: dict, extra_id: str = ''):
        """Add checkbox and +/- buttons for a schema element."""
        check_box = QCheckBox(text=name + extra_id)
        check_box.__setattr__("frame", frame)
        check_box.setCheckState(_check_state('Checked'))
        check_box.toggled.connect(self._show_frame)
        add_line_push_button = QPushButton(self.dock_widget, text='+', maximumWidth=25)
        remove_line_push_button = QPushButton(self.dock_widget, text='-', maximumWidth=25)
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

    def _show_frame(self):
        """Toggle frame visibility."""
        frame = self.dock_widget.sender().frame
        if frame.isHidden():
            frame.show()
        else:
            frame.hide()

    def _add_input_widget(self, key, name, attr, layout: QGridLayout = None, widget=None):
        """Add an input widget to the layout."""
        field_name_label = QLabel(self.dock_widget, text=name + ': ')
        widget.__setattr__("schema", {key: attr})
        widget.__setattr__("attr_name", attr)
        field_name_layout = QHBoxLayout()
        field_name_layout.setAlignment(_alignment('AlignLeft'))
        field_name_layout.setContentsMargins(0, 0, 0, 0)
        field_name_layout.addWidget(field_name_label)
        field_name_layout.addWidget(widget)
        rows = layout.rowCount()
        layout.addLayout(field_name_layout, rows, 0, 1, 3)

    def _add_file_input(self, key, item, attr_name, layout: QGridLayout, extra_id: int):
        """Add file input widget."""
        file_input_label = QLabel(self.dock_widget, text=f'{key}: ')
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
            # Populate fields from dock widget's LWFields
            # First try self.dock_widget directly (for GenerateIsoxmlController)
            # Then try parent_gdf.dock_widget (for GenerateTaskDataWidget)
            lw = None
            try:
                if hasattr(self, 'dock_widget') and self.dock_widget is not None:
                    lw = getattr(self.dock_widget, 'LWFields', None)
            except Exception:
                pass
            if lw is None:
                try:
                    if self.parent_gdf is not None and getattr(self.parent_gdf, 'dock_widget', None) is not None:
                        lw = getattr(self.parent_gdf.dock_widget, 'LWFields', None)
                except Exception:
                    pass
            if lw is not None:
                try:
                    items = [lw.item(j).text() for j in range(lw.count())]
                    field_selector.addItems(items)
                except Exception:
                    pass

            update_button = QPushButton(text='Update information', minimumHeight=20)
            update_button.__setattr__("layout", layout)
            update_button.__setattr__("schema", {key: attr_name})
            # Use lambda to pass layout, field_selector and cell_size directly
            update_button.clicked.connect(
                lambda checked, lay=layout, fs=field_selector, cs=cell_size:
                    self._update_grid_information(lay, fs, cs)
            )

            grid_label = QLabel(self.dock_widget, text='grid size:')

            input_layout = QHBoxLayout()
            input_layout.setAlignment(_alignment('AlignLeft'))
            input_layout.setContentsMargins(0, 0, 0, 0)
            input_layout.addWidget(file_input_label)
            input_layout.addWidget(field_selector)
            input_layout.addWidget(grid_label)
            input_layout.addWidget(cell_size)
            input_layout.addWidget(update_button)
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

    def _add_extra_row(self):
        """Add an extra row for a schema element."""
        sender = self.dock_widget.sender()
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
        parent_layout: QGridLayout = self.dock_widget.sender().parent_layout
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
                        attr = inner_layout.itemAtPosition(j, 0).itemAt(1).widget().schema[key]
                        value = self._get_value_from_widget(inner_layout.itemAtPosition(j, 0).itemAt(1).widget())
                        xml_sub.set(attr, str(value))
                    else:
                        if inner_layout.itemAtPosition(j, 0) is not None:
                            if type(inner_layout.itemAtPosition(j, 0).widget()) == QFrame:
                                self._set_xml_children(inner_layout.itemAtPosition(j, 0).widget().layout(), xml_sub)
        try:
            ET.indent(et_parents, space='    ', level=0)
        except AttributeError:
            pass
        with open(path, 'w') as f:
            f.write(ET.tostring(et_parents, encoding='unicode'))
        self._save_temp_files(os.path.dirname(path))

    def _get_value_from_widget(self, widget) -> str:
        """Get value from a widget."""
        if type(widget) in [QSpinBox, QDoubleSpinBox]:
            value = str(widget.value())
        elif type(widget) == QLineEdit:
            value = widget.text()
        elif type(widget) == QComboBox:
            # Check if this is an IDREF widget (references another element)
            if widget in self.idref_widgets:
                # Extract the ID from the display text (e.g., "FRM1 - hörte" -> "FRM1")
                text = widget.currentText()
                if ' - ' in text:
                    value = text.split(' - ')[0]
                else:
                    value = text
            else:
                # For NMTOKEN, use the current index
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
                    attr = item.itemAt(1).widget().schema[key]
                    value = self._get_value_from_widget(item.itemAt(1).widget())
                    xml_sub.set(attr, str(value))
                else:
                    if type(item.widget()) == QFrame:
                        self._set_xml_children(item.widget().layout(), xml_sub)

    def _save_temp_files(self, path):
        """Save temporary binary files."""
        for key in self.save_temp.keys():
            for id_ in self.save_temp[key]:
                df = self.save_temp[key][id_]
                with open(f'{path}/{key}{id_:04d}.bin', 'wb') as f:
                    for index, row in df.iterrows():
                        for col in df.columns:
                            f.write(struct.pack('L', row[col]))

    def _update_grid_information(self, layout, field_selector, cell_size_widget):
        """Update GRD widgets from selected field and provided cell size.

        Args:
            layout: The QGridLayout containing the GRD attribute widgets
            field_selector: QComboBox with the selected field name
            cell_size_widget: QDoubleSpinBox with the cell size in meters
        """
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

        layer = self._find_layer_for_field(field_name)
        if layer is None:
            return

        grd_attrs = self._compute_grid_attrs_from_layer(layer, cell_size_m)
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

    def _find_layer_for_field(self, field_name: str):
        """Find a map layer whose name matches the given field name."""
        # First try loaded map layers
        try:
            for layer in QgsProject.instance().mapLayers().values():
                try:
                    if layer.name().startswith(field_name) or layer.name() == field_name:
                        return layer
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback: try fetching the field polygon from the farm database
        db = None
        # Try multiple sources for the database connection
        try:
            # 1. Try self.parent_gdf.db
            if getattr(self, 'parent_gdf', None) is not None:
                db = getattr(self.parent_gdf, 'db', None)
                # 2. Try self.parent_gdf.populate.db
                if db is None:
                    populate = getattr(self.parent_gdf, 'populate', None)
                    if populate is not None:
                        db = getattr(populate, 'db', None)
        except Exception:
            pass

        # 3. Try self.db directly
        if db is None:
            db = getattr(self, 'db', None)

        # 4. Try self.dock_widget.db or through parent chain
        if db is None:
            try:
                if hasattr(self, 'dock_widget') and self.dock_widget is not None:
                    # The dock_widget might have a parent that is GeoDataFarm
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

        # 5. Try to get db from the GeoDataFarm instance via dock_widget's gdf reference
        if db is None:
            try:
                if hasattr(self, 'dock_widget') and self.dock_widget is not None:
                    gdf = getattr(self.dock_widget, 'gdf', None)
                    if gdf is not None:
                        db = getattr(gdf, 'db', None)
            except Exception:
                pass

        if db is None:
            return None

        try:
            safe_name = field_name.replace("'", "''")
            sql = f"select ST_AsText(polygon) from fields where field_name = '{safe_name}' limit 1"
            res = db.execute_and_return(sql, return_failure=True)

            wkt = None
            if isinstance(res, list) and res:
                if res[0] is True and len(res) > 1:
                    # Format: [True, [[wkt_value]]]
                    data = res[1]
                    if data and data[0] and data[0][0]:
                        wkt = data[0][0]
                elif res[0] and isinstance(res[0], (list, tuple)):
                    # Format: [[wkt_value]]
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
        return None

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

    def _compute_grid_attrs_from_layer(self, layer, cell_size_m: float) -> dict:
        """Compute GRD attributes from a polygon layer and desired cell size in meters."""
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
                from qgis.core import QgsPointXY, QgsGeometry
                pt_utm = QgsGeometry.fromPointXY(QgsPointXY(minx, miny))
                pt_utm.transform(xform_utm_to_wgs)
                p = pt_utm.asPoint()
                lat_min = p.y()
                lon_min = p.x()
            except Exception:
                lat_min = lat
                lon_min = lon

            try:
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

            attrs['A'] = str(lat_min)
            attrs['B'] = str(lon_min)
            attrs['C'] = str(cell_n_deg)
            attrs['D'] = str(cell_e_deg)
            attrs['E'] = str(ncols)
            attrs['F'] = str(nrows)
            attrs['G'] = 'GRD00001'
            attrs['H'] = '0'
            attrs['I'] = '1'
            attrs['J'] = '0'
        except Exception:
            pass
        return attrs

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
