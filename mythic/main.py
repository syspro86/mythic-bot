from mythic.config import config
from mythic.logger import logger
from mythic.db import MythicDatabase
from mythic.telegram import TelegramBot

from apscheduler.schedulers.blocking import BlockingScheduler
import base64
from datetime import datetime
import requests
import traceback

class MythicBot:
    def __init__(self):
        self.region = "kr"
        self.access_token = None
        self.inserted_id_set = []
        self.realm_cache = {}
        self.spec_cache = {}
        self.dungeon_cache = {}
        self.end_timestamp = 0
        self.season = -1

        self.init_api(False)
        self.need_init = False

        self.bot = TelegramBot()
        self.bot.sendMessage(text='app start')

        self.db = MythicDatabase()

    def get_token(self):
        url = f"https://{self.region}.battle.net/oauth/token"
        api_id = config.BATTLENET_API_ID
        api_secret = config.BATTLENET_API_SECRET
        auth = base64.b64encode((api_id + ':' + api_secret).encode()).decode('utf-8')

        headers = {
            'Authorization': 'Basic ' + auth,
            'Content-Type': "application/x-www-form-urlencoded"
        }
        
        res = requests.post(url, headers=headers, data={'grant_type': 'client_credentials'})
        if res.status_code == 200:
            return res.json()
        else:
            return ()

    def locale(self):
        if self.region == "us":
            return "en_US"
        elif self.region == "eu":
            return "en_GB"
        elif self.region ==  "kr":
            return "ko_KR"
        elif self.region ==  "tw":
            return "zh_TW"
        return ""

    def regionParameter(self, namespace):
        ret = f"region={self.region}"
        if namespace != None:
            ret +=f"&namespace={namespace}-{self.region}"
        ret += "&locale=" + self.locale()
        return ret

    def postfixParameter(self, namespace):
        return self.regionParameter(namespace) + "&access_token=" + self.access_token

    def bn_request(self, url):
        if not url.startswith('http'):
            url = f"https://{self.region}.api.blizzard.com:443" + url
        #logger.info(url)
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
        else:
            return ()

    def init_api(self, force):
        if self.access_token is None:
            logger.info('get new token!')
            res = self.get_token()
            if 'access_token' in res:
                self.access_token = res['access_token']
        elif isinstance(self.access_token, bytes):
            self.access_token = self.access_token.decode('utf-8')

        realms = self.bn_request("/data/wow/realm/index?" + self.postfixParameter("dynamic"))
        self.realm_cache = {}
        for realm in realms['realms']:
            realm_id = realm['id']
            self.realm_cache[realm_id] = realm

        dungeons = self.bn_request("/data/wow/mythic-keystone/dungeon/index?" + self.postfixParameter("dynamic"))
        self.dungeon_cache = {}
        for dungeon in dungeons['dungeons']:
            dungeon_id = dungeon['id']
            d = self.bn_request(f"/data/wow/mythic-keystone/dungeon/{dungeon_id}?" + self.postfixParameter("dynamic"))
            self.dungeon_cache[dungeon_id] = d

        specs = self.bn_request("/data/wow/playable-specialization/index?" + self.postfixParameter("static"))
        self.spec_cache = {}
        for spec in specs['character_specializations']:
            spec_id = spec['id']
            spec = self.bn_request("/data/wow/playable-specialization/" + str(spec_id) + "?" + self.postfixParameter("static"))
            self.spec_cache[spec_id] = spec

        seasons = self.bn_request("/data/wow/mythic-keystone/season/index?" + self.postfixParameter("dynamic"))
        self.current_season = seasons['current_season']['id']

        periods = self.bn_request("/data/wow/mythic-keystone/period/index?" + self.postfixParameter("dynamic"))
        self.period_ids = []
        for period in periods['periods']:
            period_id = period['id']
            self.period_ids.append(period_id)

        self.current_period = periods['current_period']['id']
        period_detail = self.bn_request(f"/data/wow/mythic-keystone/period/{self.current_period}?" + self.postfixParameter("dynamic"))
        self.end_timestamp = int(period_detail['end_timestamp'])

        self.need_init = False

    def get_leaderboard(self, realm_id, dungeon_id, season, period):
        board = self.bn_request(f"/data/wow/connected-realm/{realm_id}/mythic-leaderboard/{dungeon_id}/period/{period}?" + self.postfixParameter("dynamic"))
        if 'leading_groups' in board:
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
            m = {}
            m['name'] = member['profile']['name']
            rid = member['profile']['realm']['id']
            m['realm'] = self.realm_cache[rid]['name']
            m['spec'] = member['specialization']['id']
            spec = m['spec']
            spec = self.spec_cache[spec]
            m['className'] = spec['playable_class']['name']
            m['specName'] = spec['name']
            m['role'] = spec['role']['type']
            return m
        record['members'] = map(convert_member, rec['members'])

        roleNames = ['TANK', 'HEALER', 'DAMAGE']
        record['members'] = sorted(record['members'], key=lambda r: (roleNames.index(r['role']), r['spec']))

        try:
            self.db.insertRecord(record)
            logger.info(f"new record = {record['_id']}")
            
            minute = int(record['duration'] / 60000)
            second = (int(record['duration'] / 1000) % 60)
            
            msg = f"{dungeon['name']}+{record['keystone_level']} ({ts_str2})\r\n"
            msg += f"({record['keystone_upgrade']}) "
            msg += f"{minute}분 {second}초"
            for member in record['members']:
                msg += f"\r\n{member['name']}-{member['realm']}"
                msg += f" ({member['specName']} {member['className']})"

            sentBotUser = []
            for member in record['members']:
                shortName = f"{member['name']}-{member['realm']}"

                for buser in self.db.findBotUsers(shortName):
                    if buser['_id'] not in sentBotUser:
                        self.bot.sendMessage(chat_id=buser['_id'], text=msg)
                        sentBotUser.append(buser['_id'])
                        # self.bot.sendMessage(text=msg)
                        logger.info(f"message sent! {buser['id']} {msg}")
        
            self.inserted_id_set.append(record_id)
        except Exception as e:
            traceback.print_exc()
            logger.info(e)
            pass

    def start(self, **kwargs):
        sched = BlockingScheduler()
        @sched.scheduled_job('cron', **kwargs)
        def bot_work():
            try:
                now_ts = int(datetime.now().timestamp() * 1000)
                if self.end_timestamp < now_ts:
                    self.need_init = True

                if self.need_init:
                    self.init_api(True)
                    self.inserted_id_set = []

                for did in self.dungeon_cache.keys():
                    for rid in self.realm_cache.keys():
                        self.get_leaderboard(rid, did, self.current_season, self.current_period)

                now_ts2 = int(datetime.now().timestamp() * 1000)
                logger.info(f'collected in {now_ts2 - now_ts} ms')
            except Exception as e:
                self.need_init = True
                traceback.print_exc()
                logger.info(e)

                self.bot.sendMessage(text=str(e))
            except:
                self.need_init = True
                logger.info('unknown error')
                self.bot.sendMessage(text='unknown error')
                raise
        sched.start()

if __name__ == '__main__':
    MythicBot().start(minute='*/10')
