# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Run_analyse_base.ui'
#
# Created: Tue May 09 16:26:49 2017
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

class Ui_RunAnalyseDialogBase(object):
    def setupUi(self, RunAnalyseDialogBase):
        RunAnalyseDialogBase.setObjectName(_fromUtf8("RunAnalyseDialogBase"))
        RunAnalyseDialogBase.resize(685, 652)
        RunAnalyseDialogBase.setMinimumSize(QtCore.QSize(591, 652))
        RunAnalyseDialogBase.setToolTip(_fromUtf8(""))
        self.mplwindow = QtGui.QWidget(RunAnalyseDialogBase)
        self.mplwindow.setGeometry(QtCore.QRect(10, 0, 461, 361))
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.mplwindow.sizePolicy().hasHeightForWidth())
        self.mplwindow.setSizePolicy(sizePolicy)
        self.mplwindow.setMinimumSize(QtCore.QSize(461, 0))
        self.mplwindow.setObjectName(_fromUtf8("mplwindow"))
        self.mplvl = QtGui.QVBoxLayout(self.mplwindow)
        self.mplvl.setMargin(0)
        self.mplvl.setObjectName(_fromUtf8("mplvl"))
        self.pButRun = QtGui.QPushButton(RunAnalyseDialogBase)
        self.pButRun.setGeometry(QtCore.QRect(10, 370, 201, 23))
        self.pButRun.setObjectName(_fromUtf8("pButRun"))
        self.paramArea = QtGui.QScrollArea(RunAnalyseDialogBase)
        self.paramArea.setGeometry(QtCore.QRect(10, 400, 571, 241))
        self.paramArea.setWidgetResizable(True)
        self.paramArea.setObjectName(_fromUtf8("paramArea"))
        self.scrollAreaWidgetContents = QtGui.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 569, 239))
        self.scrollAreaWidgetContents.setObjectName(_fromUtf8("scrollAreaWidgetContents"))
        self.paramArea.setWidget(self.scrollAreaWidgetContents)
        self.groupBoxConstraints = QtGui.QScrollArea(RunAnalyseDialogBase)
        self.groupBoxConstraints.setGeometry(QtCore.QRect(480, 0, 201, 361))
        self.groupBoxConstraints.setWidgetResizable(True)
        self.groupBoxConstraints.setObjectName(_fromUtf8("groupBoxConstraints"))
        self.scrollAreaWidgetContents_2 = QtGui.QWidget()
        self.scrollAreaWidgetContents_2.setGeometry(QtCore.QRect(0, 0, 199, 359))
        self.scrollAreaWidgetContents_2.setObjectName(_fromUtf8("scrollAreaWidgetContents_2"))
        self.groupBoxConstraints.setWidget(self.scrollAreaWidgetContents_2)
        self.label = QtGui.QLabel(RunAnalyseDialogBase)
        self.label.setGeometry(QtCore.QRect(220, 370, 151, 20))
        self.label.setObjectName(_fromUtf8("label"))
        self.minNumber = QtGui.QLineEdit(RunAnalyseDialogBase)
        self.minNumber.setGeometry(QtCore.QRect(370, 370, 41, 20))
        self.minNumber.setObjectName(_fromUtf8("minNumber"))

        self.retranslateUi(RunAnalyseDialogBase)
        QtCore.QMetaObject.connectSlotsByName(RunAnalyseDialogBase)

    def retranslateUi(self, RunAnalyseDialogBase):
        RunAnalyseDialogBase.setWindowTitle(_translate("RunAnalyseDialogBase", "Analyse window", None))
        self.pButRun.setText(_translate("RunAnalyseDialogBase", "Update", None))
        self.label.setText(_translate("RunAnalyseDialogBase", "Minimum data points required:", None))
        self.minNumber.setToolTip(_translate("RunAnalyseDialogBase", "<html><head/><body><p>The minimum number of samples to show in the graph</p></body></html>", None))
        self.minNumber.setText(_translate("RunAnalyseDialogBase", "100", None))

