#!/usr/bin/python3
# -*- coding: utf-8 -*-
from flask import Flask
from flask import jsonify, request, render_template
from flask import abort
import eventlet
from flask_socketio import SocketIO
from flask_socketio import emit
import datetime
import json
import requests
from locale import setlocale, LC_ALL
import inspect
import sqlite3
import logging
import uuid

eventlet.monkey_patch()
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.DEBUG)


app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', engineio_logger=False)


ARDUINO_IP = 'http://192.168.1.10'
ARDUINO_WEATHER_IP = 'http://192.168.1.10'
# ARDUINO_IP='http://185.20.216.94:5555'

# ARDUINO_IP = 'http://192.168.1.144'
# ARDUINO_IP = 'http://butenko.asuscomm.com:5555'

HUMIDITY_MAX = 1000
RULES_FOR_BRANCHES = [None] * 18
SENSORS = {'time': datetime.now, 'data': {'temperature': 0, 'humidity': 0, 'rain': False, 'daylight': False}, 
'user_message': '', 'allow_irrigation': False}


# For get function name intro function. Usage mn(). Return string with current function name. Instead 'query' will be QUERY[mn()].format(....)
mn = lambda: inspect.stack()[1][3]

QUERY = {}
QUERY['get_next_active_rule'] = "SELECT l.id, l.line_id, l.rule_id, l.timer as \"[timestamp]\", l.interval_id  FROM life AS l WHERE l.state = 1 AND l.active=1 AND l.line_id={0} AND timer>=datetime('now', 'localtime') ORDER BY timer LIMIT 1"
QUERY['get_table_body_only'] = "SELECT l.id, li.name, rule_type.name, l.state, l.date, l.timer as \"[timestamp]\", l.active, rule_state.full_name, l.interval_id FROM life as l, type_of_rule as rule_type, lines as li, state_of_rule as rule_state WHERE l.rule_id = rule_type.id AND l.line_id = li.number and l.state = rule_state.id order by l.id, l.timer desc, l.interval_id"
QUERY['ongoing_rules_table'] = "SELECT w.id, dw.name, li.name, rule_type.name, \"time\" as \"[timestamp]\", \"interval\", w.active FROM week_schedule as w, day_of_week as dw, lines as li, type_of_rule as rule_type WHERE  w.day_number = dw.num AND w.line_id = li.number and w.rule_id = rule_type.id ORDER BY w.day_number, w.time"
QUERY['branches_names'] = "SELECT number, name from lines order by number"
QUERY['timetable'] = "SELECT l.id, li.name, rule_type.name, l.state, l.date, l.timer as \"[timestamp]\", l.active, rule_state.full_name, l.interval_id FROM life as l, type_of_rule as rule_type, lines as li, state_of_rule as rule_state WHERE l.rule_id = rule_type.id AND l.line_id = li.number AND l.timer>= datetime('now', 'localtime', '-{0} hours') AND l.timer<=datetime('now', 'localtime', '+{0} hours') and l.state = rule_state.id order by l.id, l.timer desc, l.interval_id"
QUERY['history_1'] = "SELECT l.id, li.name, rule_type.name, l.state, l.date, l.timer as \"[timestamp]\", l.active, rule_state.full_name FROM life as l, type_of_rule as rule_type, lines as li, state_of_rule as rule_state WHERE l.rule_id = rule_type.id AND l.line_id = li.number AND l.timer >= datetime('now', 'localtime', '-{0} day') AND l.timer <=datetime('now', 'localtime') and l.state = rule_state.id order by l.id, l.timer desc, l.interval_id"
QUERY['history_2'] = "SELECT l.id, li.name, rule_type.name, l.state, l.date, l.timer as \"[timestamp]\", l.active, rule_state.full_name FROM life as l, type_of_rule as rule_type, lines as li, state_of_rule as rule_state WHERE l.rule_id = rule_type.id AND l.line_id = li.number AND l.timer <= datetime('now', 'localtime') and l.state = rule_state.id order by l.id, l.timer desc"
QUERY['ongoing_rules'] = "SELECT w.id, dw.name, li.name, rule_type.name, \"time\" as \"[timestamp]\", \"interval\", w.active FROM week_schedule as w, day_of_week as dw, lines as li, type_of_rule as rule_type WHERE  w.day_number = dw.num AND w.line_id = li.number and w.rule_id = rule_type.id and l.state = rule_state.id ORDER BY w.day_number, w.time"
QUERY['get_timetable_list_1'] = "SELECT l.id, li.name, rule_type.name, l.state, l.date, l.timer as \"[timestamp]\", l.active, rule_state.full_name FROM life as l, type_of_rule as rule_type, lines as li, state_of_rule as rule_state WHERE l.rule_id = rule_type.id AND l.line_id = li.number AND l.timer<=datetime('now', 'localtime','+{0} day') and l.state = rule_state.id  order by l.id, l.timer desc, l.interval_id"
QUERY['get_timetable_list_2'] = "SELECT l.id, li.name, rule_type.name, l.state, l.date, l.timer as \"[timestamp]\", l.active, rule_state.full_name FROM life as l, type_of_rule as rule_type, lines as li, state_of_rule as rule_state WHERE l.rule_id = rule_type.id AND l.line_id = li.number AND l.timer>= datetime('now', 'localtime', '-{0} hour') and l.timer<=datetime('now', 'localtime', '+{0} hour') and l.state = rule_state.id  order by l.id, l.timer desc, l.interval_id"
QUERY['add_rule'] = "INSERT INTO life(line_id, rule_id, state, date, timer, interval_id) VALUES ({0}, {1}, {2}, '{3}', '{4}', '{5}')"
QUERY['add_ongoing_rule'] = "INSERT INTO week_schedule(day_number, line_id, rule_id, \"time\", \"interval\", active) VALUES ({0}, {1}, {2}, '{3}', {4}, 1)"
QUERY['activate_branch_1'] = "INSERT INTO life(line_id, rule_id, state, date, timer, interval_id) VALUES ({0}, {1}, {2}, '{3}', '{4}', '{5}')"
QUERY['activate_branch_2'] = "SELECT id, line_id, rule_id, timer, interval_id FROM life where id = {0}"
QUERY['deactivate_branch_1'] = "UPDATE life SET state=4 WHERE interval_id = '{0}'"
QUERY['deactivate_branch_2'] = "INSERT INTO life(line_id, rule_id, state, date, timer, interval_id) VALUES ({0}, {1}, {2}, '{3}', '{4}', '{5}')"
QUERY['enable_rule'] = "UPDATE life SET state=2 WHERE id={0}"
QUERY['enable_rule_state_6'] = "UPDATE life SET state=6 WHERE id={0}"
QUERY['activate_rule'] = "UPDATE life SET active=1 WHERE id={0}"
QUERY['deactivate_rule'] = "UPDATE life SET active=0 WHERE id={0}"
QUERY['deactivate_all_rules_1'] = "UPDATE life SET active=0 WHERE timer>= datetime('now', 'localtime') AND timer<=datetime('now', 'localtime', '+1 day')"
QUERY['deactivate_all_rules_2'] = "UPDATE life SET active=0 WHERE timer>= datetime('now', 'localtime')  AND timer<=datetime('now', 'localtime', '+7 days')"
QUERY['activate_ongoing_rule'] = "UPDATE week_schedule SET active=1 WHERE id={0}"
QUERY['deactivate_ongoing_rule'] = "UPDATE week_schedule SET active=0 WHERE id={0}"
QUERY['remove_rule'] = "DELETE from life WHERE id={0}"
QUERY['remove_ongoing_rule'] = "DELETE from week_schedule WHERE id={0}"
QUERY['edit_ongoing_rule'] = "DELETE from week_schedule WHERE id={0}"

