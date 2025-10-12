from typing import TYPE_CHECKING, Iterator, Self
if TYPE_CHECKING:
    import geodatafarm.GeoDataFarm
    import pytest_qgis.qgis_interface
import sys
import os
sys.path.append(os.path.abspath(os.path.curdir))
import pytest
from pytest_qgis import qgis_iface
class actionAddFeature:
    def trigger(self: Self) -> None:
        pass
class actionSaveActiveLayerEdits:
    def trigger(self: Self) -> None:
        pass
class actionToggleEditing:
    def trigger(self: Self) -> None:
        pass

from qgis.PyQt.QtCore import QSettings, QDate

from ..GeoDataFarm import GeoDataFarm
from ..database_scripts.db import DB

QSettings().setValue('locale/userLocale', 'se')
RESET_USER = 'test_user'
RESET_PASSWORD = 'test_password'


@pytest.fixture(scope='session', autouse=True)
def gdf(qgis_iface: "pytest_qgis.qgis_interface.QgisInterface") -> "Iterator[geodatafarm.GeoDataFarm.GeoDataFarm]":
    qgis_iface.actionAddFeature = actionAddFeature
    qgis_iface.actionSaveActiveLayerEdits = actionSaveActiveLayerEdits
    qgis_iface.actionToggleEditing = actionToggleEditing
    gdf = GeoDataFarm(qgis_iface, True)
    # create_new_farm(gdf)
    connect_2_farm(gdf)
    yield gdf
    #delete_farm()

def create_new_farm(gdf: GeoDataFarm):
    gdf.run()
    cf = gdf.clicked_create_farm()
    cf.CF.user_name.setText('pytest_user')
    cf.CF.pass_word.setText('pytest_pass')
    cf.CF.farm_name.setText('pytest_farm')
    cf.CF.email_field.setText('pytest@test.com')
    cf.CF.DEFirstYear.setDate(QDate.fromString('2020-01-01', 'yyyy-MM-dd'))
    suc1 = cf.create_new_farm()
    suc2 = gdf.db.execute_sql(f'GRANT ALL ON DATABASE pytest_farm TO {RESET_USER};', return_failure=True)
    suc3 = gdf.db.execute_sql(f'GRANT pytest_user TO {RESET_USER} WITH ADMIN OPTION;', return_failure=True)
    # assert all([suc1, suc2[0], suc3[0]])

def connect_2_farm(gdf: GeoDataFarm) -> None:
    gdf.test_mode = True
    gdf.run()
    cf = gdf.clicked_create_farm()
    cf.CF.user_name.setText('pytest_user')
    cf.CF.pass_word.setText('pytest_pass')
    cf.CF.farm_name.setText('pytest_farm')
    cf.connect_to_source()
    suc = gdf.db.execute_sql(f'GRANT ALL ON DATABASE pytest_farm TO {RESET_USER};', return_failure=True)
    suc = gdf.db.execute_sql(f'GRANT ALL ON USER pytest_user TO {RESET_USER};', return_failure=True)
    # assert suc
    # assert 'pytest' in gdf.dock_widget.LFarmName.text()

def delete_farm():
    db = DB(dbname='postgres', dbuser=RESET_USER, dbpass=RESET_PASSWORD)

    suc = db.execute_sql('DROP Database pytest_farm', return_failure=True)
    suc2 = db.execute_sql('DROP USER pytest_user', return_failure=True)
    # assert all([suc[0], suc2[0]])
