# -*- coding:utf-8 -*-
## src/common/pep.py
##
## Copyright (C) 2007 Piotr Gaczkowski <doomhammerng AT gmail.com>
## Copyright (C) 2007-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jean-Marie Traissard <jim AT lapin.org>
##                    Jonathan Schleifer <js-common.gajim AT webkeks.org>
##                    Stephan Erb <steve-e AT h3c.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import common.gajim
from common import xmpp

MOODS = {
	'afraid':			_('Afraid'),
	'amazed':			_('Amazed'),
	'amorous':			_('Amorous'),
	'angry':				_('Angry'),
	'annoyed':			_('Annoyed'),
	'anxious':			_('Anxious'),
	'aroused':			_('Aroused'),
	'ashamed':			_('Ashamed'),
	'bored':				_('Bored'),
	'brave':				_('Brave'),
	'calm':				_('Calm'),
	'cautious':			_('Cautious'),
	'cold':				_('Cold'),
	'confident':		_('Confident'),
	'confused':			_('Confused'),
	'contemplative':	_('Contemplative'),
	'contented':		_('Contented'),
	'cranky':			_('Cranky'),
	'crazy':				_('Crazy'),
	'creative':			_('Creative'),
	'curious':			_('Curious'),
	'dejected':			_('Dejected'),
	'depressed':		_('Depressed'),
	'disappointed':	_('Disappointed'),
	'disgusted':		_('Disgusted'),
	'dismayed':			_('Dismayed'),
	'distracted':		_('Distracted'),
	'embarrassed':		_('Embarrassed'),
	'envious':			_('Envious'),
	'excited':			_('Excited'),
	'flirtatious':		_('Flirtatious'),
	'frustrated':		_('Frustrated'),
	'grateful':			_('Grateful'),
	'grieving':			_('Grieving'),
	'grumpy':			_('Grumpy'),
	'guilty':			_('Guilty'),
	'happy':				_('Happy'),
	'hopeful':			_('Hopeful'),
	'hot':				_('Hot'),
	'humbled':			_('Humbled'),
	'humiliated':		_('Humiliated'),
	'hungry':			_('Hungry'),
	'hurt':				_('Hurt'),
	'impressed':		_('Impressed'),
	'in_awe':			_('In Awe'),
	'in_love':			_('In Love'),
	'indignant':		_('Indignant'),
	'interested':		_('Interested'),
	'intoxicated':		_('Intoxicated'),
	'invincible':		_('Invincible'),
	'jealous':			_('Jealous'),
	'lonely':			_('Lonely'),
	'lost':				_('Lost'),
	'lucky':				_('Lucky'),
	'mean':				_('Mean'),
	'moody':				_('Moody'),
	'nervous':			_('Nervous'),
	'neutral':			_('Neutral'),
	'offended':			_('Offended'),
	'outraged':			_('Outraged'),
	'playful':			_('Playful'),
	'proud':				_('Proud'),
	'relaxed':			_('Relaxed'),
	'relieved':			_('Relieved'),
	'remorseful':		_('Remorseful'),
	'restless':			_('Restless'),
	'sad':				_('Sad'),
	'sarcastic':		_('Sarcastic'),
	'satisfied':		_('Satisfied'),
	'serious':			_('Serious'),
	'shocked':			_('Shocked'),
	'shy':				_('Shy'),
	'sick':				_('Sick'),
	'sleepy':			_('Sleepy'),
	'spontaneous':		_('Spontaneous'),
	'stressed':			_('Stressed'),
	'strong':			_('Strong'),
	'surprised':		_('Surprised'),
	'thankful':			_('Thankful'),
	'thirsty':			_('Thirsty'),
	'tired':				_('Tired'),
	'undefined':		_('Undefined'),
	'weak':				_('Weak'),
	'worried':			_('Worried')}

