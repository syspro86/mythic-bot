from mythic.config import config
from mythic.logger import logger
from mythic.bots.base import BaseBot

from datetime import datetime

class CollectIndexBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.init()

        if __name__ == '__main__':
            self.telegram.send_message(text='index app start')

    def init(self):
        pass

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

    def on_schedule(self):
        try:
            now_ts = int(datetime.now().timestamp() * 1000)

            self.update_mount_index()
            self.update_pet_index()

            now_ts2 = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {now_ts2 - now_ts} ms')
        except Exception as e:
            self.print_error(e)

if __name__ == '__main__':
    CollectIndexBot().on_schedule()
