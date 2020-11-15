from flask import Flask, render_template, request
from mythic.config import MythicConfig
from mythic.logger import logger
from mythic.wowapi import WowApi
from mythic.auction.db import AuctionDatabase
from mythic.pet.db import PetDatabase
from mythic.pet.collect import CollectPetBot

app = Flask(__name__, template_folder='../../templates', static_url_path='/../../static')

config = MythicConfig()

class WebUtil:
    realms = []

    def __init__(self):
        self.api = WowApi('kr', config.BATTLENET_API_ID, config.BATTLENET_API_SECRET)

        if len(WebUtil.realms) == 0:
            realms = self.api.bn_request("/data/wow/realm/index", token=True, namespace="dynamic")
            WebUtil.realms = []
            for realm in realms['realms']:
                realm_id = realm['id']
                realm = self.api.bn_request(f"/data/wow/realm/{realm_id}", token=True, namespace="dynamic")
                if 'connected_realm' in realm:
                    realm['connected_realm'] = self.api.bn_request(realm['connected_realm']['href'], token=True)
                WebUtil.realms.append(realm)

util = WebUtil()

@app.route('/', methods=['GET', 'POST'])
def list_my_pets():
    db = PetDatabase(config.MONGO_HOST, config.MONGO_DATABASE)
    realm = request.form.get('realm')
    character_name = request.form.get('character_name')
    forms = {
        'realm': realm,
        'character_name': character_name
    }
    pets = []
    if realm is None or character_name is None:
        pass
    else:
        player = db.find_player({'realm': realm, 'character_name': character_name})
        if player is None:
            CollectPetBot().update_player(realm, character_name)
            player = db.find_player({'realm': realm, 'character_name': character_name})

        if player is not None:
            for p in player['pets']:
                pet = db.find_pet(p['species']['id'])
                p['detail'] = pet

            pets = player['pets']

    return render_template('index.html', realms=WebUtil.realms, forms=forms, pets=pets)

@app.route('/pet_auction', methods=['GET', 'POST'])
def pet_auction():
    db = PetDatabase(config.MONGO_HOST, config.MONGO_DATABASE)
    realm = request.form.get('realm')
    character_name = request.form.get('character_name')
    forms = {
        'realm': realm,
        'character_name': character_name
    }

    import pymongo
    conn = pymongo.MongoClient(config.MONGO_HOST)
    db2 = conn[config.MONGO_DATABASE]

    my_server = None
    if realm is not None:
        my_server = list(filter(lambda r: r['slug'] == realm, WebUtil.realms))
        if len(my_server) > 0:
            my_server = my_server[0]['connected_realm']
        else:
            my_server = None
    
    aggr = []
    if my_server is None:
        aggr.append({ '$match': { 'item.id': 82800 } })
    else:
        aggr.append({ '$match': { 'item.id': 82800, 'realm_id': my_server['id'] } })

    aggr.append({ '$group': { '_id': '$item.pet_species_id', 'min_buyout': { '$min': '$buyout' }, 'items': { '$push': { 'bid': '$bid', 'buyout': '$buyout', 'quantity': '$quantity'} } } })
    aggr.append({ '$sort': { 'min_buyout': 1 }})
    aggr.append({ '$lookup': { 'from': 'players',  'localField': '_id',  'foreignField': 'pets.species.id',  'as': 'owner' } })
    # aggr.append({ '$match': { 'owner._id': { '$not': { '$exists': { 'realm': realm, 'character_name': character_name } } } } })

    pets = db2.auctions.aggregate(aggr, allowDiskUse=True)

    pets = list(pets)

    for item in pets:
        pet_id = item['_id']
        pet = db.find_pet(pet_id)
        item['pet_detail'] = pet

        item['gold'] = int(item['min_buyout'] / 10000)
        item['silver'] = int(item['min_buyout'] / 100) % 100
        item['copper'] = int(item['min_buyout']) % 100
        item['items'] = sorted(item['items'], key=lambda r: r['buyout'])

        item['learned'] = False
        if realm is not None and character_name is not None:
            item['learned'] = len(list(filter(lambda r: r['_id']['realm'] == realm and r['_id']['character_name'] == character_name, item['owner']))) > 0

    return render_template('pet_auction.html', realms=WebUtil.realms, forms=forms, pet=pets)

@app.route('/mount_auction', methods=['GET', 'POST'])
def mount_auction():
    db = PetDatabase(config.MONGO_HOST, config.MONGO_DATABASE)
    realm = request.form.get('realm')
    character_name = request.form.get('character_name')
    forms = {
        'realm': realm,
        'character_name': character_name
    }

    import pymongo
    conn = pymongo.MongoClient(config.MONGO_HOST)
    db2 = conn[config.MONGO_DATABASE]

    my_server = None
    if realm is not None:
        my_server = list(filter(lambda r: r['slug'] == realm, WebUtil.realms))
        if len(my_server) > 0:
            my_server = my_server[0]['connected_realm']
        else:
            my_server = None
    
    aggr = []
    aggr.append({ '$lookup': { 'from': 'items',  'localField': 'item.id',  'foreignField': '_id',  'as': 'item_detail' } })
    aggr.append({ '$match': { 'item_detail': { '$elemMatch': { 'item_class.id': 15, 'item_subclass.id': 5 } }}})

    if my_server is not None:
        aggr.append({ '$match': { 'realm_id': my_server['id'] } })

    aggr.append({ '$group': { '_id': '$item.id', 'min_buyout': { '$min': '$buyout' }, 'item_detail': { '$first': '$item_detail' }, 'items': { '$push': { 'bid': '$bid', 'buyout': '$buyout', 'quantity': '$quantity'} } } })
    aggr.append({ '$sort': { 'min_buyout': 1 }})

    items = db2.auctions.aggregate(aggr, allowDiskUse=True)

    items = list(items)

    for item in items:
        item['item_detail'] = item['item_detail'][0] if len(item['item_detail']) > 0 else None
        item['gold'] = int(item['min_buyout'] / 10000)
        item['silver'] = int(item['min_buyout'] / 100) % 100
        item['copper'] = int(item['min_buyout']) % 100
        item['items'] = sorted(item['items'], key=lambda r: r['buyout'])

        item['learned'] = False
        #if realm is not None and character_name is not None:
        #    item['learned'] = len(list(filter(lambda r: r['_id']['realm'] == realm and r['_id']['character_name'] == character_name, item['owner']))) > 0

    return render_template('mount_auction.html', realms=WebUtil.realms, forms=forms, items=items)
