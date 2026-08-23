"""Tests for the Lemon Squeezy license client.

``requests`` is mocked, so nothing touches the network or the shared
database fixture - independent of the ordered/stateful part of the suite.
"""
from unittest import mock

import pytest

from geodatafarm.support_scripts.license_client import (
    BASE_URL, LicenseClient, LicenseError)


def _fake_response(json_data, status_code=200):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def test_activate_posts_key_and_instance_name():
    payload = {'activated': True, 'instance': {'id': 'abc123', 'name': 'my-pc'}}
    with mock.patch('requests.post', return_value=_fake_response(payload)) as m:
        result = LicenseClient().activate('LICENSE-KEY', 'my-pc')

    assert result == payload
    assert m.call_args.args[0] == '{}/activate'.format(BASE_URL)
    assert m.call_args.kwargs['data'] == {
        'license_key': 'LICENSE-KEY', 'instance_name': 'my-pc'}


def test_activate_rejected_key_is_not_an_exception():
    payload = {'activated': False, 'error': 'This license key is not valid.'}
    with mock.patch('requests.post', return_value=_fake_response(payload)):
        result = LicenseClient().activate('BAD-KEY', 'my-pc')

    assert result['activated'] is False
    assert 'not valid' in result['error']


def test_validate_posts_key_and_instance_id():
    payload = {'valid': True}
    with mock.patch('requests.post', return_value=_fake_response(payload)) as m:
        result = LicenseClient().validate('LICENSE-KEY', 'abc123')

    assert result == payload
    assert m.call_args.args[0] == '{}/validate'.format(BASE_URL)
    assert m.call_args.kwargs['data'] == {
        'license_key': 'LICENSE-KEY', 'instance_id': 'abc123'}


def test_deactivate_posts_key_and_instance_id():
    payload = {'deactivated': True}
    with mock.patch('requests.post', return_value=_fake_response(payload)) as m:
        result = LicenseClient().deactivate('LICENSE-KEY', 'abc123')

    assert result == payload
    assert m.call_args.args[0] == '{}/deactivate'.format(BASE_URL)


def test_network_error_raises_license_error():
    import requests
    with mock.patch('requests.post', side_effect=requests.RequestException('down')):
        with pytest.raises(LicenseError, match='Could not reach the license server'):
            LicenseClient().activate('KEY', 'my-pc')


def test_non_json_response_raises_license_error():
    resp = mock.Mock()
    resp.status_code = 502
    resp.json.side_effect = ValueError('not json')
    with mock.patch('requests.post', return_value=resp):
        with pytest.raises(LicenseError, match='unexpected response'):
            LicenseClient().validate('KEY', 'abc123')
