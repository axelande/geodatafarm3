@echo off
call C:\OSGeo4W\bin\o4w_env.bat
call C:\OSGeo4W\bin\qt6_env.bat

rem Add QGIS DLLs to PATH (mirrors qgis-qt6.bat)
path %OSGEO4W_ROOT%\apps\qgis-qt6\bin;%PATH%

rem Set QGIS environment (mirrors qgis-qt6.bat)
set QGIS_PREFIX_PATH=%OSGEO4W_ROOT:\=/%/apps/qgis-qt6
set QT_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\qgis-qt6\qtplugins;%OSGEO4W_ROOT%\apps\qt6\plugins
set GDAL_FILENAME_IS_UTF8=YES
set VSI_CACHE=TRUE
set VSI_CACHE_SIZE=1000000

rem o4w_env.bat resets PYTHONPATH via python3.bat; vscode.bat sets old Qt5 qgis path.
rem Override to point at the Qt6 build.
set PYTHONPATH=%OSGEO4W_ROOT%\apps\qgis-qt6\python;%OSGEO4W_ROOT%\apps\qgis-qt6\python\plugins

python -m pytest tests -s %*
