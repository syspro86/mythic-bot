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

        self.telegram = TelegramBot(polling=False)
        if __name__ == '__main__':
            self.telegram.send_message(text='app start')

        self.db = PetDatabase(config.MONGO_HOST, config.MONGO_DATABASE)

        self.init()

    def init(self):
        realms = self.api.bn_request("/data/wow/realm/index", token=True, namespace="dynamic")
        self.realms = realms['realms']

    def update_pet_index(self):
        pets = self.api.bn_request(F"/data/wow/pet/index", token=True, namespace="static")
        if pets is None or 'pets' not in pets:
            return

        pets = pets['pets']
        for pet in pets:
            changed = True
            _id = pet['id']
            pet_saved = self.db.find_pet(_id)
            if pet_saved is not None:
                pet = pet_saved
                changed = False

            if 'key' in pet:
                href = pet['key']['href']
                pet_detail = self.api.bn_request(href, token=True)
                if pet_detail is not None:
                    pet = pet_detail
                    changed = True

            if 'media' in pet and 'key' in pet['media']:
                media_href = pet['media']['key']['href']
                pet_media = self.api.bn_request(media_href, token=True)
                if pet_media is not None:
                    pet['media'] = pet_media
                    changed = True

            if changed:
                pet['_id'] = _id
                self.db.insert_pet(pet, upsert=True)

    def update_mount_index(self):
        mounts = self.api.bn_request(F"/data/wow/mount/index", token=True, namespace="static")
        if mounts is None or 'mounts' not in mounts:
            return

        mounts = mounts['mounts']
        for mount in mounts:
            changed = True
            _id = mount['id']
            mount_saved = self.db.find_mount(_id)
            if mount_saved is not None:
                mount = mount_saved
                changed = False

            if 'key' in mount:
                href = mount['key']['href']
                mount_detail = self.api.bn_request(href, token=True)
                if mount_detail is not None:
                    mount = mount_detail
                    changed = True

            if 'creature_displays' in mount:
                creature_displays = mount['creature_displays']
                for i in range(len(creature_displays)):
                    if 'key' in creature_displays[i]:
                        cd_href = creature_displays[i]['key']['href']
                        mount_media = self.api.bn_request(cd_href, token=True)
                        if mount_media is not None:
                            creature_displays[i] = mount_media
                            changed = True

            if changed:
                mount['_id'] = _id
                self.db.insert_mount(mount, upsert=True)

    def update_trainer(self, realm, character_name):
        pets = self.api.bn_request(f"/profile/wow/character/{realm}/{character_name}/collections/pets", token=True, namespace="profile")
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

        if not self.db.insert_trainer(pets):
            self.db.update_trainer(pets, {'pets': pets['pets']})

    def bot_work(self):
        try:
            now_ts = int(datetime.now().timestamp() * 1000)

            self.update_mount_index()
            self.update_pet_index()
            #self.update_trainer('hyjal', '터널기사')

            now_ts2 = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {now_ts2 - now_ts} ms')
        except Exception as e:
            traceback.print_exc()
            logger.info(e)

    def start(self, **kwargs):
        sched = BlockingScheduler()
        sched.add_job(self.bot_work,'cron', **kwargs)
        sched.start()

if __name__ == '__main__':
    #CollectPetBot().start(hour='0')
    CollectPetBot().bot_work()
