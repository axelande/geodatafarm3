from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtWidgets import QMessageBox
import os
import requests
import hashlib
from ..widgets.create_farm_popup import CreateFarmPopup
from ..support_scripts.__init__ import check_text
from .db import DB
__author__ = 'Axel Andersson'


class CreateFarm:
    def __init__(self, iface, parent_widget):
        """Sends a request to create a database for the farm"""
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'CreateFarmPopup{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        #print "** INITIALIZING GeoDataFarm"
        # Create the dialog (after translation) and keep reference
        self.CF = CreateFarmPopup()
        self.CF.PBCreateDatabase.clicked.connect(self.create_new_farm)
        self.CF.PBConnectExisting.clicked.connect(self.connect_to_source)
        self.parent_widget = parent_widget
        self.tr = parent_widget.tr
        self.plugin_dir = parent_widget.plugin_dir
        self.dock_widget = parent_widget.dock_widget

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
        username = check_text(username_inp)
        password = check_text(password_inp).encode('utf-8')
        farmname = check_text(farmname_inp)
        password = hashlib.sha256(password).hexdigest()
        r = requests.post('http://geodatafarm.com:5000/create', data={'username':username,'password':password, 'farmname':farmname, 'email':email_inp})
        if r == None:
            QMessageBox.information(None, self.tr("Error:"), self.tr('- Is your computer online? \n- If you are sure that your computer please send an email to geo_farm@gmail.com'))
            return
        r = r.text.split(',')
        if r[0] == 'false':
            QMessageBox.information(None, self.tr("Error:"), self.tr('Farm name allready taken, please choose another name for your farm!'))
            return
        elif r[1] == 'false':
            QMessageBox.information(None, self.tr("Error:"), self.tr('User name allready taken, please choose another name as user name!'))
            return
        else:
            QMessageBox.information(None, self.tr("Done"), self.tr('Database created'))
        with open(self.plugin_dir + '\database_scripts\connection_data.ini', 'w') as f:
            f.write(username + ',' + password + ',' + farmname)
        self.parent_widget.dock_widget.LFarmName.setText(farmname + ' is set\nas your farm')
        self.create_spec_functions()
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

        with open(self.plugin_dir + '\database_scripts\connection_data.ini', 'w') as f:
            f.write(username + ',' + password + ',' + farmname)
        self.parent_widget.dock_widget.LFarmName.setText(farmname + ' is set\nas your farm')
        self.CF.done(0)

    def create_spec_functions(self):
        db = DB(self.dock_widget, path=self.plugin_dir)
        connected = DB.get_conn()
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
        db.execute_sql(sql)
