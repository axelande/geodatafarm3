import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas)
import matplotlib.colors as mplib_colors
import numpy as np
import time
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QThread
from ..widgets.run_analyse import RunAnalyseDialog
from ..widgets.waiting import Waiting
from ..support_scripts.__init__ import isfloat, isint

__author__ = 'Axel Andersson'


# import pydevd
# pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)
class Analyze:
    def __init__(self, parent_widget, tables_to_analyse):
        """
        A widget that analyses the data in the database
        :param parent_widget: the docked widget
        :param tables_to_analyse: list of list schemas and tables that should 
        be included in the analyse
        :return:
        """
        self.dlg = RunAnalyseDialog()
        self.db = parent_widget.DB
        self.harvest_tables = {}
        self.activity_tables = {}
        self.soil_tables = {}
        self.tables = tables_to_analyse
        self.cb = []
        self.max_min_checked = {}
        self.harvest_tbls = {}
        self.dlg.pButRun.clicked.connect(self.run_update)
        self.scrollWidget = QtWidgets.QWidget()
        self.radio_group = QtWidgets.QButtonGroup()
        self.overlapping_tables = {}
        self.top_right_panel = []
        # self.populate_list(parameters)
        self.finish = False
        self.canvas = None

    def run(self):
        """
        Starts this widget
        :return:
        """
        self.dlg.show()
        self.dlg.exec_()

    def run_update(self):
        self.update_pic()

        # TODO: Fix threading
        # self.next_thread = QThread()
        # self.next_thread.started.connect(self.update_pic)
        # self.next_thread.start()
        # waiting_thread = QThread()
        # waiting_thread.start()
        # wait_msg = 'Please wait while data is being prosecuted'
        # self.wait = Waiting(wait_msg)
        # self.wait.moveToThread(waiting_thread)
        # self.wait.start.connect(self.wait.start_work)
        # self.wait.start.emit('run')
        # while not self.finish:
        #    time.sleep(1)
        # self.wait.stop_work()
        # self.next_thread.join()

    def check_consistency(self):
        """Checks that the harvest tables is intersecting some of the input data
        If the data is an activity does it also check that the year is the same
        """
        self.fill_dict_tables()
        self.overlapping_tables = {}
        overlapping = -1
        for ha in self.harvest_tables.keys():
            ha_year = self.db.execute_and_return("""select year from harvest.{tbl} 
                        limit 1""".format(
                tbl=self.harvest_tables[ha][0]['tbl_name']))[0][0]
            if len(self.activity_tables) > 0:
                for ac in self.activity_tables.keys():
                    ac_year = self.db.execute_and_return("""select year from activity.{tbl} 
                                limit 1""".format(
                        tbl=self.activity_tables[ac][0]['tbl_name']))[0][0]
                    if ac_year == ha_year:
                        sql = """select st_intersects(a.geom, b.geom) from 
                        (select st_extent(ac.polygon) geom from activity.{a_tbl} ac) a,
                        (select st_extent(ha.pos) geom from harvest.{h_tbl} ha) b
                        """.format(
                            a_tbl=self.activity_tables[ac][0]['tbl_name'],
                            h_tbl=self.harvest_tables[ha][0]['tbl_name'])
                        overlaps = self.db.execute_and_return(sql)[0][0]
                        if overlaps:
                            overlapping += 1
                            self.overlapping_tables[overlapping] = {}
                            for ha_key in self.harvest_tables[ha].keys():
                                if 'pkey' in self.harvest_tables[ha][ha_key][
                                    'index_name']:
                                    continue
                                self.overlapping_tables[overlapping]['ha'] = \
                                self.harvest_tables[ha][ha_key]
                            self.overlapping_tables[overlapping]['ac'] = []
                            for ac_key in self.activity_tables[ac].keys():
                                if 'pkey' in self.activity_tables[ac][ac_key][
                                    'index_name']:
                                    continue
                                self.overlapping_tables[overlapping][
                                    'ac'].append(
                                    self.activity_tables[ac][ac_key])

            if len(self.soil_tables) > 0:
                for so in self.soil_tables.keys():
                    sql = """select st_intersects(a.geom, b.geom) from 
                    (select st_extent(ac.polygon) geom from soil.{s_tbl} ac) a,
                    (select st_extent(ha.pos) geom from harvest.{h_tbl} ha) b
                    """.format(s_tbl=self.soil_tables[so][0]['tbl_name'],
                               h_tbl=self.harvest_tables[ha][0]['tbl_name'])
                    overlaps = self.db.execute_and_return(sql)[0][0]
                    if overlaps:
                        overlapping += 1
                        self.overlapping_tables[overlapping]['ha'] = \
                        self.harvest_tables[ha]
                        self.overlapping_tables[overlapping]['so'] = \
                        self.soil_tables[so]

    def fill_dict_tables(self):
        """Filles the three dict tables"""
        for i, (schema, table) in enumerate(self.tables):
            if schema == 'harvest':
                self.harvest_tables[i] = self.db.get_indexes(table, schema)
            if schema == 'activity':
                self.activity_tables[i] = self.db.get_indexes(table, schema)
            if schema == 'soil':
                self.soil_tables[i] = self.db.get_indexes(table, schema)

    def get_initial_distinct_values(self, parameter_to_eval, tbl, schema):
        """
        Calls the database and gets distinct values
        :param parameter_to_eval: list, What parameter to eval
        :param tbl: list, In what table is the param located
        :param schema: list, In what schema
        :return: analyse_params{'distinct_values':[],'distinct_count':[]}
        """
        analyse_params = {}
        temp1 = []
        temp2 = []
        for i, table in enumerate(tbl):
            distinct = self.db.get_distinct(table, parameter_to_eval, schema[i])
            for value, count in distinct:
                temp1.append(value)
                temp2.append(count)
        analyse_params['distinct_values'] = temp1
        analyse_params['distinct_count'] = temp2
        return analyse_params

    def _set_checkbox_layout(self, qbox, analyse_params, col, nbr):
        self.max_min_checked[col]['type'] = 'checked'
        self.max_min_checked[col]['checked'] = []
        self.max_min_checked[col]['checked_items'] = []
        names = analyse_params['distinct_values']
        model = QtGui.QStandardItemModel(len(names), 1)
        firstItem = QtGui.QStandardItem("---- Select ----")
        firstItem.setBackground(QtGui.QBrush(QtGui.QColor(200, 200, 200)))
        firstItem.setSelectable(False)
        model.setItem(0, 0, firstItem)
        name_text = ''
        for i, name in enumerate(names):
            item = QtGui.QStandardItem(name)
            name_text += name + ' '
            item.setFlags(
                QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            item.setData(QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
            self.max_min_checked[col]['checked'].append(name)
            self.max_min_checked[col]['checked_items'].append(item)
            model.setItem(i + 1, 0, item)
        param_label = QtWidgets.QLabel(name_text, self.top_right_panel[nbr])
        param_label.move(10, 20)
        QComb = QtWidgets.QComboBox(qbox)
        QComb.setModel(model)
        QComb.move(83, 34)
        self.max_min_checked[col]['model'] = model
        self.max_min_checked[col]['name_text'] = name_text
        self.max_min_checked[col]['param_label'] = param_label

    def _set_number_layout(self, qbox, analyse_params, col, nbr):
        QtWidgets.QLabel('Min:', qbox).move(83, 34)
        min_value = QtWidgets.QLineEdit(
            str(np.nanmin(analyse_params['distinct_values'])), qbox)
        min_value.move(108, 32)
        QtWidgets.QLabel(
            '({v})'.format(v=str(np.nanmin(analyse_params['distinct_values']))),
            qbox).move(112, 15)
        QtWidgets.QLabel('Max:', qbox).move(263, 34)
        max_value = QtWidgets.QLineEdit(
            str(np.nanmax(analyse_params['distinct_values'])), qbox)
        max_value.move(288, 32)
        QtWidgets.QLabel(
            '({v})'.format(v=str(np.nanmax(analyse_params['distinct_values']))),
            qbox).move(292, 15)
        self.max_min_checked[col]['type'] = 'max_min'
        self.max_min_checked[col]['min'] = np.nanmin(
            analyse_params['distinct_values'])
        self.max_min_checked[col]['min_text'] = min_value
        self.max_min_checked[col]['max'] = np.nanmax(
            analyse_params['distinct_values'])
        self.max_min_checked[col]['max_text'] = max_value
        if isfloat(max_value.text()):
            param_label = QtWidgets.QLabel('Min: ' + str(
                round(float(min_value.text()), 2)) + ' Max: ' + str(
                round(float(max_value.text()), 2)), self.top_right_panel[nbr])
        else:
            param_label = QtWidgets.QLabel(
                'Min: ' + str(min_value.text()) + ' Max: ' + str(
                    max_value.text()), self.top_right_panel[nbr])
        param_label.move(10, 20)

    def _update_max_min(self, analyse_params, col):
        if self.max_min_checked[col]['type'] == 'max_min':
            if self.max_min_checked[col]['min'] > np.nanmin(
                    analyse_params['distinct_values']):
                self.max_min_checked[col]['min'] = np.nanmin(
                    analyse_params['distinct_values'])
                self.max_min_checked[col]['min_text'].setText(
                    str(np.nanmin(analyse_params['distinct_values'])))
            if self.max_min_checked[col]['max'] < np.nanmax(
                    analyse_params['distinct_values']):
                self.max_min_checked[col]['max'] = np.nanmax(
                    analyse_params['distinct_values'])
                self.max_min_checked[col]['max_text'].setText(
                    str(np.nanmax(analyse_params['distinct_values'])))
        else:
            names = analyse_params['distinct_values']
            name_text = self.max_min_checked[col]['name_text']
            model = self.max_min_checked[col]['model']
            param_label = self.max_min_checked[col]['param_label'] = param_label
            i = model.rowCount()
            for name in names:
                if name in name_text:
                    continue
                i += 1
                item = QtGui.QStandardItem(name)
                name_text += name + ' '
                item.setFlags(
                    QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
                item.setData(QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
                self.max_min_checked[col]['checked'].append(name)
                self.max_min_checked[col]['checked_items'].append(item)
                model.setItem(i, 0, item)
            param_label.setText(name_text)
            self.max_min_checked[col]['model'] = model
            self.max_min_checked[col]['name_text'] = name_text
            self.max_min_checked[col]['param_label'] = param_label

    def default_layout(self):
        """
        Creating the layout, (the UI file only contains the plotting area).
        This function adds parameters names and default value both in a scroll 
        area bellow and to the right of the drawing area.
        :return:
        """
        colors = ['green', 'blue', 'red']
        for key in mplib_colors.cnames.keys():
            colors.append(key)
        scroll_area_layout = QtWidgets.QVBoxLayout()
        constranint_area = QtWidgets.QWidget()
        constranint_layout = QtWidgets.QVBoxLayout()
        first_radio = True
        first_param = True
        harvest_nbr = 0
        nbr = -1
        # Looping over all sets of overlapping data for each harvest table
        for key in self.overlapping_tables.keys():
            self.harvest_tbls[harvest_nbr] = {}
            self.harvest_tbls[harvest_nbr]['column'] = \
            self.overlapping_tables[key]['ha']['index_col']
            self.harvest_tbls[harvest_nbr]['tbl'] = \
            self.overlapping_tables[key]['ha']['tbl_name']
            harvest_nbr += 1
            defining_tlbs = []
            if 'ac' in self.overlapping_tables[key].keys():
                act_keys = range(len(self.overlapping_tables[key]['ac']))
                for k in act_keys:
                    defining_tlbs.append(['ac', k])
            if 'so' in self.overlapping_tables[key].keys():
                soil_keys = range(len(self.overlapping_tables[key]['so']))
                for k in soil_keys:
                    defining_tlbs.append(['so', k])
            # Looping over all sub sets of data
            for sch, tbl_k in defining_tlbs:
                table = self.overlapping_tables[key][sch][tbl_k]
                analyse_params = self.get_initial_distinct_values(
                    self.overlapping_tables[key][sch][tbl_k]['index_col'],
                    [self.overlapping_tables[key][sch][tbl_k]['tbl_name']],
                    [self.overlapping_tables[key][sch][tbl_k]['schema']])
                if table['index_col'] in self.max_min_checked.keys():
                    self._update_max_min(analyse_params, table['index_col'])
                    self.max_min_checked[table['index_col']]['tbl'].append(
                        table['tbl_name'])
                    self.max_min_checked[table['index_col']]['schema'].append(
                        table['schema'])
                    self.max_min_checked[table['index_col']]['harvest'].append(
                        self.overlapping_tables[key]['ha'])
                else:
                    nbr += 1
                    self.max_min_checked[table['index_col']] = {'tbl': [],
                                                                'schema': [],
                                                                'harvest': []}
                    self.max_min_checked[table['index_col']]['tbl'].append(
                        table['tbl_name'])
                    self.max_min_checked[table['index_col']]['schema'].append(
                        table['schema'])
                    self.max_min_checked[table['index_col']]['harvest'].append(
                        self.overlapping_tables[key]['ha'])
                    ## set top right data basic data
                    self.top_right_panel.append(QtWidgets.QGroupBox())
                    self.top_right_panel[nbr].setMinimumSize(
                        QtCore.QSize(30, 35))
                    self.top_right_panel[nbr].setStyleSheet("border:0px;")
                    param_label = QtWidgets.QLabel(
                        table['index_col'].replace('_', ' '),
                        self.top_right_panel[nbr])
                    param_label.move(10, 5)
                    constranint_layout.addWidget(self.top_right_panel[nbr])

                    ## Set bottom group basic data
                    qbox = QtWidgets.QGroupBox()
                    qbox.setTitle(table['index_col'].replace('_', ' '))
                    qbox.setMinimumSize(QtCore.QSize(100, 55))
                    qbox.setStyleSheet('QWidget{color:' + colors[nbr] + '}')
                    scroll_area_layout.addWidget(qbox)
                    QtWidgets.QLabel('Show:', qbox).move(10, 15)
                    QtWidgets.QLabel('Limit:', qbox).move(50, 34)

                    self.cb.append(QtWidgets.QRadioButton('', qbox))
                    if first_radio:
                        self.cb[nbr].setChecked(True)
                        first_radio = False
                    else:
                        self.cb[nbr].setChecked(False)
                    self.radio_group.addButton(self.cb[nbr], nbr)
                    self.cb[nbr].move(15, 34)
                    if isint(analyse_params['distinct_values'][0]) or isfloat(
                            analyse_params['distinct_values'][0]):
                        self._set_number_layout(qbox, analyse_params,
                                                table['index_col'], nbr)
                    else:
                        self._set_checkbox_layout(qbox, analyse_params,
                                                  table['index_col'], nbr)

        constranint_area.setLayout(constranint_layout)
        self.dlg.groupBoxConstraints.setWidget(constranint_area)
        self.scrollWidget.setLayout(scroll_area_layout)
        self.dlg.paramArea.setWidget(self.scrollWidget)
        self.update_pic()

    def update_checked_field(self, other_parameters, main_investigate_col):
        """Updates the parameters listed as checked in max_min_checked
        :param other_parameters: dict"""
        added_texts = []
        for key in self.max_min_checked.keys():
            if self.max_min_checked[key]['type'] == 'checked':
                for item in self.max_min_checked[key]['checked_items']:
                    if item.checkState() == 0 and item.text() in \
                            self.max_min_checked[key]['checked']:
                        self.max_min_checked[key]['checked'].remove(item.text())
                    if item.checkState() == 2 and item.text() not in \
                            self.max_min_checked[key]['checked']:
                        self.max_min_checked[key]['checked'].append(item.text())
                    if item.text() in added_texts:
                        continue
                    if key != main_investigate_col:
                        if key in other_parameters['check_text'].keys():
                            other_parameters['check_text'][
                                key] += item.text() + ', '
                            added_texts.append(item.text())
                        else:
                            other_parameters['check_text'][
                                key] = item.text() + ', '
                            added_texts.append(item.text())
                other_parameters['check_text'][key] = \
                other_parameters['check_text'][key][:-2]
        return other_parameters

    def update_pic(self):
        """
        Updates the diagram with a parameters and limits
        :return:
        """
        if self.canvas is not None:
            self.dlg.mplvl.removeWidget(self.canvas)
        other_parameters = {'schema': [],
                            'tbl': [],
                            'col': [],
                            'type': [],
                            'min': {},
                            'max': {},
                            'check_text': {}}
        for nbr, col in enumerate(self.max_min_checked.keys()):
            ## Update the top right panel with the data
            if self.max_min_checked[col]['type'] == 'max_min':
                self.max_min_checked[col]['min'] = self.max_min_checked[col][
                    'min_text'].text()
                self.max_min_checked[col]['max'] = self.max_min_checked[col][
                    'max_text'].text()
                if isfloat(self.max_min_checked[col]['max']):
                    self.top_right_panel[nbr].children()[1].setText(
                        'Min: ' + str(
                            round(float(self.max_min_checked[col]['min']),
                                  2)) + ' Max: ' + str(
                            round(float(self.max_min_checked[col]['max']), 2)))
                else:
                    self.top_right_panel[nbr].children()[1].setText(
                        'Min: ' + str(
                            self.max_min_checked[col]['min']) + ' Max: ' + str(
                            self.max_min_checked[col]['max']))
            else:
                text = ''
                for name in self.max_min_checked[col]['checked']:
                    text += name + ' '
                text = text[:-1]
                self.top_right_panel[nbr].children()[1].setText(text)
            if self.cb[nbr].isChecked():
                investigating_param = {}
                investigating_param['tbl'] = self.max_min_checked[col]['tbl']
                investigating_param['schema'] = self.max_min_checked[col][
                    'schema']
                investigating_param['col'] = col
                analyse_params = self.get_initial_distinct_values(col,
                                                                  self.max_min_checked[
                                                                      col][
                                                                      'tbl'],
                                                                  self.max_min_checked[
                                                                      col][
                                                                      'schema'])
                if len(analyse_params['distinct_values']) > 20:
                    investigating_param['hist'] = True
                    investigating_param['values'] = []
                    for val in range(0, len(analyse_params['distinct_values']),
                                     int(round(len(analyse_params[
                                                       'distinct_values']) / 20))):
                        investigating_param['values'].append(
                            analyse_params['distinct_values'][val])
                    investigating_param['values'].append(
                        analyse_params['distinct_values'][-1])
                else:
                    investigating_param['hist'] = False
                    investigating_param['values'] = analyse_params[
                        'distinct_values']
                if self.max_min_checked[col]['type'] != 'checked':
                    minvalue = float(self.max_min_checked[col]['min'])
                    maxvalue = float(self.max_min_checked[col]['max'])
                    for value in investigating_param['values']:
                        if round(value, 3) < minvalue or round(value,
                                                               3) > maxvalue:
                            investigating_param['values'].remove(value)
                else:
                    # This is solved for the text cases in update_checked_field,
                    # which is called later on
                    pass
            else:
                other_parameters['schema'].append(
                    self.max_min_checked[col]['schema'])
                other_parameters['tbl'].append(self.max_min_checked[col]['tbl'])
                other_parameters['col'].append(col)
                if self.max_min_checked[col]['type'] == 'max_min':
                    other_parameters['type'].append('max_min')
                    other_parameters['min'][col] = self.max_min_checked[col][
                        'min']
                    other_parameters['max'][col] = self.max_min_checked[col][
                        'max']
                else:
                    other_parameters['type'].append('checked')
        other_parameters = self.update_checked_field(other_parameters,
                                                     investigating_param['col'])
        filter = self.get_filter_text(investigating_param, other_parameters)
        fig, ax1 = plt.subplots()
        ax1.plot(filter[1], filter[0], color='green')
        ax1.yaxis.label.set_color('green')
        ax1.set_xlabel(investigating_param['col'].replace('_', ' '))
        ax1.set_ylabel('mean yield (kg/ha)')
        ax2 = ax1.twinx()
        ax2.plot(filter[1], filter[2], 'x', color='blue')
        ax2.yaxis.label.set_color('blue')
        ax2.set_ylabel('Number of harvest samples')
        plt.subplots_adjust(wspace=0.6, hspace=0.6, left=0.17, bottom=0.12,
                            right=0.85, top=0.92)
        self.canvas = FigureCanvas(fig)
        self.dlg.mplvl.addWidget(self.canvas)
        self.canvas.draw()
        self.finish = True

    def get_filter_text(self, investigating_param, other_paramameters):
        """
        Writes the sql question
        :param investigating_param: What parameter to put on the x-axis
        :return: a diagram over the mean yield
        """
        ## TODO enable the possibility to have more than one harvest table
        # self.max_min_checked[nbr]['type'] = 'checked'
        harvest_tables = []
        for table in investigating_param['tbl']:
            for key in self.overlapping_tables.keys():
                if 'ac' in self.overlapping_tables[key].keys():
                    for i in range(
                            self.overlapping_tables[key]['ac'].__len__()):
                        if self.overlapping_tables[key]['ac'][i][
                            'tbl_name'] == table:
                            harvest_tables.append(
                                self.overlapping_tables[key]['ha'])
                            break
                if 'so' in self.overlapping_tables[key].keys():
                    for i in range(
                            self.overlapping_tables[key]['so'].__len__()):
                        if self.overlapping_tables[key]['so'][i][
                            'tbl_name'] == table:
                            harvest_tables.append(
                                self.overlapping_tables[key]['ha'])
                            break
        min_counts = self.dlg.minNumber.text()
        results = sql_queary(1, investigating_param, harvest_tables,
                             other_paramameters, self.db, min_counts)
        return results


def sql_queary(task, investigating_param, harvest_tables, other_parameters, db,
               min_counts):
    mean_yields = [[], [], []]
    values = investigating_param['values']
    values.sort()
    for value_nbr, value in enumerate(values):
        if investigating_param['hist'] and value_nbr == 0:
            continue
        all_ready_joined = {}
        sql = 'with harvest_tables as('
        for ha_table in harvest_tables:
            sql += """SELECT {col} as yield, pos
            FROM harvest.{tbl} \nUNION\n""".format(col=ha_table['index_col'],
                                                   tbl=ha_table['tbl_name'])
        sql = sql[:-6] + ')\n'
        sql += """select avg(yield), count(*) from harvest_tables ha\n"""
        nbr = 0
        for i, col in enumerate(other_parameters['col']):
            for j, tbl in enumerate(other_parameters['tbl'][i]):
                nbr += 1
                sql += """join {schema}.{new_tbl} a{nbr} on st_intersects(ha.pos, a{nbr}.polygon)
                """.format(schema=other_parameters['schema'][i][j],
                           new_tbl=tbl, nbr=nbr)
        sql = sql[:-5]
        for i, tabel in enumerate(investigating_param['tbl']):
            sql += """join {schema}.{tbl} b{nbr2} on st_intersects(ha.pos, b{nbr2}.polygon)
            """.format(schema=investigating_param['schema'][i], tbl=tbl,
                       nbr2=i + 1)
        sql += "where "
        nbr = 0
        for i, col in enumerate(other_parameters['col']):
            for j, tbl in enumerate(other_parameters['tbl'][i]):
                nbr += 1
                if other_parameters['type'][i] == 'checked':
                    sql += "a{nbr}.{col} in ('{text}') and\n".format(nbr=nbr,
                                                                     col=col,
                                                                     text=
                                                                     other_parameters[
                                                                         'check_text'][
                                                                         col])
                else:
                    sql += 'a{nbr}.{col} >= {min} and\n'.format(nbr=nbr,
                                                                col=col,
                                                                text=
                                                                other_parameters[
                                                                    'min'][col])
                    sql += 'a{nbr}.{col} <= {max} and\n'.format(nbr=nbr,
                                                                col=col,
                                                                text=
                                                                other_parameters[
                                                                    'max'][col])
        for i, tabel in enumerate(investigating_param['tbl']):
            if investigating_param['hist']:
                sql += "b{nbr2}.{col} >= {min} and\n".format(nbr2=i + 1,
                                                             col=
                                                             investigating_param[
                                                                 'col'],
                                                             min=
                                                             investigating_param[
                                                                 'values'][
                                                                 value_nbr - 1])
                sql += "b{nbr2}.{col} <= {max} and\n".format(nbr2=i + 1,
                                                             col=
                                                             investigating_param[
                                                                 'col'],
                                                             max=value)
            elif not isint(value) and not isfloat(value):
                sql += """b{nbr2}.{col} = '{val}' and\n""".format(
                    nbr2=i + 1, col=investigating_param['col'],
                    val=value)
            else:
                sql += """b{nbr2}.{col} = {val} and\n""".format(
                    nbr2=i + 1, col=investigating_param['col'],
                    _val=value)
        # print(sql)
        sql = sql[:-4]
        result = db.execute_and_return(sql)[0]
        mean_value = result[0]
        count_samples = result[1]
        if count_samples <= int(min_counts):
            continue
        if investigating_param['hist']:
            value = (value + investigating_param['values'][value_nbr - 1]) / 2
        mean_yields[0].append(mean_value)
        mean_yields[1].append(value)
        mean_yields[2].append(count_samples)
    return mean_yields