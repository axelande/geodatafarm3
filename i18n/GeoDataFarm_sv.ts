<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="sv_SE" sourcelanguage="en">
<context>
    <name>CreateFarm</name>
    <message>
        <location filename="../database_scripts/create_new_farm.py" line="70"/>
        <source>Error:</source>
        <translation>Fel:</translation>
    </message>
    <message>
        <location filename="../database_scripts/create_new_farm.py" line="63"/>
        <source>- Is your computer online? 
- If you are sure that your computer please send an email to geo_farm@gmail.com</source>
        <translation>Är din dator ansluten till internet? Om så är fallet skicka gärna ett e-mail till geodatafarm@gmail.com så hjälper jag dig</translation>
    </message>
    <message>
        <location filename="../database_scripts/create_new_farm.py" line="67"/>
        <source>Farm name allready taken, please choose another name for your farm!</source>
        <translation>Gårdsnamnet är redan taget, var god välj ett annat namn på gården!</translation>
    </message>
    <message>
        <location filename="../database_scripts/create_new_farm.py" line="70"/>
        <source>User name allready taken, please choose another name as user name!</source>
        <translation>Användarsnamnet är redan taget, var god välj ett annat namn aom användarnamn!</translation>
    </message>
    <message>
        <location filename="../database_scripts/create_new_farm.py" line="73"/>
        <source>Done</source>
        <translation>Klar</translation>
    </message>
    <message>
        <location filename="../database_scripts/create_new_farm.py" line="73"/>
        <source>Database created</source>
        <translation>Databasen är skapad</translation>
    </message>
</context>
<context>
    <name>CreateGuideFile</name>
    <message>
        <location filename="../support_scripts/create_guiding_file.py" line="62"/>
        <source>No farm is created, please create a farm to continue</source>
        <translation>Ingen gård är skapad, var god god och gör det innan du fortsätter</translation>
    </message>
    <message>
        <location filename="../support_scripts/create_guiding_file.py" line="126"/>
        <source>No row selected!</source>
        <translation>Ingen rad vald!</translation>
    </message>
    <message>
        <location filename="../support_scripts/create_guiding_file.py" line="151"/>
        <source>The selected data must be integers or floats!</source>
        <translation>Den valda datan måste vara heltal eller decimaltal!</translation>
    </message>
    <message>
        <location filename="../support_scripts/create_guiding_file.py" line="247"/>
        <source>Help:</source>
        <translation>Hjälp:</translation>
    </message>
    <message>
        <location filename="../support_scripts/create_guiding_file.py" line="247"/>
        <source>Here you create a guide file.
1. Start with select which data you want to base the guide file on in the top left corner.
2. Select which of the attributes you want to use as base of calculation.
3. When this is done you will have one or a few attributes in the right list with the name, [number].
4. Now, change the equation to the right (default 100 + [0] * 2) to fit your idea and press update.
5. When you press update the max and min value should be updated.
6. Depending on your machine (that you want to feed with the guide file) you might want to use integers or float values.
7. The attribute name and File name is for you, the output path is where the guide file will be stored.
8. Cell size, how big grid you want for the guide file, EPSG let it be 4326 unless your machine require it!
9. There is also an option for you if you want to rotate your grid.
10. Finally press Create guide file and you are all set to go!</source>
        <translation>Här skapar du en styrfil.
1. Starta med att välj vilken data du ska bygga din styrfil på.
2. Välj vilka(et) attribut som ska du ska använda för att räkna ut givan.
3. När detta är gjort ska du ha en eller ett par attribut i den högra listan med namn och [nummer].
4. Nu, ända ekvationen till höger (default 100 +[0] *2, där [0] syftar till attributet i listan intil),
5. Tryck på uppdatera för att se hur max och min värdena ändras, ändra ekvationen tills du är nöjd.
6. Beroende på din maskin (som du ska använda styrfilen till) ska du ändra mellan heltal ocf decimaltal.
7. Välj attributnamn, filnamn och var filen ska sparas.
8. Cell storleken, är hur stora celler som du vill att styrfilen ska ha, EPSG är vilket koordinat system, låt det vara 4326 om du är osäker!
9. Vill du kan du även välja att rotera griddet
10. Till sist är det bara att trycka &apos;Skapa styrfil&apos;.</translation>
    </message>
