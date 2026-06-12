from typing import Self
from operator import xor
import ast
import math
import operator as op
import os
import re
import struct

from osgeo import osr, ogr


_SAFE_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.FloorDiv: op.floordiv, ast.Mod: op.mod,
    ast.Pow: op.pow, ast.USub: op.neg, ast.UAdd: op.pos,
}


def _safe_eval(expr: str) -> float:
    """Evaluate a pure arithmetic expression safely using AST.

    Only numeric literals and +, -, *, /, //, %, **, unary +/- are allowed.
    Raises ValueError on any other construct.
    """
    node = ast.parse(expr, mode='eval').body

    def _ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_ev(n.left), _ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_ev(n.operand))
        raise ValueError(f"Unsupported expression: {ast.dump(n)}")

    return _ev(node)
from psycopg2 import ProgrammingError, sql as pgsql
from qgis.PyQt.QtCore import Qt, QObject, QEvent
from qgis.PyQt.QtWidgets import QTableWidgetItem, QAbstractItemView, QMessageBox, \
    QFileDialog, QComboBox
from qgis.core import QgsProject, QgsVectorLayer

from ..support_scripts.__init__ import TR
from ..support_scripts.create_layer import CreateLayer
from ..widgets.create_guide_file import CreateGuideFileDialog
from ..support_scripts.qt_data import _item_flag

# Qt6 nests event enums under QEvent.Type; Qt5 exposes them directly.
try:
    _MOUSE_PRESS = QEvent.Type.MouseButtonPress
except AttributeError:
    _MOUSE_PRESS = QEvent.MouseButtonPress


