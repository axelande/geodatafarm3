from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QMessageBox
import os
from support_scripts.__init__ import check_text
import requests
import hashlib
from widgets.create_farm_popup import CreateFarmPopup
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
        password = check_text(password_inp)
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
        with open(self.plugin_dir + '\connection_data.ini', 'w') as f:
            f.write(username + ',' + password + ',' + farmname)
        self.parent_widget.dock_widget.LFarmName.setText(farmname + ' is set\nas your farm')
        self.CF.done(0)

    def connect_to_source(self):
        """Connects the plugin to another database"""
        username_inp = self.CF.user_name.text()
        password_inp = self.CF.pass_word.text()
        farmname_inp = self.CF.farm_name.text()
        username = check_text(username_inp)
        password = check_text(password_inp)
        farmname = check_text(farmname_inp)
        password = hashlib.sha256(password).hexdigest()

        with open(self.plugin_dir + '\connection_data.ini', 'w') as f:
            f.write(username + ',' + password + ',' + farmname)
        self.parent_widget.dock_widget.LFarmName.setText(farmname + ' is set\nas your farm')
        self.CF.done(0)