setlocale(LC_ALL, 'ru_UA.utf-8')


@socketio.on_error_default
def error_handler(e):
    """Used to handle error for websockets."""
    logging.error('error_handler for socketio. An error has occurred: ' + str(e))


@socketio.on('connect')
def connect():
    """Log info if user is connected to websocket."""
    logging.info('Client connected')


@socketio.on('disconnect')
def disconnect():
    """Log info if user is disconnected to websocket."""
    logging.info('Client disconnected')


def set_next_rule_in_redis(branch_id, data):
    """Set next rule in redis."""
    return data


def get_next_rule_in_redis(branch_id):
    """Get next rule from redis."""
    return 'data'


def send_message(channel, data):
    """Enclose emit method into try except block."""
    try:
        socketio.emit(channel, data)
        logging.debug('Message was sent')
    except Exception as e:
        logging.error(e)
        logging.error("Can't send message. Exeption occured")


def get_weather(force_update=False):
    """Use data from weather station. Refresh data per hour."""
    if (force_update is True or datetime.datetime.now() > (datetime.datetime.now() + datetime.timedelta(minutes=60))):
        json_data = ''
        try:
            response = requests.get(url=ARDUINO_WEATHER_IP + "/weather")
            json_data = json.loads(response.text)
        except Exception as e:
            logging.error(e)
            logging.error("Can't get weather status. Exeption occured")
            return None

        SENSORS['time'] = datetime.datetime.now()
        SENSORS['data']['temperature'] = json_data['temperature']
        SENSORS['data']['humidity'] = json_data['humidity']
        SENSORS['data']['rain'] = json_data['rain']
        SENSORS['data']['daylight'] = json_data['daylight']

    SENSORS['data']['allow_irrigation'] = True
    SENSORS['data']['user_message'] = 'Автоматический полив разрешен.'

    if (SENSORS['data']['rain'] is True):
        SENSORS['data']['allow_irrigation'] = False
        SENSORS['data']['user_message'] = 'Автоматический полив запрещен из-за дождя.'

    if (SENSORS['data']['humidity'] > HUMIDITY_MAX):
        SENSORS['data']['allow_irrigation'] = False
        SENSORS['data']['user_message'] = 'Автоматический полив датчиком влажности.'

    return SENSORS


