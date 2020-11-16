from flask import Flask, render_template, request
from mythic.config import MythicConfig
from mythic.logger import logger
from mythic.db import MythicDatabase
from mythic.wowapi import WowApi
from mythic.bots.base import BaseBot
from mythic.bots.player import CollectPlayerBot

app = Flask(__name__)

config = MythicConfig()

class WebUtil(BaseBot):

    def __init__(self):
        super().__init__()
        self.realms = []

        realms = self.api.bn_request("/data/wow/realm/index", token=True, namespace="dynamic")
        self.realms = []
        for realm in realms['realms']:
            realm_id = realm['id']
            realm = self.api.bn_request(f"/data/wow/realm/{realm_id}", token=True, namespace="dynamic")
            if 'connected_realm' in realm:
                realm['connected_realm'] = self.api.bn_request(realm['connected_realm']['href'], token=True)
            self.realms.append(realm)

    def pets(self, realm, character_name):
        player = self.db.find_player({'realm': realm, 'character_name': character_name})
        if player is None:
            CollectPlayerBot().update_player(realm, character_name)
            player = self.db.find_player({'realm': realm, 'character_name': character_name})

        if player is not None and 'pets' in player:
            pets = player['pets']
            pet_ids = list(map(lambda r: r['species']['id'], pets))
            pet_details = self.db.list_doc('pets', { '_id': { '$in': pet_ids } })

            for p in player['pets']:
                f = filter(lambda r: r['_id'] == p['species']['id'], pet_details)
                p['detail'] = next(f, None)

            pets = player['pets']
            return pets
        return []

    def auction_pet_list(self, realm, character_name):
        my_server = list(filter(lambda r: r['slug'] == realm, self.realms))
        my_server = my_server[0]['connected_realm']
        
        aggr = []
        aggr.append({ '$match': { 'realm_id': my_server['id'], 'item.id': 82800 } })
        aggr.append({ '$sort': { 'item.pet_species_id':1, 'buyout': 1 } })
        aggr.append({ '$group': { '_id': '$item.pet_species_id', 'min_buyout': { '$min': '$buyout' }, 'items': { '$push': { 'bid': '$bid', 'buyout': '$buyout', 'quantity': '$quantity'} } } })
        aggr.append({ '$sort': { 'min_buyout': 1 }})

        #if character_name != '':
        #    aggr.append({ '$lookup': { 'from': 'players',  'localField': '_id',  'foreignField': 'pets.species.id',  'as': 'owner' } })
        # aggr.append({ '$match': { 'owner._id': { '$not': { '$exists': { 'realm': realm, 'character_name': character_name } } } } })

        pets = self.db.aggregate('auctions', aggr)
        pets = list(pets)

        pet_ids = list(map(lambda r: r['_id'], pets))
        pet_details = self.db.list_doc('pets', { '_id': { '$in': pet_ids } })

        player = None
        if character_name != '':
            player = self.db.find_player({ 'realm': realm, 'character_name': character_name})
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
                item['learned'] = len(list(filter(lambda r: r['species']['id'] == pet_id, player['pets']))) > 0

        return pets

    def auction_mount_list(self, realm, character_name):
        my_server = list(filter(lambda r: r['slug'] == realm, self.realms))
        my_server = my_server[0]['connected_realm']
        
        aggr = []
        aggr.append({ '$match': { 'realm_id': my_server['id'] } })
        aggr.append({ '$lookup': { 'from': 'items',  'localField': 'item.id',  'foreignField': '_id',  'as': 'item_detail' } })
        aggr.append({ '$match': { 'item_detail': { '$elemMatch': { 'item_class.id': 15, 'item_subclass.id': 5 } } } })

        aggr.append({ '$group': { '_id': '$item.id', 'min_buyout': { '$min': '$buyout' }, 'item_detail': { '$first': '$item_detail' }, 'items': { '$push': { 'bid': '$bid', 'buyout': '$buyout', 'quantity': '$quantity'} } } })
        aggr.append({ '$sort': { 'min_buyout': 1 }})

        items = self.db.aggregate('auctions', aggr)
        items = list(items)

        for item in items:
            item['item_detail'] = item['item_detail'][0] if len(item['item_detail']) > 0 else None
            item['gold'] = int(item['min_buyout'] / 10000)
            item['silver'] = int(item['min_buyout'] / 100) % 100
            item['copper'] = int(item['min_buyout']) % 100
            # item['items'] = sorted(item['items'], key=lambda r: r['buyout'])

            item['learned'] = False
            #if realm is not None and character_name is not None:
            #    item['learned'] = len(list(filter(lambda r: r['_id']['realm'] == realm and r['_id']['character_name'] == character_name, item['owner']))) > 0

        return items

util = WebUtil()

@app.route('/', methods=['GET', 'POST'])
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

    return render_template('index.html', realms=util.realms, forms=forms, pets=pets)

@app.route('/pet_auction', methods=['GET', 'POST'])
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
def mount_auction():
    db = MythicDatabase(config.MONGO_HOST, config.MONGO_DATABASE)
    realm = request.form.get('realm')
    character_name = request.form.get('character_name')
    forms = {
        'realm': realm,
        'character_name': character_name
    }

    items = util.auction_mount_list(realm, character_name)
    return render_template('mount_auction.html', realms=util.realms, forms=forms, items=items)
