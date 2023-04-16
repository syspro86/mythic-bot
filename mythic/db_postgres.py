import psycopg2
import json
import traceback
from mythic.logger import logger
import copy
from datetime import datetime


class MythicDatabase:
    def __init__(self, host, port, dbname, user, password):
        self._host = host
        self._port = port
        self._dbname = dbname
        self._user = user
        self._password = password

    def connect(self):
        self.conn = psycopg2.connect(host=self._host, port=self._port, dbname=self._dbname,
            user=self._user, password=self._password, sslmode="disable")
        self.conn.autocommit = False

    def disconnect(self):
        if self.conn is not None:
            try:
                self.conn.close()
            finally:
                self.conn = None

    def insert_record(self, record):
        if self.conn is None:
            logger.info(record)
            return False

        cur = self.conn.cursor()
        record = copy.deepcopy(record)

        players = list(
            map(lambda m: (record['_id'], m['realm'], m['name'], m['spec'], m['className'], m['specName'], m['role'], m['id']), record['members']))
        
        del record['members']
        rows = [(
            record['_id'],
            record['season'],
            record['period'],
            record['dungeon_id'],
            record['duration'],
            record['completed_timestamp'],
            record['keystone_level'],
            record['keystone_upgrade'],
            record['mythic_rating'],
            json.dumps(record)
        )]

        try:
            cur.executemany(
                "insert into public.mythic_record(record_id, season, period, dungeon_id, duration, completed_timestamp, keystone_level, keystone_upgrade, mythic_rating, json_text) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", rows)

            cur.executemany(
                "insert into mythic_record_player(record_id, player_realm, player_name, spec_id, class_name, spec_name, role_name, player_id) values (%s, %s, %s, %s, %s, %s, %s, %s)", players)

            self.conn.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            self.conn.rollback()
        except:
            traceback.print_exc()
            self.conn.rollback()
        finally:
            cur.close()
        return False

    def find_records(self, char_name, realm, limit=10):
        if self.conn is None:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute("""
                select r.json_text from mythic_record r, MYTHIC_RECORD_player p
                where r.record_id = p.record_id
                and p.player_realm = %s
                and p.player_name = %s
            """, [realm, char_name])

            rows = cur.fetchmany(limit)
            if not rows:
                return []
            return list(map(lambda r: json.loads(str(r[0])), rows))
        finally:
            cur.close()

    def find_characters(self, name):
        if self.conn is None:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute("""
                select distinct player_realm from mythic_record_player
                where player_name = %s
            """, [name])

            rows = cur.fetchall()
            if not rows:
                return []

            return list(map(lambda r: r[0], rows))
        finally:
            cur.close()

    def find_dungeon(self, dungeon_id):
        if self.conn is None:
            return None
        
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT DUNGEON_NAME, ZONE, UPGRADE_1, UPGRADE_2, UPGRADE_3
                  FROM MYTHIC_DUNGEON
                 WHERE DUNGEON_ID = %s
            """, [ dungeon_id ])

            r = cur.fetchone()
            if not r:
                return None

            return {
                'dungeon_id': dungeon_id,
                'dungeon_name': r[0],
                'zone': r[1],
                'upgrade_1': int(r[2]),
                'upgrade_2': int(r[3]),
                'upgrade_3': int(r[4])
            }
        finally:
            cur.close()

    def update_dungeon(self, dungeon):
        if self.conn is None:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO MYTHIC_DUNGEON
                (DUNGEON_ID, DUNGEON_NAME, ZONE, UPGRADE_1, UPGRADE_2, UPGRADE_3)
                VALUES
                (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (DUNGEON_ID) DO UPDATE
                SET DUNGEON_NAME = %s,
                ZONE = %s,
                UPGRADE_1 = %s,
                UPGRADE_2 = %s,
                UPGRADE_3 = %s
            """, [ dungeon['id'],
                  dungeon['name'],
                  dungeon['zone']['slug'],
                  list(filter(lambda d: d['upgrade_level'] == 1, dungeon['keystone_upgrades']))[0]['qualifying_duration'],
                  list(filter(lambda d: d['upgrade_level'] == 2, dungeon['keystone_upgrades']))[0]['qualifying_duration'],
                  list(filter(lambda d: d['upgrade_level'] == 3, dungeon['keystone_upgrades']))[0]['qualifying_duration'],
                  dungeon['name'],
                  dungeon['zone']['slug'],
                  list(filter(lambda d: d['upgrade_level'] == 1, dungeon['keystone_upgrades']))[0]['qualifying_duration'],
                  list(filter(lambda d: d['upgrade_level'] == 2, dungeon['keystone_upgrades']))[0]['qualifying_duration'],
                  list(filter(lambda d: d['upgrade_level'] == 3, dungeon['keystone_upgrades']))[0]['qualifying_duration']
            ])

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()


    def find_mythic_rating(self, realm, name, period):
        if self.conn is None:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute("""
            SELECT DUNGEON_ID,DUNGEON_NAME,MYTHIC_RATING,P2
              FROM (
                SELECT DUNGEON_ID,(SELECT DUNGEON_NAME FROM MYTHIC_DUNGEON WHERE DUNGEON_ID = MR.DUNGEON_ID) AS DUNGEON_NAME, MYTHIC_RATING, MOD(PERIOD,2) AS P2,
                       ROW_NUMBER() OVER (PARTITION BY DUNGEON_ID, MOD(PERIOD,2) ORDER BY MYTHIC_RATING DESC) AS RN
                  FROM MYTHIC_RECORD MR, MYTHIC_RECORD_PLAYER MRP 
                 WHERE MRP.PLAYER_REALM = %s
                   AND MRP.PLAYER_NAME = %s
                   AND MR.RECORD_ID = MRP.RECORD_ID
                   AND MR.MYTHIC_RATING IS NOT NULL
                   AND MR.PERIOD <= %s
                ) RR
             WHERE RR.RN = 1
            """, [realm, name, period])

            rows = cur.fetchall()
            if not rows:
                return []

            return list(map(lambda r: {
                "dungeon_id": int(r[0]),
                "dungeon_name": str(r[1]),
                "mythic_rating": float(r[2]),
                "affix": int(r[3])
            }, rows))
        finally:
            cur.close()


    def find_mythic_rating_list(self, realm, name):
        if self.conn is None:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute("""
            SELECT DUNGEON_ID, DUNGEON_NAME, MYTHIC_RATING, PERIOD, (SELECT MIN(SEASON) FROM MYTHIC_SEASON_PERIOD WHERE PERIOD = RR.PERIOD) AS SEASON
            FROM (
            SELECT DUNGEON_ID,
            (SELECT DUNGEON_NAME FROM MYTHIC_DUNGEON WHERE DUNGEON_ID = MR.DUNGEON_ID) AS DUNGEON_NAME,
            PERIOD,
            MYTHIC_RATING,
            ROW_NUMBER() OVER (PARTITION BY DUNGEON_ID, PERIOD ORDER BY MYTHIC_RATING DESC) AS RN
            FROM MYTHIC_RECORD MR, MYTHIC_RECORD_PLAYER MRP 
            WHERE MRP.PLAYER_REALM = %s
            AND MRP.PLAYER_NAME = %s
            AND MR.RECORD_ID = MRP.RECORD_ID
            AND MR.MYTHIC_RATING IS NOT NULL
            ) RR
            WHERE RR.RN = 1
            ORDER BY PERIOD, DUNGEON_ID
            """, [realm, name])

            rows = cur.fetchall()
            if not rows:
                return []

            return list(map(lambda r: {
                "dungeon_id": int(r[0]),
                "dungeon_name": str(r[1]),
                "mythic_rating": float(r[2]),
                "period": int(r[3]),
                "season": int(r[4])
            }, rows))
        finally:
            cur.close()


    def save_botuser(self, user, upsert=False):
        if self.conn is None:
            return

        try:
            cur = self.conn.cursor()
            cur.execute("""
                merge into mythic_botuser b
                using dual
                on (b.user_id = %s)
                when matched then
                    update set web_session_id = %s
                when not matched then
                    insert (user_id, web_session_id)
                    values (%s, %s)
            """, [user['_id'], (user['webSessionId'] if 'webSessionId' in user else ' '),
                  user['_id'], (user['webSessionId'] if 'webSessionId' in user else ' ')])

            cur.execute(
                "delete from mythic_botuser_player where user_id = %s", [user['_id']])

            for char in user['characters']:
                rn = char.split('-')
                if len(rn) == 2:
                    cur.execute(
                        "insert into mythic_botuser_player (user_id, player_realm, player_name) values (%s, %s, %s)",
                        [user['_id'], rn[1], rn[0]])

            # cur.execute("delete from mythic_botuser_comment where user_id = $1", user['_id'])

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()

    def find_botusers(self, char_name=None, chat_id=None, session=None):
        try:
            cur = self.conn.cursor()
            if chat_id is not None:
                cur.execute("""
                    SELECT mb.USER_ID, mb.WEB_SESSION_ID, mbp.PLAYER_REALM, mbp.PLAYER_NAME
                      FROM MYTHIC_BOTUSER mb, MYTHIC_BOTUSER_PLAYER mbp
                     WHERE mb.USER_ID = mbp.USER_ID
                       AND mb.USER_ID = %s
                """, [str(chat_id)])
            elif session is not None:
                cur.execute("""
                    SELECT mb.USER_ID, mb.WEB_SESSION_ID, mbp.PLAYER_REALM, mbp.PLAYER_NAME
                      FROM MYTHIC_BOTUSER mb, MYTHIC_BOTUSER_PLAYER mbp
                     WHERE mb.USER_ID = mbp.USER_ID
                       AND mb.WEB_SESSION_ID = %s
                """, [session])
            else:
                if char_name.find('-') >= 0:
                    cur.execute("""
                        SELECT mb.USER_ID, mb.WEB_SESSION_ID, mbp.PLAYER_REALM, mbp.PLAYER_NAME
                        FROM MYTHIC_BOTUSER mb, MYTHIC_BOTUSER_PLAYER mbp
                        WHERE mb.USER_ID = mbp.USER_ID
                        AND mbp.PLAYER_NAME = %s
                        AND mbp.PLAYER_REALM = %s
                    """, char_name.split('-')[0:2])
                else:
                    cur.execute("""
                        SELECT mb.USER_ID, mb.WEB_SESSION_ID, mbp.PLAYER_REALM, mbp.PLAYER_NAME
                        FROM MYTHIC_BOTUSER mb, MYTHIC_BOTUSER_PLAYER mbp
                        WHERE mb.USER_ID = mbp.USER_ID
                        AND mbp.PLAYER_NAME = %s
                    """, [char_name])

            rows = cur.fetchall()
            if not rows:
                return []

            return [{
                '_id': rows[0][0],
                'webSessionId': rows[0][1],
                'characters': list(map(lambda r: f"{r[3]}-{r[2]}", rows)),
                'userComments': []
            }]

        finally:
            cur.close()
        return []
    
    def find_all_realm(self):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT REALM_ID, REALM_SLUG, REALM_NAME FROM PLAYER_REALM
            """)
            rows = cur.fetchall()
            if not rows:
                return []
            
            return list(map(lambda r: {
                'realm_id': int(r[0]),
                'realm_slug': str(r[1]),
                'realm_name': str(r[2]),
            }, rows))
        except Exception as e:
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()
        return None

    def find_realm_slug(self, realm_name):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT REALM_SLUG FROM PLAYER_REALM
                WHERE REALM_NAME = %s
            """, [ realm_name ])
            return cur.fetchone()[0]
        except Exception as e:
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()
        return None

    def insert_realm(self, realm):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO PLAYER_REALM
                (REALM_ID, REALM_SLUG, REALM_NAME)
                VALUES (%s, %s, %s)
                ON CONFLICT (REALM_ID) DO NOTHING
            """, [
                realm['realm_id'],
                realm['realm_slug'],
                realm['realm_name']
            ])
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()

    def update_season(self, season_id, season_name, start_timestamp, end_timestamp, periods):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO MYTHIC_SEASON
                (SEASON, SEASON_NAME, START_TIMESTAMP, END_TIMESTAMP)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (SEASON) DO UPDATE
                SET SEASON_NAME = %s,
                START_TIMESTAMP = %s,
                END_TIMESTAMP = %s
            """, [
                season_id,
                season_name, start_timestamp, end_timestamp,
                season_name, start_timestamp, end_timestamp
            ])

            cur.execute("""
                DELETE FROM MYTHIC_SEASON_PERIOD
                WHERE SEASON = %s
            """, [ season_id ])

            cur.executemany("""
                INSERT INTO MYTHIC_SEASON_PERIOD
                (SEASON, PERIOD)
                VALUES (%s, %s)
            """, list(map(lambda p: [ season_id, p ], periods)))

            self.conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()
        return False

    def find_season_period(self, season):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT PERIOD FROM MYTHIC_SEASON_PERIOD
                WHERE SEASON = %s
            """, [ season ])
            
            rows = cur.fetchall()
            if not rows:
                return []

            return list(map(lambda r: int(r[0]), rows))
        except Exception as e:
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()

    def find_period(self, period=None, timestamp=None):
        try:
            cur = self.conn.cursor()
            if period is not None:
                cur.execute("""
                    SELECT PERIOD, START_TIMESTAMP, END_TIMESTAMP FROM MYTHIC_PERIOD
                    WHERE PERIOD = %s
                """, [ period ])
            elif timestamp is not None:
                cur.execute("""
                    SELECT PERIOD, START_TIMESTAMP, END_TIMESTAMP FROM MYTHIC_PERIOD
                    WHERE START_TIMESTAMP <= %s
                      AND END_TIMESTAMP > %s
                """, [ timestamp, timestamp ])
            else:
                return None
            
            r = cur.fetchone()
            return {
                "period": int(r[0]),
                "start_timestamp": int(r[1]),
                "end_timestamp": int(r[2])
            }
        except Exception as e:
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()
        return None
    
    def find_period_minmax(self):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT MIN(PERIOD), MAX(PERIOD) FROM MYTHIC_PERIOD
            """)
            
            r = cur.fetchone()
            return {
                "min": int(r[0]),
                "max": int(r[1])
            }
        except Exception as e:
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()
        return None

    def insert_period(self, period):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO MYTHIC_PERIOD
                (PERIOD, START_TIMESTAMP, END_TIMESTAMP)
                VALUES (%s, %s, %s)
                ON CONFLICT (PERIOD) DO NOTHING
            """, [
                period['period'],
                period['start_timestamp'],
                period['end_timestamp']
            ])
            self.conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()
        return False


    def find_auction(self, auction_id):
        return True

    def insert_auction(self, record):
        return True

    def insert_auctions(self, records):
        try:
            cur = self.conn.cursor()
            data = [(item['_id'], item['realm_id'], item['item']['id'],
                     item['first_seen_ts'], item['first_seen_ts'], json.dumps(item)) for item in records]
            cur.executemany("""
                insert into mythic_auction
                (auction_id, realm_id, item_id,
                    first_seen_ts, last_seen_ts, json_text)
                values (%s, %s, %s, %s, %s, %s)
            """, data)
            self.conn.commit()
        except psycopg2.errors.UniqueViolation as e:
            pass
        except Exception as e:
            self.conn.rollback()
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()

    def update_auction(self, record, updates):
        return True

    def update_auctions(self, keys, update_ts):
        try:
            cur = self.conn.cursor()
            cur.execute(f"""
                update mythic_auction
                set last_seen_ts = %s
                where auction_id in (
                    {','.join([(':' + str(idx+2))
                              for idx in range(len(keys))])}
                )
            """, [update_ts]+keys)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()

    def find_item(self, item_id):
        if self.conn is None:
            return None

        try:
            cur = self.conn.cursor()
            cur.execute("""
                select json_text from mythic_item where item_id = %s
            """, [item_id])
            row = cur.fetchone()
            if not row:
                return None
        finally:
            cur.close()

        return json.loads(str(row[0]))

    def insert_item(self, record):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                insert into mythic_item
                (item_id, json_text) values %s, %s)
            """, [record['_id'], json.dumps(record)])
            self.conn.commit()
        except:
            self.conn.rollback()
        finally:
            cur.close()

    def update_item(self, record, updates):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                update mythic_item
                set json_text = %s
                where item_id = %s
            """, [json.dumps(record), record['_id']])
            self.conn.commit()
        except:
            self.conn.rollback()
            traceback.print_exc()
        finally:
            cur.close()

    def insert_pet(self, record, upsert=False):
        return True

    def find_pet(self, id):
        return None

    def insert_mount(self, record, upsert=False):
        return True

    def find_mount(self, id):
        return None

    def insert_player(self, record, upsert=False):
        return True

    def update_player(self, record, updates):
        return True

    def find_player(self, id):
        return None
    
    def next_update_player(self):
        try:
            cur = self.conn.cursor()

            cur.execute("""
                select player_realm, player_name from player_talent
                 where last_update_ts = 0
                limit 1
            """)
            
            r = cur.fetchone()
            if r is not None:
                return { 'realm': r[0], 'name': r[1] }

            cur.execute("""
                select rp.player_realm, rp.player_name from (
                select distinct player_realm, player_name from mythic_record_player
                where record_id in (
                select record_id from mythic_record
                where period = (select max(period) from mythic_record)
                and keystone_level >= 20
                and keystone_upgrade >= 1
                )
                ) rp left outer join player_talent pt
                on (rp.player_realm = pt.player_realm and rp.player_name = pt.player_name)
                where last_update_ts is null
                limit 1
            """)

            r = cur.fetchone()
            if r is not None:
                return { 'realm': r[0], 'name': r[1] }

            cur.execute("""
                select rp.player_realm, rp.player_name from (
                select distinct player_realm, player_name from mythic_record_player
                where record_id in (
                select record_id from mythic_record
                where period = (select max(period) from mythic_record)
                and keystone_level >= 20
                and keystone_upgrade >= 1
                )
                ) rp left outer join player_talent pt
                on (rp.player_realm = pt.player_realm and rp.player_name = pt.player_name)
                where last_update_ts < %s
                order by last_update_ts asc
                limit 1
            """, [ int(datetime.now().timestamp() * 1000) - 1000*60*60*24 ] )
            
            r = cur.fetchone()
            if r is not None:
                return { 'realm': r[0], 'name': r[1] }

            cur.execute("""
                select player_realm, player_name from player_talent
                order by last_update_ts asc
                limit 1
            """)
            
            r = cur.fetchone()
            return { 'realm': r[0], 'name': r[1] }

        except:
            traceback.print_exc()
        finally:
            cur.close()

        return None
    
    def update_player_talent(self, talent, slots):
        try:
            cur = self.conn.cursor()

            if talent['spec_id'] == 0:
                cur.execute("""
                    DELETE FROM PLAYER_TALENT
                    WHERE PLAYER_REALM = %s
                    AND PLAYER_NAME = %s
                """, [
                    talent['player_realm'],
                    talent['player_name']
                ])
            else:
                cur.execute("""
                    DELETE FROM PLAYER_TALENT
                    WHERE PLAYER_REALM = %s
                    AND PLAYER_NAME = %s
                    ABD SPEC_ID = 0
                """, [
                    talent['player_realm'],
                    talent['player_name']
                ])

            cur.execute("""
                INSERT INTO PLAYER_TALENT
                (PLAYER_REALM, PLAYER_NAME, SPEC_ID, TALENT_CODE, LAST_UPDATE_TS)
                VALUES(%s, %s, %s, %s, %s)
                ON CONFLICT (PLAYER_REALM, PLAYER_NAME, SPEC_ID) DO UPDATE
                SET TALENT_CODE = %s,
                LAST_UPDATE_TS = %s
            """, [
                talent['player_realm'],
                talent['player_name'],
                talent['spec_id'],
                talent['talent_code'],
                talent['last_update_ts'],
                talent['talent_code'],
                talent['last_update_ts']
            ])

            cur.executemany("""
                INSERT INTO PLAYER_TALENT_SLOT
                (TALENT_CODE, TALENT_ID, TALENT_RANK, TALENT_NAME, TOOLTIP_ID, SPELL_ID)
                VALUES(%s, %s, %s, %s, %s, %s)
                ON CONFLICT (TALENT_CODE, TALENT_ID) DO UPDATE
                SET TALENT_RANK = %s,
                TALENT_NAME = %s,
                TOOLTIP_ID = %s,
                SPELL_ID = %s
            """, list(map(lambda s: (
                s['talent_code'],
                s['talent_id'],
                s['talent_rank'],
                s['talent_name'],
                s['tooltip_id'],
                s['spell_id'],
                s['talent_rank'],
                s['talent_name'],
                s['tooltip_id'],
                s['spell_id']
            ), slots)))
            
            self.conn.commit()

        except:
            self.conn.rollback()
            traceback.print_exc()
        finally:
            cur.close()


    def list_doc(self, collection, match=None, limit=None, project=None):
        return []

    def aggregate(self, collection, aggr):
        return None

    def get_weekly_record(self, name, realm, period):
        if self.conn is None:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT mr.JSON_TEXT
                  FROM MYTHIC_RECORD mr, MYTHIC_RECORD_PLAYER mrp
                 WHERE mr.RECORD_ID = mrp.RECORD_ID 
                   AND mrp.PLAYER_REALM = %s
                   AND mrp.PLAYER_NAME = %s
                   AND cast(mr.JSON_TEXT::json->>'period' as numeric) = %s
            """, [realm, name, period])

            rows = cur.fetchall()
            if not rows:
                return []

            return list(map(lambda r: json.loads(str(r[0])), rows))

        except Exception as e:
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()

        return []

    def get_character_records(self, name: str, realm: str, count: int):
        if self.conn is None:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT * FROM (
                SELECT mr.JSON_TEXT
                  FROM MYTHIC_RECORD mr, MYTHIC_RECORD_PLAYER mrp
                 WHERE mr.RECORD_ID = mrp.RECORD_ID 
                   AND mrp.PLAYER_REALM = %s
                   AND mrp.PLAYER_NAME = %s
                 ORDER BY mr.RECORD_ID DESC
                ) T LIMIT %s
            """, [realm, name, count])

            rows = cur.fetchall()
            if not rows:
                return []

            return list(map(lambda r: json.loads(str(r[0])), rows))

        except Exception as e:
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()

        return []
    
    def get_relation(self, name, realm, run, limit=100):
        if self.conn is None:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT PLAYER_REALM, PLAYER_NAME, COUNT(1) FROM MYTHIC_RECORD_PLAYER
                WHERE RECORD_ID IN (
                SELECT mbp.RECORD_ID FROM MYTHIC_RECORD_PLAYER mbp
                WHERE mbp.PLAYER_REALM = %s
                AND mbp.PLAYER_NAME = %s
                )
                GROUP BY PLAYER_REALM, PLAYER_NAME
                HAVING COUNT(1) >= %s
                ORDER BY 3 DESC
                LIMIT %s
            """, [realm, name, int(run), limit])

            rows = cur.fetchall()
            if not rows:
                return []

            return list(map(lambda r: { 'name': r[1], 'realm': r[0], 'value': r[2] }, rows))

        except Exception as e:
            logger.info(str(e))
            traceback.print_exc()
        finally:
            cur.close()

        return []
    