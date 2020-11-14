import pymongo
from mythic.logger import logger

class MythicDatabase:
    def __init__(self, host, db):
        self.conn = pymongo.MongoClient(host)
        self.db = self.conn[db]

    def insert_record(self, record):
        if self.db is None:
            logger.info(record)
            return True

        try:
            self.db.records.insert_one(record)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False

    def find_records(self, char_name, realm, limit=10):
        if self.db is None:
            return []

        result = self.db.records.find({
            'members': { '$elemMatch': { 'name': char_name, 'realm': realm } }
        }).sort([('completed_timestamp', pymongo.DESCENDING)]).limit(limit)
        return list(result)

    def find_characters(self, name):
        if self.db is None:
            return []

        return list(map(lambda r: r['_id'], self.db.records.aggregate([
            { '$match': { 'members.name': name } },
            { '$unwind': '$members' },
            { '$match': { 'members.name': name } },
            { '$group': { '_id': '$members.realm' } },
        ])))

    def save_botuser(self, user, upsert=False):
        self.db.botusers.replace_one({
            '_id': user['_id']
        }, user, upsert=upsert)

    def find_botusers(self, char_name=None, chat_id=None):
        if self.db is None:
            return []

        query = {}
        if char_name is not None:
            query['chatacters'] = char_name
        if chat_id is not None:
            query['_id'] = str(chat_id)

        return list(self.db.botusers.find(query))
