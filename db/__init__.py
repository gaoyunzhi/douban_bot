import os
import yaml
from telegram_util import commitRepo

def getFile(name):
	fn = 'db/' + name
	os.system('touch ' + fn)
	with open(fn) as f:
		return set([x.strip() for x in f.readlines() if x.strip()])

class DBItem(object):
	def __init__(self, name):
		self.items = getFile(name)
		self.fn = 'db/' + name
		print(self.items)

	def add(self, x):
		x = str(x).strip()
		if not x or x in self.items:
			return False
		self.items.add(x)
		with open(self.fn, 'a') as f:
			f.write('\n' + x)
		return True

def normalizeUser(text):
	if not text:
		return
	return text.strip('/').split('/')[-1]

class Subscription(object):
	def __init__(self):
		with open('db/subscription') as f:
			self.sub = yaml.load(f, Loader=yaml.FullLoader)

	def add(self, chat_id, text):
		text = normalizeUser(text)
		if not text:
			return
		self.sub[chat_id] = self.sub.get(chat_id, []) + [text]
		self.save()

	def remove(self, chat_id, text):
		text = normalizeUser(text)
		if not text:
			return
		self.sub[chat_id] = self.sub.get(chat_id, [])
		try:
			self.sub[chat_id].remove(text)
		except:
			...
		self.save()

	def get(self, chat_id):
		return 'subscriptions: ' + ' '.join([
			'[%s](%s)' % (user_id, 'https://www.douban.com/people/' + user_id)
			for user_id in self.sub.get(chat_id, [])])

	def subscriptions(self):
		result = set()
		for chat_id in self.sub:
			for item in self.sub.get(chat_id, []):
				result.add(item)
		return result

	def channels(self, user_id, bot):
		for chat_id in self.sub:
			if user_id in self.sub.get(chat_id, []):
				try:
					yield bot.get_chat(chat_id)
				except:
					...

	def save(self):
		with open('db/subscription', 'w') as f:
			f.write(yaml.dump(self.sub, sort_keys=True, indent=2, allow_unicode=True))
		commitRepo(delay_minute=0)

class DB(object):
	def __init__(self):
		self.reload()

	def reload(self):
		self.existing = DBItem('existing')
		self.sub = Subscription()
