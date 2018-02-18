import pyowm
import time
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import psycopg2
import psycopg2.extras
import gzip
import os

class DBException(Exception):
    pass

class DB():
    def __init__(self):
        self.dbhost = '104.155.48.69'
        self.dbname = "weather_data"
        self.dbuser = "postgres"
        self.dbpass = "horteborn1"
        self.conn = None

    def _connect(self):
        if self.conn is None:
            try:
                self.conn = psycopg2.connect(
                    host=self.dbhost,
                    database=self.dbname,
                    user=self.dbuser,
                    password=self.dbpass
                    )
            except psycopg2.OperationalError as e:
                raise DBException("Error connecting to database on '%s'. %s" %
                                  (self.dbhost, str(e)))

    def _close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def run_sql(self, sql):
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql)
        self.conn.commit()
        self._close()

    def run_list_sql(self, sqls):
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        for sql in sqls:
            print(sqls.index(sql))
            cur.execute(sql)
        self.conn.commit()
        self._close()

    def execute_and_return(self, sql):
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql)
        data = cur.fetchall()
        self._close()
        return data

    def create_database(self):
        self._connect()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql1 = """DROP TABLE public.weather_data;
        Create table weather_data(
station_id bigint,
wind_speed numeric(4,2),
wind_dir numeric(4,1),
cloud smallint,
weather_discription_id smallint,
observation_time bigint,
humidity smallint,
rain_1h numeric(4,2),
rain_3h numeric(4,2),
temperature numeric(5,2),
sun_rise bigint,
sun_set bigint,
pressure_station numeric(5,1),
pressure_sea numeric(5,1)
);"""
        sql2 = """DROP TABLE public.weather_types;
        Create table weather_types(
row_id smallint,
weather_discription text
);"""
        sql3 = """DROP TABLE public.city_list;

CREATE TABLE public.city_list
(
  station_id bigint,
  country character varying(5),
  name text,
  lat numeric(10,7),
  lon numeric(10,7),
  point geometry(Point,4326)
);"""
        cur.execute(sql1)
        cur.execute(sql2)
        #cur.execute(sql3)
        self.conn.commit()



