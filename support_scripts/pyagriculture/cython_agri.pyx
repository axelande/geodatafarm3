import cython
import numpy as np
from datetime import timedelta, datetime

def empty_func3():
    pass


@cython.binding(True)
cpdef list read_static_binary_data(data_row: list, read_point: int, binary_data: object, tlg_dict: dict, dt: np.dtype,
                                    start_date: datetime):
    """Function to obtain the position and time data """
    cdef int nr_d = 3
    cdef float ten_minus_seven = pow(10, -7)
    cdef list np_data = np.frombuffer(binary_data, dt, count=1, offset=read_point)
    cdef int millis_from_midnight = int(np_data[0][0])
    cdef int days = int(np_data[0][1])
    actual_time = start_date + timedelta(days=days, milliseconds=millis_from_midnight)
    data_row[0] = actual_time.strftime('%Y-%m-%dT%H:%M:%S')
    cdef float lat = np_data[0][2]
    cdef float lon = np_data[0][3]
    data_row[1] = lat * ten_minus_seven
    data_row[2] = lon * ten_minus_seven
    cdef str key
    cdef float value
    cdef int millis_from_midnight2
    for key in tlg_dict['PTN'][''].keys():
        if key in ['C', 'D', 'E', 'F', 'G']:
            value = np_data[0][nr_d + 1]
            data_row[nr_d] = value
            nr_d += 1
    if 'H' and 'I' in tlg_dict['PTN'][''].keys():
        millis_from_midnight2 = int(np_data[0][nr_d + 1])
        days = int(np_data[0][nr_d + 2])
        actual_time = start_date + timedelta(days=days, milliseconds=millis_from_midnight)
        data_row[nr_d] = actual_time.strftime('%Y-%m-%dT%H:%M:%S')
        nr_d += 2
    cdef int nr_dlvs = np_data[0][nr_d + 1]
    return [data_row, nr_dlvs, nr_d - 1]

def empty_func2():
    pass

#@cython.binding(True)
cpdef list cython_read_dlvs(binary_data: object, read_point: int, nr_dlvs: int, nr_static: int, dpd_ids: dict,
                     tlg_dict: dict, unit_row: list, data_row: list, dlvs: list, dlv_columns:dict):
    cdef int nr_d
    cdef int dlv
    cdef int idx
    for nr, dlv in np.frombuffer(binary_data, [('DLVn', np.dtype('uint8')),
                                               ('PDV', np.dtype('int32'))],
                                 count=nr_dlvs, offset=read_point):
        read_point += 5
        dpd_key = dlvs[nr]['A']
        idx = list(dlv_columns.keys()).index(dpd_key)
        if dpd_key in dpd_ids.keys():
            dpd = dpd_ids[dpd_key]
            dvp_key = dpd.get('F')
        else:
            continue
        if dvp_key is None or dvp_key not in tlg_dict['DVP'].keys():
            continue
        dvp = tlg_dict['DVP'][dvp_key]
        decimals = float(10**int(dvp['D']))
        dlv = int((dlv + float(dvp['B'])) * float(dvp['C']) * decimals + 0.5) / decimals
        if unit_row[idx] is None:
            if 'E' in dvp.keys():
                unit_row[idx] = dvp['E']
        try:
            data_row[idx + nr_static] = dlv
        except:
            pass
    return [read_point, data_row, unit_row]

def empty_func():
    pass