from mythic.config import config
from mythic.logger import logger
from mythic.bots.base import BaseBot

from datetime import datetime

class CollectPlayerBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.init()

        if __name__ == '__main__':
            self.telegram.send_message(text='player app start')

    def init(self):
        pass

    def update_player(self, realm, character_name):
        realm_slug = self.db.find_realm_slug(realm)
        talents = self.api.bn_request(f"/profile/wow/character/{realm_slug}/{character_name}/specializations", token=True, namespace="profile")
        if talents is None:
            return
        if type(talents) is int:
            self.db.update_player_talent({
                'player_realm': realm,
                'player_name': character_name,
                'spec_id': 0,
                'talent_code': '',
                'last_update_ts': int(datetime.now().timestamp() * 1000)
            }, [])
            return
        
        for spec in talents['specializations']:
            spec_id = spec['specialization']['id']
            for loadout in spec['loadouts']:
                if not loadout['is_active']:
                    continue

                talent_code = loadout['talent_loadout_code']
                talent = {
                    'player_realm': realm,
                    'player_name': character_name,
                    'spec_id': spec_id,
                    'talent_code': talent_code,
                    'last_update_ts': int(datetime.now().timestamp() * 1000)
                }
                slots = []
                for ctal in loadout['selected_class_talents']:
                    slots.append({
                        'talent_code': talent_code,
                        'talent_id': ctal['id'],
                        'talent_rank': ctal['rank']
                    })
                for stal in loadout['selected_spec_talents']:
                    slots.append({
                        'talent_code': talent_code,
                        'talent_id': stal['id'],
                        'talent_rank': stal['rank']
                    })
                
                self.db.update_player_talent(talent, slots)

        # pets = self.api.bn_request(f"/profile/wow/character/{realm}/{character_name}/collections/pets", token=True, namespace="profile")
        # if pets is not None and 'pets' in pets:
        #     self.db.update_player(player, {'pets': pets['pets']})

        # mounts = self.api.bn_request(f"/profile/wow/character/{realm}/{character_name}/collections/mounts", token=True, namespace="profile")
        # if mounts is not None and 'mounts' in mounts:
        #     self.db.update_player(player, {'mounts': mounts['mounts']})

    def on_schedule(self):
        try:
            self.db.connect()

            now_ts = int(datetime.now().timestamp() * 1000)

            now_ts2 = now_ts
            while now_ts2 - now_ts < 300_000:
                p = self.db.next_update_player()
                if p is None:
                    break

                self.update_player(p['realm'], p['name'])
                now_ts2 = int(datetime.now().timestamp() * 1000)

            now_ts2 = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {now_ts2 - now_ts} ms')
        except Exception as e:
            self.print_error(e)

        finally:
            self.db.disconnect()

if __name__ == '__main__':
    CollectPlayerBot().on_schedule()
