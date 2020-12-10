import os
import yaml

class MythicConfig:
    def __init__(self):
        self.load_yml()

        env = dict(os.environ)
        self.update(env, 'BATTLENET_REGION')
        self.update(env, 'BATTLENET_API_ID')
        self.update(env, 'BATTLENET_API_SECRET')
        self.update(env, 'MONGO_HOST')
        self.update(env, 'MONGO_DATABASE')
        self.update(env, 'TELEGRAM_TOKEN')
        self.update(env, 'ADMIN_CHAT_ID')
        self.update(env, 'WEL_UI_URL')
        self.update(env, 'HASH_SALT_PREFIX')
        self.update(env, 'HASH_SALT_SUFFIX')

    def load_yml(self):
        try:
            with open('mythic.yml') as f:
                conf = yaml.load(f, Loader=yaml.FullLoader)

                battlenet = conf['battlenet']
                self.BATTLENET_REGION = battlenet['region']
                self.BATTLENET_API_ID  = battlenet['api_id']
                self.BATTLENET_API_SECRET = battlenet['api_secret']

                db = conf['db']
                self.MONGO_HOST = db['mongo_host']
                self.MONGO_DATABASE = db['mongo_database']

                notify = conf['notify']
                self.TELEGRAM_TOKEN = notify['telegram_token']
                self.ADMIN_CHAT_ID = notify['admin_chat_id']

                web = conf['web']
                self.WEL_UI_URL = web['url']
                self.HASH_SALT_PREFIX = web['hash_salt_prefix']
                self.HASH_SALT_SUFFIX = web['hash_salt_suffix']

        except:
            pass

    def update(self, env, key):
        if key in env:
            setattr(self, key, env[key])

config = MythicConfig()
