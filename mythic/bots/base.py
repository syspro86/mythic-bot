from apscheduler.schedulers.blocking import BlockingScheduler
import traceback

from mythic.config import config
from mythic.logger import logger
from mythic.wowapi import WowApi
from mythic.db import MythicDatabase
from mythic.telegram import TelegramBot

class BaseBot(object):
    _api_ = None
    _db_ = None
    _telegram_ = None

    def __init__(self):
        if BaseBot._api_ is None:
            BaseBot._api_ = WowApi("kr", config.BATTLENET_API_ID, config.BATTLENET_API_SECRET)
        if BaseBot._db_ is None:
            BaseBot._db_ = MythicDatabase(config.MONGO_HOST, config.MONGO_DATABASE)
        if BaseBot._telegram_ is None:
            BaseBot._telegram_ = TelegramBot(polling=False)
        
        self.api = BaseBot._api_
        self.db = BaseBot._db_
        self.telegram = BaseBot._telegram_

    def on_schedule(self):
        pass

    def cron(self, **kwargs):
        sched = BlockingScheduler()
        sched.add_job(self.on_schedule, 'cron', **kwargs)
        sched.start()

    def print_error(self, e):
        traceback.print_exc()
        logger.info(e)