</context>
<context>
    <name>CreateGuideFileBase</name>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="14"/>
        <source>Add indata to the model</source>
        <translation>Lägg till data</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="29"/>
        <source>Cell size (m):</source>
        <translation>Cell storlek (m):</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="42"/>
        <source>Data source:</source>
        <translation>Data källa:</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="55"/>
        <source>100 +  [0] *2 </source>
        <translation>100 + [0] *2</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="68"/>
        <source>EPSG:</source>
        <translation>EPSG:</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="81"/>
        <source>Update</source>
        <translation>Updatera</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="94"/>
        <source>Max value: Not selected</source>
        <translation>Max värde: Ej valt</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="107"/>
        <source>4326</source>
        <translation>4326</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="121"/>
        <source>Integear (1)</source>
        <translation>Heltal</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="126"/>
        <source>Float (1.234)</source>
        <translation>Decimaltal (1,234)</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="140"/>
        <source>Attribute:</source>
        <translation>Attribut:</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="153"/>
        <source>Write your equation here, 
denote the Attribute as &quot;[0]&quot;, &quot;[1]&quot; etc.:</source>
        <translation>Skriv din ekvation här, 
benämn ditt attribut som [0], [1] etc.:</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="167"/>
        <source>25</source>
        <translation>25</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="181"/>
        <source>-- Select base file --</source>
        <translation>-- Välj fil att utgå från --</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="198"/>
        <source>--&gt;</source>
        <translation>--&gt;</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="243"/>
        <source>&lt;--</source>
        <translation>&lt;--</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="269"/>
        <source>Store to a file:</source>
        <translation>Spara till fil:</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="282"/>
        <source>Data type:</source>
        <translation>Data typ:</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="295"/>
        <source>Min value: Not selected</source>
        <translation>Min värde: Ej valt</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="308"/>
        <source>Setting_distance</source>
        <translation>satt_avstand</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="321"/>
        <source>New attr name:</source>
        <translation>Nytt attributnamn:</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="337"/>
        <source>Select Outputpath</source>
        <translation>Välj plats att spara filen på</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="353"/>
        <source>Create Guide File</source>
        <translation>Skapa styrfil</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="366"/>
        <source>Path not selected</source>
        <translation>Plats att spara på är ej definerad</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="379"/>
        <source>File name</source>
        <translation>Fil namn</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="392"/>
        <source>guide_file</source>
        <translation>styrfil</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="405"/>
        <source>Rotation: (deg):</source>
        <translation>Rotatation (grad):</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="418"/>
        <source>0</source>
        <translation>0</translation>
    </message>
    <message>
        <location filename="../widgets/create_guide_file_base.ui" line="431"/>
        <source>Help</source>
        <translation>Hjälp</translation>
    </message>
</context>
<context>
    <name>EndMethod</name>
    <message>
        <location filename="../import_data/handle_text_data.py" line="506"/>
        <source>Min value is greater than the maximum value</source>
        <translation>Det minsta värdet är större än det största värdet</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="582"/>
        <source> rows were skipped since the row did not match the heading.</source>
        <translation>rader hoppades över då antalet columner inte matachade den översta radens antal.</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="470"/>
        <source>Yearly operations</source>
        <translation>Årlig operation</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="502"/>
        <source>harvest</source>
        <translation>Skörd data</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="616"/>
        <source>soil</source>
        <translation>Jord data</translation>
    </message>
</context>
<context>
    <name>GeoDataFarm</name>
    <message>
        <location filename="../GeoDataFarm.py" line="229"/>
        <source>&amp;GeoFarm</source>
        <translation>&amp;GeoFarm</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="210"/>
        <source>GeoDataFarm</source>
        <translation>GeoDataFarm</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="271"/>
        <source>No farm is created, please create a farm to continue</source>
        <translation>Ingen gård är skapad, var god god och gör det innan du fortsätter</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="374"/>
        <source>The name of the data set already exist in your database, would you like to replace it?</source>
        <translation>Namnet finns redan, vill du ersätta den datan?</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="334"/>
        <source>You need to have at least one input (activity or soil) and one harvest data set selected.</source>
        <translation>Du måste välja åtminstånde en aktivitet eller jorddata och en skörde data.</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="343"/>
        <source>Support for databasefiles are not implemented 100% yet</source>
        <translation>Stöd för databas filer är inte implemeterat till 100% än</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="349"/>
        <source>Support for shapefiles are not implemented 100% yet</source>
        <translation>Stöd för shapefiler filer är inte implemeterat till 100% än</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="403"/>
        <source>harvest</source>
        <translation>Skörd data</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="339"/>
        <source>Text file (.csv; .txt)</source>
        <translation>Text fil (.csv; .txt)</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="342"/>
        <source>Databasefile (.db)</source>
        <translation>Databas fil (.db)
