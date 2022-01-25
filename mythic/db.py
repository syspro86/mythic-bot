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
            'members': {'$elemMatch': {'name': char_name, 'realm': realm}}
        }).sort([('completed_timestamp', pymongo.DESCENDING)]).limit(limit)
        return list(result)

    def find_characters(self, name):
        if self.db is None:
            return []

        return list(map(lambda r: r['_id'], self.db.records.aggregate([
            {'$match': {'members.name': name}},
            {'$unwind': '$members'},
            {'$match': {'members.name': name}},
            {'$group': {'_id': '$members.realm'}},
        ])))

    def save_botuser(self, user, upsert=False):
        self.db.botusers.replace_one({
            '_id': user['_id']
        }, user, upsert=upsert)

    def find_botusers(self, char_name=None, chat_id=None, session=None):
        if self.db is None:
            return []

        query = {}
        if char_name is not None:
            query['characters'] = char_name
        if chat_id is not None:
            query['_id'] = str(chat_id)
        if session is not None:
            query['webSessionId'] = session

        return list(self.db.botusers.find(query))

    def find_auction(self, auction_id):
        if self.db is None:
            logger.info(auction_id)
            return True

        result = self.db.auctions.find_one({'_id': auction_id})
        return result

    def insert_auction(self, record):
        if self.db is None:
            logger.info(record)
            return True

        try:
            self.db.auctions.insert_one(record)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False

    def insert_auctions(self, records):
        if self.db is None:
            return

        try:
            self.db.auctions.insert_many(records, ordered=False)
        except Exception as e:
            logger.info(str(e))

    def update_auction(self, record, updates):
        if self.db is None:
            logger.info(record)
            return True

        self.db.auctions.update_one({
            '_id': record['_id']
        }, {
            '$set': updates
        }, upsert=False)

    def update_auctions(self, keys, update_ts):
        if self.db is None:
            return

        self.db.auctions.update_many(
            {'_id': {'$in': keys}},
            {'$set': {'last_seen_ts': update_ts}})

    def find_item(self, item_id):
        if self.db is None:
            return []

        result = self.db.items.find_one({'_id': item_id})
        return result

    def insert_item(self, record):
        if self.db is None:
            logger.info(record)
            return True

        try:
            self.db.items.insert_one(record)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False

    def update_item(self, record, updates):
        if self.db is None:
            logger.info(record)
            return True

        self.db.items.update_one({
            '_id': record['_id']
        }, {
            '$set': updates
        }, upsert=False)

    def insert_pet(self, record, upsert=False):
        if self.db is None:
            logger.info(record)
            return True

        try:
            if upsert:
                self.db.pets.replace_one(
                    {'_id': record['_id']}, record, upsert=True)
            else:
                self.db.pets.insert_one(record)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False

    def find_pet(self, id):
        if self.db is None:
            logger.info(id)
            return True

        return self.db.pets.find_one({'_id': id})

    def insert_mount(self, record, upsert=False):
        if self.db is None:
            logger.info(record)
            return True

        try:
            if upsert:
                self.db.mounts.replace_one(
                    {'_id': record['_id']}, record, upsert=True)
            else:
                self.db.mounts.insert_one(record)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False

    def find_mount(self, id):
        if self.db is None:
            logger.info(id)
            return True

        return self.db.mounts.find_one({'_id': id})

    def insert_player(self, record, upsert=False):
        if self.db is None:
            logger.info(record)
            return True

        try:
            if upsert:
                self.db.players.replace_one(
                    {'_id': record['_id']}, record, upsert=True)
            else:
                self.db.players.insert_one(record)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False

    def update_player(self, record, updates):
        if self.db is None:
            logger.info(record)
            return True

        self.db.players.update_one({
            '_id': record['_id']
        }, {
            '$set': updates
        }, upsert=False)

    def find_player(self, id):
        if self.db is None:
            logger.info(id)
            return True

        return self.db.players.find_one({'_id': id})

    def list_doc(self, collection, match=None, limit=None, project=None):
        if self.db is None:
            return None

        col = getattr(self.db, collection)
        aggr = []
        if match is not None:
            aggr.append({'$match': match})
        if limit is not None:
            aggr.append({'$limit': limit})
        if project is not None:
            aggr.append({'$project': project})

        return list(col.aggregate(aggr))

    def aggregate(self, collection, aggr):
        if self.db is None:
            return None

        col = getattr(self.db, collection)
        return list(col.aggregate(aggr))
