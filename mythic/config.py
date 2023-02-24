import os
import yaml


class MythicConfig:
    def __init__(self):
        env = dict(os.environ)

        def nvl(key):
            return env[key] if key in env else ''

        self.BATTLENET_REGION = nvl('BATTLENET_REGION')
        self.BATTLENET_API_ID = nvl('BATTLENET_API_ID')
        self.BATTLENET_API_SECRET = nvl('BATTLENET_API_SECRET')
        self.DB_TYPE = nvl('DB_TYPE')
        self.MONGO_HOST = nvl('MONGO_HOST')
        self.MONGO_DATABASE = nvl('MONGO_DATABASE')
        self.ORACLE_DSN = nvl('ORACLE_DSN')
        self.ORACLE_USER = nvl('ORACLE_USER')
        self.ORACLE_PASSWORD = nvl('ORACLE_PASSWORD')
        self.ORACLE_CLIENT_PATH = nvl('ORACLE_CLIENT_PATH')
        self.POSTGRES_HOST = nvl('POSTGRES_HOST')
        self.POSTGRES_PORT = nvl('POSTGRES_PORT')
        self.POSTGRES_DBNAME = nvl('POSTGRES_DBNAME')
        self.POSTGRES_USER = nvl('POSTGRES_USER')
        self.POSTGRES_PASSWORD = nvl('POSTGRES_PASSWORD')
        self.TELEGRAM_TOKEN = nvl('TELEGRAM_TOKEN')
        self.ADMIN_CHAT_ID = nvl('ADMIN_CHAT_ID')
        self.WEB_UI_URL = nvl('WEB_UI_URL')
        self.HASH_SALT_PREFIX = nvl('HASH_SALT_PREFIX')
        self.HASH_SALT_SUFFIX = nvl('HASH_SALT_SUFFIX')


config = MythicConfig()
