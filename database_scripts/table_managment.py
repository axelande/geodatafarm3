from PyQt5 import QtCore
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QListWidgetItem, QPushButton
# Import the code for the dialog
from ..widgets.table_managment_dialog import TableMgmtDialog
__author__ = 'Axel Horteborn'


class TableManagement:
    def __init__(self, parent):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        self.add_to_Param_row_count = 0
        self.db = parent.db
        self.dock_widget = parent.dock_widget
        self.parent = parent
        self.tr = parent.tr
        # Create the dialog (after translation) and keep reference
        self.TMD = TableMgmtDialog()
        self.tables_in_db = 0
        self.params_in_list = 0
        self.current_table = None
        self.current_schema = None
        self.params_in_table = None
        # TODO: check this
        self.items_in_table = []

    def run(self):
        """Connects the push buttons and enable the visibility of the dialog."""
        self.TMD.pButRemove.clicked.connect(self.remove_table_from_db)
        self.TMD.pButCombine.clicked.connect(self.merge_tbls)
        self.TMD.pButChangeTbl.clicked.connect(self.edit_tbl_name)
        self.TMD.pButChangeParam.clicked.connect(self.edit_param_name)
        self.TMD.pButAdd_Param.clicked.connect(self.retrieve_params)
        self.TMD.pButSave.clicked.connect(self.save_table)
        self.update_table_list()
        self.TMD.show()
        self.TMD.exec_()

    def merge_tbls(self):
        """Merging two data sets into one."""
        # TODO: remove all polygons and create new polygons.
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
        if new_name in self.db.get_tables_in_db():
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

    def retrieve_params(self):
        """This function is trigged by "edit" table, and basically fills the left list widget,
        all attributes that have a index get selected by default."""
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
        try:
            self.db.execute_sql("""DROP INDEX IF EXISTS {schema}.gist_{tbl};
create index gist_{tbl} on {schema}.{tbl} using gist(polygon) """.format(tbl=table, schema=schema))
        except:
            pass
        try:
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
                if str(name[0]) in ['harrowing_manual', 'plowing_manual', 'manual']:
                    continue
                item_name = schema + '.' + str(name[0])
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