</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm.py" line="348"/>
        <source>Shape file (.shp)</source>
        <translation>Shape fil (.shp)</translation>
    </message>
</context>
<context>
    <name>GeoDataFarmDockWidgetBase</name>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="14"/>
        <source>GeoDataFarm</source>
        <translation>GeoDataFarm</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="31"/>
        <source>Add data</source>
        <translation>Lägg till data</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="50"/>
        <source>---Select data type ---</source>
        <translation>----Välj data fil ----</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="55"/>
        <source>activity</source>
        <translation>Aktivitets data</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="60"/>
        <source>harvest</source>
        <translation>Skörd data</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="65"/>
        <source>soil</source>
        <translation>Jord data</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="77"/>
        <source>--- Select file type ---</source>
        <translation>----Välj fil typ ----</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="82"/>
        <source>Text file (.csv; .txt)</source>
        <translation>Text fil (.csv; .txt)</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="87"/>
        <source>Shape file (.shp)</source>
        <translation>Shape fil (.shp)</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="92"/>
        <source>Databasefile (.db)</source>
        <translation>Databas fil (.db)
</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="103"/>
        <source>Open the input and load it to the canvas</source>
        <translation>Öppna och ladda den till kartan</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="113"/>
        <source>Define field</source>
        <translation>Definera fält</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="279"/>
        <source>Reload layer</source>
        <translation>Ladda om lager</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="261"/>
        <source>Min value:</source>
        <translation>Minsta värde:</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="254"/>
        <source>Max value:</source>
        <translation>Högsta värde:</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="239"/>
        <source>Max number 
of colors:</source>
        <translation>Max antal färger:</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="247"/>
        <source>20</source>
        <translation></translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="177"/>
        <source>Labels rules</source>
        <translation>Figursättnings regler</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="192"/>
        <source>Equal count intervals</source>
        <translation>Lika antal i varje interval</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="211"/>
        <source>Evenenly distrubuted intervals</source>
        <translation>Lika stora interval</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="304"/>
        <source>Data Management</source>
        <translation>Data Management</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="331"/>
        <source>Update lists</source>
        <translation>Updatera listorna</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="349"/>
        <source>Edit datasets</source>
        <translation>Ändra i listorna</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="389"/>
        <source>Activity data sets:</source>
        <translation>Aktivitets listor:</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="430"/>
        <source>Harvest data sets:</source>
        <translation>Skörde data listor:</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="471"/>
        <source>Soil data sets:</source>
        <translation>Jorddata listor:</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="506"/>
        <source>Add selected tables to the canvas</source>
        <translation>Lägg till data till kartan</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="522"/>
        <source>Run the analyse</source>
        <translation>Kör analys</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="560"/>
        <source>No farm database created</source>
        <translation>Ingen gård är skapad</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="126"/>
        <source>Recolor the input and load it to storage</source>
        <translation>Färglägg och spara för analys</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="154"/>
        <source>Edit the attributes of the current layer</source>
        <translation>Editera följande lager i kartan</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="164"/>
        <source>Edit the presentation of the layer on the canvas:</source>
        <translation>Ändra presentationen av följande läger i kartvyn:</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="365"/>
        <source>Create guide file</source>
        <translation>Skapa styrfil</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="569"/>
        <source>Irrigation</source>
        <translation>Bevattning</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="581"/>
        <source>Import Raindancer data</source>
        <translation>Hämta Raindancer data</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="297"/>
        <source>How to use the plugin is explained at:
www.geodatafarm.com</source>
        <translation type="unfinished">Instruktioner för hur pluginet fungerar finner
du på www.geodatafarm.com</translation>
    </message>
    <message>
        <location filename="../GeoDataFarm_dockwidget_base.ui" line="538"/>
        <source>Create new/connect to farm database</source>
        <translation>Skapa ny/anslut till tidigare databas</translation>
    </message>
