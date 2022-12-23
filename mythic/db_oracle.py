import cx_Oracle
import json
import traceback
from mythic.logger import logger


class MythicDatabase:
    _inited_ = False
    # https://cx-oracle.readthedocs.io/en/latest/user_guide/batch_statement.html

    def __init__(self, dsn, user, password, client_path):
        if not MythicDatabase._inited_:
            cx_Oracle.init_oracle_client(lib_dir=client_path)
            MythicDatabase._inited_ = True
        self._dsn = dsn
        self._user = user
        self._password = password

    def connect(self):
        self.conn = cx_Oracle.connect(
            user=self._user, password=self._password, dsn=self._dsn, encoding='UTF-8')
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
        rows = [(record['_id'], json.dumps(record))]

        players = list(
            map(lambda m: (record['_id'], m['realm'], m['name']), record['members']))

        try:
            cur.executemany(
                "insert into mythic_record(record_id, json_text) values (:1, :2)", rows)

            cur.executemany(
                "insert into mythic_record_player(record_id, player_realm, player_name) values (:1, :2, :3)", players)

            self.conn.commit()
            return True
        except cx_Oracle.IntegrityError:
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
                and p.player_realm = :realm
                and p.player_name = :name
            """, realm=realm, name=char_name)

            rows = cur.fetchmany(limit)
            if not rows:
                return []
        finally:
            cur.close()

        return list(rows)

    def find_characters(self, name):
        if self.conn is None:
            return []

        try:
            cur = self.conn.cursor()
            cur.execute("""
                select distinct player_realm from mythic_record_player
                where player_name = :name
            """, name=name)

            rows = cur.fetchall()
            if not rows:
                return []

            return list(rows)
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
                on (b.user_id = :1)
                when matched then
                    update set web_session_id = :2
                when not matched then
                    insert (user_id, web_session_id)
                    values (:1, :2)
            """, [user['_id'], (user['webSessionId'] if 'webSessionId' in user else ' ')])

            cur.execute(
                "delete from mythic_botuser_player where user_id = :1", [user['_id']])

            for char in user['characters']:
                rn = char.split('-')
                if len(rn) == 2:
                    cur.execute(
                        "insert into mythic_botuser_player (user_id, player_realm, player_name) values (:1, :2, :3)", [user['_id'], rn[1], rn[0]])

            # cur.execute("delete from mythic_botuser_comment where user_id = :1", user['_id'])

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
                       AND mb.USER_ID = :1
                """, [chat_id])
            elif session is not None:
                cur.execute("""
                    SELECT mb.USER_ID, mb.WEB_SESSION_ID, mbp.PLAYER_REALM, mbp.PLAYER_NAME
                      FROM MYTHIC_BOTUSER mb, MYTHIC_BOTUSER_PLAYER mbp
                     WHERE mb.USER_ID = mbp.USER_ID
                       AND mb.WEB_SESSION_ID = :1
                """, [session])
            else:
                cur.execute("""
                    SELECT mb.USER_ID, mb.WEB_SESSION_ID, mbp.PLAYER_REALM, mbp.PLAYER_NAME
                      FROM MYTHIC_BOTUSER mb, MYTHIC_BOTUSER_PLAYER mbp
                     WHERE mb.USER_ID = mbp.USER_ID
                       AND mbp.PLAYER_NAME = :1
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
                values (:1, :2, :3, :4, :5, :6)
            """, data)
            self.conn.commit()
        except cx_Oracle.IntegrityError as e:
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
                set last_seen_ts = :1
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
                select json_text from mythic_item where item_id = :1
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
                (item_id, json_text) values (:1, :2)
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
                set json_text = :1
                where item_id = :2
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
                   AND mrp.PLAYER_REALM = :1
                   AND mrp.PLAYER_NAME = :2
                   AND json_value(mr.JSON_TEXT, '$.period') = :3
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
                   AND mrp.PLAYER_REALM = :1
                   AND mrp.PLAYER_NAME = :2
                 ORDER BY mr.RECORD_ID DESC
                ) T WHERE ROWNUM <= :3
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
