from mythic.config import config
from mythic.logger import logger

import json
import telegram
from telegram.ext import Filters, MessageHandler, Updater

class TelegramBot:
    def __init__(self, polling=True):
        self.bot = telegram.Bot(token=config.TELEGRAM_TOKEN) if config.TELEGRAM_TOKEN is not None else None
        self.chatId = config.ADMIN_CHAT_ID

        if polling:
            self.updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
            text_handler = MessageHandler(Filters.text, self.on_text)
            self.updater.dispatcher.add_handler(text_handler)
            self.updater.start_polling()

        self.callback = []

    def add_callback(self, cb):
        self.callback.append(cb)

    def on_text(self, update, context):
        message = update.message
        chat_id = message.chat.id if message is not None else None

        if chat_id is None or message.text is None:
            return

        for cb in self.callback:
            cb(chat_id, message.text)

    def send_message(self, **kwargs):
        if self.bot is None:
            if 'text' in kwargs:
                logger.info(kwargs['text'])
            return

        if 'chat_id' not in kwargs.keys():
            kwargs['chat_id'] = self.chatId
        
        self.bot.sendMessage(**kwargs)

if __name__ == '__main__':
    TelegramBot().send_message(text='test')
    import time
    time.sleep(100)