class _RefreshOnClick(QObject):
    """Event filter that runs a callback just before a widget is clicked.

    Used so the product combo re-reads the product catalog the moment the user
    opens it. Setting ``combo.showPopup`` on the instance does not work (PyQt
    does not route the C++ virtual to a Python instance attribute), but an
    installed event filter reliably sees the mouse press first.
    """

    def __init__(self: "Self", callback, parent=None) -> None:
        super().__init__(parent)
        self._callback = callback

    def eventFilter(self: "Self", obj, event) -> bool:
        if event.type() == _MOUSE_PRESS:
            try:
                self._callback()
            except Exception:  # nosec B110 - a refresh failure must not break event handling
                pass
        return False
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
        # Independent state for the ISO-XML tab (mirrors the shapefile state
        # above so the two tabs never interfere with each other).
        self.iso_attributes = {}
        self.iso_selected = {}
        self.iso_nbr_selected_attr = 0
        self.iso_save_folder = ''

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

    def setup(self: Self) -> None:
        """Wire the embedded guide-file widget: connect buttons and load the
        initial data. The widget (self.CGF) is embedded as the 'Guide file'
        dock tab by GeoDataFarm, so there is no show()/exec() here."""
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
        self._setup_iso()

    def _setup_iso(self: Self) -> None:
        """Wire the ISO-XML tab. Mirrors :meth:`setup` for the shapefile tab
        but targets the Iso* widgets and the iso_* handlers."""
        self.CGF.IsoPBRemParam.clicked.connect(self.iso_remove_from_param_list)
        self.CGF.IsoPBUpdate.clicked.connect(self.iso_update_max_min)
        self.CGF.IsoPBSelectOutput.clicked.connect(self.iso_set_output_path)
        self.CGF.IsoPBCreateFile.clicked.connect(self.iso_create_file)
        self.CGF.IsoPBHelp.clicked.connect(self.iso_help)
        self.iso_fill_cb()
        self._setup_product_combo()
        self.populate.reload_fields(self.CGF.IsoCBFields)
        self.CGF.IsoTWSelected.setColumnCount(3)
        self.CGF.IsoTWSelected.setColumnWidth(0, 150)
        self.CGF.IsoTWSelected.setColumnWidth(1, 150)
        self.CGF.IsoTWSelected.setColumnWidth(2, 25)

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

    def _validate_equation(self: Self, eq_text: str,
                           selected: "dict|None" = None) -> "str|None":
        """Validate the equation text and return an error message or None.

        Checks for:
        - References to non-existent attributes ([N] where N >= len(selected))
        - Empty equation
        - Invalid characters / syntax

        Parameters
        ----------
        eq_text: str
        selected: dict, optional
            The selected-attributes mapping to validate references against.
            Defaults to the shapefile tab's ``self.selected``.

        Returns
        -------
        str or None
            Error message if invalid, None if OK
        """
        if selected is None:
            selected = self.selected
        if not eq_text.strip():
            return self.tr('The equation is empty.')

        # Only digits, operators, parentheses, whitespace, and [N] refs are allowed.
        if not re.fullmatch(r'[\d+\-*/.() \t\r\n\[\]]+', eq_text):
            return self.tr('The equation contains invalid characters. Only '
                           'numbers, operators (+, -, *, /), parentheses, and '
                           'attribute references like [0], [1] are allowed.')

        # Find all [N] references in the equation
        refs = re.findall(r'\[(\d+)\]', eq_text)
        if not refs:
            return self.tr('The equation must contain at least one attribute '
                           'reference like [0], [1], etc.')

        max_ref = max(int(r) for r in refs)
        num_attrs = len(selected)
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
            max_val = _safe_eval(eq_text_max)
            min_val = _safe_eval(eq_text_min)
        except (TypeError, SyntaxError, NameError, ZeroDivisionError, ValueError) as e:
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

        field_name = self.CGF.CBFields.currentText()
        cell_size_i = int(cell_size)
        rotation_f = float(rotation)
        epsg_i = int(EPSG)

        eq = self.CGF.TEEquation.toPlainText()
        for i, (tbl, attribute) in self.selected.items():
            safe_attr = '"' + attribute.replace('"', '""') + '"'
            eq = eq.replace(
                f"[{i}]",
                f"CASE WHEN avg(tbl_{i}.{safe_attr}) IS NULL THEN 0"
                f" ELSE avg(tbl_{i}.{safe_attr}) END")

        join_parts = []
        for i, (tbl, attribute) in self.selected.items():
            if 'polygon' in self.db.get_all_columns(tbl.split('.')[1], tbl.split('.')[0]):
                join_geom = 'polygon'
            else:
                join_geom = 'pos'
            schema_t, table_t = tbl.split('.')
            alias = pgsql.SQL(f"tbl_{i}")
            join_parts.append(pgsql.SQL(
                " JOIN {schema}.{tbl} {alias}"
                " ON st_intersects(polys, {alias}.{geom})"
            ).format(
                schema=pgsql.Identifier(schema_t),
                tbl=pgsql.Identifier(table_t),
                alias=alias,
                geom=pgsql.Identifier(join_geom)))

        # eq is restricted by _validate_equation to digits, operators, parens,
        # and safely-quoted CASE/avg(tbl_N."col") fragments from selected attrs.
        query = pgsql.SQL(
            "WITH grid AS ("
            " SELECT ROW_NUMBER() OVER () AS grid_id, m.geom"
            " FROM ("
            " SELECT (ST_Dump(MAKEGRID_2D(polygon, {cell}, {cell}))).geom"
            " FROM fields WHERE field_name = %s"
            " ) m),"
            " centroid AS (SELECT ST_Centroid(ST_Collect(grid.geom)) AS geometry FROM grid),"
            " rotated AS (SELECT ST_Rotate(grid.geom, radians({rot}),"
            " (SELECT geometry FROM centroid)) AS polys FROM grid),"
            " final AS (SELECT st_astext(ST_Transform(polys, {epsg})), "
            + eq + " AS val FROM rotated"  # nosec B608
        ).format(
            cell=pgsql.Literal(cell_size_i),
            rot=pgsql.Literal(rotation_f),
            epsg=pgsql.Literal(epsg_i))
        for jp in join_parts:
            query = query + jp
        query = query + pgsql.SQL(
            " GROUP BY polys) SELECT * FROM final WHERE val IS NOT NULL")
        data = self.db.execute_and_return(query, params=(field_name,))
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
        # The wizard is now an embedded dock tab (no popup to close); confirm.
        self._show_message(self.tr('Guide file created'),
                           self.tr('The guide file was created successfully.'),
                           level='info')

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

    # ------------------------------------------------------------------ #
    # ISO-XML tab                                                        #
    # ------------------------------------------------------------------ #
    # The DDI written to the prescription PDV is taken from the selected
    # product's QuantityDDI (PDT attribute E). When the product has none, it
    # is suggested from the Step-1 data source via this map, and finally falls
    # back to DEFAULT_DDI. Labels are only used for the read-only DDI display.
    DATA_SOURCE_DDI = {
        'plant': '000B',    # count per area (e.g. seeds)
        'ferti': '0006',    # mass per area (e.g. fertiliser/lime)
        'spray': '0001',    # volume per area (e.g. liquid)
        'harvest': '0006',  # mass per area (e.g. yield)
        'soil': '0006',     # mass per area
    }
    DDI_LABELS = {
        '0001': 'Volume per area',
        '0006': 'Mass per area',
        '000B': 'Count per area',
        '0010': 'Spacing',
    }
    DEFAULT_DDI = '0006'

    def _pdt_xml_path(self: Self) -> str:
        """Absolute path to the shared product catalog (PDTs.xml), the same
        file the Product tab reads and writes."""
        return os.path.join(os.path.dirname(__file__), 'pyagriculture',
                            'meta_data', 'PDTs.xml')

    def _load_products(self: Self) -> list:
        """Read the products managed in the Product tab.

        Returns a list of dicts ``{'id', 'name', 'ddi'}`` (id = element tag,
        e.g. ``PDT1``). Returns an empty list if the catalog is missing or
        unreadable, so the ISO tab still works without any products defined.
        """
        import xml.etree.ElementTree as ET  # nosec B405 - local, trusted product catalog
        products = []
        try:
            tree = ET.parse(self._pdt_xml_path())  # nosec B314 - local ISO file
            for child in tree.getroot():
                products.append({
                    'id': child.tag,
                    'name': child.attrib.get('B', '') or child.tag,
                    'ddi': (child.attrib.get('E', '') or '').strip(),
                })
        except Exception:  # nosec B110 - missing/corrupt catalog just means no products
            pass
        return products

    def _refresh_products(self: Self) -> None:
        """(Re)populate the product combo from PDTs.xml, preserving the current
        selection where possible. Called every time the combo is opened so any
        change made in the Product tab is reflected immediately."""
        combo = self.CGF.IsoCBProduct
        previous = combo.currentData()
        prev_id = previous['id'] if isinstance(previous, dict) else None
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(self.tr('— No product (DDI from data source) —'), None)
        select_index = 0
        for product in self._load_products():
            label = product['name']
            if product['ddi']:
                label = f"{product['name']} (DDI {product['ddi']})"
            combo.addItem(label, product)
            if prev_id is not None and product['id'] == prev_id:
                select_index = combo.count() - 1
        combo.setCurrentIndex(select_index)
        combo.blockSignals(False)
        self._update_effective_ddi()

    def _effective_ddi(self: Self) -> str:
        """Resolve the DDI to write: the selected product's QuantityDDI, else
        the data-source suggestion, else the default."""
        product = self.CGF.IsoCBProduct.currentData()
        if isinstance(product, dict) and product.get('ddi'):
            return product['ddi']
        source = self.CGF.IsoCBDataSource.currentText()
        return self.DATA_SOURCE_DDI.get(source, self.DEFAULT_DDI)

    def _update_effective_ddi(self: Self) -> None:
        """Update the read-only label showing which DDI will be written."""
        ddi = self._effective_ddi()
        label = self.DDI_LABELS.get(ddi)
        if label:
            text = self.tr('DDI: {ddi} ({label})').format(ddi=ddi, label=label)
        else:
            text = self.tr('DDI: {ddi}').format(ddi=ddi)
        self.CGF.IsoLDDI.setText(text)

    def _setup_product_combo(self: Self) -> None:
        """Wire the product combo: load it once, refresh on every open, and
        keep the effective-DDI label in sync."""
        self._refresh_products()
        combo = self.CGF.IsoCBProduct
        # Refresh the list each time the user opens it, so products added or
        # changed in the Product tab appear without restarting the plugin.
        self._product_filter = _RefreshOnClick(self._refresh_products, combo)
        combo.installEventFilter(self._product_filter)
        combo.currentIndexChanged.connect(
            lambda _idx: self._update_effective_ddi())
        # Also refresh whenever the user switches to the ISO-XML tab.
        try:
            self.CGF.tabFormat.currentChanged.connect(
                lambda _idx: self._refresh_products())
        except AttributeError:
            pass

    def iso_fill_cb(self: Self) -> None:
        """Fill the ISO data-source combo (mirror of :meth:`fill_cb`)."""
        lw_list = [self.tr('-- Select base file --'), 'plant', 'ferti',
                   'spray', 'harvest', 'soil', 'other']
        self.CGF.IsoCBDataSource.clear()
        self.CGF.IsoCBDataSource.addItems(lw_list)
        self.CGF.IsoCBDataSource.activated.connect(
            lambda idx: self._iso_source_changed(
                self.CGF.IsoCBDataSource.currentText()))
        self.CGF.IsoCBFields.activated.connect(
            self._iso_refresh_tables_for_field)

    def _iso_source_changed(self: Self, source: str) -> None:
        """When the data source changes, refresh the attribute table and the
        effective-DDI hint (the data source is the DDI fallback)."""
        self.iso_possible_attr(source)
        self._update_effective_ddi()

    def _iso_refresh_tables_for_field(self: Self) -> None:
        """Refresh the ISO table list when the field selection changes."""
        source = self.CGF.IsoCBDataSource.currentText()
        if source and source != self.tr('-- Select base file --'):
            self.iso_possible_attr(source)

    def iso_possible_attr(self: Self, schema: str) -> None:
        """Populate the ISO available-attributes table (mirror of
        :meth:`possible_attr`, but targeting the Iso* widgets/state)."""
        self.CGF.IsoTWColumnNames.clear()
        field_name = self.CGF.IsoCBFields.currentText()
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

        self.CGF.IsoTWColumnNames.setRowCount(len(names))
        self.CGF.IsoTWColumnNames.setColumnCount(2)
        self.iso_attributes = {}

        exclude = ("'cmax', 'cmin', 'ctid', 'xmax', 'xmin', 'tableoid', "
                   "'pos', 'date_', 'polygon', 'field_row_id'")
        for i, row in enumerate(names):
            s, tbl = row.split('.')
            attributes = self.db.get_numeric_columns(
                table=tbl, schema=s, exclude=exclude)
            if not attributes:
                continue
            item1 = QTableWidgetItem('{row}'.format(row=row))
            item1.setFlags(xor(item1.flags(), _item_flag('ItemIsEditable')))
            self.CGF.IsoTWColumnNames.setItem(i, 0, item1)
            popup_menu = QComboBox()
            popup_menu.addItems(attributes)
            self.iso_attributes[i] = {'tbl': row, 'attributes': attributes}
            self.CGF.IsoTWColumnNames.setCellWidget(i, 1, popup_menu)
            popup_menu.activated.connect(
                lambda index, row=i: self.iso_add_to_param_list(index, row))

    def iso_add_to_param_list(self: Self, index: int, row: int) -> None:
        """Add the chosen column to the ISO selected list (mirror of
        :meth:`add_to_param_list`)."""
        row_count = self.iso_nbr_selected_attr + 1
        self.CGF.IsoTWSelected.setRowCount(row_count)
        item1 = QTableWidgetItem(self.iso_attributes[row]['tbl'])
        item1.setFlags(xor(item1.flags(), _item_flag('ItemIsEditable')))
        item2 = QTableWidgetItem(
            self.iso_attributes[row]['attributes'][index])
        item2.setFlags(xor(item2.flags(), _item_flag('ItemIsEditable')))
        item3 = QTableWidgetItem(f'[{len(self.iso_selected)}]')
        item3.setFlags(xor(item3.flags(), _item_flag('ItemIsEditable')))
        self.CGF.IsoTWSelected.setItem(row_count - 1, 0, item1)
        self.CGF.IsoTWSelected.setItem(row_count - 1, 1, item2)
        self.CGF.IsoTWSelected.setItem(row_count - 1, 2, item3)
        self.iso_nbr_selected_attr = row_count
        self.iso_selected[len(self.iso_selected)] = [
            self.iso_attributes[row]['tbl'],
            self.iso_attributes[row]['attributes'][index]]

    def iso_remove_from_param_list(self: Self) -> None:
        """Remove the selected ISO row(s) and re-sync ``self.iso_selected``
        (mirror of :meth:`remove_from_param_list`)."""
        if self.CGF.IsoTWSelected.selectedItems() is None:
            self._show_message('No selection',
                               self.tr('Please select a row to remove.'),
                               level='warning')
            return
        rows_to_delete = set()
        for item in self.CGF.IsoTWSelected.selectedItems():
            rows_to_delete.add(item.row())
        if not rows_to_delete:
            self._show_message('No selection',
                               self.tr('Please select a row to remove.'),
                               level='warning')
            return
        for i in sorted(rows_to_delete, reverse=True):
            self.CGF.IsoTWSelected.removeRow(i)
        new_selected = {}
        for i in range(self.CGF.IsoTWSelected.rowCount()):
            tbl = self.CGF.IsoTWSelected.item(i, 0).text()
            attr = self.CGF.IsoTWSelected.item(i, 1).text()
            new_selected[i] = [tbl, attr]
            ref_item = QTableWidgetItem(f'[{i}]')
            ref_item.setFlags(xor(ref_item.flags(),
                                  _item_flag('ItemIsEditable')))
            self.CGF.IsoTWSelected.setItem(i, 2, ref_item)
        self.iso_selected = new_selected
        self.iso_nbr_selected_attr = self.CGF.IsoTWSelected.rowCount()

    def iso_set_output_path(self: Self) -> None:
        """Choose the folder the ISO-XML dataset is written to."""
        dialog = QFileDialog()
        if self.parent.test_mode:
            folder_path = "./tests/"
        else:
            folder_path = dialog.getExistingDirectory(None, "Select Folder")
        self.CGF.IsoLOutputPath.setText(str(folder_path))
        self.iso_save_folder = folder_path
        self.CGF.IsoPBCreateFile.setEnabled(True)

    def iso_update_max_min(self: Self) -> None:
        """Preview the output range for the ISO equation (mirror of
        :meth:`update_max_min`, using the Iso* widgets/state)."""
        field = self.CGF.IsoCBFields.currentText()
        if field in (self.tr("--- Select field ---"), '-- Select field --'):
            self._show_message(
                'No field selected',
                self.tr('Please select a field in Step 1 before calculating.'))
            return
        if self.iso_nbr_selected_attr == 0:
            self._show_message(
                'No attributes selected',
                self.tr('Please select at least one attribute in Step 2 '
                        'before calculating.'))
            return

        eq_text = self.CGF.IsoTEEquation.toPlainText()
        eq_error = self._validate_equation(eq_text, self.iso_selected)
        if eq_error:
            self._show_message('Invalid equation', eq_error)
            return

        eq_text_min = eq_text
        eq_text_max = eq_text
        for i, (tbl, attribute) in self.iso_selected.items():
            columns = self.db.get_all_columns(tbl.split('.')[1],
                                              tbl.split('.')[0])
            join_geom = 'polygon' if 'polygon' in columns else 'pos'
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
            max_val = _safe_eval(eq_text_max)
            min_val = _safe_eval(eq_text_min)
        except (TypeError, SyntaxError, NameError, ZeroDivisionError,
                ValueError) as e:
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

        self.CGF.IsoLMaxVal.setText(f'Max value: {max_val}')
        self.CGF.IsoLMinVal.setText(f'Min value: {min_val}')
        self.CGF.IsoPBSelectOutput.setEnabled(True)

    def _iso_grid_dimensions(self: Self, field_name: str,
                             cell_size_m: int) -> "tuple|None":
        """Compute the WGS84 grid origin, cell sizes (in degrees) and the
        column/row counts that cover the field's bounding box.

        Returns ``(minx, miny, dlon, dlat, ncols, nrows)`` or ``None`` if the
        field could not be found.
        """
        query = pgsql.SQL(
            "SELECT ST_XMin(env), ST_YMin(env), ST_XMax(env), ST_YMax(env),"
            " ST_Y(ST_Centroid(polygon))"
            " FROM (SELECT polygon, ST_Envelope(polygon) AS env"
            "       FROM fields WHERE field_name = %s) s")
        data = self.db.execute_and_return(query, params=(field_name,))
        if not data or data[0][0] is None:
            return None
        minx, miny, maxx, maxy, clat = (float(v) for v in data[0])
        # Metres -> degrees. Latitude is ~constant; longitude shrinks with
        # the cosine of the latitude.
        dlat = cell_size_m / 111320.0
        dlon = cell_size_m / (111320.0 * math.cos(math.radians(clat)))
        ncols = max(1, math.ceil((maxx - minx) / dlon))
        nrows = max(1, math.ceil((maxy - miny) / dlat))
        return minx, miny, dlon, dlat, ncols, nrows

    def iso_create_file(self: Self) -> None:
        """Build a dense WGS84 prescription grid and write it as an ISO-XML
        (ISO 11783-10) Grid Type 2 dataset: TASKDATA/TASKDATA.XML + a binary
        grid file."""
        cell_size = self.CGF.IsoLECellSize.text()
        try:
            cell_size_i = int(cell_size)
            if f"{cell_size_i}" != f"{cell_size}" or cell_size_i <= 0:
                raise ValueError
        except ValueError:
            self._show_message(
                'Invalid cell size',
                self.tr('Cell size must be a positive whole number (e.g. 25).'))
            return

        try:
            value_scale = float(self.CGF.IsoLEValueScale.text())
        except ValueError:
            self._show_message(
                'Invalid value scale',
                self.tr('Value scale must be a number (e.g. 1 or 100).'))
            return

        field_name = self.CGF.IsoCBFields.currentText()
        if field_name in (self.tr("--- Select field ---"),
                          '-- Select field --'):
            self._show_message('No field selected',
                               self.tr('Please select a field in Step 1.'))
            return
        if self.iso_nbr_selected_attr == 0:
            self._show_message(
                'No attributes selected',
                self.tr('Please select at least one attribute in Step 2.'))
            return

        eq_text = self.CGF.IsoTEEquation.toPlainText()
        eq_error = self._validate_equation(eq_text, self.iso_selected)
        if eq_error:
            self._show_message('Invalid equation', eq_error)
            return

        dims = self._iso_grid_dimensions(field_name, cell_size_i)
        if dims is None:
            self._show_message(
                'No field found',
                self.tr('Could not read the geometry of field "{field}".')
                .format(field=field_name))
            return
        minx, miny, dlon, dlat, ncols, nrows = dims

        # Build the equation expression and the per-attribute joins, exactly
        # like the shapefile path but joining against the regular grid cells.
        eq = eq_text
        for i, (tbl, attribute) in self.iso_selected.items():
            safe_attr = '"' + attribute.replace('"', '""') + '"'
            eq = eq.replace(
                f"[{i}]",
                f"CASE WHEN avg(tbl_{i}.{safe_attr}) IS NULL THEN 0"
                f" ELSE avg(tbl_{i}.{safe_attr}) END")

        join_parts = []
        for i, (tbl, attribute) in self.iso_selected.items():
            cols = self.db.get_all_columns(tbl.split('.')[1],
                                           tbl.split('.')[0])
            join_geom = 'polygon' if 'polygon' in cols else 'pos'
            schema_t, table_t = tbl.split('.')
            alias = pgsql.SQL(f"tbl_{i}")
            join_parts.append(pgsql.SQL(
                " JOIN {schema}.{tbl} {alias}"
                " ON st_intersects(ig.cell, {alias}.{geom})"
            ).format(
                schema=pgsql.Identifier(schema_t),
                tbl=pgsql.Identifier(table_t),
                alias=alias,
                geom=pgsql.Identifier(join_geom)))

        # eq is restricted by _validate_equation to digits, operators, parens
        # and the safely-quoted avg(tbl_N."col") fragments built just above.
        query = pgsql.SQL(
            "WITH cells AS ("
            " SELECT gi, gj, ST_SetSRID(ST_MakeEnvelope("
            " {minx}+gi*{dlon}, {miny}+gj*{dlat},"
            " {minx}+(gi+1)*{dlon}, {miny}+(gj+1)*{dlat}), 4326) AS cell"
            " FROM generate_series(0, {ncols}-1) AS gi,"
            " generate_series(0, {nrows}-1) AS gj),"
            " ingrid AS ("
            " SELECT c.gi, c.gj, c.cell FROM cells c"
            " JOIN fields fi ON fi.field_name = %s"
            " AND ST_Intersects(c.cell, fi.polygon))"
            " SELECT ig.gi, ig.gj, " + eq + " AS val FROM ingrid ig"  # nosec B608
        ).format(
            minx=pgsql.Literal(minx),
            miny=pgsql.Literal(miny),
            dlon=pgsql.Literal(dlon),
            dlat=pgsql.Literal(dlat),
            ncols=pgsql.Literal(ncols),
            nrows=pgsql.Literal(nrows))
        for jp in join_parts:
            query = query + jp
        query = query + pgsql.SQL(
            " GROUP BY ig.gi, ig.gj")
        data = self.db.execute_and_return(query, params=(field_name,))
        if isinstance(data, str):
            self._show_message(
                'Database error',
                self.tr('The grid could not be calculated. Please check the '
                        'equation and the selected attributes.'),
                detail=str(data))
            return

        # Fill a dense ncols*nrows matrix; cells outside the field (or with no
        # source data) stay at 0 ("no application").
        grid = [[0 for _ in range(ncols)] for _ in range(nrows)]
        n_filled = 0
        for gi, gj, val in data:
            if val is None:
                continue
            gi, gj = int(gi), int(gj)
            if 0 <= gj < nrows and 0 <= gi < ncols:
                grid[gj][gi] = int(round(float(val) * value_scale))
                n_filled += 1
        if n_filled == 0:
            self._show_message(
                'No data',
                self.tr('No grid cells with data were produced for field '
                        '"{field}". Nothing was written.').format(
                            field=field_name),
                level='warning')
            return

        ddi = self._effective_ddi()
        product = self.CGF.IsoCBProduct.currentData()
        task_name = self.CGF.IsoLETaskName.text() or 'Guide task'
        try:
            self._write_isoxml(self.iso_save_folder, grid, minx, miny,
                               dlon, dlat, ncols, nrows, ddi, task_name,
                               product=product if isinstance(product, dict)
                               else None)
        except OSError as e:
            self._show_message(
                'Could not write files',
                self.tr('The ISO-XML dataset could not be written.'),
                detail=str(e))
            return

        self._show_message(
            self.tr('ISO-XML file created'),
            self.tr('The ISO-XML guide file was created successfully in the '
                    '"TASKDATA" sub-folder.'),
            level='info')

    @staticmethod
    def _xml_attr(value: str) -> str:
        """Escape a string for safe use inside an XML attribute."""
        return (str(value).replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))

    def _write_isoxml(self: Self, out_folder: str, grid: list,
                      minx: float, miny: float, dlon: float, dlat: float,
                      ncols: int, nrows: int, ddi: str,
                      task_name: str, product: "dict|None" = None) -> None:
        """Write the TASKDATA folder (TASKDATA.XML + binary grid) for a single
        Grid Type 2 prescription with one process-data variable.

        The binary grid stores one little-endian signed int32 per cell, in
        row order from the south-west corner: rows south->north, and within a
        row west->east, matching the GridMinimum origin declared in the XML.

        If ``product`` (a dict with ``id``/``name`` from the Product tab) is
        given, its PDT definition is embedded and the PDV references it via the
        ProductIdRef attribute, so the prescription is tied to that product.
        """
        task_dir = os.path.join(out_folder, 'TASKDATA')
        os.makedirs(task_dir, exist_ok=True)
        grid_name = 'GRD00000'

        # Binary grid: row 0 = southernmost (GridMinimumNorthPosition).
        bin_path = os.path.join(task_dir, grid_name + '.BIN')
        with open(bin_path, 'wb') as bin_file:
            for gj in range(nrows):
                for gi in range(ncols):
                    bin_file.write(struct.pack('<i', int(grid[gj][gi])))
        file_length = os.path.getsize(bin_path)

        safe_task = self._xml_attr(task_name)
        # A product definition (PDT) must precede the task it is referenced
        # from. The PDV then points at it through ProductIdRef (attribute C).
        pdt_line = ''
        pdv_product_ref = ''
        if product and product.get('id'):
            pid = self._xml_attr(product['id'])
            pname = self._xml_attr(product.get('name', '') or product['id'])
            pdt_line = f'  <PDT A="{pid}" B="{pname}"/>\n'
            pdv_product_ref = f' C="{pid}"'

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<ISO11783_TaskData VersionMajor="4" VersionMinor="0"'
            ' ManagementSoftwareManufacturer="GeoDataFarm"'
            ' ManagementSoftwareVersion="1.0" DataTransferOrigin="1">\n'
            + pdt_line +
            f'  <TSK A="TSK1" B="{safe_task}" G="1">\n'
            '    <TZN A="1">\n'
            f'      <PDV A="{ddi}" B="0"{pdv_product_ref}/>\n'
            '    </TZN>\n'
            f'    <GRD A="{miny:.9f}" B="{minx:.9f}" C="{dlat:.9f}"'
            f' D="{dlon:.9f}" E="{ncols}" F="{nrows}" G="{grid_name}"'
            f' H="{file_length}" I="2" J="1"/>\n'
            '  </TSK>\n'
            '</ISO11783_TaskData>\n')
        xml_path = os.path.join(task_dir, 'TASKDATA.XML')
        with open(xml_path, 'w', encoding='utf-8') as xml_file:
            xml_file.write(xml)

    def iso_help(self: Self) -> None:
        """Show help for the ISO-XML tab."""
        self._show_message(
            'How to create an ISO-XML guide file',
            self.tr(
                '<ol>'
                '<li><b>Step 1</b> — Select a <b>data source</b> and a '
                '<b>field</b>.</li>'
                '<li><b>Step 2</b> — Click attributes to add them and write '
                'your <b>equation</b> (e.g. <code>100 + [0] * 2</code>), then '
                'press <b>Calculate min/max</b> to preview the range.</li>'
                '<li><b>Step 3</b> — Set the <b>cell size</b> (m), pick the '
                '<b>product</b> being applied (managed in the <b>Product</b> '
                'tab), and a <b>value scale</b> to match your terminal\'s '
                'resolution. The <b>DDI</b> shown is taken from the product; '
                'if it has none, it is suggested from the data source.</li>'
                '<li>Select an <b>output folder</b> and press '
                '<b>Create ISO-XML</b>. A <code>TASKDATA</code> folder with '
                '<code>TASKDATA.XML</code> and a binary grid is written; the '
                'chosen product is embedded and referenced by the '
                'prescription.</li>'
                '</ol>'
                '<p><b>Note:</b> ISO-XML grids are axis-aligned and in WGS84, '
                'so rotation and custom CRS are not available here.</p>'),
            level='info')
