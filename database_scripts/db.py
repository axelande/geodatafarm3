from typing import TYPE_CHECKING, Callable, Never, Self
if TYPE_CHECKING:
    import psycopg2.extensions
    import qgis._core
import psycopg2
import psycopg2.pool
import psycopg2.extras
from psycopg2 import sql as pgsql
import traceback
import sys
from qgis.core import QgsDataSourceUri, QgsVectorLayer
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import QMessageBox, QInputDialog

# Qt5/Qt6 compat: ensure QMessageBox.Yes/No exist as direct attributes
if not hasattr(QMessageBox, 'Yes'):
    QMessageBox.Yes = QMessageBox.StandardButton.Yes
    QMessageBox.No = QMessageBox.StandardButton.No
try:
    from ..support_scripts.__init__ import TR
except ImportError:
    from support_scripts.__init__ import TR
__author__ = 'Axel Horteborn'


class DBException(Exception):
    pass


class SomeFailure:
    def __init__(self):
        translate = TR('SomeFailure')
        self.tr = translate.tr

    def display_failure(self, er):
        QMessageBox.information(None, self.tr('Error'),
                                self.tr('Some failure occur, please send an e-mail to geodatafarm@gmail.com with the following message:\n') + str(er))


class NoConnection:
    def __init__(self: Self, tr: Callable[[str], str], message_box: type[QMessageBox]=QMessageBox) -> None:
        self.tr = tr
        self.message_box = message_box

    def run_failure(self: Self, suppress_message: bool=False) -> None:
        if not suppress_message:
            self.message_box.information(None, self.tr('Error'),
                                         self.tr('No connection was found'))


