from mythic.config import config
from mythic.logger import logger
from mythic.telegram import TelegramBot
from mythic.wowapi import WowApi
from mythic.leaderboard.db import MythicDatabase

from apscheduler.schedulers.blocking import BlockingScheduler
import base64
from datetime import datetime
import hashlib
import json
import requests
import textwrap
import traceback

class MythicBot(object):
    def __init__(self):
        self.api = WowApi("kr", config.BATTLENET_API_ID, config.BATTLENET_API_SECRET)

        self.inserted_id_set = []
        self.realm_cache = {}
        self.spec_cache = {}
        self.dungeon_cache = {}
        self.end_timestamp = 0
        self.season = -1

        self.init_api(False)
        self.need_init = False

        self.telegram = TelegramBot()
        self.telegram.add_callback(self.on_telegram_message)
        self.telegram.send_message(text='app start')

        self.db = MythicDatabase(config.MONGO_HOST, config.MONGO_DATABASE)

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
            traceback.print_exc()
            logger.info(e)
            pass

    def on_telegram_message(self, chat_id, message):
        if message == '/me':
            self.on_telegram_message_me(chat_id)

        elif message == "/주차" or message == "/report":
            users = self.db.find_botusers(chat_id=chat_id)

        elif message.startswith("/add ") or message.startswith("/추가 "):
            char_name = str(message).split(' ', 2)[1]
            if len(char_name) > 0:
                char_name = char_name[0:1].upper() + char_name[1:].lower()
                users = self.db.find_botusers(chat_id=chat_id)
                if len(users) > 0:
                    user = users[0]
                    if 'characters' not in user:
                        user['characters'] = []
                    if char_name not in user['characters']:
                        user['characters'].append(char_name)
                        self.db.save_botuser(user)
                        self.telegram.send_message(chat_id=chat_id, text=f'{char_name} 추가되었습니다.')
                else:
                    user = {
                        '_id': str(chat_id),
                        'characters': [ char_name ]
                    }
                    self.db.save_botuser(user)
                    self.telegram.send_message(chat_id=chat_id, text=f'{char_name} 추가되었습니다.')

        elif message.startswith("/remove ") or message.startswith("/삭제 "):
            char_name = str(message).split(' ', 2)[1]
            if len(char_name) > 0:
                char_name = char_name[0:1].upper() + char_name[1:].lower()
                users = self.db.find_botusers(chat_id=chat_id)
                if len(users) > 0:
                    user = users[0]
                    if 'characters' in user and char_name in user['characters']:
                        user['characters'].remove(char_name)
                        self.db.save_botuser(user)
                        self.telegram.send_message(chat_id=chat_id, text=f'{char_name} 삭제되었습니다.')

        else:
            char_name = message.strip()
            if len(char_name) > 0:
                self.on_telegram_message_find(chat_id, char_name)

    def on_telegram_message_me(self, chat_id):
        users = self.db.find_botusers(chat_id=chat_id)
        user = None
        if len(users) == 0:
            user = { '_id': str(chat_id), 'characters': [] }
            self.db.save_botuser(user, upsert=True)
        else:
            user = users[0]

        self.telegram.send_message(chat_id=chat_id, text=json.dumps(user['characters'], ensure_ascii=False))
        
        if 'webSessionId' not in user:
            sid = f'{config.HASH_SALT_PREFIX}{chat_id}{config.HASH_SALT_SUFFIX}'

            m = hashlib.new('sha256')
            m.update(sid.encode())
            hash256 = m.digest()
            sid = base64.b64encode(hash256).decode()
            sid = sid.replace('+', '-').replace('/', '_').replace("=", "")

            user['webSessionId'] = sid
            self.db.save_botuser(user)

        self.telegram.send_message(chat_id=chat_id, text=f"{config.WEL_UI_URL}{user['webSessionId']}")

    def on_telegram_message_find(self, chat_id, char_name):
        realms = []
        if char_name.find('-') > 0:
            realms.append(char_name[char_name.find('-')+1:])
            char_name = char_name[0:char_name.find('-')]
            char_name = char_name[0:1].upper() + char_name[1:].lower()
        else:
            char_name = char_name[0:1].upper() + char_name[1:].lower()
            realms = self.db.find_characters(char_name)

        if len(realms) == 0:
            self.telegram.send_message(chat_id=chat_id, text=f'{char_name} 캐릭터가 없습니다.')

        else:
            for realm in realms:
                records = list(self.db.find_records(char_name, realm, limit=10))

                if len(records) == 0:
                    self.telegram.send_message(chat_id=chat_id, text=f'{char_name}-{realm} 쐐기 데이터가 없습니다.')
                
                else:
                    msg = ''
                    for record in records:
                        record_msg = ''
                        record_msg += textwrap.dedent(f"""
                        {self.dungeon_cache[record['dungeon_id']]['name']}+{record['keystone_level']} ({datetime.fromtimestamp(record['completed_timestamp'] / 1000).strftime('%Y-%m-%d %H:%M')})
                        ({record['keystone_upgrade']}) {int(record['duration'] / 60000)}분 {int((record['duration'] / 1000) % 60)}초
                        """)
                        for member in record['members']:
                            record_msg += textwrap.dedent(f"""
                            {member['name']}-{member['realm']} ({member['specName']} {member['className']})
                            """)
                        msg += record_msg.replace('\n\n', '\n').strip() + "\n\n"
                    self.telegram.send_message(chat_id=chat_id, text=msg)

    def bot_work(self):
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
            traceback.print_exc()
            logger.info(e)

            self.telegram.send_message(text=str(e))
        except:
            self.need_init = True
            logger.info('unknown error')
            self.telegram.send_message(text='unknown error')
            raise

    def start(self, **kwargs):
        sched = BlockingScheduler()
        sched.add_job(self.bot_work,'cron', **kwargs)
        sched.start()

if __name__ == '__main__':
    #MythicBot().start(minute='*/10')
    MythicBot().bot_work()