</context>
<context>
    <name>ImportDBFileDialogBase</name>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="14"/>
        <source>Add indata to the model</source>
        <translation>Lägg till data</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="45"/>
        <source>Add input file</source>
        <translation>Indata fil</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="58"/>
        <source>Select the main data set:</source>
        <translation>Välj huvuddata fil:</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="74"/>
        <source>Add data to canvas</source>
        <translation>Lägg till data till kartan</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="90"/>
        <source>Continue</source>
        <translation>Fortsätt</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="106"/>
        <source>Date and time 
are stored in two 
different columns</source>
        <translation>Datum och tid är sparade i två kolumner</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="137"/>
        <source>(YYYY)</source>
        <translation>(åååå)</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="192"/>
        <source>Date and time 
are stored in 
the same column</source>
        <translation>Datum och tid är sparade i samma kolumn</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="210"/>
        <source>Date:</source>
        <translation>Datum:</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="223"/>
        <source>Time:</source>
        <translation>Tid:</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="252"/>
        <source>Date stored in 
following column</source>
        <translation>Datum finns i följande kolumn</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="279"/>
        <source>Data prefix:</source>
        <translation>Data prefix:</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="292"/>
        <source>(&quot;plant&quot;, &quot;soiltype&quot;, &quot;irrigation&quot; etc.)</source>
        <translation>(&quot;sätt&quot;,&quot;jorddata&quot;, &quot;bevattning&quot; etc.)</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="305"/>
        <source>EPGS Coordinate system:</source>
        <translation>EPGCS Kordinatsystem:</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="318"/>
        <source>4326</source>
        <translation>4326</translation>
    </message>
    <message>
        <location filename="../widgets/import_db_file_dialog_base.ui" line="331"/>
        <source>WGS 84 = 4326, RT90 2.5 gon V = 3021, UTM zone 32N = 32632, SWEREF99 TM = 3006 etc.</source>
        <translation>WGS 84 = 4326, RT90 2.5 gon V = 3021, UTM zone 32N = 32632, SWEREF99 TM = 3006 etc.</translation>
    </message>
</context>
<context>
    <name>ImportInputDialogBase</name>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="14"/>
        <source>Add indata to the model</source>
        <translation>Lägg till indata till modellen</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="45"/>
        <source>Add input file</source>
        <translation>Indata fil</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="58"/>
        <source>Columns in the file:</source>
        <translation>Kolumner i filen:</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="84"/>
        <source>Parameters that could be analysed:</source>
        <translation>Parameterar som kan bli analyserade:</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="110"/>
        <source>&lt;--</source>
        <translation>&lt;--</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="123"/>
        <source>--&gt;</source>
        <translation>--&gt;</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="139"/>
        <source>Add data to canvas</source>
        <translation>Lägg till data till kartan</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="155"/>
        <source>Continue</source>
        <translation>Fortsätt</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="171"/>
        <source>Not date related data</source>
        <translation></translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="190"/>
        <source>No date column, hence 
same date for all rows</source>
        <translation>Ingen datumn kolumn, men samma datum för alla rader</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="210"/>
        <source>Date and time 
are stored in two 
different columns</source>
        <translation>Datum och tid är sparade i två kolumner</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="241"/>
        <source>(YYYY-mm-dd)</source>
        <translation>(åååå-mm-dd)</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="296"/>
        <source>Date and time 
are stored in 
the same column</source>
        <translation>Datum och tid är sparade i samma kolumn</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="314"/>
        <source>Date:</source>
        <translation>Datum:</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="327"/>
        <source>Time:</source>
        <translation>Tid:</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="356"/>
        <source>Date stored in 
following column</source>
        <translation>Datum finns i följande kolumn</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="383"/>
        <source>Data prefix:</source>
        <translation>Data prefix:</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="396"/>
        <source>(&quot;plant&quot;, &quot;soiltype&quot;, &quot;irrigation&quot; etc.)</source>
        <translation>(&quot;sätt&quot;,&quot;jorddata&quot;, &quot;bevattning&quot; etc.)</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="409"/>
        <source>EPGS Coordinate system:</source>
        <translation>EPGCS Kordinatsystem:</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="422"/>
        <source>4326</source>
        <translation>4326</translation>
    </message>
    <message>
        <location filename="../widgets/import_shp_dialog_base.ui" line="435"/>
        <source>WGS 84 = 4326, RT90 2.5 gon V = 3021, UTM zone 32N = 32632, SWEREF99 TM = 3006 etc.</source>
        <translation>WGS 84 = 4326, RT90 2.5 gon V = 3021, UTM zone 32N = 32632, SWEREF99 TM = 3006 etc.</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="14"/>
        <source>Create farm</source>
        <translation>Skapa en gård</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="48"/>
        <source>Create a new 
