from mythic.config import config
from mythic.logger import logger
from mythic.bots.base import BaseBot

from datetime import datetime

class CollectPlayerBot(BaseBot):
    def __init__(self, mythic_bot):
        super().__init__()
        self.init()

        if __name__ == '__main__':
            self.telegram.send_message(text='player app start')

        self.mythic_bot = mythic_bot
        self.mythic_bot.db = self.db

    def init(self):
        pass

    def update_player(self, realm, character_name):
        realm_slug = self.db.find_realm_slug(realm)
        self.update_player_runs(realm, realm_slug, character_name)
        self.update_player_talent(realm, realm_slug, character_name)

    def update_player_runs(self, realm, realm_slug, character_name):
        profile = self.api.bn_request(f"/profile/wow/character/{realm_slug}/{character_name}/mythic-keystone-profile", token=True, namespace="profile")
        if isinstance(profile, int):
            return
        if 'seasons' not in profile:
            return
        for season in profile['seasons']:
            href = season['key']['href']
            season_res = self.api.bn_request(href, token=True)
            if season_res['season']['id'] != self.mythic_bot.current_season:
                continue
            if 'best_runs' not in season_res:
                return
            for run in season_res['best_runs']:
                board = {
                    'period': self.db.find_period(timestamp=run['completed_timestamp'])['period']
                }
                
                for mem in run['members']:
                    mem['profile'] = mem['character']

                self.mythic_bot.insert_record(board, run, run['dungeon']['id'])
                             
    def update_player_talent(self, realm, realm_slug, character_name):
        talents = self.api.bn_request(f"/profile/wow/character/{realm_slug}/{character_name}/specializations", token=True, namespace="profile")
        if talents is None:
            return
        if isinstance(talents, int):
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
                if 'selected_class_talents' not in loadout:
                    continue
                if 'selected_spec_talents' not in loadout:
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
                        'talent_rank': ctal['rank'],
                        'talent_name': ctal['tooltip']['talent']['name']
                    })
                for stal in loadout['selected_spec_talents']:
                    slots.append({
                        'talent_code': talent_code,
                        'talent_id': stal['id'],
                        'talent_rank': stal['rank'],
                        'talent_name': stal['tooltip']['talent']['name']
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
            update_cnt = 0
            while now_ts2 - now_ts < 300_000:
                p = self.db.next_update_player()
                if p is None:
                    break

                self.update_player(p['realm'], p['name'])
                now_ts2 = int(datetime.now().timestamp() * 1000)
                update_cnt += 1

            now_ts2 = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {now_ts2 - now_ts} ms, {update_cnt} player updated.')
        except Exception as e:
            self.print_error(e)

        finally:
            self.db.disconnect()
