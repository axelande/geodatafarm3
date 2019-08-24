# -*- coding: utf-8 -*-
"""
***************************************************************************

 GeoDataFarm - A QGIS plugin
 This is a plugin that aims to determine the yield impact of different factors

 * begin                : 2016-05-13
 * copyright            : (C) 2016 by Axel Horteborn
 * email                : geodatafarm@gmail.com

***************************************************************************

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU AFFERO GENERAL PUBLIC LICENSE.

***************************************************************************

"""
# TODO: ensure that no calls to the database within tasks handel errors correctly
#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)
# Initialize Qt resources from file resources.py
# Import the code for the dialog
import os.path
from .GeoDataFarm_dockwidget import GeoDataFarmDockWidget
from qgis.core import QgsApplication
from PyQt5 import QtGui
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtWidgets import QAction, QMessageBox, QApplication, QListWidgetItem
from PyQt5.QtGui import QIcon, QImage
from psycopg2 import IntegrityError
import os
import sys
import subprocess
import platform
import webbrowser
from .resources import *
plugin_dir = os.path.dirname(__file__)

try:
    import matplotlib
except ModuleNotFoundError:
    print('installing matplotlib')
    if platform.system() == 'Windows':
        subprocess.call([sys.exec_prefix + '/python', "-m", 'pip', 'install', 'matplotlib'])
    else:
        subprocess.call(['python3', '-m', 'pip', 'install', 'matplotlib'])
    import matplotlib
    try:
        import matplotlib
        print('installation completed')
    except ModuleNotFoundError:
        QMessageBox.information(None, 'ERROR', "During the first startup this program there are some third party packages that is requried to be installed, they tries to be installed with pip but fails. If you can't get the plugin to work, don't hesitate to send an e-mail to geodatafarm@gmail.com and tell which os you are using and QGIS version.")

try:
    import reportlab
except ModuleNotFoundError:
    print('installing reportlab')
    if platform.system() == 'Windows':
        subprocess.call([sys.exec_prefix + '/python', "-m", 'pip', 'install', 'reportlab'])
    else:
        subprocess.call(['python3', '-m', 'pip', 'install', 'reportlab'])
    try:
        import reportlab
        print('installation completed')
    except ModuleNotFoundError:
        QMessageBox.information(None, 'ERROR', 'During the first startup this program is the python package Reportlab installed, this may require that you run QGIS with administration rights.')
# Import the code for the dock_widget and the subwidgets
from .database_scripts.db import DB
from .database_scripts.mean_analyse import Analyze
from .database_scripts.plan_ahead import PlanAhead
from .database_scripts.create_new_farm import CreateFarm
from .import_data.handle_irrigation import IrrigationHandler
from .import_data.save_planting_data import SavePlanting
from .import_data.save_fertilizing_data import SaveFertilizing
from .import_data.save_spraying_data import SaveSpraying
from .import_data.save_other_data import SaveOther
from .import_data.save_harvest_data import SaveHarvesting
from .import_data.save_plowing_data import SavePlowing
from .import_data.save_harrowing_data import SaveHarrowing
from .import_data.save_soil_data import SaveSoil
from .import_data.convert_harvest_to_area import ConvertToAreas
from .database_scripts.table_managment import TableManagement
from .support_scripts.create_layer import CreateLayer
from .support_scripts.create_guiding_file import CreateGuideFile
from .support_scripts.generate_reports import RapportGen
from .support_scripts.add_field import AddField
from .support_scripts.multiedit import MultiEdit
from .support_scripts.__init__ import isint, TR
from .support_scripts.populate_lists import Populate
from .support_scripts.add_layer_to_canvas import AddLayerToCanvas
from .support_scripts.fix_rows import RowFixer
from .import_data.satellite_data import SatelliteData


