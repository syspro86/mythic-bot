import sys
import subprocess
from mythic.bots.base import BaseBot
from mythic.bots.mythic import MythicBot
from mythic.bots.auction import CollectAuctionBot
from mythic.bots.index import CollectIndexBot
from mythic.bots.player import CollectPlayerBot
from mythic.bots.telegram import TelegramBot
from mythic.monitor.prom_exporter import MythicExporter

if __name__ == '__main__':
    bot = None
    if len(sys.argv) >= 2:
        bot = sys.argv[1]

    if bot == 'collect':
        MythicBot().cron(minute='*/10')
        # CollectAuctionBot().cron(minute='*/10')
        # CollectIndexBot().cron(hour='0')
        # CollectPlayerBot().cron(hour='*')
        BaseBot.start_cron()
    elif bot == 'telegram':
        TelegramBot().cron(hour='*')
        BaseBot.start_cron()
    elif bot == 'web':
        subprocess.call(
            ['gunicorn', 'mythic.web.app:app', '--timeout', '3600'])
    elif bot == 'prom':
        MythicExporter().start()
    else:
        # local test 용
        CollectIndexBot().on_schedule()
