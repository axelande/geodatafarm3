from typing import Self
from operator import xor
import os
import re

from osgeo import osr, ogr
from psycopg2 import ProgrammingError, sql as pgsql
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QTableWidgetItem, QAbstractItemView, QMessageBox, \
    QFileDialog, QComboBox
from qgis.core import QgsProject, QgsVectorLayer

from ..support_scripts.__init__ import TR
from ..support_scripts.create_layer import CreateLayer
from ..widgets.create_guide_file import CreateGuideFileDialog
from ..support_scripts.qt_data import _item_flag
#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)


class CreateGuideFile:
    def __init__(self: Self, parent) -> None:
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

    def _show_message(self: Self, title: str, message: str,
                      detail: str = '', level: str = 'error') -> None:
        """Show a styled message dialog.

        Parameters
        ----------
        title: str
        message: str
        detail: str, optional
        level: str, 'error', 'warning', or 'info'
        """
        msg = QMessageBox()
        # Qt5 uses QMessageBox.Critical, Qt6 uses QMessageBox.Icon.Critical
        try:
            icon_enum = QMessageBox.Icon
        except AttributeError:
            icon_enum = QMessageBox
        if level == 'error':
            msg.setIcon(icon_enum.Critical)
            color = '#c62828'
            icon_text = 'Error'
        elif level == 'warning':
            msg.setIcon(icon_enum.Warning)
            color = '#e65100'
            icon_text = 'Warning'
        else:
            msg.setIcon(icon_enum.Information)
            color = '#1565c0'
            icon_text = 'Info'

        msg.setWindowTitle(f'GeoDataFarm - {icon_text}')
        msg.setText(f'<b style="color: {color}; font-size: 10pt;">{title}</b>')
        msg.setInformativeText(message)
        if detail:
            msg.setDetailedText(detail)
        msg.setStyleSheet("""
            QMessageBox { background: #ffffff; }
            QMessageBox QLabel { font-size: 9pt; color: #333333; }
            QPushButton {
                background-color: #3574b0; color: white; border: none;
                border-radius: 3px; padding: 5px 16px; font-size: 9pt;
                min-width: 70px;
            }
            QPushButton:hover { background-color: #2a5f8f; }
        """)
        msg.exec()

    def run(self: Self) -> None:
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

    def set_output_path(self: Self) -> None:
        """Sets the path where the guide file should be saved."""
        dialog = QFileDialog()
        if self.parent.test_mode:
            folder_path = "./tests/"
        else:
            folder_path = dialog.getExistingDirectory(None, "Select Folder")
        self.CGF.LOutputPath.setText(str(folder_path))
        self.save_folder = folder_path
        self.CGF.PBCreateFile.setEnabled(True)

    def fill_cb(self: Self) -> None:
        """Updates the ComboBox with names from the differnt schemas in the
        database"""
        lw_list = [self.tr('-- Select base file --'),'plant', 'ferti', 'spray', 'harvest', 'soil', 'other']
        self.CGF.CBDataSource.clear()
        self.CGF.CBDataSource.addItems(lw_list)
        self.CGF.CBDataSource.activated.connect(
            lambda idx: self.possible_attr(self.CGF.CBDataSource.currentText())
        )
        self.CGF.CBFields.activated.connect(self._refresh_tables_for_field)

    def _refresh_tables_for_field(self: Self) -> None:
        """When the field selection changes, refresh the table list if a data
        source is already selected."""
        source = self.CGF.CBDataSource.currentText()
        if source and source != self.tr('-- Select base file --'):
            self.possible_attr(source)

    def _get_tables_for_field(self: Self, schema: str,
                              field_name: str) -> set:
        """Get table names associated with a field from the manual table.

        Parameters
        ----------
        schema: str
        field_name: str

        Returns
        -------
        set
            Set of table names linked to the field
        """
        tables = set()
        if schema == 'other':
            manual_tables = ['plowing_manual', 'harrowing_manual']
        else:
            manual_tables = ['manual']
        for manual_tbl in manual_tables:
            try:
                query = pgsql.SQL("SELECT table_ FROM {schema}.{tbl} WHERE field = %s").format(
                    schema=pgsql.Identifier(schema),
                    tbl=pgsql.Identifier(manual_tbl))
                rows = self.db.execute_and_return(query, params=(field_name,))
                for row in rows:
                    if row[0]:
                        tables.add(row[0])
            except Exception:
                continue
        return tables

    def possible_attr(self: Self, schema: str) -> None:
        """Adds the name of the table which the user than can use as base for
        calculation of the guiding file. If a field is selected, only tables
        linked to that field (via the manual table) are shown. Only numeric
        columns are listed as selectable attributes.

        Parameters
        ----------
        schema: str
            The schema name
        """
        self.CGF.TWColumnNames.clear()
        field_name = self.CGF.CBFields.currentText()
        filter_by_field = (field_name
                           and field_name != '-- Select field --'
                           and field_name != self.tr('--- Select field ---'))

        if filter_by_field:
            field_tables = self._get_tables_for_field(schema, field_name)
        else:
            field_tables = None

        names = []
        table_names = self.db.get_tables_in_db(schema)
        for name in table_names:
            if name in ["temp_polygon", 'manual', 'harrowing_manual',
                            'plowing_manual']:
                continue
            if field_tables is not None and name not in field_tables:
                continue
            names.append(f'{schema}.{name}')

        self.CGF.TWColumnNames.setRowCount(len(names))
        self.CGF.TWColumnNames.setColumnCount(2)
        self.attributes = {}

        exclude = "'cmax', 'cmin', 'ctid', 'xmax', 'xmin', 'tableoid', 'pos', 'date_', 'polygon', 'field_row_id'"
        for i, row in enumerate(names):
            s, tbl = row.split('.')
            attributes = self.db.get_numeric_columns(
                table=tbl, schema=s, exclude=exclude)
            if not attributes:
                continue
            item1 = QTableWidgetItem('{row}'.format(row=row))
            item1.setFlags(xor(item1.flags(), _item_flag('ItemIsEditable')))
            self.CGF.TWColumnNames.setItem(i, 0, item1)
            popup_menu = QComboBox()
            popup_menu.addItems(attributes)
            self.attributes[i] = {'tbl': row,
                                  'attributes': attributes}
            self.CGF.TWColumnNames.setCellWidget(i, 1, popup_menu)
            popup_menu.activated.connect(lambda index, row=i: self.add_to_param_list(index, row))

    def add_to_param_list(self: Self, index: int, row: int) -> None:
        """Adds the selected columns to the list of fields that should be
        treated as "special" in the database both to work as a parameter that
        could be evaluated and as a layer that is added to the canvas"""

        row_count = self.nbr_selected_attr
        row_count += 1
        self.CGF.TWSelected.setRowCount(row_count)
        item1 = QTableWidgetItem(self.attributes[row]['tbl'])
        item1.setFlags(xor(item1.flags(), _item_flag('ItemIsEditable')))
        item2 = QTableWidgetItem(self.attributes[row]['attributes'][index])
        item2.setFlags(xor(item2.flags(), _item_flag('ItemIsEditable')))
        item3 = QTableWidgetItem(f'[{len(self.selected)}]')
        item3.setFlags(xor(item3.flags(), _item_flag('ItemIsEditable')))
        self.CGF.TWSelected.setItem(row_count - 1, 0, item1)
        self.CGF.TWSelected.setItem(row_count - 1, 1, item2)
        self.CGF.TWSelected.setItem(row_count - 1, 2, item3)
        self.nbr_selected_attr = row_count
        self.selected[len(self.selected)] = [self.attributes[row]['tbl'], self.attributes[row]['attributes'][index]]

    def remove_from_param_list(self: Self) -> None:
        """Removes the selected columns from the list and rebuilds
        self.selected to stay in sync with the table widget."""
        if self.CGF.TWSelected.selectedItems() is None:
            self._show_message('No selection',
                               self.tr('Please select a row to remove.'),
                               level='warning')
            return
        rows_to_delete = set()
        for item in self.CGF.TWSelected.selectedItems():
            rows_to_delete.add(item.row())
        if not rows_to_delete:
            self._show_message('No selection',
                               self.tr('Please select a row to remove.'),
                               level='warning')
            return
        for i in sorted(rows_to_delete, reverse=True):
            self.CGF.TWSelected.removeRow(i)
        # Rebuild self.selected from the remaining table rows
        new_selected = {}
        for i in range(self.CGF.TWSelected.rowCount()):
            tbl = self.CGF.TWSelected.item(i, 0).text()
            attr = self.CGF.TWSelected.item(i, 1).text()
            new_selected[i] = [tbl, attr]
            # Update the reference label in column 3
            ref_item = QTableWidgetItem(f'[{i}]')
            ref_item.setFlags(xor(ref_item.flags(), _item_flag('ItemIsEditable')))
            self.CGF.TWSelected.setItem(i, 2, ref_item)
        self.selected = new_selected
        self.nbr_selected_attr = self.CGF.TWSelected.rowCount()

    def _validate_equation(self: Self, eq_text: str) -> "str|None":
        """Validate the equation text and return an error message or None.

        Checks for:
        - References to non-existent attributes ([N] where N >= len(selected))
        - Empty equation
        - Invalid characters / syntax

        Parameters
        ----------
        eq_text: str

        Returns
        -------
        str or None
            Error message if invalid, None if OK
        """
        if not eq_text.strip():
            return self.tr('The equation is empty.')

        # Find all [N] references in the equation
        refs = re.findall(r'\[(\d+)\]', eq_text)
        if not refs:
            return self.tr('The equation must contain at least one attribute '
                           'reference like [0], [1], etc.')

        max_ref = max(int(r) for r in refs)
        num_attrs = len(self.selected)
        if max_ref >= num_attrs:
            bad_refs = sorted(set(
                f'[{r}]' for r in refs if int(r) >= num_attrs))
            return self.tr(
                'The equation references {refs} but only {n} '
                'attribute(s) are selected ([0] to [{max}]).\n\n'
                'Please remove the invalid references or add more '
                'attributes.').format(
                    refs=', '.join(bad_refs),
                    n=num_attrs,
                    max=num_attrs - 1 if num_attrs > 0 else 0)

        return None

    def update_max_min(self: Self) -> None:
        """Update the text min, max text and set the equation for the guide
        file."""
        field = self.CGF.CBFields.currentText()
        if field == self.tr("--- Select field ---") or field == '-- Select field --':
            self._show_message(
                'No field selected',
                self.tr('Please select a field in Step 1 before calculating.'))
            return
        row_count = self.nbr_selected_attr
        if row_count == 0:
            self._show_message(
                'No attributes selected',
                self.tr('Please select at least one attribute in Step 2 '
                        'before calculating.'))
            return

        eq_text = self.CGF.TEEquation.toPlainText()
        eq_error = self._validate_equation(eq_text)
        if eq_error:
            self._show_message('Invalid equation', eq_error)
            return

        eq_text_min = eq_text
        eq_text_max = eq_text
        for i, (tbl, attribute) in self.selected.items():
            columns = self.db.get_all_columns(tbl.split('.')[1], tbl.split('.')[0])
            if 'polygon' in columns:
                join_geom = 'polygon'
            else:
                join_geom = 'pos'
            s, t = tbl.split('.')
            query = pgsql.SQL(
                "SELECT max({attr}), min({attr})"
                " FROM {schema}.{table} tbl"
                " JOIN fields fi ON st_intersects(tbl.{geom}, fi.polygon)"
                " WHERE field_name = %s"
            ).format(
                attr=pgsql.Identifier(attribute),
                schema=pgsql.Identifier(s),
                table=pgsql.Identifier(t),
                geom=pgsql.Identifier(join_geom))
            try:
                data = self.db.execute_and_return(query, params=(field,))
            except ProgrammingError:
                self._show_message(
                    'Database error',
                    self.tr('Could not query attribute "{attr}" from '
                            '"{tbl}".\n\nMake sure the selected attribute '
                            'contains numeric data.').format(
                                attr=attribute, tbl=tbl),
                    level='error')
                return
            if not data or data[0][0] is None or data[0][1] is None:
                self._show_message(
                    'No data found',
                    self.tr('No data found for attribute "{attr}" in '
                            '"{tbl}" for field "{field}".\n\nThe table may '
                            'be empty or have no data in this field.').format(
                                attr=attribute, tbl=tbl, field=field),
                    level='warning')
                return
            eq_text_min = eq_text_min.replace(f'[{i}]', f'{data[0][1]}')
            eq_text_max = eq_text_max.replace(f'[{i}]', f'{data[0][0]}')

        try:
            max_val = eval(eq_text_max)
            min_val = eval(eq_text_min)
        except (TypeError, SyntaxError, NameError, ZeroDivisionError) as e:
            self._show_message(
                'Equation error',
                self.tr('The equation could not be evaluated.\n\n'
                        'Please check that the equation syntax is valid '
                        'and only uses numbers, operators (+, -, *, /), '
                        'and attribute references like [0], [1].'),
                detail=f'Equation (max): {eq_text_max}\n'
                       f'Equation (min): {eq_text_min}\n'
                       f'Error: {e}')
            return

        self.CGF.LMaxVal.setText(f'Max value: {max_val}')
        self.CGF.LMinVal.setText(f'Min value: {min_val}')
        self.CGF.PBSelectOutput.setEnabled(True)

    def create_file(self: Self) -> None:
        """Creates the guide file with the information from the user."""
        print(self.selected)
        cell_size = self.CGF.LECellSize.text()
        try:
            int(cell_size)
        except ValueError:
            self._show_message(
                'Invalid cell size',
                self.tr('Cell size must be a whole number (e.g. 25).'))
            return
        if f"{int(cell_size)}" != f"{cell_size}":
            self._show_message(
                'Invalid cell size',
                self.tr('Cell size must be a whole number (e.g. 25).'))
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
            fd = ogr.FieldDefn(attr_name[:10], ogr.OFTReal)
        else:
            fd = ogr.FieldDefn(attr_name[:10], ogr.OFTInteger)
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

    def add_prj_file(self: Self, EPSG: str, path: str) -> None:
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(int(EPSG))
        esri_output = srs.ExportToWkt()
        with open(path[:-4] + '.prj', 'a') as prj_file:
            prj_file.write(esri_output)

    def help(self):
        """Shows a help message in a styled QMessageBox"""
        self._show_message(
            'How to create a guide file',
            self.tr(
                '<ol>'
                '<li><b>Step 1</b> — Select a <b>data source</b> (e.g. harvest, plant) '
                'and a <b>field</b>. The table list will filter to show only '
                'data for that field.</li>'
                '<li><b>Step 2</b> — Click an attribute in the left table to '
                'add it to the selected list. Each gets a reference number '
                'like [0], [1].</li>'
                '<li>Write your <b>equation</b> using these references, e.g. '
                '<code>100 + [0] * 2</code>.</li>'
                '<li>Press <b>Calculate min/max</b> to preview the output '
                'range.</li>'
                '<li><b>Step 3</b> — Set the output options:<br/>'
                '&bull; <b>Data type</b>: Integer or Float depending on your '
                'machine<br/>'
                '&bull; <b>Cell size</b>: Grid resolution in meters<br/>'
                '&bull; <b>EPSG</b>: Leave as 4326 unless your machine '
                'requires another CRS<br/>'
                '&bull; <b>Rotation</b>: Rotate the grid if needed</li>'
                '<li>Select an <b>output folder</b> and press '
                '<b>Create Guide File</b>.</li>'
                '</ol>'),
            level='info')
