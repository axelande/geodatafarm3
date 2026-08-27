from typing import TYPE_CHECKING, Iterator, Self
if TYPE_CHECKING:
    import geodatafarm.GeoDataFarm
    import pytest_qgis.qgis_interface
import sys
import os
sys.path.append(os.path.abspath(os.path.curdir))
import pytest

# Try to import pytest_qgis, but allow tests to run without it
try:
    from pytest_qgis import qgis_iface
except ImportError:
    qgis_iface = None

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

# Try to import GeoDataFarm, but allow standalone tests to run without it
# This can fail if the UI file has parsing issues
GeoDataFarm = None
DB = None
try:
    from ..GeoDataFarm import GeoDataFarm
    from ..database_scripts.db import DB
except (ImportError, SyntaxError) as e:
    # UI parsing can fail in some Qt environments; allow lightweight tests to continue
    import warnings
    warnings.warn(f"Could not import GeoDataFarm (likely UI parsing issue): {e}")

try:
    QSettings().setValue('locale/userLocale', 'se')
except Exception:
    pass
RESET_USER = 'test_user'
RESET_PASSWORD = 'test_password'
# The schemas add_schemas() lays down, and the year add_tables() counts from.
FARM_SCHEMAS = ('plant', 'harvest', 'other', 'soil', 'weather', 'spray', 'ferti')
FIRST_YEAR = 2020
# Set GDF_KEEP_TEST_DATA=1 to run against whatever the last run left behind.
KEEP_TEST_DATA = os.environ.get('GDF_KEEP_TEST_DATA') == '1'
# The gdf fixture below says scope='session', but it is defined here and
# imported into each test module, so pytest registers one fixture per
# module and sets it up once per module. Anything destructive must guard
# itself, or it runs again halfway through the suite and throws away what
# the modules before it built - which is why delete_farm() and
# create_new_farm() sit commented out rather than in the fixture.
_farm_emptied = False
# Every table the farm login owns, across its schemas and public. Written as a
# sweep rather than a list because features keep adding tables of their own
# (journal_fields did), and a list would quietly go stale again.
#
# Ownership is what marks a table as ours to throw away: public belongs to
# postgres and holds tables this login may not even read (user_meta_data), and
# spatial_ref_sys belongs to postgis. Each drop is guarded on its own so that
# one table refusing cannot abandon the rest.
#
# The schemas themselves are never dropped. pytest_user has no CREATE on the
# database - the schemas were made for it when the farm was created - so
# dropping one is a one way door that no test run could open again.
DROP_FARM_TABLES = """
DO $$
DECLARE
    tbl record;
BEGIN
    FOR tbl IN
        SELECT c.oid::regclass AS name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ({schemas})
          AND c.relkind = 'r'
          AND pg_get_userbyid(c.relowner) = current_user
          AND NOT EXISTS (SELECT 1 FROM pg_depend d
                          WHERE d.objid = c.oid AND d.deptype = 'e')
          AND c.relname NOT IN ('spatial_ref_sys', 'geometry_columns',
                                'geography_columns', 'raster_columns',
                                'raster_overviews')
    LOOP
        BEGIN
            EXECUTE format('DROP TABLE IF EXISTS %s CASCADE', tbl.name);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'left % alone: %', tbl.name, SQLERRM;
        END;
    END LOOP;
END $$;
""".format(schemas=', '.join(f"'{s}'" for s in ('public',) + FARM_SCHEMAS))


@pytest.fixture(scope='session', autouse=True)
def gdf(qgis_iface: "pytest_qgis.qgis_interface.QgisInterface") -> "Iterator[geodatafarm.GeoDataFarm.GeoDataFarm]":
    qgis_iface.actionAddFeature = actionAddFeature
    qgis_iface.actionSaveActiveLayerEdits = actionSaveActiveLayerEdits
    qgis_iface.actionToggleEditing = actionToggleEditing
    gdf = GeoDataFarm(qgis_iface, True)
    global _farm_emptied
    cf = connect_2_farm(gdf)
    if not KEEP_TEST_DATA and not _farm_emptied:
        _farm_emptied = True
        empty_farm(gdf, cf)
        # Connecting read the farm's tables, fields and crops into the plugin,
        # and that happened before they were thrown away and rebuilt. Connect
        # again so it works from what is actually in the farm now rather than
        # from the tables it saw a moment ago.
        connect_2_farm(gdf)
    yield gdf

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
    return cf


def empty_farm(gdf: GeoDataFarm, cf) -> None:
    """Put the farm back to how it looks the day it is created.

    Called once for the whole suite - see _farm_emptied - because the fixture
    that calls it is set up again for every test module.

    The suite builds every field, crop and dataset it needs, so anything a
    previous run left behind only makes this one differ from it - a journal
    field some dialog test added, an import table whose rows were never
    replaced. Those leftovers surface much later as puzzling failures in
    tests that never touched them.

    The farm itself, its login and its schemas are left alone on purpose.
    Creating a farm goes through geodatafarm.com and mails the owner, which
    has no business happening on every test run, and the login cannot create
    a schema it has dropped - it holds no CREATE on the database, the schemas
    were made for it when the farm was created. Only the tables it owns are
    thrown away, and the plugin's own setup code puts them straight back.
    """
    gdf.db.execute_sql(DROP_FARM_TABLES, return_failure=True)
    cf.add_tables(FIRST_YEAR)
    cf.create_spec_functions()

def delete_farm():
    db = DB(dbname='postgres', dbuser=RESET_USER, dbpass=RESET_PASSWORD)

    suc = db.execute_sql('DROP Database pytest_farm', return_failure=True)
    suc2 = db.execute_sql('DROP USER pytest_user', return_failure=True)
    # assert all([suc[0], suc2[0]])
