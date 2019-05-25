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
from ..support_scripts.__init__ import TR
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/forms")


class MultiEdit:
    """This class enable the user to edit the attributes in a simple way, it is
    almost a copy of QuickMultiAttributeEdit, so all cred to them for it!
    https://github.com/lucadelu/QuickMultiAttributeEdit"""
    def __init__(self, parent):
        """Initiate the plugin and calls on do_checks"""
        self.MED = MultiEditDialog()
        translate = TR('MultiEdit')
        self.tr = translate.tr
        self.iface = parent.iface
        self.db = parent.db
        self.layer = self.iface.mapCanvas().currentLayer()
        self.MED.buttonBox.accepted.connect(self.run)
        self.do_checks()

    def do_checks(self):
        """Checks that all is ready to be updated"""
        delimchars = "#"
        if self.layer is None:
            QMessageBox.information(None, self.tr("Error"),
                                    self.tr("Please select a layer"))
            return
        if self.layer.type() == QgsMapLayer.VectorLayer:
            if self.layer.type() == QgsMapLayer.VectorLayer:
                provider = self.layer.dataProvider()
                fields = provider.fields()
                self.MED.QLEvalore.setText("")
                self.MED.CBfields.clear()
                for f in fields:
                    self.MED.CBfields.addItem(f.name(), f.name())
                    nF = self.layer.selectedFeatureCount()
                    if nF > 0:
                        self.MED.label.setText("<font color='green'>For <b>" + str(
                            nF) + "</b> selected elements in <b>" + self.layer.name() + "</b> set value of field</font>")
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
                            "<font color='red'> Please select some elements into current <b>" + self.layer.name() + "</b> layer</font>")
                        self.MED.label.setText(infoString)
                        self.MED.buttonBox.button(QDialogButtonBox.Ok).setEnabled(
                            False)
                        self.MED.QLEvalore.setEnabled(False)
                        self.MED.CBfields.setEnabled(False)
        elif self.layer.type() != QgsMapLayer.VectorLayer:
            infoString = self.tr(
                "<font color='red'> Layer <b>" + self.layer.name() + "</b> is not a vector layer</font>")
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
        """Displays the widget"""
        self.MED.show()
        self.MED.exec_()

    def run(self):
        """Change the values, if it is a postgres database source it does the
        update directly to the server and then reloads the layer."""
        delimchars = "#"
        layer = self.iface.mapCanvas().currentLayer()
        if not layer.isEditable():
            layer.startEditing()
        value = self.tr(self.MED.QLEvalore.displayText())
        nPosField = self.MED.CBfields.currentIndex()
        if len(value) <= 0:
            infoString = self.tr("Warning <b> please input a value... </b>")
            self.MED.label.setText(infoString)
            return
        layer = self.iface.mapCanvas().currentLayer()
        if layer:
            if layer.source()[:6] == 'dbname':
                if layer.selectedFeatureCount() > 0:
                    ids_to_change = []
                    for feature in layer.getSelectedFeatures():
                        ids_to_change.append(feature.attributes()[0])
                    tbl = layer.source()[layer.source().find('table')+6:layer.source().find('(polygon)')-1]
                    field_name = layer.fields()[nPosField].name()
                    type_ = layer.fields()[nPosField].typeName()
                    if type_ == 'int4' or type_ == 'float4':
                        f_value = value
                    else:
                        f_value = "'" + value + "'"
                    sql = """UPDATE {tbl}
                    SET {field}={field_value}
                    where field_row_id in ({ids})""".format(tbl=tbl, field=field_name,
                                                            field_value=f_value, ids=str(ids_to_change)[1:-1])
                    self.db.execute_sql(sql)
                    self.iface.actionSaveActiveLayerEdits().trigger()
                    self.iface.actionToggleEditing().trigger()
                    layer.triggerRepaint()
                else:
                    QMessageBox.critical(self.iface.mainWindow(), self.tr("Error"),
                                         self.tr("Please select at least one feature from <b>{lyr}</b> current layer".format(lyr=layer.name())))
            else:
                nF = layer.selectedFeatureCount()
                if nF > 0:
                    oFeaIterator = layer.selectedFeatures()  # give the selected feature new in api2
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
                        path_ext = False
                        in_file = open(
                            tempfile.gettempdir() + '/QuickMultiAttributeEdit_tmp',
                            'r')
                        file_cont = in_file.read()
                        in_file.close()
                        file_cont_splitted = file_cont.split(delimchars)
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
                    QMessageBox.critical(self.iface.mainWindow(), self.tr("Error"),
                                         self.tr("Please select at least one feature from <b>{lyr}</b> current layer".format(lyr=layer.name())))
        else:
            QMessageBox.critical(self.iface.mainWindow(), self.tr("Error"),
                                 self.tr("Please select a layer"))


def bool2str(b_var):
    """Converts a str to bool

    Parameters
    ----------
    b_var: bool

    Returns
    -------
    str
    """

    if b_var:
        return 'True'
    else:
        return 'False'


def str2bool(b_var):
    """Converts a str to bool

    Parameters
    ----------
    b_var: str

    Returns
    -------
    bool
    """
    if b_var == 'True':
        return True
    else:
        return False


def rm_if_too_old_settings_file(my_path_and_file):
    """Removes the settings file if it is too old."""
    if os.path.exists(my_path_and_file) and os.path.isfile(
            my_path_and_file) and os.access(my_path_and_file, R_OK):
        now = time.time()
        tmpfileSectime = os.stat(my_path_and_file)[
            7]  # get last modified time,[8] would be last creation time
        if (
                now - tmpfileSectime > 60 * 60 * 12):  # if settings file is older than 12 hour
            os.remove(my_path_and_file)