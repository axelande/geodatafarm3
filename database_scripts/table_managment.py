from PyQt5 import QtCore
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QListWidgetItem, QPushButton
# Import the code for the dialog
from ..widgets.table_managment_dialog import TableMgmtDialog
__author__ = 'Axel Andersson'


class TableManagement:
    def __init__(self, parent):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        self.add_to_Param_row_count = 0
        self.DB = parent.DB
        self.dock_widget = parent.dock_widget
        self.tr = parent.tr
        # Create the dialog (after translation) and keep reference
        self.TMD = TableMgmtDialog()
        self.tables_in_db = 0
        self.params_in_list = 0
        self.current_table = None
        self.current_schema = None

    def run(self):
        self.TMD.pButRemove.clicked.connect(self.remove_table_from_DB)
        self.TMD.pButCombine.clicked.connect(self.merge_tbls)
        self.TMD.pButChangeTbl.clicked.connect(self.edit_tbl_name)
        self.TMD.pButChangeParam.clicked.connect(self.edit_param_name)
        self.TMD.pButAdd_Param.clicked.connect(self.retrieve_params)
        self.TMD.pButSave.clicked.connect(self.save_table)
        self.update_table_list()
        self.TMD.show()
        self.TMD.exec_()

    def merge_tbls(self):
        tables_to_merge = []
        new_name = self.TMD.LEName.text()
        new_schema = self.TMD.CBDataType.currentText()
        if new_name == '':
            QMessageBox.information(None, self.tr("Error:"), self.tr('You need to fill in a new name'))
            return
        if new_schema == '-Select data type -':
            QMessageBox.information(None, self.tr("Error:"), self.tr('You have to decide what type of data it is'))
            return
        if new_name in self.DB.get_tables_in_db():
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
        self.DB.execute_sql(sql)
        self.DB.update_row_id(new_schema, new_name)
        self.DB.create_indexes(new_name, [], new_schema)
        self.TMD.LEName.setText('')
        self.TMD.CBDataType.setCurrentIndex(0)
        self.update_table_list()

    def retrieve_params(self):
        c = 0
        for item in self.items_in_table:
            if item.checkState() == 2:
                c += 1
                table = item.text()
        if c != 1:
            QMessageBox.information(None, self.tr("Error:"), self.tr('You can only have one dataset selected'))
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
        indexes = self.DB.get_indexes(table, schema)
        for nbr in indexes.keys():
            checked_params.append(indexes[nbr]['index_col'])
        columns = self.DB.get_all_columns(table, schema)
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
        checked_params = []
        table = self.current_table
        schema = self.current_schema
        indexes = self.DB.get_indexes(table, schema)
        create_index_for = []
        for nbr in indexes.keys():
            checked_params.append(indexes[nbr]['index_col'])
        for item in self.params_in_table:
            if item.text() in checked_params:
                if item.checkState() == 1:
                    checked_params.remove(item.text())
                continue
            if item.checkState() == 2:
                create_index_for.append(item.text())
        for index in create_index_for:
            self.DB.execute_sql("""create index {index}_{tbl} on {schema}.{tbl} using btree({index})""".format(index=index, tbl=table, schema=schema))
        for del_index in checked_params:
            self.DB.execute_sql("DROP INDEX IF EXISTS {schema}.{old_index}_{tbl}".format(old_index=del_index, tbl=table, schema=schema))
        try:
            self.DB.execute_sql("""DROP INDEX IF EXISTS {schema}.gist_{tbl};
create index gist_{tbl} on {schema}.{tbl} using gist(polygon) """.format(tbl=table, schema=schema))
        except:
            pass
        try:
            self.DB.execute_sql("""DROP INDEX IF EXISTS {schema}.gist_{tbl};
create index gist_{tbl} on {schema}.{tbl} using gist(pos) """.format(tbl=table, schema=schema))
        except:
            pass
        model = self.TMD.SAParams.model()
        for item in self.params_in_table:
            qIndex = self.TMD.SAParams.indexFromItem(item)
            model.removeRow(qIndex.row())
        self.params_in_list = 0

    def edit_tbl_name(self):
        for item in self.items_in_table:
            if item.checkState() == 2:
                schema, tbl = item.text().split('.')
                text, y_n = QInputDialog.getText(None, 'Dataset name', 'What do you want to '
                                                       'rename ' + tbl + ' to?')
                if y_n:
                    sql = "ALTER TABLE {schema}.{old} RENAME TO {new}".format(schema=schema, old=tbl, new=text)
                    self.DB.execute_sql(sql)
                    #sql = "ALTER TABLE public." + tbl_name + " RENAME " + item.text() + " TO " + text
        self.update_table_list()

    def edit_param_name(self):
        for item in self.params_in_table:
            if item.checkState() == 2:
                text, y_n = QInputDialog.getText(None, 'Dataset name', 'What do you want to '
                                                       'rename ' + item.text() + ' to?')
                if y_n:
                    sql = "ALTER TABLE {tbl} RENAME {new_name} TO {text}".format(tbl=self.current_table, new_name=item.text(), text=text)
                    self.DB.execute_sql(sql)

        self.retrieve_params()

    def update_table_list(self):
        """Update the list of tables in the docket widget"""
        lw_list = [[self.dock_widget.LWActivityTable, 'activity'],
                   [self.dock_widget.LWHarvestTable, 'harvest'],
                   [self.dock_widget.LWSoilTable, 'soil']]
        if self.tables_in_db != 0:
            model = self.TMD.SATables.model()
            for item in self.items_in_table:
                qIndex = self.TMD.SATables.indexFromItem(item)
                model.removeRow(qIndex.row())
        self.tables_in_db = 0
        for lw, schema in lw_list:
            table_names = self.DB.get_tables_in_db(schema)
            for name in table_names:
                if name[0] in ["spatial_ref_sys", "pointcloud_formats", "temp_polygon"]:
                    continue
                item_name = schema + '.' + str(name[0])
                testcase_name = QtCore.QCoreApplication.translate("qadashboard", item_name, None)
                item = QListWidgetItem(testcase_name, self.TMD.SATables)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Unchecked)
                self.tables_in_db += 1
        self.items_in_table = self.TMD.SATables.findItems('', QtCore.Qt.MatchContains)


    def remove_table_from_DB(self):
        """Removes the selected tables from the database"""
        msgBox = QMessageBox()
        msgBox.setText(self.tr('Do you really want to remove the selected tables from the database?'))
        msgBox.addButton(QPushButton(self.tr('Yes')), QMessageBox.YesRole)
        msgBox.addButton(QPushButton(self.tr('No')), QMessageBox.NoRole)
        ret = msgBox.exec_()
        if ret == 1:
            return
        model = self.TMD.SATables.model()
        for item in self.items_in_table:
            if item.checkState() == 2:
                self.DB.remove_table(item.text())
                qIndex = self.TMD.SATables.indexFromItem(item)
                model.removeRow(qIndex.row())
                self.tables_in_db -= 1
        self.items_in_table = self.TMD.SATables.findItems('', QtCore.Qt.MatchContains)
