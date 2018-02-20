from osgeo import ogr


def shapefile_create_def_field( field_def ):

    fieldDef = ogr.FieldDefn( field_def['name'], field_def['ogr_type'] )
    if field_def['ogr_type'] == ogr.OFTString:
        fieldDef.SetWidth(field_def['width'] )
        
    return fieldDef


def shapefile_create( path, geom_type, fields_dict_list, plugin_dir, layer_name = "layer"):
    file_name = path[:-4]
    text_file = open(file_name + ".prj", "w")
    text_file.write('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["'
                    'WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",'
                    '0],UNIT["Degree",0.017453292519943295]]')
    text_file.close()
    driver = ogr.GetDriverByName("ESRI Shapefile")
    
    outShapefile = driver.CreateDataSource( str( path ) )
    if outShapefile is None:
        raise (Exception, 'Unable to save shapefile in provided path')

    outShapelayer = outShapefile.CreateLayer("layer", geom_type=geom_type )
        
    map( lambda field_def_params: outShapelayer.CreateField( shapefile_create_def_field( field_def_params ) ), fields_dict_list )

    return outShapefile, outShapelayer
