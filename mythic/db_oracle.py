import cx_Oracle
import json
import traceback
from mythic.logger import logger


class MythicDatabase:
    # https://cx-oracle.readthedocs.io/en/latest/user_guide/batch_statement.html
    def __init__(self, dsn, user, password, client_path):
        cx_Oracle.init_oracle_client(lib_dir=client_path)
        self.conn = cx_Oracle.connect(
            user=user, password=password, dsn=dsn, encoding='UTF-8')
        self.conn.autocommit = False

    def insert_record(self, record):
        if self.conn is None:
            logger.info(record)
            return True

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
        except:
            self.conn.rollback()
        finally:
            cur.close()

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
        finally:
            cur.close()

        rows = cur.fetchall()
        if not rows:
            return []

        return list(rows)

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
            """, user['_id'], user['webSessionId'])

            cur.execute(
                "delete from mythic_botuser_player where user_id = :1", user['_id'])

            # cur.executemany("insert into mythic_botuser_player (user_id, player_realm, player_name) values (:1, :2, :3)", )

            cur.execute(
                "delete from mythic_botuser_comment where user_id = :1", user['_id'])

            self.conn.commit()
        except:
            self.conn.rollback()
        finally:
            cur.close()

    def find_botusers(self, char_name=None, chat_id=None, session=None):
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
                    {','.join([(':' + str(idx+2)) for idx in range(len(keys))])}
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
