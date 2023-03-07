from flask import Flask, render_template, request, jsonify, send_from_directory
from functools import wraps
from mythic.config import MythicConfig
from mythic.logger import logger
from mythic.db import MythicDatabase
from mythic.wowapi import WowApi
from mythic.bots.base import BaseBot
from mythic.bots.player import CollectPlayerBot
from datetime import datetime

app = Flask(__name__, static_url_path="", static_folder="static")

config = MythicConfig()


class WebUtil(BaseBot):

    def __init__(self):
        super().__init__()
        self.realms = []
        self.realm_name = {}
        self.realm_name_to_slug = {}
        self.dungeon_cache = {}
        self.specs = {}

        realms = self.api.bn_request(
            "/data/wow/realm/index", token=True, namespace="dynamic")
        self.realms = []
        for realm in realms['realms']:
            realm_id = realm['id']
            realm = self.api.bn_request(
                f"/data/wow/realm/{realm_id}", token=True, namespace="dynamic")
            if 'connected_realm' in realm:
                realm['connected_realm'] = self.api.bn_request(
                    realm['connected_realm']['href'], token=True)
            self.realms.append(realm)
        for realm in realms['realms']:
            realm_id = realm['id']
            self.realm_name[realm_id] = realm['name']
            self.realm_name_to_slug[realm['name']] = realm['slug']

        dungeons = self.api.bn_request(
            "/data/wow/mythic-keystone/dungeon/index", token=True, namespace="dynamic")
        self.dungeon_cache = {}
        for dungeon in dungeons['dungeons']:
            dungeon_id = dungeon['id']
            d = self.api.bn_request(
                f"/data/wow/mythic-keystone/dungeon/{dungeon_id}", token=True, namespace="dynamic")
            self.dungeon_cache[dungeon_id] = d

        periods = self.api.bn_request(
            "/data/wow/mythic-keystone/period/index", token=True, namespace="dynamic")
        self.period_ids = []
        for period in periods['periods']:
            period_id = period['id']
            self.period_ids.append(period_id)

        self.current_period = periods['current_period']['id']
        period_detail = self.api.bn_request(
            f"/data/wow/mythic-keystone/period/{self.current_period}", token=True, namespace="dynamic")
        self.end_timestamp = int(period_detail['end_timestamp'])

        specs = self.api.bn_request(
            '/data/wow/playable-specialization/index', token=True, namespace="static")
        for spec in specs['character_specializations']:
            spec_id = spec["id"]
            spec = self.api.bn_request(
                f'/data/wow/playable-specialization/{spec_id}', token=True, namespace="static")
            self.specs[spec_id] = spec

    def get_current_period(self):
        now_ts = int(datetime.now().timestamp() * 1000)
        if self.end_timestamp < now_ts:
            periods = self.api.bn_request(
                "/data/wow/mythic-keystone/period/index", token=True, namespace="dynamic")
            period_ids = []
            for period in periods['periods']:
                period_id = period['id']
                period_ids.append(period_id)
            self.period_ids = period_ids

            self.current_period = periods['current_period']['id']
            period_detail = self.api.bn_request(
                f"/data/wow/mythic-keystone/period/{self.current_period}", token=True, namespace="dynamic")
            self.end_timestamp = int(period_detail['end_timestamp'])
        return self.current_period

    def pets(self, realm, character_name):
        my_server = list(filter(lambda r: r['slug'] == realm, self.realms))
        my_server = my_server[0]['connected_realm']

        player = self.db.find_player(
            {'realm': realm, 'character_name': character_name})
        if player is None:
            CollectPlayerBot().update_player(realm, character_name)
            player = self.db.find_player(
                {'realm': realm, 'character_name': character_name})

        if player is not None and 'pets' in player:
            pets = player['pets']
            pets = sorted(player['pets'], key=lambda r: r['species']['id'])
            pet_ids = list(set(map(lambda r: r['species']['id'], pets)))
            pet_details = self.db.list_doc('pets', {'_id': {'$in': pet_ids}})

            min_ts = int(datetime.now().timestamp() * 1000) - \
                1000 * 60 * 60 * 24 * 7  # 1week
            aggr = []
            aggr.append({'$match': {
                        'realm_id': my_server['id'], 'item.id': 82800, 'last_seen_ts': {'$gte': min_ts}}})
            aggr.append({'$match': {'item.pet_species_id': {'$in': pet_ids}}})
            aggr.append({'$group': {'_id': '$item.pet_species_id',
                        'min_buyout': {'$min': '$buyout'}}})
            auctions = self.db.aggregate('auctions', aggr)
            auctions = list(auctions)

            for p in pets:
                f = filter(lambda r: r['_id'] ==
                           p['species']['id'], pet_details)
                p['detail'] = next(f, None)
                f = filter(lambda r: r['_id'] == p['species']['id'], auctions)
                p['auction'] = next(f, {'min_buyout': 0})

            pets = reversed(
                sorted(pets, key=lambda r: r['auction']['min_buyout']))

            return pets
        return []

    def auction_pet_list(self, realm, character_name):
        my_server = list(filter(lambda r: r['slug'] == realm, self.realms))
        my_server = my_server[0]['connected_realm']

        min_ts = int(datetime.now().timestamp() * 1000) - \
            1000 * 60 * 30  # 30min

        aggr = []
        aggr.append({'$match': {
                    'realm_id': my_server['id'], 'item.id': 82800, 'last_seen_ts': {'$gte': min_ts}}})
        aggr.append({'$sort': {'item.pet_species_id': 1, 'buyout': 1}})
        aggr.append({'$group': {'_id': '$item.pet_species_id', 'min_buyout': {'$min': '$buyout'}, 'items': {
                    '$push': {'bid': '$bid', 'buyout': '$buyout', 'quantity': '$quantity'}}}})
        aggr.append({'$sort': {'min_buyout': 1}})

        # if character_name != '':
        #    aggr.append({ '$lookup': { 'from': 'players',  'localField': '_id',  'foreignField': 'pets.species.id',  'as': 'owner' } })
        # aggr.append({ '$match': { 'owner._id': { '$not': { '$exists': { 'realm': realm, 'character_name': character_name } } } } })

        pets = self.db.aggregate('auctions', aggr)
        pets = list(pets)

        pet_ids = list(map(lambda r: r['_id'], pets))
        pet_details = self.db.list_doc('pets', {'_id': {'$in': pet_ids}})

        player = None
        if character_name != '':
            player = self.db.find_player(
                {'realm': realm, 'character_name': character_name})
            if player is not None and 'pets' not in player:
                player = None

        for item in pets:
            pet_id = item['_id']
            f = filter(lambda r: r['_id'] == pet_id, pet_details)
            item['pet_detail'] = next(f, None)

            item['gold'] = int(item['min_buyout'] / 10000)
            item['silver'] = int(item['min_buyout'] / 100) % 100
            item['copper'] = int(item['min_buyout']) % 100
            # item['items'] = sorted(item['items'], key=lambda r: (r['buyout'] if 'buyout' in r else 0, r['bid'] if 'bid' in r else 0))

            item['learned'] = False
            if player != None:
                item['learned'] = len(
                    list(filter(lambda r: r['species']['id'] == pet_id, player['pets']))) > 0

        return pets

    def auction_mount_list(self, realm, character_name):
        my_server = list(filter(lambda r: r['slug'] == realm, self.realms))
        my_server = my_server[0]['connected_realm']

        min_ts = int(datetime.now().timestamp() * 1000) - \
            1000 * 60 * 30  # 30min

        aggr = []
        aggr.append(
            {'$match': {'realm_id': my_server['id'], 'last_seen_ts': {'$gte': min_ts}}})
        aggr.append({'$lookup': {'from': 'items',  'localField': 'item.id',
                    'foreignField': '_id',  'as': 'item_detail'}})
        aggr.append({'$match': {'item_detail': {'$elemMatch': {
                    'item_class.id': 15, 'item_subclass.id': 5}}}})

        aggr.append({'$group': {'_id': '$item.id', 'min_buyout': {'$min': '$buyout'}, 'item_detail': {
                    '$first': '$item_detail'}, 'items': {'$push': {'bid': '$bid', 'buyout': '$buyout', 'quantity': '$quantity'}}}})
        aggr.append({'$sort': {'min_buyout': 1}})

        items = self.db.aggregate('auctions', aggr)
        items = list(items)

        #items_ids = list(map(lambda r: r['_id'], items))
        #items_details = self.db.list_doc('mounts', { '_id': { '$in': items_ids } })

        #player = None
        # if character_name != '':
        #    player = self.db.find_player({ 'realm': realm, 'character_name': character_name})
        #    if player is not None and 'mounts' not in player:
        #        player = None

        for item in items:
            item['item_detail'] = item['item_detail'][0] if len(
                item['item_detail']) > 0 else None
            item['gold'] = int(item['min_buyout'] / 10000)
            item['silver'] = int(item['min_buyout'] / 100) % 100
            item['copper'] = int(item['min_buyout']) % 100
            # item['items'] = sorted(item['items'], key=lambda r: r['buyout'])

            item['learned'] = False
            # if player != None:
            #    item['learned'] = len(list(filter(lambda r: r['mount']['id'] == item['_id'], player['mounts']))) > 0

        return items


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


