import hashlib
from qgis.PyQt.QtWidgets import QMessageBox, QListWidgetItem, QInputDialog
from qgis.PyQt.QtCore import Qt
from psycopg2.errors import UndefinedTable
import pytest
from unittest.mock import patch, MagicMock

from database_scripts.db import DB
from database_scripts.table_managment import TableManagement

@pytest.fixture
def db():
    return DB(test_mode=True)

@patch('database_scripts.db.QMessageBox')
def test_check_table_exists_table_not_exists(mock_QMessageBox, db):
    # Arrange
    db.execute_and_return = MagicMock(return_value=[[0]])

    # Act
    result = db.check_table_exists('non_existing_table', 'public')

    # Assert
    db.execute_and_return.assert_called_once()
    assert result == False

@patch('database_scripts.db.QMessageBox')
def test_check_table_exists_table_exists_no_replace(mock_QMessageBox, db):
    # Arrange
    db.execute_and_return = MagicMock(return_value=[[1]])
    mock_QMessageBox().question.return_value = mock_QMessageBox.No

    # Act
    result = db.check_table_exists('existing_table', 'public')

    # Assert
    db.execute_and_return.assert_called_once()
    mock_QMessageBox().question.assert_called_once()
    assert result is True

@patch('database_scripts.db.QMessageBox')
def test_check_table_exists_table_exists_replace(mock_QMessageBox, db):
    # Arrange
    db.execute_and_return = MagicMock(return_value=[[1]])
    db.execute_sql = MagicMock()
    mock_QMessageBox().question.return_value = mock_QMessageBox.Yes

    # Act
    result = db.check_table_exists('existing_table', 'public')

    # Assert
    db.execute_and_return.assert_called_once()
    mock_QMessageBox().question.assert_called_once()
    db.execute_sql.assert_called()
    assert result == False

@patch('database_scripts.db.QMessageBox')
def test_check_table_exists_no_ask_replace(mock_QMessageBox, db):
    # Arrange
    db.execute_and_return = MagicMock(return_value=[[1]])
    mock_QMessageBox().question.return_value = mock_QMessageBox.No

    # Act
    result = db.check_table_exists('existing_table', 'public', ask_replace=True)

    # Assert
    db.execute_and_return.assert_called_once()
    assert result == True

@patch('database_scripts.db.QMessageBox')
def test_execute_and_return_no_connection(mock_QMessageBox, db):
    # Arrange
    db._connect = MagicMock(return_value=False)
    mock_QMessageBox.information = mock_QMessageBox.ok

    # Act
    result = db.execute_and_return('SELECT 1', suppress_message=True)

    assert result == 'There was no connection established'

@patch('database_scripts.db.QMessageBox')
def test_execute_and_return_exception(mock_QMessageBox, db):
    # Arrange
    # Remove the mock for db._connect to connect to the real server
    db.dbuser = 'pytest_user'
    db.dbpass = hashlib.sha256('pytest_pass'.encode()).hexdigest()
    db.dbname = 'pytest_farm'
    db.test_mode = True
    db.set_conn(set_farm_name=False)

    # Act
    result = db.execute_and_return('SELECT 1 from non_existing_table', return_failure=True)

    # Assert
    assert isinstance(result[2], UndefinedTable)

@pytest.fixture
def table_management(db):
    parent = MagicMock()
    parent.db = db
    parent.dock_widget = MagicMock()
    parent.test_mode = True
    return TableManagement(parent)

def test_table_management_init(table_management):
    assert table_management.db is not None
    assert table_management.dock_widget is not None

def test_table_management_run(table_management):
    table_management.TMD.show = MagicMock()
    table_management.TMD.exec_ = MagicMock()
    table_management.run()
    table_management.TMD.show.assert_called_once()

def test_table_management_merge_tbls(table_management):
    table_management.items_in_table = [MagicMock(checkState=MagicMock(return_value=2), text=MagicMock(return_value='schema.table1')),
                                       MagicMock(checkState=MagicMock(return_value=2), text=MagicMock(return_value='schema.table2'))]
    table_management.TMD.LEName.text = MagicMock(return_value='new_table')
    table_management.TMD.CBDataType.currentText = MagicMock(return_value='plant')
    table_management.db.get_tables_in_db = MagicMock(return_value=[])
    table_management.db.execute_sql = MagicMock()
    table_management.db.update_row_id = MagicMock()
    table_management.db.create_indexes = MagicMock()
    table_management.update_table_list = MagicMock()

    table_management.merge_tbls()

    table_management.db.execute_sql.assert_called()
    table_management.db.update_row_id.assert_called_once_with('plant', 'new_table')
    table_management.db.create_indexes.assert_called_once_with('new_table', [], 'plant')
    table_management.update_table_list.assert_called_once()

def test_table_management_check_multiple(table_management):
    table_management.items_in_table = [MagicMock(checkState=MagicMock(return_value=2), text=MagicMock(return_value='schema.table'))]
    result, table = table_management.check_multiple()
    assert result == True
    assert table == 'schema.table'

def test_table_management_retrieve_params(table_management):
    table_management.check_multiple = MagicMock(return_value=(True, 'schema.table'))
    table_management.db.get_indexes = MagicMock(return_value={0: {'index_col': 'col1'}})
    table_management.db.get_all_columns = MagicMock(return_value=(['col1', 'col2']))
    table_management.TMD.SAParams.findItems = MagicMock(return_value=[])

    table_management.retrieve_params()

    assert table_management.params_in_list == 2

