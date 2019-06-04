from PyQt5.QtWidgets import QMessageBox
from qgis.core import QgsTask
import traceback
from ..widgets.fix_rows import FixRowsDialog
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
        self.FRD.exec_()

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
                if name[0] in ["temp_polygon", 'manual', 'harrowing_manual',
                               'plowing_manual']:
                    continue
                names.append(schema + '.' + str(name[0]))
        self.FRD.CBDataSource.addItems(names)
        self.FRD.CBDataSource.activated[str].connect(self.set_possible_columns)

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
        cols = self.db.get_all_columns(table=text.split('.')[1],
                                       schema=text.split('.')[0],
                                       exclude="'cmax', 'cmin', 'ctid', 'xmax', 'xmin', 'tableoid', 'pos', 'date_', 'polygon', 'field_row_id'")
        columns = []
        for col in cols:
            columns.append(col[0])
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
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr(
                                        'Following error occurred: {m}\n\n Traceback: {t}'.format(
                                            m=values[1],
                                            t=values[2])))
            return
        else:
            QMessageBox.information(None, self.tr("Information:"),
                                    self.tr('The geometries have updated'))

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
            row = self.FRD.CBRow.currentText()
            course = self.FRD.CBCourse.currentText()
            sql = """alter table {s_t}
                add column new_row_id int;
            with dat as(SELECT field_row_id, pos, {course} as course, {row} as row_nbr
                FROM {s_t}
                       limit 1000
            ), 
            all_data as (select field_row_id, pos, course, {row} as row_nbr, lead(field_row_id) OVER(ORDER BY {row}, field_row_id ASC) as row_id2, lag(field_row_id) OVER(ORDER BY {row}, field_row_id ASC) as row_id3
                         FROM {s_t}
                         --limit 10000
            ),
            dat2 as (SELECT field_row_id, pos, course, row_nbr, lead(field_row_id) OVER(ORDER BY row_nbr, field_row_id ASC) as row_id2
                     from dat
            ), 
            course_limits as (select (degrees(atan2(sind((select mode() within group (order by course) -10 from all_data)), cosd((select mode() within group (order by course) -10 from all_data)))) + 360)::int % 360 as min_dir_1,
                       (degrees(atan2(sind((select mode() within group (order by course) from all_data)+10), cosd((select mode() within group (order by course) from all_data)+10))) + 360)::int % 360  as max_dir_1,
                       (degrees(atan2(sind((select mode() within group (order by course) +170 from all_data)), cosd((select mode() within group (order by course) +170 from all_data)))) + 360)::int % 360 as min_dir_2,
                       (degrees(atan2(sind((select mode() within group (order by course) from all_data)+190), cosd((select mode() within group (order by course) from all_data)+190)))  + 360)::int % 360 as max_dir_2
            ), 
            row_width as(
                       select st_distance(ss.pos, 
                                          (select i2.pos from dat i2 where i2.row_nbr=3 order by st_distance(i2.pos, ss.pos) limit 1)) as side_dist
                       from dat ss
                       where ss.row_nbr = 2
            ),
            point_length as(
                       select field_row_id, st_distance(pos, 
                                          (select i2.pos from all_data i2 where ss.field_row_id=i2.row_id2)) as front_dist
                       from all_data ss
                       --where ss.row_nbr=2
            ), 
    
            dire as (select field_row_id, pos, row_id2, row_id3, row_nbr, 
                case when abs(min_dir_1-max_dir_1) < 25 and course > min_dir_1 and course < max_dir_1 then 1 
                  when abs(min_dir_1-max_dir_1) > 25 and (course > min_dir_1 or course < max_dir_1) then 1 
                  when abs(min_dir_2-max_dir_2) < 25 and course > min_dir_2 and course < max_dir_2 then 2
                  when abs(min_dir_2-max_dir_2) > 25 and (course > min_dir_2 or course < max_dir_2) then 2 	
                  else 0
                end as direction
                from all_data, 
                     course_limits
            ),
            tractor_turn as(select field_row_id, pos,row_id2, row_id3, row_nbr, direction, count(*) filter (where dir_change) over (order by field_row_id) as tractor_row
                from (select *, lag(direction) over (order by field_row_id) <> direction as dir_change from dire where direction>0) s
            ),
            sep_rows as(select field_row_id, pos, row_nbr, row_id2, row_id3, tractor_row, row_nbr+((tractor_row+1)*{max_rows})-{max_rows} as uni_row
                        from tractor_turn 
                        order by row_nbr+((tractor_row+1)*{max_rows})-{max_rows}, row_nbr, tractor_row, field_row_id
            )
            update {s_t} old_t
            set new_row_id = org.uni_row,
            polygon =  st_multi(st_buffer(st_makeline(st_centroid(st_makeline(org.pos, i2.pos)), st_centroid(st_makeline(org.pos, i3.pos))),
                                                             (select PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY side_dist) from row_width)/2,
                                                             'endcap=flat'
                                                             ))
            from sep_rows org
            join sep_rows i2 on org.field_row_id=i2.row_id2 and org.uni_row=i2.uni_row
            join sep_rows i3 on org.field_row_id=i3.row_id3 and org.uni_row=i3.uni_row
            where st_length(st_makeline(st_centroid(st_makeline(org.pos, i2.pos)), st_centroid(st_makeline(org.pos, i3.pos)))) < (select PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY front_dist) from point_length)*4
            and old_t.field_row_id=org.field_row_id
            """.format(s_t=schema_table, max_rows=max_rows, row=row, course=course)
            self.db.execute_sql(sql)
            sql = """with data as(select field_row_id, pos, new_row_id, lag(pos) OVER(partition BY new_row_id ORDER BY field_row_id ASC) as pos2, lag(field_row_id) OVER(partition BY new_row_id ORDER BY field_row_id ASC) as id2
            from {s_t})
            Select new_row_id, field_row_id, st_distance(pos::geography,pos2::geography), id2 
            from data 
            where st_distance(pos::geography,pos2::geography) > 35 and new_row_id is not Null""".format(
                s_t=schema_table)
            data = self.db.execute_and_return(sql)
            max_id = self.db.execute_and_return(
                "select max(new_row_id) from {s_t}".format(s_t=schema_table))[0][0]
            for row_id, tbl_id, dist, tbl_id2 in data:
                max_id += 1
                sql = """Update {s_t}
                set new_row_id = {nbr}
                where new_row_id = {r_id} and field_row_id >= {t_id}""".format(
                    s_t=schema_table, nbr=max_id, r_id=row_id, t_id=tbl_id)
                self.db.execute_sql(sql)
            sql = """with f_sel as (select new_row_id, st_x(pos), st_y(pos), {course}
            from {s_t}
            where new_row_id is not Null),
            s_sel as (select new_row_id, avg(course) as av_course, min(st_x) as min_x, max(st_x) as max_x, min(st_y) as min_y, max(st_y) as max_y
            from f_sel 
            group by new_row_id),
            northsouth as (select case when ((select av_course from s_sel limit 1) between 45 and 135) or ((select av_course from s_sel limit 1) between 225 and 315) then false
            else true end as ns),
            t_sel as (select new_row_id
            from s_sel, northsouth
            order by case when ns is true then min_x end asc, case when ns is false then max_y end desc),
            fo_sel as (select ROW_NUMBER() OVER() as up_nbr, new_row_id
            from t_sel)
            update {s_t} u1
            set new_row_id = up_nbr
            from fo_sel
            where u1.new_row_id = fo_sel.new_row_id
            """.format(s_t=schema_table, course=course)
            self.db.execute_sql(sql)
            return [True]
        except Exception as e:
            return [False, e, traceback.format_exc()]
