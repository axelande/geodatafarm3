from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from datetime import date
from PyQt5.QtWidgets import QMessageBox, QFileDialog
width, height = A4


def coord(x, y, unit=1):
    x, y = x * unit, height - y * unit
    return x, y


class RepportGen:
    def __init__(self, parent):
        self.tr = parent.tr
        self.db = parent.db
        self.dw = parent.dock_widget
        self.parent = parent
        self.path = None

    def set_widget_connections(self):
        """A simple function that sets the buttons on the planting tab"""
        self.parent.dock_widget.PBReportListAll.clicked.connect(self.generate_report)
        self.parent.dock_widget.PBReportSelectFolder.clicked.connect(self.select_folder)

    def select_folder(self):
        """A function that lets the user select the folder for the
        generated reports. The self.path will be updated with this function."""
        dialog = QFileDialog()
        folder_path = dialog.getExistingDirectory(None, "Select Folder")
        if folder_path:
            self.path = folder_path

    def generate_report(self):
        if self.path is None:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('A directory to save the report must be selected.'))
            return
        year = self.dw.DEReportYear.text()
        if self.dw.RBReportWithoutDetails.isChecked():
            report_name = '{t}_{y}'.format(t=self.tr('GeoDataFarm_Limited_report'),
                                           y=year)
            self.compact_report(report_name, year)
        else:
            report_name = '{t}_{y}'.format(t=self.tr('GeoDataFarm_Limited_report'),
                                           y=year)

    def compact_report(self, report_name, year):
        cur_date = date.today().isoformat()
        can = canvas.Canvas('{p}/{r}_{d}.pdf'.format(p=self.path, r=report_name,
                                                     d=cur_date), pagesize=A4)
        can.setLineWidth(.3)
        can.setFont('Helvetica', 12)

        can.drawString(30, 750, self.tr('Simple report from GeoDataFarm'))
        can.drawString(30, 733, self.tr('For the growing season of ') + str(year))
        can.drawString(500, 750, cur_date)
        can.line(30, 723, 580, 723)

        ## Body
        sql = """select date_, field, crop, variety from plant.manual where table_ = 'None'"""
        planting_data_simple = [[self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Variety')]]
        planting_data_simple.extend(self.db.execute_and_return(sql))
        sql = """select date_, field, crop, variety, table_ from plant.manual where table_ <> 'None'"""
        planting_data_advanced = self.db.execute_and_return(sql)
        planting_space = 0
        if len(planting_data_simple) > 0:
            can.drawString(35, 703, self.tr('Planting data (simple input)'))
            planting_space = len(planting_data_simple) * 10
            table = Table(planting_data_simple, repeatRows=1)
            w, h = table.wrap(width, height)
            table.wrapOn(can, width, height)
            table.drawOn(can, 35, 683 - h)
        if len(planting_data_advanced) > 0:
            can.drawString(35, 683 - h - 18, self.tr('Planting data (text input)'))
            planting_space2 = len(planting_data_advanced) * 10
            adv_data = [[self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Variety')]]
            for date_, field, crop, variety, table_ in planting_data_advanced:
                if date_[:2] == 'c_':
                    _date_ = date_[2:]
                else:
                    sql = """ select array_agg(distinct({d})) from plant.{t}""".format(d=date_, t=table_)
                    _date_ = str(self.db.execute_and_return(sql)[0][0])[1:-1]
                if variety[:2] == 'c_':
                    _variety_ = variety[2:]
                elif variety == '':
                    _variety_ = ''
                else:
                    sql = """ select array_agg(distinct({v})) from plant.{t}""".format(v=variety, t=table_)
                    _variety_ = str(self.db.execute_and_return(sql)[0][0])[1:-1]
                adv_data.extend([[_date_, field, crop, _variety_]])
            table2 = Table(adv_data, repeatRows=1)
            w1, h1 = table2.wrap(0, 0)
            table2.wrapOn(can, width, height)
            table2.drawOn(can, 35, 683 - h - 24 - h1)
        try:
            can.save()
        except OSError:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('You must close the file in order to create it again'))
            return
