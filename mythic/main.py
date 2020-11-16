import sys
import subprocess
from mythic.bots.mythic import MythicBot
from mythic.bots.auction import CollectAuctionBot
from mythic.bots.index import CollectIndexBot
from mythic.bots.player import CollectPlayerBot

if __name__ == '__main__':
    bot = 'mythic'
    if len(sys.argv) >= 2:
        bot = sys.argv[1]
    
    if bot == 'mythic':
        MythicBot().cron(minute='*/10')
    elif bot == 'auction':
        CollectAuctionBot().cron(minute='*/10')
    elif bot == 'index':
        CollectIndexBot().cron(hour='0')
    elif bot == 'player':
        CollectPlayerBot().cron(hour='*')
    elif bot == 'web':
        subprocess.call(['gunicorn', 'mythic.web.app:app', '--timeout', '200'])
