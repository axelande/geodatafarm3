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
from ..support_scripts.__init__ import TR
width, height = A4
styles = getSampleStyleSheet()
styleH = styles['Heading1']
styleN = styles['Normal']


class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, plugin_dir, growing_year, cur_date, **kw):
        """Generate a basic A4 pdf document

        Parameters
        ----------
        filename: str
            The file name to store the PDF document
        tr: translation
            The Translation function from GeoDataFarm
        plugin_dir: str
            path to the plugin dir in order to find the icon
        growing_year: int
             What growing year
        cur_date: str
            Current date, to write on the report
        kw
        """
        BaseDocTemplate.__init__(self, filename, **kw)
        self.allowSplitting = 1
        translate = TR('MyDocTemplate')
        self.tr = translate.tr
        self.plugin_dir = plugin_dir
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height - 2 * cm, id='normal')
        template = PageTemplate(id='test', frames=frame, onPage=partial(self.header,
                                                                        growing_year=growing_year,
                                                                        cur_date=cur_date))
        self.addPageTemplates(template)

    def header(self, canvas, doc, growing_year, cur_date):
        """Create the header of the document

        Parameters
        ----------
        canvas
        doc
        growing_year: int
        cur_date: str, with the current date

        """
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
        """Generates reports from GeoDataFarm

        Parameters
        ----------
        parent: GeoDataFarm
        """
        translate = TR('RapportGen')
        self.tr = translate.tr
        self.db = parent.db
        self.dw = parent.dock_widget
        self.plugin_dir = parent.plugin_dir
        self.tsk_mngr = parent.tsk_mngr
        self.parent = parent
        self.path = None

    def set_widget_connections(self):
        """A simple function that sets the buttons on the report tab"""
        self.dw.PBReportPerOperation.clicked.connect(self.report_per_operation)
        self.dw.PBReportPerField.clicked.connect(self.report_per_field)
        self.dw.PBReportSelectFolder.clicked.connect(self.select_folder)

    def select_folder(self):
        """A function that lets the user select the folder for the
        generated reports. The self.path will be updated with this function."""
        dialog = QFileDialog()
        folder_path = dialog.getExistingDirectory(None, "Select Folder")
        if folder_path:
            self.path = folder_path

    def report_per_operation(self):
        """Creates a QgsTask in order to collect data then on finish it runs
        simple_operation."""
        if self.path is None:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('A directory to save the report must be selected.'))
            return
        year = self.dw.DEReportYear.text()
        if self.dw.RBReportWithoutDetails.isChecked():
            self.report_name = '{p}\\{t}_{y}.pdf'.format(p=self.path,
                                                         t=self.tr('GeoDataFarm_Limited_report_per_operation'),
                                                         y=year)
            if self.dw.RBAllYear.isChecked():
                year = None
            else:
                year = self.dw.DEReportYear.text()
            data = {'db': self.db, 'tr': self.tr, 'year': year}
            task = QgsTask.fromFunction('Run import text data',
                                        self.collect_data, data,
                                        on_finished=self.simple_operation)
            #self.tsk_mngr.addTask(task)
            a = self.collect_data('debug', data)
            self.simple_operation('a', a)
        else:
            report_name = '{p}\\{t}_{y}.pdf'.format(p=self.path,
                                                    t=self.tr('GeoDataFarm_Limited_report'),
                                                    y=year)

    def report_per_field(self):
        """Creates a QgsTask in order to collect data then on finish it runs
        simple_field."""
        if self.path is None:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('A directory to save the report must be selected.'))
            return
        year = self.dw.DEReportYear.text()
        if self.dw.RBReportWithoutDetails.isChecked():
            self.report_name = '{p}\\{t}_{y}.pdf'.format(p=self.path,
                                                         t=self.tr('GeoDataFarm_Limited_report_per_field'),
                                                         y=year)
            if self.dw.RBAllYear.isChecked():
                year = None
            else:
                year = self.dw.DEReportYear.text()
            data = {'db': self.db, 'tr': self.tr, 'year': year}
            task = QgsTask.fromFunction('Run import text data', self.collect_data, data,
                                        on_finished=self.simple_field)
            self.tsk_mngr.addTask(task)
        else:
            report_name = '{p}\\{t}_{y}.pdf'.format(p=self.path,
                                                    t=self.tr('GeoDataFarm_Limited_report'),
                                                    y=year)

    def simple_operation(self,  result, values):
        """Generates a simple report of all operations

        Parameters
        ----------
        result: QgsTask.result
            Not used
        values: list
            if success:
                [True, dict]
            else:
                [False, message, tracback]"""
        if values[0] is False:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('Following error occurred: {m}\n\n Traceback: {t}'.format(m=values[1],
                                                                                                      t=values[2])))
            return
        operation_dict = values[1]
        cur_date = date.today().isoformat()
        growing_year = self.dw.DEReportYear.text()
        doc = MyDocTemplate(self.report_name, self.plugin_dir, growing_year, cur_date)
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
        """Generates a simple report of all operations listed by fields.

        Parameters
        ----------
        result: QgsTask.result
            Not used
        values: list
            if success:
                [True, dict]
            else:
                [False, message, tracback]
        """
        if values[0] is False:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('Following error occurred: {m}'.format(m=values[1])))
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

    @staticmethod
    def collect_data(task, data):
        """Collect data from the different schemas at the server and
        store them in a dict

        Parameters
        ----------
        task: QgsTask
        data: dict

        Returns
        -------
        list
            if success:
                [bool, dict]
            else:
                [bool, str, str]
        """
        data_dict = {'planting': {'simple': False, 'advanced': False},
                     'fertilizing': {'simple': False, 'advanced': False},
                     'spraying': {'simple': False, 'advanced': False},
                     'harvesting': {'simple': False, 'advanced': False},
                     'plowing': {'simple': False, 'advanced': False},
                     'harrowing': {'simple': False, 'advanced': False},
                     'soil': {'simple': False, 'advanced': False}
                     }

        def get_temp_ans(sql: str, list_: bool):
            temp_ans = data['db'].execute_and_return(sql, return_failure=True)
            if isinstance(temp_ans, str) or temp_ans[0] is False:
                return False
            if not list_:
                temp_ans = temp_ans[0][0]
            return temp_ans

        def get_data(dat: dict, schema: str):
            return_list = []
            if 'date' in dat.keys():
                if dat['date'][:2] == 'c_':
                    _date_ = dat['date'][2:]
                else:
                    sql = """ select array_agg(distinct({d}::date)) from {s}.{t}""".format(
                        d=dat['date'], t=dat['tbl'], s=schema)
                    if data['year'] is not None:
                        sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
                    _date_ = ''
                    temp_date = get_temp_ans(sql, True)
                    if temp_date is not None and temp_date:
                        for temp in temp_date:
                            _date_ += temp.isoformat() + ', '
                    _date_ = Paragraph(_date_[:-2], styleN)
                return_list.append(_date_)
            if 'variety' in dat.keys():
                if dat['variety'][:2] == 'c_':
                    _variety_ = dat['variety'][2:]
                elif dat['variety'] == 'None':
                    _variety_ = ''
                else:
                    sql = """ select array_agg(distinct({v})) from {s}.{t}""".format(v=dat['variety'],
                                                                                     t=dat['tbl'],
                                                                                     s=schema)
                    if data['year'] is not None:
                        sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
                    temp_var = get_temp_ans(sql, True)
                    if temp_var is not None and temp_var:
                        _variety_ = Paragraph(str(temp_var)[1:-1], styleN)
                    else:
                        _variety_ = ''
                return_list.append(_variety_)
            if 'field' in dat.keys():
                field = Paragraph(dat['field'], styleN)
                return_list.append(field)
            if 'crop' in dat.keys():
                crop = Paragraph(dat['crop'], styleN)
                return_list.append(crop)
            if 'rate' in dat.keys():
                if dat['rate'][:2] == 'c_':
                    _rate_ = dat['rate'][2:]
                elif dat['rate'] == 'None':
                    _rate_ = ''
                else:
                    sql = """ select array_agg(distinct({r})) from {s}.{t}""".format(r=dat['rate'],
                                                                                     t=dat['tbl'],
                                                                                     s=schema)
                    if data['year'] is not None:
                        sql += " where extract(year from date_) = {y}".format(y=data['year'])
                    temp_rate = get_temp_ans(sql, True)
                    if temp_rate is not None and temp_rate:
                        _rate_ = Paragraph(str(temp_rate)[1:-1], styleN)
                    else:
                        _rate_ = ''
                return_list.append(_rate_)
            if 'yield' in dat.keys():
                if dat['yield'][:2] == 'c_':
                    _yield_ = dat['yield'][2:]
                elif dat['yield'] == 'None':
                    _yield_ = ''
                else:
                    sql = " select round(avg({v})*100)/100::double precision from harvest.{t}".format(v=dat['yield'], t=dat['tbl'])
                    if data['year'] is not None:
                        sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
                    temp_yield = get_temp_ans(sql, False)
                    if temp_yield is not None and temp_yield:
                        _yield_ = Paragraph(str(temp_yield)[1:-1], styleN)
                    else:
                        _yield_ = ''
                return_list.append(_yield_)
            if 'total_yield' in dat.keys():
                if dat['total_yield'][:2] == 'c_':
                    _total_yield_ = dat['total_yield'][2:]
                elif dat['total_yield'] == 'None':
                    _total_yield_ = ''
                else:
                    sql = """ select round(avg({v})*100)/100::double precision from harvest.{t} """.format(
                        v=dat['total_yield'], t=table_)
                    if data['year'] is not None:
                        sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
                    temp_t_yield = get_temp_ans(sql, False)
                    if temp_t_yield is not None and temp_t_yield:
                        _total_yield_ = Paragraph(str(temp_t_yield)[1:-1], styleN)
                    else:
                        _total_yield_ = ''
                return_list.append(_total_yield_)
            if 'clay' in dat.keys():
                if dat['clay'][:2] == 'c_':
                    _clay_ = dat['clay'][2:]
                elif dat['clay'] == 'None':
                    _clay_ = ''
                else:
                    sql = """ select round(avg({v})*100)/100::double precision 
                    from {s}.{t}""".format(v=dat['clay'], t=dat['tbl'], s=schema)
                    if data['year'] is not None:
                        sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
                    temp_clay = get_temp_ans(sql, False)
                    if temp_clay is not None and temp_clay:
                        _clay_ = Paragraph(str(temp_clay), styleN)
                    else:
                        _clay_ = ''
                return_list.append(_clay_)
            if 'humus' in dat.keys():
                if dat['humus'][:2] == 'c_':
                    _humus_ = dat['humus'][2:]
                elif dat['humus'] == 'None':
                    _humus_ = ''
                else:
                    sql = """ select round(avg({r})*100)/100::double precision 
                    from {s}.{t}""".format(r=dat['humus'], t=dat['tbl'], s=schema)
                    if data['year'] is not None:
                        sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
                    temp_hum = get_temp_ans(sql, False)
                    if temp_hum is not None and temp_hum:
                        _humus_ = Paragraph(str(temp_hum), styleN)
                    else:
                        _humus_ = ''
                return_list.append(_humus_)
            if 'ph' in dat.keys():
                if dat['ph'][:2] == 'c_':
                    _ph_ = dat['ph'][2:]
                elif dat['ph'] == 'None':
                    _ph_ = ''
                else:
                    sql = """ select round(avg({r})*100)/100::double precision from {s}.{t}""".format(
                        r=dat['ph'], t=dat['tbl'], s=schema)
                    if data['year'] is not None:
                        sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
                    temp_ph = get_temp_ans(sql, False)
                    if temp_ph is not None and temp_ph:
                        _ph_ = Paragraph(str(temp_ph), styleN)
                    else:
                        _ph_ = ''
                return_list.append(_ph_)
            if 'rx' in dat.keys():
                if dat['rx'][:2] == 'c_':
                    _rx_ = dat['rx'][2:]
                elif dat['rx'] == 'None':
                    _rx_ = ''
                else:
                    sql = """ select round(avg({r})*100)/100::double precision from {s}.{t} """.format(
                        r=dat['rx'], t=dat['tbl'], s=schema)
                    if data['year'] is not None:
                        sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
                    temp_rx = get_temp_ans(sql, False)
                    if temp_rx is not None and temp_rx:
                        _rx_ = Paragraph(str(temp_rx), styleN)
                    else:
                        _rx_ = ''
                return_list.append(_rx_)

            return return_list
        try:
            # Planting
            if task != 'debug':
                task.setProgress(5)
            sql = """select date_, field, crop, variety from plant.manual 
            where table_ = 'None' """
            if data['year'] is not None:
                sql += """and extract(year from date_) = {y}""".format(y=data['year'])
            simple_plant_data = data['db'].execute_and_return(sql)
            if len(simple_plant_data) > 0:
                simple_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Crop'), data['tr']('Variety')]
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
            if data['year'] is not None:
                sql += """ and extract(year from date_) = {y} or date_text like '%{y}%'""".format(
                    y=data['year'])
            planting_data_advanced = data['db'].execute_and_return(sql)
            if len(planting_data_advanced) > 0:
                adv_data = []
                for date_, field, crop, variety, table_ in planting_data_advanced:
                    dat = {'date': date_, 'field': field, 'crop': crop, 'variety': variety,
                           'tbl': table_}
                    [_date_, field, crop, _variety_] = get_data(dat, 'plant')
                    adv_data.append([_date_, field, crop, _variety_])
                if len(adv_data) > 0:
                    adv_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Crop'), data['tr']('Variety')]
                    data_dict['planting']['advanced'] = True
                    data_dict['planting']['advance_dat'] = adv_data
                    data_dict['planting']['adv_heading'] = adv_heading
            sql = """select date_, field, crop, variety, rate from ferti.manual 
            where table_ = 'None' """
            if data['year'] is not None:
                sql += """ and extract(year from date_) = {y} or date_text like '%{y}%'""".format(
                    y=data['year'])
            # Fertilizing
            if task != 'debug':
                task.setProgress(15)
            simple_ferti_data = data['db'].execute_and_return(sql)
            if len(simple_ferti_data) > 0:
                simple_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Crop'), data['tr']('Variety'), data['tr']('Rate')]
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
            if data['year'] is not None:
                sql += """ and extract(year from date_) = {y} or date_text like '%{y}%'""".format(y=data['year'])
            fertilizing_data_advanced = data['db'].execute_and_return(sql)
            if len(fertilizing_data_advanced) > 0:
                adv_data = []
                for date_, field, crop, variety, rate, table_ in fertilizing_data_advanced:
                    dat = {'date': date_, 'field': field, 'crop': crop, 'variety': variety,
                           'tbl': table_, 'rate': rate}
                    [_date_, field, crop, _variety_, rate_] = get_data(dat, 'ferti')
                    adv_data.append([_date_, field, crop, _variety_, rate_])
                if len(adv_data) > 0:
                    adv_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Crop'), data['tr']('Variety'), data['tr']('Rate')]
                    data_dict['fertilizing']['advanced'] = True
                    data_dict['fertilizing']['advance_dat'] = adv_data
                    data_dict['fertilizing']['adv_heading'] = adv_heading
            # Spraying
            if task != 'debug':
                task.setProgress(25)
            sql = """select date_, field, crop, variety, rate from spray.manual 
            where table_ = 'None' """
            if data['year'] is not None:
                sql += """ and extract(year from date_) = {y} or date_text like '%{y}%'""".format(
                    y=data['year'])
            simple_data = data['db'].execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Crop'), data['tr']('Variety'), data['tr']('Rate')]
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
            spraying_data_advanced = data['db'].execute_and_return(sql)
            if data['year'] is not None:
                sql += """ and extract(year from date_) = {y}""".format(y=data['year'])
            if len(spraying_data_advanced) > 0:
                adv_data = []
                for date_, field, crop, variety, rate, table_ in spraying_data_advanced:
                    dat = {'date': date_, 'field': field, 'crop': crop, 'variety': variety,
                           'tbl': table_, 'rate': rate}
                    [_date_, field, crop, _variety_, rate_] = get_data(dat, 'spray')
                    adv_data.append([_date_, field, crop, _variety_, rate_])
                if len(adv_data) > 0:
                    adv_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Crop'), data['tr']('Variety'), data['tr']('Rate')]
                    data_dict['spraying']['advanced'] = True
                    data_dict['spraying']['advance_dat'] = adv_data
                    data_dict['spraying']['adv_heading'] = adv_heading
            #Harvest
            if task != 'debug':
                task.setProgress(35)
            sql = """select date_, field, crop, total_yield, yield from harvest.manual 
            where table_ = 'None' """
            if data['year'] is not None:
                sql += """and extract(year from date_) = {y}""".format(y=data['year'])
            simple_data = data['db'].execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Crop'), data['tr']('Total yield'), data['tr']('Yield (kg/ha)')]
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
            if data['year'] is not None:
                sql += """ and extract(year from date_) = {y} or date_text like '%{y}%'""".format(
                    y=data['year'])
            data_advanced = data['db'].execute_and_return(sql)
            if len(data_advanced) > 0:
                adv_data = []
                for date_, field, crop, yield_, total_yield, table_ in data_advanced:
                    dat = {'date': date_, 'field': field, 'crop': crop, 'yield': yield_,
                           'tbl': table_, 'total_yield': total_yield}
                    [_date_, field, crop, _yield_, _total_yield_] = get_data(dat, 'harvest')
                    adv_data.append([_date_, field, crop, _yield_, _total_yield_])
                if len(adv_data) > 0:
                    adv_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Crop'), data['tr']('Yield (kg/ha)'), data['tr']('Total Yield')]
                    data_dict['harvesting']['advanced'] = True
                    data_dict['harvesting']['advance_dat'] = adv_data
                    data_dict['harvesting']['adv_heading'] = adv_heading
            # Plowing
            if task != 'debug':
                task.setProgress(50)
            sql = """select date_, field, depth from other.plowing_manual"""
            if data['year'] is not None:
                sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
            simple_data = data['db'].execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Depth')]
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
            if data['year'] is not None:
                sql += """ where extract(year from date_) = {y}""".format(y=data['year'])
            simple_data = data['db'].execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Depth')]
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
            if data['year'] is not None:
                sql += """and extract(year from date_) = {y}""".format(y=data['year'])
            simple_data = data['db'].execute_and_return(sql)
            if len(simple_data) > 0:
                simple_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Clay'), data['tr']('Humus'), data['tr']('pH'), data['tr']('rx')]
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
            if data['year'] is not None:
                sql += """ and extract(year from date_) = {y} or date_text like '%{y}%'""".format(
                    y=data['year'])
            data_advanced = data['db'].execute_and_return(sql)
            if len(data_advanced) > 0:
                adv_data = []
                for date_, field, clay, humus, ph, rx, table_ in data_advanced:
                    dat = {'date': date_, 'field': field, 'crop': clay, 'humus': humus,
                           'tbl': table_, 'rx': rx, 'ph': ph}
                    [_date_, field, _clay_, _humus_, _ph_, _rx_] = get_data(dat, 'harvest')
                    adv_data.append([_date_, field, _clay_, _humus_, _ph_, _rx_])
                adv_heading = [data['tr']('Date'), data['tr']('Field'), data['tr']('Clay'), data['tr']('Humus'), data['tr']('pH'), data['tr']('rx')]
                data_dict['soil']['advanced'] = True
                data_dict['soil']['advance_dat'] = adv_data
                data_dict['soil']['adv_heading'] = adv_heading
            if task != 'debug':
                task.setProgress(95)
            return [True, data_dict]
        except Exception as e:
            return [False, e, traceback.format_exc()]
