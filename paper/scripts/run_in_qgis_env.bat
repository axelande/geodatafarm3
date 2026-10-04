@echo off
rem Runs a paper script inside the OSGeo4W / QGIS-Qt6 Python environment,
rem the same one run_tests.bat uses, so the plugin's modules import cleanly.
rem
rem Usage (from the repository root):
rem   paper\scripts\run_in_qgis_env.bat paper\scripts\export_training_examples.py --farm myfarm --user me
rem
rem The farm password can be given as --password or via the GDF_PASSWORD
rem environment variable (preferred, keeps it out of the shell history).
call C:\OSGeo4W\bin\o4w_env.bat
call C:\OSGeo4W\bin\qt6_env.bat
path %OSGEO4W_ROOT%\apps\qgis-qt6\bin;%PATH%
set QGIS_PREFIX_PATH=%OSGEO4W_ROOT:\=/%/apps/qgis-qt6
set QT_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\qgis-qt6\qtplugins;%OSGEO4W_ROOT%\apps\qt6\plugins
set GDAL_FILENAME_IS_UTF8=YES
set VSI_CACHE=TRUE
set VSI_CACHE_SIZE=1000000
set PYTHONPATH=%OSGEO4W_ROOT%\apps\qgis-qt6\python;%OSGEO4W_ROOT%\apps\qgis-qt6\python\plugins
set QT_QPA_PLATFORM=offscreen
python %*
