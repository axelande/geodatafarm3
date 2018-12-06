from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from datetime import date
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from qgis.core import QgsTask
from functools import partial
import traceback
width, height = A4
styles = getSampleStyleSheet()
styleH = styles['Heading1']
styleN = styles['Normal']


def coord(x, y, unit=1):
    x, y = x * unit, height - y * unit
    return x, y


class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, tr, plugin_dir, growing_year, cur_date, **kw):
        self.allowSplitting = 0
        BaseDocTemplate.__init__(self, filename, **kw)
        self.tr = tr
        self.plugin_dir = plugin_dir
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height - 2 * cm, id='normal')
        template = PageTemplate(id='test', frames=frame, onPage=partial(self.header,
                                                                        growing_year=growing_year,
                                                                        cur_date=cur_date))
        self.addPageTemplates(template)

    def header(self, canvas, doc, growing_year, cur_date):
        canvas.saveState()
        canvas.drawString(30, 750, self.tr('Simple report from GeoDataFarm'))
        canvas.drawString(30, 733, self.tr('For the growing season of ') + str(growing_year))
        canvas.drawImage(self.plugin_dir + '\\img\\icon.png', 500, 765, width=50, height=50)
        canvas.drawString(500, 750, 'Generated:')
        canvas.drawString(500, 733, cur_date)
        canvas.line(30, 723, 580, 723)
        #w, h = content.wrap(doc.width, doc.topMargin)
        #content.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - h)
        canvas.restoreState()


