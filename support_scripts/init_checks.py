import os
import sys
import subprocess
import platform

from PyQt5.QtWidgets import QMessageBox

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
GeoDataFarm tried to install them automatic but failed. You can try to manually install the two packages with "pip install matplotlib", "pip install reportlab", "pip install cython", "pip install pandas"
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
GeoDataFarm tried to install them automatic but failed. You can try to manually install the two packages with "pip install matplotlib", "pip install reportlab", "pip install cython", "pip install pandas"
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
GeoDataFarm tried to install them automatic but failed. You can try to manually install the two packages with "pip install matplotlib", "pip install reportlab", "pip install cython", "pip install pandas"
(If you are using Windows you need to run it from the OSGeo4W shell) 
If can't get the plugin to work, don't hesitate to send an e-mail to geodatafarm@gmail.com and tell which os you are using and QGIS version.""")
            sys.exit()


def check_if_pyagri_is_built():
    try:
        import cython
    except ModuleNotFoundError:
        print('installing cython')
        if platform.system() == 'Windows':
            subprocess.call([sys.exec_prefix + '/python', "-m", 'pip', 'install', 'cython'])
        else:
            subprocess.call(['python3', '-m', 'pip', 'install', 'cython'])
        try:
            import cython
            print('installation completed')
        except ModuleNotFoundError:
            QMessageBox.information(None, 'ERROR',
                                    """During the first startup this program there are some third party packages that is required to be installed, 
GeoDataFarm tried to install them automatic but failed. You can try to manually install the two packages with "pip install cython"
(If you are using Windows you need to run it from the OSGeo4W shell) 
If can't get the plugin to work, don't hesitate to send an e-mail to geodatafarm@gmail.com and tell which os you are using and QGIS version.""")
            return False
    try:
        from geodatafarm.support_scripts.pyagriculture.cython_agri import read_static_binary_data
        return True
    except ModuleNotFoundError:
        try:
            print('Trying to compile py_agri')
            this_folder = os.path.dirname(os.path.abspath(__file__))
            if platform.system() == 'Windows':
                subprocess.call([sys.exec_prefix + '/python', f'{this_folder}/pyagriculture/setup.py', 'build_ext', '--build-lib', f'{this_folder}/pyagriculture'])
            else:
                subprocess.call(['python3', f'{this_folder}/pyagriculture/setup.py', 'build_ext', '--build-lib', f'{this_folder}/pyagriculture'])
            print('installation complete')
            from geodatafarm.support_scripts.pyagriculture.cython_agri import read_static_binary_data
            print('import ok')
            return True
        except Exception as e:
            print('failed')
            print(e)
            return False