ACTIVITIES = {
	'doing_chores': {'category':			_('Doing Chores'),
		'buying_groceries':					_('Buying Groceries'),
		'cleaning':								_('Cleaning'),
		'cooking':								_('Cooking'),
		'doing_maintenance':					_('Doing Maintenance'),
		'doing_the_dishes':					_('Doing the Dishes'),
		'doing_the_laundry':					_('Doing the Laundry'),
		'gardening':							_('Gardening'),
		'running_an_errand':					_('Running an Errand'),
		'walking_the_dog':					_('Walking the Dog')},
	'drinking': {'category':				_('Drinking'),
		'having_a_beer':						_('Having a Beer'),
		'having_coffee':						_('Having Coffee'),
		'having_tea':							_('Having Tea')},
	'eating': {'category':					_('Eating'),
		'having_a_snack':						_('Having a Snack'),
		'having_breakfast':					_('Having Breakfast'),
		'having_dinner':						_('Having Dinner'),
		'having_lunch':						_('Having Lunch')},
	'exercising': {'category':				_('Exercising'),
		'cycling':								_('Cycling'),
		'dancing':								_('Dancing'),
		'hiking':								_('Hiking'),
		'jogging':								_('Jogging'),
		'playing_sports':						_('Playing Sports'),
		'running':								_('Running'),
		'skiing':								_('Skiing'),
		'swimming':								_('Swimming'),
		'working_out':							_('Working out')},
	'grooming': {'category':				_('Grooming'),
		'at_the_spa':							_('At the Spa'),
		'brushing_teeth':						_('Brushing Teeth'),
		'getting_a_haircut':					_('Getting a Haircut'),
		'shaving':								_('Shaving'),
		'taking_a_bath':						_('Taking a Bath'),
		'taking_a_shower':					_('Taking a Shower')},
	'having_appointment': {'category':	_('Having an Appointment')},
	'inactive': {'category':				_('Inactive'),
		'day_off':								_('Day Off'),
		'hanging_out':							_('Hanging out'),
		'hiding':								_('Hiding'),
		'on_vacation':							_('On Vacation'),
		'praying':								_('Praying'),
		'scheduled_holiday':					_('Scheduled Holiday'),
		'sleeping':								_('Sleeping'),
		'thinking':								_('Thinking')},
	'relaxing': {'category':				_('Relaxing'),
		'fishing':								_('Fishing'),
		'gaming':								_('Gaming'),
		'going_out':							_('Going out'),
		'partying':								_('Partying'),
		'reading':								_('Reading'),
		'rehearsing':							_('Rehearsing'),
		'shopping':								_('Shopping'),
		'smoking':								_('Smoking'),
		'socializing':							_('Socializing'),
		'sunbathing':							_('Sunbathing'),
		'watching_tv':							_('Watching TV'),
		'watching_a_movie':					_('Watching a Movie')},
	'talking': {'category':					_('Talking'),
		'in_real_life':						_('In Real Life'),
		'on_the_phone':						_('On the Phone'),
		'on_video_phone':						_('On Video Phone')},
	'traveling': {'category':				_('Traveling'),
		'commuting':							_('Commuting'),
		'cycling':								_('Cycling'),
		'driving':								_('Driving'),
		'in_a_car':								_('In a Car'),
		'on_a_bus':								_('On a Bus'),
		'on_a_plane':							_('On a Plane'),
		'on_a_train':							_('On a Train'),
		'on_a_trip':							_('On a Trip'),
		'walking':								_('Walking')},
	'working': {'category':					_('Working'),
		'coding':								_('Coding'),
		'in_a_meeting':						_('In a Meeting'),
		'studying':								_('Studying'),
		'writing':								_('Writing')}}

TUNE_DATA = ['artist', 'title', 'source', 'track', 'length']

import logging
log = logging.getLogger('gajim.c.pep')

import helpers
import atom


class AbstractPEP(object):
	
	type = ''
	namespace = ''
		
	@classmethod
	def get_tag_as_PEP(cls, jid, account, event_tag):
		items = event_tag.getTag('items', {'node': cls.namespace})
		if items:
			log.debug("Received PEP 'user %s' from %s" % (cls.type, jid)) 
			return cls(jid, account, items)
		else:
			return None 
	
	def __init__(self, jid, account, items):
		self._pep_specific_data, self._retracted = self._extract_info(items)
		self.do(jid, account)
	
	def _extract_info(self, items):
		'''To be implemented by subclasses'''
		raise NotImplementedError
	
class UserMoodPEP(AbstractPEP):
	'''XEP-0107: User Mood'''
	
	type = 'mood'
	namespace = common.xmpp.NS_MOOD
		
	def _extract_info(self, items):
		mood_dict = {}
		
		for item in items.getTags('item'):
			mood_tag = item.getTag('mood')
			if mood_tag:
				for child in mood_tag.getChildren():
					name = child.getName().strip()
					if name == 'text':
						mood_dict['text'] = child.getData()
					elif name in MOODS :
						mood_dict['mood'] = name
						
		retracted = items.getTag('retract') or not mood_dict		
		return (mood_dict, retracted)

	def do(self, jid, name):
		mood_dict = {} if self._retracted else self._pep_specific_data 
	
		if jid == common.gajim.get_jid_from_account(name):
			acc = common.gajim.connections[name]
			acc.mood = mood_dict
	
		user = common.gajim.get_room_and_nick_from_fjid(jid)[0]
		for contact in common.gajim.contacts.get_contacts(name, user):
			contact.mood = mood_dict
	
		if jid == common.gajim.get_jid_from_account(name):
			common.gajim.interface.roster.draw_account(name)
		common.gajim.interface.roster.draw_mood(user, name)
		ctrl = common.gajim.interface.msg_win_mgr.get_control(user, name)
		if ctrl:
			ctrl.update_mood()
		

