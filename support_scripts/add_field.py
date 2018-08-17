from qgis.core import QgsProject, QgsVectorLayer
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMessageBox, QListWidgetItem, QApplication
from operator import xor
from psycopg2 import ProgrammingError, IntegrityError
from ..widgets.add_field import AddFieldFileDialog
#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)


class AddField:
    def __init__(self, parent_widget):
        """This class creates a guide file
        :param parent_widget"""
        self.iface = parent_widget.iface
        self.db = parent_widget.db
        self.tr = parent_widget.tr
        self.dock_widget = parent_widget.dock_widget
        self.AFD = AddFieldFileDialog()
        self._enable_years()
        self.field = None

    def _enable_years(self):
        for nr, y in enumerate(range(2000, 2030)):
            self.AFD.CBYear.addItem(str(y))
            item = self.AFD.CBYear.model().item(nr, 0)
            item.setCheckState(QtCore.Qt.Checked)
            item.setFlags(xor(item.flags(), QtCore.Qt.ItemIsEditable))
            item.setFlags(xor(item.flags(), QtCore.Qt.ItemIsUserCheckable))
            item.setFlags(xor(item.flags(), QtCore.Qt.ItemIsSelectable))

    def run(self):
        """Presents the sub widget HandleInput and connects the different
        buttons to their function"""
        self.AFD.show()
        self.AFD.PBSelectExtent.clicked.connect(self.clicked_define_field)
        self.AFD.PBSave.clicked.connect(self.save)
        self.AFD.PBHelp.clicked.connect(self.help)
        self.AFD.PBQuit.clicked.connect(self.quit)
        self.AFD.exec()

    def clicked_define_field(self):
        """Creates an empty polygon that's define a field"""
        self.field = QgsVectorLayer("Polygon?crs=epsg:4326", "temporary_points", "memory")
        sources = [layer.source() for layer in QgsProject.instance().mapLayers().values()]
        print(sources)
        source_found = False
        for source in sources:
            if 'xyz&url' in source:
                source_found = True
                print('found')
        if not source_found:
            print('adding')
            open_street_map = ["connections-xyz","OpenStreetMap Standard", "", "",
                               "OpenStreetMap contributors, CC-BY-SA",
                               "http://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png",
                               "", "19", "0"]
            urlWithParams = 'type=xyz&url=http://a.tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0'
            rlayer = QgsVectorLayer(urlWithParams, 'Open street map', 'wms')
            rlayer.isValid()
            QgsProject.instance().addMapLayer(rlayer)
        self.field.startEditing()
        self.iface.actionAddFeature().trigger()
        QgsProject.instance().addMapLayer(self.field)

    def quit(self):
        """Closes the widget."""
        self.AFD.done(0)

    def save(self):
        """Saves the field in the database"""
        try:
            self.iface.actionSaveActiveLayerEdits().trigger()
            self.iface.actionToggleEditing().trigger()
            feature = self.field.getFeature(1)
        except:
            QMessageBox.information(None, self.tr("Error:"), self.tr(
                'No coordinates where found, did you mark the field on the canvas?'))
            return
        polygon = feature.geometry().asWkt()
        name = self.AFD.LEFieldName.text()
        if len(name) == 0:
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Field name must be filled in.'))
            return
        year_str = ''
        for nr, y in enumerate(range(2000, 2030)):
            item = self.AFD.CBYear.model().item(nr, 0)
            if item.checkState():
                year_str += str(y) + ','
        year_str =year_str[:-1]
        sql = """Insert into fields (field_name, years, polygon) 
        VALUES ('{name}', '{year}', st_geomfromtext('{poly}', 4326))""".format(name=name, year=year_str, poly=polygon)
        try:
            self.db.execute_sql(sql)
        except IntegrityError:
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Field name all ready exist, please select a new name'))
            return
        _name = QApplication.translate("qadashboard", name, None)
        item = QListWidgetItem(_name, self.dock_widget.LWFields)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.Unchecked)

    def help(self):
        QMessageBox.information(None, self.tr("Help:"), self.tr(
            'Here is where you add a field.\n'
            '1. Start with giving the field a name.\n'
            '2. Press "select extent" and switch to the QGIS window and zoom to your field.\n'
            '3. To mark your field, left click with the mouse in one corner of the field.\n'
            'then left click in all corners of the field then right click anywhere on the map.\n'
            '(There might be some errors while clicking the corners if the lines are crossing each other but in the end this does not matter if they does not do it in the end)\n'
            '4. If a field is temporary or only valid since/until you can specify which years the field is valid to.\n'
            '5. Press "Save field" to store the field.\n'
            '6. When all fields are added press "Finished"'))
        return
