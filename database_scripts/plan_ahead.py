from typing import Self
from datetime import datetime
from psycopg2 import sql as pgsql
from qgis.PyQt.QtWidgets import QComboBox, QTableWidgetItem, QMessageBox
from ..support_scripts.create_layer import CreateLayer, add_background
from ..support_scripts.__init__ import TR
from ..support_scripts.notifier import report_warning


class PlanAhead:
    """A class that fill the tab plan ahead with content"""
    def __init__(self: Self, parent) -> None:
        self.parent = parent
        self.db = parent.db
        translate = TR('PlanAhead')
        self.tr = translate.tr
        self.create_layer = CreateLayer(self.db)

    def set_widget_connections(self: Self) -> None:
        """A simple function that sets the buttons on the plan ahead tab"""
        self.parent.dock_widget.PBUpdatePlaning.clicked.connect(self.update_fields)
        self.parent.dock_widget.PBUpdateSummary.clicked.connect(self.update_sum)
        self.parent.dock_widget.PBSavePlan.clicked.connect(self.save_data)
        self.parent.dock_widget.PBViewPlan.clicked.connect(self.view_year)

    def update_fields(self):
        """A function that updates the crops and field table."""
        year_cols = []
        temp = self.db.execute_and_return("""SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = 'fields'
              """)
        for col in temp:
            if col[0][0] == '_':
                year_cols.append(col[0])
        _years = ''.join(', ' + c for c in year_cols)
        select_cols = pgsql.SQL(", ").join(
            [pgsql.SQL("field_name")] + [pgsql.Identifier(c) for c in year_cols])
        fields = self.db.execute_and_return(
            pgsql.SQL("SELECT {cols} FROM fields ORDER BY field_name").format(cols=select_cols))
        year_now = datetime.now().year
        valid_years = []
        for year in _years.split(', ')[1:]:
            year = year[1:]
            if int(year) > (year_now - 5) and int(year) < (year_now + 3):
                valid_years.append(year)
        crops = {}
        for row in fields:
            field_name = row[0]
            crops[field_name] = {}
            for i, col in enumerate(row):
                if i == 0:
                    continue
                crops[field_name][_years.split(', ')[i]] = col
        self.parent.dock_widget.TWPlan.setRowCount(len(crops))
        self.parent.dock_widget.TWPlan.setColumnCount(7)
        temp = self.db.execute_and_return("select crop_name from crops")
        crop_list = [self.tr('Select crop')]
        for row in temp:
            crop_list.append(row[0])
        for col, year in enumerate(valid_years):
            heading = QTableWidgetItem(year)
            self.parent.dock_widget.TWPlan.setHorizontalHeaderItem(col, heading)
            year = '_' + year
            for row, field in enumerate(crops.keys()):
                if col == 0:
                    heading = QTableWidgetItem(field)
                    self.parent.dock_widget.TWPlan.setVerticalHeaderItem(row, heading)
                cmd_box = QComboBox()
                cmd_box.addItems(crop_list)
                self.parent.dock_widget.TWPlan.setCellWidget(row, col, cmd_box)
                if crops[field][year] is not None:
                    cell = self.parent.dock_widget.TWPlan.cellWidget(row, col)
                    index = cell.findText(crops[field][year])
                    cell.setCurrentIndex(index)

    def update_sum(self):
        """Update the yearly summary for current and last year"""
        year_now = int(datetime.now().year) + 1
        y1_col = pgsql.Identifier(f"_{year_now - 1}")
        y2_col = pgsql.Identifier(f"_{year_now}")
        query = pgsql.SQL(
            "WITH first AS (SELECT round(st_area(polygon::geography)/100)/100 AS field_size, {y1}, {y2}"
            " FROM fields),"
            " year1 AS (SELECT {y1}, sum(field_size) AS y1_size FROM first GROUP BY {y1}),"
            " year2 AS (SELECT {y2}, sum(field_size) AS y2_size FROM first GROUP BY {y2})"
            " SELECT CASE WHEN {y1} IS NULL THEN {y2} ELSE {y1} END, y1_size, y2_size"
            " FROM year1 FULL OUTER JOIN year2 ON year2.{y2} = year1.{y1}"
        ).format(y1=y1_col, y2=y2_col)
        data = self.db.execute_and_return(query)
        formated_row = []
        for row in data:
            formated_row.append(f'{row[0]}: {row[2]} ({row[1]})')
        self.parent.dock_widget.LWPlanSummary.clear()
        self.parent.dock_widget.LWPlanSummary.addItems(formated_row)
        self.parent.dock_widget.LPlanSummaryLabel.setText(f'Plan summary {year_now} ({year_now - 1})')

    def save_data(self):
        """Saves the plan"""
        table = self.parent.dock_widget.TWPlan
        nbr_rows = table.rowCount()
        if nbr_rows < 1:
            report_warning(self.tr('No data is available to save.'))
        nbr_cols = table.columnCount()
        for row in range(nbr_rows):
            set_parts = []
            params = []
            for col in range(nbr_cols):
                item = table.cellWidget(row, col)
                col_name = '_' + table.horizontalHeaderItem(col).text()
                if item.currentText() != self.tr('Select crop'):
                    set_parts.append(
                        pgsql.SQL("{c} = %s").format(c=pgsql.Identifier(col_name)))
                    params.append(item.currentText())
                else:
                    set_parts.append(
                        pgsql.SQL("{c} = NULL").format(c=pgsql.Identifier(col_name)))
            row_name = table.verticalHeaderItem(row).text()
            params.append(row_name)
            query = pgsql.SQL('UPDATE "fields" SET {sets} WHERE field_name = %s').format(
                sets=pgsql.SQL(", ").join(set_parts))
            self.db.execute_sql(query, params=tuple(params))

    def view_year(self):
        """Add a background map to the canvas."""
        add_background()
        year = self.parent.dock_widget.DEPlanYear.text()
        query = pgsql.SQL("SELECT {col}, st_astext(polygon) FROM fields").format(
            col=pgsql.Identifier(f"_{year}"))
        self.db.execute_and_return(query)
        layer = self.db.add_postgis_layer('fields', 'polygon', 'public', extra_name=str(year))
        self.create_layer.create_layer_style(layer, '_' + year, 'fields', 'public')
