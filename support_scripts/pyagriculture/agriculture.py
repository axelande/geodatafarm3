# Author Axel Hörteborn
from datetime import datetime, timedelta
import json
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from pyAgriculture.sorting_utils import find_by_key
from pathlib import Path


class PyAgriculture:
    """This is a copy of the python package https://github.com/axelande/pyAgriculture11783 """
    def __init__(self, path):
        self.path = path
        self.tasks = []
        self.task_dicts = {}
        self.task_infos = []
        self.read_with_cython = True
        self.start_date = datetime(year=1980, month=1, day=1)
        self.dt = None
        self.static_bytes = 0
        self.convert_field = False
        self._check_path_is_ok()

    def _check_path_is_ok(self):
        if self.path[-1] not in ['/', '\\']:
            self.path += '/'
        if not Path(self.path + 'TaskData.xml').is_file():
            print(self.path + 'TaskData.xml')
            raise FileNotFoundError('The specified path does not contain a taskdata.xml file')

    @staticmethod
    def _add_from_root_or_child(r_or_c, task_data_dict: dict) -> list:
        """
        :param r_or_c: Root or child object
        """
        if r_or_c.tag not in task_data_dict.keys():
            task_data_dict[r_or_c.tag] = {}
        found_children = False
        if r_or_c.attrib["A"] not in task_data_dict[r_or_c.tag].keys():
            found_children = True
            task_data_dict[r_or_c.tag][r_or_c.attrib["A"]] = r_or_c.attrib
            task_data_dict[r_or_c.tag][r_or_c.attrib["A"]]['parent_tag'] = r_or_c.tag
            try:
                task_data_dict[r_or_c.tag][r_or_c.attrib["A"]]['parent_id'] = r_or_c.attrib["A"]
            except Exception as e1:
                task_data_dict[r_or_c.tag][r_or_c.attrib["A"]]['parent_id'] = None
        else:
            for attribute in r_or_c.attrib.keys():
                if attribute in task_data_dict[r_or_c.tag][r_or_c.attrib["A"]]:
                    if isinstance(task_data_dict[r_or_c.tag][r_or_c.attrib["A"]][attribute], list):
                        if r_or_c.attrib[attribute] not in task_data_dict[r_or_c.tag][r_or_c.attrib["A"]][attribute]:
                            task_data_dict[r_or_c.tag][r_or_c.attrib["A"]][attribute].append(r_or_c.attrib[attribute])
                    else:
                        if task_data_dict[r_or_c.tag][r_or_c.attrib["A"]][attribute] != r_or_c.attrib[attribute]:
                            task_data_dict[r_or_c.tag][r_or_c.attrib["A"]][attribute] = [task_data_dict[r_or_c.tag][r_or_c.attrib["A"]][attribute], r_or_c.attrib[attribute]]
                else:
                    task_data_dict[r_or_c.tag][r_or_c.attrib["A"]][attribute] = r_or_c.attrib[attribute]
            a=1
        return [task_data_dict, found_children]

    def add_children(self, task_data_dict, root):
        """Adds data from the xml schema to a dict, walking down the tags in the .xml file
        """
        if "A" in root.keys():
            task_data_dict, found_children = self._add_from_root_or_child(root, task_data_dict)
        for child in root:
            task_data_dict, found_children = self._add_from_root_or_child(child, task_data_dict)
            if found_children:
                for sub_c in child:
                    self.add_children(task_data_dict, sub_c)
        return task_data_dict

    def gather_task_names(self, continue_on_fail=True) -> list:
        """This function will use the specified path to the taskdata.xml to build a tree of all information in the
         taskdata file and all the files tlg xml and bin files."""

        task_data_dict = {}
        task_names = []
        tree = ET.parse(self.path + 'TASKDATA.xml')
        self.task_dicts = self.add_children(task_data_dict, tree.getroot())
        if 'TLG' in self.task_dicts.keys():
            for i, tsk in enumerate(list(self.task_dicts['TLG'].keys())):
                try:
                    branch = ET.parse(self.path + self.task_dicts['TLG'][tsk]['A'] + '.xml')
                except FileNotFoundError:
                    if not continue_on_fail:
                        raise FileNotFoundError(f"The TLG file {self.task_dicts['TLG'][tsk]['A']}.xml was not found.")
                    else:
                        continue
                except ET.ParseError:
                    if not continue_on_fail:
                        raise FileNotFoundError(f"The file {self.task_dicts['TLG'][tsk]['A']}.xml was empty")
                    else:
                        continue
                except Exception as e:
                    print('error: ' + str(e))
                tlg_dict = self.add_children({}, branch.getroot())
                self.set_ptn_data(tlg_dict)
                tlg_dict = self.combine_task_tlg_data(tlg_dict, task_data_dict)
                self.task_infos.append(tlg_dict)
                try:
                    task_name = task_data_dict['TSK'][list(task_data_dict['TSK'].keys())[i]]['B']
                except IndexError:
                    task_name = 'unkown'
                task_names.append(task_name)
        return task_names

    def gather_data(self, most_important='dry yield', continue_on_fail=True, only_tasks=[]):
        """This function will use the specified path to the taskdata.xml to build a tree of all information in the
         taskdata file and all the files tlg xml and bin files."""

        task_data_dict = {}
        tree = ET.parse(self.path + 'TASKDATA.xml')
        self.task_dicts = self.add_children(task_data_dict, tree.getroot())
        if 'TLG' in self.task_dicts.keys():
            for i, tsk in enumerate(list(self.task_dicts['TLG'].keys())):
                try:
                    branch = ET.parse(self.path + self.task_dicts['TLG'][tsk]['A'] + '.xml')
                except FileNotFoundError:
                    if not continue_on_fail:
                        raise FileNotFoundError(f"The TLG file {self.task_dicts['TLG'][tsk]['A']}.xml was not found.")
                    else:
                        continue
                except ET.ParseError:
                    if not continue_on_fail:
                        raise FileNotFoundError(f"The file {self.task_dicts['TLG'][tsk]['A']}.xml was empty")
                    else:
                        continue
                except Exception as e:
                    print('error: ' + str(e))
                #if i < 70 or i > 80:
                #    continue
                tlg_dict = self.add_children({}, branch.getroot())
                self.set_ptn_data(tlg_dict)
                tlg_dict = self.combine_task_tlg_data(tlg_dict, task_data_dict)
                self.task_infos.append(tlg_dict)
                columns = self.get_tlg_columns(tlg_dict)
                try:
                    task_name = task_data_dict['TSK'][list(task_data_dict['TSK'].keys())[i]]['B']
                except IndexError:
                    task_name = 'unkown'
                if len(only_tasks) > 0:
                    if not task_name in only_tasks:
                        continue
                self.tasks.append(self.read_binaryfile(self.path + self.task_dicts['TLG'][tsk]['A'], tlg_dict, columns,
                                                       most_important, task_name))

        if self.convert_field:
            self.convert_yield_field()

    def set_ptn_data(self, tlg_dict: dict) -> None:
        if 'PTN' not in tlg_dict.keys():
            raise BaseException('Point data does not exist in all TLG files..')
        dtypes = [('millisFromMidnight', np.dtype('uint32')),
                  ('days', np.dtype('uint16')),
                  ('pos north', np.dtype('int32')),
                  ('pos east', np.dtype('int32'))]
        static_bytes = 16
        if 'C' in tlg_dict['PTN'][''].keys():
            dtypes.append(('pos up', np.dtype('int32')))
            static_bytes += 4
        dtypes.append(('pos status', np.dtype('uint8')))
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
        self.dt = np.dtype(dtypes)
        self.static_bytes = static_bytes

    @staticmethod
    def get_tlg_columns(tlg_dict) -> list:
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
            columns.append('gps_time')

        for key in tlg_dict['DLV'].keys():
            if 'Name' in tlg_dict['DLV'][key].keys():
                columns.append(tlg_dict['DLV'][key]['Name'].lower())
        return columns

    @staticmethod
    def _add_device(task_data_dict, dlv_key, tlg_dict, pd_id):
        found, dpd_key = find_by_key(task_data_dict['DPD'], 'B', pd_id)
        if found:
            dpd = task_data_dict['DPD'][dpd_key]
            tlg_dict['DLV'][dlv_key]['Name'] = dpd['E']
            if 'F' in dpd.keys():
                dvp = task_data_dict['DVP'][dpd['F']]
                tlg_dict['DLV'][dlv_key]['DVP'] = {'nr_decimals': dvp['D'], 'scale': dvp['C'],
                                                   'offset': dvp['B']}
                if 'E' in dvp.keys():
                    tlg_dict['DLV'][dlv_key]['DVP']['unit'] = dvp['E']

    def combine_task_tlg_data(self, tlg_dict, task_data_dict):
        for dlv_key in tlg_dict['DLV'].keys():
            # Obtains the DeviceElementIdRef
            de_id = tlg_dict['DLV'][dlv_key]['C']
            # Obtains the ProcessDataDDI
            pd_id = tlg_dict['DLV'][dlv_key]['A']
            # Adding the DeviceElement to the tlg dict
            if not isinstance(de_id, list):
                tlg_dict['DLV'][dlv_key]['DET'] = task_data_dict['DET'][de_id]
                tlg_dict['DLV'][dlv_key]['DET']['list'] = False
            else:
                tlg_dict['DLV'][dlv_key]['DET'] = {}
                tlg_dict['DLV'][dlv_key]['DET']['list'] = True
                for i, de_i in enumerate(de_id):
                    tlg_dict['DLV'][dlv_key]['DET'][i] = {}
                    tlg_dict['DLV'][dlv_key]['DET'][i] = task_data_dict['DET'][de_i]
            self._add_device(task_data_dict, dlv_key, tlg_dict, pd_id)
        return tlg_dict

    def _read_static_binary_python(self, data_row: list, read_point: int, binary_data: object, tlg_dict: dict) -> list:
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
        return [data_row, nr_dlvs, nr_d - 1]

    def read_binaryfile(self, file_path: str, tlg_dict: dict, df_columns: list, most_important: str,
                        task_name: str) -> pd.DataFrame:
        with open(file_path + '.bin', 'rb') as fin:
            binary_data = fin.read()
        read_point = 0
        nr_columns = len(df_columns)
        to_tlg_df = []
        dlvs = list(tlg_dict['DLV'])
        data_row = [None] * nr_columns
        unit_row = [None] * nr_columns

        while read_point < len(binary_data):
            # The first part of each "row" contains of static data, a timestamp and some satellite data.
            if self.read_with_cython:
                from pyAgriculture.cython_agri import read_static_binary_data
                data_row, nr_dlvs, nr_static = read_static_binary_data(data_row, read_point, binary_data, tlg_dict,
                                                                       self.dt, self.start_date)
            else:
                data_row, nr_dlvs, nr_static = self._read_static_binary_python(data_row, read_point, binary_data,
                                                                              tlg_dict)
            read_point += self.static_bytes
            for nr, dlv in np.frombuffer(binary_data, [('DLVn', np.dtype('uint8')),
                                                       ('PDV', np.dtype('int32'))],
                                         count=nr_dlvs, offset=read_point):
                if (nr + nr_static + 1) >= len(data_row):
                    # fail?
                    nr = len(data_row) - 1 - nr_static
                if nr >= len(dlvs):
                    dlv_key = dlvs[-1]
                else:
                    dlv_key = dlvs[nr]
                if 'DVP' in tlg_dict['DLV'][dlv_key].keys():
                    dvp = tlg_dict['DLV'][dlv_key]['DVP']
                    dlv = (dlv + float(dvp['offset'])) * float(dvp['scale']) * pow(10, -int(dvp['nr_decimals']))
                    if unit_row[nr] is None:
                        if 'unit' in dvp.keys():
                            unit_row[nr] = dvp['unit']
                data_row[nr + nr_static] = dlv
                read_point += 5
            if most_important is None:
                to_tlg_df.append(data_row)
                continue
            if data_row[df_columns.index(most_important)] is not None:
                to_tlg_df.append(data_row)
                data_row = [None] * nr_columns
        if len(to_tlg_df) == 0:
            return pd.DataFrame([[None] * nr_columns], columns=df_columns)
        for idx, col_name in enumerate(df_columns):
            if idx > (nr_static - 1):
                try:
                    df_columns[idx] = col_name + f" ({tlg_dict['DLV'][dlvs[idx - nr_static]]['DVP']['unit']})"
                    if col_name == most_important and 'lb/ac' in tlg_dict['DLV'][dlvs[idx - nr_static]]['DVP']['unit']:
                        self.convert_field = True
                except IndexError and KeyError:
                    pass
        df = pd.DataFrame(to_tlg_df, columns=df_columns)
        df.attrs['task_name'] = task_name
        df.attrs['columns'] = df_columns
        return df

    def convert_yield_field(self):
        """Converts the yield output from lb/ac to kg/ha"""
        column = 'dry yield (lb/ac)'
        for j, task in enumerate(self.tasks):
            if isinstance(task, pd.DataFrame):
                try:
                    self.tasks[j][column] = task[column] * 1.12085
                    self.tasks[j].rename({'dry yield (lb/ac)': 'dry yield (kg/ha)'}, axis='columns', inplace=True)
                except KeyError:
                    pass  # This may occur if the dataframe is empty
