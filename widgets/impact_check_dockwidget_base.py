# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'impact_check_dockwidget_base.ui'
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

class Ui_GeoDataFarmDockWidgetBase(object):
    def setupUi(self, GeoDataFarmDockWidgetBase):
        GeoDataFarmDockWidgetBase.setObjectName(_fromUtf8("GeoDataFarmDockWidgetBase"))
        GeoDataFarmDockWidgetBase.resize(290, 480)
        GeoDataFarmDockWidgetBase.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.dockWidgetContents = QtGui.QWidget()
        self.dockWidgetContents.setObjectName(_fromUtf8("dockWidgetContents"))
        self.label = QtGui.QLabel(self.dockWidgetContents)
        self.label.setGeometry(QtCore.QRect(10, 155, 291, 31))
        self.label.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.label.setObjectName(_fromUtf8("label"))
        self.pb_add_input_file = QtGui.QPushButton(self.dockWidgetContents)
        self.pb_add_input_file.setGeometry(QtCore.QRect(10, 10, 231, 23))
        self.pb_add_input_file.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.pb_add_input_file.setObjectName(_fromUtf8("pb_add_input_file"))
        self.pb_run_analyse = QtGui.QPushButton(self.dockWidgetContents)
        self.pb_run_analyse.setGeometry(QtCore.QRect(10, 360, 211, 23))
        self.pb_run_analyse.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.pb_run_analyse.setObjectName(_fromUtf8("pb_run_analyse"))
        self.LWtable_names = QtGui.QListWidget(self.dockWidgetContents)
        self.LWtable_names.setGeometry(QtCore.QRect(10, 190, 256, 131))
        self.LWtable_names.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.LWtable_names.setObjectName(_fromUtf8("LWtable_names"))
        self.pb_uppdate_list = QtGui.QPushButton(self.dockWidgetContents)
        self.pb_uppdate_list.setGeometry(QtCore.QRect(10, 132, 75, 23))
        self.pb_uppdate_list.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.pb_uppdate_list.setObjectName(_fromUtf8("pb_uppdate_list"))
        self.pb_add_harvest_file = QtGui.QPushButton(self.dockWidgetContents)
        self.pb_add_harvest_file.setGeometry(QtCore.QRect(10, 70, 231, 23))
        self.pb_add_harvest_file.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.pb_add_harvest_file.setObjectName(_fromUtf8("pb_add_harvest_file"))
        self.pb_remove_item = QtGui.QPushButton(self.dockWidgetContents)
        self.pb_remove_item.setGeometry(QtCore.QRect(10, 390, 211, 23))
        self.pb_remove_item.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.pb_remove_item.setObjectName(_fromUtf8("pb_remove_item"))
        self.pb_add_input_file_2 = QtGui.QPushButton(self.dockWidgetContents)
        self.pb_add_input_file_2.setEnabled(False)
        self.pb_add_input_file_2.setGeometry(QtCore.QRect(10, 40, 231, 23))
        self.pb_add_input_file_2.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.pb_add_input_file_2.setObjectName(_fromUtf8("pb_add_input_file_2"))
        self.pb_add_new_farm = QtGui.QPushButton(self.dockWidgetContents)
        self.pb_add_new_farm.setGeometry(QtCore.QRect(10, 420, 141, 23))
        self.pb_add_new_farm.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.pb_add_new_farm.setObjectName(_fromUtf8("pb_add_new_farm"))
        self.farm_name = QtGui.QLabel(self.dockWidgetContents)
        self.farm_name.setGeometry(QtCore.QRect(160, 420, 131, 31))
        self.farm_name.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.farm_name.setObjectName(_fromUtf8("farm_name"))
        self.pb_add_harvest_file_2 = QtGui.QPushButton(self.dockWidgetContents)
        self.pb_add_harvest_file_2.setEnabled(False)
        self.pb_add_harvest_file_2.setGeometry(QtCore.QRect(10, 100, 231, 23))
        self.pb_add_harvest_file_2.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.pb_add_harvest_file_2.setObjectName(_fromUtf8("pb_add_harvest_file_2"))
        self.pb_add_2_canvas = QtGui.QPushButton(self.dockWidgetContents)
        self.pb_add_2_canvas.setGeometry(QtCore.QRect(10, 330, 211, 23))
        self.pb_add_2_canvas.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedKingdom))
        self.pb_add_2_canvas.setObjectName(_fromUtf8("pb_add_2_canvas"))
        GeoDataFarmDockWidgetBase.setWidget(self.dockWidgetContents)

        self.retranslateUi(GeoDataFarmDockWidgetBase)
        QtCore.QMetaObject.connectSlotsByName(GeoDataFarmDockWidgetBase)

    def retranslateUi(self, GeoDataFarmDockWidgetBase):
        GeoDataFarmDockWidgetBase.setWindowTitle(_translate("GeoDataFarmDockWidgetBase", "GeoFarm", None))
        self.label.setText(_translate("GeoDataFarmDockWidgetBase", "Choose which files that you want to \n"
"include in the analyse: ", None))
        self.pb_add_input_file.setText(_translate("GeoDataFarmDockWidgetBase", "1. Add point input data", None))
        self.pb_run_analyse.setText(_translate("GeoDataFarmDockWidgetBase", "Run the analyse", None))
        self.pb_uppdate_list.setText(_translate("GeoDataFarmDockWidgetBase", "Update list", None))
        self.pb_add_harvest_file.setText(_translate("GeoDataFarmDockWidgetBase", "3. Add harvest data", None))
        self.pb_remove_item.setText(_translate("GeoDataFarmDockWidgetBase", "Remove selected items", None))
        self.pb_add_input_file_2.setText(_translate("GeoDataFarmDockWidgetBase", "2. Input -> surface and insert to database", None))
        self.pb_add_new_farm.setText(_translate("GeoDataFarmDockWidgetBase", "Create new farm database", None))
        self.farm_name.setText(_translate("GeoDataFarmDockWidgetBase", "No farm database created", None))
        self.pb_add_harvest_file_2.setText(_translate("GeoDataFarmDockWidgetBase", "4. Add harvest data to database", None))
        self.pb_add_2_canvas.setText(_translate("GeoDataFarmDockWidgetBase", "Add selected tables to the canvas", None))

