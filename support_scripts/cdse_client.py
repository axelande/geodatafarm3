"""Lightweight client for the Copernicus Data Space Ecosystem (CDSE).

This talks directly to the CDSE Sentinel Hub services with ``requests`` (the
same dependency already used by :mod:`rain_dancer`) so that the plugin does not
need the heavier ``sentinelhub-py`` package, which is awkward to ship inside
the QGIS Python environment.

Three things are needed for the satellite workflow:

* an OAuth2 access token (client-credentials grant, per-user credentials),
* a catalog search returning the available acquisition dates and their cloud
  cover for a field, and
* a Process API call that returns a single Sentinel-2 band (B04 / B08) clipped
  to the field geometry as a GeoTIFF.

All endpoints live under the CDSE Sentinel Hub deployment::

    token   : https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token
    catalog : https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search
    process : https://sh.dataspace.copernicus.eu/api/v1/process
"""
import requests

__author__ = 'Axel Horteborn'

TOKEN_URL = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
             "protocol/openid-connect/token")
CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
COLLECTION = "sentinel-2-l2a"


class CDSEError(Exception):
    """Raised when the CDSE API cannot fulfil a request."""


class CDSEClient:
    """Per-user CDSE Sentinel Hub client.

    Parameters
    ----------
    client_id: str
        OAuth client id created in the CDSE dashboard
        (https://shapps.dataspace.copernicus.eu/dashboard/).
    client_secret: str
        The matching OAuth client secret.
    """

    def __init__(self, client_id='', client_secret=''):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None

    def get_token(self):
        """Fetches (and caches) an OAuth2 access token.

        Returns
        -------
        str
            The bearer access token.

        Raises
        ------
        CDSEError
            If the credentials are rejected or the service is unreachable.
        """
        if self._token is not None:
            return self._token
        try:
            resp = requests.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials",
                      "client_id": self.client_id,
                      "client_secret": self.client_secret},
                timeout=30)
        except requests.RequestException as e:
            raise CDSEError("Could not reach the Copernicus login service: "
                            "{}".format(e))
        if resp.status_code != 200:
            raise CDSEError("Authentication failed, please check your "
                            "Copernicus client id and secret.")
        self._token = resp.json().get("access_token")
        if not self._token:
            raise CDSEError("Copernicus did not return an access token.")
        return self._token

    def _auth_header(self):
        return {"Authorization": "Bearer {}".format(self.get_token())}

    def search_images(self, bbox, date_from, date_to, max_cloud=100):
        """Lists available Sentinel-2 scenes for a field and date range.

        Parameters
        ----------
        bbox: list[float]
            ``[min_lon, min_lat, max_lon, max_lat]`` in EPSG:4326.
        date_from: str
            Start date, ``YYYY-MM-DD``.
        date_to: str
            End date, ``YYYY-MM-DD`` (inclusive).
        max_cloud: float
            Only return scenes with at most this cloud cover (percent).

        Returns
        -------
        list[dict]
            One entry per acquisition date, sorted oldest first, each with
            ``{'date': 'YYYY-MM-DD', 'cloud': float}``. Dates are de-duplicated
            keeping the lowest cloud cover seen for that day.
        """
        body = {
            "collections": [COLLECTION],
            "bbox": bbox,
            "datetime": "{}T00:00:00Z/{}T23:59:59Z".format(date_from, date_to),
            "limit": 100,
            "fields": {"include": ["properties.datetime",
                                   "properties.eo:cloud_cover"],
                       "exclude": []},
        }
        try:
            resp = requests.post(CATALOG_URL, json=body,
                                 headers=self._auth_header(), timeout=60)
        except requests.RequestException as e:
            raise CDSEError("Could not reach the Copernicus catalog: "
                            "{}".format(e))
        if resp.status_code != 200:
            raise CDSEError("Copernicus catalog search failed ({}): {}".format(
                resp.status_code, resp.text[:200]))
        features = resp.json().get("features", [])
        by_date = {}
        for feat in features:
            props = feat.get("properties", {})
            stamp = props.get("datetime", "")
            if not stamp:
                continue
            day = stamp[:10]
            cloud = props.get("eo:cloud_cover")
            cloud = float(cloud) if cloud is not None else 100.0
            if cloud > max_cloud:
                continue
            if day not in by_date or cloud < by_date[day]:
                by_date[day] = cloud
        return [{"date": day, "cloud": by_date[day]}
                for day in sorted(by_date)]

    def get_band(self, geometry, date, band, width, height):
        """Downloads a single Sentinel-2 band clipped to the field geometry.

        Parameters
        ----------
        geometry: dict
            GeoJSON geometry (EPSG:4326) of the field; the result is masked to
            it, so pixels outside the field come back as 0.
        date: str
            Acquisition date, ``YYYY-MM-DD``.
        band: str
            Band name, e.g. ``'B04'`` or ``'B08'``.
        width: int
            Output width in pixels.
        height: int
            Output height in pixels.

        Returns
        -------
        bytes
            The GeoTIFF content of the requested band (Float32 reflectance).
        """
        evalscript = (
            "//VERSION=3\n"
            "function setup() {\n"
            "  return {\n"
            "    input: [{bands: [\"" + band + "\", \"dataMask\"]}],\n"
            "    output: {bands: 1, sampleType: \"FLOAT32\"}\n"
            "  };\n"
            "}\n"
            "function evaluatePixel(s) {\n"
            "  return [s." + band + " * s.dataMask];\n"
            "}\n"
        )
        body = {
            "input": {
                "bounds": {
                    "geometry": geometry,
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [{
                    "type": COLLECTION,
                    "dataFilter": {
                        "timeRange": {
                            "from": "{}T00:00:00Z".format(date),
                            "to": "{}T23:59:59Z".format(date)},
                    },
                }],
            },
            "output": {
                "width": int(width),
                "height": int(height),
                "responses": [{
                    "identifier": "default",
                    "format": {"type": "image/tiff"}}],
            },
            "evalscript": evalscript,
        }
        headers = self._auth_header()
        headers["Accept"] = "image/tiff"
        try:
            resp = requests.post(PROCESS_URL, json=body, headers=headers,
                                 timeout=120)
        except requests.RequestException as e:
            raise CDSEError("Could not download band {} from Copernicus: "
                            "{}".format(band, e))
        if resp.status_code != 200:
            raise CDSEError("Copernicus image request failed ({}): {}".format(
                resp.status_code, resp.text[:200]))
        return resp.content

    def get_truecolor(self, geometry, date, width, height):
        """Downloads a true-color (RGB) preview of the field for a date.

        Parameters
        ----------
        geometry: dict
            GeoJSON field geometry (EPSG:4326); the result is masked to it
            (transparent outside the field).
        date: str
            Acquisition date, ``YYYY-MM-DD``.
        width, height: int
            Requested size in pixels (capped to 1024 to keep it a thumbnail).

        Returns
        -------
        bytes
            PNG content (RGBA) of the true-color composite.
        """
        width = min(1024, max(1, int(width)))
        height = min(1024, max(1, int(height)))
        evalscript = (
            "//VERSION=3\n"
            "function setup() {\n"
            "  return {\n"
            "    input: [{bands: [\"B04\", \"B03\", \"B02\", \"dataMask\"]}],\n"
            "    output: {bands: 4, sampleType: \"UINT8\"}\n"
            "  };\n"
            "}\n"
            "function evaluatePixel(s) {\n"
            "  let g = 2.5;\n"
            "  return [255 * Math.min(1, s.B04 * g),\n"
            "          255 * Math.min(1, s.B03 * g),\n"
            "          255 * Math.min(1, s.B02 * g),\n"
            "          255 * s.dataMask];\n"
            "}\n"
        )
        body = {
            "input": {
                "bounds": {
                    "geometry": geometry,
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [{
                    "type": COLLECTION,
                    "dataFilter": {
                        "timeRange": {
                            "from": "{}T00:00:00Z".format(date),
                            "to": "{}T23:59:59Z".format(date)},
                    },
                }],
            },
            "output": {
                "width": width,
                "height": height,
                "responses": [{
                    "identifier": "default",
                    "format": {"type": "image/png"}}],
            },
            "evalscript": evalscript,
        }
        headers = self._auth_header()
        headers["Accept"] = "image/png"
        try:
            resp = requests.post(PROCESS_URL, json=body, headers=headers,
                                 timeout=120)
        except requests.RequestException as e:
            raise CDSEError("Could not download the preview image from "
                            "Copernicus: {}".format(e))
        if resp.status_code != 200:
            raise CDSEError("Copernicus preview request failed ({}): "
                            "{}".format(resp.status_code, resp.text[:200]))
        return resp.content
