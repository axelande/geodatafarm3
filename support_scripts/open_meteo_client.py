"""Client for Open-Meteo's free historical weather archive.

Unlike :mod:`support_scripts.cdse_client`, this needs no account, no API key
and no per-user credentials: Open-Meteo's archive API is free for
non-commercial use, keyless, and rate-limited generously (10 000 calls/day).
GeoDataFarm's weather import is a free feature with no subscription attached
to it, so it fits Open-Meteo's own definition of non-commercial use. See
https://open-meteo.com/en/docs/historical-weather-api for the endpoint docs.
"""
import requests

__author__ = 'Axel Horteborn'

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class OpenMeteoError(Exception):
    """Raised when the Open-Meteo API cannot fulfil a request."""


class OpenMeteoClient:
    """Keyless client for Open-Meteo's historical weather archive."""

    def _fetch_daily(self, latitude, longitude, date_from, date_to, daily_vars):
        """GETs the archive endpoint for ``daily_vars`` and returns the raw
        ``daily`` object from the response (a dict of equal-length lists).

        Raises
        ------
        OpenMeteoError
            If the service cannot be reached or returns a non-200 response.
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": date_from,
            "end_date": date_to,
            "daily": daily_vars,
            "timezone": "auto",
        }
        try:
            resp = requests.get(ARCHIVE_URL, params=params, timeout=30)
        except requests.RequestException as e:
            raise OpenMeteoError(
                "Could not reach Open-Meteo: {}".format(e))
        if resp.status_code != 200:
            raise OpenMeteoError("Open-Meteo request failed ({}): {}".format(
                resp.status_code, resp.text[:200]))
        return resp.json().get("daily", {})

    def daily_precipitation(self, latitude, longitude, date_from, date_to):
        """Fetches daily precipitation totals for a point and date range.

        Parameters
        ----------
        latitude: float
        longitude: float
        date_from: str
            Start date, ``YYYY-MM-DD``.
        date_to: str
            End date, ``YYYY-MM-DD`` (inclusive).

        Returns
        -------
        list[tuple[str, float | None]]
            ``(date, precipitation_mm)`` pairs, one per day, oldest first.
            ``precipitation_mm`` is ``None`` for days Open-Meteo has no data
            for yet (e.g. the last few days of the archive).

        Raises
        ------
        OpenMeteoError
            If the service cannot be reached or returns an error/unexpected
            payload.
        """
        daily = self._fetch_daily(latitude, longitude, date_from, date_to,
                                  "precipitation_sum")
        dates = daily.get("time", [])
        values = daily.get("precipitation_sum", [])
        if len(dates) != len(values):
            raise OpenMeteoError(
                "Open-Meteo returned mismatched dates and precipitation "
                "values.")
        return list(zip(dates, values))

    def daily_weather(self, latitude, longitude, date_from, date_to):
        """Fetches daily precipitation, reference evapotranspiration (ET0),
        mean temperature, solar radiation and daylight duration for a point
        and date range - the inputs the crop simulation needs (see
        support_scripts/fertilizer_timing_model.py and
        support_scripts/season_water_model.py). Solar radiation and
        daylight are used for photosynthesis/growth-limiting factors, not
        just the water/nitrogen balance the other three alone can drive.

        Parameters
        ----------
        latitude: float
        longitude: float
        date_from: str
            Start date, ``YYYY-MM-DD``.
        date_to: str
            End date, ``YYYY-MM-DD`` (inclusive).

        Returns
        -------
        list[dict]
            One dict per day, oldest first, with keys ``date``,
            ``precipitation_mm``, ``et0_mm``, ``temp_mean_c``,
            ``solar_radiation_mj_m2`` and ``daylight_hours``. Any value may
            be ``None`` for days Open-Meteo has no data for yet.

        Raises
        ------
        OpenMeteoError
            If the service cannot be reached, or returns an error/unexpected
            payload.
        """
        daily = self._fetch_daily(
            latitude, longitude, date_from, date_to,
            "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_mean,"
            "shortwave_radiation_sum,daylight_duration")
        dates = daily.get("time", [])
        n = len(dates)
        precip = daily.get("precipitation_sum", [None] * n)
        et0 = daily.get("et0_fao_evapotranspiration", [None] * n)
        temp = daily.get("temperature_2m_mean", [None] * n)
        radiation = daily.get("shortwave_radiation_sum", [None] * n)
        daylight_seconds = daily.get("daylight_duration", [None] * n)
        if len(precip) != n or len(et0) != n or len(temp) != n \
                or len(radiation) != n or len(daylight_seconds) != n:
            raise OpenMeteoError(
                "Open-Meteo returned mismatched daily weather values.")
        return [
            {"date": dates[i], "precipitation_mm": precip[i],
             "et0_mm": et0[i], "temp_mean_c": temp[i],
             "solar_radiation_mj_m2": radiation[i],
             "daylight_hours": (daylight_seconds[i] / 3600.0
                                if daylight_seconds[i] is not None else None)}
            for i in range(n)
        ]
