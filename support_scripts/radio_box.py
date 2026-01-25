from typing import Self
__author__ = 'Axel Horteborn'
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QComboBox
from qgis.PyQt.QtGui import QStandardItemModel
from .qt_data import _check_state


class RadioComboBox(QComboBox):
    def __init__(self: Self) -> None:
        super(RadioComboBox, self).__init__()
        self.view().pressed.connect(self.handle_item_pressed)
        self.setModel(QStandardItemModel(self))

    def handle_item_pressed(self, index):
        item = self.model().itemFromIndex(index)
        target_row = item.index().row()
        if item.checkState() != _check_state('Checked'):
            item.setCheckState(_check_state('Checked'))
        self.check_others(target_row)

    def check_others(self, target_row):
        for i in range(self.model().rowCount()):
            if i == target_row:
                continue
            else:
                item = self.model().item(i)
                item.setCheckState(_check_state('Unchecked'))
