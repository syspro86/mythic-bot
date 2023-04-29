from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_session import Session
from functools import wraps
from mythic.config import config
from mythic.bots.base import BaseBot
from datetime import datetime
import redis

app = Flask(__name__, static_url_path="", static_folder="static")
if config.REDIS_URL is not None and config.SESSION_SECRET is not None:
    app.secret_key = config.SESSION_SECRET
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_REDIS'] = redis.from_url(config.REDIS_URL)
    server_session = Session(app)


class WebUtil(BaseBot):
    def __init__(self):
        super().__init__()

        try:
            self.db.connect()
            self.realms = self.db.find_all_realm()
            self.realm_name = {}
            self.realm_name_to_slug = {}
            for realm in self.realms:
                realm_id = realm['realm_id']
                self.realm_name[realm_id] = realm['realm_name']
                self.realm_name_to_slug[realm['realm_name']] = realm['realm_slug']
        finally:
            self.db.disconnect()

    def get_current_period(self):
        try:
            self.db.connect()
            now_ts = int(datetime.now().timestamp() * 1000)
            period = self.db.find_period(timestamp=now_ts)
            return period['period']
        finally:
            self.db.disconnect()

util = WebUtil()


def using_db(rt):
    @wraps(rt)
    def wrapper(*args, **kwargs):
        try:
            util.db.connect()
            return rt(*args, **kwargs)
        finally:
            util.db.disconnect()

    return wrapper


@app.route('/')
def index_page():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/form/init')
def form_init():
    return jsonify({
        'region': "kr",
        'realms': util.realm_name,
        'dungeons': util.dungeon_cache,
        'specs': util.specs,
    })


@app.route('/form/realms')
def form_realms():
    return jsonify(util.realm_name)


@app.route('/user/<session>')
@using_db
def user_session(session):
    users = util.db.find_botusers(session=session)
    if len(users) > 0:
        return jsonify(users[0])
    else:
        return None


@app.route('/user/<session>/char')
@using_db
def user_session_char(session):
    users = util.db.find_botusers(session=session)
    if len(users) > 0:
        return jsonify(users[0]['characters'])
    else:
        return None


@app.route('/user/<session>/comments')
@using_db
def user_session_comments(session):
    users = util.db.find_botusers(session=session)
    if len(users) > 0:
        return jsonify(users[0]['userComments'])
    else:
        return None


@app.route('/char/profile/<realm>/<name>')
def char_profile_realm_name(realm, name):
    realm = util.realm_name_to_slug[realm]
    profile = util.api.bn_request(
        f'/profile/wow/character/{realm}/{name}', token=True, namespace="profile")
    media = util.api.bn_request(
        f'/profile/wow/character/{realm}/{name}/character-media', token=True, namespace="profile")
    if profile is not None:
        if media is not None:
            profile['avatar_url'] = list(
                filter(lambda r: r['key'] == 'avatar',   media['assets']))[0]['value']
            profile['inset_url'] = list(
                filter(lambda r: r['key'] == 'inset',    media['assets']))[0]['value']
            profile['main_url'] = list(
                filter(lambda r: r['key'] == 'main',     media['assets']))[0]['value']
            profile['main_raw_url'] = list(
                filter(lambda r: r['key'] == 'main-raw', media['assets']))[0]['value']
        return jsonify(profile)
    else:
        return jsonify({})


@app.route('/char/record/<realm>/<name>')
@using_db
def char_record_realm_name(realm, name):
    records = util.db.get_character_records(name, realm, 20)
    if len(records) > 0:
        records = sorted(
            records, key=lambda r: (-r['keystone_level'], -r['keystone_upgrade'], -r['duration']))
        return jsonify(records)
    else:
        return jsonify([])


@app.route('/char/weekly/<realm>/<name>')
@using_db
def char_weekly_realm_name(realm, name):
    records = util.db.get_weekly_record(name, realm, util.get_current_period())
    if len(records) > 0:
        records = sorted(
            records, key=lambda r: (-r['keystone_level'], -r['keystone_upgrade'], -r['duration']))
        return jsonify(records[0])
    else:
        return jsonify(None)


@app.route('/char/relation/<realm>/<name>/<run>')
@using_db
def char_relation_realm_name(realm, name, run):
    name = name[0:1].upper() + name[1:].lower()
    records = util.db.get_relation(name, realm, run)
    if len(records) > 0:
        records = list(
            filter(lambda r: r['name'] != name or r['realm'] != realm, records))
        return jsonify(records)
    else:
        return jsonify([])


@app.route('/char/mythic_rating/<realm>/<name>')
@using_db
def char_mythicrating_realm_name(realm, name):
    name = name[0:1].upper() + name[1:].lower()
    records = util.db.find_mythic_rating_list(realm, name)
    if len(records) > 0:
        periods = {}
        for r in records:
            if r['period'] not in periods:
                p = util.db.find_period(period=r['period'])
                periods[r['period']] = p['start_timestamp']
            r['timestamp'] = periods[r['period']]
        return jsonify(records)
    else:
        return jsonify([])