database</source>
        <translation>Skapa en ny databas</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="62"/>
        <source>farmname</source>
        <translation>Gårdsnamn</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="75"/>
        <source>Farm name:</source>
        <translation>Gårdsnamn:</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="88"/>
        <source>User name:</source>
        <translation>Användarnamn:</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="101"/>
        <source>name</source>
        <translation>Namn</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="114"/>
        <source>choose password</source>
        <translation>Välj lösenord</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="127"/>
        <source>Password:</source>
        <translation>Lösenord:</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="140"/>
        <source>your@email.com</source>
        <translation>din@epostadress</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="153"/>
        <source>e-mail</source>
        <translation>E-mail</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="166"/>
        <source>(e-mail is only used to recover database)</source>
        <translation>(e-post adressen är enbart tänkt att användas för att återskapa databasen)</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="179"/>
        <source>Create a new farm database</source>
        <translation>Skapa en ny gård</translation>
    </message>
    <message>
        <location filename="../widgets/create_farm_popup_base.ui" line="195"/>
        <source>Connect to 
excisting database</source>
        <translation>Anslut till en redan exiceterande databas</translation>
    </message>
</context>
<context>
    <name>ImportTextDialogBase</name>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="14"/>
        <source>Add indata to the model</source>
        <translation>Lägg till data</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="51"/>
        <source>Add input file</source>
        <translation>Indata fil</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="67"/>
        <source>Columns in the file:</source>
        <translation>Kolumner i filen:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="99"/>
        <source>Parameters that could be analysed:</source>
        <translation>Parameterar som kan bli analyserade:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="131"/>
        <source>&lt;--</source>
        <translation>&lt;--</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="147"/>
        <source>--&gt;</source>
        <translation>--&gt;</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="166"/>
        <source>Add data to canvas</source>
        <translation>Lägg till data till kartan</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="185"/>
        <source>Continue</source>
        <translation>Fortsätt</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="204"/>
        <source>Date and time 
are stored in two 
different columns</source>
        <translation>Datum och tid är sparade i två kolumner</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="241"/>
        <source>Year:</source>
        <translation>År:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="308"/>
        <source>Date and time 
are stored in 
the same column</source>
        <translation>Datum och tid är sparade i samma kolumn</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="329"/>
        <source>Date:</source>
        <translation>Datum:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="345"/>
        <source>Time:</source>
        <translation>Tid:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="380"/>
        <source>Date stored in 
following column</source>
        <translation>Datum finns i följande kolumn</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="400"/>
        <source>4326</source>
        <translation>4326</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="416"/>
        <source>WGS 84 = 4326, RT90 2.5 gon V = 3021, UTM zone 32N = 32632, SWEREF99 TM = 3006 etc.</source>
        <translation></translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="464"/>
        <source>N:</source>
        <translation>N:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="480"/>
        <source>E:</source>
        <translation>E:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="514"/>
        <source>Comma</source>
        <translation>Komma</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="530"/>
        <source>Semicolon</source>
        <translation>Semikolon</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="546"/>
        <source>Tab</source>
        <translation>Tab</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="562"/>
        <source>Separator</source>
        <translation>Separator</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="578"/>
        <source>Other:</source>
        <translation>Övrigt:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="612"/>
        <source>Yearly operations</source>
        <translation>Årlig operation</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="617"/>
        <source>Time influenced operation</source>
        <translation>Tidsberoende operation</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="634"/>
        <source>EPGS Coordinate system:</source>
        <translation>EPGCS Kordinatsystem:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="650"/>
        <source>99999</source>
        <translation>99999</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="666"/>
        <source>1</source>
        <translation>1</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="682"/>
        <source>Minimum yield:</source>
        <translation>Minsta skördevärde:</translation>
    </message>
    <message>
        <location filename="../widgets/import_text_dialog_base.ui" line="698"/>
        <source>Maximum yield:</source>
        <translation>Största skördevärde:</translation>
    </message>
