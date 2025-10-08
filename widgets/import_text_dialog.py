# -*- coding: utf-8 -*-
"""
"""
from typing import Self

import os
from PyQt5 import QtWidgets, uic

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'import_text_dialog_base.ui'))


class ImportTextDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self: Self, parent: None=None) -> None:
        """Constructor."""
        super(ImportTextDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        
        self.ComBNorth: QtWidgets.QComboBox
        self.ComBEast: QtWidgets.QComboBox
        self.ComBDate: QtWidgets.QComboBox
        self.ComBDate_2: QtWidgets.QComboBox
        self.ComBYield: QtWidgets.QComboBox
        self.CBField: QtWidgets.QComboBox
        self.CBType: QtWidgets.QComboBox
        self.LEEPSG: QtWidgets.QLineEdit
        self.buttonBox: QtWidgets.QDialogButtonBox
        self.label_7: QtWidgets.QLabel
        self.label_8: QtWidgets.QLabel
        self.label_9: QtWidgets.QLabel
        self.label_10: QtWidgets.QLabel
        self.label_11: QtWidgets.QLabel
        self.label_12: QtWidgets.QLabel
        self.label_13: QtWidgets.QLabel
        self.label_14: QtWidgets.QLabel
        self.RBSemi: QtWidgets.QRadioButton
        self.RBTab: QtWidgets.QRadioButton
        self.RBComma: QtWidgets.QRadioButton
        self.LEOwnSep: QtWidgets.QRadioButton
        self.LEMinYield: QtWidgets.QLineEdit
        self.LEMaxYield: QtWidgets.QLineEdit
        self.LEMoveX: QtWidgets.QLineEdit
        self.LEMoveY: QtWidgets.QLineEdit
        self.PBContinue: QtWidgets.QPushButton
        self.PBAddInputFile: QtWidgets.QPushButton
        self.PBHelp: QtWidgets.QPushButton
        self.PBInsertDataIntoDB: QtWidgets.QPushButton

