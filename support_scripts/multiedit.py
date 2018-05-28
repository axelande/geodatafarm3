import tempfile
import time
import codecs
import os
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QMessageBox
from PyQt5 import QtCore
from qgis.core import QgsMapLayer
from os import R_OK
import sys
from ..widgets.multiedit_dialog import MultiEditDialog

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/forms")


class MultiEdit:
    """This class enable the user to edit the attributes in a simple way, it is
    almost a copy of QuickMultiAttributeEdit, so all cred to them for it!
    https://github.com/lucadelu/QuickMultiAttributeEdit"""
    def __init__(self, parent):
        self.MED = MultiEditDialog()
        self.tr = parent.tr
        self.iface = parent.iface
        layer = self.iface.mapCanvas().currentLayer()
        self.MED.buttonBox.accepted.connect(self.run)
        delimchars = "#"

        if layer.type() == QgsMapLayer.VectorLayer:
            if layer.type() == QgsMapLayer.VectorLayer:
                provider = layer.dataProvider()
                fields = provider.fields()
                self.MED.QLEvalore.setText("")
                self.MED.CBfields.clear()
                for f in fields:
                    self.MED.CBfields.addItem(f.name(), f.name())
                    nF = layer.selectedFeatureCount()
                    if nF > 0:
                        self.MED.label.setText("<font color='green'>For <b>" + str(
                            nF) + "</b> selected elements in <b>" + layer.name() + "</b> set value of field</font>")
                        self.MED.CBfields.setFocus(True)
                        rm_if_too_old_settings_file(
                            tempfile.gettempdir() + "/QuickMultiAttributeEdit_tmp")
                        if os.path.exists(
                                tempfile.gettempdir() + "/QuickMultiAttributeEdit_tmp"):
                            in_file = codecs.open(
                                tempfile.gettempdir() + '/QuickMultiAttributeEdit_tmp',
                                encoding='utf8')
                            file_cont = in_file.read()
                            in_file.close()
                            file_cont_splitted = file_cont.split(delimchars)
                            lastlayer = file_cont_splitted[0]
                            lastfield = file_cont_splitted[1]
                            lastvalue = file_cont_splitted[2]
                            lkeepLatestValue = file_cont_splitted[3]
                            if (self.MED.CBfields.findText(
                                    lastfield) > -1):  # se esiste il nome del campo nel combobox
                                self.MED.CBfields.setCurrentIndex(
                                    self.MED.CBfields.findText(lastfield))
                                self.MED.cBkeepLatestValue.setChecked(str2bool(
                                    lkeepLatestValue))  # read thevalue from settings
                                if (
                                self.MED.cBkeepLatestValue.isChecked()):  # if true to keep latest input value
                                    self.MED.QLEvalore.setText(lastvalue)
                                    self.MED.QLEvalore.setFocus()

                    if (nF == 0):
                        infoString = self.tr(
                            "<font color='red'> Please select some elements into current <b>" + layer.name() + "</b> layer</font>")
                        self.MED.label.setText(infoString)
                        self.MED.buttonBox.button(QDialogButtonBox.Ok).setEnabled(
                            False)
                        self.MED.QLEvalore.setEnabled(False)
                        self.MED.CBfields.setEnabled(False)
        elif layer.type() != QgsMapLayer.VectorLayer:
            infoString = self.tr(
                "<font color='red'> Layer <b>" + layer.name() + "</b> is not a vector layer</font>")
            self.MED.label.setText(infoString)
            self.MED.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.MED.QLEvalore.setEnabled(False)
            self.MED.CBfields.setEnabled(False)
        else:
            infoString = self.tr(
                "<font color='red'> <b>No layer selected... Select a layer from the layer list...</b></font>")
            self.MED.label.setText(infoString)
            self.MED.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.MED.QLEvalore.setEnabled(False)
            self.MED.CBfields.setEnabled(False)

    def show(self):
        self.MED.show()
        self.MED.exec_()

    def run(self):
        delimchars = "#"
        layer = self.iface.mapCanvas().currentLayer()
        if not layer.isEditable():
            layer.startEditing()
        value = self.tr(self.MED.QLEvalore.displayText())
        nPosField = self.MED.CBfields.currentIndex()
        f_index = self.MED.CBfields.itemData(nPosField)[0]
        f_name = self.MED.CBfields.itemData(nPosField)
        if len(value) <= 0:
            infoString = self.tr("Warning <b> please input a value... </b>")
            self.MED.label.setText(infoString)
            return
        layer = self.iface.mapCanvas().currentLayer()
        if (layer):
            nF = layer.selectedFeatureCount()  # numero delle features selezionate
            if (nF > 0):
                oFeaIterator = layer.selectedFeatures()  # give the selected feauter new in api2
                for feature in oFeaIterator:  # in oFea2 there is an iterator object (api2)
                    layer.changeAttributeValue(feature.id(), nPosField, value,
                                               True)
                if not os.path.exists(
                        tempfile.gettempdir() + "/QuickMultiAttributeEdit_tmp"):
                    out_file = open(
                        tempfile.gettempdir() + '/QuickMultiAttributeEdit_tmp',
                        'w')
                    # out_file.write( layer.name() + delimchars +  self.tr(self.MED.CBfields.currentText()) + delimchars + value + delimchars + bool2str(self.MED.cBkeepLatestValue.isChecked())  )
                    out_file.write(layer.name() + delimchars + self.MED.CBfields.currentText() + delimchars + value + delimchars + bool2str(
                                           self.MED.cBkeepLatestValue.isChecked()))
                    out_file.close()

                else:
                    in_file = open(
                        tempfile.gettempdir() + '/QuickMultiAttributeEdit_tmp',
                        'r')
                    file_cont = in_file.read()
                    in_file.close()
                    file_cont_splitted = file_cont.split(delimchars)
                    lastlayer = file_cont_splitted[0]
                    lastfield = file_cont_splitted[1]
                    lastvalue = file_cont_splitted[2]
                    out_file = open(
                        tempfile.gettempdir() + '/QuickMultiAttributeEdit_tmp',
                        'w')
                    # out_file.write( layer.name() + delimchars +  self.tr(self.MED.CBfields.currentText()) + delimchars + value + delimchars + bool2str(self.MED.cBkeepLatestValue.isChecked())  )
                    out_file.write(layer.name() + delimchars + self.MED.CBfields.currentText() + delimchars + value + delimchars + bool2str(
                                           self.MED.cBkeepLatestValue.isChecked()))
                    out_file.close()
                self.iface.actionSaveActiveLayerEdits().trigger()
                self.iface.actionToggleEditing().trigger()
                # layer.commitChanges()
            else:
                QMessageBox.critical(self.iface.mainWindow(), "Error",
                                     "Please select at least one feature from <b> " + layer.name() + "</b> current layer")
        else:
            QMessageBox.critical(self.iface.mainWindow(), "Error",
                                 "Please select a layer")


def bool2str(bVar):
    if bVar:
        return 'True'
    else:
        return 'False'


def str2bool(bVar):
    if (bVar == 'True'):
        return True
    else:
        return False


def rm_if_too_old_settings_file(myPath_and_File):
    if os.path.exists(myPath_and_File) and os.path.isfile(
            myPath_and_File) and os.access(myPath_and_File, R_OK):
        now = time.time()
        tmpfileSectime = os.stat(myPath_and_File)[
            7]  # get last modified time,[8] would be last creation time
        if (
                now - tmpfileSectime > 60 * 60 * 12):  # if settings file is older than 12 hour
            os.remove(myPath_and_File)