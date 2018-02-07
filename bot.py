from telegram.ext import Updater, CommandHandler


class Bot:
    def __init__(self, token, db):
        self.updater = Updater(token)
        self.updater.dispatcher.add_handler(CommandHandler('ping', self.ping))
        self.updater.dispatcher.add_handler(CommandHandler('watch', self.watch))
        self.db = db

    def run(self):
        self.updater.start_polling()
        self.updater.idle()

    def ping(self, bot, update):
        update.message.reply_text('PONG')

    def watch(self, bot, update):
        update.message.reply_text('NOT IMPLEMENTED')
