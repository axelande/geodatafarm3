"""Tests for the Open-Meteo historical weather client.

These are pure-function tests: ``requests`` is mocked, so nothing touches the
network or the shared database fixture, and they are independent of the
ordered/stateful part of the suite.
"""
from unittest import mock

import pytest

from geodatafarm.support_scripts.open_meteo_client import (
    ARCHIVE_URL,
    OpenMeteoClient,
    OpenMeteoError,
)


def _fake_response(status_code=200, json_data=None, text=''):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def test_daily_precipitation_returns_date_value_pairs():
    payload = {'daily': {'time': ['2024-05-01', '2024-05-02'],
                         'precipitation_sum': [0.0, 5.4]}}
    with mock.patch('requests.get', return_value=_fake_response(json_data=payload)) as m:
        client = OpenMeteoClient()
        result = client.daily_precipitation(55.4, 13.5, '2024-05-01', '2024-05-02')

    assert result == [('2024-05-01', 0.0), ('2024-05-02', 5.4)]
    called_url = m.call_args.args[0]
    called_params = m.call_args.kwargs['params']
    assert called_url == ARCHIVE_URL
    assert called_params == {
        'latitude': 55.4, 'longitude': 13.5,
        'start_date': '2024-05-01', 'end_date': '2024-05-02',
        'daily': 'precipitation_sum', 'timezone': 'auto',
    }


def test_daily_precipitation_keeps_none_for_missing_days():
    payload = {'daily': {'time': ['2024-05-01'], 'precipitation_sum': [None]}}
    with mock.patch('requests.get', return_value=_fake_response(json_data=payload)):
        client = OpenMeteoClient()
        result = client.daily_precipitation(55.4, 13.5, '2024-05-01', '2024-05-01')

    assert result == [('2024-05-01', None)]


def test_daily_precipitation_raises_on_http_error():
    with mock.patch('requests.get',
                    return_value=_fake_response(status_code=500, text='boom')):
        client = OpenMeteoClient()
        with pytest.raises(OpenMeteoError, match='500'):
            client.daily_precipitation(55.4, 13.5, '2024-05-01', '2024-05-02')


def test_daily_precipitation_raises_on_network_error():
    import requests
    with mock.patch('requests.get', side_effect=requests.RequestException('down')):
        client = OpenMeteoClient()
        with pytest.raises(OpenMeteoError, match='Could not reach Open-Meteo'):
            client.daily_precipitation(55.4, 13.5, '2024-05-01', '2024-05-02')


def test_daily_precipitation_raises_on_mismatched_lengths():
    payload = {'daily': {'time': ['2024-05-01', '2024-05-02'],
                         'precipitation_sum': [0.0]}}
    with mock.patch('requests.get', return_value=_fake_response(json_data=payload)):
        client = OpenMeteoClient()
        with pytest.raises(OpenMeteoError, match='mismatched'):
            client.daily_precipitation(55.4, 13.5, '2024-05-01', '2024-05-02')


def test_daily_weather_returns_precipitation_et0_temperature_radiation_and_daylight():
    payload = {'daily': {
        'time': ['2024-05-01', '2024-05-02'],
        'precipitation_sum': [0.0, 5.4],
        'et0_fao_evapotranspiration': [3.1, 2.8],
        'temperature_2m_mean': [12.5, 13.0],
        'shortwave_radiation_sum': [18.2, 15.6],
        'daylight_duration': [50400.0, 50760.0],  # seconds -> 14h, 14.1h
    }}
    with mock.patch('requests.get', return_value=_fake_response(json_data=payload)) as m:
        client = OpenMeteoClient()
        result = client.daily_weather(55.4, 13.5, '2024-05-01', '2024-05-02')

    assert result == [
        {'date': '2024-05-01', 'precipitation_mm': 0.0, 'et0_mm': 3.1, 'temp_mean_c': 12.5,
         'solar_radiation_mj_m2': 18.2, 'daylight_hours': 14.0},
        {'date': '2024-05-02', 'precipitation_mm': 5.4, 'et0_mm': 2.8, 'temp_mean_c': 13.0,
         'solar_radiation_mj_m2': 15.6, 'daylight_hours': pytest.approx(14.1)},
    ]
    assert m.call_args.kwargs['params']['daily'] == (
        'precipitation_sum,et0_fao_evapotranspiration,temperature_2m_mean,'
        'shortwave_radiation_sum,daylight_duration')


def test_daily_weather_keeps_none_for_missing_radiation_or_daylight():
    payload = {'daily': {
        'time': ['2024-05-01'],
        'precipitation_sum': [0.0],
        'et0_fao_evapotranspiration': [3.1],
        'temperature_2m_mean': [12.5],
        'shortwave_radiation_sum': [None],
        'daylight_duration': [None],
    }}
    with mock.patch('requests.get', return_value=_fake_response(json_data=payload)):
        client = OpenMeteoClient()
        result = client.daily_weather(55.4, 13.5, '2024-05-01', '2024-05-01')

    assert result[0]['solar_radiation_mj_m2'] is None
    assert result[0]['daylight_hours'] is None


def test_daily_weather_raises_on_mismatched_lengths():
    payload = {'daily': {
        'time': ['2024-05-01', '2024-05-02'],
        'precipitation_sum': [0.0, 5.4],
        'et0_fao_evapotranspiration': [3.1],
        'temperature_2m_mean': [12.5, 13.0],
    }}
    with mock.patch('requests.get', return_value=_fake_response(json_data=payload)):
        client = OpenMeteoClient()
        with pytest.raises(OpenMeteoError, match='mismatched'):
            client.daily_weather(55.4, 13.5, '2024-05-01', '2024-05-02')
