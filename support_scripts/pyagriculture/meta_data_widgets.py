from operator import xor
import os
import xml.etree.ElementTree as ET

from qgis.PyQt.QtWidgets import (QDialog, QWidget, QLabel, QGridLayout, QListWidget, QListWidgetItem, QSpacerItem,
                                  QFileDialog, QPushButton, QComboBox, QSizePolicy, QAbstractItemView, QApplication,
                                  QMessageBox, QVBoxLayout, QHBoxLayout, QLineEdit, QFrame)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont

from .errors import MsgError

THIS_DIR = os.path.dirname(__file__)


class MetaData(QDialog):
    def __init__(self, parent=None, meta_data_type: str = 'Farm', schema: dict = None, meta_data_dir: str | None = None):
        # Only pass QWidget as parent to the dialog
        parent_widget = parent if isinstance(parent, QWidget) else None
        super(MetaData, self).__init__(parent_widget)
        # top-level dialog and ensure it is deleted on close to avoid lingering
        try:
            self.setAttribute(Qt.WA_DeleteOnClose)
            self.setModal(True)
        except Exception:
            pass
        self.main_layout = QGridLayout()
        self.available_items_table_widget = QListWidget()
        self.current_sub_element = ET.Element('')
        self.update_item_name = False
        self.meta_data_type = meta_data_type
        self.schema = schema
        self.edit_item_push_button = QPushButton(self, text='Edit ->')
        self.edit_item_push_button.clicked.connect(self.edit_item)
        self.update_item_push_button = QPushButton(self, text='Update <-')
        self.update_item_push_button.clicked.connect(self.update_item)
        self.update_item_push_button.setEnabled(False)
        self.save_item_push_button = QPushButton(self, text='Save as new<-')
        self.save_item_push_button.clicked.connect(self.save_item)
        self.delete_item_push_button = QPushButton(self, text='Remove item')
        self.delete_item_push_button.clicked.connect(self.remove_item)
        self.type_widgets_layout = QVBoxLayout()
        self.type_widgets = QFrame(self)
        self.type_widgets.setLayout(self.type_widgets_layout)
        self.main_layout.addWidget(self.available_items_table_widget, 1, 0, 7, 1)
        self.main_layout.addWidget(self.edit_item_push_button, 2, 1, 1, 1)
        self.main_layout.addWidget(self.update_item_push_button, 3, 1, 1, 1)
        self.main_layout.addWidget(self.save_item_push_button, 4, 1, 1, 1)
        self.main_layout.addWidget(self.delete_item_push_button, 5, 1, 1, 1)
        self.main_layout.addWidget(self.type_widgets, 1, 2, 7, 1)
        self.set_type_items()
        base_dir = meta_data_dir if meta_data_dir is not None else THIS_DIR

        # Map metadata type to file name
        file_map = {
            'Farm': 'FRMs.xml',
            'Customer': 'CTRs.xml',
            'Worker': 'WRKs.xml',
            'Device': 'DVCs.xml',
            'Product': 'PDTs.xml',
            'ProductGroup': 'PGPs.xml',
            'ValuePresentation': 'VPNs.xml',
            'CulturalPractice': 'CPCs.xml',
            'OperationTechnique': 'OTQs.xml',
            'CropType': 'CTPs.xml',
            'CodedCommentGroup': 'CCGs.xml'
        }

        if meta_data_type in file_map:
            xml_file = file_map[meta_data_type]
            self.file_name = os.path.join(base_dir, 'meta_data', xml_file)
            self.tree_root = ET.parse(self.file_name).getroot()
        else:
            raise MsgError(f'Unknown metadata type: {meta_data_type}')
        self.fill_existing_table()
        # For dialogs, set the layout directly without unnecessary nesting
        self.setLayout(self.main_layout)

        self.setGeometry(100, 100, 800, 800)
        self.setWindowTitle(f"GeoDataFarm - Edit {meta_data_type}")

    def fill_existing_table(self):
        self.available_items_table_widget.clear()
        for child in self.tree_root:
            name = f'{child.tag} - {child.attrib["B"]}'
            item1 = QListWidgetItem(name)
            self.available_items_table_widget.addItem(item1)

    def remove_item(self):
        """Removes the selected schemas from the table: included_schemas_list"""
        if self.available_items_table_widget.selectedItems() is None:
            return
        for item in self.available_items_table_widget.selectedItems():
            xml_item = self.tree_root.findall(item.text().split(' - ')[0])
            self.tree_root.remove(xml_item[0])
            self.available_items_table_widget.removeItemWidget(item)
        self.save_tree()
        self.fill_existing_table()

    def edit_item(self):
        from qgis.PyQt.QtWidgets import QSpinBox, QDoubleSpinBox
        for item in self.available_items_table_widget.selectedItems():
            xml_item = self.tree_root.findall(item.text().split(' - ')[0])[0]
            for i in range(self.type_widgets_layout.count()):
                if type(self.type_widgets_layout.itemAt(i).widget()) == QFrame:
                    lay = self.type_widgets_layout.itemAt(i).widget().layout()
                    widget = lay.itemAt(1).widget()
                    attr_value = xml_item.attrib.get(widget.attr, '')
                    if type(widget) == QLineEdit:
                        widget.setText(attr_value)
                    elif type(widget) == QComboBox:
                        # Try to find and select the matching item
                        idx = widget.findText(attr_value)
                        if idx >= 0:
                            widget.setCurrentIndex(idx)
                        else:
                            # Try matching by index for NMTOKEN numeric values
                            try:
                                widget.setCurrentIndex(int(attr_value))
                            except (ValueError, TypeError):
                                pass
                    elif type(widget) == QSpinBox:
                        try:
                            widget.setValue(int(attr_value))
                        except (ValueError, TypeError):
                            widget.setValue(0)
                    elif type(widget) == QDoubleSpinBox:
                        try:
                            widget.setValue(float(attr_value))
                        except (ValueError, TypeError):
                            widget.setValue(0.0)
            self.update_item_push_button.setEnabled(True)
            self.current_sub_element = xml_item

    def clear_widgets(self):
        # Remove all widgets from the layout to prevent stacking
        while self.type_widgets_layout.count():
            item = self.type_widgets_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_type_items(self):
        # Clear existing widgets before adding new ones to prevent stacking
        self.clear_widgets()
        if self.schema is None:
            return
        for key, item in self.schema.items():
            if 'name' in key.lower() or 'includes' in key.lower():
                continue
            label = QLabel(self, text=f"{item['Attribute_name']}: ")
            type_lower = item['Type'].lower()

            if 'string' in type_lower or 'hexbinary' in type_lower:
                widget = QLineEdit(self)
            elif 'xs:idref' in type_lower:
                widget = self.get_ctr_widgets()
            elif 'nmtoken' in type_lower:
                # NMTOKEN - use combobox with predefined values
                widget = QComboBox(self)
                if 'nm_list' in item:
                    widget.addItems(item['nm_list'])
            elif 'unsignedbyte' in type_lower:
                # unsignedByte: 0-255
                from qgis.PyQt.QtWidgets import QSpinBox
                widget = QSpinBox(self)
                widget.setMinimum(0)
                widget.setMaximum(255)
            elif 'unsignedshort' in type_lower:
                # unsignedShort: 0-65535
                from qgis.PyQt.QtWidgets import QSpinBox
                widget = QSpinBox(self)
                widget.setMinimum(0)
                widget.setMaximum(65535)
            elif 'unsignedlong' in type_lower:
                # unsignedLong: 0 to max int
                from qgis.PyQt.QtWidgets import QSpinBox
                widget = QSpinBox(self)
                widget.setMinimum(0)
                widget.setMaximum(2147483647)
            elif 'long' in type_lower:
                # xs:long (signed)
                from qgis.PyQt.QtWidgets import QSpinBox
                widget = QSpinBox(self)
                widget.setMinimum(-2147483648)
                widget.setMaximum(2147483647)
            elif 'short' in type_lower:
                # xs:short (signed): -32768 to 32767
                from qgis.PyQt.QtWidgets import QSpinBox
                widget = QSpinBox(self)
                widget.setMinimum(-32768)
                widget.setMaximum(32767)
            elif 'byte' in type_lower:
                # xs:byte (signed): -128 to 127
                from qgis.PyQt.QtWidgets import QSpinBox
                widget = QSpinBox(self)
                widget.setMinimum(-128)
                widget.setMaximum(127)
            elif 'decimal' in type_lower or 'double' in type_lower:
                # Decimal/double with 2 decimal places
                from qgis.PyQt.QtWidgets import QDoubleSpinBox
                widget = QDoubleSpinBox(self)
                widget.setDecimals(2)
                widget.setMinimum(-999999999.99)
                widget.setMaximum(999999999.99)
            elif 'xs:id' in type_lower:
                # ID fields are auto-generated, show as read-only
                widget = QLineEdit(self)
                widget.setReadOnly(True)
                widget.setPlaceholderText('(auto-generated)')
            else:
                # Fallback to line edit for unknown types
                widget = QLineEdit(self)
            widget.__setattr__('attr', key)
            lay = QHBoxLayout()
            lay.addWidget(label)
            lay.addWidget(widget)
            frame = QFrame()
            frame.setLayout(lay)
            self.type_widgets_layout.addWidget(frame)

    def get_ctr_widgets(self, schema: str = 'CTR') -> QComboBox:
        root = ET.parse(os.path.join(THIS_DIR, 'meta_data', f'{schema}s.xml')).getroot()
        widget = QComboBox(self)
        items = []
        for child in root:
            items.append(f'{child.tag} - {child.attrib["B"]}')
        widget.addItems(items)
        return widget

    def update_item(self):
        self.update_item_name = True
        self.save_item()
        self.update_item_push_button.setEnabled(False)
        self.current_sub_element = None
        self.update_item_name = False

    def get_xml_sub_schema(self) -> ET.SubElement:
        if self.current_sub_element is not None and self.update_item_name:
            return self.current_sub_element
        schema = self.tree_root.attrib['schema']
        max_number = 0
        for item in self.tree_root.iter("*"):
            try:
                number = int(item.tag.strip(schema))
                if number > max_number:
                    max_number = number
            except ValueError:
                pass
        name = schema + str(max_number + 1)
        sub = ET.SubElement(self.tree_root, name)
        return sub

    def save_item(self):
        from qgis.PyQt.QtWidgets import QSpinBox, QDoubleSpinBox
        sub = self.get_xml_sub_schema()
        for i in range(self.type_widgets_layout.count()):
            if type(self.type_widgets_layout.itemAt(i).widget()) == QFrame:
                lay = self.type_widgets_layout.itemAt(i).widget().layout()
                widget = lay.itemAt(1).widget()
                key = widget.attr
                if type(widget) == QLineEdit:
                    value = widget.text()
                elif type(widget) == QComboBox:
                    # For IDREF comboboxes, extract the ID part
                    text = widget.currentText()
                    if ' - ' in text:
                        value = text.split(' - ')[0]
                    else:
                        # For NMTOKEN, use the current index
                        value = str(widget.currentIndex())
                elif type(widget) == QSpinBox:
                    value = str(widget.value())
                elif type(widget) == QDoubleSpinBox:
                    value = str(widget.value())
                else:
                    value = ''
                sub.set(key, value)
        self.save_tree()
        self.fill_existing_table()

    def save_tree(self):
        try:
            ET.indent(self.tree_root, space='    ', level=0)
        except AttributeError:
            pass
        with open(self.file_name, 'wb') as f:
            string = ET.tostring(self.tree_root, encoding='unicode')
            f.write(string.encode('utf-8'))