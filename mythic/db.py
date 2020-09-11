import pymongo
from mythic.config import config
from mythic.logger import logger

class MythicDatabase:
    def __init__(self):
        self.conn = pymongo.MongoClient(config.MONGO_URL) if config.MONGO_URL is not None else None
        self.db = self.conn[config.MONGO_DATABASE] if self.conn is not None and config.MONGO_DATABASE is not None else None

    def insertRecord(self, record):
        if self.db is None:
            logger.info(record)
            return True

        try:
            self.db.records.insert_one(record)
            return True
        except pymongo.errors.DuplicateKeyError:
            return False

    def findBotUsers(self, charName):
        if self.db is None:
            return []

        return list(self.db.botusers.find({ 'characters': charName }))
