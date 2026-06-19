from typing import Self

from psycopg2 import sql as pgsql
from qgis.core import QgsProject, QgsTask
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas)
import numpy as np
from functools import partial
import copy
import traceback
import time
from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel, QBrush, QColor

from qgis.PyQt.QtWidgets import (QMessageBox, QWidget, QButtonGroup, QLabel, QLineEdit,
QRadioButton, QCheckBox, QGroupBox, QComboBox, QVBoxLayout)
from ..widgets.run_analyse import RunAnalyseDialog
from ..support_scripts.__init__ import isfloat, isint, TR
from ..support_scripts.qt_data import _check_state, _item_data_role, _item_flag
from ..support_scripts.add_field import AddField
from ..support_scripts.notifier import report_warning, report_error

__author__ = 'Axel Horteborn'


#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)
class Analyze:
    def __init__(self: Self, parent_widget, tables_to_analyse: list[list[str]]) -> None:
        """A widget that analyses the data in the database

        Parameters
        ----------
        parent_widget: GeoDataFarm
            The main class
        tables_to_analyse: list
            list of list schemas and tables that should
            be included in the analyse

        """
        self.dlg = RunAnalyseDialog()
        self.db = parent_widget.db
        self.tsk_mngr = parent_widget.tsk_mngr
        translate = TR('Analyze')
        self.tr = translate.tr
        self.iface = parent_widget.iface
        self.harvest_tables = {}
        self.plant_tables = {}
        self.spray_tables = {}
        self.ferti_tables = {}
        self.soil_tables = {}
        self.weather_tables = {}
        self.tables = tables_to_analyse
        self.cb = []
        self.harvest_tbls = {}
        self.scrollWidget = QWidget()
        self.radio_group = QButtonGroup()
        self.overlapping_tables = {}
        self.layout_dict = {}
        self.top_right_panel = []
        # self.populate_list(parameters)
        self.finish = False
        self.canvas = None
        self.search_area = ''
        self.add_field = AddField(parent_widget)

    def run(self):
        """Starts this widget"""
        self.dlg.show()
        self.dlg.pButRun.clicked.connect(self.update_pic)
        self.dlg.PBSelectArea.clicked.connect(partial(self.add_field.clicked_define_field, ignore_name=True))
        self.dlg.exec()

    def check_consistency(self: Self) -> bool:
        """Checks that the harvest tables is intersecting some of the input data
        If the data is an activity does it also check that the year is the same
        table both with respect to location and time!
        """
        self.fill_dict_tables()
        self.overlapping_tables = {}
        overlapping = -1
        for ha in self.harvest_tables.keys():
            ha_tbl = self.harvest_tables[ha][0]['tbl_name']
            ha_year = self.db.execute_and_return(
                pgsql.SQL("SELECT extract(year FROM date_) FROM harvest.{tbl} LIMIT 1").format(
                    tbl=pgsql.Identifier(ha_tbl)))[0][0]
            overlapping_nbr = overlapping
            if len(self.plant_tables) > 0:
                for ac in self.plant_tables.keys():
                    ac_tbl = self.plant_tables[ac][0]['tbl_name']
                    ac_year = self.db.execute_and_return(
                        pgsql.SQL("SELECT extract(year FROM date_) FROM plant.{tbl} LIMIT 1").format(
                            tbl=pgsql.Identifier(ac_tbl)))[0][0]
                    if ac_year == ha_year:
                        query = pgsql.SQL(
                            "SELECT sum(CASE WHEN st_intersects(a.geom, b.geom) THEN 1 ELSE 0 END)"
                            "/count(a.geom)::double precision"
                            " FROM (SELECT (ac.polygon) geom FROM plant.{a_tbl} ac) a,"
                            " (SELECT st_setsrid(st_extent(ha.pos), 4326) geom FROM harvest.{h_tbl} ha) b"
                        ).format(
                            a_tbl=pgsql.Identifier(ac_tbl),
                            h_tbl=pgsql.Identifier(ha_tbl))
                        overlaps = self.db.execute_and_return(query)[0][0]
                        if overlaps > 0.5:
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
                    ac_tbl = self.spray_tables[ac][0]['tbl_name']
                    ac_year = self.db.execute_and_return(
                        pgsql.SQL("SELECT extract(year FROM date_) FROM spray.{tbl} LIMIT 1").format(
                            tbl=pgsql.Identifier(ac_tbl)))[0][0]
                    if ac_year == ha_year:
                        query = pgsql.SQL(
                            "SELECT st_intersects(a.geom, b.geom)"
                            " FROM (SELECT st_extent(ac.polygon) geom FROM spray.{a_tbl} ac) a,"
                            " (SELECT st_extent(ha.pos) geom FROM harvest.{h_tbl} ha) b"
                        ).format(
                            a_tbl=pgsql.Identifier(ac_tbl),
                            h_tbl=pgsql.Identifier(ha_tbl))
                        overlaps = self.db.execute_and_return(query)[0][0]
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
                    ac_tbl = self.ferti_tables[ac][0]['tbl_name']
                    ac_year = self.db.execute_and_return(
                        pgsql.SQL("SELECT extract(year FROM date_) FROM ferti.{tbl} LIMIT 1").format(
                            tbl=pgsql.Identifier(ac_tbl)))[0][0]
                    if ac_year == ha_year:
                        query = pgsql.SQL(
                            "SELECT st_intersects(a.geom, b.geom)"
                            " FROM (SELECT st_extent(ac.polygon) geom FROM ferti.{a_tbl} ac) a,"
                            " (SELECT st_extent(ha.pos) geom FROM harvest.{h_tbl} ha) b"
                        ).format(
                            a_tbl=pgsql.Identifier(ac_tbl),
                            h_tbl=pgsql.Identifier(ha_tbl))
                        overlaps = self.db.execute_and_return(query)[0][0]
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
                    query = pgsql.SQL(
                        "SELECT st_intersects(a.geom, b.geom)"
                        " FROM (SELECT st_extent(ac.polygon) geom FROM soil.{s_tbl} ac) a,"
                        " (SELECT st_extent(ha.pos) geom FROM harvest.{h_tbl} ha) b"
                    ).format(
                        s_tbl=pgsql.Identifier(self.soil_tables[so][0]['tbl_name']),
                        h_tbl=pgsql.Identifier(ha_tbl))
                    overlaps = self.db.execute_and_return(query)[0][0]
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
            if len(self.weather_tables) > 0:
                for ac in self.weather_tables.keys():
                    ac_year = int(self.weather_tables[ac][0]['tbl_name'][-4:])
                    if ac_year == ha_year:
                        query = pgsql.SQL(
                            "SELECT st_intersects(a.geom, b.geom)"
                            " FROM (SELECT st_extent(ac.polygon) geom FROM weather.{a_tbl} ac) a,"
                            " (SELECT st_extent(ha.pos) geom FROM harvest.{h_tbl} ha) b"
                        ).format(
                            a_tbl=pgsql.Identifier(self.weather_tables[ac][0]['tbl_name']),
                            h_tbl=pgsql.Identifier(ha_tbl))
                        overlaps = self.db.execute_and_return(query)[0][0]
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
                            for ac_key in self.weather_tables[ac].keys():
                                if 'pkey' in self.weather_tables[ac][ac_key][
                                    'index_name']:
                                    continue
                                self.overlapping_tables[overlapping][
                                    'ac'].append(
                                    self.weather_tables[ac][ac_key])

            if overlapping_nbr == overlapping:
                report_warning(self.tr('All selected harvest table did not have a second '
                        'table to be analysed against'))
                return False
        return True

    def fill_dict_tables(self: Self) -> None:
        """Fills the dict tables"""
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
            if schema == 'weather':
                self.weather_tables[i] = self.db.get_indexes(table, schema)

    def get_initial_distinct_values(self: Self, parameter_to_eval: str, tbl: str, 
                                    schema: str) -> dict[str, list[int]]:
        """Calls the database and gets distinct values

        Parameters
        ----------
        parameter_to_eval: str, What parameter to eval
        tbl: str, In what table is the param located
        schema: str, In what schema

        Returns
        -------
        dict
            analyse_params{'distinct_values':[],'distinct_count':[]}
        """
        analyse_params = {}
        temp1 = []
        temp2 = []
        distinct = self.db.get_distinct(tbl, parameter_to_eval, schema)
        for value, count in distinct:
            temp1.append(value)
            temp2.append(count)
        analyse_params['distinct_values'] = temp1
        analyse_params['distinct_count'] = temp2
        return analyse_params

    def _set_checkbox_layout(self, qbox, analyse_params, col, nbr):
        """Sets the layout of a parameter that has strings as distinct values.

        Parameters
        ----------
        qbox: QGroupBox
        analyse_params: dict, {'distinct_values':[],'distinct_count':[]}
        col: str
        nbr: int

        """
        if None in analyse_params['distinct_values']:
            QLabel('Include No Data:', qbox).move(380, 15)
            cb_none = QCheckBox('', qbox)
            cb_none.move(434, 34)
            cb_none.setChecked(True)
            analyse_params['distinct_values'].remove(None)
            self.layout_dict[col]['None'] = cb_none
        else:
            self.layout_dict[col]['None'] = False
        if len(analyse_params['distinct_values']) == 0:
            analyse_params['distinct_values'] = ['None']
        self.layout_dict[col]['type'] = 'checked'
        self.layout_dict[col]['checked'] = []
        self.layout_dict[col]['checked_items'] = []
        names = analyse_params['distinct_values']
        model = QStandardItemModel(len(names), 1)
        firstItem = QStandardItem("---- Select ----")
        firstItem.setBackground(QBrush(QColor(200, 200, 200)))
        firstItem.setSelectable(False)
        model.setItem(0, 0, firstItem)
        name_text = ''
        for i, name in enumerate(names):
            item = QStandardItem(name)
            name_text += name + ' '
            item.setFlags(
                _item_flag('ItemIsUserCheckable') | _item_flag('ItemIsEnabled'))
            item.setData(_check_state('Checked'), _item_data_role('CheckStateRole'))
            self.layout_dict[col]['checked'].append(name)
            self.layout_dict[col]['checked_items'].append(item)
            model.setItem(i + 1, 0, item)
        param_label = QLabel(name_text, self.top_right_panel[nbr])
        param_label.move(10, 20)
        QComb = QComboBox(qbox)
        QComb.setModel(model)
        QComb.move(83, 34)
        self.layout_dict[col]['model'] = model
        self.layout_dict[col]['name_text'] = name_text
        self.layout_dict[col]['param_label'] = param_label

    def _set_number_layout(self, qbox, analyse_params, col, nbr):
        """Sets the layout of a parameter that has floats or ints as distinct
        values.

        Parameters
        ----------
        qbox: QGroupBox
        analyse_params: dict, {'distinct_values':[],'distinct_count':[]}
        col: str
        nbr: int

        """
        if None in analyse_params['distinct_values']:
            QLabel('Include No Data:', qbox).move(380, 15)
            cb_none = QCheckBox('', qbox)
            cb_none.move(434, 34)
            cb_none.setChecked(True)
            analyse_params['distinct_values'].remove(None)
            self.layout_dict[col]['None'] = cb_none
        else:
            self.layout_dict[col]['None'] = False
        if len(analyse_params['distinct_values']) == 0:
            analyse_params['distinct_values'] = [0, 1]
        QLabel('Min:', qbox).move(93, 34)
        min_value = QLineEdit(str(np.nanmin(analyse_params['distinct_values'])), qbox)
        min_value.move(118, 32)
        min_value.setFixedWidth(80)
        org_min = QLabel(f"({str(np.nanmin(analyse_params['distinct_values']))})", qbox)
        org_min.move(120, 15)
        QLabel('Max:', qbox).move(263, 34)
        max_value = QLineEdit(str(np.nanmax(analyse_params['distinct_values'])), qbox)
        max_value.move(295, 32)
        max_value.setFixedWidth(80)
        org_max = QLabel(f"({str(np.nanmax(analyse_params['distinct_values']))})", qbox)
        org_max.move(292, 15)
        self.layout_dict[col]['type'] = 'max_min'
        self.layout_dict[col]['min'] = np.nanmin(analyse_params['distinct_values'])
        self.layout_dict[col]['min_text'] = min_value
        self.layout_dict[col]['min_label_text'] = org_min
        self.layout_dict[col]['max'] = np.nanmax(analyse_params['distinct_values'])
        self.layout_dict[col]['max_text'] = max_value
        self.layout_dict[col]['max_label_text'] = org_max
        if isfloat(max_value.text()):
            param_label = QLabel('Min: ' + str(
                round(float(min_value.text()), 2)) + ' Max: ' + str(
                round(float(max_value.text()), 2)), self.top_right_panel[nbr])
        else:
            param_label = QLabel(
                'Min: ' + str(min_value.text()) + ' Max: ' + str(
                    max_value.text()), self.top_right_panel[nbr])
        param_label.move(10, 20)

    def _update_layout(self, analyse_params, col):
        """Updates the layout there are multiple tables with the same col name

        Parameters
        ----------
        analyse_params: dict
        col: str
        """
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
            print(names)
            for name in names:
                if name is None:
                    continue
                if name in name_text:
                    continue
                i += 1
                item = QStandardItem(name)
                name_text += name + ' '
                item.setFlags(
                    _item_flag('ItemIsUserCheckable') | _item_flag('ItemIsEnabled'))
                item.setData(_check_state('Checked'), _item_data_role('CheckStateRole'))
                self.layout_dict[col]['checked'].append(name)
                self.layout_dict[col]['checked_items'].append(item)
                model.setItem(i, 0, item)
            param_label.setText(name_text)
            self.layout_dict[col]['model'] = model
            self.layout_dict[col]['name_text'] = name_text
            self.layout_dict[col]['param_label'] = param_label

    def default_layout(self):
        """Creating the layout, (the UI file only contains the plotting area).
        This function adds parameters names and default value both in a scroll
        area bellow and to the right of the drawing area.
        """
        colors = ['green', 'blue', 'red', 'green', 'blue', 'red', 'green',
                  'blue', 'red', 'green', 'blue', 'red', 'green', 'blue', 'red']
        #for key in mplib_colors.cnames.keys():
        #    colors.append(key)
        scroll_area_layout = QVBoxLayout()
        constraint_area = QWidget()
        constraint_layout = QVBoxLayout()
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
                if len(analyse_params['distinct_values']) == 0:
                    continue
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
                    self.top_right_panel.append(QGroupBox())
                    self.top_right_panel[nbr].setMinimumSize(QSize(30, 35))
                    self.top_right_panel[nbr].setStyleSheet("border:0px;")
                    param_label = QLabel(table['index_col'].replace('_', ' '), self.top_right_panel[nbr])
                    param_label.move(10, 5)
                    constraint_layout.addWidget(self.top_right_panel[nbr])

                    ## Set bottom group basic data
                    qbox = QGroupBox()
                    qbox.setTitle(table['index_col'].replace('_', ' '))
                    qbox.setMinimumSize(QSize(100, 55))
                    qbox.setStyleSheet('QWidget{color:' + colors[nbr] + '}')
                    scroll_area_layout.addWidget(qbox)
                    QLabel('Show:', qbox).move(10, 15)
                    QLabel('Limit:', qbox).move(50, 34)

                    self.cb.append(QRadioButton('', qbox))
                    if first_radio:
                        self.cb[nbr].setChecked(True)
                        first_radio = False
                    else:
                        self.cb[nbr].setChecked(False)
                    self.radio_group.addButton(self.cb[nbr], nbr)
                    self.cb[nbr].move(15, 34)
                    if isinstance(analyse_params['distinct_values'][0], str):
                        self._set_checkbox_layout(qbox, analyse_params,
                                                  table['index_col'], nbr)
                    elif (len(analyse_params['distinct_values']) == 1 and
                          analyse_params['distinct_values'][0] is None):
                        self._set_checkbox_layout(qbox, analyse_params,
                                                  table['index_col'], nbr)
                    else:
                        self._set_number_layout(qbox, analyse_params,
                                                table['index_col'], nbr)

        constraint_area.setLayout(constraint_layout)
        self.dlg.groupBoxConstraints.setWidget(constraint_area)
        self.scrollWidget.setLayout(scroll_area_layout)
        self.dlg.paramArea.setWidget(self.scrollWidget)
        self.update_pic()

    def update_checked_field(self, other_parameters, main_investigate_col):
        """Updates the parameters listed as checked in layout_dict

        Parameters
        ----------
        other_parameters: dict
        main_investigate_col: dict
        """
        for col in self.layout_dict.keys():
            text_v = ""
            for tbl_nr in range(len(self.layout_dict[col]['tbl'])):
                if self.layout_dict[col]['type'] == 'checked':
                    table = self.layout_dict[col]['tbl'][tbl_nr]
                    schema = self.layout_dict[col]['schema'][tbl_nr]
                    ha = self.layout_dict[col]['harvest'][tbl_nr]['tbl_name']
                    s_t = f'{schema}.{table}'
                    for item in self.layout_dict[col]['checked_items']:
                        if ha in other_parameters.keys():
                            if s_t in other_parameters[ha].keys():
                                if item.checkState() == 2 and col in other_parameters[ha][s_t].keys():
                                    other_parameters[ha][s_t][col]['check_text'] += item.text() + "','"
                        if ha in main_investigate_col.keys():
                            if s_t in main_investigate_col[ha].keys():
                                if item.checkState() == 2 and col == main_investigate_col[ha][s_t]['col'] and item.text() not in text_v:
                                    text_v += f"'{item.text()}',"
                    if ha in other_parameters.keys():
                        if s_t in other_parameters[ha].keys():
                            if col in other_parameters[ha][s_t].keys():
                                other_parameters[ha][s_t][col]['check_text'] = other_parameters[ha][s_t][col]['check_text'][:-2]
                else:
                    break
            if len(text_v) > 0:
                main_investigate_col['values'] = text_v[:-1]
        return other_parameters, main_investigate_col

    def update_top_panel(self, nbr, col):
        """Updates the top right panel with the data that complies the diagram

        Parameters
        ----------
        nbr: int, what number to update
        col: str, the name och parameter to update
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
        """Collects the data that the user gave as input and starts the QgsTask
        that runs the SQL query. On finish plot_data is called"""
        if self.canvas is not None:
            self.dlg.mplvl.removeWidget(self.canvas)
        limiting_polygon = self.get_search_area()
        other_parameters, investigating_param, column_investigated, i_col = self.update_parameters()
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
        task1 = QgsTask.fromFunction('running script', sql_query,
                                     investigating_param, other_parameters,
                                     self.db, min_counts, limiting_polygon,
                                     on_finished=self.plot_data)
        self.tsk_mngr.addTask(task1)
        #a = sql_query('debug', investigating_param, other_parameters, self.db, min_counts, limiting_polygon)
        #self.plot_data('a', a)

    def update_parameters(self):
        other_parameters = {}
        investigating_param = {}
        investigating_param['values'] = []
        prefixes = {}
        prefix_count = 0
        print(self.layout_dict)
        for nbr, col in enumerate(self.layout_dict.keys()):
            self.update_top_panel(nbr, col)
            for tbl_nr in range(len(self.layout_dict[col]['tbl'])):
                table = self.layout_dict[col]['tbl'][tbl_nr]
                schema = self.layout_dict[col]['schema'][tbl_nr]
                data_type = self.layout_dict[col]['type']
                if self.layout_dict[col]['None']:
                    if self.layout_dict[col]['None'].checkState() == 2:
                        find_none = True
                    else:
                        find_none = False
                else:
                    find_none = False
                ha = self.layout_dict[col]['harvest'][tbl_nr]['tbl_name']
                s_t = f'{schema}.{table}'
                if s_t not in prefixes.keys():
                    prefix_count += 1
                    prefixes[s_t] = f'a{prefix_count}'
                if self.cb[nbr].isChecked():
                    column_investigated = col
                    if ha not in investigating_param.keys():
                        investigating_param[ha] = {}
                        investigating_param[ha]['ha_col'] = self.layout_dict[col]['harvest'][tbl_nr]['index_col']
                    if s_t not in investigating_param[ha].keys():
                        investigating_param[ha][s_t] = {}
                    investigating_param[ha][s_t] = {}
                    investigating_param[ha][s_t]['prefix'] = prefixes[s_t]
                    investigating_param[ha][s_t]['col'] = col
                    investigating_param[ha][s_t]['None'] = find_none
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
                    other_parameters[ha][s_t][col]['None'] = find_none
                    if self.layout_dict[col]['type'] == 'max_min':
                        other_parameters[ha][s_t][col]['type'] = 'max_min'
                        other_parameters[ha][s_t][col]['min'] = self.layout_dict[col]['min']
                        other_parameters[ha][s_t][col]['max'] = self.layout_dict[col]['max']
                    else:
                        other_parameters[ha][s_t][col]['type'] = 'checked'
                        other_parameters[ha][s_t][col]['check_text'] = "'"
        return other_parameters,investigating_param,column_investigated,i_col

    def get_search_area(self):
        if self.dlg.CBLimitArea.isChecked() and self.search_area == '':
            try:
                self.iface.actionSaveActiveLayerEdits().trigger()
                self.iface.actionToggleEditing().trigger()
                feature = self.add_field.field.getFeature(1)
                QgsProject.instance().removeMapLayer(self.add_field.field.id())
                self.add_field.field = None
            except:
                report_warning(self.tr(
                'No coordinates were found, did you mark the field on the canvas?'))
                return
            limiting_polygon = feature.geometry().asWkt()
            self.search_area = limiting_polygon
        elif self.dlg.CBLimitArea.isChecked() and self.add_field.field is not None:
            self.iface.actionSaveActiveLayerEdits().trigger()
            self.iface.actionToggleEditing().trigger()
            feature = self.add_field.field.getFeature(1)
            QgsProject.instance().removeMapLayer(self.add_field.field.id())
            self.add_field.field = None
            limiting_polygon = feature.geometry().asWkt()
            self.search_area = limiting_polygon
        elif self.dlg.CBLimitArea.isChecked():
            limiting_polygon = self.search_area
        else:
            limiting_polygon = None
            self.search_area = ''
        return limiting_polygon

    def plot_data(self, result, values):
        """Plots the data from the sql query.

        Parameters
        ----------
        result: Unused parameter

        values: list
            if success:
                [True, dict]
            else:
                [False, message, tracback]
        """
        if values[0] is False:
            report_error(self.tr(f'Following error occurred: {values[1]}\n\n Traceback: {values[2]}'), detail=str(values[1]))
            return
        else:
            filtered_data = values[1]
        fig, ax1 = plt.subplots()
        #ax2 = ax1.twinx()
        if self.investigating_param['checked']:
            xlabels = filtered_data[1]
            x = np.arange(len(xlabels))
            ax1.plot(x, filtered_data[0], color='green')
            ax1.set_xticks(x)
            ax1.set_xticklabels(xlabels, rotation=40, ha='right')
            #ax2.plot(x, filtered_data[2], 'x', color='blue')
            #ax2.set_xticks(x)
            #ax2.set_xticklabels(xlabels, rotation=40, ha='right')
        else:
            ax1.plot(filtered_data[1], filtered_data[0], color='green')
            #ax2.plot(filtered_data[1], filtered_data[2], 'x', color='blue')
        ax1.yaxis.label.set_color('green')
        ax1.set_xlabel(self.column_investigated.replace('_', ' '))
        ax1.set_ylabel('mean yield (kg/ha)')
        #ax2.yaxis.label.set_color('blue')
        #ax2.set_ylabel(sel.tr('Number of harvest samples'))
        plt.subplots_adjust(wspace=0.6, hspace=0.6, left=0.17, bottom=0.12,
                            right=0.85, top=0.92)
        self.canvas = FigureCanvas(fig)
        self.dlg.mplvl.addWidget(self.canvas)
        self.canvas.draw()
        model = QStandardItemModel()
        model.setRowCount(len(filtered_data[0]))
        model.setColumnCount(3)
        model.setHorizontalHeaderItem(0, QStandardItem(self.column_investigated.replace('_', ' ')))
        model.setHorizontalHeaderItem(1, QStandardItem(self.tr('Average yield')))
        model.setHorizontalHeaderItem(2, QStandardItem(self.tr('Yield samples')))
        for i, m_yield in enumerate(filtered_data[0]):
            try:
                current_value = filtered_data[1][i].replace("'", "")
            except AttributeError:
                try:
                    current_value = round(filtered_data[1][i], 2)
                except:
                    current_value = filtered_data[1][i]
            current_count = filtered_data[2][i]
            m_yield = round(m_yield, 2)
            item1 = QStandardItem()
            item1.setText(str(current_value))
            item2 = QStandardItem()
            item2.setText(str(m_yield))
            item3 = QStandardItem()
            item3.setText(str(current_count))
            model.setItem(i, 0, item1)
            model.setItem(i, 1, item2)
            model.setItem(i, 2, item3)
        self.dlg.TVValues.setModel(model)

def sql_query(task, investigating_param, other_parameters, db,
              min_counts, limiting_polygon):
    """Function that creates and runs the SQL questions to the database, creates
    filters and connects the correct tables to each other. Runs one question for
    each interval.

    Parameters
    ----------
    task: QgsTask
    investigating_param: dict
    other_parameters: dict
    db: DB
    min_counts: int, the minimum data points that are required.
    limiting_polygon: str, a wkt string with a polygon limiting the search.

    Returns
    -------
    list
        if success:
            [bool, dict]
        else:
            [bool, str, str]
    """
    try:
        print(investigating_param)
        print(other_parameters)
        mean_yields = [[], [], []]
        values = investigating_param['values']
        if investigating_param['checked']:
            values = values.split(',')
        values.sort()
        if task != 'debug':
            task.setProgress(25)
        for value_nbr, value in enumerate(values):
            if investigating_param['hist'] and value_nbr == 0:
                continue
            if value == '':
                value = ' '
            ha_keys = [k for k in investigating_param.keys()
                       if isinstance(investigating_param[k], dict)]
            cte_parts = []
            for ha in ha_keys:
                parts = [pgsql.SQL(
                    "{ha} AS (SELECT COALESCE(avg({avg_val}), 0) AS yield, count(*)"
                    " FROM harvest.{ha} ha"
                ).format(
                    ha=pgsql.Identifier(ha),
                    avg_val=pgsql.Identifier(investigating_param[ha]['ha_col']))]

                all_ready_joined = []
                for in_key in investigating_param[ha].keys():
                    if in_key == 'ha_col':
                        continue
                    pre = investigating_param[ha][in_key]['prefix']
                    in_schema, in_tbl = in_key.split('.')
                    parts.append(pgsql.SQL(
                        " JOIN {schema}.{tbl} {pre} ON st_intersects(ha.pos, {pre}.polygon)"
                    ).format(
                        schema=pgsql.Identifier(in_schema),
                        tbl=pgsql.Identifier(in_tbl),
                        pre=pgsql.Identifier(pre)))
                    all_ready_joined.append(in_key)
                if ha in other_parameters.keys():
                    for oth_key in other_parameters[ha].keys():
                        if oth_key in all_ready_joined:
                            continue
                        pre = other_parameters[ha][oth_key]['prefix']
                        oth_schema, oth_tbl = oth_key.split('.')
                        parts.append(pgsql.SQL(
                            " JOIN {schema}.{tbl} {pre} ON st_intersects(ha.pos, {pre}.polygon)"
                        ).format(
                            schema=pgsql.Identifier(oth_schema),
                            tbl=pgsql.Identifier(oth_tbl),
                            pre=pgsql.Identifier(pre)))
                        all_ready_joined.append(oth_key)

                where_conds = []
                if limiting_polygon is not None:
                    where_conds.append(pgsql.SQL(
                        "st_intersects(st_geomfromtext({lp}, 4326), ha.pos)"
                    ).format(lp=pgsql.Literal(limiting_polygon)))
                if ha in other_parameters.keys():
                    for oth_key in other_parameters[ha].keys():
                        pre = other_parameters[ha][oth_key]['prefix']
                        for attr_name, attr_val in other_parameters[ha][oth_key].items():
                            if attr_name == 'prefix':
                                continue
                            inner = None
                            if attr_val['type'] == 'max_min':
                                inner = pgsql.SQL(
                                    "{pre}.{attr} >= {min_v} AND {pre}.{attr} <= {max_v}"
                                ).format(
                                    pre=pgsql.Identifier(pre),
                                    attr=pgsql.Identifier(attr_name),
                                    min_v=pgsql.Literal(attr_val['min']),
                                    max_v=pgsql.Literal(attr_val['max']))
                            elif attr_val['type'] == 'checked':
                                inner = pgsql.SQL(
                                    "{pre}.{attr} IN ({txt})"
                                ).format(
                                    pre=pgsql.Identifier(pre),
                                    attr=pgsql.Identifier(attr_name),
                                    txt=pgsql.SQL(attr_val['check_text']))
                            if inner is None:
                                continue
                            if attr_val['None']:
                                where_conds.append(pgsql.SQL(
                                    "(({inner}) OR {pre}.{attr} IS NULL)"
                                ).format(
                                    inner=inner,
                                    pre=pgsql.Identifier(pre),
                                    attr=pgsql.Identifier(attr_name)))
                            else:
                                where_conds.append(inner)
                for in_key in investigating_param[ha].keys():
                    if in_key == 'ha_col':
                        continue
                    for in_key in investigating_param[ha].keys():
                        if in_key == 'ha_col':
                            continue
                        pre = investigating_param[ha][in_key]['prefix']
                        col = investigating_param[ha][in_key]['col']
                        if investigating_param['checked']:
                            where_conds.append(pgsql.SQL(
                                "{pre}.{col} LIKE {val}"
                            ).format(
                                pre=pgsql.Identifier(pre),
                                col=pgsql.Identifier(col),
                                val=pgsql.Literal(value)))
                        elif investigating_param['hist']:
                            op = pgsql.SQL("<") if len(values) != value_nbr else pgsql.SQL("<=")
                            where_conds.append(pgsql.SQL(
                                "{pre}.{col} >= {v2} AND {pre}.{col} {op} {v}"
                            ).format(
                                pre=pgsql.Identifier(pre),
                                col=pgsql.Identifier(col),
                                v2=pgsql.Literal(values[value_nbr - 1]),
                                op=op,
                                v=pgsql.Literal(value)))
                        else:
                            where_conds.append(pgsql.SQL(
                                "{pre}.{col} = {v}"
                            ).format(
                                pre=pgsql.Identifier(pre),
                                col=pgsql.Identifier(col),
                                v=pgsql.Literal(value)))

                if where_conds:
                    parts.append(pgsql.SQL(" WHERE "))
                    parts.append(pgsql.SQL(" AND ").join(where_conds))
                parts.append(pgsql.SQL(")"))
                cte_parts.append(pgsql.Composed(parts))

            ha_idents = [pgsql.Identifier(k) for k in ha_keys]
            count_sum = pgsql.SQL(" + ").join([
                pgsql.SQL("{h}.count").format(h=h) for h in ha_idents])
            yield_sum = pgsql.SQL(" + ").join([
                pgsql.SQL("{h}.yield * {h}.count").format(h=h) for h in ha_idents])
            from_list = pgsql.SQL(", ").join(ha_idents)

            query = pgsql.SQL("WITH ") + pgsql.SQL(", ").join(cte_parts) + pgsql.SQL(
                " SELECT CASE WHEN ("
            ) + count_sum + pgsql.SQL(") > 0 THEN ("
            ) + yield_sum + pgsql.SQL(")/("
            ) + count_sum + pgsql.SQL(") ELSE 0 END AS yield, ("
            ) + count_sum + pgsql.SQL(") FROM "
            ) + from_list
            if task == 'debug':
                print(query)
            result = db.execute_and_return(query)[0]
            mean_value = result[0]
            count_samples = result[1]
            if count_samples <= int(min_counts):
                continue
            if investigating_param['hist']:
                value = (value + investigating_param['values'][value_nbr - 1]) / 2
            mean_yields[0].append(mean_value)
            mean_yields[1].append(value)
            mean_yields[2].append(count_samples)
            if task != 'debug':
                task.setProgress(25 + value_nbr / len(values) * 50)
        return [True, mean_yields]
    except Exception as e:
        return [False, e, traceback.format_exc()]
