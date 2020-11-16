from mythic.config import config
from mythic.logger import logger
from mythic.bots.base import BaseBot

from datetime import datetime

class CollectAuctionBot(BaseBot):
    def __init__(self):
        super().__init__()

        self.telegram.send_message(text='app start')

        self.connected_realms = []
        crealms = self.api.bn_request(f"/data/wow/connected-realm/index", token=True, namespace="dynamic")
        for cr in crealms['connected_realms']:
            crealm = self.api.bn_request(cr['href'], token=True)
            self.connected_realms.append(crealm)

    def update_auction_list(self, realm_id):
        now_ts = int(datetime.now().timestamp() * 1000)
        auctions = self.api.bn_request(f"/data/wow/connected-realm/{realm_id}/auctions", token=True, namespace="dynamic")
        #logger.info(json.dumps(auctions))
        if auctions is None:
            return

        if 'auctions' not in auctions:
            return
        
        auctions = auctions['auctions']

        for auction in auctions:
            auction['_id'] = auction['id']
            auction['realm_id'] = realm_id
            auction['first_seen_ts'] = now_ts
        
        for i in range(0, len(auctions), 10000):
            split = auctions[i:i+10000]
            try:
                self.db.insert_many('auctions', split, ordered=False)
            except Exception as e:
                print(type(e))

            keys = list(map(lambda r: r['_id'], split))
            self.db.update_many('auctions',
                { '_id': { '$in': keys } },
                { '$set': { 'last_seen_ts': now_ts } })
        
        item_ids = sorted(list(set(map(lambda r: r['item']['id'], auctions))))
        for item_id in item_ids:
            self.update_item(item_id)

    def update_item(self, item_id):
        item = self.db.find_item(item_id)
        if item is None:
            item = self.api.bn_request(f"/data/wow/item/{item_id}", token=True, namespace="static")
            if item is not None:
                item['_id'] = item['id']
                self.db.insert_item(item)
                logger.info(f"new item {item['_id']}")
        
        if item is not None:
            if 'key' in item['media']:
                item_media = self.api.bn_request(item['media']['key']['href'], token=True)
                if item_media is not None:
                    item['media'] = item_media
                    self.db.update_item(item, {'media': item['media']})
                    logger.info(f"item media updated {item['_id']}")
        
        return item

    def on_schedule(self):
        try:
            now_ts = int(datetime.now().timestamp() * 1000)

            for cr in self.connected_realms:
                self.update_auction_list(cr['id'])

            now_ts2 = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {now_ts2 - now_ts} ms')
        except Exception as e:
            self.print_error(e)

if __name__ == '__main__':
    CollectAuctionBot().on_schedule()
