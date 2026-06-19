from psycopg2 import sql as pgsql
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsTask
import traceback
from ..widgets.fix_rows import FixRowsDialog
from .notifier import report_success, report_error
from ..support_scripts.__init__ import TR


class RowFixer:
    def __init__(self, parent):
        """Runs Row Fixer

        References
        ----------
        self: fill_cb

        Connects
        --------
        self: initiate_update
        """
        self.FRD = FixRowsDialog()
        translate = TR('RowFixer')
        self.tr = translate.tr
        self.db = parent.db
        self.tsk_mngr = parent.tsk_mngr
        self.fill_cb()
        self.FRD.PBUpdateGeom.clicked.connect(self.initiate_update)
        self.FRD.CBMaxRows.setCurrentIndex(3)
        self.FRD.show()
        self.FRD.exec()

    def fill_cb(self):
        """Updates the ComboBox with names from the different schemas in the
        database

        References
        ----------
        db: get_tabels_in_db
            schema

        Connects
        --------
        self: set_possible_columns
        """
        lw_list = ['plant', 'ferti', 'spray', 'soil', 'other']
        self.FRD.CBDataSource.clear()
        names = []
        for schema in lw_list:
            table_names = self.db.get_tables_in_db(schema)
            for name in table_names:
                if name in ["temp_polygon", 'manual', 'harrowing_manual',
                               'plowing_manual']:
                    continue
                names.append(schema + '.' + str(name))
        self.FRD.CBDataSource.addItems(names)
        self.FRD.CBDataSource.activated.connect(
            lambda idx: self.set_possible_columns(self.FRD.CBDataSource.currentText())
        )

    def set_possible_columns(self, text):
        """Adds the columns that could be used.

        Parameters
        ----------
        text: str
            The schema.table

        References
        ----------
        db: get_all_columns
            table, schema, exclude
        """
        self.FRD.CBRow.clear()
        self.FRD.CBCourse.clear()
        columns = self.db.get_all_columns(table=text.split('.')[1],
                                       schema=text.split('.')[0],
                                       exclude="'cmax', 'cmin', 'ctid', 'xmax', 'xmin', 'tableoid', 'pos', 'date_', 'polygon', 'field_row_id'")
        self.FRD.CBRow.addItems(columns)
        self.FRD.CBCourse.addItems(columns)

    def initiate_update(self):
        """Initiate the update with QgsTask manager

        Connects
        --------
        self: update_geom
        """
        task = QgsTask.fromFunction('Updates the geometries...',
                                    self.update_geom, on_finished=self.finish)
        self.tsk_mngr.addTask(task)
        #a = self.update_geom('debug')
        #self.finish('debug', a)

    def finish(self, result, values):
        """CProduce a message telling if the operation went well or not

        Parameters
        ----------
        result: object
            The result object
        values: list
            list with [bool, str, str]
        """
        if values[0] is False:
            report_error(self.tr(
                                        'Following error occurred: {m}\n\n Traceback: {t}'.format(
                                            m=values[1],
                                            t=values[2])), detail=str(values[1]))
            return
        else:
            report_success(self.tr('The geometries have updated'))

    def update_geom(self, task):
        """Runs the sql query that updates the 'polygon' and adds 'new_row_id

        Parameters
        ----------
        task: QgsTask

        References
        ----------
        db: execute_sql
            sql
        """
        try:
            schema_table = self.FRD.CBDataSource.currentText()
            max_rows = self.FRD.CBMaxRows.currentText()
            row = self.FRD.CBRow.currentText()  # The column with row_number from planting machine
            course = self.FRD.CBCourse.currentText()  # The course in degrees
            parts = schema_table.split('.')
            s_t = pgsql.SQL("{schema}.{tbl}").format(
                schema=pgsql.Identifier(parts[0]),
                tbl=pgsql.Identifier(parts[1]))
            row_id = pgsql.Identifier(row)
            course_id = pgsql.Identifier(course)
            max_rows_lit = pgsql.Literal(int(max_rows))
            sql = pgsql.SQL("""ALTER TABLE {s_t}
                ADD COLUMN new_row_id int;
            WITH dat AS (SELECT field_row_id, pos, {course} AS course, {row} AS row_nbr
                FROM {s_t} LIMIT 1000),
            all_data AS (SELECT field_row_id, pos, course, {row} AS row_nbr,
                         lead(field_row_id) OVER(ORDER BY {row}, field_row_id ASC) AS row_id2,
                         lag(field_row_id) OVER(ORDER BY {row}, field_row_id ASC) AS row_id3
                         FROM {s_t}),
            dat2 AS (SELECT field_row_id, pos, course, row_nbr,
                     lead(field_row_id) OVER(ORDER BY row_nbr, field_row_id ASC) AS row_id2
                     FROM dat),
            course_limits AS (SELECT (degrees(atan2(sind((SELECT mode() WITHIN GROUP (ORDER BY course) -10 FROM all_data)), cosd((SELECT mode() WITHIN GROUP (ORDER BY course) -10 FROM all_data)))) + 360)::int % 360 AS min_dir_1,
                       (degrees(atan2(sind((SELECT mode() WITHIN GROUP (ORDER BY course) FROM all_data)+10), cosd((SELECT mode() WITHIN GROUP (ORDER BY course) FROM all_data)+10))) + 360)::int % 360 AS max_dir_1,
                       (degrees(atan2(sind((SELECT mode() WITHIN GROUP (ORDER BY course) +170 FROM all_data)), cosd((SELECT mode() WITHIN GROUP (ORDER BY course) +170 FROM all_data)))) + 360)::int % 360 AS min_dir_2,
                       (degrees(atan2(sind((SELECT mode() WITHIN GROUP (ORDER BY course) FROM all_data)+190), cosd((SELECT mode() WITHIN GROUP (ORDER BY course) FROM all_data)+190)))  + 360)::int % 360 AS max_dir_2),
            row_width AS (SELECT st_distance(ss.pos,
                                  (SELECT i2.pos FROM dat i2 WHERE i2.row_nbr=3 ORDER BY st_distance(i2.pos, ss.pos) LIMIT 1)) AS side_dist
                          FROM dat ss WHERE ss.row_nbr = 2),
            point_length AS (SELECT field_row_id, st_distance(pos,
                                  (SELECT i2.pos FROM all_data i2 WHERE ss.field_row_id=i2.row_id2)) AS front_dist
                             FROM all_data ss),
            dire AS (SELECT field_row_id, pos, row_id2, row_id3, row_nbr,
                CASE WHEN abs(min_dir_1-max_dir_1) < 25 AND course > min_dir_1 AND course < max_dir_1 THEN 1
                     WHEN abs(min_dir_1-max_dir_1) > 25 AND (course > min_dir_1 OR course < max_dir_1) THEN 1
                     WHEN abs(min_dir_2-max_dir_2) < 25 AND course > min_dir_2 AND course < max_dir_2 THEN 2
                     WHEN abs(min_dir_2-max_dir_2) > 25 AND (course > min_dir_2 OR course < max_dir_2) THEN 2
                     ELSE 0 END AS direction
                FROM all_data, course_limits),
            tractor_turn AS (SELECT field_row_id, pos, row_id2, row_id3, row_nbr, direction,
                             count(*) FILTER (WHERE dir_change) OVER (ORDER BY field_row_id) AS tractor_row
                             FROM (SELECT *, lag(direction) OVER (ORDER BY field_row_id) <> direction AS dir_change FROM dire WHERE direction>0) s),
            sep_rows AS (SELECT field_row_id, pos, row_nbr, row_id2, row_id3, tractor_row,
                         row_nbr+((tractor_row+1)*{max_rows})-{max_rows} AS uni_row
                         FROM tractor_turn
                         ORDER BY row_nbr+((tractor_row+1)*{max_rows})-{max_rows}, row_nbr, tractor_row, field_row_id)
            UPDATE {s_t} old_t
            SET new_row_id = org.uni_row,
                polygon = st_multi(st_buffer(st_makeline(st_centroid(st_makeline(org.pos, i2.pos)), st_centroid(st_makeline(org.pos, i3.pos))),
                                             (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY side_dist) FROM row_width)/2,
                                             'endcap=flat'))
            FROM sep_rows org
            JOIN sep_rows i2 ON org.field_row_id=i2.row_id2 AND org.uni_row=i2.uni_row
            JOIN sep_rows i3 ON org.field_row_id=i3.row_id3 AND org.uni_row=i3.uni_row
            WHERE st_length(st_makeline(st_centroid(st_makeline(org.pos, i2.pos)), st_centroid(st_makeline(org.pos, i3.pos)))) < (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY front_dist) FROM point_length)*4
            AND old_t.field_row_id=org.field_row_id
            """).format(s_t=s_t, max_rows=max_rows_lit, row=row_id, course=course_id)
            self.db.execute_sql(sql)
            sql = pgsql.SQL(
                "WITH data AS (SELECT field_row_id, pos, new_row_id,"
                " lag(pos) OVER(PARTITION BY new_row_id ORDER BY field_row_id ASC) AS pos2,"
                " lag(field_row_id) OVER(PARTITION BY new_row_id ORDER BY field_row_id ASC) AS id2"
                " FROM {s_t})"
                " SELECT new_row_id, field_row_id, st_distance(pos::geography, pos2::geography), id2"
                " FROM data"
                " WHERE st_distance(pos::geography, pos2::geography) > 35 AND new_row_id IS NOT NULL"
            ).format(s_t=s_t)
            data = self.db.execute_and_return(sql)
            max_id = self.db.execute_and_return(
                pgsql.SQL("SELECT max(new_row_id) FROM {s_t}").format(s_t=s_t))[0][0]
            for r_id, tbl_id, dist, tbl_id2 in data:
                max_id += 1
                self.db.execute_sql(
                    pgsql.SQL(
                        "UPDATE {s_t} SET new_row_id = %s"
                        " WHERE new_row_id = %s AND field_row_id >= %s"
                    ).format(s_t=s_t),
                    params=(max_id, r_id, tbl_id))
            sql = pgsql.SQL(
                "WITH f_sel AS (SELECT new_row_id, st_x(pos), st_y(pos), {course}"
                " FROM {s_t} WHERE new_row_id IS NOT NULL),"
                " s_sel AS (SELECT new_row_id, avg(course) AS av_course,"
                " min(st_x) AS min_x, max(st_x) AS max_x, min(st_y) AS min_y, max(st_y) AS max_y"
                " FROM f_sel GROUP BY new_row_id),"
                " northsouth AS (SELECT CASE WHEN ((SELECT av_course FROM s_sel LIMIT 1) BETWEEN 45 AND 135)"
                " OR ((SELECT av_course FROM s_sel LIMIT 1) BETWEEN 225 AND 315) THEN FALSE"
                " ELSE TRUE END AS ns),"
                " t_sel AS (SELECT new_row_id FROM s_sel, northsouth"
                " ORDER BY CASE WHEN ns IS TRUE THEN min_x END ASC,"
                " CASE WHEN ns IS FALSE THEN max_y END DESC),"
                " fo_sel AS (SELECT ROW_NUMBER() OVER() AS up_nbr, new_row_id FROM t_sel)"
                " UPDATE {s_t} u1 SET new_row_id = up_nbr"
                " FROM fo_sel WHERE u1.new_row_id = fo_sel.new_row_id"
            ).format(s_t=s_t, course=course_id)
            self.db.execute_sql(sql)
            return [True]
        except Exception as e:
            return [False, e, traceback.format_exc()]
