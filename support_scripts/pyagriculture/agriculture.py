# Author Axel Hörteborn
from typing import Never, Self
from datetime import datetime, timedelta
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
if __name__ == '__main__':
    import sys
    sys.path.append(os.path.abspath(os.path.curdir))
    from support_scripts.__init__ import TR, getfile_insensitive
    from support_scripts.pyagriculture.sorting_utils import find_by_key
    from support_scripts.pyagriculture.grid import Grid
else:
    from .. import TR, getfile_insensitive
    from .sorting_utils import find_by_key
    from .grid import Grid
#from .cython_agri import read_static_binary_data, cython_read_dlvs


class PyAgriculture:
    def __init__(self: Self, path: str) -> None:
        self.path = path
        translate = TR('Agriculture')
        self.tr = translate.tr
        self.tasks = []
        self.task_dicts = {}
        self.task_infos = []
        self.dlvs = []
        self.dlv_idx = {}
        self.read_with_cython = False
        self.rename_columns_with_units = False
        self.start_date = datetime(year=1980, month=1, day=1)
        self.dt = None
        self.static_bytes = 0
        self.convert_field = False
        self._check_path_is_ok()

    def _check_path_is_ok(self: Self) -> None:
        if self.path[-1] not in ['/', '\\']:
            self.path += '/'
        path = getfile_insensitive(self.path + 'TaskData.xml')
        if not Path(path).is_file():
            print(self.path + 'TaskData.xml')
            raise FileNotFoundError(self.tr('The specified path does not contain a taskdata.xml file'))

    @staticmethod
    def _add_from_root_or_child(r_or_c: ET.Element, 
                                task_data_dict: dict) -> list:
        """
        Adds an element to the task_data_dict, initializing it if necessary.
        """
        if r_or_c.tag not in task_data_dict:
            task_data_dict[r_or_c.tag] = {}

        found_children = False
        element_id = r_or_c.attrib.get("A")
        if element_id:
            # Check if the element already exists
            if element_id not in task_data_dict[r_or_c.tag]:
                found_children = True
                task_data_dict[r_or_c.tag][element_id] = r_or_c.attrib
                task_data_dict[r_or_c.tag][element_id]['parent_tag'] = r_or_c.tag
                task_data_dict[r_or_c.tag][element_id]['parent_id'] = r_or_c.attrib.get("parent_id", None)
            else:
                # If the element already exists, skip adding it again
                return [task_data_dict, found_children]

        return [task_data_dict, found_children]

    def add_children(self: Self, task_data_dict: dict, 
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
    
    def get_structure(self: Self, tree: ET.Element, task_data_structure={}) -> dict:
        """Adds data from the xml schema to a dict, walking down the tags in the .xml file
        """
        for child in tree:
            if child.tag not in task_data_structure.keys():
                task_data_structure[child.tag] = []
            grand_child = self.get_structure(child, {})
            child.attrib["child"] = grand_child
            task_data_structure[child.tag].append(child.attrib)
        return task_data_structure

    def add_xfr_parts(self: Self, tree:ET.ElementTree) -> ET.ElementTree:
        for child in tree.getroot():
            if child.tag == 'XFR':
                child_data = ET.parse(getfile_insensitive(self.path + child.attrib["A"] + '.xml'))
                child_list = list(child_data.getroot())
                for sub in child_list:
                    tree.getroot().append(sub)
        return tree

    def gather_task_names(self: Self, 
                          continue_on_fail: bool=True) -> list:
        """This function will use the specified path to the taskdata.xml to build a tree of all information in the
         taskdata file and all the files tlg xml and bin files."""

        task_data_dict = {}
        task_names = []
        file_names = []
        tree = ET.parse(getfile_insensitive(self.path + 'TaskData.xml'))
        tree = self.add_xfr_parts(tree)
        self.task_dicts = self.add_children(task_data_dict, tree.getroot())
        task_structure = self.get_structure(tree.getroot())
        if 'TSK' in task_structure.keys():
            if 'GRD' in task_structure['TSK'][0]['child'].keys():
                for i, tsk in enumerate(task_structure['TSK']):
                    task_names.append(f'unknown - {tsk["B"]}')
                    file_names.append(tsk['child']['GRD'][0]['G'])
            else:
                for i, tsk in enumerate(list(self.task_dicts['TLG'].keys())):
                    equipment = 'unknown'
                    try:
                        equipment = self.task_dicts['DVC'][task_structure['TSK'][i]["child"]["CNN"][0]["C"]]["B"]
                    except:
                        pass
                    try:
                        file = getfile_insensitive(self.path + self.task_dicts['TLG'][tsk]['A'] + '.xml')
                        branch = ET.parse(file)
                    except (FileNotFoundError, ET.ParseError):
                        if not continue_on_fail:
                            raise FileNotFoundError(self.tr(f"The TLG file {self.task_dicts['TLG'][tsk]['A']}.xml was not found."))
                        else:
                            continue
                    tlg_dict = self.add_children({}, branch.getroot())
                    self.set_ptn_data(tlg_dict)
                    tlg_dict = self.combine_task_tlg_data(tlg_dict, task_data_dict)
                    self.task_infos.append(tlg_dict)
                    try:
                        task_name = task_data_dict['TSK'][list(task_data_dict['TSK'].keys())[i]]['B']
                    except IndexError:
                        task_name = 'unkown'
                    task_names.append(f"{equipment}-{task_name}")
                    file_names.append(self.task_dicts['TLG'][tsk]['A'] + '.xml')
        return task_names, file_names

    def gather_data(self: Self, qtask: str, 
                    only_tasks: list[str|Never|Never]=[], 
                    most_importants: list=['dry yield']) -> None:
        """This function will use the specified path to the taskdata.xml to build a tree of all information in the
         taskdata file and all the files tlg xml and bin files."""
        reset_columns = False  # Resets all columns when the "most_important" have been used.
        task_data_dict = {}
        tree = ET.parse(getfile_insensitive(self.path + 'TASKDATA.xml'))
        tree = self.add_xfr_parts(tree)
        self.task_dicts = self.add_children(task_data_dict, tree.getroot())
        structure = self.get_structure(tree.getroot())
        if 'TSK' in self.task_dicts.keys():
            if 'GRD' in self.task_dicts.keys():
                tasked_run = []
                grid_data = Grid(self.path + 'TASKDATA.xml')
                for i, tsk in enumerate(structure['TSK']):
                    g = tsk['child']['GRD'][0]
                    if tsk['A'] not in tasked_run:
                        tasked_run.append(tsk['A'])
                    else:
                        continue
                    if len(only_tasks) > 0:
                        if not g['G'] in only_tasks:
                            continue
                    gdp = grid_data.read_grid_binary_file(self.path + g['G'], float(g['A']), float(g['B']), float(g['C']),
                                              float(g['D']), int(g['F']), int(g['E']), tsk, self.task_dicts.get('VPN'))
                    self.tasks.append(gdp)
                    if qtask != "debug":
                        qtask.setProgress(float(i/len(list(self.task_dicts['TSK'].keys())) * 90)+10)
            else:                
                nr_tlgs = len(list(self.task_dicts['TLG'].keys()))
                for i, tsk in enumerate(list(self.task_dicts['TLG'].keys())):
                    try:
                        file = getfile_insensitive(self.path + self.task_dicts['TLG'][tsk]['A'] + '.xml')
                        branch = ET.parse(file)
                    except (FileNotFoundError, ET.ParseError):
                        continue
                    if len(only_tasks) > 0:
                        if not self.task_dicts['TLG'][tsk]['A'] + '.xml' in only_tasks:
                            continue
                    self.dlvs = []
                    self.dlv_idx = {}
                    tlg_dict = self.add_children({}, branch.getroot())
                    self.set_ptn_data(tlg_dict)
                    tlg_dict = self.combine_task_tlg_data(tlg_dict, task_data_dict)
                    self.task_infos.append(tlg_dict)
                    columns = self.get_tlg_columns(tlg_dict)
                    try:
                        task_name = task_data_dict['TSK'][list(task_data_dict['TSK'].keys())[i]]['B']
                    except IndexError:
                        task_name = 'unkown'
                    if len(most_importants) == 0:
                        most_important = None
                    else:
                        most_important = most_importants[i]
                    path = self.path + self.task_dicts['TLG'][tsk]['A']
                    task = self.read_binaryfile(path, tlg_dict, columns,
                                                        most_important, task_name, reset_columns)
                    if task is not None:
                        self.tasks.append(task)
                    if qtask != "debug":
                        qtask.setProgress(float(i/nr_tlgs * 90)+10)
                
        if self.convert_field:
            self.convert_yield_field()

    def set_ptn_data(self: Self, tlg_dict: dict) -> None:
        if 'PTN' not in tlg_dict.keys():
            raise BaseException(self.tr('Point data does not exist in all TLG files..'))
        dtypes = [('millisFromMidnight', np.dtype('uint32')),
                  ('days', np.dtype('uint16')),
                  ('pos north', np.dtype('int32')),
                  ('pos east', np.dtype('int32'))]
        static_bytes = 14
        if 'C' in tlg_dict['PTN'][''].keys():
            dtypes.append(('pos up', np.dtype('int32')))
            static_bytes += 4
        dtypes.append(('pos status', np.dtype('uint8')))
        static_bytes += 1
        if 'E' in tlg_dict['PTN'][''].keys():
            dtypes.append(('pdop', np.dtype('uint16')))
            static_bytes += 2
        if 'F' in tlg_dict['PTN'][''].keys():
            dtypes.append(('hdop', np.dtype('uint16')))
            static_bytes += 2
        if 'G' in tlg_dict['PTN'][''].keys():
            dtypes.append(('nr_sat', np.dtype('byte')))
            static_bytes += 1
        if 'H' in tlg_dict['PTN'][''].keys():
            dtypes.append(('GPS time', np.dtype('uint32')))
            static_bytes += 4
        if 'I' in tlg_dict['PTN'][''].keys():
            dtypes.append(('GPS date', np.dtype('uint16')))
            static_bytes += 2
        dtypes.append(('nr dlv', np.dtype('uint8')))
        static_bytes += 1
        self.dt = np.dtype(dtypes)
        self.static_bytes = static_bytes

    @staticmethod
    def get_tlg_columns(tlg_dict: dict[str, dict[str, dict[str, str]]]) -> list:
        columns = ['time_stamp', 'latitude', 'longitude']
        if 'C' in tlg_dict['PTN'][''].keys():
            columns.append('pos_up')
        columns.append('position_status')
        if 'E' in tlg_dict['PTN'][''].keys():
            columns.append('pdop')
        if 'F' in tlg_dict['PTN'][''].keys():
            columns.append('hdop')
        if 'G' in tlg_dict['PTN'][''].keys():
            columns.append('nr_sat')
        if 'H' and 'I' in tlg_dict['PTN'][''].keys():
            columns.append('GPS time')

        for key in tlg_dict['DLV'].keys():
            if isinstance(tlg_dict['DLV'][key], list):
                for dlv in tlg_dict['DLV'][key]:
                    if 'Name' in dlv.keys():
                        columns.append(dlv['Name'])
            else:
                if 'Name' in tlg_dict['DLV'][key].keys():
                    columns.append(tlg_dict['DLV'][key]['Name'])
        return columns

    @staticmethod
    def _add_device(task_data_dict: dict[str, dict[str, dict[str, str]]], 
                    dlv_key: str, dlv_idx: int,
                    tlg_dict: dict[str, dict[str, dict[str, str]]], 
                    pd_id: str, det_a: str) -> None:
        """
        Adds device information to the DLV entry, resolving names and units using DPD and DPT mappings.
        Ensures the correct DOR is used based on the DET's A value.
        """
        # Iterate through all DORs in the DET
        b, c, d = find_by_key(tlg_dict['DLV'], 'B', pd_id)
        for dor_key in task_data_dict['DET'][det_a]['children']:
            if dor_key in task_data_dict['DPD']:
                dpd_list = task_data_dict['DPD'][dor_key]
                
                if isinstance(dpd_list, list):
                    # Find the correct DPD where the PD ID matches
                    dpd = next((dpd for dpd in dpd_list if dpd['B'] == pd_id), None)
                else:
                    dpd = dpd_list if dpd_list['B'] == pd_id else None

                if dpd:
                    # Assign the name from the DPD entry
                    tlg_dict['DLV'][dlv_key][dlv_idx]['Name'] = dpd['E']
                    # Check for DVP (Device Value Parameters) and assign scale, offset, and unit
                    if 'F' in dpd.keys():
                        if dpd['F'] not in task_data_dict['DVP']:
                            return
                        dvp = task_data_dict['DVP'][dpd['F']]
                        tlg_dict['DLV'][dlv_key][dlv_idx]['DVP'] = {
                            'nr_decimals': dvp['D'],
                            'scale': dvp['C'],
                            'offset': dvp['B']
                        }
                        if 'E' in dvp.keys():
                            tlg_dict['DLV'][dlv_key][dlv_idx]['DVP']['unit'] = dvp['E']
                    return  # Exit after finding the correct DPD

        # If no matching DPD is found, check DPT
        for dor_key in task_data_dict['DET'][det_a].keys():
            if dor_key in task_data_dict['DPT']:
                dpt_list = task_data_dict['DPT'][dor_key]
                if isinstance(dpt_list, list):
                    # Find the correct DPT where the PD ID matches
                    dpt = next((dpt for dpt in dpt_list if dpt['B'] == pd_id), None)
                else:
                    dpt = dpt_list if dpt_list['B'] == pd_id else None

                if dpt:
                    # Assign the name from the DPT entry
                    tlg_dict['DLV'][dlv_key][dlv_idx]['Name'] = dpt['D']
                    # Check for DVP and assign scale, offset, and unit
                    if 'E' in dpt.keys():
                        if dpt['E'] not in task_data_dict['DVP']:
                            return
                        dvp = task_data_dict['DVP'][dpt['E']]
                        tlg_dict['DLV'][dlv_key][dlv_idx]['DVP'] = {
                            'nr_decimals': dvp['D'],
                            'scale': dvp['C'],
                            'offset': dvp['B']
                        }
                        if 'E' in dvp.keys():
                            tlg_dict['DLV'][dlv_key][dlv_idx]['DVP']['unit'] = dvp['E']
                    return  # Exit after finding the correct DPT

    def combine_task_tlg_data(self: Self, 
                              tlg_dict: dict[str, dict[str, dict[str, str]]], 
                              task_data_dict: dict[str, dict[str, dict[str, str]]]
                              ) -> dict[str, dict[str, dict[str, str]]]:
        for dlv_key in tlg_dict['DLV'].keys():
            dlvs = tlg_dict['DLV'][dlv_key]
            if not isinstance(dlvs, list):
                tlg_dict['DLV'][dlv_key] = [dlvs]
                dlvs = [dlvs]
            for idx, dlv in enumerate(dlvs):
                # Obtains the DeviceElementIdRef
                de_id = dlv['C']
                # Obtains the ProcessDataDDI
                pd_id = dlv['A']
                # Adding the DeviceElement to the tlg dict
                det_a = de_id  # Pass the DET's A value
                if not isinstance(de_id, list):
                    dlv['DET'] = task_data_dict['DET'][de_id]
                    dlv['DET']['list'] = False
                else:
                    dlv['DET'] = {}
                    dlv['DET']['list'] = True
                    for i, de_i in enumerate(de_id):
                        dlv['DET'][i] = {}
                        dlv['DET'][i] = task_data_dict['DET'][de_i]
                self._add_device(task_data_dict, dlv_key, idx, tlg_dict, pd_id, det_a)
        return tlg_dict

    def _read_static_binary_python(self: Self, data_row: list, 
                                   read_point: int, binary_data: object, 
                                   tlg_dict: dict) -> list:
        nr_d = 3
        np_data = np.frombuffer(binary_data, self.dt, count=1, offset=read_point)
        millis_from_midnight = int(np_data[0][0])
        days = int(np_data[0][1])
        actual_time = self.start_date + timedelta(days=days, milliseconds=millis_from_midnight)
        data_row[0] = actual_time.strftime('%Y-%m-%dT%H:%M:%S')
        data_row[1] = np_data[0][2] * pow(10, -7)
        data_row[2] = np_data[0][3] * pow(10, -7)
        for key in tlg_dict['PTN'][''].keys():
            if key in ['C', 'D', 'E', 'F', 'G']:
                data_row[nr_d] = np_data[0][nr_d + 1]
                nr_d += 1
        if 'H' and 'I' in tlg_dict['PTN'][''].keys():
            millis_from_midnight = int(np_data[0][nr_d + 1])
            days = int(np_data[0][nr_d + 2])
            actual_time = self.start_date + timedelta(days=days, milliseconds=millis_from_midnight)
            data_row[nr_d] = actual_time.strftime('%Y-%m-%dT%H:%M:%S')
            nr_d += 2
        nr_dlvs = np_data[0][nr_d + 1]
        return [data_row, nr_dlvs, nr_d]

    def read_binaryfile(self: Self, file_path: str, 
                        tlg_dict: dict, 
                        df_columns: list, most_important: str,
                        task_name: str, reset_columns: bool
                        ) -> pd.DataFrame:
        with open(getfile_insensitive(file_path + '.bin'), 'rb') as fin:
            binary_data = fin.read()
        read_point = 0
        nr_columns = len(df_columns)
        to_tlg_df = []
        data_row = [None] * nr_columns
        unit_row = [None] * nr_columns
        dpd_ids = {}
        for dpd in self.task_dicts['DPD'].values():
            if isinstance(dpd, list):
                for dpd_i in dpd:
                    dpd_ids[f'{dpd_i["A"]}-{dpd_i["B"]}'] = dpd_i
            else:
                dpd_ids[f'{dpd["A"]}-{dpd["B"]}'] = dpd
        
        for key, item in tlg_dict['DLV'].items():
            for item_i in item:
                self.dlvs.append(item_i['DVP'])

        while read_point < len(binary_data):
            # The first part of each "row" contains of static data, a timestamp and some satellite data.
            if self.read_with_cython:
                raise DeprecationWarning("Cython reading is removed")
            #    data_row, nr_dlvs, nr_static = read_static_binary_data(data_row, read_point, binary_data, tlg_dict,
            #                                                           self.dt, self.start_date)
            #    read_point += self.static_bytes
            #    read_point, data_row, unit_row = cython_read_dlvs(binary_data, read_point, nr_dlvs, nr_static, dpd_ids,
            #                                                self.task_dicts, unit_row, data_row, self.dlvs,
            #                                                self.dlv_idx)
            else:
                data_row, nr_dlvs, nr_static = self._read_static_binary_python(data_row, read_point, binary_data,
                                                                               tlg_dict)
                read_point += self.static_bytes
                read_point, data_row, unit_row = self.read_dlvs(binary_data, read_point, nr_dlvs, nr_static, 
                                                                unit_row, data_row, self.dlvs)

            if most_important is None:
                to_tlg_df.append(data_row[:])
                continue
            if data_row[df_columns.index(most_important)] is not None:
                to_tlg_df.append(data_row[:])
                if reset_columns:
                    data_row = [None] * nr_columns
                else:
                    data_row[df_columns.index(most_important)] = None
        if len(to_tlg_df) == 0:
            return None
        if self.rename_columns_with_units:
            for idx, col_name in enumerate(df_columns):
                if idx >= nr_static:
                    try:
                        df_columns[idx] = col_name + f" ({unit_row[idx-nr_static+1]})"
                        if unit_row[idx-nr_static-1] is None:
                            continue
                    except IndexError and KeyError:
                        pass
        df = pd.DataFrame(to_tlg_df, columns=df_columns)
        for i in range(nr_static - 3): #Exclude 1 + 2 for lat/lon
            unit_row.insert(i, '')
        df.attrs['task_name'] = task_name
        df.attrs['columns'] = df_columns
        df.attrs['unit_row'] = unit_row

        return df

    @staticmethod
    def read_dlvs(binary_data: bytes, read_point: int, 
                  nr_dlvs: int, nr_static: int, unit_row: list, 
                  data_row: list, dlvs: list) -> list:
        for idx, dlv in np.frombuffer(binary_data, [('DLVn', np.dtype('uint8')),
                                                   ('PDV', np.dtype('int32'))],
                                     count=nr_dlvs, offset=read_point):
            read_point += 5
            dvp = dlvs[idx]
            decimals = float(10**int(dvp['nr_decimals']))
            dlv = int((dlv + float(dvp['offset'])) * float(dvp['scale']) * decimals + 0.5) / decimals
            if unit_row[idx + 1] is None:
                if 'unit' in dvp.keys():
                    unit_row[idx + 1] = dvp['unit']
            try:
                data_row[idx + nr_static] = dlv
            except:
                pass
        return [read_point, data_row, unit_row]

    def convert_yield_field(self):
        """Converts the yield output from lb/ac to kg/ha"""
        column = 'dry yield (lb/ac)'
        for j, task in enumerate(self.tasks):
            if isinstance(task, pd.DataFrame):
                self.tasks[j][column] = task[column] * 1.12085
                self.tasks[j].rename({'dry yield (lb/ac)': 'dry yield (kg/ha)'}, axis='columns', inplace=True)
