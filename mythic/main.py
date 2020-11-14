import sys
from mythic.leaderboard.collect import MythicBot
from mythic.auction.collect import CollectAuctionBot
from mythic.pet.collect import CollectPetBot

if __name__ == '__main__':
    bot = 'leaderboard'
    if len(sys.argv) >= 2:
        bot = sys.argv[1]
    
    if bot == 'leaderboard':
        MythicBot().start(minute='*/10')
    elif bot == 'auction':
        CollectAuctionBot().start(minute='*/10')
    elif bot == 'pet':
        CollectPetBot().start(hour='*')
