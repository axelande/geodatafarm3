"""Client for the Lemon Squeezy License API.

Gates GeoDataFarm's premium fertilizer-timing analysis behind a paid
license without GeoDataFarm running any billing/licensing server itself:
Lemon Squeezy issues and verifies the keys, this just calls their hosted
API. See https://docs.lemonsqueezy.com/api/license-api for the endpoint
docs.
"""
import requests

__author__ = 'Axel Horteborn'

BASE_URL = "https://api.lemonsqueezy.com/v1/licenses"
_HEADERS = {"Accept": "application/json"}


class LicenseError(Exception):
    """Raised when the license server cannot be reached or returns a
    response that isn't parseable JSON. A *rejected* key (bad/expired/out of
    activations) is not an error - see the ``activated``/``valid``/``error``
    keys in the returned dict instead."""


class LicenseClient:
    """Thin client for Lemon Squeezy's activate/validate/deactivate endpoints."""

    def activate(self, license_key, instance_name):
        """Activates ``license_key`` for this installation.

        Parameters
        ----------
        license_key: str
        instance_name: str
            Something identifying this installation (e.g. the machine
            hostname), so the same key can be activated on a small, tracked
            number of machines and deactivated individually.

        Returns
        -------
        dict
            Parsed response, e.g. ``{'activated': True, 'instance':
            {'id': '...', 'name': '...'}, ...}`` on success, or
            ``{'activated': False, 'error': '...'}`` if the key is invalid
            or has no activations left.
        """
        return self._post('activate', {'license_key': license_key,
                                       'instance_name': instance_name})

    def validate(self, license_key, instance_id):
        """Checks whether ``license_key``/``instance_id`` is still active
        (e.g. hasn't been refunded, or deactivated from another machine).

        Returns
        -------
        dict
            E.g. ``{'valid': True, ...}`` or ``{'valid': False, 'error': '...'}``.
        """
        return self._post('validate', {'license_key': license_key,
                                       'instance_id': instance_id})

    def deactivate(self, license_key, instance_id):
        """Frees up the activation slot used by ``instance_id``.

        Returns
        -------
        dict
            E.g. ``{'deactivated': True, ...}``.
        """
        return self._post('deactivate', {'license_key': license_key,
                                         'instance_id': instance_id})

    def _post(self, action, data):
        try:
            resp = requests.post('{}/{}'.format(BASE_URL, action), data=data,
                                 headers=_HEADERS, timeout=30)
        except requests.RequestException as e:
            raise LicenseError(
                'Could not reach the license server: {}'.format(e))
        try:
            return resp.json()
        except ValueError:
            raise LicenseError(
                'The license server returned an unexpected response ({}).'
                .format(resp.status_code))
