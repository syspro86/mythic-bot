from apscheduler.schedulers.blocking import BlockingScheduler
import traceback

from mythic.config import config
from mythic.logger import logger
from mythic.wowapi import WowApi
from mythic.db import MythicDatabase as MythicDatabaseMongo
from mythic.db_oracle import MythicDatabase as MythicDatabaseOracle
from mythic.telegram import TelegramBot


class BaseBot(object):
    _region_ = None
    _api_ = None
    _db_ = None
    _telegram_ = None
    _sched_ = BlockingScheduler()

    def __init__(self):
        if BaseBot._region_ is None:
            BaseBot._region_ = config.BATTLENET_REGION
        if BaseBot._api_ is None:
            BaseBot._api_ = WowApi(
                BaseBot._region_, config.BATTLENET_API_ID, config.BATTLENET_API_SECRET)
        if True:  # BaseBot._db_ is None:
            if config.DB_TYPE == 'oracle':
                BaseBot._db_ = MythicDatabaseOracle(
                    config.ORACLE_DSN, config.ORACLE_USER, config.ORACLE_PASSWORD, config.ORACLE_CLIENT_PATH)
            elif config.DB_TYPE == 'mongo':
                BaseBot._db_ = MythicDatabaseMongo(
                    config.MONGO_HOST, config.MONGO_DATABASE)
        if BaseBot._telegram_ is None:
            BaseBot._telegram_ = TelegramBot(polling=False)

        self.api = BaseBot._api_
        self.db = BaseBot._db_
        self.telegram = BaseBot._telegram_

    def on_schedule(self):
        pass

    @classmethod
    def start_cron(cls):
        BaseBot._sched_.start()

    def cron(self, **kwargs):
        BaseBot._sched_.add_job(self.on_schedule, 'cron', **kwargs)

    def print_error(self, e):
        traceback.print_exc()
        logger.info(e)
