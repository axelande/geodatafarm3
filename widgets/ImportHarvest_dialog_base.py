# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ImportHarvest_dialog_base.ui'
#
# Created: Tue May 09 16:26:50 2017
#      by: PyQt4 UI code generator 4.10.2
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_ImportHarvestDialogBase(object):
    def setupUi(self, ImportHarvestDialogBase):
        ImportHarvestDialogBase.setObjectName(_fromUtf8("ImportHarvestDialogBase"))
        ImportHarvestDialogBase.resize(549, 462)
        self.button_box = QtGui.QDialogButtonBox(ImportHarvestDialogBase)
        self.button_box.setGeometry(QtCore.QRect(40, 430, 231, 23))
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtGui.QDialogButtonBox.Cancel)
        self.button_box.setCenterButtons(False)
        self.button_box.setObjectName(_fromUtf8("button_box"))
        self.add_input_file = QtGui.QPushButton(ImportHarvestDialogBase)
        self.add_input_file.setGeometry(QtCore.QRect(11, 10, 85, 23))
        self.add_input_file.setObjectName(_fromUtf8("add_input_file"))
        self.TWColumnNames = QtGui.QTableWidget(ImportHarvestDialogBase)
        self.TWColumnNames.setGeometry(QtCore.QRect(10, 71, 401, 221))
        self.TWColumnNames.setEditTriggers(QtGui.QAbstractItemView.AnyKeyPressed)
        self.TWColumnNames.setObjectName(_fromUtf8("TWColumnNames"))
        self.TWColumnNames.setColumnCount(0)
        self.TWColumnNames.setRowCount(0)
        self.pButInsertDataIntoDB = QtGui.QPushButton(ImportHarvestDialogBase)
        self.pButInsertDataIntoDB.setEnabled(False)
        self.pButInsertDataIntoDB.setGeometry(QtCore.QRect(50, 430, 131, 23))
        self.pButInsertDataIntoDB.setObjectName(_fromUtf8("pButInsertDataIntoDB"))
        self.label_4 = QtGui.QLabel(ImportHarvestDialogBase)
        self.label_4.setGeometry(QtCore.QRect(20, 300, 491, 31))
        self.label_4.setWordWrap(True)
        self.label_4.setObjectName(_fromUtf8("label_4"))
        self.ComBHarvestCol = QtGui.QComboBox(ImportHarvestDialogBase)
        self.ComBHarvestCol.setGeometry(QtCore.QRect(20, 400, 291, 22))
        self.ComBHarvestCol.setEditable(True)
        self.ComBHarvestCol.setObjectName(_fromUtf8("ComBHarvestCol"))
        self.label_5 = QtGui.QLabel(ImportHarvestDialogBase)
        self.label_5.setGeometry(QtCore.QRect(20, 380, 271, 21))
        self.label_5.setWordWrap(True)
        self.label_5.setObjectName(_fromUtf8("label_5"))
        self.LEYear = QtGui.QLineEdit(ImportHarvestDialogBase)
        self.LEYear.setGeometry(QtCore.QRect(100, 330, 113, 20))
        self.LEYear.setObjectName(_fromUtf8("LEYear"))
        self.label_3 = QtGui.QLabel(ImportHarvestDialogBase)
        self.label_3.setGeometry(QtCore.QRect(70, 330, 47, 13))
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.minimum_yield = QtGui.QLineEdit(ImportHarvestDialogBase)
        self.minimum_yield.setGeometry(QtCore.QRect(90, 360, 51, 20))
        self.minimum_yield.setObjectName(_fromUtf8("minimum_yield"))
        self.label_6 = QtGui.QLabel(ImportHarvestDialogBase)
        self.label_6.setGeometry(QtCore.QRect(20, 360, 71, 16))
        self.label_6.setObjectName(_fromUtf8("label_6"))
        self.maximum_yield = QtGui.QLineEdit(ImportHarvestDialogBase)
        self.maximum_yield.setGeometry(QtCore.QRect(230, 360, 51, 20))
        self.maximum_yield.setObjectName(_fromUtf8("maximum_yield"))
        self.label_12 = QtGui.QLabel(ImportHarvestDialogBase)
        self.label_12.setGeometry(QtCore.QRect(160, 360, 71, 16))
        self.label_12.setObjectName(_fromUtf8("label_12"))
        self.frame = QtGui.QFrame(ImportHarvestDialogBase)
        self.frame.setGeometry(QtCore.QRect(10, 50, 511, 21))
        self.frame.setFrameShape(QtGui.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtGui.QFrame.Raised)
        self.frame.setObjectName(_fromUtf8("frame"))
        self.RBComma = QtGui.QRadioButton(self.frame)
        self.RBComma.setGeometry(QtCore.QRect(80, 0, 61, 17))
        self.RBComma.setObjectName(_fromUtf8("RBComma"))
        self.RBSemi = QtGui.QRadioButton(self.frame)
        self.RBSemi.setGeometry(QtCore.QRect(160, 0, 82, 17))
        self.RBSemi.setObjectName(_fromUtf8("RBSemi"))
        self.RBTab = QtGui.QRadioButton(self.frame)
        self.RBTab.setGeometry(QtCore.QRect(250, 0, 41, 17))
        self.RBTab.setObjectName(_fromUtf8("RBTab"))
        self.label_2 = QtGui.QLabel(self.frame)
        self.label_2.setGeometry(QtCore.QRect(10, 0, 51, 16))
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.RBOwnSep = QtGui.QRadioButton(self.frame)
        self.RBOwnSep.setGeometry(QtCore.QRect(320, 0, 51, 17))
        self.RBOwnSep.setObjectName(_fromUtf8("RBOwnSep"))
        self.LEOwnSep = QtGui.QLineEdit(self.frame)
        self.LEOwnSep.setGeometry(QtCore.QRect(370, 0, 31, 20))
        self.LEOwnSep.setObjectName(_fromUtf8("LEOwnSep"))

        self.retranslateUi(ImportHarvestDialogBase)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("accepted()")), ImportHarvestDialogBase.accept)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("rejected()")), ImportHarvestDialogBase.reject)
        QtCore.QMetaObject.connectSlotsByName(ImportHarvestDialogBase)

    def retranslateUi(self, ImportHarvestDialogBase):
        ImportHarvestDialogBase.setWindowTitle(_translate("ImportHarvestDialogBase", "Add harvest data to the model", None))
        ImportHarvestDialogBase.setToolTip(_translate("ImportHarvestDialogBase", "\'Positive values for moving the GPS to right, negative values to move it left\'", None))
        self.add_input_file.setText(_translate("ImportHarvestDialogBase", "Add harvest file", None))
        self.pButInsertDataIntoDB.setText(_translate("ImportHarvestDialogBase", "Add data to canvas", None))
        self.label_4.setText(_translate("ImportHarvestDialogBase", "Note that there need to be one (and only one) header column contating \"lat\" and one with \"lon\"", None))
        self.label_5.setText(_translate("ImportHarvestDialogBase", "Choose which column that contains  the harvest yield:", None))
        self.label_3.setText(_translate("ImportHarvestDialogBase", "Year:", None))
        self.minimum_yield.setText(_translate("ImportHarvestDialogBase", "1", None))
        self.label_6.setText(_translate("ImportHarvestDialogBase", "Minimum yield:", None))
        self.maximum_yield.setText(_translate("ImportHarvestDialogBase", "99999", None))
        self.label_12.setText(_translate("ImportHarvestDialogBase", "Maximum yield:", None))
        self.RBComma.setText(_translate("ImportHarvestDialogBase", "Comma", None))
        self.RBSemi.setText(_translate("ImportHarvestDialogBase", "Semicolon", None))
        self.RBTab.setText(_translate("ImportHarvestDialogBase", "Tab", None))
        self.label_2.setText(_translate("ImportHarvestDialogBase", "Separator", None))
        self.RBOwnSep.setText(_translate("ImportHarvestDialogBase", "Other:", None))

