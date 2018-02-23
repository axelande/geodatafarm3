import psycopg2
import psycopg2.extras
import time
from qgis.core import QgsDataSourceUri, QgsVectorLayer
from PyQt5.QtWidgets import QMessageBox
__author__ = 'Axel Andersson'


class DBException(Exception):
    pass


class DB:
    def __init__(self, dock_widget, path=None):
        """The widget that is connects to the database
        :param dock_widget: The docked widget
        :return:
        """
        self.dock_widget = dock_widget
        self.path = path
        self.conn = None
        self.dbhost = "geodatafarm.com"
        self.dbport = '5432'
        self.dbname = None
        self.dbuser = None
        self.dbpass = None

    def get_conn(self):
        """
        A function that checks if the database is created and sets then the
        database name, user name and password.
        :return: True or False
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
        self.dock_widget.LFarmName.setText(farmname + ' is\nset as your farm')
        return True

    def _connect(self):
        """
        Connects to the database
        :return:
        """
        if self.conn is None:
            try:
                self.conn = psycopg2.connect(
                    host=self.dbhost,
                    database=self.dbname,
                    user=self.dbuser,
                    password=self.dbpass
                    )
                self.conn.set_isolation_level(0)
            except psycopg2.OperationalError as e:
                raise DBException("Error connecting to database on '%s'. %s" %
                                  (self.dbhost, str(e)))

    def _close(self):
        """
        Closes the connection to the database
        :return:
        """
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def addPostGISLayer(self, table, geom_col, schema, extra_name=''):
        """
        Creates a qgis layer from a postgres database table.
        :param table: The table that should be added
        :param geom_col: the geometry column in that table
        :param schema: text string
        :param extra_name: text string for a "prename" in front of the table
        :return:
        """
        host = self.dbhost
        port = self.dbport
        dbname = self.dbname
        username = self.dbuser
        password = self.dbpass

        ## Adds a PostGIS table to the map
        uri = QgsDataSourceURI()
        uri.setConnection(str(host), str(port), str(dbname), str(username), str(password))
        uri.setDataSource(str(schema), str(table), str(geom_col), '', 'field_row_id')
        uri.setKeyColumn('field_row_id')
        vlayer = QgsVectorLayer(uri.uri(), str(extra_name) + str(table[1:]), 'postgres')

        if not vlayer.isValid():
            QMessageBox.information(None,'Layer not loaded', uri.host(),
                   uri.database(), uri.port(), uri.username(), uri.password(),
                   uri.schema(), uri.table(), uri.geometryColumn())
        return vlayer

    def check_table_exists(self, tablename):
        """
        :param tablename: text string
        :return: True or False
        """
        self._connect()
        dbcur = self.conn.cursor()
        dbcur.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = '{tbl}'
            """.format(tbl=tablename.replace('\'', '\'\'')))
        if dbcur.fetchone()[0] == 1:
            self._close()
            return True

        self._close()
        return False

    def create_table(self, sql, tbl_name):
        """
        :param sql: text string with the sql statement
        :param tbl_name: text string
        :return:
        """
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("DROP TABLE IF EXISTS {tbl}".format(tbl=tbl_name))
        cur.execute(sql)
        self.conn.commit()
        self._close()

    def insert_data(self, sql, tbl_name, params_to_eval):
        """
        :param sql: text string with the sql statement
        :param tbl_name: text string
        :param params_to_eval: list of text strings
        :return:
        """
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        #for sql in sql_list:
        #print(sql)
        cur.execute(sql)
        self.conn.commit()
        self._close()

    def create_indexes(self, tbl_name, params_to_eval, schema):
        """
        :param tbl_name: text string
        :param params_to_eval: list of text strings
        :return:
        """
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""DROP INDEX IF EXISTS gist_{schema}_{tbl2}""".format(schema=schema, tbl2=tbl_name.replace('.', '_')))
        cur.execute("""create index gist_{tbl2}
    on {schema}.{tbl} using gist(pos) """.format(schema=schema, tbl=tbl_name, tbl2=tbl_name.replace('.', '_')))
        for parm in params_to_eval:
            cur.execute("DROP INDEX IF EXISTS {param}_{schema}{tbl2}".format(schema=schema, param=parm, tbl2=tbl_name.replace('.', '_')))
            cur.execute("""create index {param}_{schema}_{tbl2} on {schema}.{tbl} 
    using btree({param})""".format(schema=schema, param=parm, tbl=tbl_name, tbl2=tbl_name.replace('.', '_')))
        cur.execute("""ALTER TABLE {schema}.{tbl}
    ADD CONSTRAINT pkey_{schema}_{tbl} PRIMARY KEY (field_row_id);""".format(tbl=tbl_name, schema=schema))
        self.conn.commit()
        self._close()

    def insert_data_polygon(self, sql, tbl_name):
        """
        :param sql: text string with the sql statement
        :param tbl_name: text string
        :return:
        """
        t0 = time.time()
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # for sql in sql_list:
        #print(sql)
        cur.execute(sql)
        self.conn.commit()
        cur.execute("""DROP INDEX IF EXISTS gist_{tbl2}""".format(tbl2=tbl_name.replace('.', '_')))
        cur.execute("""create index gist_{tbl2}
         on {tbl} using gist(polygon) """.format(tbl=tbl_name, tbl2=tbl_name.replace('.', '_')))
        sql = """UPDATE {tbl}
                set polygon = subquery.poly
                from (SELECT polygon as poly
                      from temp_polygon) AS subquery
                WHERE ST_INTERSECTS({tbl}.pos, subquery.poly)""".format(tbl=tbl_name)
        cur.execute(sql)
        self.conn.commit()
        self._close()

    def get_tables_in_db(self, schema='public'):
        """
        :param: str
        :return: A list of tables in the database
        """
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql = """select table_name 
from information_schema.tables 
where table_schema = '{schema}' and table_type = 'BASE TABLE'
ORDER BY table_name""".format(schema=schema)
        cur.execute(sql)
        table_names = cur.fetchall()
        return table_names

    def get_distinct(self, table, column, schema):
        """
        :param table: text string
        :param column: text string
        :return: list [distinct value, count]
        """
        sql = """SELECT {item}, count(*)
        FROM {schema}.{tbl}
        GROUP BY {item}
        ORDER BY {item}""".format(item=column, tbl=table, schema=schema)
        self._connect()
        dbcur = self.conn.cursor()
        dbcur.execute(sql)
        all_distinct = dbcur.fetchall()
        self._close()
        checked_values = []
        for col, count in all_distinct:
            if col != " ":
                checked_values.append([col, count])

        return checked_values

    def get_all_columns(self, table, schema):
        """
        :param table: text string
        :param schema: text string
        :return
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
        and t.relname in ('{tbl}')
        and n.nspname in ('{schema}')
        group by t.relname,
        a.attname""".format(tbl=table, schema=schema)
        columns = self.execute_and_return(sql)
        return columns

    def get_indexes(self, tables, analyse):
        """
        :param tables: text string
        :param analyse: True, False depending if it is to analyse or not
        :return: list of strings of the index names
        """
        sql= """select
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
             and t.relname in ('{tbls}')
            order by
             t.relname,
             i.relname;""".format(tbls=tables)
        big_table = self.execute_and_return(sql)
        parameter_to_eval = {}
        ind = -1
        self.yield_tbls = []
        self.yield_col = []
        for table, index_name, index_col, schema in big_table:
            if 'field_row_id' in index_name or 'gist' in index_name:
                continue
            ind += 1
            parameter_to_eval[ind] = {}
            parameter_to_eval[ind]['tbl_name'] = table.encode("ascii")
            parameter_to_eval[ind]['index_name'] = index_name.encode("ascii")
            parameter_to_eval[ind]['index_col'] = index_col
            parameter_to_eval[ind]['schema'] = schema
        return parameter_to_eval

    def execute_sql(self, sql):
        """
        :param sql: text string with the sql statement
        :return: the data requested in the statement
        """
        self._connect()

        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql)
        self.conn.commit()
        self._close()

    def execute_and_return(self, sql):
        """
        :param sql: text string with the sql statement
        :return: the data requested in the statement
        """
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql)
        data = cur.fetchall()
        self._close()
        return data

    def remove_table(self, tbl_name):
        """
        :param tbl_name: list of strings
        :return:
        """
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("DROP TABLE IF EXISTS {tbl}".format(tbl=tbl_name))
        self.conn.commit()
        self._close()

    def test_connection(self):
        """
        Tests to open the connection and then closes it again
        :return: True, False
        """
        try:
            self._connect()
            return True
        except DBException as e:
            return False
        finally:
            self._close()