class RapportGen:
    def __init__(self, parent):
        self.tr = parent.tr
        self.db = parent.db
        self.dw = parent.dock_widget
        self.plugin_dir = parent.plugin_dir
        self.tsk_mngr = parent.tsk_mngr
        self.parent = parent
        self.path = None

    def set_widget_connections(self):
        """A simple function that sets the buttons on the report tab"""
        self.parent.dock_widget.PBReportPerOperation.clicked.connect(self.report_per_operation)
        self.parent.dock_widget.PBReportPerField.clicked.connect(self.report_per_field)
        self.parent.dock_widget.PBReportSelectFolder.clicked.connect(self.select_folder)

    def select_folder(self):
        """A function that lets the user select the folder for the
        generated reports. The self.path will be updated with this function."""
        dialog = QFileDialog()
        folder_path = dialog.getExistingDirectory(None, "Select Folder")
        if folder_path:
            self.path = folder_path

    def report_per_operation(self):
        if self.path is None:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('A directory to save the report must be selected.'))
            return
        year = self.dw.DEReportYear.text()
        if self.dw.RBReportWithoutDetails.isChecked():
            self.report_name = '{p}\\{t}_{y}.pdf'.format(p=self.path,
                                                         t=self.tr('GeoDataFarm_Limited_report'),
                                                         y=year)
            if self.dw.RBAllYear.isChecked():
                year = None
            else:
                year = self.dw.DEReportYear.text()
            task = QgsTask.fromFunction('Run import text data', self.collect_data, year,
                                        on_finished=self.simple_operation)
            self.tsk_mngr.addTask(task)
        else:
            report_name = '{p}\\{t}_{y}.pdf'.format(p=self.path,
                                                    t=self.tr('GeoDataFarm_Limited_report'),
                                                    y=year)

    def report_per_field(self):
        if self.path is None:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('A directory to save the report must be selected.'))
            return
        year = self.dw.DEReportYear.text()
        if self.dw.RBReportWithoutDetails.isChecked():
            self.report_name = '{p}\\{t}_{y}.pdf'.format(p=self.path,
                                                         t=self.tr('GeoDataFarm_Limited_report'),
                                                         y=year)
            if self.dw.RBAllYear.isChecked():
                year = None
            else:
                year = self.dw.DEReportYear.text()
            task = QgsTask.fromFunction('Run import text data', self.collect_data, year,
                                        on_finished=self.simple_field)
            self.tsk_mngr.addTask(task)
        else:
            report_name = '{p}\\{t}_{y}.pdf'.format(p=self.path,
                                                    t=self.tr('GeoDataFarm_Limited_report'),
                                                    y=year)

    def simple_operation(self,  result, values):
        """Generates a simple report of all operations"""
        if values[0] is False:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('Following error occurred: {m}\n\n Traceback: {t}'.format(m=values[1],
                                                                                                      t=values[2])))
            return
        operation_dict = values[1]
        cur_date = date.today().isoformat()
        growing_year = self.dw.DEReportYear.text()
        doc = MyDocTemplate(self.report_name, self.tr, self.plugin_dir, growing_year, cur_date)
        story = []
        operation_found = False
        for operation in ['planting', 'fertilizing', 'spraying', 'harvesting', 'plowing', 'harrowing', 'soil']:
            if operation_dict[operation]['simple']:
                if operation == 'planting':
                    story.append(Paragraph(self.tr('Planting data (simple input)'), styleH))
                elif operation == 'fertilizing':
                    story.append(Paragraph(self.tr('Fertilizing data (simple input)'), styleH))
                elif operation == 'spraying':
                    story.append(Paragraph(self.tr('Spraying data (simple input)'), styleH))
                elif operation == 'harvesting':
                    story.append(Paragraph(self.tr('Harvest data (simple input)'), styleH))
                elif operation == 'plowing':
                    story.append(Paragraph(self.tr('Harvest data (simple input)'), styleH))
                elif operation == 'harrowing':
                    story.append(Paragraph(self.tr('Harvest data (simple input)'), styleH))
                elif operation == 'soil':
                    story.append(Paragraph(self.tr('Harvest data (simple input)'), styleH))

                temp_d = [operation_dict[operation]['simple_heading']]
                l_heading = len(temp_d[0]) - 1
                temp_d.extend(operation_dict[operation]['simple_data'])
                table = Table(temp_d, repeatRows=1, hAlign='LEFT', colWidths=[380/l_heading] * l_heading)
                table.setStyle(TableStyle([('FONTSIZE', (0, 0), (l_heading, 0), 16)]))
                story.append(table)
                operation_found = True
            if operation_dict[operation]['advanced']:
                if operation == 'planting':
                    story.append(Paragraph(self.tr('Planting data (text input)'), styleH))
                elif operation == 'fertilizing':
                    story.append(Paragraph(self.tr('Fertilizing data (text input)'), styleH))
                elif operation == 'spraying':
                    story.append(Paragraph(self.tr('Spraying data (text input)'), styleH))
                elif operation == 'harvesting':
                    story.append(Paragraph(self.tr('Harvest data (text input)'), styleH))
                elif operation == 'soil':
                    story.append(Paragraph(self.tr('Soil data (text input)'), styleH))
                temp_d = [operation_dict[operation]['adv_heading']]
                l_heading = len(temp_d[0]) - 1
                temp_d.extend(operation_dict[operation]['advance_dat'])
                table = Table(temp_d, repeatRows=1, hAlign='LEFT', colWidths=[380/l_heading] * l_heading)
                table.setStyle(TableStyle([('FONTSIZE', (0, 0), (l_heading, 0), 16)]))
                story.append(table)
                operation_found = True
        if not operation_found:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('No data where found for that year'))
            return
        try:
            doc.multiBuild(story)
        except OSError:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('You must close the file in order to create it again'))
            return

    def simple_field(self, result, values):
        """Generates a simple report of all operations listed by fields."""
        if values[0] is False:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('Following error occurred: {m}\n\n Traceback: {t}'.format(m=values[1],
                                                                                                      t=values[2])))
            return
        operation_dict = values[1]
        cur_date = date.today().isoformat()
        growing_year = self.dw.DEReportYear.text()
        doc = MyDocTemplate(self.report_name, self.tr, self.plugin_dir, growing_year, cur_date)
        story = []
        field_dict = {}
        for field in self.db.execute_and_return('select field_name from fields'):
            field = field[0]
            if field is None:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr('You must create fields before you can get make reports'))
                return
            field_dict[field] = {'tables': [],
                                 'headings': []}
        data_found = False
        for operation in ['planting', 'fertilizing', 'spraying', 'harvesting', 'plowing', 'harrowing', 'soil']:
            if operation == 'planting':
                operation_name = self.tr('Planting')
                if not self.dw.CBPlanting.isChecked():
                    continue
            elif operation == 'fertilizing':
                operation_name = self.tr('Fertilizing')
                if not self.dw.CBFertilizing.isChecked():
                    continue
            elif operation == 'spraying':
                operation_name = self.tr('Spraying')
                if not self.dw.CBSpraying.isChecked():
                    continue
            elif operation == 'harvesting':
                operation_name = self.tr('Harvest')
                if not self.dw.CBHarvest.isChecked():
                    continue
            elif operation == 'plowing':
                operation_name = self.tr('Plowing')
                if not self.dw.CBPlowing.isChecked():
                    continue
            elif operation == 'harrowing':
                operation_name = self.tr('Harrowing')
                if not self.dw.CBHarrowing.isChecked():
                    continue
            elif operation == 'soil':
                operation_name = self.tr('Soil')
                if not self.dw.CBSoil.isChecked():
                    continue
            if operation_dict[operation]['simple']:
                data_found = True
                field_col = operation_dict[operation]['simple_heading'].index(self.tr('Field'))
                operation_dict[operation]['adv_heading'][field_col] = self.tr('Operation')
                head_row = operation_dict[operation]['adv_heading']
                for row in operation_dict[operation]['simple_data']:
                    field_dict[row[field_col].text]['heading'].append(head_row)
                    temp_row = []#[None] * len(field_dict[row[field_col]]['heading'])
                    for i, col in enumerate(row):
                        if i == field_col:
                            col = operation_name
                        temp_row.append(col)
                    field_dict[row[field_col].text]['table'].append(temp_row)
            if operation_dict[operation]['advanced']:
                data_found = True
                field_col = operation_dict[operation]['adv_heading'].index(self.tr('Field'))
                operation_dict[operation]['adv_heading'][field_col] = self.tr('Operation')
                head_row = operation_dict[operation]['adv_heading']
                for row in operation_dict[operation]['advance_dat']:
                    field_dict[row[field_col].text]['headings'].append(head_row)
                    temp_row = []#[None] * len(field_dict[row[field_col].text]['headings'])
                    for i, col in enumerate(row):
                        if i == field_col:
                            col = operation_name
                        temp_row.append(col)
                    field_dict[row[field_col].text]['tables'].append(temp_row)

        if not data_found:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('No data where found for that year'))
            return
        for field in field_dict.keys():
            story.append(Paragraph(field, styleH))
            for i, heading in enumerate(field_dict[field]['headings']):
                l_heading = len(heading) - 1
                tmp_tabl = [heading]
                tmp_tabl.append(field_dict[field]['tables'][i])
                table = Table(tmp_tabl, repeatRows=1, hAlign='LEFT', colWidths=[380 / l_heading] * l_heading)
                table.setStyle(TableStyle([('FONTSIZE', (0, 0), (l_heading, 0), 12)]))
                story.append(table)
        try:
            doc.multiBuild(story)
        except OSError:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('You must close the file in order to create it again'))
            return

    def collect_data(self, task, year):
        """Collect data from the different schemas at the server and
        store them in a dict

        Returns
        -------------------
        dict
         """
        data_dict = {'planting': {'simple': False, 'advanced': False},
                     'fertilizing': {'simple': False, 'advanced': False},
                     'spraying': {'simple': False, 'advanced': False},
                     'harvesting': {'simple': False, 'advanced': False},
                     'plowing': {'simple': False, 'advanced': False},
                     'harrowing': {'simple': False, 'advanced': False},
                     'soil': {'simple': False, 'advanced': False}
                     }
        try:
            # Planting
            if task != 'debug':
                task.setProgress(5)
            sql = """select date_, field, crop, variety from plant.manual 
            where table_ = 'None' """
            if year is not None:
                sql += """and extract(year from date_) = {y}""".format(y=year)
            simple_plant_data = self.db.execute_and_return(sql)
            if len(simple_plant_data) > 0:
                simple_heading = [self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Variety')]
                for row in simple_plant_data:
                    date_str = ''
                    for date_nr in row[0].split(','):
                        date_str += date_nr.date().isoformat() + ', '
                    row[0] = Paragraph(date_str[:-2], styleN)
                    row[1] = Paragraph(row[1], styleN)
                    row[2] = Paragraph(row[2], styleN)
                    row[3] = Paragraph(row[3], styleN)
                data_dict['planting']['simple'] = True
                data_dict['planting']['simple_data'] = simple_plant_data
                data_dict['planting']['simple_heading'] = simple_heading
            sql = """select date_text, field, crop, variety, table_ from plant.manual 
            where table_ <> 'None'"""
            planting_data_advanced = self.db.execute_and_return(sql)
            if len(planting_data_advanced) > 0:
                adv_data = []
                for date_, field, crop, variety, table_ in planting_data_advanced:
                    if date_[:2] == 'c_':
                        _date_ = date_[2:]
                    else:
                        sql = """ select array_agg(distinct({d}::date)) from plant.{t}""".format(
                            d=date_, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _date_ = ''
                        temp_ans = self.db.execute_and_return(sql)[0][0]
                        if temp_ans is None:
                            continue
                        for temp in temp_ans:
                            _date_ += temp.isoformat() + ', '
                        _date_ = Paragraph(_date_[:-2], styleN)
                    if variety[:2] == 'c_':
                        _variety_ = variety[2:]
                    elif variety == 'None':
                        _variety_ = ''
                    else:
                        sql = """ select array_agg(distinct({v})) from plant.{t}""".format(v=variety, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _variety_ = Paragraph(str(self.db.execute_and_return(sql)[0][0])[1:-1], styleN)
                    field = Paragraph(field, styleN)
                    crop = Paragraph(crop, styleN)
                    adv_data.append([_date_, field, crop, _variety_])
                if len(adv_data) > 0:
                    adv_heading = [self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Variety')]
                    data_dict['planting']['advanced'] = True
                    data_dict['planting']['advance_dat'] = adv_data
                    data_dict['planting']['adv_heading'] = adv_heading
            sql = """select date_, field, crop, variety, rate from ferti.manual 
            where table_ = 'None' """
            if year is not None:
                sql += """and extract(year from date_) = {y}""".format(y=year)
            # Fertilizing
            if task != 'debug':
                task.setProgress(15)
            simple_ferti_data = self.db.execute_and_return(sql)
            if len(simple_ferti_data) > 0:
                simple_heading = [self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Variety'), self.tr('Rate')]
                for row in simple_ferti_data:
                    date_str = ''
                    for date_nr in row[0].split(','):
                        date_str += date_nr.date().isoformat() + ', '
                    row[0] = Paragraph(date_str[:-2], styleN)
                    row[1] = Paragraph(row[1], styleN)
                    row[2] = Paragraph(row[2], styleN)
                    row[3] = Paragraph(row[3], styleN)
                data_dict['fertilizing']['simple'] = True
                data_dict['fertilizing']['simple_data'] = simple_ferti_data
                data_dict['fertilizing']['simple_heading'] = simple_heading
            sql = """select date_text, field, crop, variety, rate, table_ from ferti.manual 
            where table_ <> 'None'"""
            fertilizing_data_advanced = self.db.execute_and_return(sql)
            if len(fertilizing_data_advanced) > 0:
                adv_data = []
                for date_, field, crop, variety, rate, table_ in fertilizing_data_advanced:
                    if date_[:2] == 'c_':
                        _date_ = date_[2:]
                    else:
                        sql = """ select array_agg(distinct(date_)) from ferti.{t}""".format(t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _date_ = ''
                        for temp in self.db.execute_and_return(sql)[0][0]:
                            _date_ += temp.date().isoformat() + ', '
                        _date_ = Paragraph(_date_[:-2], styleN)
                    if variety[:2] == 'c_':
                        _variety_ = variety[2:]
                    elif variety == 'None':
                        _variety_ = ''
                    else:
                        sql = """ select array_agg(distinct({v})) from ferti.{t}""".format(v=variety, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _variety_ = str(self.db.execute_and_return(sql)[0][0])[1:-1]
                    if rate[:2] == 'c_':
                        _rate_ = rate[2:]
                    elif rate == 'None':
                        _rate_ = ''
                    else:
                        sql = """ select array_agg(distinct({r})) from ferti.{t} where extract(year from date_) = {y}""".format(r=rate, t=table_, y=year)
                        _rate_ = str(self.db.execute_and_return(sql)[0][0])[1:-1]
                    field = Paragraph(field, styleN)
                    crop = Paragraph(crop, styleN)
                    _variety_ = Paragraph(_variety_, styleN)
                    adv_data.append([_date_, field, crop, _variety_, _rate_])
                if len(adv_data) > 0:
                    adv_heading = [self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Variety'), self.tr('Rate')]
                    data_dict['fertilizing']['advanced'] = True
                    data_dict['fertilizing']['advance_dat'] = adv_data
                    data_dict['fertilizing']['adv_heading'] = adv_heading
            # Spraying
            if task != 'debug':
                task.setProgress(25)
            sql = """select date_, field, crop, variety, rate from spray.manual 
            where table_ = 'None' """
            if year is not None:
                sql += """and extract(year from date_) = {y}""".format(y=year)
            simple_data = self.db.execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Variety'), self.tr('Rate')]
                for row in simple_data:
                    date_str = ''
                    for date_nr in row[0].split(','):
                        date_str += date_nr.date().isoformat() + ', '
                    row[0] = Paragraph(date_str[:-2], styleN)
                    row[1] = Paragraph(row[1], styleN)
                    row[2] = Paragraph(row[2], styleN)
                    row[3] = Paragraph(row[3], styleN)
                data_dict['spraying']['simple'] = True
                data_dict['spraying']['simple_data'] = simple_data
                data_dict['spraying']['simple_heading'] = simple_heading
            sql = """select date_text, field, crop, variety, rate, table_ from spray.manual 
            where table_ <> 'None'"""
            spraying_data_advanced = self.db.execute_and_return(sql)
            if len(spraying_data_advanced) > 0:
                adv_data = []
                for date_, field, crop, variety, rate, table_ in spraying_data_advanced:
                    if date_ == 'None':
                        pass
                    elif date_[:2] == 'c_':
                        _date_ = date_[2:]
                    else:
                        sql = """ select array_agg(distinct({d})) from spray.{t}""".format(
                            d=date_, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _date_ = ''
                        for temp in self.db.execute_and_return(sql)[0][0]:
                            _date_ += temp.date().isoformat() + ', '
                        _date_ = Paragraph(_date_[:-2], styleN)
                    if variety[:2] == 'c_':
                        _variety_ = variety[2:]
                    elif variety == 'None':
                        _variety_ = ''
                    else:
                        sql = """ select array_agg(distinct({v})) from spray.{t}""".format(v=variety, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _variety_ = str(self.db.execute_and_return(sql)[0][0])[1:-1]
                    if rate[:2] == 'c_':
                        _rate_ = rate[2:]
                    elif rate == 'None':
                        _rate_ = ''
                    else:
                        sql = """ select array_agg(distinct({r})) from spray.{t}""".format(r=rate, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _rate_ = str(self.db.execute_and_return(sql)[0][0])[1:-1]
                    field = Paragraph(field, styleN)
                    crop = Paragraph(crop, styleN)
                    _variety_ = Paragraph(_variety_)
                    adv_data.append([_date_, field, crop, _variety_, _rate_])
                if len(adv_data) > 0:
                    adv_heading = [self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Variety'), self.tr('Rate')]
                    data_dict['spraying']['advanced'] = True
                    data_dict['spraying']['advance_dat'] = adv_data
                    data_dict['spraying']['adv_heading'] = adv_heading
            #Harvest
            if task != 'debug':
                task.setProgress(35)
            sql = """select date_, field, crop, total_yield, yield from harvest.manual 
            where table_ = 'None' """
            if year is not None:
                sql += """and extract(year from date_) = {y}""".format(y=year)
            simple_data = self.db.execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Total yield'), self.tr('Yield (kg/ha)')]
                for row in simple_data:
                    date_str = ''
                    for date_nr in row[0].split(','):
                        date_str += date_nr.date().isoformat() + ', '
                    row[0] = Paragraph(date_str[:-2], styleN)
                    row[1] = Paragraph(row[1], styleN)
                    row[2] = Paragraph(row[2], styleN)
                data_dict['harvesting']['simple'] = True
                data_dict['harvesting']['simple_data'] = simple_data
                data_dict['harvesting']['simple_heading'] = simple_heading
            sql = """select date_text, field, crop, yield, total_yield, table_ from harvest.manual 
            where table_ <> 'None'"""
            data_advanced = self.db.execute_and_return(sql)
            if len(data_advanced) > 0:
                adv_data = []
                for date_, field, crop, yield_, total_yield, table_ in data_advanced:
                    if date_[:2] == 'c_':
                        _date_ = date_[2:]
                    else:
                        sql = """ select array_agg(distinct({d}::date)) from harvest.{t}""".format(d=date_, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _date_ = ''
                        temp_ans = self.db.execute_and_return(sql)[0][0]
                        if temp_ans is None:
                            continue
                        for temp in temp_ans:
                            _date_ += temp.isoformat() + ', '
                        _date_ = Paragraph(_date_[:-2], styleN)
                    if yield_[:2] == 'c_':
                        _yield_ = yield_[2:]
                    elif yield_ == 'None':
                        _yield_ = ''
                    else:
                        sql = """ select round(avg({v})*100)/100::double precision from harvest.{t}""".format(v=yield_, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _yield_ = str(self.db.execute_and_return(sql)[0][0])
                    if total_yield[:2] == 'c_':
                        _total_yield_ = total_yield[2:]
                    elif total_yield == 'None':
                        _total_yield_ = ''
                    else:
                        sql = """ select round(avg({v})*100)/100::double precision from harvest.{t} """.format(v=total_yield, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _total_yield_ = str(self.db.execute_and_return(sql)[0][0])
                    field = Paragraph(field, styleN)
                    crop = Paragraph(crop, styleN)
                    adv_data.append([_date_, field, crop, _yield_, _total_yield_])
                if len(adv_data) > 0:
                    adv_heading = [self.tr('Date'), self.tr('Field'), self.tr('Crop'), self.tr('Yield (kg/ha)'), self.tr('Total Yield')]
                    data_dict['harvesting']['advanced'] = True
                    data_dict['harvesting']['advance_dat'] = adv_data
                    data_dict['harvesting']['adv_heading'] = adv_heading
            # Plowing
            if task != 'debug':
                task.setProgress(50)
            sql = """select date_, field, depth from other.plowing_manual"""
            if year is not None:
                sql += """ where extract(year from date_) = {y}""".format(y=year)
            simple_data = self.db.execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [self.tr('Date'), self.tr('Field'), self.tr('Depth')]
                for row in simple_data:
                    date_str = ''
                    for date_nr in row[0].split(','):
                        date_str += date_nr.date().isoformat() + ', '
                    row[0] = Paragraph(date_str[:-2], styleN)
                    row[1] = Paragraph(row[1], styleN)
                data_dict['plowing']['simple'] = True
                data_dict['plowing']['simple_data'] = simple_data
                data_dict['plowing']['simple_heading'] = simple_heading
            # Harrowing
            if task != 'debug':
                task.setProgress(55)
            sql = """select date_, field, depth from other.harrowing_manual"""
            if year is not None:
                sql += """ where extract(year from date_) = {y}""".format(y=year)
            simple_data = self.db.execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [self.tr('Date'), self.tr('Field'), self.tr('Depth')]
                for row in simple_data:
                    date_str = ''
                    for date_nr in row[0].split(','):
                        date_str += date_nr.date().isoformat() + ', '
                    row[0] = Paragraph(date_str[:-2], styleN)
                    row[1] = Paragraph(row[1], styleN)
                data_dict['harrowing']['simple'] = True
                data_dict['harrowing']['simple_data'] = simple_data
                data_dict['harrowing']['simple_heading'] = simple_heading
            #Soil
            if task != 'debug':
                task.setProgress(60)
            sql = """select date_, field, clay, humus, ph, rx from soil.manual 
            where table_ = 'None' """
            if year is not None:
                sql += """and extract(year from date_) = {y}""".format(y=year)
            simple_data = self.db.execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [self.tr('Date'), self.tr('Field'), self.tr('Clay'), self.tr('Humus'), self.tr('pH'), self.tr('rx')]
                for row in simple_data:
                    date_str = ''
                    for date_nr in row[0].split(','):
                        date_str += date_nr.date().isoformat() + ', '
                    row[0] = Paragraph(date_str[:-2], styleN)
                    row[1] = Paragraph(row[1], styleN)
                data_dict['soil']['simple'] = True
                data_dict['soil']['simple_data'] = simple_data
                data_dict['soil']['simple_heading'] = simple_heading
            sql = """select date_text, field, clay, humus, ph, rx, table_ from soil.manual 
            where table_ <> 'None'"""
            data_advanced = self.db.execute_and_return(sql)
            if len(data_advanced) > 0:
                adv_data = []
                for date_, field, clay, humus, ph, rx, table_ in data_advanced:
                    if date_ == 'None':
                        pass
                    elif date_[:2] == 'c_':
                        _date_ = date_[2:]
                    else:
                        sql = """ select array_agg(distinct({d})) from soil.{t} 
                        """.format(d=date_, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _date_ = ''
                        for temp in self.db.execute_and_return(sql)[0][0]:
                            _date_ += temp.date().isoformat()
                        _date_ = Paragraph(_date_[:-2], styleN)
                    if clay[:2] == 'c_':
                        _clay_ = clay[2:]
                    elif clay == 'None':
                        _clay_ = ''
                    else:
                        sql = """ select round(avg({v})*100)/100::double precision 
                        from soil.{t}""".format(v=clay, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _clay_ = str(self.db.execute_and_return(sql)[0][0])
                    if humus[:2] == 'c_':
                        _humus_ = humus[2:]
                    elif humus == 'None':
                        _humus_ = ''
                    else:
                        sql = """ select round(avg({r})*100)/100::double precision 
                        from soil.{t}""".format(r=humus, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _humus_ = str(self.db.execute_and_return(sql)[0][0])
                    if ph[:2] == 'c_':
                        _ph_ = ph[2:]
                    elif ph == 'None':
                        _ph_ = ''
                    else:
                        sql = """ select round(avg({r})*100)/100::double precision from soil.{t}""".format(r=ph, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _ph_ = str(self.db.execute_and_return(sql)[0][0])
                    if rx[:2] == 'c_':
                        _rx_ = rx[2:]
                    elif rx == 'None':
                        _rx_ = ''
                    else:
                        sql = """ select round(avg({r})*100)/100::double precision from soil.{t} """.format(r=rx, t=table_)
                        if year is not None:
                            sql += """ where extract(year from date_) = {y}""".format(y=year)
                        _rx_ = str(self.db.execute_and_return(sql)[0][0])
                    field = Paragraph(field, styleN)
                    adv_data.append([_date_, field, _clay_, _humus_, _ph_, _rx_])
                adv_heading = [self.tr('Date'), self.tr('Field'), self.tr('Clay'), self.tr('Humus'), self.tr('pH'), self.tr('rx')]
                data_dict['soil']['advanced'] = True
                data_dict['soil']['advance_dat'] = adv_data
                data_dict['soil']['adv_heading'] = adv_heading
            if task != 'debug':
                task.setProgress(95)
            return [True, data_dict]
        except Exception as e:
            return [False, e, traceback.format_exc()]
