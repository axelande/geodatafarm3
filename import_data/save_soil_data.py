from ..import_data.handle_text_data import InputTextHandler
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate


class SaveSoil:
    def __init__(self, parent):
        """
        A class for storing spraying data
        :param parent: GeoDataFarm "self"
        """
        self.dw = parent.dock_widget
        self.tr = parent.tr
        self.parent = parent

    def set_widget_connections(self):
        """A simple function that sets the buttons on the planting tab"""
        self.parent.dock_widget.PBSoAddFile.clicked.connect(self.run_file_import)
        self.parent.dock_widget.PBSoSaveManual.clicked.connect(self.save_manual_data)

    def run_file_import(self):
        """The function loads the correct import dialog for files"""
        columns = [self.tr('Clay'), self.tr('Humus'), self.tr('pH'), self.tr('rx')]
        if self.dw.CBSoFileType.currentText() == self.tr('Text file (.csv; .txt)'):
            add_f = InputTextHandler(self.parent, 'soil', columns=columns)
            add_f.run()
        elif self.dw.CBSoFileType.currentText() == self.tr('Databasefile (.db)'):
            QMessageBox.information(None, "Error:", self.tr(
                'Support for databasefiles are not implemented 100% yet'))
            return
            self.IH = dbFileHandler(self.iface, self.dock_widget)
            self.IH.start_up()
        elif self.dw.CBSoFileType.currentText() == self.tr('Shape file (.shp)'):
            QMessageBox.information(None, "Error:", self.tr(
                'Support for shapefiles are not implemented 100% yet'))
            return
            try:
                feature = self.df.getFeatures().next()
                polygon = feature.geometry().asPolygon()[0]
            except:
                polygon = None
            self.ShpHandler = InputShpHandler(self.iface, self, polygon)
            self.ShpHandler.add_input()

    def save_manual_data(self):
        if self.check_input():
            field = self.dw.CBSoField.currentText()
            date_ = self.dw.DESoil.text()
            clay = self.dw.LESoClay.text()
            humus = self.dw.LESoHumus.text()
            ph = self.dw.LESoPh.text()
            rx = self.dw.LESoRx.text()
            other = self.dw.LESoOther.toPlainText()
            if clay == '':
                clay = 'Null'
            if humus == '':
                humus = 'Null'
            if ph == '':
                ph = 'Null'
            if rx == '':
                rx = 'Null'
            if other == '':
                other = 'Null'
            sql = """Insert into soil.manual(field, date_, clay, humus, ph, rx, other, table_) 
            VALUES ('{field}', '{date_}','{clay}','{humus}','{ph}','{rx}','{other}', 'None')
            """.format(field=field, date_=date_, clay=clay, humus=humus, ph=ph, rx=rx, other=other)
            try:
                self.parent.db.execute_sql(sql)
                QMessageBox.information(None, self.tr('Success'), self.tr('The data was stored correctly'))
            except Exception as e:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr('Following error occurred: {m}'.format(m=e)))
        self.reset_widget()

    def reset_widget(self):
        """Resets the widget to the default values"""
        self.dw.CBSoField.setCurrentIndex(0)
        self.dw.DESoil.setDate(QDate.fromString('2000-01-01', 'yyyy-MM-dd'))
        self.dw.LESoClay.setText('')
        self.dw.LESoHumus.setText('')
        self.dw.LESoPh.setText('')
        self.dw.LESoRx.setText('')
        self.dw.LESoOther.setPlainText('')

    def check_input(self):
        """Some simple checks that ensure that the basic data is filled in.
        :return bool"""
        if self.dw.CBSoField.currentText() == self.tr('--- Select field ---'):
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.DESoil.text() == '2000-01-01':
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a date'))
            return False
        return True
