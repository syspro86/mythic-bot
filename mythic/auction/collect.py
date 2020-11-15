from mythic.config import config
from mythic.logger import logger
from mythic.telegram import TelegramBot
from mythic.wowapi import WowApi
from mythic.auction.db import AuctionDatabase

from apscheduler.schedulers.blocking import BlockingScheduler
import base64
from datetime import datetime
import hashlib
import json
import requests
import textwrap
import traceback

class CollectAuctionBot(object):
    def __init__(self):
        self.api = WowApi("kr", config.BATTLENET_API_ID, config.BATTLENET_API_SECRET)

        self.telegram = TelegramBot(polling=False)
        self.telegram.send_message(text='app start')

        self.db = AuctionDatabase(config.MONGO_HOST, config.MONGO_DATABASE)

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
        
        for auction in auctions['auctions']:
            auction['_id'] = auction['id']
            auc = self.db.find_auction(auction['_id'])
            if auc is None:
                auction['realm_id'] = realm_id
                auction['first_seen_ts'] = now_ts
                auction['last_seen_ts'] = now_ts
                self.db.insert_auction(auction)
                logger.info(f"new auction item {auction['_id']}")
            else:
                self.db.update_auction(auc, {'last_seen_ts': now_ts})
        
        for auction in auctions['auctions']:
            item_id = auction['item']['id']
            item = self.update_item(item_id)

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

    def bot_work(self):
        try:
            now_ts = int(datetime.now().timestamp() * 1000)

            for cr in self.connected_realms:
                self.update_auction_list(cr['id'])

            now_ts2 = int(datetime.now().timestamp() * 1000)
            logger.info(f'collected in {now_ts2 - now_ts} ms')
        except Exception as e:
            traceback.print_exc()
            logger.info(e)

    def start(self, **kwargs):
        sched = BlockingScheduler()
        sched.add_job(self.bot_work,'cron', **kwargs)
        sched.start()

if __name__ == '__main__':
    #CollectAuctionBot().start(minute='*/10')
    CollectAuctionBot().bot_work()
