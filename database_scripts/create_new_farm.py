from PyQt5.QtWidgets import QMessageBox
import requests
import hashlib
from ..support_scripts.__init__ import check_text
from .db import DB
#from ..GeoDataFarm import GeoDataFarm
__author__ = 'Axel Horteborn'


class CreateFarm:
    def __init__(self, parent_widget, new_farm):
        """Sends a request to create a database for the farm

        Parameters
        ----------
        parent_widget: GeoDataFarm
        new_farm: bool,
            True if the user creates new farm,
            False if user connects to a farm
        """
        if new_farm:
            from ..widgets.create_farm_popup import CreateFarmPopup
            self.CF = CreateFarmPopup()
            self.CF.PBCreateDatabase.clicked.connect(self.create_new_farm)
        else:
            from ..widgets.connect_to_farm import ConnectFarmPopup
            self.CF = ConnectFarmPopup()
            self.CF.PBConnectExisting.clicked.connect(self.connect_to_source)
        self.parent_widget = parent_widget
        self.tr = parent_widget.tr
        self.plugin_dir = parent_widget.plugin_dir
        self.dock_widget = parent_widget.dock_widget
        self.db = None

    def run(self):
        """Presents the sub widget CreateFarm"""
        self.CF.show()
        self.CF.exec_()

    def create_new_farm(self):
        """Sends a request to the server and asks it to create the database for
         the farm, when the database is created does the server return a
         message telling if the farm name or user name is taken else a message
         that the database has been created."""
        username_inp = self.CF.user_name.text()
        password_inp = self.CF.pass_word.text()
        farmname_inp = self.CF.farm_name.text()
        email_inp = self.CF.email_field.text()
        first_year = int(self.CF.DEFirstYear.text())
        if first_year > 2029:
            QMessageBox.information(None, self.tr("Error:"), self.tr(
                'The first year must be less than 2030'))
            return
        if username_inp == self.tr('name'):
            QMessageBox.information(None, self.tr("Error:"), self.tr(
                'The user name must be different from "name"'))
            return
        if email_inp == self.tr('your@email.com'):
            QMessageBox.information(None, self.tr("Error:"), self.tr(
                'The e-mail must be a real e-mail address'))
            return
        if farmname_inp == self.tr('farmname'):
            QMessageBox.information(None, self.tr("Error:"), self.tr(
                'The farm name must be different from "farmname"'))
            return
        username = check_text(username_inp)
        password = check_text(password_inp).encode('utf-8')
        farmname = check_text(farmname_inp)
        password = hashlib.sha256(password).hexdigest()
        insertion_ok = False
        r = requests.post(
            'http://geodatafarm.com/create/?username={u}&password={p}&farmname={f}&email={e}'.format(u=username,
                                                                                                     p=password,
                                                                                                     f=farmname,
                                                                                                     e=email_inp))
        if r is None:
            QMessageBox.information(None, self.tr("Error:"), self.tr(
                '- Is your computer online? \n- If you are sure that your computer please send an email to geofarm@gmail.com'))
            return
        r = r.text.split(',')
        if r[0] == 'false':
            QMessageBox.information(None, self.tr("Error:"),
                                    self.tr('Farm name allready taken, please choose another name for your farm!'))
            return
        elif r[1] == ' false':
            QMessageBox.information(None, self.tr("Error:"),
                                    self.tr('User name allready taken, please choose another name as user name!'))
            return
        else:
            insertion_ok = True
        with open(self.plugin_dir + '\database_scripts\connection_data.ini', 'w') as f:
            f.write(username + ',' + password + ',' + farmname)
        self.parent_widget.dock_widget.LFarmName.setText(farmname + ' is set\nas your farm')
        self._connect_to_db()
        self.parent_widget.db = self.db
        self.create_spec_functions()
        self.add_schemas()
        self.add_tables(first_year)
        self.parent_widget.set_buttons()
        self.parent_widget.populate.db = self.db
        self.parent_widget.populate.update_table_list()
        self.parent_widget.populate.reload_fields()
        self.parent_widget.populate.reload_crops()
        if insertion_ok:
            QMessageBox.information(None, self.tr("Done"),
                                    self.tr('Database created'))
        self.CF.done(0)

    def connect_to_source(self):
        """Connects the plugin to another database"""
        username_inp = self.CF.user_name.text()
        password_inp = self.CF.pass_word.text()
        farmname_inp = self.CF.farm_name.text()
        username = check_text(username_inp)
        password = check_text(password_inp).encode('utf-8')
        farmname = check_text(farmname_inp)
        password = hashlib.sha256(password).hexdigest()

        with open(self.plugin_dir +
                  '\database_scripts\connection_data.ini', 'w') as f:
            f.write(username + ',' + password + ',' + farmname)
        self.parent_widget.dock_widget.LFarmName.setText(farmname +
                                                         ' is set\nas your farm')
        self._connect_to_db()
        self.reset_db_connections()
        # This is important when no connection is active at startup
        self.parent_widget.set_buttons()
        # This is important when another connection is active at startup
        self.parent_widget.populate.update_table_list()
        self.parent_widget.populate.reload_fields()
        self.parent_widget.populate.reload_crops()
        self.CF.done(0)

    def reset_db_connections(self):
        """Resets the database connection"""
        self.parent_widget.db = self.db
        try:
            self.parent_widget.add_field.db = self.db
            self.parent_widget.populate.db = self.db
        except AttributeError:
            pass

    def _connect_to_db(self):
        """Simple function to connect to the new database"""
        self.db = DB(self.dock_widget, path=self.plugin_dir, tr=self.tr)
        connected = self.db.get_conn()

    def create_spec_functions(self):
        """Generates the function makegrid_2d in the users postgres
        database."""
        if self.db is None:
            self._connect_to_db()
        sql = """CREATE OR REPLACE FUNCTION public.makegrid_2d (
      bound_polygon public.geometry,
      width_step integer,
      height_step integer
    )
    RETURNS public.geometry AS
    $body$
    DECLARE
      Xmin DOUBLE PRECISION;
      Xmax DOUBLE PRECISION;
      Ymax DOUBLE PRECISION;
      X DOUBLE PRECISION;
      Y DOUBLE PRECISION;
      NextX DOUBLE PRECISION;
      NextY DOUBLE PRECISION;
      CPoint public.geometry;
      sectors public.geometry[];
      i INTEGER;
      SRID INTEGER;
    BEGIN
      Xmin := ST_XMin(bound_polygon);
      Xmax := ST_XMax(bound_polygon);
      Ymax := ST_YMax(bound_polygon);
      SRID := ST_SRID(bound_polygon);

      Y := ST_YMin(bound_polygon); --current sector's corner coordinate
      i := -1;
      <<yloop>>
      LOOP
        IF (Y > Ymax) THEN  
            EXIT;
        END IF;

        X := Xmin;
        <<xloop>>
        LOOP
          IF (X > Xmax) THEN
              EXIT;
          END IF;

          CPoint := ST_SetSRID(ST_MakePoint(X, Y), SRID);
          NextX := ST_X(ST_Project(CPoint, $2, radians(90))::geometry);
          NextY := ST_Y(ST_Project(CPoint, $3, radians(0))::geometry);

          i := i + 1;
          sectors[i] := ST_MakeEnvelope(X, Y, NextX, NextY, SRID);

          X := NextX;
        END LOOP xloop;
        CPoint := ST_SetSRID(ST_MakePoint(X, Y), SRID);
        NextY := ST_Y(ST_Project(CPoint, $3, radians(0))::geometry);
        Y := NextY;
      END LOOP yloop;

      RETURN ST_Collect(sectors);
    END;
    $body$
    LANGUAGE 'plpgsql';"""
        self.db.execute_sql(sql)

    def add_tables(self, first_year):
        """Add field, crops and manual tables to the database"""
        if self.db is None:
            self._connect_to_db()
        sql = """CREATE table fields(field_row_id serial,
            field_name text COLLATE pg_catalog."default" NOT NULL,
            years text,
            polygon geometry(Polygon,4326),"""
        for year in range(first_year, 2051):
            sql += """_{y} text,
            """.format(y=year)
        sql += """CONSTRAINT p_key_field PRIMARY KEY (field_row_id),
            CONSTRAINT field_name UNIQUE (field_name))"""
        self.db.execute_sql(sql)
        sql = """CREATE table crops(row_id serial,
            crop_name text COLLATE pg_catalog."default" NOT NULL,
            CONSTRAINT p_key_crop PRIMARY KEY (row_id),
            CONSTRAINT crop_name UNIQUE (crop_name))"""
        self.db.execute_sql(sql)
        sql = """CREATE table plant.manual(field text, 
            crop text, 
            date_ date, 
            date_text text,
            variety text, 
            spacing text, 
            seed_rate text, 
            saw_depth text, 
            other text, 
            table_ text)"""
        self.db.execute_sql(sql)
        sql = """create table ferti.manual(field text, 
            crop text, 
            date_ date, 
            date_text text,
            variety text, 
            rate text, 
            saw_depth text, 
            other text, 
            table_ text)"""
        self.db.execute_sql(sql)
        sql = """create table spray.manual(field text, 
                    crop text, 
                    date_ date, 
                    date_text text,
                    variety text, 
                    rate text, 
                    wind_speed text,
                    wind_dir text, 
                    other text, 
                    table_ text)"""
        self.db.execute_sql(sql)
        sql = """create table harvest.manual(field text, 
                    crop text, 
                    date_ date,
                    date_text text, 
                    total_yield text, 
                    yield text, 
                    other text, 
                    table_ text)"""
        self.db.execute_sql(sql)
        sql = """create table other.plowing_manual(field text, 
                    date_ date, 
                    depth text, 
                    other text)"""
        self.db.execute_sql(sql)
        sql = """create table other.harrowing_manual(field text, 
                            date_ date, 
                            depth text, 
                            other text)"""
        self.db.execute_sql(sql)
        sql = """create table soil.manual(field text, 
                            date_ date,
                            date_text text, 
                            clay text,
                            humus text, 
                            ph text,
                            rx text,
                            other text,
                            table_ text)"""
        self.db.execute_sql(sql)

    def add_schemas(self):
        """Adds schemas to the new database"""
        if self.db is None:
            self._connect_to_db()
        sql = """create schema plant;
        create schema harvest;
        create schema other;
        create schema soil;
        create schema weather;
        create schema spray;
        create schema ferti;"""
        self.db.execute_sql(sql)
