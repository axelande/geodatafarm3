from operator import xor
import os
import re
import xml.etree.ElementTree as ET
from typing import Self

from qgis.PyQt.QtWidgets import (QDialog, QWidget, QLabel, QGridLayout, QTableWidget, QTableWidgetItem, QSpacerItem,
                               QPushButton, QComboBox, QSizePolicy, QAbstractItemView, QApplication,
                               QMessageBox, QLineEdit)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont

from ...support_scripts.qt_data import _enum_select_rows, _font_weight_bold, _size_policy, _item_flag, _check_state, _widget_attribute


class CheckableComboBox(QComboBox):
    def __init__(self, parent=None):
        super(CheckableComboBox, self).__init__(parent=parent)

    def addItem(self, item, checked=False):
        super(CheckableComboBox, self).addItem(item)
        item = self.model().item(self.count() - 1, 0)
        
        flags = _item_flag('ItemIsUserCheckable') | _item_flag('ItemIsEnabled')
        item.setFlags(flags)
        if checked:
            item.setCheckState(_check_state('Checked'))
            item.setEnabled(False)
        else:
            item.setCheckState(_check_state('Unchecked'))

    def itemChecked(self, index):
        item = self.model().item(index, 0)
        return item.checkState() == _check_state('Checked')


class CreateRecipe(QDialog):
    def __init__(self, parent=None, parent_gdf=None):
        # Only pass a QWidget (or None) as the dialog parent; tests may pass a plain object
        parent_widget = parent if isinstance(parent, QWidget) else None
        super(CreateRecipe, self).__init__(parent_widget)
        self.parent_widget = parent
        self.parent_gdf = parent_gdf
        self.main_layout = QGridLayout()
        intro_label = QLabel(self, text=('Here you define what the ISOXML files should contain, in the first table to '
                                         'the left you select which schemas and "sub schemas" to include, in the second'
                                         ' table to the right you double check\nthat the correct schemas are included. '
                                         '(by "tick" the applicable sub schemas and then press "Add ->"). Finally press'
                                         ' "Continue" and select which attributes each schema must contain.'))
        self.main_layout.addWidget(intro_label, 0, 0, 1, 3)
        self.central_widget = QWidget(self)
        self.included_schemas_list = QTableWidget(self.central_widget)
        self.available_schemas_list = QTableWidget(self.central_widget)

        self.available_attributes_list = QTableWidget(self)

        self.set_qtables()
        bold = _font_weight_bold()
        self.add_item_button = QPushButton(text='Add ->', font=QFont('Times', 12))
        self.remove_item_button = QPushButton(text='<- Remove', font=QFont('Times', 12))
        self.continue_button = QPushButton(text='Continue', font=QFont('Times', 12, weight=bold))
        self.store_recipe_button = QPushButton(text='Store data', font=QFont('Times', 12, weight=bold))

        self.recipe_name_label = QLabel(self, text='Recipe name:')
        self.recipe_name_edit = QLineEdit(self)
        self.recipe_name_edit.setPlaceholderText('Enter recipe name')

        self.attribute_dict = {}

        self.add_widgets_to_layout()

        # If a QWidget parent with schemas wasn't provided, fall back to parent_gdf
        if (self.parent_widget is not None and hasattr(self.parent_widget, 'schemas')) or (
            self.parent_gdf is not None and hasattr(self.parent_gdf, 'schemas')
        ):
            if not (self.parent_widget is not None and hasattr(self.parent_widget, 'schemas')):
                # use parent_gdf as the source for schemas
                self.parent_widget = self.parent_gdf
            self.fill_available_columns()
        
        # setup the dialog's central widget

        self.central_widget.setLayout(self.main_layout)
        self.central_widget.adjustSize()
        outer_layout = QGridLayout(self)
        outer_layout.addWidget(self.central_widget, 0, 0)
        self.setLayout(outer_layout)

        self.setGeometry(100, 100, 1000, 800)
        self.setWindowTitle("GeoDataFarm - Create Recipe")
        # Ensure this dialog is deleted on close
        try:
            self.setAttribute(_widget_attribute('WA_DeleteOnClose'))
            self.setModal(True)
        except Exception:
            pass

    def add_widgets_to_layout(self):
        self.add_item_button.clicked.connect(self.add_schema)
        self.remove_item_button.clicked.connect(self.remove_schema)
        self.continue_button.clicked.connect(self.continue_to_attributes)
        self.store_recipe_button.clicked.connect(self.store_data)

        self.main_layout.addWidget(self.available_schemas_list, 1, 0, 4, 1)
        self.main_layout.addItem(QSpacerItem(20, 40, _size_policy("Minimum"), _size_policy("Expanding")), 1, 1)
        self.main_layout.addWidget(self.add_item_button, 2, 1)
        self.main_layout.addWidget(self.remove_item_button, 3, 1)
        self.main_layout.addItem(QSpacerItem(20, 40, _size_policy("Minimum"), _size_policy("Expanding")), 4, 1)
        self.main_layout.addWidget(self.included_schemas_list, 1, 2, 4, 1)
        self.main_layout.addWidget(self.continue_button, 5, 0)
        self.main_layout.addWidget(self.available_attributes_list, 6, 0)
        self.main_layout.addWidget(self.recipe_name_label, 6, 1)
        self.main_layout.addWidget(self.recipe_name_edit, 6, 2)
        self.main_layout.addWidget(self.store_recipe_button, 7, 2)

    def set_qtables(self):
        for i, table in enumerate([self.included_schemas_list, self.available_schemas_list, self.available_attributes_list]):
            table.setMinimumHeight(350)
            table.setColumnCount(2)
            if i == 2:
                table.setHorizontalHeaderLabels(('Schema', 'Attributes'))
            else:
                table.setHorizontalHeaderLabels(('Schema', 'SubSchema'))
            select_rows = _enum_select_rows()
            table.setSelectionBehavior(select_rows)
            table.setColumnWidth(0, 150)
            table.setColumnWidth(1, 220)
            table.setMaximumWidth(430)
            table.setMinimumWidth(430)

    def get_existing_values_from_included_schemas(self) -> list:
        existing_values = []
        if self.included_schemas_list.rowCount() != 0:
            for i in range(self.included_schemas_list.rowCount()):
                existing_values.append(self.included_schemas_list.item(i, 0).text())
                cb: QComboBox = self.included_schemas_list.cellWidget(i, 1)
                if cb is None:
                    continue
                for cb_i in range(cb.count()):
                    existing_values.append(cb.itemText(cb_i))
        return existing_values

    def continue_to_attributes(self):
        """Add schemas and their attributes to the available_attributes_list table"""
        if self.parent_widget is None or not hasattr(self.parent_widget, 'schemas'):
            QMessageBox.information(None, "Error", "No schemas available")
            return
        
        existing_values = self.get_existing_values_from_included_schemas()
        self.available_attributes_list.setRowCount(len(existing_values))
        self.attribute_dict = {}
        for i, item_name in enumerate(existing_values):
            code = item_name.split('| ')[1]
            self.attribute_dict[code] = {}
            cb = CheckableComboBox()
            for attribute in self.parent_widget.schemas[code]:
                if attribute in ["Name", "includes"]:
                    continue
                name = self.parent_widget.schemas[code][attribute]['Attribute_name']
                attr_name = ''.join(' ' + char if char.isupper() else char.strip() for char in name).strip()
                self.attribute_dict[code][attr_name] = attribute
                if self.parent_widget.schemas[code][attribute]['Use'] == 'r':
                    cb.addItem(attr_name + f' | {attribute}', True, )
                else:
                    cb.addItem(attr_name + f' | {attribute}', False)
            item1 = QTableWidgetItem(item_name)
            item3 = QTableWidgetItem(code)
            item1.setFlags(xor(item1.flags(), _item_flag('ItemIsEditable')))
            self.available_attributes_list.setItem(i, 0, item1)
            self.available_attributes_list.setCellWidget(i, 1, cb)
            self.available_attributes_list.setItem(i, 2, item3)

    def dict_to_xml(self, tag: str, d: dict) -> ET.Element:
        elem = ET.Element(tag)
        for key, val in d.items():
            # create an Element
            # class object
            if type(val) == dict:

                val = self.dict_to_xml(key, val)
                ET.SubElement(elem, val)
            elif type(val) == list:
                child = ET.Element(key)
                child.text = str(val)
                elem.append(child)
        return elem

    def get_xml_tree(self) -> ET.Element:
        """Compiles the Element tree from the available_attributes_list"""
        lvl = -1
        key_list = [ET.Element('ISO11783_TaskData')]
        for i in range(self.available_attributes_list.rowCount()):
            code = self.available_attributes_list.item(i, 0).text().split('| ')[1]
            c_lvl = self.determine_nested_level(self.available_attributes_list.item(i, 0).text())
            if c_lvl <= lvl:
                key_list = key_list[: - (lvl - c_lvl + 1)]
            xml_sub = ET.SubElement(key_list[-1], code)

            cb = self.available_attributes_list.cellWidget(i, 1)
            for cb_i in range(cb.count()):
                if cb.itemChecked(cb_i):
                    xml_sub.set(cb.itemText(cb_i).split('| ')[1], '')

            lvl = c_lvl
            key_list.append(xml_sub)
        return key_list[0]

    def store_data(self, *, path: str = None):
        """Retrieves the xml structure and save it to the recipes folder (or path if specified in eg. testcases)."""
        xml_tree = self.get_xml_tree()

        # Handle ET.indent for both Python 3.9+ and older versions
        if hasattr(ET, 'indent'):
            ET.indent(xml_tree, space='    ', level=0)

        running_test = True
        if path is None:
            running_test = False
            recipe_name = self.recipe_name_edit.text().strip()
            if not recipe_name:
                QMessageBox.warning(self, 'Missing name', 'Please enter a recipe name')
                return
            # Get the recipes folder path (relative to this file)
            recipes_folder = os.path.join(os.path.dirname(__file__), 'recipes')
            os.makedirs(recipes_folder, exist_ok=True)
            # Ensure .recipe extension
            if not recipe_name.endswith('.recipe'):
                recipe_name += '.recipe'
            path = os.path.join(recipes_folder, recipe_name)

        if not path:
            return

        with open(path, 'w') as f:
            f.write(ET.tostring(xml_tree, encoding='unicode'))
        self.available_attributes_list.clear()
        self.included_schemas_list.clear()
        self.recipe_name_edit.clear()
        # Only show a blocking QMessageBox in normal (non-test) runs. If this dialog
        # is owned by a plugin object that sets `test_mode=True` skip the popup so
        # automated tests don't hang waiting for user interaction.
        show_popup = not running_test
        parent_plugin = getattr(self, 'parent_gdf', None) or getattr(self, 'parent_widget', None)
        if hasattr(parent_plugin, 'test_mode') and parent_plugin.test_mode:
            show_popup = False

        if show_popup:
            QMessageBox.information(self, 'Save complete', f'Recipe saved to {path}')

    def remove_schema(self):
        """Removes the selected schemas from the table: included_schemas_list"""
        if self.included_schemas_list.selectedItems() is None:
            return
        for item in self.included_schemas_list.selectedItems():
            self.included_schemas_list.removeRow(item.row())

    def add_schema(self):
        """Adds the schemas and subschemas to the table included_schemas_list"""
        row_count = self.included_schemas_list.rowCount()
        items_to_add = []
        existing_values = []
        if row_count != 0:
            for i in range(row_count):
                existing_values.append(self.included_schemas_list.item(i, 0).text())
        for item in self.available_schemas_list.selectedItems():
            row = item.row()
            if item.column() == 0 and item.text() not in existing_values:
                cb: CheckableComboBox = self.available_schemas_list.cellWidget(row, 1)
                items = self.add_items_from_checkbox(cb)
                items_to_add.append([item.text(), items])
        for i, item in enumerate(items_to_add, self.included_schemas_list.rowCount()):
            row_count += 1
            self.included_schemas_list.setRowCount(row_count)
            item1 = QTableWidgetItem(item[0])
            item1.setFlags(xor(item1.flags(), _item_flag('ItemIsEditable')))
            self.included_schemas_list.setItem(i, 0, item1)
            if len(item[1]) > 0:
                item2 = QComboBox()
                item2.addItems(item[1])
                self.included_schemas_list.setCellWidget(i, 1, item2)

    @staticmethod
    def determine_nested_level(text_) -> int:
        """Returns an int depending on how many '- ' there is in the string"""
        return text_.count('- ')

    def add_items_from_checkbox(self, cb: CheckableComboBox) -> list:
        items = []
        prev_level = [False, False, False, False, False, False]
        for cb_i in range(cb.count()):
            if cb.itemChecked(cb_i):
                prev_level[self.determine_nested_level(cb.itemText(cb_i)) - 1] = True
                if self.determine_nested_level(cb.itemText(cb_i)) == 1:
                    prev_level = [True, False, False, False, False, False]
                    items.append(cb.itemText(cb_i))
                elif all(prev_level[:self.determine_nested_level(cb.itemText(cb_i)) - 1]):
                    items.append(cb.itemText(cb_i))
            else:
                prev_level[self.determine_nested_level(cb.itemText(cb_i)) - 1] = False
        return items

    def fill_available_columns(self):
        """Fills the available_schemas_list table with the available schemas and their sub schemas."""
        self.available_schemas_list.setRowCount(len(self.parent_widget.schemas))
        self.available_schemas_list.setColumnCount(2)
        for index, schema in enumerate(self.parent_widget.schemas):
            name = self.parent_widget.schemas[schema]["Name"]
            schema_name = ''.join(' ' + char if char.isupper() else char.strip() for char in name).strip()
            item = QTableWidgetItem(schema_name + f' | {schema}')
            cb = CheckableComboBox()
            self.add_required(cb, schema, intro_text='- ')
            self.available_schemas_list.setItem(index, 0, item)
            self.available_schemas_list.setCellWidget(index, 1, cb)

    def add_required(self, cb: CheckableComboBox, schema: str, intro_text: str = '', prev_name: str = ''):
        """Adds the sub schemas to the checkbox"""
        includes = self.parent_widget.schemas[schema]['includes']
        for code in includes.keys():
            name = intro_text + self.parent_widget.schemas[code]['Name']
            name = ''.join(' ' + char if char.isupper() else char.strip() for char in name).strip()
            prev_lvl = self.determine_nested_level(prev_name)
            name = '- ' * prev_lvl + name
            includes_in = self.parent_widget.schemas[code]['includes']
            if includes[code]["Use"] == 'r':
                required = True
            else:
                required = False
            if code != schema and len(includes_in) > 0:
                cb.addItem(name + f' | {code}', required)
                self.add_required(cb, code, intro_text='- ', prev_name=name)
            else:
                cb.addItem(name + f' | {code}', required)

    def run(self: Self) -> None:
        """Show the dialog window as non-blocking (backwards compatibility)."""
        try:
            # preserve older behavior if callers use run()
            self.show()
        except Exception:
            pass
