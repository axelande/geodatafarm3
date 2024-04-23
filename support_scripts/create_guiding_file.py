from operator import xor
import os

from osgeo import osr, ogr
from psycopg2 import ProgrammingError
from PyQt5 import QtCore
from PyQt5.QtCore import QVariant
from PyQt5.QtWidgets import QTableWidgetItem, QAbstractItemView, QMessageBox, \
    QFileDialog, QComboBox
from qgis.core import QgsProject, QgsVectorLayer

from ..support_scripts.__init__ import TR
from ..support_scripts.create_layer import CreateLayer
from ..widgets.create_guide_file import CreateGuideFileDialog
#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)


class CreateGuideFile:
    def __init__(self, parent):
        """This class creates a guide file

        Parameters
        ----------
        parent_widget: GeoDataFarm
        """
        self.iface = parent.iface
        self.plugin_dir = parent.plugin_dir
        self.populate = parent.populate
        self.CGF = CreateGuideFileDialog()
        self.grid_layer = None
        translate = TR('CreateGuideFile')
        self.tr = translate.tr
        self.dock_widget = parent.dock_widget
        self.db = parent.db
        self.parent = parent
        self.tables_in_tw_cb = 0
        self.nbr_selected_attr = 0
        self.select_table = ''
        self.eq_text2 = ''
        self.save_folder = ''
        self.rotation = 0
        self.attributes = {}
        self.selected = {}

    def run(self):
        """Presents the sub widget HandleInput and connects the different
        buttons to their function"""
        self.CGF.show()
        self.CGF.PBRemParam.clicked.connect(self.remove_from_param_list)
        self.CGF.PBUpdate.clicked.connect(self.update_max_min)
        self.CGF.PBSelectOutput.clicked.connect(self.set_output_path)
        self.CGF.PBCreateFile.clicked.connect(self.create_file)
        self.CGF.PBHelp.clicked.connect(self.help)
        self.fill_cb()
        self.populate.reload_fields(self.CGF.CBFields)
        self.CGF.TWSelected.setColumnCount(3)
        self.CGF.TWSelected.setColumnWidth(0, 150)
        self.CGF.TWSelected.setColumnWidth(1, 150)
        self.CGF.TWSelected.setColumnWidth(2, 25)
        if not self.parent.test_mode:
            self.CGF.exec()

    def set_output_path(self):
        """Sets the path where the guide file should be saved."""
        dialog = QFileDialog()
        if self.parent.test_mode:
            folder_path = "./tests/"
        else:
            folder_path = dialog.getExistingDirectory(None, "Select Folder")
        self.CGF.LOutputPath.setText(str(folder_path))
        self.save_folder = folder_path
        self.CGF.PBCreateFile.setEnabled(True)

    def fill_cb(self):
        """Updates the ComboBox with names from the differnt schemas in the
        database"""
        lw_list = ['plant', 'ferti', 'spray', 'harvest', 'soil', 'other']
        self.CGF.CBDataSource.clear()
        self.CGF.CBDataSource.addItems(lw_list)
        self.CGF.CBDataSource.activated[str].connect(self.possible_attr)

    def possible_attr(self, schema):
        """Adds the name of the table which the user than can use as base for
        calculation of the guiding file.

        Parameters
        ----------
        text: str
            The schema.table
        """
        self.CGF.TWColumnNames.clear()
        names = []
        table_names = self.db.get_tables_in_db(schema)
        for name in table_names:
            if name in ["temp_polygon", 'manual', 'harrowing_manual',
                            'plowing_manual']:
                continue
            names.append(f'{schema}.{name}')
        self.CGF.TWColumnNames.setRowCount(len(names))
        self.CGF.TWColumnNames.setColumnCount(2)
        self.attributes = {}
        
        for i, row in enumerate(names):
            schema, tbl = row.split('.')
            attributes = self.db.get_all_columns(table=tbl,
                                            schema=schema,
                                            exclude="'cmax', 'cmin', 'ctid', 'xmax', 'xmin', 'tableoid', 'pos', 'date_', 'polygon', 'field_row_id'")
            # self.CGF.TWColumnNames.setSelectionBehavior(QAbstractItemView.SelectRows)
            item1 = QTableWidgetItem('{row}'.format(row=row))
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            self.CGF.TWColumnNames.setItem(i, 0, item1)
            popup_menu = QComboBox()
            popup_menu.addItems(attributes)
            self.attributes[i] = {'tbl': row,
                                  'attributes': attributes}
            self.CGF.TWColumnNames.setCellWidget(i, 1, popup_menu)
            popup_menu.activated.connect(lambda index, row=i: self.add_to_param_list(index, row))

    def add_to_param_list(self, index, row):
        """Adds the selected columns to the list of fields that should be
        treated as "special" in the database both to work as a parameter that
        could be evaluated and as a layer that is added to the canvas"""

        row_count = self.nbr_selected_attr
        row_count += 1
        self.CGF.TWSelected.setRowCount(row_count)
        item1 = QTableWidgetItem(self.attributes[row]['tbl'])
        item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
        item2 = QTableWidgetItem(self.attributes[row]['attributes'][index])
        item2.setFlags(xor(item2.flags(), QtCore.Qt.ItemIsEditable))
        item3 = QTableWidgetItem(f'[{len(self.selected)}]')
        item3.setFlags(xor(item3.flags(), QtCore.Qt.ItemIsEditable))
        self.CGF.TWSelected.setItem(row_count - 1, 0, item1)
        self.CGF.TWSelected.setItem(row_count - 1, 1, item2)
        self.CGF.TWSelected.setItem(row_count - 1, 2, item3)
        self.nbr_selected_attr = row_count
        self.selected[len(self.selected)] = [self.attributes[row]['tbl'], self.attributes[row]['attributes'][index]]

    def remove_from_param_list(self):
        """Removes the selected columns from the list"""
        row_count = self.nbr_selected_attr
        if self.CGF.TWSelected.selectedItems() is None:
            QMessageBox.information(None, "Error:", self.tr('No row selected!'))
            return
        rows_to_delete = []
        for item in self.CGF.TWSelected.selectedItems():
            if not item.row() in rows_to_delete:
                rows_to_delete.append(item.row())
        deleted_rows = 0
        for i in rows_to_delete:
            self.CGF.TWSelected.removeRow(i - deleted_rows)
            row_count -= 1
            deleted_rows += 1
        self.nbr_selected_attr = row_count

    def update_max_min(self):
        """Update the text min, max text and set the equation for the guide
        file."""
        field = self.CGF.CBFields.currentText()
        if field == self.tr("--- Select field ---"):
            QMessageBox.information(None, "Error:", self.tr('A field must be selected'))
            return
        eq_text_min = self.CGF.TEEquation.toPlainText()
        eq_text_max = self.CGF.TEEquation.toPlainText()
        row_count = self.nbr_selected_attr
        if row_count == 0:
            QMessageBox.information(None, "Error:", self.tr('You need to select at least one row'))
            return
        for i, (tbl, attribute) in self.selected.items():
            columns = self.db.get_all_columns(tbl.split('.')[1], tbl.split('.')[0])
            if 'polygon' in columns:
                join_geom = 'polygon'
            else:
                join_geom = 'pos'
            sql = f"""SELECT max({attribute}), min({attribute})
            FROM {tbl} tbl
            join fields fi on st_intersects(tbl.{join_geom}, fi.polygon)
            where field_name = '{self.CGF.CBFields.currentText()}'"""
            try:
                data = self.db.execute_and_return(sql)
            except ProgrammingError:
                QMessageBox.information(None, "Error:",
                                        self.tr('The selected data must be '
                                                        'integers or floats!'))
                return
            eq_text_min = eq_text_min.replace(f'[{i}]', f'{data[0][1]}')
            eq_text_max = eq_text_max.replace(f'[{i}]', f'{data[0][0]}')
        print(eq_text_min)
        
        self.CGF.LMaxVal.setText(f'Max value: {eval(eq_text_max)}')
        self.CGF.LMinVal.setText(f'Min value: {eval(eq_text_min)}')
        self.CGF.PBSelectOutput.setEnabled(True)

    def create_file(self):
        """Creates the guide file with the information from the user."""
        print(self.selected)
        cell_size = self.CGF.LECellSize.text()
        try: 
            int(cell_size) 
        except ValueError:
            QMessageBox.information(None, "Error:", self.tr('Cell size must be integer'))
            return
        if f"{int(cell_size)}" != f"{cell_size}":
            QMessageBox.information(None, "Error:", self.tr('Cell size must be integer'))
            return
        attr_name = self.CGF.LEAttrName.text()
        EPSG = self.CGF.LEEPSG.text()
        file_name = self.CGF.LEFileName.text()
        rotation = self.CGF.LERotation.text()
        float_type = False
        if self.CGF.CBDataType.currentText() == self.tr('Float (1.234)'):
            float_type = True

        sql = f"""WITH grid AS (
      SELECT 
        ROW_NUMBER() OVER () AS grid_id,
        m.geom 
      FROM (
        SELECT (
          ST_Dump(
            MAKEGRID_2D(polygon,{cell_size},{cell_size}))
             ).geom  
             from fields
            where field_name = '{self.CGF.CBFields.currentText()}'
      ) m
    ),
    --Defines the centroid of the whole grid
    centroid AS (
      SELECT ST_Centroid(ST_Collect(grid.geom)) AS geometry FROM grid
    ), 
    --Rotates around the defined centroid
    rotated as(SELECT ST_Rotate(grid.geom,radians({rotation}),(SELECT geometry FROM centroid)) as polys 
               FROM grid
              ),
    
    --Do the final selections and joining in some average data
    final as(select st_astext(ST_Transform(polys, {EPSG})), """
        eq = self.CGF.TEEquation.toPlainText()
        for i, (tbl, attribute) in self.selected.items():
            eq =  eq.replace(f"[{i}]", f"case when avg(tbl_{i}.{attribute}) is null then 0 else avg(tbl_{i}.{attribute}) end")
        sql += eq +""" as val
        from rotated
        """
        for i, (tbl, attribute) in self.selected.items():
            if 'polygon' in self.db.get_all_columns(tbl.split('.')[1], tbl.split('.')[0]):
                join_geom = 'polygon'
            else:
                join_geom = 'pos'
            sql += f"""JOIN {tbl} tbl_{i} on st_intersects(polys, tbl_{i}.{join_geom})
            """
        sql += """group by polys)
                select * 
    from final 
    where val is not null"""
        print(sql)
        data = self.db.execute_and_return(sql)
        attribute_values = []
        driver = ogr.GetDriverByName('Esri Shapefile')
        path = os.path.join(self.save_folder, f'{file_name}.shp')
        print(path)
        ds = driver.CreateDataSource(path)
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
            if float_type:
                feat.SetField(attr_name[:10], value)
            else:
                feat.SetField(attr_name[:10], int(value))
            geom = ogr.CreateGeometryFromWkt(poly)
            feat.SetGeometry(geom)
            layer.CreateFeature(feat)
            attribute_values.append(float(value))
            feat = geom = None  # destroy these
        self.add_prj_file(EPSG, path)
        
        # Save and close everything
        ds.Destroy()
        layer = ds  = feat = geom = driver = None
        if not self.parent.test_mode:
            cl = CreateLayer(self.db, self.dock_widget)
            v_layer = QgsVectorLayer(path,
                                    file_name, "ogr")
            layer = cl.equal_count(v_layer, data_values_list=attribute_values,
                                field=attr_name[:10], steps=15)
            QgsProject.instance().addMapLayer(layer)
            cl = v_layer = layer = None
        self.CGF.done(0)

    def add_prj_file(self, EPSG, path):
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(int(EPSG))
        esri_output = srs.ExportToWkt()
        with open(path[:-4] + '.prj', 'a') as prj_file:
            prj_file.write(esri_output)

    def help(self):
        """Shows a help message in a QMessageBox"""
        QMessageBox.information(None, self.tr("Help:"), self.tr(
            'Here you create a guide file.\n'
            '1. Start with select which data you want to base the guide file on in the top left corner.\n'
            '2. Select your field.\n'
            '3. Select which of the data sets and attributes you want to use as base of calculation.\n'
            '4. Now, change the equation to the right (default 100 + [0] * 2) to fit your idea and press update. (use the equivalent [number] to include each data set)\n'
            '5. When you press update the max and min value should be updated.\n'
            '6. Depending on your machine (that you want to feed with the guide file) you might want to use integers or float values.\n'
            '7. The attribute name and File name is for you, the output path is where the guide file will be stored.\n'
            '8. Cell size, how big grid you want for the guide file, EPSG let it be 4326 unless your machine require it!\n'
            '9. There is also an option for you if you want to rotate your grid.\n'
            '10. Finally press Create guide file and you are all set to go!'))
        return
