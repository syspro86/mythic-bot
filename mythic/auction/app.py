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
    def __init__(self):
        self.api = WowApi('kr', config.BATTLENET_API_ID, config.BATTLENET_API_SECRET)
        realms = self.api.bn_request("/data/wow/realm/index", token=True, namespace="dynamic")
        self.realms = []
        for realm in realms['realms']:
            realm_id = realm['id']
            realm = self.api.bn_request(f"/data/wow/realm/{realm_id}", token=True, namespace="dynamic")
            if 'connected_realm' in realm:
                realm['connected_realm'] = self.api.bn_request(realm['connected_realm']['href'], token=True)
            self.realms.append(realm)

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
        trainer = db.find_trainer({'realm': realm, 'character_name': character_name})
        if trainer is None:
            CollectPetBot().update_trainer(realm, character_name)
            trainer = db.find_trainer({'realm': realm, 'character_name': character_name})

        if trainer is not None:
            for p in trainer['pets']:
                pet = db.find_pet(p['species']['id'])
                p['detail'] = pet

            pets = trainer['pets']

    return render_template('index.html', realms=util.realms, forms=forms, pets=pets)

@app.route('/missing', methods=['GET', 'POST'])
def missing_pet():
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
    
    pets = db2.auctions.aggregate([
        { '$match': { 'item.id': 82800 } },
        { '$group': { '_id': '$item.pet_species_id', 'min_buyout': { '$min': '$buyout' }, 'items': { '$push': { 'bid': '$bid', 'buyout': '$buyout', 'quantity': '$quantity'} } } },
        { '$sort': { 'min_buyout': 1 }},
        { '$lookup': { 'from': 'trainers',  'localField': '_id',  'foreignField': 'pets.species.id',  'as': 'owner' } },
        # { '$match': { 'owner._id': { '$not': { '$exists': { 'realm': realm, 'character_name': character_name } } } } },
        ], allowDiskUse=True)

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

    return render_template('auction.html', realms=util.realms, forms=forms, pet=pets)
