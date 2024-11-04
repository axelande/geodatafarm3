# GeoDataFarm

This is QGIS plugin, intended to be used by farmers that wants to analyze their field data. The first version of the plugin was released to [plugins.qgis.org](https://plugins.qgis.org) in 2018 and since then has many updates been added. The plugin is 100% free and the development is performed as an active hobby project.

For guidance on the usage of the plugin please have a look at [geodatafarm.com](http://www.geodatafarm.com) 

## Contributions
To contribute to the project please fork the repository and create Pull requests with suggested updates/ new features. If possible try to create requests as simple as possible regarding only one topic. Also before creating any pull requests make sure that all tests passes (`pytest tests`)

### How to setup development environment
If you are running on Windows and want to help and contribute to the project it could be a good idea to download `VSCode`. I also recommend to use the Network installer to install QGIS. If you have installed the network installer it is recommended to add a `VSCode.bat` in the `C:\OSGeo4W\etc\ini` folder. The content of the `VSCode.bat` could look something like this:
>SET PYTHONPATH=%OSGEO4W_ROOT%\apps\qgis\python;%OSGEO4W_ROOT%\apps\qgis\python\plugins
SET PATH=%PATH%;%LOCALAPPDATA%\Programs\Microsoft VS Code;%ProgramFiles%\7-Zip\

Then `VSCode` should be launched by just typing "`code`" in the `OSGeo4W Shell`. By launching `VSCode` like this it knowns the correct python etc.

Appart from the listed packages in `requirements_dev.txt` some additional packages is also recommended to install:
- `pip install pb_tool` <- With this tool it is possible to run commands like:
  -  `pb_tool de`, which will deploy the GeoDataFarm to the correct plugins folder so you don't have to copy it your plugin storage.
  -  `pb_tool zip` which adds GeoDataFarm as a Zip file.
- `pip install "pyqt5-tools<5.15.2.1.3" --no-deps`. This will help with translation.
  - If new files are added make sure to add them in `i18n/geodatafarm.pro` and navigate to the `i18n` folder
  - Run `Pylupdate5 -noobsolete geodatafarm.pro` to generate the updates in the .ts files
  - Open Linguist and the .ts files and edit the translation.
  - Run `qt5-tools lrelease geodatafarm_[sv].ts`