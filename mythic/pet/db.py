import pymongo
from mythic.logger import logger

class PetDatabase:
    def __init__(self, host, db):
        self.conn = pymongo.MongoClient(host)
        self.db = self.conn[db]

    def insert_pet(self, record):
        if self.db is None:
            logger.info(record)
            return True

        try:
            self.db.pets.insert_one(record)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False

    def update_pet(self, record, updates):
        if self.db is None:
            logger.info(record)
            return True

        self.db.pets.update_one({
            '_id': record['_id']
            },{
            '$set': updates
        }, upsert=False)