</context>
<context>
    <name>InputShpHandler</name>
    <message>
        <location filename="../import_data/handle_input_shp_data.py" line="170"/>
        <source>Error:</source>
        <translation>Fel:</translation>
    </message>
    <message>
        <location filename="../import_data/handle_input_shp_data.py" line="96"/>
        <source>No shapes was found in the file</source>
        <translation>Ingen geometri hittades i filen</translation>
    </message>
    <message>
        <location filename="../import_data/handle_input_shp_data.py" line="170"/>
        <source>The projection is probably wrong, please change from 4326</source>
        <translation>Projektionen är troligen fel, var god ändra från 4326</translation>
    </message>
</context>
<context>
    <name>InputTextHandler</name>
    <message>
        <location filename="../import_data/handle_text_data.py" line="119"/>
        <source>No row selected!</source>
        <translation>Ingen rad vald!</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="248"/>
        <source>The shape file already exist on your computer, would you like to replace it?</source>
        <translation>Det finns redan en fil med samma namn på din dator, vill du spara över den?</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="295"/>
        <source>Error:</source>
        <translation>Fel:</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="292"/>
        <source>There needs to be a column called latitude (wgs84) or you need to change the EPSG system</source>
        <translation>Det måste finnas en kolumn som är döpt till latitude eller så måste du ändra koordinatssystem</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="295"/>
        <source>There needs to be a column called longitude (wgs84) or you need to change the EPSG system</source>
        <translation>Det måste finnas en kolumn som är döpt till longiitud eller så måste du ändra koordinatssystem</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="100"/>
        <source>You can only select one yield column!</source>
        <translation>Du kan endast välja en kolumn med skörd resultat!</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="300"/>
        <source>harvest</source>
        <translation>Skörd data</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="415"/>
        <source>soil</source>
        <translation>Jord data</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="301"/>
        <source>Yearly operations</source>
        <translation>Årlig operation</translation>
    </message>
    <message>
        <location filename="../import_data/handle_text_data.py" line="304"/>
        <source>Time influenced operation</source>
        <translation>Tidsberoende operation</translation>
    </message>
</context>
<context>
    <name>IrrigationHandler</name>
    <message>
        <location filename="../import_data/handle_irrigation.py" line="39"/>
        <source>ClintID must be a number</source>
        <translation>Klient id måste vara siffror</translation>
    </message>
    <message>
        <location filename="../import_data/handle_irrigation.py" line="106"/>
        <source>Wasn&apos;t able to fetch data from raindancer.
Are you sure that id, username and password was correct?</source>
        <translation>Kunde inte hämta data från Raindancer, är du säker på att du angav rätt användarnamn och lösenord?</translation>
    </message>
</context>
<context>
    <name>RunAnalyseDialogBase</name>
    <message>
        <location filename="../widgets/Run_analyse_base.ui" line="20"/>
        <source>Analyse window</source>
        <translation>Analys fönster</translation>
    </message>
    <message>
        <location filename="../widgets/Run_analyse_base.ui" line="71"/>
        <source>Update</source>
        <translation>Updatera</translation>
    </message>
    <message>
        <location filename="../widgets/Run_analyse_base.ui" line="130"/>
        <source>Minimum data points required:</source>
        <translation>Minsta antalet datapunker som krävs:</translation>
    </message>
    <message>
        <location filename="../widgets/Run_analyse_base.ui" line="143"/>
        <source>&lt;html&gt;&lt;head/&gt;&lt;body&gt;&lt;p&gt;The minimum number of samples to show in the graph&lt;/p&gt;&lt;/body&gt;&lt;/html&gt;</source>
        <translation>&lt;html&gt;&lt;head/&gt;&lt;body&gt;&lt;p&gt;Minsta antalet stickprov som visas i grafen&lt;/p&gt;&lt;/body&gt;&lt;/html&gt;</translation>
    </message>
    <message>
        <location filename="../widgets/Run_analyse_base.ui" line="146"/>
        <source>100</source>
        <translation>100</translation>
    </message>
