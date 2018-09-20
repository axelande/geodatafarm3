from qgis.core import QgsTask
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas)
import matplotlib.colors as mplib_colors
import numpy as np
import time
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QThread
from ..widgets.run_analyse import RunAnalyseDialog
from ..support_scripts.__init__ import isfloat, isint
import copy
__author__ = 'Axel Andersson'


#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)
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
        self.db = parent_widget.db
        self.tsk_mngr = parent_widget.tsk_mngr
        self.harvest_tables = {}
        self.plant_tables = {}
        self.spray_tables = {}
        self.ferti_tables = {}
        self.soil_tables = {}
        self.tables = tables_to_analyse
        self.cb = []
        self.harvest_tbls = {}
        self.dlg.pButRun.clicked.connect(self.run_update)
        self.scrollWidget = QtWidgets.QWidget()
        self.radio_group = QtWidgets.QButtonGroup()
        self.overlapping_tables = {}
        self.layout_dict = {}
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
            ha_year = self.db.execute_and_return("""select extract(year from date_) from harvest.{tbl} 
                        limit 1""".format(
                tbl=self.harvest_tables[ha][0]['tbl_name']))[0][0]
            if len(self.plant_tables) > 0:
                for ac in self.plant_tables.keys():
                    ac_year = self.db.execute_and_return("""select extract(year from date_) from plant.{tbl} 
                                limit 1""".format(
                        tbl=self.plant_tables[ac][0]['tbl_name']))[0][0]
                    if ac_year == ha_year:
                        sql = """select st_intersects(a.geom, b.geom) from 
                        (select st_extent(ac.polygon) geom from plant.{a_tbl} ac) a,
                        (select st_extent(ha.pos) geom from harvest.{h_tbl} ha) b
                        """.format(
                            a_tbl=self.plant_tables[ac][0]['tbl_name'],
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
                            for ac_key in self.plant_tables[ac].keys():
                                if 'pkey' in self.plant_tables[ac][ac_key][
                                    'index_name']:
                                    continue
                                self.overlapping_tables[overlapping][
                                    'ac'].append(
                                    self.plant_tables[ac][ac_key])
            if len(self.spray_tables) > 0:
                for ac in self.spray_tables.keys():
                    ac_year = self.db.execute_and_return("""select extract(year from date_) from spray.{tbl} 
                                limit 1""".format(
                        tbl=self.spray_tables[ac][0]['tbl_name']))[0][0]
                    if ac_year == ha_year:
                        sql = """select st_intersects(a.geom, b.geom) from 
                        (select st_extent(ac.polygon) geom from spray.{a_tbl} ac) a,
                        (select st_extent(ha.pos) geom from harvest.{h_tbl} ha) b
                        """.format(
                            a_tbl=self.spray_tables[ac][0]['tbl_name'],
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
                            for ac_key in self.spray_tables[ac].keys():
                                if 'pkey' in self.spray_tables[ac][ac_key][
                                    'index_name']:
                                    continue
                                self.overlapping_tables[overlapping][
                                    'ac'].append(
                                    self.spray_tables[ac][ac_key])
            if len(self.ferti_tables) > 0:
                for ac in self.ferti_tables.keys():
                    ac_year = self.db.execute_and_return("""select extract(year from date_) from ferti.{tbl} 
                                limit 1""".format(
                        tbl=self.ferti[ac][0]['tbl_name']))[0][0]
                    if ac_year == ha_year:
                        sql = """select st_intersects(a.geom, b.geom) from 
                        (select st_extent(ac.polygon) geom from ferti.{a_tbl} ac) a,
                        (select st_extent(ha.pos) geom from harvest.{h_tbl} ha) b
                        """.format(
                            a_tbl=self.ferti_tables[ac][0]['tbl_name'],
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
                            for ac_key in self.ferti_tables[ac].keys():
                                if 'pkey' in self.ferti_tables[ac][ac_key][
                                    'index_name']:
                                    continue
                                self.overlapping_tables[overlapping][
                                    'ac'].append(
                                    self.ferti_tables[ac][ac_key])

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
                        self.overlapping_tables[overlapping] = {}
                        for ha_key in self.harvest_tables[ha].keys():
                            if 'pkey' in self.harvest_tables[ha][ha_key]['index_name']:
                                continue
                            self.overlapping_tables[overlapping]['ha'] = self.harvest_tables[ha][ha_key]
                        self.overlapping_tables[overlapping]['so'] = []
                        for so_key in self.soil_tables[so].keys():
                            if 'pkey' in self.soil_tables[so][so_key]['index_name']:
                                continue
                            self.overlapping_tables[overlapping]['so'].append(self.soil_tables[so][so_key])

    def fill_dict_tables(self):
        """Filles the three dict tables"""
        for i, (schema, table) in enumerate(self.tables):
            if schema == 'harvest':
                self.harvest_tables[i] = self.db.get_indexes(table, schema)
            if schema == 'plant':
                self.plant_tables[i] = self.db.get_indexes(table, schema)
            if schema == 'ferti':
                self.ferti_tables[i] = self.db.get_indexes(table, schema)
            if schema == 'spray':
                self.spray_tables[i] = self.db.get_indexes(table, schema)

            if schema == 'soil':
                self.soil_tables[i] = self.db.get_indexes(table, schema)

    def get_initial_distinct_values(self, parameter_to_eval, tbl, schema):
        """
        Calls the database and gets distinct values
        :param parameter_to_eval: str, What parameter to eval
        :param tbl: str, In what table is the param located
        :param schema: str, In what schema
        :return: analyse_params{'distinct_values':[],'distinct_count':[]}
        """
        analyse_params = {}
        temp1 = []
        temp2 = []
        #TODO: Handle None values
        distinct = self.db.get_distinct(tbl, parameter_to_eval, schema)
        for value, count in distinct:
            temp1.append(value)
            temp2.append(count)
        analyse_params['distinct_values'] = temp1
        analyse_params['distinct_count'] = temp2
        return analyse_params

    def _set_checkbox_layout(self, qbox, analyse_params, col, nbr):
        self.layout_dict[col]['type'] = 'checked'
        self.layout_dict[col]['checked'] = []
        self.layout_dict[col]['checked_items'] = []
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
            self.layout_dict[col]['checked'].append(name)
            self.layout_dict[col]['checked_items'].append(item)
            model.setItem(i + 1, 0, item)
        param_label = QtWidgets.QLabel(name_text, self.top_right_panel[nbr])
        param_label.move(10, 20)
        QComb = QtWidgets.QComboBox(qbox)
        QComb.setModel(model)
        QComb.move(83, 34)
        self.layout_dict[col]['model'] = model
        self.layout_dict[col]['name_text'] = name_text
        self.layout_dict[col]['param_label'] = param_label

    def _set_number_layout(self, qbox, analyse_params, col, nbr):
        QtWidgets.QLabel('Min:', qbox).move(83, 34)
        if None in analyse_params['distinct_values']:
            analyse_params['distinct_values'].remove(None)
        min_value = QtWidgets.QLineEdit(str(np.nanmin(analyse_params['distinct_values'])), qbox)
        min_value.move(108, 32)
        org_min = QtWidgets.QLabel('({v})'.format(v=str(np.nanmin(analyse_params['distinct_values']))), qbox)
        org_min.move(112, 15)
        QtWidgets.QLabel('Max:', qbox).move(263, 34)
        max_value = QtWidgets.QLineEdit(str(np.nanmax(analyse_params['distinct_values'])), qbox)
        max_value.move(288, 32)
        org_max = QtWidgets.QLabel('({v})'.format(v=str(np.nanmax(analyse_params['distinct_values']))), qbox)
        org_max.move(292, 15)
        self.layout_dict[col]['type'] = 'max_min'
        self.layout_dict[col]['min'] = np.nanmin(analyse_params['distinct_values'])
        self.layout_dict[col]['min_text'] = min_value
        self.layout_dict[col]['min_label_text'] = org_min
        self.layout_dict[col]['max'] = np.nanmax(analyse_params['distinct_values'])
        self.layout_dict[col]['max_text'] = max_value
        self.layout_dict[col]['max_label_text'] = org_max
        if isfloat(max_value.text()):
            param_label = QtWidgets.QLabel('Min: ' + str(
                round(float(min_value.text()), 2)) + ' Max: ' + str(
                round(float(max_value.text()), 2)), self.top_right_panel[nbr])
        else:
            param_label = QtWidgets.QLabel(
                'Min: ' + str(min_value.text()) + ' Max: ' + str(
                    max_value.text()), self.top_right_panel[nbr])
        param_label.move(10, 20)

    def _update_layout(self, analyse_params, col):
        if self.layout_dict[col]['type'] == 'max_min':
            if self.layout_dict[col]['min'] > np.nanmin(analyse_params['distinct_values']):
                self.layout_dict[col]['min'] = np.nanmin(analyse_params['distinct_values'])
                self.layout_dict[col]['min_text'].setText(str(np.nanmin(analyse_params['distinct_values'])))
                self.layout_dict[col]['min_label_text'].setText(str(np.nanmin(analyse_params['distinct_values'])))
            if self.layout_dict[col]['max'] < np.nanmax(analyse_params['distinct_values']):
                self.layout_dict[col]['max'] = np.nanmax(analyse_params['distinct_values'])
                self.layout_dict[col]['max_text'].setText(str(np.nanmax(analyse_params['distinct_values'])))
                self.layout_dict[col]['max_label_text'].setText(str(np.nanmax(analyse_params['distinct_values'])))
        else:
            names = analyse_params['distinct_values']
            name_text = self.layout_dict[col]['name_text']
            model = self.layout_dict[col]['model']
            param_label = self.layout_dict[col]['param_label']
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
                self.layout_dict[col]['checked'].append(name)
                self.layout_dict[col]['checked_items'].append(item)
                model.setItem(i, 0, item)
            param_label.setText(name_text)
            self.layout_dict[col]['model'] = model
            self.layout_dict[col]['name_text'] = name_text
            self.layout_dict[col]['param_label'] = param_label

    def default_layout(self):
        """
        Creating the layout, (the UI file only contains the plotting area).
        This function adds parameters names and default value both in a scroll
        area bellow and to the right of the drawing area.
        :return:
        """
        colors = ['green', 'blue', 'red', 'green', 'blue', 'red', 'green', 'blue', 'red']
        #for key in mplib_colors.cnames.keys():
        #    colors.append(key)
        scroll_area_layout = QtWidgets.QVBoxLayout()
        constranint_area = QtWidgets.QWidget()
        constranint_layout = QtWidgets.QVBoxLayout()
        first_radio = True
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
                    self.overlapping_tables[key][sch][tbl_k]['tbl_name'],
                    self.overlapping_tables[key][sch][tbl_k]['schema'])
                if table['index_col'] in self.layout_dict.keys():
                    self._update_layout(analyse_params, table['index_col'])
                    self.layout_dict[table['index_col']]['tbl'].append(table['tbl_name'])
                    self.layout_dict[table['index_col']]['schema'].append(table['schema'])
                    self.layout_dict[table['index_col']]['harvest'].append(self.overlapping_tables[key]['ha'])
                else:
                    nbr += 1
                    self.layout_dict[table['index_col']] = {'tbl': [],
                                                                'schema': [],
                                                                'harvest': []}
                    self.layout_dict[table['index_col']]['tbl'].append(
                        table['tbl_name'])
                    self.layout_dict[table['index_col']]['schema'].append(
                        table['schema'])
                    self.layout_dict[table['index_col']]['harvest'].append(
                        self.overlapping_tables[key]['ha'])
                    ## set top right data basic data
                    self.top_right_panel.append(QtWidgets.QGroupBox())
                    self.top_right_panel[nbr].setMinimumSize(QtCore.QSize(30, 35))
                    self.top_right_panel[nbr].setStyleSheet("border:0px;")
                    param_label = QtWidgets.QLabel(table['index_col'].replace('_', ' '), self.top_right_panel[nbr])
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
        """Updates the parameters listed as checked in layout_dict
        :param other_parameters: dict"""
        for col in self.layout_dict.keys():
            text_v = ""
            for tbl_nr in range(len(self.layout_dict[col]['tbl'])):
                if self.layout_dict[col]['type'] == 'checked':
                    table = self.layout_dict[col]['tbl'][tbl_nr]
                    schema = self.layout_dict[col]['schema'][tbl_nr]
                    ha = self.layout_dict[col]['harvest'][tbl_nr]['tbl_name']
                    s_t = f'{schema}.{table}'
                    for item in self.layout_dict[col]['checked_items']:
                        if item.checkState() == 2 and col in other_parameters[ha][s_t].keys():
                            other_parameters[ha][s_t][col]['check_text'] += item.text() + "','"
                        if item.checkState() == 2 and col == main_investigate_col[ha][s_t]['col'] and item.text() not in text_v:
                            text_v += f"'{item.text()}',"
                    if col in other_parameters[ha][s_t].keys():
                        other_parameters[ha][s_t][col]['check_text'] = other_parameters[ha][s_t][col]['check_text'][:-2]
                else:
                    break
            if len(text_v) > 0:
                main_investigate_col['values'] = text_v[:-1]
        return other_parameters, main_investigate_col

    def update_top_panel(self, nbr, col):
        """Updates the top right panel with the data that complies the diagram
        """
        if self.layout_dict[col]['type'] == 'max_min':
            self.layout_dict[col]['min'] = self.layout_dict[col][
                'min_text'].text()
            self.layout_dict[col]['max'] = self.layout_dict[col][
                'max_text'].text()
            if isfloat(self.layout_dict[col]['max']):
                self.top_right_panel[nbr].children()[1].setText(
                    'Min: ' + str(
                        round(float(self.layout_dict[col]['min']),
                              2)) + ' Max: ' + str(
                        round(float(self.layout_dict[col]['max']), 2)))
            else:
                self.top_right_panel[nbr].children()[1].setText(
                    'Min: ' + str(
                        self.layout_dict[col]['min']) + ' Max: ' + str(
                        self.layout_dict[col]['max']))
        else:
            text = ''
            for item in self.layout_dict[col]['checked_items']:
                if item.checkState() == 2:
                    text += item.text() + ' '
            text = text[:-1]
            self.top_right_panel[nbr].children()[1].setText(text)

    def update_pic(self):
        """
        Updates the diagram with a parameters and limits
        :return:
        """
        if self.canvas is not None:
            self.dlg.mplvl.removeWidget(self.canvas)
        other_parameters = {}
        investigating_param = {}
        investigating_param['values'] = []
        prefixes = {}
        prefix_count = 0
        for nbr, col in enumerate(self.layout_dict.keys()):
            self.update_top_panel(nbr, col)
            for tbl_nr in range(len(self.layout_dict[col]['tbl'])):
                table = self.layout_dict[col]['tbl'][tbl_nr]
                schema = self.layout_dict[col]['schema'][tbl_nr]
                data_type = self.layout_dict[col]['type']
                ha = self.layout_dict[col]['harvest'][tbl_nr]['tbl_name']
                s_t = f'{schema}.{table}'
                if s_t not in prefixes.keys():
                    prefix_count += 1
                    prefixes[s_t] = f'a{prefix_count}'
                if self.cb[nbr].isChecked():
                    column_investigated = col
                    if ha not in investigating_param.keys():
                        investigating_param[ha] = {}
                        investigating_param[ha]['ha_col'] = \
                        self.layout_dict[col]['harvest'][tbl_nr]['index_col']
                    if s_t not in investigating_param[ha].keys():
                        investigating_param[ha][s_t] = {}
                    investigating_param[ha][s_t] = {}
                    investigating_param[ha][s_t]['prefix'] = prefixes[s_t]
                    investigating_param[ha][s_t]['col'] = col
                    i_col = col
                    analyse_params = self.get_initial_distinct_values(col,
                                                                      table,
                                                                      schema)
                    investigating_param['values'].extend(analyse_params['distinct_values'])
                    # Can happens multiple times, hence shouldn't be a problem.
                    if data_type == 'checked':
                        investigating_param['checked'] = True
                    else:
                        investigating_param['checked'] = False
                else:
                    if ha not in other_parameters.keys():
                        other_parameters[ha] = {}
                    if s_t not in other_parameters[ha].keys():
                        other_parameters[ha][s_t] = {}

                    other_parameters[ha][s_t]['prefix'] = prefixes[s_t]
                    other_parameters[ha][s_t][col] = {}
                    if self.layout_dict[col]['type'] == 'max_min':
                        other_parameters[ha][s_t][col]['type'] = 'max_min'
                        other_parameters[ha][s_t][col]['min'] = self.layout_dict[col]['min']
                        other_parameters[ha][s_t][col]['max'] = self.layout_dict[col]['max']
                    else:
                        other_parameters[ha][s_t][col]['type'] = 'checked'
                        other_parameters[ha][s_t][col]['check_text'] = "'"
        if not investigating_param['checked']:
            minvalue = float(self.layout_dict[i_col]['min'])
            maxvalue = float(self.layout_dict[i_col]['max'])
            values = copy.deepcopy(investigating_param['values'])
            for value in investigating_param['values']:
                if value is None:
                    values.remove(value)
                elif round(value, 3) < minvalue:
                    values.remove(value)
                elif round(value, 3) > maxvalue:
                    values.remove(value)
            investigating_param['values'] = values
        if not investigating_param['checked'] and len(
                investigating_param['values']) > 20:
            investigating_param['hist'] = True
            investigating_param['values'].sort()
            temp = []
            for val in range(0, len(investigating_param['values']),
                             int(round(len(investigating_param['values']) / 20))):
                temp.append(investigating_param['values'][val])
            temp.append(investigating_param['values'][-1])
            investigating_param['values'] = temp
        elif not investigating_param['checked']:
            investigating_param['hist'] = False
            investigating_param['values'].sort()
        else:
            investigating_param['hist'] = False
            investigating_param['values'] = "'"
        other_parameters, investigating_param = self.update_checked_field(other_parameters, investigating_param)
        min_counts = self.dlg.minNumber.text()
        self.column_investigated = column_investigated
        self.investigating_param = investigating_param
        task1 = QgsTask.fromFunction('running script', sql_queary,
                                     investigating_param, other_parameters,
                                     self.db, min_counts,
                                     on_finished=self.end_method)
        self.tsk_mngr.addTask(task1)

    def end_method(self, result, filter):
        fig, ax1 = plt.subplots()
        ax2 = ax1.twinx()
        if self.investigating_param['checked']:
            xlabels = filter[1]
            x = np.arange(len(xlabels))
            ax1.plot(x, filter[0], color='green')
            ax1.set_xticks(x)
            ax1.set_xticklabels(xlabels, rotation=40, ha='right')
            ax2.plot(x, filter[2], 'x', color='blue')
            ax2.set_xticks(x)
            ax2.set_xticklabels(xlabels, rotation=40, ha='right')
        else:
            ax1.plot(filter[1], filter[0], color='green')
            ax2.plot(filter[1], filter[2], 'x', color='blue')
        ax1.yaxis.label.set_color('green')
        ax1.set_xlabel(self.column_investigated.replace('_', ' '))
        ax1.set_ylabel('mean yield (kg/ha)')
        ax2.yaxis.label.set_color('blue')
        ax2.set_ylabel('Number of harvest samples')
        plt.subplots_adjust(wspace=0.6, hspace=0.6, left=0.17, bottom=0.12,
                            right=0.85, top=0.92)
        self.canvas = FigureCanvas(fig)
        self.dlg.mplvl.addWidget(self.canvas)
        self.canvas.draw()


def sql_queary(task, investigating_param, other_parameters, db,
               min_counts):
    mean_yields = [[], [], []]
    values = investigating_param['values']
    if investigating_param['checked']:
        values = values.split(',')
    values.sort()
    task.setProgress(25)
    for value_nbr, value in enumerate(values):
        if investigating_param['hist'] and value_nbr == 0:
            continue
        if value == '':
            value = ' '
        sql = 'with '
        for ha in investigating_param.keys():
            all_ready_joined = []
            if not type(investigating_param[ha]) == dict:
                continue
            sql += f"""{ha} as(select COALESCE(avg({investigating_param[ha]['ha_col']}),0) as yield, count(*)
            FROM harvest.{ha} ha
            """
            for in_key in investigating_param[ha].keys():
                if in_key == 'ha_col':
                    continue
                pre = investigating_param[ha][in_key]['prefix']
                sql += f"""JOIN {in_key} {pre} ON st_intersects(ha.pos, {pre}.polygon)
                """
                all_ready_joined.append(in_key)
            if ha in other_parameters.keys():
                for oth_key in other_parameters[ha].keys():
                    if not oth_key in sql:
                        pre = other_parameters[ha][oth_key]['prefix']
                        sql += f"""JOIN {oth_key} {pre} ON st_intersects(ha.pos, {pre}.polygon)
                        """
                        all_ready_joined.append(oth_key)
            sql += 'WHERE '
            if ha in other_parameters.keys():
                for oth_key in other_parameters[ha].keys():
                    pre = other_parameters[ha][oth_key]['prefix']
                    for attr in other_parameters[ha][oth_key].items():
                        if attr[0] == 'prefix':
                            continue
                        if attr[1]['type'] == 'max_min':
                            sql+= f"""{pre}.{attr[0]} >= {attr[1]['min']} AND
                            """
                            sql += f"""{pre}.{attr[0]} <= {attr[1]['max']} AND
                            """
                        if attr[1]['type'] == 'checked':
                            sql+= f"""{pre}.{attr[0]} in ({attr[1]['check_text']}) AND
                            """
            for in_key in investigating_param[ha].keys():
                if in_key == 'ha_col':
                    continue
                for in_key in investigating_param[ha].keys():
                    if in_key == 'ha_col':
                        continue
                    pre = investigating_param[ha][in_key]['prefix']
                    col = investigating_param[ha][in_key]['col']
                    if investigating_param['checked']:
                        sql += f"{pre}.{col} like {value}),"
                    elif investigating_param['hist']:
                        if len(values) != value_nbr:
                            sql += f"""{pre}.{col} >= {values[value_nbr - 1]} AND
                            {pre}.{col} < {value}),"""
                        else:
                            sql += f"""{pre}.{col} >= {values[value_nbr - 1]} AND
                            {pre}.{col} <= {value}),"""
                    else:
                        sql += f'{pre}.{col} = {value}),'
        sql = sql[:-1]
        sql += f"""
        SELECT case when("""
        for ha in investigating_param.keys():
            if not type(investigating_param[ha]) == dict:
                continue
            sql += f'{ha}.count + '
        sql = sql[:-3] + ') > 0 then ('
        for ha in investigating_param.keys():
            if not type(investigating_param[ha]) == dict:
                continue
            sql += f' {ha}.yield * {ha}.count + '
        sql = sql[:-3] + ')/('
        for ha in investigating_param.keys():
            if not type(investigating_param[ha]) == dict:
                continue
            sql += f'{ha}.count + '
        sql = sql[:-3] + ') else 0 end as yield, ('
        for ha in investigating_param.keys():
            if not type(investigating_param[ha]) == dict:
                continue
            sql += f'{ha}.count + '
        sql = sql[:-3] + """)
        FROM """
        for ha in investigating_param.keys():
            if not type(investigating_param[ha]) == dict:
                continue
            sql += f'{ha}, '
        sql = sql[:-2]
        #print(sql)
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
        task.setProgress(25 + value_nbr / len(values) * 50)
    return mean_yields