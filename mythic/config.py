import os

class MythicConfig:
    def __init__(self):
        try:
            self.BATTLENET_API_ID  = os.environ['BATTLENET_API_ID']
            self.BATTLENET_API_SECRET = os.environ['BATTLENET_API_SECRET']

            self.MONGO_URL = os.environ['MONGO_URL']
            self.MONGO_DATABASE = os.environ['MONGO_DATABASE']

            self.TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
            self.ADMIN_CHAT_ID = os.environ['ADMIN_CHAT_ID']
        except:
            self.dev()
            pass

    def dev(self):
        self.BATTLENET_API_ID  = ''
        self.BATTLENET_API_SECRET = ''

        self.MONGO_URL = ''
        self.MONGO_DATABASE = ''

        self.TELEGRAM_TOKEN = ''
        self.ADMIN_CHAT_ID = ''
        return self

config = MythicConfig()
