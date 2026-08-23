from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtWidgets import (
    QComboBox, QCheckBox, QDateEdit, QDialog, QGridLayout, QLabel,
    QPushButton, QVBoxLayout)

__author__ = 'Axel Horteborn'


class WeatherDialog(QDialog):
    """Free weather import window, opened from the "Weather" card on the
    "Add data" page (see widgets/add_data_form.py's ``OPERATIONS['opWeather']``
    and GeoDataFarm.handle_add_data_action).

    Built directly in Python/Qt rather than loaded from a .ui file (same
    reasoning as widgets/crop_simulation_page.py). The Pro license key
    section lives on the "Crop simulation" tab instead - see
    ``database_scripts/crop_simulation.py``'s ``license_dlg``.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Weather import'))
        self.resize(520, 220)

        layout = QVBoxLayout(self)

        grid = QGridLayout()
        grid.addWidget(QLabel(self.tr('Field:')), 0, 0)
        self.CBWeatherField = QComboBox()
        grid.addWidget(self.CBWeatherField, 0, 1)
        self.PBWeatherUpdateFields = QPushButton(self.tr('Update field list'))
        grid.addWidget(self.PBWeatherUpdateFields, 0, 2)

        grid.addWidget(QLabel(self.tr('From:')), 1, 0)
        self.DEWeatherFrom = QDateEdit()
        self.DEWeatherFrom.setCalendarPopup(True)
        grid.addWidget(self.DEWeatherFrom, 1, 1)

        grid.addWidget(QLabel(self.tr('To:')), 2, 0)
        self.DEWeatherTo = QDateEdit()
        self.DEWeatherTo.setCalendarPopup(True)
        # Open-Meteo's historical archive has no data beyond today - block
        # picking a later date here rather than letting the fetch fail.
        self.DEWeatherTo.setMaximumDate(QDate.currentDate())
        grid.addWidget(self.DEWeatherTo, 2, 1)

        self.PBFetchWeather = QPushButton(self.tr('Fetch weather data'))
        grid.addWidget(self.PBFetchWeather, 3, 0)
        self.CBWeatherAllFields = QCheckBox(self.tr(
            'Apply to all fields (nearby fields share one fetch)'))
        grid.addWidget(self.CBWeatherAllFields, 3, 1, 1, 2)
        layout.addLayout(grid)

        self.LWeatherInfo = QLabel(self.tr(
            "Daily rainfall, mean temperature and reference evapotranspiration "
            "(ET0) are fetched from Open-Meteo's free historical archive "
            "(open-meteo.com) - no account needed. Fetched data is stored per "
            "field and year, and appears in the table list on the \"Data "
            "sets\" page; fetching again asks before replacing data you "
            "already have. Using this data in the yield analysis is a Pro "
            "feature - activate your license on the \"Farm & Fields\" page."))
        self.LWeatherInfo.setWordWrap(True)
        layout.addWidget(self.LWeatherInfo)
        layout.addStretch(1)