@app.route("/weather_station")
def weather_station():
    """Synchronize with weather station."""
    get_weather(True)
    return str(SENSORS)


# executes query and returns fetch* result
def execute_request(query, method='fetchall'):
    """Use this method in case you need to get info from database."""
    conn = None
    try:
        # conn = psycopg2.connect("dbname='test' user='sprinkler' host='185.20.216.94' port='35432' password='drop#'")
        conn = sqlite3.connect('/var/sqlite_db/test_v4', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        # conn.cursor will return a cursor object, you can use this cursor to perform queries
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # execute our Query
        cursor.execute(query)
        logging.debug("db request '{0}' executed".format(query))
        return getattr(cursor, method)()
    except Exception as e:
        logging.error("Error while performing operation with database: {0}".format(e))
        return None
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception as e:
            logging.error("Error while closing connection with database: {0}".format(e))


# executes query and returns fetch* result
def update_db_request(query):
    """Doesn't have fetch* methods. Returns lastrowid after database insert command."""
    conn = None
    lastrowid = 0
    try:
        # conn = psycopg2.connect("dbname='test' user='sprinkler' host='185.20.216.94' port='35432' password='drop#'")
        conn = sqlite3.connect('/var/sqlite_db/test', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        # conn.cursor will return a cursor object, you can use this cursor to perform queries
        cursor = conn.cursor()
        # execute our Query
        cursor.execute(query)
        conn.commit()
        logging.debug("db request '{0}' executed".format(query))
        lastrowid = cursor.lastrowid
        return lastrowid
    except Exception as e:
        logging.error("Error while performing operation with database: {0}".format(e))
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception as e:
            logging.error("Error while closing connection with database: {0}".format(e))
            return None


def get_next_active_rule(line_id):
    """Return nex active rule."""
    query = QUERY[mn()].format(line_id)
    res = execute_request(query, 'fetchone')
    if res is None:
        return None

    logging.info("Next active rule retrieved for line id {0}".format(line_id))
    return {'id': res[0], 'line_id': res[1], 'rule_id': res[2], 'timer': res[3], 'interval_id': res[4]}


def update_all_rules():
    """Set next active rules for all branches."""
    try:
        for i in range(1, len(RULES_FOR_BRANCHES), 1):
            RULES_FOR_BRANCHES[i] = get_next_active_rule(i)
        logging.info("Rules updated")
    except Exception as e:
        logging.error("Exeption occured while updating all rules. {0}".format(e))


@app.route("/update_all_rules")
def update_rules():
    """Synchronize rules with database."""
    update_rules()
    return str(RULES_FOR_BRANCHES)


@app.route("/branches_names")
def branches_names():
    """Return branch names."""
    branch_list = []
    res = execute_request(QUERY[mn()], 'fetchall')
    if res is None:
        logging.error("Can't get branches names from database")
        abort(500)

    for row in res:
        branch_list.append({'id': row[0], 'name': row[1]})

    return jsonify(list=branch_list)


@app.route("/")
def index():
    """Index page."""
    return app.send_static_file('index.html')


def get_table_body_only(query=None):
    """If no query is passed returns all entries from life table."""
    if (query is None):
        query = QUERY[mn()]

    list_arr = execute_request(query, 'fetchall')

    rows = []
    if list_arr is not None:
        for row in list_arr:
            id = row[0]
            branch_name = row[1]
            rule_name = row[2]
            state = row[3]
            timer = row[5]
            active = row[6]
            rule_state = row[7]
            outdated = 0
            if (state == 1 and timer < datetime.datetime.now() - datetime.timedelta(minutes=1)):
                outdated = 1

            rows.append({'id': id, 'branch_name': branch_name, 'rule_name': rule_name, 'state': state,
                'timer': "{:%A, %d-%m-%y %R}".format(timer), 'outdated': outdated, 'active': active, 'rule_state': rule_state})

    template = render_template('timetable_table_only.html', my_list=rows)
    return template


@app.route("/timetable")
def timetable():
    """Blablbal."""
    list_arr = execute_request(QUERY[mn()].format(1, 24), 'fetchall')
    rows = []
    for row in list_arr:
        id = row[0]
        branch_name = row[1]
        rule_name = row[2]
        state = row[3]
        timer = row[5]
        active = row[6]
        rule_state = row[7]
        outdated = 0
        if (state == 1 and timer < datetime.datetime.now() - datetime.timedelta(minutes=1)):
            outdated = 1

        rows.append({'id': id, 'branch_name': branch_name, 'rule_name': rule_name, 'state': state,
            'timer': "{:%A, %d-%m-%y %R}".format(timer), 'outdated': outdated, 'active': active, 'rule_state': rule_state})

    template = render_template('timetable.html', my_list=rows)
    return template


@app.route("/history")
def history():
    """Return history page if no parameters passed and only table body if opposite."""
    if 'days' in request.args:
        days = int(request.args.get('days'))
        return get_table_body_only(QUERY[mn() + '_1'].format(days))

    list_arr = execute_request(QUERY[mn() + '_2'], 'fetchall')
    rows = []
    if list_arr is not None:
        for row in list_arr:
            id = row[0]
            branch_name = row[1]
            rule_name = row[2]
            state = row[3]
            timer = row[5]
            active = row[6]
            rule_state = row[7]
            outdated = 0
            if (state == 1 and timer < datetime.datetime.now() - datetime.timedelta(minutes=1)):
                outdated = 1

            rows.append({'id': id, 'branch_name': branch_name, 'rule_name': rule_name, 'state': state,
                'timer': "{:%A, %d-%m-%y %R}".format(timer), 'outdated': outdated, 'active': active, 'rule_state': rule_state})

    template = render_template('history.html', my_list=rows)
    return template


@app.route("/add_rule")
def add_rule():
    """Used in add rule modal window."""
    is_interval = request.args.get('is_interval')
    if (is_interval is None):
        logging.error("no interval parameter passed")
        abort(404)
    is_interval = str(is_interval)

    if (is_interval == 'false'):
        branch_id = int(request.args.get('branch_id'))
        time_min = int(request.args.get('time_min'))
        start_time = datetime.datetime.strptime(request.args.get('datetime_start'), "%Y-%m-%d %H:%M")

        time_wait = 0
        num_of_intervals = 0
    elif (is_interval == 'true'):
        branch_id = int(request.args.get('branch_id'))
        time_min = int(request.args.get('time_min'))
        start_time = datetime.datetime.strptime(request.args.get('datetime_start'), "%Y-%m-%d %H:%M")

        time_wait = int(request.args.get('time_wait'))
        num_of_intervals = int(request.args.get('quantity'))
    else:
        logging.error("incorrect interval parameter passed: {0}".format(is_interval))
        abort(404)

    interval_id = str(uuid.uuid4())
    now = datetime.datetime.now()
    stop_time = start_time + datetime.timedelta(minutes=time_min)

    update_db_request(QUERY[mn()].format(branch_id, 1, 1, now.date(), start_time, interval_id))
    update_db_request(QUERY[mn()].format(branch_id, 2, 1, now.date(), stop_time, interval_id))

    # first interval is executed
    for x in range(2, num_of_intervals + 1):
        start_time = stop_time + datetime.timedelta(minutes=time_wait)
        stop_time = start_time + datetime.timedelta(minutes=time_min)
        update_db_request(QUERY[mn()].format(branch_id, 1, 1, now.date(), start_time, interval_id))
        update_db_request(QUERY[mn()].format(branch_id, 2, 1, now.date(), stop_time, interval_id))
        logging.info("Start time: {0}. Stop time: {1} added to database".format(str(start_time), str(stop_time)))

    update_all_rules()
    template = get_table_body_only()
    send_message('list_update', {'data': template})
    return template


@app.route("/remove_rule")
def remove_rule():
    """User can remove rule from ongoing rules table."""
    id = int(request.args.get('id'))
    update_db_request(QUERY[mn()].format(id))
    update_all_rules()
    template = get_table_body_only()
    send_message('list_update', {'data': template})
    return template


# @app.route("/modify_rule")
# def modify_rule():


@app.route("/activate_rule")
def activate_rule():
    """Rule can be activated from timetable and hostory pages."""
    id = int(request.args.get('id'))
    update_db_request(QUERY[mn()].format(id))
    update_all_rules()
    template = get_table_body_only()
    send_message('list_update', {'data': template})
    return template


@app.route("/deactivate_rule")
def deactivate_rule():
    """Rule can be deactivated from timetable and hostory pages."""
    id = int(request.args.get('id'))
    update_db_request(QUERY[mn()].format(id))
    update_all_rules()
    template = get_table_body_only()
    send_message('list_update', {'data': template})
    return template


@app.route("/deactivate_all_rules")
def deactivate_all_rules():
    """User can deactivate all rules for one day and a week."""
    id = int(request.args.get('id'))
    # 1-24h;2-7d;3-on demand
    if (id == 1):
        update_db_request(QUERY[mn() + '_1'])
        update_all_rules()
        template = get_table_body_only()
        send_message('list_update', {'data': template})
        return template

    if (id == 2):
        update_db_request(QUERY[mn() + '_2'])
        update_all_rules()
        template = get_table_body_only()
        send_message('list_update', {'data': template})
        return template

    if (id == 3):
        logging.warn("Is not implemented yet")
        # RULES_ENABLED=False

    return 'OK'


def ongoing_rules_table():
    """Return only table for ongoing rules page."""
    list_arr = execute_request(QUERY[mn()], 'fetchall')
    if (list_arr is None):
        list_arr = []

    rows = []
    for row in list_arr:
        id = row[0]
        day_number = row[1]
        branch_name = row[2]
        rule_name = row[3]
        time = row[4]
        minutes = row[5]
        active = row[6]
        rule_state = row[7]
        rows.append({'id': id, 'branch_name': branch_name, 'dow': day_number, 'rule_name': rule_name,
                'time': time, 'minutest': minutes, 'active': active, 'rule_state': rule_state})

    template = render_template('ongoing_rules_table_only.html', my_list=rows)
    return template


@app.route("/ongoing_rules")
def ongoing_rules():
    """Return ongoing_rules.html."""
    list_arr = execute_request(QUERY[mn()], 'fetchall')
    if (list_arr is None):
        list_arr = []

    rows = []
    for row in list_arr:
        id = row[0]
        day_number = row[1]
        branch_name = row[2]
        rule_name = row[3]
        time = row[4]
        minutes = row[5]
        active = row[6]
        rule_state = row[7]
        rows.append({'id': id, 'branch_name': branch_name, 'dow': day_number, 'rule_name': rule_name,
                    'time': time, 'minutest': minutes, 'active': active, 'rule_state': rule_state})

    template = render_template('ongoing_rules.html', my_list=rows)
    return template


@app.route("/add_ongoing_rule")
def add_ongoing_rule():
    """User can add ongoing rule from ui."""
    branch_id = int(request.args.get('branch_id'))
    time_min = int(request.args.get('time_min'))
    time_start = request.args.get('datetime_start')
    dow = int(request.args.get('dow'))

    update_db_request(QUERY[mn()].format(dow, branch_id, 1, time_start, time_min))
    update_all_rules()
    template = ongoing_rules_table()
    send_message('ongoind_rules_update', {'data': template})
    return template


@app.route("/remove_ongoing_rule")
def remove_ongoing_rule():
    """User can remove ongoing rule from ui."""
    id = int(request.args.get('id'))
    update_db_request(QUERY[mn()].format(id))
    update_all_rules()
    template = ongoing_rules_table()
    send_message('ongoind_rules_update', {'data': template})
    return template


@app.route("/edit_ongoing_rule")
def edit_ongoing_rule():
    """User can edit ongoing rule from ui."""
    id = int(request.args.get('id'))
    # update_db_request(QUERY[mn()].format(id))
    update_all_rules()
    template = ongoing_rules_table()
    send_message('ongoind_rules_update', {'data': template})
    return template


@app.route("/activate_ongoing_rule")
def activate_ongoing_rule():
    """User can activate ongoing rule from ui."""
    id = int(request.args.get('id'))
    update_db_request(QUERY[mn()].format(id))
    update_all_rules()
    template = ongoing_rules_table()
    send_message('ongoind_rules_update', {'data': template})
    return template


@app.route("/deactivate_ongoing_rule")
def deactivate_ongoing_rule():
    """User can deactivate ongoing rule from ui."""
    id = int(request.args.get('id'))
    update_db_request(QUERY[mn()].format(id))
    update_all_rules()
    template = ongoing_rules_table()
    send_message('ongoind_rules_update', {'data': template})
    return template


@app.route("/get_timetable_list")
def get_timetable_list():
    """Blablbal."""
    if 'days' in request.args:
        days = int(request.args.get('days'))
        return get_table_body_only(QUERY[mn() + '_1'].format(days))

    if 'before' in request.args and 'after' in request.args:
        before = int(request.args.get('before'))
        after = int(request.args.get('after'))
        return get_table_body_only(QUERY[mn() + '_2'].format(before, after))


@app.route('/arduino_status', methods=['GET'])
def arduino_status():
    """Return status of arduino relay."""
    try:
        response_status = requests.get(url=ARDUINO_IP + '/branch_status')
    except requests.exceptions.RequestException as e:
        logging.error(e)
        logging.error("Can't get arduino status. Exception occured")
        abort(404)

    return (response_status.text, response_status.status_code)


@app.route('/activate_branch', methods=['GET'])
def activate_branch():
    """Blablbal."""
    mode = request.args.get('mode')
    if (mode is None):
        logging.error("no 'mode' parameter passed")
        abort(404)

    if (mode == 'single'):
        id = int(request.args.get('id'))
        time_min = int(request.args.get('time_min'))
    elif (mode == 'interval'):
        id = int(request.args.get('id'))
        time_min = int(request.args.get('time_min'))
        time_wait = int(request.args.get('time_wait'))
        num_of_intervals = int(request.args.get('quantity'))
    elif (mode == 'auto'):
        id = int(request.args.get('id'))
        # time_min = int(request.args.get('time_min')) || 25
        time_min = 25
    else:
        logging.error("incorrect mode parameter passed: {0}".format(mode))
        abort(404)

    try:
        payload = (('branch_id', id), ('branch_alert', time_min + 2))
        response_on = requests.get(url=ARDUINO_IP + '/branch_on', params=payload)
        send_message('branch_status', {'data': response_on.text})
    except Exception as e:
        logging.error(e)
        logging.error("Can't turn on branch id={0}. Exception occured".format(id))
        abort(404)

    # needs to be executed in both cases single and interval, but in in auto
    if (mode != 'auto'):
        interval_id = str(uuid.uuid4())
        now = datetime.datetime.now()
        stop_time = now + datetime.timedelta(minutes=time_min)

        update_db_request(QUERY[mn() + '_1'].format(id, 1, 2, now.date(), now, interval_id))
        lastid = update_db_request(QUERY[mn() + '_1'].format(id, 2, 1, now.date(), stop_time, interval_id))
        logging.debug("lastid:{0}".format(lastid))

        res = execute_request(QUERY[mn() + '_2'].format(lastid), 'fetchone')
        logging.debug("res:{0}".format(res[0]))

        RULES_FOR_BRANCHES[id] = {'id': res[0], 'line_id': res[1], 'rule_id': res[2], 'timer': res[3], 'interval_id': res[4]}
        logging.info("Rule '{0}' added".format(str(RULES_FOR_BRANCHES[id])))

    if (mode == 'interval'):
        # first interval is already added
        for x in range(2, num_of_intervals + 1):
            start_time = stop_time + datetime.timedelta(minutes=time_wait)
            stop_time = start_time + datetime.timedelta(minutes=time_min)
            update_db_request(QUERY[mn() + '_1'].format(id, 1, 1, now.date(), start_time, interval_id))
            update_db_request(QUERY[mn() + '_1'].format(id, 2, 1, now.date(), stop_time, interval_id))
            logging.info("Start time: {0}. Stop time: {1} added to database".format(str(start_time), str(stop_time)))

    if (mode == 'auto'):
        logging.info("Branch '{0}' activated from rules service".format(id))
    else:
        logging.info("Branch '{0}' activated manually".format(id))

    return (response_on.text, response_on.status_code)


@app.route('/deactivate_branch', methods=['GET'])
def deactivate_branch():
    """Route is used to disable branch."""
    """Can be executed manaully - row will be added to database
    or with rules service - no new row will be added to database"""
    id = int(request.args.get('id'))
    mode = request.args.get('mode')
    if (mode is None):
        logging.error("no 'mode' parameter passed")
        abort(404)

    try:
        response_off = requests.get(url=ARDUINO_IP + '/branch_off', params={"branch_id": id})
    except requests.exceptions.RequestException as e:
        logging.error(e.inspect)
        logging.error("Can't turn on branch id={0}. Exception occured".format(id))
        abort(404)

    if (mode == 'manually'):
        now = datetime.datetime.now()
        if RULES_FOR_BRANCHES[id] is not None:
            update_db_request(QUERY[mn() + '_1'].format(RULES_FOR_BRANCHES[id]['interval_id']))
        else:
            update_db_request(QUERY[mn() + '_2'].format(id, 2, 4, now.date(), now, None))

        RULES_FOR_BRANCHES[id] = get_next_active_rule(id)
        logging.info("Rule '{0}' added".format(str(RULES_FOR_BRANCHES[id])))

        logging.info("Branch '{0}' deactivated manually".format(id))
    else:
        logging.info('No new entries is added to database.')

    return (response_off.text, response_off.status_code)


@app.route("/weather")
def weather():
    """Blablbal."""
    url = 'http://apidev.accuweather.com/currentconditions/v1/360247.json?language=en&apikey=hoArfRosT1215'
    response = requests.get(url=url)
    json_data = json.loads(response.text)
    return jsonify(
        temperature=str(json_data[0]['Temperature']['Metric']['Value'])
    )


@app.route("/sensors")
def sensors():
    """Blablbal."""
    return app.send_static_file('sensors.html')


@app.after_request
def after_request(response):
    """Blablbal."""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response


if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=7543, debug=False)
