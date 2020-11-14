from mythic.config import config
from mythic.logger import logger
from mythic.telegram import TelegramBot
from mythic.wowapi import WowApi
from mythic.pet.db import PetDatabase

from apscheduler.schedulers.blocking import BlockingScheduler
import base64
from datetime import datetime
import hashlib
import json
import requests
import textwrap
import traceback

class CollectPetBot(object):
    def __init__(self):
        self.api = WowApi("kr", config.BATTLENET_API_ID, config.BATTLENET_API_SECRET)

        self.telegram = TelegramBot()
        self.telegram.send_message(text='app start')

        self.db = PetDatabase(config.MONGO_HOST, config.MONGO_DATABASE)

        self.init()

    def init(self):
        realms = self.api.bn_request("/data/wow/realm/index?" + self.api.postfix_parameter("dynamic"))
        self.realms = realms['realms']

    def update_pet_list(self, realm, character_name):
        pets = self.api.bn_request(f"/profile/wow/character/{realm}/{character_name}/collections/pets?" + self.api.postfix_parameter("profile"))
        logger.info(json.dumps(pets))
        if pets is None:
            return

        if 'pets' not in pets:
            return
        
        #pets = pets['pets']
        pets['_id'] = {
            'realm': realm,
            'character_name': character_name
        }

        if not self.db.insert_pet(pets):
            self.db.update_pet(pets, {'pets': pets['pets']})

    def bot_work(self):
        self.update_pet_list('hyjal', '터널기사')
        return

    def start(self, **kwargs):
        sched = BlockingScheduler()
        sched.add_job(self.bot_work,'cron', **kwargs)
        sched.start()

if __name__ == '__main__':
    #CollectPetBot().start(hour='0')
    CollectPetBot().bot_work()
