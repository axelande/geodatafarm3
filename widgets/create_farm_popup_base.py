# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'create_farm_popup_base.ui'
#
# Created: Tue May 09 16:26:49 2017
#      by: PyQt4 UI code generator 4.10.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtWidgets

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtWidgets.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtWidgets.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtWidgets.QApplication.translate(context, text, disambig)

class Ui_ImportInputDialogBase(object):
    def setupUi(self, ImportInputDialogBase):
        ImportInputDialogBase.setObjectName(_fromUtf8("ImportInputDialogBase"))
        ImportInputDialogBase.resize(250, 267)
        self.button_box = QtWidgets.QDialogButtonBox(ImportInputDialogBase)
        self.button_box.setGeometry(QtCore.QRect(60, 240, 81, 23))
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel)
        self.button_box.setCenterButtons(False)
        self.button_box.setObjectName(_fromUtf8("button_box"))
        self.pb_insert_data_into_DB = QtWidgets.QPushButton(ImportInputDialogBase)
        self.pb_insert_data_into_DB.setEnabled(True)
        self.pb_insert_data_into_DB.setGeometry(QtCore.QRect(0, 190, 91, 41))
        self.pb_insert_data_into_DB.setObjectName(_fromUtf8("pb_insert_data_into_DB"))
        self.farm_name = QtWidgets.QLineEdit(ImportInputDialogBase)
        self.farm_name.setGeometry(QtCore.QRect(80, 40, 121, 20))
        self.farm_name.setObjectName(_fromUtf8("farm_name"))
        self.label_8 = QtWidgets.QLabel(ImportInputDialogBase)
        self.label_8.setGeometry(QtCore.QRect(18, 40, 61, 16))
        self.label_8.setObjectName(_fromUtf8("label_8"))
        self.label_10 = QtWidgets.QLabel(ImportInputDialogBase)
        self.label_10.setGeometry(QtCore.QRect(20, 70, 121, 16))
        self.label_10.setObjectName(_fromUtf8("label_10"))
        self.user_name = QtWidgets.QLineEdit(ImportInputDialogBase)
        self.user_name.setGeometry(QtCore.QRect(80, 70, 121, 20))
        self.user_name.setObjectName(_fromUtf8("user_name"))
        self.pass_word = QtWidgets.QLineEdit(ImportInputDialogBase)
        self.pass_word.setGeometry(QtCore.QRect(80, 100, 121, 20))
        self.pass_word.setObjectName(_fromUtf8("pass_word"))
        self.label_12 = QtWidgets.QLabel(ImportInputDialogBase)
        self.label_12.setGeometry(QtCore.QRect(20, 100, 121, 16))
        self.label_12.setObjectName(_fromUtf8("label_12"))
        self.email_field = QtWidgets.QLineEdit(ImportInputDialogBase)
        self.email_field.setGeometry(QtCore.QRect(80, 130, 121, 20))
        self.email_field.setObjectName(_fromUtf8("email_field"))
        self.label_13 = QtWidgets.QLabel(ImportInputDialogBase)
        self.label_13.setGeometry(QtCore.QRect(20, 130, 121, 16))
        self.label_13.setObjectName(_fromUtf8("label_13"))
        self.label_14 = QtWidgets.QLabel(ImportInputDialogBase)
        self.label_14.setGeometry(QtCore.QRect(10, 160, 201, 16))
        self.label_14.setObjectName(_fromUtf8("label_14"))
        self.label_9 = QtWidgets.QLabel(ImportInputDialogBase)
        self.label_9.setGeometry(QtCore.QRect(40, 0, 151, 16))
        self.label_9.setObjectName(_fromUtf8("label_9"))
        self.pButInsertDataIntoDB_2 = QtWidgets.QPushButton(ImportInputDialogBase)
        self.pButInsertDataIntoDB_2.setEnabled(True)
        self.pButInsertDataIntoDB_2.setGeometry(QtCore.QRect(100, 190, 131, 41))
        self.pButInsertDataIntoDB_2.setObjectName(_fromUtf8("pButInsertDataIntoDB_2"))

        self.retranslateUi(ImportInputDialogBase)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("accepted()")), ImportInputDialogBase.accept)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("rejected()")), ImportInputDialogBase.reject)
        QtCore.QMetaObject.connectSlotsByName(ImportInputDialogBase)

    def retranslateUi(self, ImportInputDialogBase):
        ImportInputDialogBase.setWindowTitle(_translate("ImportInputDialogBase", "Create farm", None))
        self.pb_insert_data_into_DB.setText(_translate("ImportInputDialogBase", "Create a new \n"
"database", None))
        self.farm_name.setText(_translate("ImportInputDialogBase", "farmname", None))
        self.label_8.setText(_translate("ImportInputDialogBase", "Farm name:", None))
        self.label_10.setText(_translate("ImportInputDialogBase", "User name:", None))
        self.user_name.setText(_translate("ImportInputDialogBase", "name", None))
        self.pass_word.setText(_translate("ImportInputDialogBase", "choose password", None))
        self.label_12.setText(_translate("ImportInputDialogBase", "Password:", None))
        self.email_field.setText(_translate("ImportInputDialogBase", "your@email.com", None))
        self.label_13.setText(_translate("ImportInputDialogBase", "e-mail", None))
        self.label_14.setText(_translate("ImportInputDialogBase", "(e-mail is only used to recover database)", None))
        self.label_9.setText(_translate("ImportInputDialogBase", "Create a new farm database", None))
        self.pButInsertDataIntoDB_2.setText(_translate("ImportInputDialogBase", "Connect to \n"
"existing database", None))

