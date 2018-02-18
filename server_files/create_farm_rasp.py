__author__ = 'Matrix'
import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
class DBException(Exception):
    pass

class CreateFarm():
    def __init__(self):
        self.dbhost = "localhost"
        self.dbname = "postgres"
        self.dbuser = 'postgres'
        self.dbpass = 'horteudde1'
        self.dbport = '5432'
        self.conn = None
    def _connect(self):
        if self.conn is None:
            try:
                self.conn = psycopg2.connect(
                    host=self.dbhost,
                    database=self.dbname,
                    user=self.dbuser,
                    password=self.dbpass,
                    port=self.dbport)
            except psycopg2.OperationalError as e:
                raise DBException("Error connecting to database on '%s'. %s" %
                                  (self.dbhost, str(e)))

    def _close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def check_data(self, farmname, username):
        self._connect()
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT datname FROM pg_catalog.pg_database")
        farm_names_in_db = cur.fetchall()
        cur.execute("SELECT rolname FROM pg_catalog.pg_roles")
        user_names_in_db = cur.fetchall()
        self._close()
        for name in farm_names_in_db:
            #print(name)
            if farmname in name[0]:
                return 'false, true, true'
        for name in user_names_in_db:
            #print(name)
            if username in name[0]:
                return 'true, false, true'
        return 'true, true, true'

    def create_user_and_farm(self, farmname, username, password, email):
        self._connect()
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql1 = "CREATE DATABASE " + farmname
        sql2 = "CREATE EXTENSION postgis;"
        sql3 = """create user {user} password '{passw}';
REVOKE CONNECT ON DATABASE {farm} FROM PUBLIC;
GRANT CONNECT
ON DATABASE {farm}
TO {user};
REVOKE ALL
ON ALL TABLES IN SCHEMA public 
FROM public;
""".format(farm=farmname, user=username, passw=password)
        for table in ['public', 'activity', 'soil', 'harvest', 'weather']:
            sql3 += """
GRANT USAGE ON ALL SEQUENCES IN SCHEMA {table} TO {user};
GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA {table}
TO {user};
GRANT ALL ON SCHEMA {table} TO {user};
""".format(table=table, user=username)
        sql4 = """create table user_meta_data(user_name text, farm text, password text, email text);
INSERT INTO user_meta_data(user_name, farm, password, email) VALUES('{user}', '{farm}', '{passw}', '{email}')
""".format(user=username, farm=farmname, passw=password, email=email) 
        sql5 = """create schema activity;
create schema harvest;
create schema soil;
create schema weather"""
        cur.execute(sql1)
        #cur.execute(sql2)
        self._close()
        self.dbname = farmname
        #self.dbuser = username
        #self.dbpass = password
        self._connect()
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql2)
        cur.execute(sql5)
        cur.execute(sql4)
        cur.execute(sql3)
        self._close()
        print("Database " + str(farmname) + " was created")
        return 'true, true, true'
