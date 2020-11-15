import pymongo
from mythic.logger import logger

class PetDatabase:
    def __init__(self, host, db):
        self.conn = pymongo.MongoClient(host)
        self.db = self.conn[db]

    def insert_pet(self, record, upsert=False):
        if self.db is None:
            logger.info(record)
            return True

        try:
            if upsert:
                self.db.pets.replace_one({'_id': record['_id']}, record, upsert=True)
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
                self.db.mounts.replace_one({'_id': record['_id']}, record, upsert=True)
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

    def insert_trainer(self, record, upsert=False):
        if self.db is None:
            logger.info(record)
            return True

        try:
            if upsert:
                self.db.trainers.replace_one({'_id': record['_id']}, record, upsert=True)
            else:
                self.db.trainers.insert_one(record)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False

    def update_trainer(self, record, updates):
        if self.db is None:
            logger.info(record)
            return True

        self.db.trainers.update_one({
            '_id': record['_id']
            },{
            '$set': updates
        }, upsert=False)

    def find_trainer(self, id):
        if self.db is None:
            logger.info(id)
            return True

        return self.db.trainers.find_one({'_id': id})
