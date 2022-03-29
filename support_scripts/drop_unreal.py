from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QMessageBox

from ..support_scripts.__init__ import TR
from ..widgets.drop_un_real import DropUnRealWidget


class DropUnReal:
    def __init__(self, parent):
        self.parent = parent
        self.db = parent.db
        translate = TR('DropUnReal')
        self.tr = translate.tr
        self.DUR = DropUnRealWidget()
        self.schema = ''
        self.table = ''


    def show(self):
        """Displays the widget"""
        self.connect_boxes()
        self.DUR.show()
        self.DUR.exec_()

    def connect_boxes(self):
        self.DUR.CBTypes.currentIndexChanged.connect(self.get_tables)
        self.DUR.CBTables.currentIndexChanged.connect(self.get_attributes)
        self.DUR.PBOK.clicked.connect(self.run)
        self.DUR.PBCancel.clicked.connect(self.cancel)

    def disconnect_boxes(self):
        self.DUR.CBTypes.currentIndexChanged.disconnect()
        self.DUR.CBTables.currentIndexChanged.disconnect()
        self.DUR.PBOK.clicked.disconnect()
        self.DUR.PBCancel.clicked.disconnect()

    def get_tables(self):
        self.DUR.CBTables.clear()
        self.DUR.CBTables.addItem(self.tr('- select dataset -'))
        if self.DUR.CBTypes.currentText() == self.tr('- Select type -'):
            return
        elif self.DUR.CBTypes.currentText() == self.tr('plant'):
            schema = 'plant'
        elif self.DUR.CBTypes.currentText() == self.tr('fertilize'):
            schema = 'ferti'
        elif self.DUR.CBTypes.currentText() == self.tr('spray'):
            schema = 'spray'
        elif self.DUR.CBTypes.currentText() == self.tr('other'):
            schema = 'other'
        elif self.DUR.CBTypes.currentText() == self.tr('harvest'):
            schema = 'harvest'
        elif self.DUR.CBTypes.currentText() == self.tr('soil'):
            schema = 'soil'
        elif self.DUR.CBTypes.currentText() == self.tr('weather'):
            schema = 'plant'
        else:
            raise ValueError('Wrong type' + self.DUR.CBTypes.currentText())
            return
        self.schema = schema
        tables = self.db.get_tables_in_db(schema)
        self.DUR.CBTables.addItems(tables)

    def get_attributes(self):
        if self.DUR.CBTables.currentText() != self.tr('- select dataset -'):
            self.DUR.CBAttributes.clear()
            self.DUR.CBAttributes.addItem(self.tr('- select attribute -'))
            cols_ = self.db.get_all_columns(self.DUR.CBTables.currentText(), self.schema)
            cols = []
            for col in cols_:
                cols.append(col[0])
            self.DUR.CBAttributes.addItems(cols)
            self.table = self.DUR.CBTables.currentText()

    def run(self):
        if self.DUR.CBAttributes.currentText() == self.tr('- select attribute -'):
            return
        attribute = self.DUR.CBAttributes.currentText()
        operator = self.DUR.CBOperator.currentText()
        value = self.DUR.QLValue.text()
        sql = f"""select count(*) FROM {self.schema}.{self.table} where {attribute} {operator} {value}"""
        rows_affected = self.db.execute_and_return(sql)[0][0]
        question = QMessageBox.question(None, 'Proceed?', f'The action will remove all rows where {attribute} {operator} {value}\nThis will remove: {rows_affected}, are you sure that you want to proceed?')
        if question == QMessageBox.Yes:
            sql = f'DELETE FROM {self.schema}.{self.table} where {attribute} {operator} {value}'
            self.db.execute_sql(sql)
            self.cancel()

    def cancel(self):
        self.disconnect_boxes()
        self.DUR.close()
