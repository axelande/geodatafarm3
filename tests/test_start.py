from PyQt5 import QtCore
import pytest

from ..database_scripts.db import DB
from ..GeoDataFarm import GeoDataFarm
from . import gdf, RESET_USER, RESET_PASSWORD

@pytest.mark.skip('No need to test connection')
def test_startup(gdf):
    gdf.run()

@pytest.mark.skip('No need to create test_farm')
def test_create_new_farm(gdf):
    gdf.run()
    cf = gdf.clicked_create_farm()
    cf.CF.user_name.setText('pytest_user')
    cf.CF.pass_word.setText('pytest_pass')
    cf.CF.farm_name.setText('pytest_farm')
    cf.CF.email_field.setText('pytest@test.com')
    cf.CF.DEFirstYear.setDate(QtCore.QDate.fromString('2020-01-01', 'yyyy-MM-dd'))
    suc1 = cf.create_new_farm()
    suc2 = gdf.db.execute_sql(f'GRANT ALL ON DATABASE pytest_farm TO {RESET_USER};', return_failure=True)
    suc3 = gdf.db.execute_sql(f'GRANT pytest_user TO {RESET_USER} WITH ADMIN OPTION;', return_failure=True)
    assert all([suc1, suc2[0], suc3[0]])

@pytest.mark.skip('No need to create test_farm')
def test_connect_2_farm(gdf):
    gdf.run()
    cf = gdf.clicked_create_farm()
    cf.CF.user_name.setText('pytest_user')
    cf.CF.pass_word.setText('pytest_pass')
    cf.CF.farm_name.setText('pytest_farm')
    cf.connect_to_source()
    suc = gdf.db.execute_sql(f'GRANT ALL ON DATABASE pytest_farm TO {RESET_USER};', return_failure=True)
    suc = gdf.db.execute_sql(f'GRANT ALL ON USER pytest_user TO {RESET_USER};', return_failure=True)
    print(suc)
    assert suc
    assert 'pytest' in gdf.dock_widget.LFarmName.text()

@pytest.mark.skip('No need to create test_farm')
def test_delete_farm():
    #db = DB(dbname='pytest_farm', dbuser='pytest_user', dbpass='pytest_pass')
    #db.execute_sql(f'GRAMT ALL ON DATABASE pytest_farm TO {RESET_USER};')
    db = DB(dbname='postgres', dbuser=RESET_USER, dbpass=RESET_PASSWORD)

    suc = db.execute_sql('DROP Database pytest_farm', return_failure=True)
    suc2 = db.execute_sql('DROP USER pytest_user', return_failure=True)
    assert all([suc[0], suc2[0]])
