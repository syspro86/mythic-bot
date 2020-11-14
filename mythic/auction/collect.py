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

        self.telegram = TelegramBot()
        self.telegram.send_message(text='app start')

        self.db = AuctionDatabase(config.MONGO_HOST, config.MONGO_DATABASE)

    def update_auction_list(self, realm_id):
        now_ts = int(datetime.now().timestamp() * 1000)
        auctions = self.api.bn_request(f"/data/wow/connected-realm/{realm_id}/auctions?" + self.api.postfix_parameter("dynamic"))
        #logger.info(json.dumps(auctions))
        if auctions is None:
            return

        if 'auctions' not in auctions:
            return
        
        for auction in auctions['auctions']:
            auction['_id'] = auction['id']
            auc = self.db.find_auction(auction['_id'])
            if auc is None:
                auction['first_seen_ts'] = now_ts
                auction['last_seen_ts'] = now_ts
                self.db.insert_auction(auction)
            else:
                self.db.update_auction(auc, {'last_seen_ts': now_ts})
        
        for auction in auctions['auctions']:
            item_id = auction['item']['id']

            item = self.db.find_item(item_id)
            if item is None:
                item = self.update_item(item_id)

    def update_item(self, item_id):
        item = self.api.bn_request(f"/data/wow/item/{item_id}?" + self.api.postfix_parameter("static"))
        if item is not None:
            item['_id'] = item['id']
            self.db.insert_item(item)
        return item

    def bot_work(self):
        self.update_auction_list(2116)
        return

    def start(self, **kwargs):
        sched = BlockingScheduler()
        sched.add_job(self.bot_work,'cron', **kwargs)
        sched.start()

if __name__ == '__main__':
    #CollectAuctionBot().start(minute='*/10')
    CollectAuctionBot().bot_work()
