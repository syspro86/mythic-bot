import pymongo
from mythic.logger import logger

class AuctionDatabase:
    def __init__(self, host, db):
        self.conn = pymongo.MongoClient(host)
        self.db = self.conn[db]

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

    def update_auction(self, record, updates):
        if self.db is None:
            logger.info(record)
            return True

        self.db.auctions.update_one({
            '_id': record['_id']
            },{
            '$set': updates
        }, upsert=False)

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

