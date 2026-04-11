from psycopg2 import sql as pgsql

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
        query = pgsql.SQL("UPDATE {schema}.{tbl} SET {col} = {col} {op} %s").format(
            schema=pgsql.Identifier(self.schema),
            tbl=pgsql.Identifier(self.table),
            col=pgsql.Identifier(attribute),
            op=pgsql.SQL(operator))
        self.db.execute_sql(query, params=(value,))
        self.cancel()
