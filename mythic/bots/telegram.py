from mythic.config import config
from mythic.logger import logger
from mythic.bots.base import BaseBot
from mythic.telegram import TelegramBot as TBot

import base64
from datetime import datetime
import hashlib
import json
import requests
import textwrap


class TelegramBot(BaseBot):
    def __init__(self):
        super().__init__()

        self.dungeon_cache = {}

        self.init_api(False)
        self.need_init = False

        self.telegram = TBot(polling=True)
        self.telegram.add_callback(self.on_telegram_message)
        self.telegram.send_message(text='telegram app start')

    def init_api(self, force):

        dungeons = self.api.bn_request(
            "/data/wow/mythic-keystone/dungeon/index", token=True, namespace="dynamic")
        self.dungeon_cache = {}
        for dungeon in dungeons['dungeons']:
            dungeon_id = dungeon['id']
            d = self.api.bn_request(
                f"/data/wow/mythic-keystone/dungeon/{dungeon_id}", token=True, namespace="dynamic")
            self.dungeon_cache[dungeon_id] = d

        self.need_init = False

    def dungeon_name(self, dungeon_id):
        if dungeon_id not in self.dungeon_cache:
            return '이름모를던전'
        return self.dungeon_cache[dungeon_id]['name']

    def on_telegram_message(self, chat_id, message):
        try:
            self.db.connect()
            if message == '/me':
                self.on_telegram_message_me(chat_id)

            elif message == "/주차" or message == "/report":
                users = self.db.find_botusers(chat_id=chat_id)

            elif message.startswith("/add ") or message.startswith("/추가 "):
                char_name = str(message).split(' ', 2)[1]
                if len(char_name) > 0:
                    char_name = char_name[0:1].upper() + char_name[1:].lower()
                    users = self.db.find_botusers(chat_id=chat_id)
                    if len(users) > 0:
                        user = users[0]
                        if 'characters' not in user:
                            user['characters'] = []
                        if char_name not in user['characters']:
                            user['characters'].append(char_name)
                            self.db.save_botuser(user)
                            self.telegram.send_message(
                                chat_id=chat_id, text=f'{char_name} 추가되었습니다.')
                    else:
                        user = {
                            '_id': str(chat_id),
                            'characters': [char_name]
                        }
                        self.db.save_botuser(user, upsert=True)
                        self.telegram.send_message(
                            chat_id=chat_id, text=f'{char_name} 추가되었습니다.')

            elif message.startswith("/remove ") or message.startswith("/삭제 "):
                char_name = str(message).split(' ', 2)[1]
                if len(char_name) > 0:
                    char_name = char_name[0:1].upper() + char_name[1:].lower()
                    users = self.db.find_botusers(chat_id=chat_id)
                    if len(users) > 0:
                        user = users[0]
                        if 'characters' in user and char_name in user['characters']:
                            user['characters'].remove(char_name)
                            self.db.save_botuser(user)
                            self.telegram.send_message(
                                chat_id=chat_id, text=f'{char_name} 삭제되었습니다.')

            else:
                char_name = message.strip()
                if len(char_name) > 0:
                    self.on_telegram_message_find(chat_id, char_name)
        finally:
            self.db.disconnect()

    def on_telegram_message_me(self, chat_id):
        users = self.db.find_botusers(chat_id=chat_id)
        user = None
        if len(users) == 0:
            user = {'_id': str(chat_id), 'characters': []}
            self.db.save_botuser(user, upsert=True)
        else:
            user = users[0]

        self.telegram.send_message(chat_id=chat_id, text=json.dumps(
            user['characters'], ensure_ascii=False))

        if 'webSessionId' not in user or user['webSessionId'].strip() == '':
            sid = f'{config.HASH_SALT_PREFIX}{chat_id}{config.HASH_SALT_SUFFIX}'

            m = hashlib.new('sha256')
            m.update(sid.encode())
            hash256 = m.digest()
            sid = base64.b64encode(hash256).decode()
            sid = sid.replace('+', '-').replace('/', '_').replace("=", "")

            user['webSessionId'] = sid
            self.db.save_botuser(user)

        self.telegram.send_message(
            chat_id=chat_id, text=f"{config.WEB_UI_URL}{user['webSessionId']}")

    def on_telegram_message_find(self, chat_id, char_name):
        realms = []
        if char_name.find('-') > 0:
            realms.append(char_name[char_name.find('-')+1:])
            char_name = char_name[0:char_name.find('-')]
            char_name = char_name[0:1].upper() + char_name[1:].lower()
        else:
            char_name = char_name[0:1].upper() + char_name[1:].lower()
            realms = self.db.find_characters(char_name)

        if len(realms) == 0:
            self.telegram.send_message(
                chat_id=chat_id, text=f'{char_name} 캐릭터가 없습니다.')

        else:
            for realm in realms:
                records = list(self.db.find_records(
                    char_name, realm, limit=10))

                if len(records) == 0:
                    self.telegram.send_message(
                        chat_id=chat_id, text=f'{char_name}-{realm} 쐐기 데이터가 없습니다.')

                else:
                    msg = ''
                    for record in records:
                        record_msg = ''
                        record_msg += textwrap.dedent(f"""
                        {self.dungeon_name(record['dungeon_id'])}+{record['keystone_level']} ({datetime.fromtimestamp(record['completed_timestamp'] / 1000).strftime('%Y-%m-%d %H:%M')})
                        ({record['keystone_upgrade']}) {int(record['duration'] / 60000)}분 {int((record['duration'] / 1000) % 60)}초
                        """)
                        if 'members' in record:
                            for member in record['members']:
                                record_msg += textwrap.dedent(f"""
                                {member['name']}-{member['realm']} ({member['specName']} {member['className']})
                                """)
                        msg += record_msg.replace('\n\n',
                                                  '\n').strip() + "\n\n"
                    self.telegram.send_message(chat_id=chat_id, text=msg)

    def on_schedule(self):
        pass


if __name__ == '__main__':
    TelegramBot().on_schedule()
