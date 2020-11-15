from flask import Flask, render_template
from mythic.config import MythicConfig
from mythic.logger import logger
from mythic.wowapi import WowApi
from mythic.auction.db import AuctionDatabase
from mythic.pet.db import PetDatabase

app = Flask(__name__, template_folder='../../templates', static_url_path='/../../static')

config = MythicConfig()
api = WowApi('kr', config.BATTLENET_API_ID, config.BATTLENET_API_SECRET)

@app.route('/')
def list_my_pets():
    db = PetDatabase(config.MONGO_HOST, config.MONGO_DATABASE)
    trainer = db.find_trainer({'realm': 'hyjal', 'character_name': '터널기사'})
    for p in trainer['pets']:
        pet = db.find_pet(p['species']['id'])
        p['detail'] = pet

    return render_template('index.html', pets=trainer['pets'])

@app.route('/missing')
def missing_pet():
    db = PetDatabase(config.MONGO_HOST, config.MONGO_DATABASE)
    import pymongo
    conn = pymongo.MongoClient(config.MONGO_HOST)
    db2 = conn[config.MONGO_DATABASE]
    
    missing = db2.auctions.aggregate([
        { '$match': { 'item.id': 82800 } },
        { '$group': { '_id': '$item.pet_species_id', 'min_buyout': { '$min': '$buyout' }, 'items': { '$push': { 'bid': '$bid', 'buyout': '$buyout', 'quantity': '$quantity'} } } },
        { '$sort': { 'min_buyout': 1 }},
        { '$lookup': { 'from': 'trainers',  'localField': '_id',  'foreignField': 'pets.species.id',  'as': 'owner' } },
        # { '$match': { 'owner._id': { '$not': { '$exists': { 'realm': 'hyjal',  'character_name': '터널기사' } } } } },
        ], allowDiskUse=True)

    missing = list(missing)

    for item in missing:
        pet_id = item['_id']
        pet = db.find_pet(pet_id)
        item['pet_detail'] = pet

        item['gold'] = int(item['min_buyout'] / 10000)
        item['silver'] = int(item['min_buyout'] / 100) % 100
        item['copper'] = int(item['min_buyout']) % 100
        item['items'] = sorted(item['items'], key=lambda r: r['buyout'])

    return render_template('auction.html', pet=missing)
