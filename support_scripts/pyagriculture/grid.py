import xml.etree.ElementTree as ET
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon


class Grid:
    def __init__(self, path):
        self.path = path
    
    def add_children(self, task_data_dict: dict, 
                     root: ET.Element, parent_id: str = None) -> dict[str, dict[str, dict[str, str]]]:
        """Adds data from the XML schema to a dict, walking down the tags in the .xml file.
        Includes parent-child relationships."""
        # Ensure the root tag exists in the dictionary
        if root.tag not in task_data_dict:
            task_data_dict[root.tag] = {}

        # Handle elements with an "A" attribute
        if "A" in root.attrib:
            element_id = root.attrib["A"]
            if element_id in task_data_dict[root.tag]:
                # If the element already exists, convert it to a list if necessary
                if not isinstance(task_data_dict[root.tag][element_id], list):
                    task_data_dict[root.tag][element_id] = [task_data_dict[root.tag][element_id]]
                task_data_dict[root.tag][element_id].append(root.attrib)
            else:
                # Add the element as a single entry
                task_data_dict[root.tag][element_id] = root.attrib
        else:
            # Handle elements without an "A" attribute (e.g., PTN, TIM)
            if "" in task_data_dict[root.tag]:
                if not isinstance(task_data_dict[root.tag][""], list):
                    task_data_dict[root.tag][""] = [task_data_dict[root.tag][""]]
                task_data_dict[root.tag][""].append(root.attrib)
            else:
                task_data_dict[root.tag][""] = root.attrib

        # Add parent reference
        if parent_id:
            root.attrib["parent_id"] = parent_id

        # Add child references
        if "children" not in root.attrib:
            root.attrib["children"] = []

        # Recursively process child elements
        for child in root:
            # Add the current element as the parent of the child
            child.attrib["parent_id"] = root.attrib.get("A", "")
            # Add the child to the parent's "children" list
            root.attrib["children"].append(child.attrib.get("A", ""))
            task_data_dict = self.add_children(task_data_dict, child, 
                                               parent_id=root.attrib.get("A", "") if root.attrib.get("A", "") != "" else root.tag)

        return task_data_dict

    def read_indata(self) -> list:
        tree = ET.parse(self.path + 'TASKDATA.xml')
        task_data_dict = {}
        self.task_dicts = self.add_children(task_data_dict, tree.getroot())
        tasks = []
        for key in task_data_dict['GRD']:
            try:
                grd = task_data_dict['GRD'][key]
                if isinstance(grd, list):
                    for g in grd:
                        gpd_ = self.read_grid_binary_file(self.path + g['G'], float(g['A']), float(g['B']), float(g['C']),
                                                float(g['D']), int(g['F']), int(g['E']), g.get('J', 0))
                        tasks.append(gpd_)
                else:
                    gpd_ = self.read_grid_binary_file(self.path + grd['G'], float(grd['A']), float(grd['B']), float(grd['C']),
                                                float(grd['D']), int(grd['F']), int(grd['E']), grd.get('J', 0))
                tasks.append(gpd_)
            except FileNotFoundError as e:
                pass
        return tasks

    def get_pdv(self, tsk, vpns):
        tzn_data = {}
        if 'TZN' in tsk['child']:
            if 'PDV' in tsk['child']['TZN'][0]['child']:
                for tzn in tsk['child']['TZN']:
                    tzn_data[int(tzn['A'])] = {'values': [], 'names': []}
                    for pdv in tzn['child']['PDV']:
                        value = float(pdv['B'])
                        vpn_ref = pdv.get('E')
                        if vpn_ref in vpns:
                            vpn = vpns[vpn_ref]
                            value += float(vpn['B'])
                            value *= float(vpn['C'])
                            name = vpn.get('E')
                        else:
                            name = 'unkown'
                        tzn_data[int(tzn['A'])]['values'].append(value)
                        tzn_data[int(tzn['A'])]['names'].append(name)
            else:
                raise ValueError("No PDV found in TZN")
        else:
            raise ValueError("No TZN found in task")
        return tzn_data
                    

    def read_grid_binary_file(self, file_path: str, n_start, e_start, n_delta, e_delta, nr_n_cols, nr_e_cols, tsk, vpns=None,
                              treatment_zone_code=0, qtask=None) -> gpd.GeoDataFrame:
        with open(file_path + '.bin', 'rb') as fin:
            binary_data = fin.read()
        read_point = 0
        east_count = 0
        north_count = 0
        cols = list(np.arange(e_start, e_start + e_delta * (nr_e_cols + 1), e_delta))
        rows = list(np.arange(n_start, n_start + n_delta * (nr_n_cols + 1), n_delta))
        polygons = []
        pdvs = {}
        tzn_data = self.get_pdv(tsk, vpns)
        for name in list(tzn_data.values())[0]['names']:
            pdvs[name] = []
        if treatment_zone_code == 0:
            data_type = (list(tzn_data.values())[0]['names'][0], np.dtype('uint8'))
            read_plus = 1
        else:
            read_plus = 4
            pdvs_keys = list(pdvs.keys())
            for name in list(tzn_data.values())[0]['names']:
                data_type = (name, np.dtype('int32'))
        while read_point < len(binary_data):
            try:

                for values in np.frombuffer(binary_data, [data_type],
                                        count=1, offset=read_point):
                    if qtask != 'debug':
                        if qtask.isCanceled():
                            return None
                    for idx, value in enumerate(values):
                        if treatment_zone_code == 0:    
                            pdv = tzn_data[value]
                            pdvs[pdv['names'][idx]].append(pdv['values'][idx])
                        else:
                            pdvs[pdvs_keys[idx]].append(value)
                    read_point += read_plus
                    if east_count >= nr_e_cols:
                        east_count = 0
                        north_count += 1
                    x = cols[east_count]
                    y = rows[north_count]
                    polygons.append(Polygon([(x, y), (x + e_delta, y), (x + e_delta, y + n_delta), (x, y + n_delta)]))
                    east_count += 1
            except Exception as e:
                pass
        pdvs['grid'] = polygons
        grid_ = gpd.GeoDataFrame(pdvs)
        # grid_ = grid_.set_crs(epsg=4326)
        # Add longitude and latitude columns based on the centroid of the polygons
        grid_['longitude'] = grid_['grid'].apply(lambda geom: geom.centroid.x if geom else None)
        grid_['latitude'] = grid_['grid'].apply(lambda geom: geom.centroid.y if geom else None)
        grid_.attrs['unit_row'] = tzn_data[int(tsk['child']['TZN'][0]['A'])]['names']
        grid_.attrs['columns'] = tzn_data[int(tsk['child']['TZN'][0]['A'])]['names']
        return grid_
    

if __name__ == '__main__':
    g = Grid('C:/Users/AxelHor/Downloads/TASKDATA (1)/')
    grid_list = g.read_indata()
    for i, grid in enumerate(grid_list):
        grid.to_file(f"C:/Users/AxelHor/Downloads/TASKDATA (1)/grd_{i}.shp")
