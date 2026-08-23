import math
from datetime import date

from psycopg2 import sql as pgsql
from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtWidgets import QMessageBox, QPushButton
from qgis.core import QgsTask

from ..widgets.weather_dialog import WeatherDialog
from ..support_scripts.__init__ import check_text, TR
from ..support_scripts.notifier import report_warning, report_error, report_success
from ..support_scripts.open_meteo_client import OpenMeteoClient, OpenMeteoError

__author__ = 'Axel Horteborn'

# Fields within this distance of each other are treated as sharing the same
# weather when "Apply to all fields" is used, so they share one Open-Meteo
# call instead of one each - useful since Open-Meteo's own historical models
# are themselves gridded at a coarser resolution than this in most places,
# and it keeps a many-field farm well under the free rate limit.
_SHARED_WEATHER_RADIUS_KM = 5.0


def _default_from_date(today=None):
    """The 1st of March of the current growing season: this year's if
    ``today`` is already on/after March 1st, otherwise last year's (so the
    default always points at the most recent 1 March that isn't in the
    future)."""
    today = today or date.today()
    year = today.year if today.month >= 3 else today.year - 1
    return date(year, 3, 1)


class WeatherData:
    """Fetches free historical daily weather (rain, mean temperature, and
    reference evapotranspiration/ET0) for one field - or all fields at once
    - from Open-Meteo and stores it in the ``weather`` schema.

    This only imports and stores the data (a free feature); turning it into
    the crop simulation is a separate, licensed feature (see
    database_scripts/crop_simulation.py), which fetches its own live data
    rather than reading what's stored here.

    Opened from the "Weather" card on the "Add data" page (a
    ``picker_action`` entry in widgets/add_data_form.py's ``OPERATIONS`` -
    see GeoDataFarm.handle_add_data_action) rather than living in a docked
    tab, since the old nested "Import data" tab is removed at startup by
    GeoDataFarm_dockwidget._setup_sidebar_nav() in favour of the "Add data"
    page.

    The actual fetch (network call + DB writes) runs in a QgsTask, since
    both can be slow for "apply to all fields" on a large farm; only the
    field lookup and the already-exists confirmation dialogs run beforehand
    on the UI thread (QMessageBox/QGIS message bar calls aren't safe from a
    background thread, so the task functions only ever return plain data -
    see :meth:`_on_fetch_one_finished`/:meth:`_on_fetch_all_fields_finished`).
    """

    def __init__(self, parent):
        self.parent = parent
        self.dlg = WeatherDialog()
        self.db = parent.db
        self.tsk_mngr = parent.tsk_mngr
        translate = TR('WeatherData')
        self.tr = translate.tr
        self.client = OpenMeteoClient()
        self.connect_buttons = False

    def set_widget_connections(self):
        """Wires the buttons on the Weather dialog."""
        if self.connect_buttons:
            return
        self.dlg.PBWeatherUpdateFields.clicked.connect(self.update_field_list)
        self.dlg.PBFetchWeather.clicked.connect(self.fetch_weather)
        self.connect_buttons = True

    def open_dialog(self):
        """Shows the weather dialog, with the field list and the date range
        (1 March of the current growing season through today) refreshed."""
        self.update_field_list()
        today = date.today()
        self.dlg.DEWeatherTo.setDate(QDate(today.year, today.month, today.day))
        from_date = _default_from_date(today)
        self.dlg.DEWeatherFrom.setDate(
            QDate(from_date.year, from_date.month, from_date.day))
        self.dlg.show()
        self.dlg.exec()

    def update_field_list(self):
        """(re)loads the field names into the Weather tab's field combo."""
        self.parent.populate.reload_fields(self.dlg.CBWeatherField)

    def _field_location(self, field_name):
        """Returns ``(longitude, latitude, polygon_wkt)`` for a field, or
        None (no warning raised here; callers decide how to report it)."""
        rows = self.db.execute_and_return(
            "SELECT st_x(st_centroid(polygon)), st_y(st_centroid(polygon)),"
            " st_astext(polygon) FROM fields WHERE field_name = %s",
            params=(field_name,))
        if not rows:
            return None
        longitude, latitude, polygon_wkt = rows[0]
        return float(longitude), float(latitude), polygon_wkt

    def fetch_weather(self):
        """Downloads daily weather for the date range and stores it in the
        ``weather`` schema, for either the selected field or every field
        (see :attr:`~GeoDataFarm_dockwidget.CBWeatherAllFields`)."""
        date_from = self.dlg.DEWeatherFrom.date().toString("yyyy-MM-dd")
        date_to = self.dlg.DEWeatherTo.date().toString("yyyy-MM-dd")
        if date_from >= date_to:
            report_warning(self.tr(
                'The "to date" must be later than the "from date".'))
            return
        if self.dlg.CBWeatherAllFields.isChecked():
            self._start_fetch_all_fields(date_from, date_to)
            return
        field_name = self.dlg.CBWeatherField.currentText()
        if not field_name or field_name == self.tr('--- Select field ---'):
            report_warning(self.tr('Please select a field first.'))
            return
        self._start_fetch_one(field_name, date_from, date_to)

    # ------------------------------------------------------------------
    # Single field
    # ------------------------------------------------------------------

    def _start_fetch_one(self, field_name, date_from, date_to):
        """Resolves the field and asks before overwriting existing data (both
        UI-thread only), then hands the actual fetch to a background QgsTask."""
        location = self._field_location(field_name)
        if location is None:
            report_warning(self.tr('Could not find the location of that field.'))
            return
        longitude, latitude, polygon_wkt = location
        table = check_text('{}_weather_{}'.format(field_name, date_from[:4]))
        if (self.db.check_table_exists(table, 'weather', False)
                and not self._confirm_overwrite_one(field_name)):
            return
        task = QgsTask.fromFunction(
            self.tr('Fetching weather for {}').format(field_name),
            self._fetch_one_task, table, latitude, longitude, polygon_wkt,
            date_from, date_to, on_finished=self._on_fetch_one_finished)
        self.tsk_mngr.addTask(task)

    def _fetch_one_task(self, task, table, latitude, longitude, polygon_wkt,
                        date_from, date_to):
        """Runs in the background: only returns plain data, never touches
        Qt widgets/the message bar (see the class docstring)."""
        task.setProgress(10)
        try:
            daily = self.client.daily_weather(latitude, longitude, date_from, date_to)
        except OpenMeteoError as e:
            return {'ok': False, 'error': str(e)}
        if not daily:
            return {'ok': False, 'error': 'no_data'}
        task.setProgress(60)
        self._store(table, daily, polygon_wkt)
        task.setProgress(100)
        return {'ok': True, 'table': table, 'n': len(daily)}

    def _on_fetch_one_finished(self, exception, result):
        """Runs back on the UI thread once :meth:`_fetch_one_task` completes."""
        if exception is not None:
            report_error(str(exception))
            return
        if not result.get('ok'):
            if result.get('error') == 'no_data':
                report_warning(self.tr(
                    'Open-Meteo returned no data for that date range.'))
            else:
                report_error(result.get('error') or self.tr('The fetch failed.'))
            return
        if getattr(self.parent, 'populate', None) is not None:
            self.parent.populate.update_table_list()
        report_success(self.tr(
            'Fetched {n} day(s) of weather data into weather.{t}').format(
                n=result['n'], t=result['table']))

    # ------------------------------------------------------------------
    # All fields
    # ------------------------------------------------------------------

    def _start_fetch_all_fields(self, date_from, date_to):
        """Gathers fields/clusters and asks before overwriting existing data
        (both UI-thread only), then hands the actual fetching to a
        background QgsTask."""
        rows = self.db.execute_and_return(
            "SELECT field_name, st_x(st_centroid(polygon)),"
            " st_y(st_centroid(polygon)), st_astext(polygon) FROM fields"
            " ORDER BY field_name")
        if not rows:
            report_warning(self.tr('No fields found.'))
            return
        year = date_from[:4]
        fields = [(name, float(lon), float(lat)) for name, lon, lat, _wkt in rows]
        polygons = {name: wkt for name, _lon, _lat, wkt in rows}
        tables = {name: check_text('{}_weather_{}'.format(name, year))
                 for name, _lon, _lat in fields}
        existing = [name for name, _lon, _lat in fields
                   if self.db.check_table_exists(tables[name], 'weather', False)]
        mode = 'overwrite'
        if existing:
            mode = self._confirm_overwrite_many(existing)
            if mode == 'cancel':
                return
        clusters = self._cluster_by_location(fields)
        task = QgsTask.fromFunction(
            self.tr('Fetching weather for {} field(s)').format(len(fields)),
            self._fetch_all_fields_task, clusters, tables, polygons, existing,
            mode, date_from, date_to, on_finished=self._on_fetch_all_fields_finished)
        self.tsk_mngr.addTask(task)

    def _fetch_all_fields_task(self, task, clusters, tables, polygons, existing,
                               mode, date_from, date_to):
        """Runs in the background: only returns plain data, never touches Qt
        widgets/the message bar (see the class docstring)."""
        fetched_fields = 0
        skipped_fields = 0
        calls_made = 0
        total_fields = sum(len(c) for c in clusters) or 1
        processed = 0
        for cluster in clusters:
            if task.isCanceled():
                return {'ok': False, 'error': 'canceled'}
            targets = [f for f in cluster if not (mode == 'skip' and f[0] in existing)]
            skipped_fields += len(cluster) - len(targets)
            processed += len(cluster) - len(targets)
            if not targets:
                task.setProgress(processed / total_fields * 100)
                continue
            _rep_name, rep_lon, rep_lat = cluster[0]
            try:
                daily = self.client.daily_weather(rep_lat, rep_lon, date_from, date_to)
            except OpenMeteoError as e:
                return {'ok': False, 'error': str(e)}
            if not daily:
                return {'ok': False, 'error': 'no_data'}
            calls_made += 1
            for name, _lon, _lat in targets:
                self._store(tables[name], daily, polygons[name])
                fetched_fields += 1
                processed += 1
                task.setProgress(processed / total_fields * 100)
        return {'ok': True, 'fetched': fetched_fields, 'skipped': skipped_fields,
               'calls': calls_made}

    def _on_fetch_all_fields_finished(self, exception, result):
        """Runs back on the UI thread once :meth:`_fetch_all_fields_task`
        completes."""
        if exception is not None:
            report_error(str(exception))
            return
        if not result.get('ok'):
            if result.get('error') == 'no_data':
                report_warning(self.tr(
                    'Open-Meteo returned no data for that date range.'))
            elif result.get('error') != 'canceled':
                report_error(result.get('error') or self.tr('The fetch failed.'))
            return
        if getattr(self.parent, 'populate', None) is not None:
            self.parent.populate.update_table_list()
        report_success(self.tr(
            'Fetched weather for {n} field(s) using {c} Open-Meteo call(s) '
            '(nearby fields share a call); skipped {s} field(s) that already '
            'had data.').format(n=result['fetched'], c=result['calls'],
                                s=result['skipped']))

    def _confirm_overwrite_many(self, existing_names):
        """Asks once how to handle every field that already has weather data
        for this period, instead of prompting once per field.

        Returns
        -------
        str
            ``'overwrite'``, ``'skip'``, or ``'cancel'``.
        """
        if self.parent.test_mode:
            return 'skip'
        preview = ', '.join(existing_names[:8])
        if len(existing_names) > 8:
            preview += ', ...'
        msg_box = QMessageBox()
        msg_box.setText(self.tr(
            '{n} field(s) already have weather data for this period: {names}.'
        ).format(n=len(existing_names), names=preview))
        msg_box.addButton(QPushButton(self.tr('Overwrite all')),
                          QMessageBox.ButtonRole.YesRole)
        msg_box.addButton(QPushButton(self.tr('Skip existing')),
                          QMessageBox.ButtonRole.NoRole)
        msg_box.addButton(QPushButton(self.tr('Cancel')),
                          QMessageBox.ButtonRole.RejectRole)
        ret = msg_box.exec()
        return ('overwrite', 'skip', 'cancel')[ret]

    def _confirm_overwrite_one(self, field_name):
        """Asks before replacing weather data already fetched for this
        field/year. Doesn't reuse ``db.check_table_exists(ask_replace=True)``
        since that assumes every schema has a ``<schema>.manual`` tracking
        table to clean up too - the ``weather`` schema doesn't have one, so
        that path would fail with a "relation does not exist" error."""
        if self.parent.test_mode:
            return False
        msg_box = QMessageBox()
        msg_box.setText(self.tr(
            '{field} already has weather data fetched for this period.'
            ' Overwrite it?').format(field=field_name))
        msg_box.addButton(QPushButton(self.tr('Yes')), QMessageBox.ButtonRole.YesRole)
        msg_box.addButton(QPushButton(self.tr('No')), QMessageBox.ButtonRole.NoRole)
        ret = msg_box.exec()
        return ret == 0

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2):
        """Great-circle distance in km between two lat/lon points."""
        r = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2
             + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2)
        return 2 * r * math.asin(math.sqrt(a))

    @classmethod
    def _cluster_by_location(cls, fields):
        """Greedily groups ``(name, lon, lat)`` tuples so any two fields in
        the same group are within :data:`_SHARED_WEATHER_RADIUS_KM` of that
        group's first (representative) field. Not optimal clustering, just
        enough to cut duplicate Open-Meteo calls for fields that sit close
        together.

        Returns
        -------
        list[list[tuple]]
        """
        clusters = []
        for field in fields:
            _name, lon, lat = field
            target = None
            for cluster in clusters:
                _rep_name, rep_lon, rep_lat = cluster[0]
                if cls._haversine_km(lat, lon, rep_lat, rep_lon) <= _SHARED_WEATHER_RADIUS_KM:
                    target = cluster
                    break
            if target is not None:
                target.append(field)
            else:
                clusters.append([field])
        return clusters

    def _store(self, table, daily, polygon_wkt):
        """(Re)creates ``weather.{table}`` and inserts one row per day of
        ``daily`` (the ``list[dict]`` shape returned by
        ``OpenMeteoClient.daily_weather``).

        The field polygon is stored on every row (denormalised, matching how
        other schemas such as ``plant``/``spray`` already store the field
        reference per row) so the existing spatial ``st_extent`` handling in
        ``database_scripts/mean_analyse.py`` works unchanged if this table is
        ever selected there.
        """
        tbl_id = pgsql.Identifier(table)
        self.db.execute_sql(
            pgsql.SQL("DROP TABLE IF EXISTS weather.{tbl}").format(tbl=tbl_id))
        self.db.execute_sql(
            pgsql.SQL(
                "CREATE TABLE weather.{tbl} (row_id serial PRIMARY KEY,"
                " date_ date, precipitation_mm double precision,"
                " temp_mean_c double precision, et0_mm double precision,"
                " polygon geometry, source text)"
            ).format(tbl=tbl_id))
        insert = pgsql.SQL(
            "INSERT INTO weather.{tbl}"
            " (date_, precipitation_mm, temp_mean_c, et0_mm, polygon, source)"
            " VALUES (%s, %s, %s, %s, st_geomfromtext(%s, 4326), %s)"
        ).format(tbl=tbl_id)
        for day in daily:
            self.db.execute_sql(insert, params=(
                day['date'], day['precipitation_mm'], day['temp_mean_c'],
                day['et0_mm'], polygon_wkt, 'open-meteo'))