class DB:
    def __init__(self: Self, dock_widget=None, path: str|None|None=None,
                 dbname: str|None=None, dbuser: str|None=None,
                 dbpass: str|None=None, test_mode: bool=False) -> None:
        """The widget that is connects to the database
        Parameters
        ----------
        dock_widget: dock_widget
            The widget from GeoDataFarm
        path: str
            The path to plugin main folder
        tr: tr
            The translation function of GeoDataFarm
        """
        self.qsettings: QSettings = QSettings()

        self.dock_widget = dock_widget
        self.path = path
        self.dbhost = "geodatafarm.com"
        self.dbport = '5432'
        self.dbname = dbname
        self.dbuser = dbuser
        self.dbpass = dbpass
        translate = TR('DB')
        self.tr = translate.tr
        self.test_mode = test_mode
        self.pool = None

    def set_conn(self: Self, set_farm_name:bool=True) -> bool:
        """A function that checks if the database is created and then sets the
        database name, user name, password and the pool to the class.

        Returns
        -------
        bool
        """
        try:
            if not self.test_mode:
                if self.dbname is None:
                    self.dbname = self.qsettings.value("geodatafarm/farmname", "")
                    self.dbuser = self.qsettings.value("geodatafarm/username", "")
                    self.dbpass = self.qsettings.value("geodatafarm/dbpass", "")
        except IOError:
            raise psycopg2.OperationalError("Could not make a stable connection to the GeoDataFarm server")
        if self.dbname == '' or self.dbuser == '' or self.dbpass == '':
            return False
        if not self.test_mode:
            self.dock_widget.LFarmName.setText(self.dbname +
                                           self.tr(' is set as your farm'))
        self.pool = psycopg2.pool.ThreadedConnectionPool(1, 20,
            host=self.dbhost,
            database=self.dbname,
            user=self.dbuser,
            password=self.dbpass
            )
        return True

    def _connect(self: Self) -> "psycopg2.extensions.connection":
        """Connects to the database
        Returns
        -------
        bool
        """
        try:
            if not self.pool:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr('Could not make a stable connection to the GeoDataFarm server'))
                return False
            conn = self.pool.getconn()
            conn.set_isolation_level(0)
            return conn
        except psycopg2.OperationalError as e:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr(f"Error connecting to database on {self.dbhost}. {e}"))
            return False

    def add_postgis_layer(self: Self, table: str, geom_col: str, schema: str, extra_name: str='',
                          filter_text: str='') -> "qgis._core.QgsVectorLayer":
        """Creates a qgis layer from a postgres database table.

        Parameters
        ----------
        table: str
            The table that should be added
        geom_col: str
            the geometry column in that table
        schema: str
            The schema
        extra_name: str, optional
            for a "pre name" in front of the table
        filter_text: str, optional
            SQL statement to filter the data

        Returns
        -------
        QgsVectorLayer
            A QgsVectorLayer ready to be styled.

        """
        host = self.dbhost
        port = self.dbport
        dbname = self.dbname
        username = self.dbuser
        password = self.dbpass
        # Adds a PostGIS table to the map
        uri = QgsDataSourceUri()
        uri.setConnection(str(host), str(port), str(dbname), str(username),
                          str(password))
        uri.setDataSource(str(schema), str(table), str(geom_col), filter_text,
                          'field_row_id')
        uri.setKeyColumn('field_row_id')
        uri.setSrid('4326')
        vlayer = QgsVectorLayer(uri.uri(), str(extra_name) + str(table),
                                'postgres')
        if not vlayer.isValid():
            QMessageBox.information(None, 'Error',
                                    'Layer not loaded correctly,Connection:\n' +
                                    str(uri.uri()))
        return vlayer

    def check_table_exists(self: Self, table_name: str, schema: str,
                           ask_replace: bool=True) -> bool:
        """Checks if a table already exists, if it exists, the user can choose
        if it wants to reset the table. Returns False the table doesn't exists
        or have been dropped.

        Parameters
        ----------
        table_name: str
        schema: str
        ask_replace: bool, default True

        Returns
        -------
        bool
        """
        sql = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = %s
            And table_schema= %s
            """
        res = self.execute_and_return(sql, params=(table_name, schema))
        if res[0][0] > 0:
            if ask_replace:
                qm = QMessageBox
                res_qm = qm().question(None, self.tr('Message'),
                                self.tr(
                                    "The name of the data set already exist in your database, would you like to replace it? (If not please rename the file)"),
                                qm.Yes, qm.No)
                if res_qm == qm.No:
                    return True
                else:
                    query = pgsql.SQL(
                        "DROP TABLE {schema}.{tbl};"
                        " DELETE FROM {schema}.manual"
                        " WHERE table_ = %s"
                    ).format(
                        schema=pgsql.Identifier(schema),
                        tbl=pgsql.Identifier(table_name)
                    )
                    self.execute_sql(query, params=(table_name,))
                    return False
            else:
                return True
        return False

    def create_table(self: Self, sql: str, tbl_name: str,
                     drop_if_exist: bool=True) -> None:
        """Create s table, if table exists the table is dropped.

        Parameters
        ----------
        sql: str
            With the sql statement to create the table
        tbl_name: str
            table name
        drop_if_exist: bool
            If drop exist leave it as True
        """
        if drop_if_exist:
            parts = tbl_name.split('.')
            if len(parts) == 2:
                tbl_id = pgsql.SQL("{}.{}").format(
                    pgsql.Identifier(parts[0]), pgsql.Identifier(parts[1]))
            else:
                tbl_id = pgsql.Identifier(tbl_name)
            query = pgsql.SQL("DROP TABLE IF EXISTS {}").format(tbl_id)
            self.execute_sql(query)
        self.execute_sql(sql)

    def create_indexes(self: Self, tbl_name: str, params_to_eval: list[str],
                       schema: str, primary_key: bool=True) -> None:
        """Drops is exists and create a gist index and
        btree indexes for params_to_eval a table

        Parameters
        ----------
        tbl_name: str
            table name
        params_to_eval: list
            of text strings with columns to make indexes over
        schema: str
            schema name
        primary_key: bool
            default True -> create a primary key over field_row_id
        """
        tbl_safe = tbl_name.replace('.', '_')
        try:
            self.execute_sql(
                pgsql.SQL("DROP INDEX IF EXISTS {}").format(
                    pgsql.Identifier(f"gist_{schema}_{tbl_safe}")),
                disregard_failure=True)
            self.execute_sql(
                pgsql.SQL("CREATE INDEX {} ON {}.{} USING gist(pos)").format(
                    pgsql.Identifier(f"gist_{schema}_{tbl_safe}"),
                    pgsql.Identifier(schema),
                    pgsql.Identifier(tbl_name)),
                disregard_failure=True)
            if schema != 'harvest':
                self.execute_sql(
                    pgsql.SQL("DROP INDEX IF EXISTS {}").format(
                        pgsql.Identifier(f"gist2_{schema}_{tbl_safe}")))
                self.execute_sql(
                    pgsql.SQL("CREATE INDEX {} ON {}.{} USING gist(polygon)").format(
                        pgsql.Identifier(f"gist2_{schema}_{tbl_safe}"),
                        pgsql.Identifier(schema),
                        pgsql.Identifier(tbl_name)),
                    disregard_failure=True)
            for parm in params_to_eval:
                self.execute_sql(
                    pgsql.SQL("DROP INDEX IF EXISTS {}").format(
                        pgsql.Identifier(f"{parm}_{schema}_{tbl_safe}")),
                    disregard_failure=True)
                self.execute_sql(
                    pgsql.SQL("CREATE INDEX {} ON {}.{} USING btree({})").format(
                        pgsql.Identifier(f"{parm}_{schema}_{tbl_safe}"),
                        pgsql.Identifier(schema),
                        pgsql.Identifier(tbl_name),
                        pgsql.Identifier(parm)),
                    disregard_failure=True)
            if primary_key:
                self.execute_sql(
                    pgsql.SQL("ALTER TABLE {}.{} ADD CONSTRAINT {} PRIMARY KEY (field_row_id)").format(
                        pgsql.Identifier(schema),
                        pgsql.Identifier(tbl_name),
                        pgsql.Identifier(f"pkey_{schema}_{tbl_name}")))
        except Exception as e:
            print('Failed when trying to create indexes')
            print(e)

    def get_tables_in_db(self: Self, schema: str) -> list:
        """Get the tables in schema

        Parameters
        ----------
        schema: str

        Returns
        -------
        list
            A list of tables in the database
        """
        sql = """select table_name
        from information_schema.tables
        where table_schema = %s and table_type = 'BASE TABLE'
        ORDER BY table_name"""
        table_names = self.execute_and_return(sql, params=(schema,))
        names = []
        for name in table_names:
            names.append(name[0])
        return names

    def get_distinct(self: Self, table: str, column: str,
                     schema: str) -> list[list[int|str]]:
        """Get distinct values from a schema.table

        Parameters
        ----------
        table: str
        column: str
        schema: str

        Returns
        -------
        list
            [distinct value, count]
        """
        query = pgsql.SQL(
            "SELECT {item}, count(*)"
            " FROM {schema}.{tbl}"
            " GROUP BY {item}"
            " ORDER BY {item}"
        ).format(
            item=pgsql.Identifier(column),
            tbl=pgsql.Identifier(table),
            schema=pgsql.Identifier(schema)
        )
        all_distinct = self.execute_and_return(query)
        checked_values = []
        for col, count in all_distinct:
            checked_values.append([col, count])
        return checked_values

    def get_all_columns(self: Self, table: str, schema: str,
                        exclude: str="''") -> list:
        """Get all columns of a table

        Parameters
        ----------
        table: str
        schema: str
        exclude: str, optional, string with comma sep names

        Returns
        -------
        list of lists
        """
        query = pgsql.SQL(
            "SELECT a.attname AS column_name"
            " FROM pg_class t"
            " JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace,"
            " pg_class i, pg_attribute a"
            " WHERE a.attrelid = t.oid"
            " AND t.relkind = 'r'"
            " AND t.relname = %s"
            " AND n.nspname = %s"
            " AND attisdropped IS False"
            " AND attstattarget < 0"
            " AND a.attname NOT IN ({exclude})"
            " GROUP BY t.relname, a.attname"
            " ORDER BY a.attname"
        ).format(exclude=pgsql.SQL(exclude))
        cols = self.execute_and_return(query, params=(table, schema))
        columns = []
        for col in cols:
            columns.append(col[0])
        return columns

    def get_numeric_columns(self: Self, table: str, schema: str,
                            exclude: str = "''") -> list:
        """Get only numeric columns of a table.

        Parameters
        ----------
        table: str
        schema: str
        exclude: str, optional, string with comma sep names

        Returns
        -------
        list
            A list of numeric column names
        """
        query = pgsql.SQL(
            "SELECT a.attname AS column_name"
            " FROM pg_class t"
            " JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace,"
            " pg_attribute a, pg_type ty"
            " WHERE a.attrelid = t.oid"
            " AND a.atttypid = ty.oid"
            " AND t.relkind = 'r'"
            " AND t.relname = %s"
            " AND n.nspname = %s"
            " AND attisdropped IS False"
            " AND attstattarget < 0"
            " AND a.attname NOT IN ({exclude})"
            " AND ty.typname IN ('int2', 'int4', 'int8', 'float4', 'float8', 'numeric')"
            " GROUP BY t.relname, a.attname"
            " ORDER BY a.attname"
        ).format(exclude=pgsql.SQL(exclude))
        cols = self.execute_and_return(query, params=(table, schema))
        return [col[0] for col in cols]

    def update_row_id(self, schema, table):
        """Update the field_row_id
        Parameters
        ----------
        schema: str
        table: str
        """
        query = pgsql.SQL(
            "ALTER TABLE {schema}.{table} DROP COLUMN field_row_id;"
            " ALTER TABLE {schema}.{table} ADD COLUMN field_row_id serial UNIQUE NOT NULL"
        ).format(
            schema=pgsql.Identifier(schema),
            table=pgsql.Identifier(table)
        )
        res = self.execute_sql(query, return_failure=True)


    def get_indexes(self: Self, tables: str, schema: str) -> dict[int, dict[str, str]]:
        """Get indexes of tables in a schema, returns a dict.

        Parameters
        ----------
        tables: str
            what table(s) to look for. (separated by comma if multiple)
        schema: str
            schema name

        Returns
        -------
        dict
            int as first arg and for each int 'tbl_name','index_name',
            'index_col' and 'schema'

        """
        if schema == '':
            schema_clause = pgsql.SQL("")
        else:
            schema_clause = pgsql.SQL("AND n.nspname = %s")
        query = pgsql.SQL(
            "SELECT t.relname AS table_name,"
            " i.relname AS index_name,"
            " a.attname AS column_name,"
            " n.nspname AS schema_name"
            " FROM pg_class t"
            " JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace,"
            " pg_class i, pg_index ix, pg_attribute a"
            " WHERE t.oid = ix.indrelid"
            " AND i.oid = ix.indexrelid"
            " AND a.attrelid = t.oid"
            " AND a.attnum = ANY(ix.indkey)"
            " AND t.relkind = 'r'"
            " AND t.relname = %s"
            " {schema_clause}"
            " ORDER BY t.relname, i.relname"
        ).format(schema_clause=schema_clause)
        if schema == '':
            params = (tables,)
        else:
            params = (tables, schema)
        big_table = self.execute_and_return(query, params=params)
        parameter_to_eval = {}
        ind = -1
        for table, index_name, index_col, schema in big_table:
            if index_col == 'field_row_id' or 'gist' in index_name:
                continue
            ind += 1
            parameter_to_eval[ind] = {}
            parameter_to_eval[ind]['tbl_name'] = table.encode("ascii").decode('utf-8')
            parameter_to_eval[ind]['index_name'] = index_name.encode("ascii").decode('utf-8')
            parameter_to_eval[ind]['index_col'] = index_col
            parameter_to_eval[ind]['schema'] = schema
        return parameter_to_eval

    def execute_sql(self: Self, sql, params: tuple|None=None,
                    return_failure: bool=False,
                    return_row_count: bool=False, disregard_failure: bool=False,
                    suppress_message: bool=False) -> "list[bool|int|str]|None":
        """
        Parameters
        ----------
        sql: str or psycopg2.sql.Composable
            the sql statement
        params: tuple, optional
            parameters for parameterized query (use %s placeholders in sql)
        return_failure: bool, optional default False
            If True returns if failure
        disregard_failure: bool, optional default False
            If True disregards failures and don't print etc.
        """
        conn = self._connect()
        if not conn:
            nc = NoConnection(self.tr)
            nc.run_failure(suppress_message=suppress_message)
            return 'There was no connection established'
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute(sql, params)
            conn.commit()
            row_count = cur.rowcount
        except Exception as e:
            if return_failure:
                self.pool.putconn(conn)
                error_type, value_, traceback_ = sys.exc_info()
                return [False, error_type, e]
            elif disregard_failure:
                pass
            else:
                sf = SomeFailure()
                if self.test_mode:
                    self.pool.putconn(conn)
                    return False
                else:
                    sf.display_failure(e)
        self.pool.putconn(conn)
        if return_failure:
            if return_row_count:
                return [True, 'suc', row_count]
            else:
                return [True, 'suc']

    def execute_and_return(self: Self, sql, params: tuple|None=None,
                           return_failure: bool=False,
                           suppress_message: bool=False
                           ) -> "list[list[float|int|str|None]]|list[bool|list[float|int|str|None]|str]":
        """Execute and returns an SQL statement

        Parameters
        ----------
        sql: str or psycopg2.sql.Composable
            the sql statement
        params: tuple, optional
            parameters for parameterized query (use %s placeholders in sql)
        return_failure: bool
            if the error should be returned instead of showed to the user

        Returns
        -------
        list of lists
            the data requested in the statement
        """
        conn = self._connect()
        if not conn:
            nc = NoConnection(self.tr)
            nc.run_failure(suppress_message=suppress_message)
            return 'There was no connection established'
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute(sql, params)
            data = cur.fetchall()
        except Exception as e:
            self.pool.putconn(conn)
            if return_failure:
                error_type, value_, traceback_ = sys.exc_info()
                return [False, error_type, e]
            else:
                if self.test_mode:
                    return 'There were an error..'
                else:
                    sf = SomeFailure()
                    sf.display_failure(e)
                    return 'There were an error..'
        self.pool.putconn(conn)
        if return_failure:
            return [True, data]
        else:
            return data

    def remove_table(self: Self, tbl_schema_name: str) -> None:
        """Function that removes a table from the database

        Parameters
        ----------
        tbl_schema_name: str
            string with schema.table

        """
        schema, tbl = tbl_schema_name.split('.')[0], tbl_schema_name.split('.')[1]
        query = pgsql.SQL("DROP TABLE IF EXISTS {}.{}").format(
            pgsql.Identifier(schema), pgsql.Identifier(tbl))
        self.execute_sql(query)
        try:
            query = pgsql.SQL("DELETE FROM {}.manual WHERE table_ = %s").format(
                pgsql.Identifier(schema))
            self.execute_sql(query, params=(tbl,))
        except:
            pass

    def reset_row_id(self: Self, schema: str, tbl: str) -> list:
        query = pgsql.SQL(
            "ALTER TABLE {schema}.{tbl} DROP CONSTRAINT IF EXISTS {pkey};"
            " WITH a AS (SELECT field_row_id AS a_old, ROW_NUMBER() OVER() AS a_row FROM {schema}.{tbl})"
            " UPDATE {schema}.{tbl} b SET field_row_id = a_row FROM a WHERE field_row_id = a_old;"
            " ALTER TABLE {schema}.{tbl} ADD CONSTRAINT {pkey} PRIMARY KEY (field_row_id)"
        ).format(
            schema=pgsql.Identifier(schema),
            tbl=pgsql.Identifier(tbl),
            pkey=pgsql.Identifier(f"pkey_{schema}_{tbl}")
        )
        fail = self.execute_sql(query, return_failure=True)
        return [fail]
