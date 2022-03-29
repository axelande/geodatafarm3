import psycopg2
import psycopg2.pool
import psycopg2.extras
import traceback
import sys
from qgis.core import QgsDataSourceUri, QgsVectorLayer
from PyQt5.QtWidgets import QMessageBox
try:
    from ..support_scripts.__init__ import TR
except ValueError:
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
    def __init__(self, tr):
        self.tr = tr

    def run_failure(self):
        QMessageBox.information(None, self.tr('Error'),
                                self.tr('No connection was found'))


class DB:
    def __init__(self, dock_widget, path=None):
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

        self.dock_widget = dock_widget
        self.path = path
        self.conn = None
        self.dbhost = "geodatafarm.com"
        self.dbport = '5432'
        self.dbname = None
        self.dbuser = None
        self.dbpass = None
        translate = TR('DB')
        self.tr = translate.tr

    def get_conn(self):
        """A function that checks if the database is created and sets then the
        database name, user name and password.

        Returns
        -------
        bool
        """
        try:
            with open(self.path + '\database_scripts\connection_data.ini', 'r') as f:
                text = f.readline()
                [username, password, farmname] = text.split(',')
        except IOError:
            return False
        self.dbname = farmname
        self.dbuser = username
        self.dbpass = password
        self.dock_widget.LFarmName.setText(farmname +
                                           self.tr(' is set as your farm'))
        return True

    def _connect(self):
        """Connects to the database
        Returns
        -------
        bool
        """
        if self.conn is None:
            try:
                pool = psycopg2.pool.SimpleConnectionPool(1, 20,
                    host=self.dbhost,
                    database=self.dbname,
                    user=self.dbuser,
                    password=self.dbpass
                    )
                if not pool:
                    QMessageBox.information(None, self.tr('Error'),
                                            self.tr('Could not make a stable connection to the GeoDataFarm server'))
                self.conn = pool.getconn()
                self.conn.set_isolation_level(0)
                return True
            except psycopg2.OperationalError as e:
                QMessageBox.information(None, self.tr('Error'), self.tr("Error connecting to database on {host}. {e}".format(
                        host=self.dbhost, e=str(e))))
                return False

    def _close(self):
        """Closes the connection to the database"""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def add_postgis_layer(self, table, geom_col, schema, extra_name='',
                          filter_text=''):
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

    def check_table_exists(self, table_name, schema, ask_replace=True):
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
            WHERE table_name = '{tbl}'
            And table_schema='{s}'
            """.format(tbl=table_name.replace('\'', '\'\''), s=schema)
        res = self.execute_and_return(sql)
        if res[0][0] > 0:
            if ask_replace:
                qm = QMessageBox()
                res = qm.question(None, self.tr('Message'),
                                  self.tr(
                                      "The name of the data set already exist in your database, would you like to replace it? (If not please rename the file)"),
                                  qm.Yes, qm.No)
                if res == qm.No:
                    return True
                else:
                    self.execute_sql("""DROP TABLE {schema}.{tbl};
                                                       DELETE FROM {schema}.manual
                                                       WHERE table_ = '{tbl}';
                                                       """.format(
                        schema=schema,
                        tbl=table_name))
            else:
                return True
        return False

    def create_table(self, sql, tbl_name):
        """Create s table, if table exists the table is dropped.

        Parameters
        ----------
        sql: str
            With the sql statement to create the table
        tbl_name: str
            table name
        """
        self.execute_sql("DROP TABLE IF EXISTS {tbl}".format(tbl=tbl_name))
        self.execute_sql(sql)

    def create_indexes(self, tbl_name, params_to_eval, schema,
                       primary_key=True):
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
        try:
            self.execute_sql("""DROP INDEX IF EXISTS gist_{schema}_{tbl2}""".format(schema=schema, tbl2=tbl_name.replace('.', '_')))
            self.execute_sql("""create index gist_{schema}_{tbl2}
        on {schema}.{tbl} using gist(pos) """.format(schema=schema, tbl=tbl_name, tbl2=tbl_name.replace('.', '_')))
            if schema != 'harvest':
                self.execute_sql("""DROP INDEX IF EXISTS gist2_{schema}_{tbl2}""".format(
                    schema=schema, tbl2=tbl_name.replace('.', '_')))
                self.execute_sql("""create index gist2_{schema}_{tbl2}
                    on {schema}.{tbl} using gist(polygon) """.format(schema=schema,
                                                                 tbl=tbl_name,
                                                                 tbl2=tbl_name.replace(
                                                                     '.', '_')))
            for parm in params_to_eval:
                self.execute_sql("DROP INDEX IF EXISTS {param}_{schema}_{tbl2}".format(schema=schema, param=parm, tbl2=tbl_name.replace('.', '_')))
                self.execute_sql("""create index {param}_{schema}_{tbl2} on {schema}.{tbl} 
        using btree({param})""".format(schema=schema, param=parm, tbl=tbl_name, tbl2=tbl_name.replace('.', '_')))
            if primary_key:
                self.execute_sql("""ALTER TABLE {schema}.{tbl}
        ADD CONSTRAINT pkey_{schema}_{tbl} PRIMARY KEY (field_row_id);""".format(tbl=tbl_name, schema=schema))
        except Exception as e:
            print('Failed when trying to create indexes')
            print(e)

    def get_tables_in_db(self, schema) -> list:
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
        where table_schema = '{schema}' and table_type = 'BASE TABLE'
        ORDER BY table_name""".format(schema=schema)
        table_names = self.execute_and_return(sql)
        names = []
        for name in table_names:
            names.append(name[0])
        return names

    def get_distinct(self, table, column, schema):
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
        sql = """SELECT {item}, count(*)
        FROM {schema}.{tbl}
        GROUP BY {item}
        ORDER BY {item}""".format(item=column, tbl=table, schema=schema)
        all_distinct = self.execute_and_return(sql)
        checked_values = []
        for col, count in all_distinct:
            checked_values.append([col, count])
        return checked_values

    def get_all_columns(self, table, schema, exclude="''") -> list:
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

        sql = """select
        a.attname as column_name
        from
        pg_class t
        JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace,
        pg_class i,
        pg_attribute a
        where
        a.attrelid = t.oid
        and t.relkind = 'r'
        and t.relname = '{table}'
        and n.nspname in ('{schema}')
        and attisdropped is False 
        and attstattarget < 0
        and a.attname not in ({exclude})
        group by t.relname,
        a.attname order by a.attname""".format(table=table, schema=schema,
                                               exclude=exclude)
        columns = self.execute_and_return(sql)
        return columns

    def update_row_id(self, schema, table):
        """Update the field_row_id
        Parameters
        ----------
        schema: str
        table: str
        """
        sql = """ALTER TABLE {schema}.{table} drop COLUMN field_row_id;
        ALTER TABLE {schema}.{table} add COLUMN field_row_id serial UNIQUE NOT NULL
        """.format(schema=schema, table=table)
        self.execute_sql(sql)

    def get_indexes(self, tables, schema):
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
        schema_txt = "" if schema == '' else "and n.nspname='{s}'".format(s=schema)
        sql = """select
             t.relname as table_name,
             i.relname as index_name,
             a.attname as column_name,
             n.nspname as schema_name
            from
             pg_class t
             JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace,
             pg_class i,
             pg_index ix,
             pg_attribute a
            where
             t.oid = ix.indrelid
             and i.oid = ix.indexrelid
             and a.attrelid = t.oid
             and a.attnum = ANY(ix.indkey)
             and t.relkind = 'r'
             and t.relname in ('{tables}')
             {schema_txt}
            order by
             t.relname,
             i.relname;""".format(tables=tables, schema_txt=schema_txt)
        big_table = self.execute_and_return(sql)
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

    def execute_sql(self, sql, return_failure=False, return_row_count=False):
        """
        Parameters
        ----------
        sql: str
            text string with the sql statement
        return_failure: bool, optional default False
            If True returns if failure
        """
        self._connect()
        if self.conn is None:
            nc = NoConnection(self.tr)
            nc.run_failure()
            return 'There was no connection established'
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute(sql)
            self.conn.commit()
            row_count = cur.rowcount
        except Exception as e:
            if return_failure:
                error_type, value_, traceback_ = sys.exc_info()
                return [False, error_type, e]
            else:
                sf = SomeFailure()
                sf.display_failure(e)
        self._close()
        if return_failure:
            if return_row_count:
                return [True, 'suc', row_count]
            else:
                return [True, 'suc']

    def execute_and_return(self, sql, return_failure=False):
        """Execute and returns an SQL statement

        Parameters
        ----------
        sql: str
            text string with the sql statement
        return_failure: bool
            if the error should be returned instead of showed to the user

        Returns
        -------
        list of lists
            the data requested in the statement
        """
        self._connect()
        if self.conn is None:
            nc = NoConnection(self.tr)
            nc.run_failure()
            return 'There was no connection established'
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute(sql)
            data = cur.fetchall()
        except Exception as e:
            if return_failure:
                error_type, value_, traceback_ = sys.exc_info()
                self._close()
                return [False, error_type, e]
            else:
                sf = SomeFailure()
                sf.display_failure(e)
            data = 'There were an error..'
        self._close()
        return data

    def remove_table(self, tbl_schema_name):
        """Function that removes a table from the database

        Parameters
        ----------
        tbl_schema_name: str
            string with schema.table

        """
        self.execute_sql("DROP TABLE IF EXISTS {tbl}".format(tbl=tbl_schema_name))
        try:
            schema = tbl_schema_name.split('.')[0]
            tbl = tbl_schema_name.split('.')[1]
            sql = "DELETE FROM {s}.manual WHERE table_='{tbl}'".format(s=schema, tbl=tbl)
            self.execute_sql(sql)
        except:
            pass

    def reset_row_id(self, schema, tbl) -> list:
        sql = """ALTER TABLE {schema}.{tbl} drop constraint if exists pkey_{schema}_{tbl};
        with a as(select field_row_id as a_old, ROW_NUMBER() OVER() as a_row from {schema}.{tbl})
        UPDATE {schema}.{tbl} b
        SET field_row_id= a_row
        from a
        where field_row_id=a_old;
        ALTER TABLE {schema}.{tbl} add constraint pkey_{schema}_{tbl} primary key (field_row_id);
        """.format(schema=schema, tbl=tbl)
        fail = self.execute_sql(sql, return_failure=True)
        return [fail]

    def test_connection(self):
        """Tests to open the connection and then closes it again
        Returns
        -------
        bool
        """
        try:
            self._connect()
            return True
        except DBException as e:
            return False
        finally:
            self._close()
