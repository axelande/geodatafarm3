import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt4agg import (FigureCanvasQTAgg as FigureCanvas)
import matplotlib.colors as mplib_colors
import numpy as np
import time
from PyQt4 import QtCore, QtGui
from widgets.run_analyse import RunAnalyseDialog
from widgets.waiting import Waiting
from support_scripts.__init__ import isfloat, isint
__author__ = 'Axel Andersson'


class Analyze:
    def __init__(self, tables_to_analyse, parent_widget):
        """
        A widget that analyses the data in the database
        :param tables_to_analyse: the tables that should be included in the
        analyse
        :param parent_widget: the docked widget
        :return:
        """
        self.dlg = RunAnalyseDialog()
        self.DB = parent_widget.DB
        self.tables = str(tables_to_analyse)[1:-1]
        self.parameters = self.DB.get_indexes(self.tables[1:-1], True)
        self.cb = []
        self.max_min_checked = {}
        self.harvest_tbls = {}
        self.dlg.pButRun.clicked.connect(self.run_update)
        self.default_layout()
        #self.populate_list(parameters)
        self.finish = False

    def add_input(self):
        """
        Starts this widget
        :return:
        """
        self.dlg.show()
        self.dlg.exec_()

    def run_update(self):
        #self.update_pic()
        from PyQt4.QtCore import QThread
        #TODO: Fix threading
        self.next_thread = QThread()
        self.next_thread.started.connect(self.update_pic)
        self.next_thread.start()
        #waiting_thread = QThread()
        #waiting_thread.start()
        #wait_msg = 'Please wait while data is being prosecuted'
        #self.wait = Waiting(wait_msg)
        #self.wait.moveToThread(waiting_thread)
        #self.wait.start.connect(self.wait.start_work)
        #self.wait.start.emit('run')
        #while not self.finish:
        #    time.sleep(1)
        #self.wait.stop_work()
        #self.next_thread.join()

    def get_initial_distinct_values(self, parameter_to_eval, tbl, schema):
        """
        Calls the database and gets distinct values
        :param parameter_to_eval: What parameter to eval
        :param tbl: In what table is the param located
        :return: analyse_params{'distinct_values':[],'distinct_count':[]}
        """
        self.max_bins = None
        analyse_params = {}
        distinct = self.DB.get_distinct(tbl, parameter_to_eval, schema)
        temp1 = []
        temp2 = []
        for value, count in distinct:
            temp1.append(value)
            temp2.append(count)
        analyse_params['distinct_values'] = temp1
        analyse_params['distinct_count'] = temp2
        return analyse_params

    def default_layout(self):
        """
        Set the default layout included running the first parameter
        :return:
        """
        colors = ['green', 'blue', 'red']
        for key in mplib_colors.cnames.keys():
            colors.append(key)
        self.scrollWidget = QtGui.QWidget()
        scroll_area_layout = QtGui.QVBoxLayout()
        constranint_area = QtGui.QWidget()
        constranint_layout = QtGui.QVBoxLayout()
        first_radio = True
        first_param = True
        self.radio_group = QtGui.QButtonGroup()
        harvest_nbr = 0
        self.qbox_constraint = []
        for nbr, param_text in enumerate(self.parameters.keys()):
            if self.parameters[param_text]['schema'] == 'harvest':
                self.harvest_tbls[harvest_nbr] = {}
                self.harvest_tbls[harvest_nbr]['column'] = self.parameters[param_text]['index_col']
                self.harvest_tbls[harvest_nbr]['tbl'] = self.parameters[param_text]['tbl_name']
                harvest_nbr +=1
                continue

            nbr = nbr - harvest_nbr
            self.max_min_checked[nbr] = {}
            self.max_min_checked[nbr]['column'] = self.parameters[param_text]['index_col']
            self.qbox_constraint.append(QtGui.QGroupBox())
            self.qbox_constraint[nbr].setMinimumSize(QtCore.QSize(30, 35))
            self.qbox_constraint[nbr].setStyleSheet("border:0px;")
            param_label = QtGui.QLabel(self.parameters[param_text]['index_col'].replace('_', ' '), self.qbox_constraint[nbr])
            param_label.move(10, 5)
            constranint_layout.addWidget(self.qbox_constraint[nbr])
            self.max_min_checked[nbr]['tbl'] = self.parameters[param_text]['tbl_name']
            self.max_min_checked[nbr]['schema'] = self.parameters[param_text]['schema']
            qbox = QtGui.QGroupBox()
            qbox.setTitle(self.parameters[param_text]['index_col'].replace('_', ' '))
            qbox.setMinimumSize(QtCore.QSize(100, 55))
            qbox.setStyleSheet('QWidget{color:' + colors[nbr] + '}')
            scroll_area_layout.addWidget(qbox)
            QtGui.QLabel('Show:', qbox).move(10, 15)
            self.cb.append(QtGui.QRadioButton('', qbox))
            if first_radio:
                self.cb[len(self.cb)-1].setChecked(True)
                first_radio = False
            else:
                self.cb[len(self.cb)-1].setChecked(False)

            self.radio_group.addButton(self.cb[len(self.cb)-1], len(self.cb)-1)
            self.cb[len(self.cb)-1].move(15, 34)
            QtGui.QLabel('Limit:', qbox).move(50, 34)
            analyse_params = self.get_initial_distinct_values(self.parameters[param_text]['index_col'], self.parameters[param_text]['tbl_name'], self.parameters[param_text]['schema'])
            if first_param:
                first_param = False
                investigating_param = {}
                investigating_param['tbl'] = self.max_min_checked[nbr]['tbl']
                investigating_param['col'] = self.max_min_checked[nbr]['column']

                if len(analyse_params['distinct_values']) > 20:
                    investigating_param['hist'] = True
                    investigating_param['values'] = []
                    for val in range(0, len(analyse_params['distinct_values']), int(round(len(analyse_params['distinct_values'])/20))):
                        investigating_param['values'].append(analyse_params['distinct_values'][val])
                    investigating_param['values'].append(analyse_params['distinct_values'][-1])
                else:
                    investigating_param['hist'] = False
                    investigating_param['values'] = analyse_params['distinct_values']
                if isint(analyse_params['distinct_values'][0]) or isfloat(analyse_params['distinct_values'][0]):
                    investigating_param['type'] = 'max_min'
                else:
                    investigating_param['type'] = 'checked'

            if isint(analyse_params['distinct_values'][0]) or isfloat(analyse_params['distinct_values'][0]):
                QtGui.QLabel('Min:', qbox).move(83, 34)
                min_value = QtGui.QLineEdit(str(np.nanmin(analyse_params['distinct_values'])), qbox)
                min_value.move(108, 32)
                QtGui.QLabel('('+str(np.nanmin(analyse_params['distinct_values'])) + ')', qbox).move(112, 15)
                QtGui.QLabel('Max:', qbox).move(263, 34)
                max_value = QtGui.QLineEdit(str(np.nanmax(analyse_params['distinct_values'])), qbox)
                max_value.move(288, 32)
                QtGui.QLabel('('+str(np.nanmax(analyse_params['distinct_values'])) + ')', qbox).move(292, 15)
                self.max_min_checked[nbr]['type'] = 'max_min'
                self.max_min_checked[nbr]['min'] = np.nanmin(analyse_params['distinct_values'])
                self.max_min_checked[nbr]['min_text'] = min_value
                self.max_min_checked[nbr]['max'] = np.nanmax(analyse_params['distinct_values'])
                self.max_min_checked[nbr]['max_text'] = max_value
                if isfloat(max_value.text()):
                    param_label = QtGui.QLabel('Min: ' + str(round(float(min_value.text()), 2)) + ' Max: ' + str(round(float(max_value.text()), 2)), self.qbox_constraint[nbr])
                else:
                    param_label = QtGui.QLabel('Min: ' + str(min_value.text()) + ' Max: ' + str(max_value.text()), self.qbox_constraint[nbr])
                param_label.move(10, 20)
            else:
                self.max_min_checked[nbr]['type'] = 'checked'
                self.max_min_checked[nbr]['checked'] = []
                self.max_min_checked[nbr]['checked_items'] = []
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
                    item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
                    item.setData(QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
                    self.max_min_checked[nbr]['checked'].append(name)
                    self.max_min_checked[nbr]['checked_items'].append(item)
                    model.setItem(i+1, 0, item)
                param_label = QtGui.QLabel(name_text, self.qbox_constraint[nbr])
                param_label.move(10, 20)
                QComb = QtGui.QComboBox(qbox)
                QComb.setModel(model)
                QComb.move(83, 34)
                self.max_min_checked[nbr]['model'] = model
        filter = self.get_filter_text(investigating_param)

        fig, ax1 = plt.subplots()
        if investigating_param['type'] == 'max_min':
            ax1.plot(filter[1], filter[0], color = 'green')
        else:
            x = []
            my_xticks = []
            for i, name in enumerate(filter[1]):
                my_xticks.append(name)
                x.append(i)
            ax1.plot(x, filter[0], color = 'green')
            plt.xticks(x, my_xticks, rotation=45)
        ax1.yaxis.label.set_color('green')
        ax1.set_xlabel(investigating_param['col'].replace('_', ' '))
        ax1.set_ylabel('mean yield (kg/ha)')
        ax2 = ax1.twinx()
        if investigating_param['type'] == 'max_min':
            ax2.plot(filter[1], filter[2], 'x', color='blue')
        else:
            ax2.plot(x, filter[2], 'x', color='blue')
            plt.xticks(x, my_xticks, rotation=45)
        ax2.yaxis.label.set_color('blue')
        ax2.set_ylabel('Number of harvest samples')
        plt.subplots_adjust(wspace=0.6, hspace=0.6, left=0.17, bottom=0.12, right=0.85, top=0.92)
        self.canvas = FigureCanvas(fig)
        self.dlg.mplvl.addWidget(self.canvas)
        self.canvas.draw()

        constranint_area.setLayout(constranint_layout)
        self.dlg.groupBoxConstraints.setWidget(constranint_area)
        self.scrollWidget.setLayout(scroll_area_layout)
        self.dlg.paramArea.setWidget(self.scrollWidget)

    def update_checked_field(self):
        for nbr in range(len(self.cb)):
            if self.max_min_checked[nbr]['type'] == 'checked':
                for item in self.max_min_checked[nbr]['checked_items']:
                    if item.checkState() == 0 and item.text() in self.max_min_checked[nbr]['checked']:
                        self.max_min_checked[nbr]['checked'].remove(item.text())
                    if item.checkState() == 2 and item.text() not in self.max_min_checked[nbr]['checked']:
                        self.max_min_checked[nbr]['checked'].append(item.text())

    def update_pic(self):
        """
        Updates the diagram with a parameters and limits
        :return:
        """
        self.finish = False
        try:
            self.dlg.mplvl.removeWidget(self.canvas)
            #for
        except:
            pass
        for nbr in range(len(self.cb)):
            if self.max_min_checked[nbr]['type'] == 'max_min':
                self.max_min_checked[nbr]['min'] = self.max_min_checked[nbr]['min_text'].text()
                self.max_min_checked[nbr]['max'] = self.max_min_checked[nbr]['max_text'].text()
                if isfloat(self.max_min_checked[nbr]['max']):
                    self.qbox_constraint[nbr].children()[1].setText('Min: ' + str(round(float(self.max_min_checked[nbr]['min']), 2)) + ' Max: ' + str(round(float(self.max_min_checked[nbr]['max']), 2)))
                else:
                    self.qbox_constraint[nbr].children()[1].setText('Min: ' + str(self.max_min_checked[nbr]['min']) + ' Max: ' + str(self.max_min_checked[nbr]['max']))
            else:
                text = ''
                for name in self.max_min_checked[nbr]['checked']:
                    text += name + ', '
                text = text[:-2]
                self.qbox_constraint[nbr].children()[1].setText(text)
            if self.cb[nbr].isChecked():
                analyse_params = self.get_initial_distinct_values(self.max_min_checked[nbr]['column'], self.max_min_checked[nbr]['tbl'], self.max_min_checked[nbr]['schema'])
                investigating_param = {}
                investigating_param['tbl'] = self.max_min_checked[nbr]['tbl']
                investigating_param['col'] = self.max_min_checked[nbr]['column']
                if len(analyse_params['distinct_values']) > 20:
                    investigating_param['hist'] = True
                    investigating_param['values'] = []
                    for val in range(0, len(analyse_params['distinct_values']), int(round(len(analyse_params['distinct_values'])/20))):
                        investigating_param['values'].append(analyse_params['distinct_values'][val])
                    investigating_param['values'].append(analyse_params['distinct_values'][-1])
                else:
                    investigating_param['hist'] = False
                    investigating_param['values'] = analyse_params['distinct_values']
                if self.max_min_checked[nbr]['type'] != 'checked':
                    minvalue = float(self.max_min_checked[nbr]['min'])
                    maxvalue = float(self.max_min_checked[nbr]['max'])
                    remove_list = []
                    for value in investigating_param['values']:
                        if round(value, 3) < minvalue or round(value, 3) > maxvalue:
                            remove_list.append(value)
                    for value in remove_list:
                        investigating_param['values'].remove(value)
                else:
                    # TODO: Fix this
                    pass

                    #print(value)
                #print(investigating_param['values'])
            #print(self.qbox_constraint[nbr].children())
        filter = self.get_filter_text(investigating_param)
        fig, ax1 = plt.subplots()
        ax1.plot(filter[1], filter[0], color = 'green')
        ax1.yaxis.label.set_color('green')
        ax1.set_xlabel(investigating_param['col'].replace('_', ' '))
        ax1.set_ylabel('mean yield (kg/ha)')
        ax2 = ax1.twinx()
        ax2.plot(filter[1], filter[2], 'x', color='blue')
        ax2.yaxis.label.set_color('blue')
        ax2.set_ylabel('Number of harvest samples')
        plt.subplots_adjust(wspace=0.6, hspace=0.6, left=0.17, bottom=0.12, right=0.85, top=0.92)
        self.canvas = FigureCanvas(fig)
        self.dlg.mplvl.addWidget(self.canvas)
        self.canvas.draw()
        self.finish = True

    def get_filter_text(self, investigating_param):
        """
        Writes the sql question
        :param investigating_param: What parameter to put on the x-axis
        :return: a diagram over the mean yield
        """
        ## TODO enable the possibility to have more than one harvest table
        #self.max_min_checked[nbr]['type'] = 'checked'
        mean_yields = [[], [], []]
        found = False
        histogramed = False
        self.update_checked_field()
        if investigating_param['hist']:
            histogramed = True
            investigating_param['values'] = investigating_param['values']
        for value_nbr, value in enumerate(investigating_param['values']):
            if histogramed and value_nbr == 0:
                continue
            all_ready_joined = {}
            sql = """select avg(ha.{col}), count(*) from harvest.{tbl} ha
                     join """.format(col=self.harvest_tbls[0]['column'], tbl=self.harvest_tbls[0]['tbl'])
            for nbr in range(len(self.max_min_checked)):
                if self.max_min_checked[nbr]['column'] == investigating_param['col'] and self.max_min_checked[nbr]['tbl'] == investigating_param['tbl']:
                    continue
                if self.max_min_checked[nbr]['type'] == 'harvest':
                    all_ready_joined[self.max_min_checked[nbr]['tbl']] = None
                    # all_ready_joined[investigating_param['tbl']] = None
                    break

            for nbr in range(len(self.max_min_checked)):
                if self.max_min_checked[nbr]['column'] == investigating_param['col'] and self.max_min_checked[nbr]['tbl'] == investigating_param['tbl']:
                    continue
                if self.max_min_checked[nbr]['tbl'] in all_ready_joined.keys():
                    continue
                all_ready_joined[self.max_min_checked[nbr]['tbl']] = 'a' + str(nbr)
                sql += """{schema}.{new_tbl} a{nbr} on st_intersects(ha.pos, a{nbr}.polygon)
                join """.format(schema=self.max_min_checked[nbr]['schema'], new_tbl=self.max_min_checked[nbr]['tbl'], nbr=nbr)
            if investigating_param['tbl'] in all_ready_joined:
                sql = sql[:-5]
                value_prefix = all_ready_joined[investigating_param['tbl']]
            else:
                sql += """{param} b1 on st_intersects(ha.pos, b1.polygon)""".format(param=investigating_param['tbl'])
                value_prefix = 'b1'
            sql += "where "
            for nbr in range(len(self.max_min_checked)):
                if self.max_min_checked[nbr]['column'] == investigating_param['col'] and self.max_min_checked[nbr]['tbl'] == investigating_param['tbl']:
                    continue
                prefix = all_ready_joined[self.max_min_checked[nbr]['tbl']]
                if self.max_min_checked[nbr]['type'] == 'checked':
                    sql += '('
                    for item in self.max_min_checked[nbr]['checked']:
                        sql += """{prefix}.{col} = '{item}'
                         or """.format(prefix=prefix, col=self.max_min_checked[nbr]['column'], item=item)
                    sql = sql[:-3] + ') and '
                elif self.max_min_checked[nbr]['type'] == 'max_min':
                    sql += """{prefix}.{col} >= {min} and
                     {prefix}.{col} <= {max} and
                    """.format(prefix=prefix,
                               col=self.max_min_checked[nbr]['column'],
                               min=str(self.max_min_checked[nbr]['min']),
                               max=str(self.max_min_checked[nbr]['max']))

            if histogramed:
                sql += """{prefix}.{col} >= {val} and
                """.format(prefix=value_prefix, col=investigating_param['col'],
                           val=str(investigating_param['values'][value_nbr - 1]))
                sql += """{prefix}.{col} <= {val}""".format(prefix=value_prefix,
                                                            col=investigating_param['col'],
                                                            val=str(value))
            elif not isint(value) and not isfloat(value):
                sql += """{prefix}.{col} = '{str_val}'""".format(prefix=value_prefix, col=investigating_param['col'], str_val=value)
            else:
                sql += """{prefix}.{col} = {str_val}""".format(prefix=value_prefix, col=investigating_param['col'], str_val=str(value))
            #print(sql)
            result = self.DB.execute_and_return(sql)[0]
            mean_value = result[0]
            count_samples = result[1]
            if count_samples <= int(self.dlg.minNumber.text()):
                continue
            if histogramed:
                value = (value + investigating_param['values'][value_nbr - 1]) / 2
            mean_yields[0].append(mean_value)
            mean_yields[1].append(value)
            mean_yields[2].append(count_samples)
        return mean_yields