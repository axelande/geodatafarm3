from PyQt5 import QtCore
from qgis.core import QgsTask
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QListWidgetItem, QPushButton
# Import the code for the dialog
from ..widgets.table_managment_dialog import TableMgmtDialog
from ..support_scripts.__init__ import TR
__author__ = 'Axel Horteborn'


class TableManagement:
    def __init__(self, parent):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        self.add_to_Param_row_count = 0
        self.db = parent.db
        self.dock_widget = parent.dock_widget
        self.parent = parent
        translate = TR('TableManagement')
        self.tr = translate.tr
        # Create the dialog (after translation) and keep reference
        self.TMD = TableMgmtDialog()
        self.tables_in_db = 0
        self.params_in_list = 0
        self.current_table = None
        self.current_schema = None
        self.params_in_table = None
        self.items_in_table = []

    def run(self):
        """Connects the push buttons and enable the visibility of the dialog."""
        self.TMD.pButRemove.clicked.connect(self.remove_table_from_db)
        self.TMD.pButCombine.clicked.connect(self.merge_tbls)
        self.TMD.pButChangeTbl.clicked.connect(self.edit_tbl_name)
        self.TMD.pButChangeParam.clicked.connect(self.edit_param_name)
        self.TMD.pButAdd_Param.clicked.connect(self.retrieve_params)
        self.TMD.pButSave.clicked.connect(self.save_table)
        self.TMD.pButGetYieldCol.clicked.connect(self.update_column_list)
        self.TMD.pButSplitRows.clicked.connect(self.split_rows)
        self.TMD.PBMakeRows.clicked.connect(self.make_rows)
        self.update_table_list()
        self.TMD.show()
        if not self.parent.test_mode:
            self.TMD.exec_()

    def merge_tbls(self):
        """Merging two data sets into one."""
        tables_to_merge = []
        new_name = self.TMD.LEName.text()
        new_type = self.TMD.CBDataType.currentText()
        if new_type == self.tr('plant'):
            new_schema = 'plant'
        if new_type == self.tr('fertilize'):
            new_schema = 'ferti'
        if new_type == self.tr('spray'):
            new_schema = 'spray'
        if new_type == self.tr('other'):
            new_schema = 'other'
        if new_type == self.tr('harvest'):
            new_schema = 'harvest'
        if new_type == self.tr('soil'):
            new_schema = 'soil'
        if new_name == '':
            QMessageBox.information(None, self.tr("Error:"), self.tr('You need to fill in a new name'))
            return
        if new_schema == self.tr('-Select data type -'):
            QMessageBox.information(None, self.tr("Error:"), self.tr('You have to decide what type of data it is'))
            return
        if new_name in self.db.get_tables_in_db(new_schema):
            QMessageBox.information(None, self.tr("Error:"), self.tr('You need a new name'))
            return
        c = 0
        for item in self.items_in_table:
            if item.checkState() == 2:
                c += 1
                tables_to_merge.append(item.text())
        if c < 2:
            QMessageBox.information(None, self.tr("Error:"), self.tr('You need at least 2 dataset when merging'))
            return
        sql = "Create table {schema}.{new} AS (".format(new=new_name, schema=new_schema)
        for table in tables_to_merge:
            sql += "select * from {tbl} UNION ".format(tbl=table)
        sql = sql[:-7]
        sql += ")"
        self.db.execute_sql(sql)
        self.db.update_row_id(new_schema, new_name)
        self.db.create_indexes(new_name, [], new_schema)
        self.TMD.LEName.setText('')
        self.TMD.CBDataType.setCurrentIndex(0)
        self.update_table_list()

    def check_multiple(self):
        """Checks if multiple table is selected

        Returns
        -------
        Bool, False if more than one row is selected
        str, schema.table_name"""
        c = 0
        for item in self.items_in_table:
            if item.checkState() == 2:
                c += 1
                table = item.text()
        if c != 1:
            QMessageBox.information(None, self.tr("Error:"),
                                    self.tr('You can only have one dataset selected'))
            return False, 'failed'
        return True, table

    def retrieve_params(self):
        """This function is trigged by "edit" table, and basically fills the left list widget,
        all attributes that have a index get selected by default."""
        suc, table = self.check_multiple()
        if suc is False:
            return
        self.current_schema, self.current_table = table.split('.')
        if self.params_in_list != 0:
            model = self.TMD.SAParams.model()
            for item in self.params_in_table:
                qIndex = self.TMD.SAParams.indexFromItem(item)
                model.removeRow(qIndex.row())
        self.params_in_list = 0
        checked_params = []
        table = self.current_table
        schema = self.current_schema
        indexes = self.db.get_indexes(table, schema)
        for nbr in indexes.keys():
            checked_params.append(indexes[nbr]['index_col'])
        columns = self.db.get_all_columns(table, schema)
        for param_name in columns:
            if param_name[0] in ['cmin', 'xmin', 'xmax', 'cmax', 'ctid', 'pos',
                                 'polygon', 'tableoid', '_', 'field_row_id']:
                continue
            if param_name[0][:3] == '...':
                continue
            item_name = str(param_name[0])
            testcase_name = QtCore.QCoreApplication.translate("qadashboard", item_name, None)
            item = QListWidgetItem(testcase_name, self.TMD.SAParams)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            if param_name[0] in checked_params:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            self.params_in_list += 1
        self.params_in_table = self.TMD.SAParams.findItems('', QtCore.Qt.MatchContains)

    def save_table(self):
        """Updates the attribute indexes that are checked in the list widget"""
        checked_params = []
        table = self.current_table
        schema = self.current_schema
        indexes = self.db.get_indexes(table, schema)
        create_index_for = []
        remove_index_for = []
        for nbr in indexes.keys():
            checked_params.append(indexes[nbr]['index_col'])
        for item in self.params_in_table:
            if item.text() in checked_params:
                if item.checkState() == 0:
                    remove_index_for.append(item.text())
            else:
                if item.checkState() == 2:
                    create_index_for.append(item.text())
        for index in create_index_for:
            self.db.execute_sql("""create index {index}_{schema}_{tbl} on {schema}.{tbl} using btree({index})""".format(index=index, tbl=table, schema=schema))
        for index in remove_index_for:
            self.db.execute_sql("DROP INDEX IF EXISTS {schema}.{index}_{schema}_{tbl}".format(index=index, tbl=table, schema=schema))
        if schema != 'harvest':
            self.db.execute_sql("""DROP INDEX IF EXISTS {schema}.gist_{tbl};
create index gist_{tbl} on {schema}.{tbl} using gist(polygon) """.format(tbl=table, schema=schema))
        try:
            if schema != 'weather':
                self.db.execute_sql("""DROP INDEX IF EXISTS {schema}.gist_{tbl};
create index gist_{tbl} on {schema}.{tbl} using gist(pos) """.format(tbl=table, schema=schema))
        except:
            pass
        model = self.TMD.SAParams.model()
        for item in self.params_in_table:
            qIndex = self.TMD.SAParams.indexFromItem(item)
            model.removeRow(qIndex.row())
        self.params_in_list = 0

    def edit_tbl_name(self):
        """This function pops a question if the user wants to rename the selected tables to.
        Then it is replaced and the manual table is also updated."""
        for item in self.items_in_table:
            if item.checkState() == 2:
                schema, tbl = item.text().split('.')
                text, y_n = QInputDialog.getText(None, self.tr('Data set name'),
                                                 self.tr('What do you want to rename ') + tbl + self.tr(' to?'))
                if y_n:
                    sql = "ALTER TABLE {schema}.{old} RENAME TO {new}".format(schema=schema, old=tbl, new=text)
                    self.db.execute_sql(sql)
                    sql = "Update {schema}.manual SET table_ = '{new}' where table_ = '{old}'".format(schema=schema, old=tbl, new=text)
                    self.db.execute_sql(sql)
        self.update_table_list()

    def edit_param_name(self):
        """Edit the name of all selected parameters."""
        for item in self.params_in_table:
            if item.checkState() == 2:
                text, y_n = QInputDialog.getText(None, self.tr('Parameter name'),
                                                 self.tr('What do you want to rename ') + item.text() +
                                                 self.tr(' to?'))
                if y_n:
                    sql = """ALTER TABLE {schema}.{tbl} RENAME {new_name} TO {text}
                    """.format(schema=self.current_schema, tbl=self.current_table, new_name=item.text(), text=text)
                    self.db.execute_sql(sql)
                    try:
                        sql = """ALTER INDEX {schema}.{old}_{schema}_{tbl}
                              RENAME TO {new}_{schema}_{tbl}
                              """.format(schema=self.current_schema, tbl=self.current_table,
                                         old=item.text(), new=text)
                        self.db.execute_sql(sql)
                    except:
                        pass
        self.retrieve_params()

    def update_table_list(self):
        """Update the list of tables in the docket widget"""
        lw_list = self.parent.populate.get_lw_list()
        if self.tables_in_db != 0:
            model = self.TMD.SATables.model()
            for item in self.items_in_table:
                qIndex = self.TMD.SATables.indexFromItem(item)
                model.removeRow(qIndex.row())
        self.tables_in_db = 0
        for lw, schema in lw_list:
            table_names = self.db.get_tables_in_db(schema)
            for name in table_names:
                if str(name) in ['harrowing_manual', 'plowing_manual', 'manual']:
                    continue
                item_name = schema + '.' + str(name)
                testcase_name = QtCore.QCoreApplication.translate("qadashboard", item_name, None)
                item = QListWidgetItem(testcase_name, self.TMD.SATables)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Unchecked)
                self.tables_in_db += 1
        self.items_in_table = self.TMD.SATables.findItems('', QtCore.Qt.MatchContains)

    def remove_table_from_db(self):
        """Removes the selected tables from the database"""
        msgBox = QMessageBox()
        msgBox.setText(self.tr('Do you really want to remove the selected tables from the database?'))
        msgBox.addButton(QPushButton(self.tr('Yes')), QMessageBox.YesRole)
        msgBox.addButton(QPushButton(self.tr('No')), QMessageBox.NoRole)
        if self.parent.test_mode:
            ret = 0
        else:
            ret = msgBox.exec_()
        if ret == 1:
            return
        model = self.TMD.SATables.model()
        for item in self.items_in_table:
            if item.checkState() == 2:
                self.db.remove_table(item.text())
                qIndex = self.TMD.SATables.indexFromItem(item)
                model.removeRow(qIndex.row())
                self.tables_in_db -= 1
        self.items_in_table = self.TMD.SATables.findItems('', QtCore.Qt.MatchContains)

    def make_rows(self):
        suc, s_table = self.check_multiple()
        if not suc:
            return
        schema, tbl = s_table.split('.')
        if schema == 'harvest':
            QMessageBox(None, self.tr('Error'),
                        self.tr('This option is not possible for harvest tables'))
            return
        sql = f"select field_row_id, row, course from {schema}.{tbl} order by row, field_row_id"
        row_courses = self.db.execute_and_return(sql, return_failure=False)
        nr_rows = int(self.TMD.SBNumberOfRows.value())
        max_dev = int(self.TMD.SBMaxAngleOffset.value())
        avg_dist = float(self.TMD.SBAvgDistance.value())
        distance_bet_rows = float(self.TMD.SBRowDistance_2.value()) / 2
        stops = {}
        for i in range(1, nr_rows + 1):
            stops[i] = []

        current_course = 0
        for id_, row, course in row_courses:
            if len(stops[row]) == 0:
                stops[row].append(id_)
                current_course = course
                continue
            if round(course/max_dev) != round(current_course/max_dev):
                stops[row].append(id_)
                current_course = course
        for row in stops.keys():
            stops[row].append(len(row_courses)+1)
        task1 = QgsTask.fromFunction('Updating rows', make_rows, self.db, schema, tbl, avg_dist, distance_bet_rows, stops)
        self.parent.tsk_mngr.addTask(task1)
        

    def split_rows(self):
        """Spilt the harvest data to multiple rows."""
        suc, s_table = self.check_multiple()
        if not suc:
            return
        split_yield = self.TMD.CBSplitYield.isChecked()
        if split_yield:
            yield_row = self.TMD.CBColumns.currentText()
            if yield_row == self.tr('--- Select yield column ---'):
                QMessageBox(None, self.tr('Error'),
                            self.tr('In order to split the yield you need to specify the yield column'))
                return

        schema, tbl = s_table.split('.')
        if schema != 'harvest':
            QMessageBox(None, self.tr('Error'),
                        self.tr('This option is only possible for harvest tables'))
            return
        nbr_rows = int(self.TMD.CBNbrRows.currentText())
        spacing = float(self.TMD.SBRowDistance.text().replace(',', '.'))
        if nbr_rows == 2:
            move_d = [spacing / 2, spacing]
        elif nbr_rows == 4:
            move_d = [spacing + spacing / 2, spacing, spacing * 2, spacing * 3]
        else:  # nbr_rows == 6
            move_d = [2 * spacing + spacing / 2, spacing, spacing * 2,
                      spacing * 3, spacing * 4, spacing * 5]
        sql = "select min(field_row_id) from harvest.{tbl}".format(tbl=tbl)
        min_row_id = self.db.execute_and_return(sql)[0][0]
        sql = "select max(field_row_id) from harvest.{tbl}".format(tbl=tbl)
        max_row_id = self.db.execute_and_return(sql)[0][0]
        org_min = min_row_id
        org_max = max_row_id
        if min_row_id is None:
            # If the user choose the wrong field and this part cant be used.
            return [False, 'Wrong field']
        for row_nbr in range(nbr_rows):
            if row_nbr == 0:
                bearing = 270
            else:
                min_row_id, max_row_id = self.duplicate_first_row(org_min, org_max, tbl)
                bearing = 90
            distance = move_d[row_nbr]
            for i in range(min_row_id, max_row_id, 2000):
                sql = """
                        WITH first_selected as
                            (SELECT field_row_id, pos, st_azimuth(pos,
                                (SELECT pos
                                FROM {tbl} new
                                WHERE org.field_row_id+1=new.field_row_id)
                                ) as bearing
                            FROM {tbl} org
                        where org.field_row_id >= {i1} - 3
                        and org.field_row_id < {i3} + 3
                        ),
                        sub_section as(SELECT field_row_id, st_project(pos::geography, 
                                                                       {dist}, 
                                                                       (select atan2(avg(sin(bearing)), avg(cos(bearing))) 
                                                                        from first_selected fs 
                                                                        where fs.field_row_id > (ss.field_row_id -3) 
                                                                        and fs.field_row_id < (ss.field_row_id +3)
                                                                        ) + radians({p_bearing})
                                                                      )::geometry as new_pos
                        FROM first_selected ss
                        )
                        update {tbl}
                        set pos=new_pos
                        from sub_section
                        where {tbl}.field_row_id = sub_section.field_row_id
                        and {tbl}.field_row_id >= {i1}
                        and {tbl}.field_row_id < {i3}""".format(tbl='harvest.' + tbl, i1=i,
                                                                i2=i + 1,
                                                                i3=i + 2000, dist=distance,
                                                                p_bearing=bearing)
                # print(sql)
                self.db.execute_sql(sql)
            if split_yield:
                sql = f"""UPDATE {schema}.{tbl}
	            SET {yield_row} = {yield_row} / {nbr_rows}"""
                self.db.execute_sql(sql)

    def update_column_list(self):
        suc, s_table = self.check_multiple()
        if not suc:
            return
        schema, tbl = s_table.split('.')
        columns = self.db.get_all_columns(tbl, schema, "'field_row_id'")
        lw = self.TMD.CBColumns
        lw.clear()
        lw.addItem(self.tr('--- Select yield column ---'))
        for name in columns:
            lw.addItem(str(name[0]))

    def duplicate_first_row(self, org_min, org_max, table, schema='harvest'):
        """Duplicates the original data table and returns the first and last row_id"""
        sql_max_row = "select max(field_row_id) from {s}.{t}".format(s=schema, t=table)
        current_max = self.db.execute_and_return(sql_max_row)[0][0]
        columns_ = self.db.get_all_columns(table, schema)
        columns = []
        for row in columns_:
            columns.append(row[0])
        c1 = ','.join(columns)
        c2 = ','.join(columns)
        c2 = c2.replace('field_row_id', 'ROW_NUMBER() OVER () + {n}'.format(n=current_max+1))
        sql = """INSERT into {s}.{t}({c1})
        SELECT {c2}
        FROM {s}.{t}
        where field_row_id >= {min_r} AND field_row_id <= {max_r}
        """.format(s=schema, t=table, min_r=org_min, max_r=org_max, c1=c1, c2=c2)
        self.db.execute_sql(sql)
        now_max = self.db.execute_and_return(sql_max_row)[0][0]
        return current_max + 1, now_max


def make_rows(db, schema, tbl, avg_dist, distance_bet_rows, stops):
        for j, (row, stops_) in enumerate(stops.items()):
            for i, stop in enumerate(stops_[:-1]):
                sql = f"""with sel as(select st_buffer(st_makeline(pos order by field_row_id)::geography, {distance_bet_rows}) as outer_row
        from {schema}.{tbl} 
        where row={row} and field_row_id < {stops[row][i+1]} and field_row_id >={stop}
        )
        Update {schema}.{tbl}
        set polygon=st_multi(st_intersection(st_buffer(pos::geography, {avg_dist}), outer_row)::geometry)
        from sel
        where row={row} and field_row_id < {stops[row][i+1]} and field_row_id >={stop}
        """
                db.execute_sql(sql)
