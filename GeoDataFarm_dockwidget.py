# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GeoDataFarmDockWidget
                                 A QGIS plugin
 This is a plugin that aims to determine the yield impact of different parameters
                             -------------------
        begin                : 2016-10-24
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Axel Horteborn
        email                : axel.n.c.andersson@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from typing import Self

import os

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCalendarWidget, QCheckBox, QComboBox, QDateEdit, QFrame, QGroupBox,
    QLabel, QLineEdit, QListWidget, QPlainTextEdit, QPushButton, QRadioButton,
    QTableWidget, QTabWidget, QVBoxLayout, QWidget
)
from qgis.gui import QgsMapLayerComboBox

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'GeoDataFarm_dockwidget_base.ui'))


class GeoDataFarmDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    """GeoDataFarm dock widget with type hints for all UI elements.

    All UI elements are defined in GeoDataFarm_dockwidget_base.ui and loaded via uic.
    Type hints below provide IDE autocompletion and type checking support.
    """

    # ==================== Main Tab Widget ====================
    tabWidget: QTabWidget

    # ==================== Tab: Your Farm (tab_4) ====================
    PBConnect2Farm: QPushButton
    PBAddNewFarm: QPushButton
    PBViewFields: QPushButton
    PBAddField: QPushButton
    PBAddShapeField: QPushButton
    PBAddIsoField: QPushButton
    PBRemoveField: QPushButton
    PBWebbpage: QPushButton
    PBAddCrop: QPushButton
    PBRemoveCrop: QPushButton
    LWFields: QListWidget
    LWCrops: QListWidget
    LECropName: QLineEdit
    LFarmName: QLabel
    Label3: QLabel
    Label3_2: QLabel
    LIcon: QLabel
    label_5: QLabel

    # ==================== Tab: Import data (tab_5) ====================
    tabWidget_2: QTabWidget
    label_112: QLabel

    # ------ Sub-tab: Planting (tab_6) ------
    DEPlanting: QCalendarWidget
    CBPFileType: QComboBox
    CBPCrop: QComboBox
    CBPField: QComboBox
    LEPSeedRate: QLineEdit
    LEPSawDepth: QLineEdit
    LEPVarerity: QLineEdit
    LEPSpacing: QLineEdit
    LEPOther: QPlainTextEdit
    PBPAddFile: QPushButton
    PBPSaveManual: QPushButton
    label_10: QLabel
    label_11: QLabel
    label_12: QLabel
    label_13: QLabel
    label_14: QLabel
    label_15: QLabel
    label_16: QLabel
    label_103: QLabel
    label_105: QLabel
    label_107: QLabel
    label_108: QLabel

    # ------ Sub-tab: Fertilizing (tab_7) ------
    DEFertilizing: QCalendarWidget
    CBFFileType: QComboBox
    CBFCrop: QComboBox
    CBFField: QComboBox
    LEFSeedRate: QLineEdit
    LEFSawDepth: QLineEdit
    LEFVarerity: QLineEdit
    LEFOther: QPlainTextEdit
    PBFAddFile: QPushButton
    PBFSaveManual: QPushButton
    label_20: QLabel
    label_23: QLabel
    label_24: QLabel
    label_25: QLabel
    label_26: QLabel
    label_28: QLabel
    label_29: QLabel
    label_104: QLabel
    label_109: QLabel

    # ------ Sub-tab: Spraying (tab_8) ------
    DESpraying: QCalendarWidget
    CBSpFileType: QComboBox
    CBSpCrop: QComboBox
    CBSpField: QComboBox
    LESpRate: QLineEdit
    LESpVarerity: QLineEdit
    LESpWindSpeed: QLineEdit
    LESpWindDir: QLineEdit
    LESpOther: QPlainTextEdit
    PBSpAddFile: QPushButton
    PBSpSaveManual: QPushButton
    label_30: QLabel
    label_33: QLabel
    label_34: QLabel
    label_35: QLabel
    label_36: QLabel
    label_37: QLabel
    label_38: QLabel
    label_39: QLabel
    label_59: QLabel
    label_100: QLabel
    label_101: QLabel

    # ------ Sub-tab: Other (tab_9) ------
    DEOther: QCalendarWidget
    CBOField: QComboBox
    CBOCrop: QComboBox
    LEOtherName: QLineEdit
    LEOOption_1: QLineEdit
    LEOOption_2: QLineEdit
    LEOOption_3: QLineEdit
    LEOOption_4: QLineEdit
    LEOValue_1: QLineEdit
    LEOValue_2: QLineEdit
    LEOValue_3: QLineEdit
    LEOValue_4: QLineEdit
    LEOUnit_1: QLineEdit
    LEOUnit_2: QLineEdit
    LEOUnit_3: QLineEdit
    LEOUnit_4: QLineEdit
    LEOOther: QPlainTextEdit
    PBSaveOther: QPushButton
    label_44: QLabel
    label_46: QLabel
    label_48: QLabel
    label_71: QLabel
    label_73: QLabel
    label_77: QLabel

    # ------ Sub-tab: Harvest (tab_12) ------
    DEHarvest: QCalendarWidget
    CBHvFileType: QComboBox
    CBHvCrop: QComboBox
    CBHvField: QComboBox
    LEHvYield: QLineEdit
    LEHvTotalYield: QLineEdit
    LEHvOther: QPlainTextEdit
    PBHvAddFile: QPushButton
    PBHvSaveManual: QPushButton
    PBHvInterpolateData: QPushButton
    label_43: QLabel
    label_50: QLabel
    label_51: QLabel
    label_52: QLabel
    label_54: QLabel
    label_55: QLabel
    label_56: QLabel
    label_57: QLabel
    label_58: QLabel

    # ------ Sub-tab: Plowing (tab_10) ------
    DEPlowing: QCalendarWidget
    CBPloField: QComboBox
    LEPloDepth: QLineEdit
    LEPloOther: QPlainTextEdit
    PBPloSaveManual: QPushButton
    label_62: QLabel
    label_63: QLabel
    label_66: QLabel
    label_68: QLabel
    label_69: QLabel

    # ------ Sub-tab: Harrowing (tab_11) ------
    DEHarrowing: QCalendarWidget
    CBHwField: QComboBox
    LEHwDepth: QLineEdit
    LEHwOther: QPlainTextEdit
    PBHwSaveManual: QPushButton
    label_70: QLabel
    label_72: QLabel
    label_75: QLabel
    label_76: QLabel
    label_78: QLabel

    # ------ Sub-tab: Irrigation (tab_13) ------
    DEIrrigation: QDateEdit
    CBIField: QComboBox
    LEPSpacing_8: QLineEdit
    LEPOther_8: QPlainTextEdit
    PBOpenRD: QPushButton
    PBAddFieldToDB_9: QPushButton
    label_74: QLabel
    label_82: QLabel
    label_83: QLabel
    label_84: QLabel
    label_87: QLabel
    label_110: QLabel

    # ------ Sub-tab: Weather (tab_14) ------
    label_65: QLabel

    # ------ Sub-tab: Soil (tab_15) ------
    DESoil: QCalendarWidget
    CBSoFileType: QComboBox
    CBSoField: QComboBox
    LESoClay: QLineEdit
    LESoHumus: QLineEdit
    LESoPh: QLineEdit
    LESoRx: QLineEdit
    LESoOther: QPlainTextEdit
    PBSoAddFile: QPushButton
    PBSoSaveManual: QPushButton
    label_91: QLabel
    label_92: QLabel
    label_93: QLabel
    label_94: QLabel
    label_95: QLabel
    label_96: QLabel
    label_97: QLabel
    label_98: QLabel
    label_99: QLabel
    label_102: QLabel
    label_106: QLabel
    label_111: QLabel

    # ==================== Tab: View Data (tab_2) ====================
    LWPlantingTable: QListWidget
    LWFertiTable: QListWidget
    LWSprayingTable: QListWidget
    LWHarvestTable: QListWidget
    LWOtherTable: QListWidget
    LWSoilTable: QListWidget
    LWWeatherTable: QListWidget
    PBAdd2Canvas: QPushButton
    PBEditTables: QPushButton
    PBUpdateLists: QPushButton
    PBRunAnalyses: QPushButton
    groupBox_2: QGroupBox
    RBSelectAllYears: QRadioButton
    RBSpecificYear: QRadioButton
    DEYear: QDateEdit
    LActivity: QLabel
    LActivity_2: QLabel
    LActivity_3: QLabel
    LActivity_4: QLabel
    LActivity_5: QLabel
    Lsoil: QLabel
    Lsoil_3: QLabel
    label_7: QLabel
    label_113: QLabel

    # ==================== Tab: Guide file / NDVI (tab_16) ====================
    CBFieldList: QComboBox
    CWPlannedDate: QCalendarWidget
    LEVal_1: QLineEdit
    LEVal_2: QLineEdit
    LEVal_3: QLineEdit
    LEVal_4: QLineEdit
    LEVal_5: QLineEdit
    QWGraphArea: QWidget
    PBListCropstat: QPushButton
    PBListGeoDataFarm: QPushButton
    PBListEOBrowser: QPushButton
    PBUpdateFieldList: QPushButton
    PBSelectZipFile: QPushButton
    PBGenerateGuideFile: QPushButton
    PBUpdateGraph: QPushButton
    CheckBPlanned: QCheckBox
    groupBox_5: QGroupBox
    RBNdviIndex: QRadioButton
    RBMsavi2Index: QRadioButton
    LVal_1: QLabel
    LVal_2: QLabel
    LVal_3: QLabel
    LVal_4: QLabel
    LVal_5: QLabel
    label_22: QLabel
    label_27: QLabel
    label_31: QLabel
    label_32: QLabel
    label_42: QLabel

    # ==================== Tab: Edit layer (tab) ====================
    mMapLayerComboBox: QgsMapLayerComboBox
    LEMinColor: QLineEdit
    LEMaxColor: QLineEdit
    LEMaxNbrColor: QLineEdit
    PBReloadLayer: QPushButton
    PBCreateGuide: QPushButton
    PBMultiEdit: QPushButton
    PBDropUnReal: QPushButton
    PBRescaleValues: QPushButton
    PBFixRows: QPushButton
    groupBox: QGroupBox
    RBNomalized: QRadioButton
    RBEvenly: QRadioButton
    label: QLabel
    label_2: QLabel
    label_3: QLabel
    label_4: QLabel
    label_6: QLabel
    label_8: QLabel
    label_9: QLabel
    label_19: QLabel
    label_21: QLabel
    label_40: QLabel
    label_41: QLabel
    label_45: QLabel
    label_47: QLabel
    label_49: QLabel
    label_53: QLabel

    # ==================== Tab: Report (tab_3) ====================
    PBReportPerField: QPushButton
    PBReportPerCrop: QPushButton
    PBReportPerOperation: QPushButton
    PBReportSelectFolder: QPushButton
    RBReportWithDetails: QRadioButton
    RBReportWithoutDetails: QRadioButton
    groupBox_3: QGroupBox
    RBAllYear: QRadioButton
    RBSpecYear: QRadioButton
    DEReportYear: QDateEdit
    groupBox_4: QGroupBox
    CBPlanting: QCheckBox
    CBSpraying: QCheckBox
    CBFertilizing: QCheckBox
    CBHarvest: QCheckBox
    CBPlowing: QCheckBox
    CBHarrowing: QCheckBox
    CBSoil: QCheckBox
    CBOther: QCheckBox
    CBIrrigation: QCheckBox
    CBWeather: QCheckBox
    label_17: QLabel
    label_18: QLabel

    # ==================== Tab: Plan (tab_31) ====================
    TWPlan: QTableWidget
    LWPlanSummary: QListWidget
    DEPlanYear: QDateEdit
    PBSavePlan: QPushButton
    PBViewPlan: QPushButton
    PBUpdatePlaning: QPushButton
    PBUpdateSummary: QPushButton
    LPlanSummaryLabel: QLabel
    label_174: QLabel

    # ==================== Tab: Generate ISOXML (tab_generate_isoxml) ====================
    tabWidgetGenerateIsoxml: QTabWidget

    # ------ Sub-tab: Recipe (tabRecipe) ------
    tableRecipe: QTableWidget
    btnNewRecipe: QPushButton
    btnLoadRecipe: QPushButton
    btnLoadSelected: QPushButton
    btnResetRecipe: QPushButton
    btnRefreshRecipes: QPushButton
    btnCreateFile: QPushButton
    frameRecipeContent: QFrame
    layoutRecipeContent: QVBoxLayout
    labelRecipeIntro: QLabel

    # ------ Sub-tab: Farm (tabFarm) ------
    tableFarm: QTableWidget
    btnAddFarm: QPushButton
    btnEditFarm: QPushButton
    btnRemoveFarm: QPushButton

    # ------ Sub-tab: Customer (tabCustomer) ------
    tableCustomer: QTableWidget
    btnAddCustomer: QPushButton
    btnEditCustomer: QPushButton
    btnRemoveCustomer: QPushButton

    # ------ Sub-tab: Worker (tabWorker) ------
    tableWorker: QTableWidget
    btnAddWorker: QPushButton
    btnEditWorker: QPushButton
    btnRemoveWorker: QPushButton

    # ------ Sub-tab: Device (tabDevice) ------
    tableDevice: QTableWidget
    btnAddDevice: QPushButton
    btnEditDevice: QPushButton
    btnRemoveDevice: QPushButton

    # ------ Sub-tab: Product (tabProduct) ------
    tableProduct: QTableWidget
    btnAddProduct: QPushButton
    btnEditProduct: QPushButton
    btnRemoveProduct: QPushButton

    # ------ Sub-tab: ProductGroup (tabProductGroup) ------
    tableProductGroup: QTableWidget
    btnAddProductGroup: QPushButton
    btnEditProductGroup: QPushButton
    btnRemoveProductGroup: QPushButton

    # ------ Sub-tab: ValuePresentation (tabValuePresentation) ------
    tableValuePresentation: QTableWidget
    btnAddValuePresentation: QPushButton
    btnEditValuePresentation: QPushButton
    btnRemoveValuePresentation: QPushButton

    # ------ Sub-tab: CulturalPractice (tabCulturalPractice) ------
    tableCulturalPractice: QTableWidget
    btnAddCulturalPractice: QPushButton
    btnEditCulturalPractice: QPushButton
    btnRemoveCulturalPractice: QPushButton

    # ------ Sub-tab: OperationTechnique (tabOperationTechnique) ------
    tableOperationTechnique: QTableWidget
    btnAddOperationTechnique: QPushButton
    btnEditOperationTechnique: QPushButton
    btnRemoveOperationTechnique: QPushButton

    # ------ Sub-tab: CropType (tabCropType) ------
    tableCropType: QTableWidget
    btnAddCropType: QPushButton
    btnEditCropType: QPushButton
    btnRemoveCropType: QPushButton

    # ------ Sub-tab: CodedCommentGroup (tabCodedCommentGroup) ------
    tableCodedCommentGroup: QTableWidget
    btnAddCodedCommentGroup: QPushButton
    btnEditCodedCommentGroup: QPushButton
    btnRemoveCodedCommentGroup: QPushButton

    closingPlugin = pyqtSignal()

    def __init__(self: Self, parent: None=None) -> None:
        """Constructor."""
        super(GeoDataFarmDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # Initialize the Generate ISOXML tab controller
        self._setup_generate_isoxml_controller()

    def _setup_generate_isoxml_controller(self):
        """Initialize the controller for the static Generate ISOXML tabs."""
        try:
            try:
                from .support_scripts.pyagriculture.generate_taskdata_widgets import GenerateIsoxmlController
            except ImportError:
                from support_scripts.pyagriculture.generate_taskdata_widgets import GenerateIsoxmlController

            # Create controller that wires up the static UI elements
            self.generate_isoxml_controller = GenerateIsoxmlController(self, parent_gdf=None)
        except Exception as e:
            print(f"ERROR setting up GenerateIsoxmlController: {e}")
            import traceback
            traceback.print_exc()

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

