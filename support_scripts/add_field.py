from qgis.core import QgsProject, QgsVectorLayer, QgsTask
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMessageBox, QListWidgetItem, QApplication
from psycopg2 import IntegrityError, InternalError
from ..widgets.add_field import AddFieldFileDialog
from ..support_scripts.create_layer import set_label, add_background, set_zoom
from ..support_scripts.__init__ import TR
import traceback
import time
#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)


def add_fields_2_canvas(task, db, fields_db, defined_field, sources):
    """A function that adds fields that are not added previously.

    Parameters
    ----------
    task: QgsTask
        a QgsTask to run the function in
    db: DB
        A database connection
    fields_db: list
        list of the names of all fields in the database
    defined_field: str
        the last added field name
    sources: list
        list of source names

    Returns
    -------
    list
        If all went ok:
            [True, list of layers]
        Else:
            [False, exception, traceback]
    """
    try:
        layers = []
        for i, field in enumerate(fields_db):
            task.setProgress(i / len(fields_db) * 100)
            field = field[0]
            if defined_field != '':
                if field != defined_field:
                    continue
            for source in sources:
                if str(field).lower() in source.lower():
                    continue
            layer = db.add_postgis_layer('fields', 'polygon', 'public',
                                       extra_name=field + '_',
                                       filter_text="field_name='{f}'".format(f=field))
            set_label(layer, 'field_name')
            layers.append(layer)
        return [True, layers]
    except Exception as e:
        return [False, e, traceback.format_exc()]