class store_weather():
    def __init__(self):
        self.DB = DB()
        res = input('Do you really want to reset the weather database? (y/n): ')
        if res == 'y':
            self.DB.create_database()

    def read_city_list(self):
        data = []
        with open('city.list.json', encoding="utf8") as f:
            for line in f.readlines():
                id = line[line.find('_id')+5:line.find('name')-2]
                country = line[line.find('country')+9:line.find(',"coord')]
                name = line[line.find('name')+6:line.find('country')-2]
                name = name.replace("'","_")
                lon = line[line.find('"lon"')+6:line.find('"lat"')-1]
                lat = line[line.find('"lat"') + 6:- 3]
                point = "ST_PointFromText('POINT(" + str(lon) + " " + str(lat)+ ")', 4326)"
                sql = """insert into city_list Values(""" + str(id) + """,
""" + str(country) + """,
""" + str(name) + """,
""" + str(lat) + """,
""" + str(lon) + """,
""" + str(point) + """)"""
                sql = sql.replace('"',"'")
                data.append(sql)
            self.DB.run_list_sql(data)

    def get_swedish_id(self):
        sql = "select station_id from city_list where country = 'SE'"
        list = self.DB.execute_and_return(sql)
        return list

    def get_weather_description(self, description):
        sql = """select row_id from weather_types where weather_discription = '%s'""" %description
        sql = sql.replace("\\\\", "")
        _id = self.DB.execute_and_return(sql)
        if len(_id) == 0:
            max_id = self.DB.execute_and_return("select max(row_id) from weather_types")
            if max_id[0][0] == None:
                self.DB.run_sql("""insert into weather_types Values(1, '%s')""" %description)
                return 1
            else:
                self.DB.run_sql("""insert into weather_types Values(""" + str(max_id[0][0]+1) + """, '%s')""" %description)
                return max_id[0][0] + 1
        else:
            return _id[0][0]

    def run(self):
        printing = False
        owm = pyowm.OWM('922e511606ba08af257f1fc5986903db')
        #print(owm._parsers['station_list'])
        station_ids = self.get_swedish_id()
        i = 0
        t1 = time.time()
        with open('error_log', 'a') as f:
            for station_id in station_ids:
                station_id = station_id[0]
                #print(i)
                i += 1
                #time.sleep(0.5)
                try:
                    try:
                        station = owm.weather_at_id(station_id)
                    except:
                        continue
                    if station == None:
                        #print('Failed: ' + str(station_id))
                        continue
                    w = station.get_weather()
                    wind_speed = w.get_wind()['speed']
                    wind_dir = w.get_wind()['deg']
                    visability = w.get_visibility_distance()
                    cloud = w.get_clouds()
                    weather_description = w.get_detailed_status()
                    observation_time = w._reference_time
                    humidity = w.get_humidity()
                    try:
                        rain_3h = w.get_rain()['3h']
                        if rain_3h == None:
                            rain_3h = 0
                    except:
                        #print(w.get_rain())
                        rain_3h = None
                    try:
                        rain_1h = w.get_rain()['1h']
                        if rain_1h == None:
                            rain_1h = 0
                    except:
                        rain_1h = None
                    temperature = w.get_temperature()['temp']
                    sun_rise = w.get_sunrise_time()
                    sun_set = w.get_sunset_time()
                    pressure_station = w.get_pressure()['press']
                    pressure_sea = w.get_pressure()['sea_level']
                    description_id = self.get_weather_description(weather_description)
                    sql = """insert into weather_data Values(""" + str(station_id) + """,
        """ + str(wind_speed) + """,
        """ + str(wind_dir) + """,
        """ + str(cloud) + """,
        """ + str(description_id) + """,
        """+ str(observation_time) + """,
        """+ str(humidity) + """,
        """+ str(rain_1h) + """,
        """+ str(rain_3h) + """,
        """+ str(temperature) + """,
        """+ str(sun_rise) + """,
        """+ str(sun_set) + """,
        """+ str(pressure_station) + """,
        """+ str(pressure_sea) + """)"""
                    sql = sql.replace('None', 'Null')
                    self.DB.run_sql(sql)
                    if printing:
                        #print('Current weather in ' + w.get_weather_icon_name())
                        print('wind speed: ' + str(wind_speed))
                        print('wind direction: ' + str(wind_dir))
                        print('Visability length: ' + str(visability))
                        print('Current weather: ' + weather_description)
                        print('Cloud cover: ' + str(cloud) + '%')
                        print('Temperature: ' + str(temperature-273) + ' deg C')
                        #print(w.get_heat_index())
                        #print(w.get_weather_code())
                        print('Observation time: ' + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(observation_time)))
                except Exception as exp:
                    f.write(str(station_id) + ', ' + str(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + str(exp) + '\n')
        print(datetime.datetime.strftime(datetime.datetime.now() + datetime.timedelta(hours=1), "%Y-%m-%d %H:%M:%S") + ' The cycle took ' +str((time.time()-t1)/60) + ' minutes to run ')

    def safe_copy(self):
        name = str(time.strftime("%Y_%m_%d", time.localtime())) + '.txt'
        sql = "select * from weather_data"
        data = self.DB.execute_and_return(sql)
        with open(name, 'w') as f:
            for sublist in data:
                for item in sublist:
                    f.write(str(item) + ', ')
                f.write('\n')
        f_in = open(name, 'rb')
        f_out = gzip.open(name + '.gz', 'wb')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()
        os.remove(name)

store_weather = store_weather()
t1 = time.time()
#store_weather.safe_copy()
#store_weather.get_swedish_id()
scheduler = BlockingScheduler()
scheduler.add_job(store_weather.run, 'interval', hours=1)
scheduler.add_job(store_weather.safe_copy, 'interval', weeks=1)
scheduler.start()
