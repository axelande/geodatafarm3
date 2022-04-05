from ..support_scripts.drop_unreal import DropUnReal
from ..widgets.rescale_values_widget import RescaleValuesWidget


class RescaleValues(DropUnReal):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.DUR = RescaleValuesWidget()

    def run(self):
        if self.DUR.CBAttributes.currentText() == self.tr('- select attribute -'):
            return
        attribute = self.DUR.CBAttributes.currentText()
        operator = self.DUR.CBOperator.currentText()
        value = self.DUR.QLValue.text()
        sql = f"""UPDATE {self.schema}.{self.table} 
        SET {attribute} = {attribute} {operator} {value}"""
        self.db.execute_sql(sql)
        self.cancel()
