import os
import sys
import subprocess
import platform

from qgis.PyQt.QtWidgets import QMessageBox

def check_and_install_requirements():
    try:
        import matplotlib
    except ModuleNotFoundError:
        print('installing matplotlib')
        if platform.system() == 'Windows':
            subprocess.call([sys.exec_prefix + '/python', "-m", 'pip', 'install', 'matplotlib'])
        else:
            subprocess.call(['python3', '-m', 'pip', 'install', 'matplotlib'])
        import matplotlib
        try:
            import matplotlib
            print('installation completed')
        except ModuleNotFoundError:
            QMessageBox.information(None, 'ERROR',
                                    """During the first startup this program there are some third party packages that is required to be installed, 
GeoDataFarm tried to install them automatic but failed. You can try to manually install the two packages with "pip install matplotlib", "pip install reportlab", "pip install pandas"
(If you are using Windows you need to run it from the OSGeo4W shell) 
If can't get the plugin to work, don't hesitate to send an e-mail to geodatafarm@gmail.com and tell which os you are using and QGIS version.""")
            sys.exit()
    try:
        import reportlab
    except ModuleNotFoundError:
        print('installing reportlab')
        if platform.system() == 'Windows':
            subprocess.call([sys.exec_prefix + '/python', "-m", 'pip', 'install', 'reportlab'])
        else:
            subprocess.call(['python3', '-m', 'pip', 'install', 'reportlab'])
        try:
            import reportlab
            print('installation completed')
        except ModuleNotFoundError:
            QMessageBox.information(None, 'ERROR',
                                    """During the first startup this program there are some third party packages that is required to be installed, 
GeoDataFarm tried to install them automatic but failed. You can try to manually install the two packages with "pip install matplotlib", "pip install reportlab", "pip install pandas"
(If you are using Windows you need to run it from the OSGeo4W shell) 
If can't get the plugin to work, don't hesitate to send an e-mail to geodatafarm@gmail.com and tell which os you are using and QGIS version.""")
            sys.exit()

    try:
        import pandas
    except ModuleNotFoundError:
        print('installing pandas')
        if platform.system() == 'Windows':
            subprocess.call([sys.exec_prefix + '/python', "-m", 'pip', 'install', 'pandas'])
        else:
            subprocess.call(['python3', '-m', 'pip', 'install', 'pandas'])
        try:
            import pandas
            print('installation completed')
        except ModuleNotFoundError:
            QMessageBox.information(None, 'ERROR',
                                    """During the first startup this program there are some third party packages that is required to be installed, 
GeoDataFarm tried to install them automatic but failed. You can try to manually install the two packages with "pip install matplotlib", "pip install reportlab", "pip install pandas"
(If you are using Windows you need to run it from the OSGeo4W shell) 
If can't get the plugin to work, don't hesitate to send an e-mail to geodatafarm@gmail.com and tell which os you are using and QGIS version.""")
            sys.exit()
