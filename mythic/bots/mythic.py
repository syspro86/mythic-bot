from mythic.config import config
from mythic.logger import logger
from mythic.bots.base import BaseBot

from datetime import datetime
import json


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
        try:
            self.db.connect()

            realms = self.api.bn_request(
                "/data/wow/realm/index", token=True, namespace="dynamic")
            self.realm_cache = {}
            for realm in realms['realms']:
                realm_id = realm['id']
                self.realm_cache[realm_id] = realm
                
                realm_id = realm['id']
                realm_slug = realm['slug']
                realm_name = realm['name']
                self.db.insert_realm({
                    'realm_id': realm_id,
                    'realm_slug': realm_slug,
                    'realm_name': realm_name
                })

            self.connected_realms = []
            connected_realms = self.api.bn_request(
                "/data/wow/connected-realm/index", token=True, namespace="dynamic")
            for realm in connected_realms['connected_realms']:
                href = realm['href']
                realm = self.api.bn_request(href, token=True)
                self.connected_realms.append(realm['id'])

            dungeons = self.api.bn_request(
                "/data/wow/mythic-keystone/dungeon/index", token=True, namespace="dynamic")
            self.dungeon_cache = {}
            for dungeon in dungeons['dungeons']:
                dungeon_id = dungeon['id']
                d = self.api.bn_request(
                    f"/data/wow/mythic-keystone/dungeon/{dungeon_id}", token=True, namespace="dynamic")
                if isinstance(d, int):
                    logger.info(f"failed to update dungeon_id: {dungeon_id}, code: {d}")
                    continue
                self.db.update_dungeon(d)
                self.dungeon_cache[dungeon_id] = self.db.find_dungeon(dungeon_id)

            specs = self.api.bn_request(
                "/data/wow/playable-specialization/index", token=True, namespace="static")
            self.spec_cache = {}
            for spec in specs['character_specializations']:
                spec_id = spec['id']
                spec = self.api.bn_request(
                    f"/data/wow/playable-specialization/{spec_id}", token=True, namespace="static")
                if isinstance(spec, int):
                    logger.info(f"failed to get spec_id: {spec_id}, code: {spec}")
                self.spec_cache[spec_id] = spec

            seasons = self.api.bn_request(
                "/data/wow/mythic-keystone/season/index", token=True, namespace="dynamic")
            self.current_season = seasons['current_season']['id']
            for season in seasons['seasons']:
                season_id = season['id']
                # 과거 시즌 정보가 잘못되어 수작업으로 수정함.
                # 다시 망가지지 않도록 현재 시즌만 갱신함.
                if self.current_season != season_id:
                    continue
                season = self.api.bn_request(
                    f"/data/wow/mythic-keystone/season/{season_id}", token=True, namespace="dynamic")
                season_name = season['season_name']
                start_timestamp = season['start_timestamp']
                end_timestamp = season['end_timestamp'] if 'end_timestamp' in season else None
                periods = []
                if 'periods' in season:
                    for period in season['periods']:
                        periods.append(period['id'])
                self.db.update_season(season_id, season_name, start_timestamp, end_timestamp, periods)

            periods = self.api.bn_request(
                "/data/wow/mythic-keystone/period/index", token=True, namespace="dynamic")
            for period in sorted(periods['periods'], key=lambda r: -r['id']):
                period_res = self.api.bn_request(
                    f"/data/wow/mythic-keystone/period/{period['id']}", token=True, namespace="dynamic")
                period_res['period'] = period_res['id']
                if not self.db.insert_period(period_res):
                    break

            self.current_period = periods['current_period']['id']
            self.end_timestamp = int(self.db.find_period(period=self.current_period)['end_timestamp'])
            end_timestamp_str = datetime.fromtimestamp(
                self.end_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(
                f"season: {self.current_season}, period: {self.current_period}, ends: {end_timestamp_str}")

            self.need_init = False
        except TypeError:
            self.need_init = True
        finally:
            self.db.disconnect()

    def get_leaderboard(self, realm_id, dungeon_id, period):
        board = self.api.bn_request(
            f"/data/wow/connected-realm/{realm_id}/mythic-leaderboard/{dungeon_id}/period/{period}", token=True, namespace="dynamic")
        if type(board) is not dict or 'leading_groups' not in board:
            logger.info(f"leaderboard for {dungeon_id}, {realm_id} is empty. {board}")
            return

        board['season'] = self.current_season
        for rec in board['leading_groups']:
            self.insert_record(board, rec, dungeon_id)

    def insert_record(self, board, rec, dungeon_id):
        record = {}
        # ranking = rec['ranking']
        duration = rec['duration']
        completed_timestamp = rec['completed_timestamp']
        keystone_level = rec['keystone_level']

        # map_name = board['map']['name']
        season = board['season']
        period = board['period']

        if dungeon_id not in self.dungeon_cache:
            dungeon = self.db.find_dungeon(dungeon_id)
            if dungeon is None:
                print('unregistered dungeon = {dungeon_id}')
                return
            self.dungeon_cache[dungeon_id] = dungeon
        dungeon = self.dungeon_cache[dungeon_id]
        dungeon_name = dungeon['dungeon_name']

        ts_str = datetime.fromtimestamp(
            completed_timestamp / 1000).strftime('%Y-%m-%d_%H:%M:%S')
        ts_str2 = datetime.fromtimestamp(
            completed_timestamp / 1000).strftime('%Y-%m-%d %H:%M')

        def convert_member(member):
            try:
                m = {}
                m['id'] = member['profile']['id']
                m['name'] = member['profile']['name']
                if m['name'] == '':
                    m['name'] = '?'
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
            except KeyError as key_error:
                logger.info(str(key_error))
                self.telegram.send_message(
                    text=f'failed to convert member data {json.dumps(member)}')
                raise key_error
        record['members'] = map(convert_member, rec['members'])

        role_names = ['TANK', 'HEALER', 'DAMAGE', 'UNKNOWN']
        record['members'] = sorted(record['members'], key=lambda r: (
            role_names.index(r['role']), r['spec'], r['realm'], r['name']))
        
        record_id = f'{ts_str}_{dungeon_name}_{keystone_level}_{period}_{completed_timestamp}_'
        for mem in record['members']:
            record_id += mem['realm'][0] + mem['name'][0]

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
        record['keystone_upgrade'] = 1 if duration < dungeon['upgrade_1'] else record['keystone_upgrade']
        record['keystone_upgrade'] = 2 if duration < dungeon['upgrade_2'] else record['keystone_upgrade']
        record['keystone_upgrade'] = 3 if duration < dungeon['upgrade_3'] else record['keystone_upgrade']

        if 'mythic_rating' in rec and 'rating' in rec['mythic_rating']:
            record['mythic_rating'] = float(rec['mythic_rating']['rating'])
        else:
            upgrade = dungeon['upgrade_1']
            if upgrade >= duration:
                score = 30 + keystone_level * 7 + min(float(upgrade - duration) / upgrade, 0.4) * 5 / 0.4
            elif (duration-upgrade)/upgrade < 0.4:
                score = 25 + min(keystone_level, 20) * 7 - min(float(duration - upgrade) / upgrade, 0.4) * 5 / 0.4
            else:
                score = 0
            record['mythic_rating'] = score

        try:
            if self.db.insert_record(record):
                logger.info(f"new record = {record['_id']}")

                if season != self.current_season:
                    return
                
                minute = int(record['duration'] / 60000)
                second = (int(record['duration'] / 1000) % 60)

                msg = f"{dungeon_name}+{record['keystone_level']} ({ts_str2})\r\n"
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
                            self.telegram.send_message(
                                chat_id=buser['_id'], text=msg)
                            sent_botusers.append(buser['_id'])
                            # self.bot.send_message(text=msg)
                            logger.info(f"message sent! {buser['_id']} {msg}")

            self.inserted_id_set.append(record_id)
        except Exception as e:
            self.print_error(e)

    def update_player(self, realm, character_name):
        realm_slug = self.db.find_realm_slug(realm)
        self.update_player_runs(realm, realm_slug, character_name)
        self.update_player_talent(realm, realm_slug, character_name)

    def update_player_runs(self, realm, realm_slug, character_name):
        profile = self.api.bn_request(f"/profile/wow/character/{realm_slug}/{character_name.lower()}/mythic-keystone-profile", token=True, namespace="profile")
        if isinstance(profile, int):
            return
        if 'seasons' not in profile:
            return
        
        if 'current_period' in profile:
            if 'best_runs' in profile['current_period']:
                for run in profile['current_period']['best_runs']:
                    board = {
                        'period': profile['current_period']['period']['id'],
                        'season': self.season
                    }
                    
                    for mem in run['members']:
                        mem['profile'] = mem['character']

                    self.insert_record(board, run, run['dungeon']['id'])

        for season in profile['seasons']:
            href = season['key']['href']
            season_res = self.api.bn_request(href, token=True)
            if isinstance(season_res, int):
                continue
            #if season_res['season']['id'] != self.current_season:
            #    continue
            if 'best_runs' not in season_res:
                return
            for run in season_res['best_runs']:
                board = {
                    'period': self.db.find_period(timestamp=run['completed_timestamp'])['period'],
                    'season': season_res['season']['id']
                }
                
                for mem in run['members']:
                    mem['profile'] = mem['character']

                self.insert_record(board, run, run['dungeon']['id'])
                             
    def update_player_talent(self, realm, realm_slug, character_name):
        talents = self.api.bn_request(f"/profile/wow/character/{realm_slug}/{character_name.lower()}/specializations", token=True, namespace="profile")
        update_ts = int(datetime.now().timestamp() * 1000)
        if talents is None or isinstance(talents, int) or 'specializations' not in talents:
            self.db.update_player_talent({
                'player_realm': realm,
                'player_name': character_name,
                'spec_id': 0,
                'talent_code': '',
                'last_update_ts': update_ts
            }, [])

            self.db.update_player({
                'player_realm': realm,
                'player_name': character_name,
                'spec_id': 0,
                'class_name': 'Error',
                'spec_name': 'Error',
                'last_update_ts': update_ts
            })
            return
        
        spec = self.spec_cache[talents['active_specialization']['id']]
        self.db.update_player({
            'player_realm': realm,
            'player_name': character_name,
            'spec_id': talents['active_specialization']['id'],
            'class_name': spec['playable_class']['name'],
            'spec_name': spec['name'],
            'last_update_ts': update_ts
        })
        updated = 0
        for spec in talents['specializations']:
            try:
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
                        'last_update_ts': update_ts
                    }
                    slots = []
                    for ctal in loadout['selected_class_talents']:
                        slots.append({
                            'talent_code': talent_code,
                            'talent_id': ctal['id'],
                            'talent_rank': ctal['rank'],
                            'talent_name': self.get_field(ctal, ['tooltip', 'talent', 'name'], ''),
                            'tooltip_id': ctal['tooltip']['talent']['id'],
                            'spell_id': ctal['tooltip']['spell_tooltip']['spell']['id']
                        })
                    for stal in loadout['selected_spec_talents']:
                        slots.append({
                            'talent_code': talent_code,
                            'talent_id': stal['id'],
                            'talent_rank': stal['rank'],
                            'talent_name': self.get_field(stal, ['tooltip', 'talent', 'name'], ''),
                            'tooltip_id': stal['tooltip']['talent']['id'],
                            'spell_id': stal['tooltip']['spell_tooltip']['spell']['id']
                        })
                    
                    self.db.update_player_talent(talent, slots)
                    updated += 1
            except Exception as e:
                self.print_error(e)
                
        if updated == 0:
            self.db.update_player_talent({
                'player_realm': realm,
                'player_name': character_name,
                'spec_id': 0,
                'talent_code': '',
                'last_update_ts': update_ts
            }, [])  

        # pets = self.api.bn_request(f"/profile/wow/character/{realm}/{character_name}/collections/pets", token=True, namespace="profile")
        # if pets is not None and 'pets' in pets:
        #     self.db.update_player(player, {'pets': pets['pets']})

        # mounts = self.api.bn_request(f"/profile/wow/character/{realm}/{character_name}/collections/mounts", token=True, namespace="profile")
        # if mounts is not None and 'mounts' in mounts:
        #     self.db.update_player(player, {'mounts': mounts['mounts']})

    def get_field(self, obj, fields, default_value=None):
        for f in fields:
            if f in obj:
                obj = obj[f]
            else:
                return default_value
        return obj

    def on_schedule(self):
        try:
            start_ts = int(datetime.now().timestamp() * 1000)
            if self.end_timestamp < start_ts:
                self.need_init = True

            if self.need_init:
                self.init_api(True)
                self.inserted_id_set = []

                if self.need_init:
                    return

                # 현재 시간에 맞는 period가 없음.
                if self.end_timestamp < start_ts:
                    return

            self.db.connect()

            for rid in self.connected_realms:
                leaderboards = self.api.bn_request(f"/data/wow/connected-realm/{rid}/mythic-leaderboard/index", token=True, namespace="dynamic")
                if not isinstance(leaderboards, int):
                    continue

                for leaderboard in leaderboards['current_leaderboards']:
                    did = leaderboard['id']
                    logger.info(f"{rid} {self.dungeon_cache[did]['dungeon_name']} ({did})")
                    self.get_leaderboard(rid, did, self.current_period)

            cur_ts = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {cur_ts - start_ts} ms')

            break_ts = start_ts + 60_000 * 9
            add_cnt = 0
            while cur_ts > break_ts:
                break_ts += 60_000 * 10
                add_cnt += 0
            while add_cnt > 0:
                break_ts += 60_000 * 10
                add_cnt -= 0

            update_cnt = 0
            while cur_ts < break_ts:
                p = self.db.next_update_player()
                if p is None:
                    break

                self.update_player(p['realm'], p['name'])
                cur_ts = int(datetime.now().timestamp() * 1000)
                update_cnt += 1

            cur_ts = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {cur_ts - start_ts} ms, {update_cnt} player updated.')

        except Exception as e:
            self.need_init = True
            self.print_error(e)

            # self.telegram.send_message(text=str(e))
        except:
            self.need_init = True
            logger.info('unknown error')
            self.telegram.send_message(text='unknown error')
            raise

        finally:
            self.db.disconnect()


if __name__ == '__main__':
    MythicBot().on_schedule()