class UserTunePEP(AbstractPEP):
	'''XEP-0118: User Tune'''
	
	type = 'tune'
	namespace = common.xmpp.NS_TUNE
					
	def _extract_info(self, items):		
		tune_dict = {}
	
		for item in items.getTags('item'):
			tune_tag = item.getTag('tune')
			if tune_tag:
				for child in tune_tag.getChildren():
					name = child.getName().strip()
					data = child.getData().strip()
					if child.getName() in TUNE_DATA:
						tune_dict[name] = data
						
		retracted = items.getTag('retract') or not tune_dict
		return (tune_dict, retracted)
		
					
	def do(self, jid, name):
		tune_dict = {} if self._retracted else self._pep_specific_data 

		if jid == common.gajim.get_jid_from_account(name):
			acc = common.gajim.connections[name]
			acc.tune = tune_dict
	
		user = common.gajim.get_room_and_nick_from_fjid(jid)[0]
		for contact in common.gajim.contacts.get_contacts(name, user):
			contact.tune = tune_dict
	
		if jid == common.gajim.get_jid_from_account(name):
			common.gajim.interface.roster.draw_account(name)
		common.gajim.interface.roster.draw_tune(user, name)
		ctrl = common.gajim.interface.msg_win_mgr.get_control(user, name)
		if ctrl:
			ctrl.update_tune()
		

class UserActivityPEP(AbstractPEP):
	'''XEP-0108: User Activity'''
	
	type = 'activity'
	namespace = common.xmpp.NS_ACTIVITY
			
	def _extract_info(self, items):
		activity_dict = {}
		
		for item in items.getTags('item'):
			activity_tag = item.getTag('activity')
			if activity_tag:
				for child in activity_tag.getChildren():
					name = child.getName().strip()
					data = child.getData().strip()
					if name == 'text':
						activity_dict['text'] = data
					elif name in ACTIVITIES:
						activity_dict['activity'] = name
						for subactivity in child.getChildren():
							subactivity_name = subactivity.getName().strip()
							if subactivity_name in ACTIVITIES[name]:
								activity_dict['subactivity'] = subactivity_name
		
		retracted = items.getTag('retract') or not activity_dict
		return (activity_dict, retracted)
		
	def do(self, jid, name):
		activity_dict = {} if self._retracted else self._pep_specific_data

		if jid == common.gajim.get_jid_from_account(name):
			acc = common.gajim.connections[name]
			acc.activity = activity_dict
	
		user = common.gajim.get_room_and_nick_from_fjid(jid)[0]
		for contact in common.gajim.contacts.get_contacts(name, user):
			contact.activity = activity_dict
	
		if jid == common.gajim.get_jid_from_account(name):
			common.gajim.interface.roster.draw_account(name)
		common.gajim.interface.roster.draw_activity(user, name)
		ctrl = common.gajim.interface.msg_win_mgr.get_control(user, name)
		if ctrl:
			ctrl.update_activity()
	
	
class UserNicknamePEP(AbstractPEP):
	'''XEP-0172: User Nickname'''
	
	type = 'activity'
	namespace = common.xmpp.NS_NICK
			
	def _extract_info(self, items):	
		nick = ''
		for item in items.getTags('item'):
			child = item.getTag('nick')
			if child:
				nick = child.getData()
				break
		
		retracted = items.getTag('retract') or not nick
		return (nick, retracted)		
			
	def do(self, jid, name):
		if jid == common.gajim.get_jid_from_account(name):
			if self._retracted:
				common.gajim.nicks[name] = common.gajim.config.get_per('accounts',
					name, 'name')
			else:
				common.gajim.nicks[name] = self._pep_specific_data
	
		nick = '' if self._retracted else self._pep_specific_data
		
		user = common.gajim.get_room_and_nick_from_fjid(jid)[0]
		for contact in common.gajim.contacts.get_contacts(name, user):
			contact.contact_name = nick
			common.gajim.interface.roster.draw_contact(user, name)
	
			ctrl = common.gajim.interface.msg_win_mgr.get_control(user, name)
			if ctrl:
				ctrl.update_ui()
				win = ctrl.parent_win
				win.redraw_tab(ctrl)
				win.show_title()
		
		
SUPPORTED_PERSONAL_USER_EVENTS = [UserMoodPEP, UserTunePEP, UserActivityPEP, UserNicknamePEP]

