from typing import Self
from datetime import datetime
from qgis.PyQt.QtWidgets import QComboBox, QTableWidgetItem, QMessageBox
from ..support_scripts.create_layer import CreateLayer, add_background
from ..support_scripts.__init__ import TR


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
        _years = ''
        temp = self.db.execute_and_return("""SELECT column_name 
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = 'fields'
              """)
        for col in temp:
            if col[0][0] == '_':
                _years += ', ' + col[0]
        fields = self.db.execute_and_return("select field_name {y} from fields order by field_name".format(y=_years))
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
        sql = """with first as (select round(st_area(polygon::geography)/100)/100 as field_size, _{y1}, _{y2} 
        from fields), 
        year1 as (select _{y1}, sum(field_size) as y1_size
        from first
        group by _{y1}), 
        year2 as (select _{y2}, sum(field_size) as y2_size
        from first
        group by _{y2})
        select case when _{y1} is null then _{y2} else _{y1} end, y1_size, y2_size
        from year1
        full outer join year2 on year2._{y2}=year1._{y1}
        """.format(y1=(year_now - 1), y2=year_now)
        data = self.db.execute_and_return(sql)
        formated_row = []
        for row in data:
            formated_row.append('{name}: {y2} ({y1})'.format(name=row[0], y1=row[1],
                                                             y2=row[2]))
        self.parent.dock_widget.LWPlanSummary.clear()
        self.parent.dock_widget.LWPlanSummary.addItems(formated_row)
        self.parent.dock_widget.LPlanSummaryLabel.setText('Plan summary {y2} ({y1})'.format(y1=year_now-1, y2=year_now))

    def save_data(self):
        """Saves the plan"""
        table = self.parent.dock_widget.TWPlan
        nbr_rows = table.rowCount()
        if nbr_rows < 1:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('No data is available to save.'))
        nbr_cols = table.columnCount()
        for row in range(nbr_rows):
            sql = """UPDATE "fields" set """
            for col in range(nbr_cols):
                item = table.cellWidget(row, col)
                if item.currentText() != self.tr('Select crop'):
                    col_name = '_' + table.horizontalHeaderItem(col).text()
                    sql += "{c}='{t}', ".format(c=col_name, t=item.currentText())
                else:
                    col_name = '_' + table.horizontalHeaderItem(col).text()
                    sql += "{c}=Null, ".format(c=col_name)
            row_name = table.verticalHeaderItem(row).text()
            sql = sql[:-2] + " where field_name='{c}'".format(c=row_name)
            self.db.execute_sql(sql)

    def view_year(self):
        """Add a background map to the canvas."""
        add_background()
        year = self.parent.dock_widget.DEPlanYear.text()
        sql = "select _{y}, st_astext(polygon) from fields".format(y=year)
        self.db.execute_and_return(sql)
        layer = self.db.add_postgis_layer('fields', 'polygon', 'public', extra_name=str(year))
        self.create_layer.create_layer_style(layer, '_' + year, 'fields', 'public')