class AddField:
    def __init__(self, parent_widget):
        """This class handle the creation of Fields. This class is also imported
        in the MeanAnalyse class.

        Parameters
        ----------
        parent_widget: GeoDataFarm
        """
        self.iface = parent_widget.iface
        self.tsk_mngr = parent_widget.tsk_mngr
        self.db = parent_widget.db
        translate = TR('AddField')
        self.tr = translate.tr
        self.dock_widget = parent_widget.dock_widget
        self.parent = parent_widget
        self.AFD = AddFieldFileDialog()
        self.field = None
        self.defined_field = ''

    def run(self):
        """Presents the sub widget AddField and connects the different
        buttons to their function"""
        self.AFD.show()
        self.AFD.PBSelectExtent.clicked.connect(self.clicked_define_field)
        self.AFD.PBSave.clicked.connect(self.save)
        self.AFD.PBHelp.clicked.connect(self.help)
        self.AFD.PBQuit.clicked.connect(self.quit)
        self.AFD.exec()
        self.parent.populate.reload_fields()

    def set_widget_connections(self):
        """Function that sets the main widget connections."""
        self.parent.dock_widget.PBAddField.clicked.connect(self.run)
        self.parent.dock_widget.PBRemoveField.clicked.connect(self.remove_field)
        self.parent.dock_widget.PBViewFields.clicked.connect(self.view_fields)

    def clicked_define_field(self, ignore_name=True):
        """Creates an empty polygon that's define a field"""
        if ignore_name:
            self.field = QgsVectorLayer("Polygon?crs=epsg:4326", 'Search area',
                                        "memory")
        else:
            name = self.AFD.LEFieldName.text()
            if len(name) == 0:
                QMessageBox.information(None, self.tr('Error:'),
                                        self.tr('Field name must be filled in.'))
                return
            self.field = QgsVectorLayer("Polygon?crs=epsg:4326", name, "memory")

        add_background()
        set_zoom(self.parent.iface, 2)
        self.field.startEditing()
        self.iface.actionAddFeature().trigger()
        QgsProject.instance().addMapLayer(self.field)

    def remove_field(self):
        """Removes a field that the user wants, a check that there are no
        data that is depended on is made."""
        j = -1
        for i in range(self.parent.dock_widget.LWFields.count()):
            j += 1
            item = self.parent.dock_widget.LWFields.item(j)
            if item.checkState() == 2:
                field_name = item.text()
                qm = QMessageBox()
                res = qm.question(None, self.tr('Question'),
                                  self.tr("Do you want to delete ") + str(field_name),
                                  qm.Yes, qm.No)
                if res == qm.No:
                    continue
                field_names = []
                for tble_type in ['plant', 'ferti', 'spray', 'harvest', 'soil']:
                    field_names.extend(self.db.execute_and_return("select field from {type}.manual".format(type=tble_type)))
                sql = """SELECT table_name
               FROM   information_schema.tables 
               WHERE  table_schema = 'other'"""
                for tble_type in self.db.execute_and_return(sql):
                    tbl = tble_type[0]
                    field_names.extend(self.db.execute_and_return("select field from other.{tbl}".format(tbl=tbl)))
                stop_removing = False
                for row in field_names:
                    if row[0] == field_name:
                        QMessageBox.information(None, self.tr('Error'),
                                                self.tr('There are data sets that are dependent on this field, '
                                                        'it cant be removed.'))
                        stop_removing = True
                if stop_removing:
                    continue
                sql = "delete from fields where field_name='{f}'".format(f=field_name)
                self.db.execute_sql(sql)
                self.parent.dock_widget.LWFields.takeItem(j)
                j -= 1

    def view_fields(self):
        """Add all fields that aren't displayed on the canvas,
        if no background map is loaded Google maps are loaded."""
        defined_field = self.defined_field
        if defined_field == '':
            add_background()
        sources = [layer.name().split('_')[0] for layer in QgsProject.instance().mapLayers().values()]
        fields_db = self.db.execute_and_return("select field_name from fields")
        task = QgsTask.fromFunction('Adding fields to the canvas', add_fields_2_canvas, self.db, fields_db,
                                    defined_field, sources,
                                    on_finished=self.finish)
        self.tsk_mngr.addTask(task)

    def finish(self, result, values):
        """Produces either an error message telling what went wrong or adds the fields to canvas and zoom to the layers.

        Parameters
        ----------
        result: object
        values: list
            If all went ok:
                [True, list of layers]
            Else:
                [False, exception, traceback]
        """
        if values[0] is False:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('Following error occurred: {m}\n\n Traceback: {t}'.format(m=values[1],
                                                                                                      t=values[2])))
            return
        for layer in values[-1]:
            QgsProject.instance().addMapLayer(layer)
        if self.defined_field == '':
            set_zoom(self.parent.iface, 1.1)
        self.defined_field = ''

    def quit(self):
        """Closes the widget."""
        self.AFD.PBSelectExtent.clicked.disconnect()
        self.AFD.PBSave.clicked.disconnect()
        self.AFD.PBHelp.clicked.disconnect()
        self.AFD.PBQuit.clicked.disconnect()
        self.AFD.done(0)

    def save(self):
        """Saves the field in the database"""
        try:
            self.iface.actionSaveActiveLayerEdits().trigger()
            self.iface.actionToggleEditing().trigger()
            feature = self.field.getFeature(1)
            QgsProject.instance().removeMapLayers([self.field.id()])
        except:
            QMessageBox.information(None, self.tr("Error:"), self.tr(
                'No coordinates were found, did you mark the field on the canvas?'))
            return
        polygon = feature.geometry().asWkt()
        name = self.AFD.LEFieldName.text()
        if len(name) == 0:
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Field name must be filled in.'))
            return
        sql = """Insert into fields (field_name, polygon) 
        VALUES ('{name}', st_geomfromtext('{poly}', 4326))""".format(name=name, poly=polygon)
        try:
            self.db.execute_sql(sql)
        except IntegrityError:
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Field name already exist, please select a new name'))
            return
        except InternalError as e:
            QMessageBox.information(None, self.tr('Error:'),
                                    str(e))
            return
        _name = QApplication.translate("qadashboard", name, None)
        item = QListWidgetItem(_name, self.dock_widget.LWFields)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.Unchecked)
        self.defined_field = name
        self.view_fields()

    def help(self):
        """A function that gives some advice on how the function works for the user.
        """
        QMessageBox.information(None, self.tr("Help:"), self.tr(
            'Here is where you add a field.\n'
            '1. Start with giving the field a name.\n'
            '2. Press "select extent" and switch to the QGIS window and zoom to your field.\n'
            '3. To mark your field, left click with the mouse in one corner of the field.\n'
            'then left click in all corners of the field then right click anywhere on the map.\n'
            '(There might be some errors while clicking the corners if the lines are crossing each other but in the end this does not matter if they does not do it in the end)\n'
            '4. Press "Save field" to store the field.\n'
            '5. When all fields are added press "Finished"'))
        return