class ConnectionPEP:
	
	def _pubsubEventCB(self, xmpp_dispatcher, msg):
		''' Called when we receive <message /> with pubsub event. '''
		if msg.getTag('error'):
			log.warning('PubsubEventCB received error stanza')
			return
				
		# TODO: Logging? (actually services where logging would be useful, should
		# TODO: allow to access archives remotely...)
		jid = helpers.get_full_jid_from_iq(msg)
		event_tag = msg.getTag('event')

		for pep_class in SUPPORTED_PERSONAL_USER_EVENTS:
			pep = pep_class.get_tag_as_PEP(jid, self.name, event_tag)
			if pep:
				self.dispatch('PEP_RECEIVED', (pep.type, pep))
		
		items = event_tag.getTag('items')
		if items is None: return

		for item in items.getTags('item'):
			entry = item.getTag('entry')
			if entry is not None:
				# for each entry in feed (there shouldn't be more than one,
				# but to be sure...
				self.dispatch('ATOM_ENTRY', (atom.OldEntry(node=entry),))
				continue
			# unknown type... probably user has another client who understands that event
			
		raise common.xmpp.NodeProcessed


def user_send_mood(account, mood, message=''):
	if not common.gajim.connections[account].pep_supported:
		return
	item = xmpp.Node('mood', {'xmlns': xmpp.NS_MOOD})
	if mood != '':
		item.addChild(mood)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	common.gajim.connections[account].send_pb_publish('', xmpp.NS_MOOD, item,
		'0')

def user_send_activity(account, activity, subactivity='', message=''):
	if not common.gajim.connections[account].pep_supported:
		return
	item = xmpp.Node('activity', {'xmlns': xmpp.NS_ACTIVITY})
	if activity != '':
		i = item.addChild(activity)
	if subactivity != '':
		i.addChild(subactivity)
	if message != '':
		i = item.addChild('text')
		i.addData(message)

	common.gajim.connections[account].send_pb_publish('', xmpp.NS_ACTIVITY, item,
		'0')

def user_send_tune(account, artist='', title='', source='', track=0, length=0,
items=None):
	if not (common.gajim.config.get_per('accounts', account, 'publish_tune') and\
	common.gajim.connections[account].pep_supported):
		return
	item = xmpp.Node('tune', {'xmlns': xmpp.NS_TUNE})
	if artist != '':
		i = item.addChild('artist')
		i.addData(artist)
	if title != '':
		i = item.addChild('title')
		i.addData(title)
	if source != '':
		i = item.addChild('source')
		i.addData(source)
	if track != 0:
		i = item.addChild('track')
		i.addData(track)
	if length != 0:
		i = item.addChild('length')
		i.addData(length)
	if items is not None:
		item.addChild(payload=items)

	common.gajim.connections[account].send_pb_publish('', xmpp.NS_TUNE, item,
		'0')

def user_send_nickname(account, nick):
	if not common.gajim.connections[account].pep_supported:
		return
	item = xmpp.Node('nick', {'xmlns': xmpp.NS_NICK})
	item.addData(nick)

	common.gajim.connections[account].send_pb_publish('', xmpp.NS_NICK, item,
		'0')

def user_retract_mood(account):
	common.gajim.connections[account].send_pb_retract('', xmpp.NS_MOOD, '0')

def user_retract_activity(account):
	common.gajim.connections[account].send_pb_retract('', xmpp.NS_ACTIVITY, '0')

def user_retract_tune(account):
	common.gajim.connections[account].send_pb_retract('', xmpp.NS_TUNE, '0')

def user_retract_nickname(account):
	common.gajim.connections[account].send_pb_retract('', xmpp.NS_NICK, '0')

def delete_pep(jid, name):
	user = common.gajim.get_room_and_nick_from_fjid(jid)[0]

	if jid == common.gajim.get_jid_from_account(name):
		acc = common.gajim.connections[name]
		del acc.activity
		acc.activity = {}
		user_send_tune(name)
		del acc.tune
		acc.tune = {}
		del acc.mood
		acc.mood = {}

	for contact in common.gajim.contacts.get_contacts(name, user):
		del contact.activity
		contact.activity = {}
		del contact.tune
		contact.tune = {}
		del contact.mood
		contact.mood = {}

	if jid == common.gajim.get_jid_from_account(name):
		common.gajim.interface.roster.draw_account(name)

	common.gajim.interface.roster.draw_activity(user, name)
	common.gajim.interface.roster.draw_tune(user, name)
	common.gajim.interface.roster.draw_mood(user, name)
	ctrl = common.gajim.interface.msg_win_mgr.get_control(user, name)
	if ctrl:
		ctrl.update_activity()
		ctrl.update_tune()
		ctrl.update_mood()

# vim: se ts=3:
