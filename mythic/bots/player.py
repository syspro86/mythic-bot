from mythic.config import config
from mythic.logger import logger
from mythic.bots.base import BaseBot

from datetime import datetime

class CollectPlayerBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.init()

        if __name__ == '__main__':
            self.telegram.send_message(text='player app start')

    def init(self):
        pass

    def update_player(self, realm, character_name):
        player_id = {
            'realm': realm,
            'character_name': character_name
        }
        player = self.db.find_player(player_id)
        if player is None:
            player = {
                '_id': player_id
            }
            self.db.insert_player(player)

        pets = self.api.bn_request(f"/profile/wow/character/{realm}/{character_name}/collections/pets", token=True, namespace="profile")
        if pets is not None and 'pets' in pets:
            self.db.update_player(player, {'pets': pets['pets']})

        mounts = self.api.bn_request(f"/profile/wow/character/{realm}/{character_name}/collections/mounts", token=True, namespace="profile")
        if mounts is not None and 'mounts' in mounts:
            self.db.update_player(player, {'mounts': mounts['mounts']})

    def on_schedule(self):
        try:
            now_ts = int(datetime.now().timestamp() * 1000)

            for char in self.db.list_doc('players', limit=10, project={ '_id': 1 }):
                self.update_player(char['_id']['realm'], char['_id']['character_name'])

            now_ts2 = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {now_ts2 - now_ts} ms')
        except Exception as e:
            self.print_error(e)

if __name__ == '__main__':
    CollectPlayerBot().on_schedule()