@app.route('/char/mythic_rating/<realm>/<name>/<period>')
@using_db
def char_mythicrating_realm_name(realm, name, period):
    name = name[0:1].upper() + name[1:].lower()
    records = util.db.find_mythic_rating(realm, name, int(period))
    if len(records) > 0:
        return jsonify(records)
    else:
        return jsonify([])


@app.route('/my_pet', methods=['GET', 'POST'])
@using_db
def list_my_pets():
    realm = request.form.get('realm')
    character_name = request.form.get('character_name')
    realm = '' if realm is None else realm
    character_name = '' if character_name is None else character_name.lower()
    forms = {
        'realm': realm,
        'character_name': character_name
    }

    pets = []
    if realm == '' or character_name == '':
        pass
    else:
        pets = util.pets(realm, character_name)

    return render_template('my_pet.html', realms=util.realms, forms=forms, pets=pets)


@app.route('/pet_auction', methods=['GET', 'POST'])
@using_db
def pet_auction():
    realm = request.form.get('realm')
    character_name = request.form.get('character_name')
    realm = '' if realm is None else realm
    character_name = '' if character_name is None else character_name.lower()
    forms = {
        'realm': realm,
        'character_name': character_name
    }

    pets = util.auction_pet_list(realm, character_name)
    return render_template('pet_auction.html', realms=util.realms, forms=forms, pet=pets)


@app.route('/mount_auction', methods=['GET', 'POST'])
@using_db
def mount_auction():
    realm = request.form.get('realm')
    character_name = request.form.get('character_name')
    forms = {
        'realm': realm,
        'character_name': character_name
    }

    items = util.auction_mount_list(realm, character_name)
    return render_template('mount_auction.html', realms=util.realms, forms=forms, items=items)
