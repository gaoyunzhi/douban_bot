#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telegram_util import removeOldFiles, matchKey, cutCaption, clearUrl, splitCommand, log_on_fail, compactText
from telegram.ext import Updater, MessageHandler, Filters
import export_to_telegraph
import time
import yaml
import web_2_album
import album_sender
import BeautifulSoup
import cached_url
from db import DB
import threading

with open('credential') as f:
	credential = yaml.load(f, Loader=yaml.FullLoader)
export_to_telegraph.token = credential['telegraph_token']

tele = Updater(credential['bot_token'], use_context=True)
debug_group = tele.bot.get_chat(420074357)

db = DB()

def getSource(item):
	new_status = item
	while 'new-status' not in new_status.get('class'):
		new_status = new_status.parent
	if new_status.get('data-sid'):
		return 'https://www.douban.com/people/%s/status/%s/' % \
			(new_status['data-uid'], new_status['data-sid'])

def getCap(quote, url):
	if '_' in url:
		url = '[%s](%s)' % (url, url)
	return cutCaption(quote, url, 4000)

def getResult(post_link, item):
	raw_quote = item.find('blockquote') or ''
	quote = export_to_telegraph.exportAllInText(raw_quote)
	quote = compactText(quote).strip('更多转发...').strip()

	r = web_2_album.Result()

	note = item.find('div', class_='note-block')
	if (note and note.get('data-url')) or matchKey(post_link, 
			['https://book.douban.com/review/', 'https://www.douban.com/note/']):
		note = (note and note.get('data-url')) or post_link
		url = export_to_telegraph.export(note, force=True) or note
		r.cap = getCap(quote, url)
		return r

	if item.find('div', class_='url-block'):
		url = item.find('div', class_='url-block')
		url = url.find('a')['href']
		url = clearUrl(export_to_telegraph.export(url) or url)
		r.cap = getCap(quote, url)
		return r

	if '/status/' in post_link:
		r = web_2_album.get(post_link, force_cache=True)
		r.cap = quote
		if r.imgs:
			return r

	if quote and raw_quote.find('a', title=True, href=True):
		r.cap = quote
		return r

def process(item, channels):
	try:
		post_link = item.find('span', class_='created_at').find('a')['href']
	except:
		return
	source = getSource(item) or post_link

	if db.existing.add(source) or db.existing.add(post_link):
		return

	result = getResult(post_link, item)
	if not result:
		return

	for channel in channels:
		time.sleep(20)
		album_sender.send(channel, source, result)

@log_on_fail(debug_group)
def loopImp():
	removeOldFiles('tmp', day=0.1)
	for user_id in db.sub.subscriptions():
		channels = db.sub.channels(user_id)
		url = 'https://www.douban.com/people/%s/statuses' % user_id
		soup = BeautifulSoup(cached_url.get(url, sleep=20), 'html.parser')
		for item in soup.find_all('div', class_='status-item'):
			process(item, channels)

def backfill(chat_id):
	channels = [tele.bot.get_chat(chat_id)]
	for user_id in db.sub.sub.get(chat_id, []):
		url_prefix = 'https://www.douban.com/people/%s/statuses' % user_id
		page = 0
		while True:
			page += 1
			url = url_prefix + '?p=' + str(page)
			soup = BeautifulSoup(cached_url.get(url_prefix, sleep=20), 'html.parser')
			items = list(soup.find_all('div', class_='status-item'))
			if not items:
				return
			for item in items:
				process(item, channels)

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