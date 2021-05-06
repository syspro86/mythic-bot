from mythic.config import config
from mythic.logger import logger
from mythic.bots.base import BaseBot

import base64
from datetime import datetime
import hashlib
import json
import requests
import textwrap

class MythicBot(BaseBot):
    def __init__(self):
        super().__init__()

        self.inserted_id_set = []
        self.realm_cache = {}
        self.spec_cache = {}
        self.dungeon_cache = {}
        self.end_timestamp = 0
        self.season = -1

        self.init_api(False)
        self.need_init = False

        if __name__ == '__main__':
            self.telegram.send_message(text='mythic app start')

    def init_api(self, force):

        realms = self.api.bn_request("/data/wow/realm/index", token=True, namespace="dynamic")
        self.realm_cache = {}
        for realm in realms['realms']:
            realm_id = realm['id']
            self.realm_cache[realm_id] = realm

        dungeons = self.api.bn_request("/data/wow/mythic-keystone/dungeon/index", token=True, namespace="dynamic")
        self.dungeon_cache = {}
        for dungeon in dungeons['dungeons']:
            dungeon_id = dungeon['id']
            d = self.api.bn_request(f"/data/wow/mythic-keystone/dungeon/{dungeon_id}", token=True, namespace="dynamic")
            self.dungeon_cache[dungeon_id] = d

        specs = self.api.bn_request("/data/wow/playable-specialization/index", token=True, namespace="static")
        self.spec_cache = {}
        for spec in specs['character_specializations']:
            spec_id = spec['id']
            spec = self.api.bn_request(f"/data/wow/playable-specialization/{spec_id}", token=True, namespace="static")
            self.spec_cache[spec_id] = spec

        seasons = self.api.bn_request("/data/wow/mythic-keystone/season/index", token=True, namespace="dynamic")
        self.current_season = seasons['current_season']['id']

        periods = self.api.bn_request("/data/wow/mythic-keystone/period/index", token=True, namespace="dynamic")
        self.period_ids = []
        for period in periods['periods']:
            period_id = period['id']
            self.period_ids.append(period_id)

        self.current_period = periods['current_period']['id']
        period_detail = self.api.bn_request(f"/data/wow/mythic-keystone/period/{self.current_period}", token=True, namespace="dynamic")
        self.end_timestamp = int(period_detail['end_timestamp'])
        end_timestamp_str = datetime.fromtimestamp(self.end_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"season: {self.current_season}, period: {self.current_period}, ends: {end_timestamp_str}")

        self.need_init = False

    def get_leaderboard(self, realm_id, dungeon_id, season, period):
        board = self.api.bn_request(f"/data/wow/connected-realm/{realm_id}/mythic-leaderboard/{dungeon_id}/period/{period}", token=True, namespace="dynamic")
        if board is not None and 'leading_groups' in board:
            for rec in board['leading_groups']:
                self.insert_record(board, rec, season, dungeon_id)

    def insert_record(self, board, rec, season, dungeon_id):
        record = {}
        # ranking = rec['ranking']
        duration = rec['duration']
        completed_timestamp = rec['completed_timestamp']
        keystone_level = rec['keystone_level']
        
        # map_name = board['map']['name']
        period = board['period']
        
        dungeon = self.dungeon_cache[dungeon_id]
        dungeon_name = dungeon['name']
        
        ts_str  = datetime.fromtimestamp(completed_timestamp / 1000).strftime('%Y-%m-%d_%H:%M:%S')
        ts_str2 = datetime.fromtimestamp(completed_timestamp / 1000).strftime('%Y-%m-%d %H:%M')
        
        record_id = f'{ts_str}_{dungeon_name}_{keystone_level}_{period}_{completed_timestamp}'
        record['_id'] = record_id
        if record_id in self.inserted_id_set:
            return

        record['season'] = season
        record['period'] = period
        record['dungeon_id'] = dungeon_id
        record['duration'] = duration
        record['completed_timestamp'] = completed_timestamp
        record['keystone_level'] = keystone_level
        record['keystone_upgrade'] = -1
        
        for ku in dungeon['keystone_upgrades']:
            if ku['qualifying_duration'] > duration:
                record['keystone_upgrade'] = max(record['keystone_upgrade'], ku['upgrade_level'])

        def convert_member(member):
            try:
                m = {}
                m['name'] = member['profile']['name']
                rid = member['profile']['realm']['id']
                m['realm'] = self.realm_cache[rid]['name']
                if 'specialization' in member:
                    m['spec'] = member['specialization']['id']
                    spec = m['spec']
                    spec = self.spec_cache[spec]
                    m['className'] = spec['playable_class']['name']
                    m['specName'] = spec['name']
                    m['role'] = spec['role']['type']
                else:
                    m['spec'] = -1
                    m['className'] = '알수없음'
                    m['specName'] = ''
                    m['role'] = 'UNKNOWN'
                return m
            except KeyError as e:
                logger.info(str(e))
                self.telegram.send_message(text=f'failed to convert member data {json.dumps(member)}')
                raise e
        record['members'] = map(convert_member, rec['members'])

        role_names = ['TANK', 'HEALER', 'DAMAGE', 'UNKNOWN']
        record['members'] = sorted(record['members'], key=lambda r: (role_names.index(r['role']), r['spec']))

        try:
            if self.db.insert_record(record):
                logger.info(f"new record = {record['_id']}")
                
                minute = int(record['duration'] / 60000)
                second = (int(record['duration'] / 1000) % 60)
                
                msg = f"{dungeon['name']}+{record['keystone_level']} ({ts_str2})\r\n"
                msg += f"({record['keystone_upgrade']}) "
                msg += f"{minute}분 {second}초"
                for member in record['members']:
                    msg += f"\r\n{member['name']}-{member['realm']}"
                    msg += f" ({member['specName']} {member['className']})"

                sent_botusers = []
                for member in record['members']:
                    full_name = f"{member['name']}-{member['realm']}"

                    for buser in self.db.find_botusers(full_name):
                        if buser['_id'] not in sent_botusers:
                            self.telegram.send_message(chat_id=buser['_id'], text=msg)
                            sent_botusers.append(buser['_id'])
                            # self.bot.send_message(text=msg)
                            logger.info(f"message sent! {buser['id']} {msg}")
        
            self.inserted_id_set.append(record_id)
        except Exception as e:
            self.print_error(e)

    def on_schedule(self):
        try:
            now_ts = int(datetime.now().timestamp() * 1000)
            if self.end_timestamp < now_ts:
                self.need_init = True

            if self.need_init:
                self.init_api(True)
                self.inserted_id_set = []
                
                # 현재 시간에 맞는 period가 없음.
                if self.end_timestamp < now_ts:
                    return

            for did in self.dungeon_cache.keys():
                for rid in self.realm_cache.keys():
                    self.get_leaderboard(rid, did, self.current_season, self.current_period)

            now_ts2 = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {now_ts2 - now_ts} ms')
        except Exception as e:
            self.need_init = True
            self.print_error(e)

            #self.telegram.send_message(text=str(e))
        except:
            self.need_init = True
            logger.info('unknown error')
            self.telegram.send_message(text='unknown error')
            raise

if __name__ == '__main__':
    MythicBot().on_schedule()
