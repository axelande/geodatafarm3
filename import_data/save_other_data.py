from typing import Self
from psycopg2 import sql as pgsql
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QDate
from ..support_scripts.__init__ import check_text
from ..support_scripts.__init__ import TR
from ..support_scripts.notifier import report_success, report_warning, report_error


class SaveOther:
    def __init__(self: Self, parent) -> None:
        """A class for storing other data

        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.dw = parent.dock_widget
        translate = TR('SaveOther')
        self.tr = translate.tr
        self.parent = parent

    def set_widget_connections(self: Self) -> None:
        """A simple function that sets the buttons on the planting tab"""
        self.parent.dock_widget.PBSaveOther.clicked.connect(self.save_manual_data)

    def save_manual_data(self):
        """Saves manual data."""
        if self.check_input():
            field = self.dw.CBOField.currentText()
            crop = self.dw.CBOCrop.currentText()
            if crop == self.tr('--- Select crop ---'):
                crop = None
            date_ = self.dw.DEOther.selectedDate().toString("yyyy-MM-dd")

            select_parts = [
                pgsql.SQL("%s AS field"),
                pgsql.SQL("%s AS crop"),
                pgsql.SQL("%s AS date_"),
            ]
            params = [field, crop, date_]

            for opt_w, unit_w, val_w in [
                (self.dw.LEOOption_1, self.dw.LEOUnit_1, self.dw.LEOValue_1),
                (self.dw.LEOOption_2, self.dw.LEOUnit_2, self.dw.LEOValue_2),
                (self.dw.LEOOption_3, self.dw.LEOUnit_3, self.dw.LEOValue_3),
                (self.dw.LEOOption_4, self.dw.LEOUnit_4, self.dw.LEOValue_4),
            ]:
                option = check_text(opt_w.text())
                if option == '':
                    continue
                unit = check_text(unit_w.text())
                if unit == '':
                    unit = 'Null'
                value = check_text(val_w.text())
                if value == '':
                    continue
                select_parts.append(
                    pgsql.SQL("%s AS {alias}").format(
                        alias=pgsql.Identifier(f"{option}_{unit}")))
                params.append(value)

            other = self.dw.LEOOther.toPlainText()
            if other == '':
                other = None
            select_parts.append(pgsql.SQL("%s AS other"))
            params.append(other)

            name = self.dw.LEOtherName.text()
            tbl = f"{check_text(name)}_{check_text(date_)}_{field}"
            exists = self.parent.db.execute_and_return(
                "SELECT EXISTS ("
                " SELECT 1 FROM information_schema.tables"
                " WHERE table_schema = 'other' AND table_name = %s)",
                params=(tbl,))[0][0]
            if exists:
                report_warning(self.tr('That operation, at that field on that day is already stored'))
                return
            query = pgsql.SQL("SELECT {cols} INTO other.{tbl}").format(
                cols=pgsql.SQL(", ").join(select_parts),
                tbl=pgsql.Identifier(tbl))
            try:
                self.parent.db.execute_sql(query, params=tuple(params))
                report_success(self.tr('The data was stored correctly'))
            except Exception as e:
                report_error(self.tr(f'Following error occurred: {e}'), detail=str(e))
        self.reset_widget()

    def reset_widget(self):
        """Resets the widget to the default values"""
        self.dw.CBOField.setCurrentIndex(0)
        self.dw.CBOCrop.setCurrentIndex(0)
        self.dw.LEOOption_1.setText('')
        self.dw.LEOValue_1.setText('')
        self.dw.LEOUnit_1.setText('')
        self.dw.LEOOption_2.setText('')
        self.dw.LEOValue_2.setText('')
        self.dw.LEOUnit_2.setText('')
        self.dw.LEOOption_3.setText('')
        self.dw.LEOValue_3.setText('')
        self.dw.LEOUnit_3.setText('')
        self.dw.LEOOption_4.setText('')
        self.dw.LEOValue_4.setText('')
        self.dw.LEOUnit_4.setText('')
        self.dw.LEOOther.setPlainText('')
        self.dw.LEOtherName.setText('')

    def check_input(self):
        """Some simple checks that ensure that the basic data is filled in.

        Returns
        -------
        bool
        """
        if self.dw.CBOField.currentText() == self.tr('--- Select field ---'):
            report_warning(self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.DEOther.selectedDate().toString("yyyy-MM-dd") == '2000-01-01':
            report_warning(self.tr('In order to save the data you must select a date'))
            return False
        return True