class GeoDataFarm:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        Parameters
        ----------
        iface: QgsInterface, An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.

        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        translate = TR()
        self.tr = translate.tr
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GeoDataFarm_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&GeoFarm')
        self.toolbar = self.iface.addToolBar(u'GeoDataFarm')
        self.toolbar.setObjectName(u'GeoDataFarm')
        self.tsk_mngr = QgsApplication.taskManager()

        #print "** INITIALIZING GeoDataFarm"
        self.items_in_table = None
        self.pluginIsActive = False
        self.dock_widget = None
        self.populate = None
        self.db = None
        self.IH = None
        self.df = None
        self.db = None
        self.add_field = None
        self.save_planting = None
        self.save_fertilizing = None
        self.save_spraying = None
        self.save_other = None
        self.save_harvesting = None
        self.save_plowing = None
        self.save_harrowing = None
        self.save_soil = None
        self.plan_ahead = None
        self.report_generator = None

    # noinspection PyMethodMayBeStatic

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                   add_to_menu=True, add_to_toolbar=True, status_tip=None,
                   whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar.

        Parameters
        ----------
        icon_path: str
            Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        text: str
            Text that should be shown in menu items for this action.
        callback: function
            Function to be called when the action is triggered.
        enabled_flag: bool
            A flag indicating if the action should be enabled
            by default. Defaults to True.
        add_to_menu: bool
            Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        add_to_toolbar: bool
            Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        status_tip: str
            Optional text to show in a popup when mouse pointer
            hovers over the action.
        parent: QWidget
            Parent widget for the new action. Defaults None.
        whats_this: str
            Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        Returns
        -------
        QAction
            The action that was created. Note that the action is also
            added to self.actions list.

        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/GeoDataFarm/img/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'GeoDataFarm'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dock_widget is closed"""
        self.dock_widget.closingPlugin.disconnect(self.onClosePlugin)
        self.pluginIsActive = False

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        #print "** UNLOAD GeoDataFarm"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&GeoFarm'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    # Functions create specific for GeoDataFarm-----------------------------
    def add_selected_tables(self):
        """Adds a layer for each "parameter" of all selected tables"""
        add_layer_to_canvas = AddLayerToCanvas(self)
        add_layer_to_canvas.run()

    def reload_layer(self):
        """Reloads a layer be create a CreateLayer object and call
        the function repaint_layer"""
        create_layer = CreateLayer(self.db, self.dock_widget)
        create_layer.repaint_layer()

    def reload_range(self):
        """Reload the range of the lowest and highest value of the layer"""
        cb = self.dock_widget.mMapLayerComboBox
        layer = cb.currentLayer()
        if layer is not None:
            try:
                lv = layer.renderer().ranges()[0].lowerValue()
                hv = layer.renderer().ranges()[-1].upperValue()
                nbr_cat = len(layer.renderer().ranges())
                self.dock_widget.LEMinColor.setText(str(lv))
                self.dock_widget.LEMaxColor.setText(str(hv))
                self.dock_widget.LEMaxNbrColor.setText(str(nbr_cat))
            except AttributeError:
                pass

    def run_analyse(self):
        """Gathers the parameters and start the analyse dialog"""
        names = []
        harvest_file = False
        input_file = False
        self.items_in_table = self.populate.get_items_in_table()
        self.lw_list = self.populate.get_lw_list()
        for i, (lw, schema) in enumerate(self.lw_list):
            for item in self.items_in_table[i][0]:
                if (item.checkState() == 2 and
                        self.db.check_table_exists(item.text(), schema, False)):
                    if schema == 'harvest':
                        harvest_file = True
                    if schema == 'plant' or schema == 'soil' or schema == 'spray' or schema == 'ferti' or schema == 'weather':
                        input_file = True
                    names.append([schema, item.text()])
        if harvest_file and input_file:
            analyse = Analyze(self, names)
            if analyse.check_consistency():
                analyse.default_layout()
                analyse.run()
            else:
                return
        else:
            QMessageBox.information(None, self.tr("Error:"),
                                    self.tr('You need to have at least one input (activity or soil) and one harvest data set selected.'))

    def _q_replace_db_data(self, tbl=None):
        """Function that might be removed after the full support for shape files
        """
        schema = self.dock_widget.CBDataType.currentText()
        tables_in_db = self.db.get_tables_in_db(schema=schema)
        if tbl is not None:
            tbl_name = tbl
        else:
            tbl_name = str(self.IH.file_name)
        tbls = []
        for row in tables_in_db:
            tbls.append(str(row[0]))
        if isint(tbl_name[0]):
            tbl_name = '_' + tbl_name
        if tbl_name in tbls:
            qm = QMessageBox()
            ret = qm.question(None, 'Message',
                              self.tr("The name of the data set already exist in your database, would you like to replace it?"),
                              qm.Yes, qm.No)
            if ret == qm.No:
                return False
            else:
                self.db.execute_sql(
                    "DROP TABLE {schema}.{tbl}".format(schema=schema,
                                                       tbl=tbl_name))
                return True
        else:
            return True

    def tbl_mgmt(self):
        """Open the table manager widget"""
        tabel_mgmt = TableManagement(self)
        tabel_mgmt.run()

    def multi_edit(self):
        """Opens the multi edit widget"""
        me = MultiEdit(self)
        me.show()

    def import_irrigation(self):
        """Opens the irrigation handler widget"""
        irr = IrrigationHandler(self)
        irr.run()

    def create_guide(self):
        """Opens the create guide file widget"""
        guide = CreateGuideFile(self)
        guide.run()

    def get_database_connection(self):
        """Connects to the database and create the db object"""
        self.db = DB(self.dock_widget, path=self.plugin_dir)
        connected = self.db.get_conn()
        if not connected:
            QMessageBox.information(None, "Information:", self.tr("Welcome to GeoDataFarm, this is a plugin still under development, if you have any suggestions of imporvements or don't understand some parts please do send a e-mail to me at geodatafarm@gmail.com"))
            return False
        return True

    def add_crop(self):
        """Adds a crop to the database"""
        crop_name = self.dock_widget.LECropName.text()
        if len(crop_name) == 0:
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Crop name must be filled in.'))
            return
        sql = """Insert into crops (crop_name) 
                VALUES ('{name}')""".format(name=crop_name)
        r_value = self.db.execute_sql(sql, return_failure=True)
        if r_value is IntegrityError:

            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Crop name already exist, please select a new name'))
            return
        _name = QApplication.translate("qadashboard", crop_name, None)
        item = QListWidgetItem(_name, self.dock_widget.LWCrops)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.Unchecked)
        self.populate.reload_crops()

    def remove_crop_name(self):
        for i in range(self.dock_widget.LWCrops.count()):
            item = self.dock_widget.LWCrops.item(i)
            if item.checkState() == 2:
                sql = "delete from crops where crop_name = '{n}'".format(n=item.text())
                self.db.execute_sql(sql)
        self.populate.reload_crops()

    def clicked_create_farm(self):
        """Connects the docked widget with the CreateFarm script and starts
        the create_farm widget"""
        create_farm = CreateFarm(self, True)
        create_farm.run()

    def connect_to_farm(self):
        """Connects the docked widget with the CreateFarm script and starts
        the connect to farm widget"""
        create_farm = CreateFarm(self, False)
        create_farm.run()

    def fix_rows(self):
        RowFixer(self)

    def run_interpolate_harvest(self):
        cta = ConvertToAreas(self)
        cta.run()

    def set_buttons(self):
        """Since most functions are dependent on that a database connections
        exist the buttons are set when a connection is set. If new connections
        are added here do not forget to add them in create_new_farms function
        that resets the database connection"""
        if self.populate is None:
            self.populate = Populate(self)
            self.dock_widget.PBOpenRD.clicked.connect(self.import_irrigation)
            self.dock_widget.PBUpdateLists.clicked.connect(self.populate.update_table_list)
            self.save_planting = SavePlanting(self)
            self.satellite_data = SatelliteData(self)
            self.satellite_data.set_widget_connections()
            self.save_planting.set_widget_connections()
            self.save_fertilizing = SaveFertilizing(self)
            self.save_fertilizing.set_widget_connections()
            self.report_generator = RapportGen(self)
            self.report_generator.set_widget_connections()
            self.add_field = AddField(self)
            self.add_field.set_widget_connections()
            self.plan_ahead = PlanAhead(self)
            self.plan_ahead.set_widget_connections()
            self.save_spraying = SaveSpraying(self)
            self.save_spraying.set_widget_connections()
            self.save_other = SaveOther(self)
            self.save_other.set_widget_connections()
            self.save_harvesting = SaveHarvesting(self)
            self.save_harvesting.set_widget_connections()
            self.save_plowing = SavePlowing(self)
            self.save_plowing.set_widget_connections()
            self.save_harrowing = SaveHarrowing(self)
            self.save_harrowing.set_widget_connections()
            self.save_soil = SaveSoil(self)
            self.save_soil.set_widget_connections()
            self.dock_widget.PBAddCrop.clicked.connect(self.add_crop)
            self.dock_widget.PBRemoveCrop.clicked.connect(self.remove_crop_name)
            self.dock_widget.PBMultiEdit.clicked.connect(self.multi_edit)
            self.dock_widget.PBReloadLayer.clicked.connect(self.reload_layer)
            self.dock_widget.PBEditTables.clicked.connect(self.tbl_mgmt)
            self.dock_widget.PBCreateGuide.clicked.connect(self.create_guide)
            self.dock_widget.PBFixRows.clicked.connect(self.fix_rows)
            self.dock_widget.PBRunAnalyses.clicked.connect(self.run_analyse)
            self.dock_widget.PBAdd2Canvas.clicked.connect(self.add_selected_tables)
            self.dock_widget.PBWebbpage.clicked.connect(lambda: webbrowser.open('http://www.geodatafarm.com/'))
            self.dock_widget.PBHvInterpolateData.clicked.connect(self.run_interpolate_harvest)

    def run(self):
        """Run method that loads and starts the plugin"""
        icon_path = ':/plugins/GeoDataFarm/img/icon.png'
        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING GeoDataFarm"

            # dock_widget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dock_widget is None:
                # Create the dock_widget (after translation) and keep reference
                self.dock_widget = GeoDataFarmDockWidget()
                img = QImage(icon_path)
                pimg = QtGui.QPixmap.fromImage(img).scaled(91, 91,
                                                                QtCore.Qt.KeepAspectRatio)
                self.dock_widget.LIcon.setPixmap(pimg)
            if self.get_database_connection():
                self.set_buttons()
            self.dock_widget.PBAddNewFarm.clicked.connect(self.clicked_create_farm)
            self.dock_widget.PBConnect2Farm.clicked.connect(self.connect_to_farm)
            try:
                self.reload_range()
            except:
                pass
            self.dock_widget.mMapLayerComboBox.currentIndexChanged.connect(self.reload_range)
            # show the dock_widget
            # connect to provide cleanup on closing of dock_widget
            self.dock_widget.closingPlugin.connect(self.onClosePlugin)
            #self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
            self.dock_widget.show()