</context>
<context>
    <name>TableManagement</name>
    <message>
        <location filename="../database_scripts/table_managment.py" line="74"/>
        <source>Error:</source>
        <translation>Fel:</translation>
    </message>
    <message>
        <location filename="../database_scripts/table_managment.py" line="39"/>
        <source>You need to fill in a new name</source>
        <translation>Du måste fylla i ett nytt namn</translation>
    </message>
    <message>
        <location filename="../database_scripts/table_managment.py" line="42"/>
        <source>You have to decide what type of data it is</source>
        <translation>Du måste välja vilken typ av data det är</translation>
    </message>
    <message>
        <location filename="../database_scripts/table_managment.py" line="45"/>
        <source>You need a new name</source>
        <translation>Du behöver välja ett nytt namn</translation>
    </message>
    <message>
        <location filename="../database_scripts/table_managment.py" line="53"/>
        <source>You need at least 2 dataset when merging</source>
        <translation>Du måste välja två data mångder att slå samman</translation>
    </message>
    <message>
        <location filename="../database_scripts/table_managment.py" line="74"/>
        <source>You can only have one dataset selected</source>
        <translation>Du kan bara ha en en data mängd vald</translation>
    </message>
    <message>
        <location filename="../database_scripts/table_managment.py" line="193"/>
        <source>Do you really want to remove the selected tables from the database?</source>
        <translation>Vill du verkligen ta bort de valda data mängderna?</translation>
    </message>
    <message>
        <location filename="../database_scripts/table_managment.py" line="194"/>
        <source>Yes</source>
        <translation>Ja</translation>
    </message>
    <message>
        <location filename="../database_scripts/table_managment.py" line="195"/>
        <source>No</source>
        <translation>Nej</translation>
    </message>
    <message>
        <location filename="../database_scripts/table_managment.py" line="41"/>
        <source>-Select data type -</source>
        <translation>-Välj data typ</translation>
    </message>
</context>
<context>
    <name>TableMgmtDialogBase</name>
    <message>
        <location filename="../widgets/table_managment.ui" line="14"/>
        <source>Edit datasets</source>
        <translation>Gör analys förändringar</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="45"/>
        <source>Datasets in database</source>
        <translation>Fältdata i databasen</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="58"/>
        <source>Parameters in dataset

 that could be analysed:</source>
        <translation>Parameterar i datan\n som kan bli analyserade:</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="76"/>
        <source>Edit
--&gt;</source>
        <translation>Editera\n ---&gt;</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="93"/>
        <source>Change dataset name</source>
        <translation>Ändra namnet på källan</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="109"/>
        <source>Combine multiple datasets</source>
        <translation>Kombinera flera källor</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="122"/>
        <source>*To rename any dataset or parameter make sure that only one is selected</source>
        <translation>*För att ändra namnet på en datakälla eller parameter, säkerställ att det är endast en som är markerad</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="145"/>
        <source>New name:</source>
        <translation>Nytt namn:</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="161"/>
        <source>Remove selected datasets</source>
        <translation>Ta bort vald datakälla</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="177"/>
        <source>Change parameter name</source>
        <translation>Ändra parameter namn</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="210"/>
        <source>Save
&lt;--</source>
        <translation>Spara &lt;--</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="228"/>
        <source>-Select data type -</source>
        <translation>-Välj data typ</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="233"/>
        <source>activity</source>
        <translation>Aktivitets data</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="238"/>
        <source>harvest</source>
        <translation>Skörd data</translation>
    </message>
    <message>
        <location filename="../widgets/table_managment.ui" line="243"/>
        <source>soil</source>
        <translation>Jord data</translation>
    </message>
</context>
<context>
    <name>multieditform</name>
    <message>
        <location filename="../widgets/multi_attribute_edit_dialog.ui" line="14"/>
        <source>MBupSelected</source>
        <translation>Attribut editering</translation>
    </message>
    <message>
        <location filename="../widgets/multi_attribute_edit_dialog.ui" line="65"/>
        <source>For all selected elements in the current layer set the value of field:</source>
        <translation>För alla valda punkter i lagret, sätt följande värde på attributet:</translation>
    </message>
    <message>
        <location filename="../widgets/multi_attribute_edit_dialog.ui" line="81"/>
        <source>equal to:</source>
        <translation>Är lika med:</translation>
    </message>
    <message>
        <location filename="../widgets/multi_attribute_edit_dialog.ui" line="94"/>
        <source>Keep latest input value</source>
        <translation>Spara senaste värde</translation>
    </message>
</context>
</TS>
