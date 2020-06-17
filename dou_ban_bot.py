#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telegram_util import removeOldFiles, matchKey, cutCaption, clearUrl, splitCommand, log_on_fail, compactText
from telegram.ext import Updater, MessageHandler, Filters
import export_to_telegraph
import time
import yaml
from bs4 import BeautifulSoup
import cached_url
from db import DB
import threading

with open('credential') as f:
	credential = yaml.load(f, Loader=yaml.FullLoader)
export_to_telegraph.token = credential['telegraph_token']

tele = Updater(credential['bot_token'], use_context=True)
debug_group = tele.bot.get_chat(420074357)

db = DB()

def process(note, channels):
	if db.existing.add(note):
		return
	note = export_to_telegraph.export(note, force=True) or note
	for channel in channels:
		channel.send_message(note)

def getNotes(user_id, page=1):
	url = 'https://www.douban.com/people/%s/notes?p=%d' % (user_id, page)
	soup = BeautifulSoup(cached_url.get(url, sleep=20), 'html.parser')
	for item in soup.find_all('div', class_="note-container"):
		yield item['data-url']
		
@log_on_fail(debug_group)
def loopImp():
	removeOldFiles('tmp', day=0.1)
	for user_id in db.sub.subscriptions():
		channels = db.sub.channels(user_id)
		for note in getNotes(user_id)
			process(note, channels)

def backfill(chat_id):
	channels = [tele.bot.get_chat(chat_id)]
	for user_id in db.sub.sub.get(chat_id, []):
		page = 0
		while True:
			page += 1
			notes = list(getNotes(user_id, page))
			if not notes:
				return
			for note in notes:
				process(item, channels)
	tele.bot.get_chat(chat_id).send_message('finished backfill')

def doubanLoop():
	loopImp()
	threading.Timer(60 * 60 * 2, doubanLoop).start()

@log_on_fail(debug_group)
def handleCommand(update, context):
	msg = update.effective_message
	if not msg or not msg.text.startswith('/dbb'):
		return
	command, text = splitCommand(msg.text)
	if 'remove' in command:
		db.sub.remove(msg.chat_id, text)
	elif 'add' in command:
		db.sub.add(msg.chat_id, text)
	elif 'backfill' in command:
		backfill(msg.chat_id)
	msg.reply_text(db.sub.get(msg.chat_id), 
		parse_mode='markdown', disable_web_page_preview=True)

HELP_MESSAGE = '''
** Currently support notes only **

Commands:
/dbb_add - add douban user
/dbb_remove - remove douban user
/dbb_view - view subscription
/dbb_backfill - backfill 

Can be used in group/channel also.

Github： https://github.com/gaoyunzhi/douban_bot
'''

def handleHelp(update, context):
	update.message.reply_text(HELP_MESSAGE)

def handleStart(update, context):
	if 'start' in update.message.text:
		update.message.reply_text(HELP_MESSAGE)

if __name__ == '__main__':
	threading.Timer(1, doubanLoop).start() 
	dp = tele.dispatcher
	dp.add_handler(MessageHandler(Filters.command, handleCommand))
	dp.add_handler(MessageHandler(Filters.private & (~Filters.command), handleHelp))
	dp.add_handler(MessageHandler(Filters.private & Filters.command, handleStart), group=2)
	tele.start_polling()
	tele.idle()