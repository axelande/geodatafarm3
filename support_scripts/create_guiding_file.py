from qgis.core import QgsProject, QgsVectorLayer, QgsField
from PyQt5 import QtCore
from PyQt5.QtCore import QVariant
from PyQt5.QtWidgets import QTableWidgetItem, QAbstractItemView, QMessageBox, \
    QFileDialog
from operator import xor
from osgeo import osr, ogr
from psycopg2 import ProgrammingError
from ..widgets.create_guide_file import CreateGuideFileDialog
from ..database_scripts.db import DB
from ..support_scripts.create_layer import CreateLayer
#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)


class CreateGuideFile:
    def __init__(self, parent_widget):
        """This class creates a guide file

        Parameters
        ----------
        parent_widget: GeoDataFarm
        """
        self.iface = parent_widget.iface
        self.plugin_dir = parent_widget.plugin_dir
        self.CGF = CreateGuideFileDialog()
        self.grid_layer = None
        self.tr = parent_widget.tr
        self.dock_widget = parent_widget.dock_widget
        self.db = parent_widget.db
        self.tables_in_tw_cb = 0
        self.nbr_selected_attr = 0
        self.select_table = ''
        self.eq_text2 = ''
        self.save_folder = ''
        self.rotation = 0

    def run(self):
        """Presents the sub widget HandleInput and connects the different
        buttons to their function"""
        self.CGF.show()
        self.CGF.PBAddParam.clicked.connect(self.add_to_param_list)
        self.CGF.PBRemParam.clicked.connect(self.remove_from_param_list)
        self.CGF.PBUpdate.clicked.connect(self.update_max_min)
        self.CGF.PBSelectOutput.clicked.connect(self.set_output_path)
        self.CGF.PBCreateFile.clicked.connect(self.create_file)
        self.CGF.PBHelp.clicked.connect(self.help)
        self.fill_cb()
        self.CGF.exec()

    def set_output_path(self):
        """Sets the path where the guide file should be saved."""
        dialog = QFileDialog()
        folder_path = dialog.getExistingDirectory(None, "Select Folder")
        self.CGF.LOutputPath.setText(str(folder_path))
        self.save_folder = folder_path
        self.CGF.PBCreateFile.setEnabled(True)

    def fill_cb(self):
        """Updates the ComboBox with names from the differnt schemas in the
        database"""
        lw_list = ['plant', 'ferti', 'spray', 'harvest', 'soil', 'other']
        self.CGF.CBDataSource.clear()
        names = []
        for schema in lw_list:
            table_names = self.db.get_tables_in_db(schema)
            for name in table_names:
                if name[0] in ["temp_polygon", 'manual', 'harrowing_manual',
                               'plowing_manual']:
                    continue
                names.append(schema + '.' + str(name[0]))
        self.CGF.CBDataSource.addItems(names)
        self.CGF.CBDataSource.activated[str].connect(self.possible_attr)

    def possible_attr(self, text):
        """Adds the name of the table which the user than can use as base for
        calculation of the guiding file.

        Parameters
        ----------
        text: str
            The schema.table
        """
        self.selected_table = text
        self.CGF.TWColumnNames.clear()
        params = self.db.get_all_columns(table=text.split('.')[1],
                                         schema=text.split('.')[0],
                                         exclude="'cmax', 'cmin', 'ctid', 'xmax', 'xmin', 'tableoid', 'pos', 'date_', 'polygon', 'field_row_id'")
        self.CGF.TWColumnNames.setRowCount(len(params))
        self.CGF.TWColumnNames.setColumnCount(1)
        self.CGF.TWColumnNames.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.attr_short_names = []
        for i, row in enumerate(params):
            item1 = QTableWidgetItem('{row}'.format(row=row[0]))
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            self.CGF.TWColumnNames.setItem(i, 0, item1)
        self.number_of_attr = i

    def add_to_param_list(self):
        """Adds the selected columns to the list of fields that should be
        treated as "special" in the database both to work as a parameter that
        could be evaluated and as a layer that is added to the canvas"""
        row_count = self.nbr_selected_attr
        self.CGF.TWSelected.setColumnCount(2)
        self.CGF.TWSelected.setColumnWidth(0, 75)
        self.CGF.TWSelected.setColumnWidth(1, 25)
        items_to_add = []
        existing_values = []
        if row_count != 0:
            for i in range(row_count):
                existing_values.append(self.CGF.TWSelected.item(i, 0).text())
        for i, item in enumerate(self.CGF.TWColumnNames.selectedItems()):
            if item.column() == 0 and item.text() not in existing_values:
                items_to_add.append(item.text())
        for i, item in enumerate(items_to_add, self.nbr_selected_attr):
            row_count += 1
            self.CGF.TWSelected.setRowCount(row_count)
            item1 = QTableWidgetItem(item)
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            item2 = QTableWidgetItem('[{i}]'.format(i=i))
            item2.setFlags(xor(item2.flags(), QtCore.Qt.ItemIsEditable))
            self.CGF.TWSelected.setItem(i, 0, item1)
            self.CGF.TWSelected.setItem(i, 1, item2)
        self.nbr_selected_attr = row_count

    def remove_from_param_list(self):
        """Removes the selected columns from the list of fields that should be
        treated as "special" in the database"""
        row_count = self.nbr_selected_attr
        if self.CGF.TWSelected.selectedItems() is None:
            QMessageBox.information(None, "Error:", self.tr('No row selected!'))
            return
        for item in self.CGF.TWSelected.selectedItems():
            self.CGF.TWSelected.removeRow(item.row())
            row_count -= 1
        self.nbr_selected_attr = row_count

    def update_max_min(self):
        """Update the text min, max text and set the equation for the guide
        file."""
        eq_text = self.CGF.TEEquation.toPlainText()
        row_count = self.nbr_selected_attr
        existing_values = []
        if row_count != 0:
            for i in range(row_count):
                existing_values.append([i, self.CGF.TWSelected.item(i, 0).text()])
        else:
            QMessageBox.information(None, "Error:", self.tr('You need to select at least one row'))
            return
        for i, attr_name in existing_values:
            eq_text2 = eq_text.replace('[{i}]'.format(i=i),
                                       'avg({n})'.format(n=attr_name))
            eq_text = eq_text.replace('[{i}]'.format(i=i),
                            attr_name)
        sql = """SELECT max({eq}), min({eq})
        FROM {tbl}""".format(eq=eq_text, tbl=self.selected_table)
        try:
            data = self.db.execute_and_return(sql)
        except ProgrammingError:
            QMessageBox.information(None, "Error:",
                                    self.tr('The selected data must be '
                                                    'integers or floats!'))
            return
        self.CGF.LMaxVal.setText('Max value: {val}'.format(val=data[0][0]))
        self.CGF.LMinVal.setText('Min value: {val}'.format(val=data[0][1]))
        self.eq_text2 = eq_text2
        self.CGF.PBSelectOutput.setEnabled(True)

    def create_file(self):
        """Creates the guide file with the information from the user."""
        cell_size = self.CGF.LECellSize.text()
        attr_name = self.CGF.LEAttrName.text()
        EPSG = self.CGF.LEEPSG.text()
        file_name = self.CGF.LEFileName.text()
        rotation = self.CGF.LERotation.text()
        float_type = False
        if self.CGF.CBDataType.currentText() == self.tr('Float (1.234)'):
            float_type = True
        sql = """WITH grid AS (
      SELECT 
        ROW_NUMBER() OVER () AS grid_id,
        m.geom 
      FROM (
        SELECT (
          ST_Dump(
            MAKEGRID_2D(
              ST_SetSRID(st_buffer(ST_Extent(pos),
                                   GREATEST(((select max(st_x(pos)) from {tbl}) - 
                                        (select min(st_x(pos)) from {tbl})),
                                       ((select max(st_y(pos)) from {tbl}) - 
                                        (select min(st_y(pos)) from {tbl})))/4
                                  ),4326),{c_size},{c_size}))
             ).geom  from {tbl}
      ) m
    ),
    --Defines the centroid of the whole grid
    centroid AS (
      SELECT ST_Centroid(ST_Collect(grid.geom)) AS geometry FROM grid
    ), 
    --Rotates around the defined centroid
    rotated as(SELECT ST_Rotate(grid.geom,radians({rot}),(SELECT geometry FROM centroid)) as polys 
               FROM grid
              ),
    --Selectes the polygons that are intersecting the orignal data
    select_data as (select polys
                   from rotated
                   where st_intersects(ST_SetSRID((select ST_Extent(pos) from {tbl}), 4326),
                                       polys))
    --Do the final selections and joining in some average data
    select st_astext(ST_Transform(polys, {EPSG})), {eq} 
    from select_data
    left join {tbl} on st_intersects(polys, pos)
    group by polys;""".format(c_size=cell_size, eq=self.eq_text2,
                              tbl=self.selected_table, EPSG=EPSG, rot=rotation)
        data = self.db.execute_and_return(sql)
        attribute_values = []
        driver = ogr.GetDriverByName('Esri Shapefile')
        ds = driver.CreateDataSource(self.save_folder + '\\' + file_name +'.shp')
        layer = ds.CreateLayer('', None, ogr.wkbPolygon)
        # Add one attribute
        if float_type:
            fd = ogr.FieldDefn(attr_name[:10], QVariant.Double)
        else:
            fd = ogr.FieldDefn(attr_name[:10], QVariant.Int)
        layer.CreateField(fd)
        defn = layer.GetLayerDefn()
        for poly, value in data:
            feat = ogr.Feature(defn)
            feat.SetField(attr_name[:10], value)
            geom = ogr.CreateGeometryFromWkt(poly)
            feat.SetGeometry(geom)
            layer.CreateFeature(feat)
            attribute_values.append(float(value))
            feat = geom = None  # destroy these

        # Save and close everything
        layer = ds  = feat = geom = None
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(int(EPSG))
        esri_output = srs.ExportToWkt()
        with open(self.save_folder + '\\' + file_name + '.prj',
                  'a') as prj_file:
            prj_file.write(esri_output)
        cl = CreateLayer(self.db, self.dock_widget)
        v_layer = QgsVectorLayer(self.save_folder + '\\' + file_name + ".shp",
                                 file_name, "ogr")
        layer = cl.equal_count(v_layer, data_values_list=attribute_values,
                               field=attr_name[:10], steps=15)
        QgsProject.instance().addMapLayer(layer)
        self.CGF.done(0)

    def help(self):
        """Shows a help message in a QMessageBox"""
        QMessageBox.information(None, self.tr("Help:"), self.tr(
            'Here you create a guide file.\n'
            '1. Start with select which data you want to base the guide file on in the top left corner.\n'
            '2. Select which of the attributes you want to use as base of calculation.\n'
            '3. When this is done you will have one or a few attributes in the right list with the name, [number].\n'
            '4. Now, change the equation to the right (default 100 + [0] * 2) to fit your idea and press update.\n'
            '5. When you press update the max and min value should be updated.\n'
            '6. Depending on your machine (that you want to feed with the guide file) you might want to use integers or float values.\n'
            '7. The attribute name and File name is for you, the output path is where the guide file will be stored.\n'
            '8. Cell size, how big grid you want for the guide file, EPSG let it be 4326 unless your machine require it!\n'
            '9. There is also an option for you if you want to rotate your grid.\n'
            '10. Finally press Create guide file and you are all set to go!'))
        return
