__author__ = 'Axel Horteborn'
from PyQt5 import QtCore
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtGui import QStandardItemModel


class RadioComboBox(QComboBox):
    def __init__(self):
        super(RadioComboBox, self).__init__()
        self.view().pressed.connect(self.handle_item_pressed)
        self.setModel(QStandardItemModel(self))

    def handle_item_pressed(self, index):
        item = self.model().itemFromIndex(index)
        target_row = item.index().row()
        if item.checkState() != QtCore.Qt.Checked:
            item.setCheckState(QtCore.Qt.Checked)
        self.check_others(target_row)

    def check_others(self, target_row):
        for i in range(self.model().rowCount()):
            if i == target_row:
                continue
            else:
                item = self.model().item(i)
                item.setCheckState(QtCore.Qt.Unchecked)