def test_table_management_save_table(table_management):
    table_management.current_table = 'table'
    table_management.current_schema = 'schema'
    table_management.params_in_table = [QListWidgetItem('col1'), QListWidgetItem('col2')]
    table_management.params_in_table[0].setCheckState(Qt.CheckState.Checked)
    table_management.params_in_table[1].setCheckState(Qt.CheckState.Unchecked)
    table_management.db.get_indexes = MagicMock(return_value={0: {'index_col': 'col2'}})
    table_management.db.execute_sql = MagicMock()

    table_management.save_table()

    table_management.db.execute_sql.assert_any_call("create index col1_schema_table on schema.table using btree(col1)")
    table_management.db.execute_sql.assert_any_call("DROP INDEX IF EXISTS schema.col2_schema_table")

@patch('database_scripts.db.QInputDialog')
def test_table_management_edit_tbl_name(mock_QInputDialog, table_management):
    table_management.items_in_table = [MagicMock(checkState=MagicMock(return_value=2), text=MagicMock(return_value='schema.table'))]
    table_management.db.execute_sql = MagicMock()
    table_management.update_table_list = MagicMock()
    QInputDialog.getText = MagicMock(return_value=('new_table', True))

    table_management.edit_tbl_name()

    table_management.db.execute_sql.assert_any_call("ALTER TABLE schema.table RENAME TO new_table")
    table_management.db.execute_sql.assert_any_call("Update schema.manual SET table_ = 'new_table' where table_ = 'table'")
    table_management.update_table_list.assert_called_once()

def test_table_management_edit_param_name(table_management):
    table_management.current_table = 'table'
    table_management.current_schema = 'schema'
    table_management.params_in_table = [MagicMock(text=MagicMock(return_value='col1'), checkState=MagicMock(return_value=2))]
    table_management.items_in_table = [MagicMock(text=MagicMock(return_value='schema.table'), checkState=MagicMock(return_value=2))]
    table_management.db.execute_sql = MagicMock()
    table_management.db.execute_and_return = MagicMock(return_value=[['tbl', 'index_idx', 'col1', 'schema']])
    table_management.db.get_indexes("table", "schema")
    QInputDialog.getText = MagicMock(return_value=('new_col', True))

    table_management.edit_param_name()

    table_management.db.execute_sql.assert_any_call("ALTER TABLE schema.table RENAME col1 TO new_col")
    table_management.db.execute_sql.assert_any_call("ALTER INDEX schema.col1_schema_table RENAME TO new_col_schema_table")

def test_table_management_update_table_list(table_management):
    table_management.parent.populate.get_lw_list = MagicMock(return_value=[(MagicMock(), 'schema')])
    table_management.db.get_tables_in_db = MagicMock(return_value=['table'])
    table_management.TMD.SATables.findItems = MagicMock(return_value=[])

    table_management.update_table_list()

    assert table_management.tables_in_db == 1

def test_table_management_remove_table_from_db(table_management):
    table_management.tables_in_db = 1
    mock_item = QListWidgetItem()
    mock_item.checkState = MagicMock(return_value=2)
    mock_item.text = MagicMock(return_value='schema.table')
    table_management.items_in_table = [mock_item]
    table_management.db.remove_table = MagicMock()
    table_management.TMD.SATables.findItems = MagicMock(return_value=[])

    table_management.remove_table_from_db()

    table_management.db.remove_table.assert_called_once_with('schema.table')
    assert table_management.tables_in_db == 0

def test_table_management_make_rows(table_management):
    table_management.check_multiple = MagicMock(return_value=(True, 'schema.table'))
    table_management.db.execute_and_return = MagicMock(return_value=[[1, 1, 1], [2, 1, 2]])
    table_management.parent.tsk_mngr.addTask = MagicMock()

    table_management.make_rows()

    table_management.parent.tsk_mngr.addTask.assert_called_once()

def test_table_management_split_rows(table_management):
    table_management.check_multiple = MagicMock(return_value=(True, 'harvest.table'))
    table_management.TMD.CBSplitYield.isChecked = MagicMock(return_value=True)
    table_management.TMD.CBColumns.currentText = MagicMock(return_value='yield_col')
    mock = MagicMock()
    mock.side_effect = [[[1], [2]],[[1], [2]], [[2]], [['field_row_id'], ['test1']], [[4]]]
    table_management.db.execute_and_return = mock

    table_management.db.execute_sql = MagicMock()

    table_management.split_rows()

    table_management.db.execute_sql.assert_called()
    table_management.db.execute_sql.assert_any_call("""UPDATE harvest.table SET yield_col = yield_col / 2""")

def test_table_management_update_column_list(table_management):
    table_management.check_multiple = MagicMock(return_value=(True, 'schema.table'))
    table_management.db.get_all_columns = MagicMock(return_value=(['col1', 'col2']))
    table_management.TMD.CBColumns.clear = MagicMock()
    table_management.TMD.CBColumns.addItem = MagicMock()

    table_management.update_column_list()

    table_management.TMD.CBColumns.clear.assert_called_once()
    table_management.TMD.CBColumns.addItem.assert_any_call('col1')
    table_management.TMD.CBColumns.addItem.assert_any_call('col2')
