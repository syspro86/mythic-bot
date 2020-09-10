from mythic.config import config
from mythic.logger import logger

import telegram

class TelegramBot:
    def __init__(self):
        self.bot = telegram.Bot(token=config.TELEGRAM_TOKEN) if config.TELEGRAM_TOKEN is not None else None
        self.chatId = config.ADMIN_CHAT_ID

    def sendMessage(self, **kwargs):
        if self.bot is None:
            if 'text' in kwargs:
                logger.info(kwargs['text'])
            return

        if 'chat_id' not in kwargs.keys():
            kwargs['chat_id'] = self.chatId
        
        self.bot.sendMessage(**kwargs)

