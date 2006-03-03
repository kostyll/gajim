##	common/connection.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

# kind of events we can wait for an answer
VCARD_PUBLISHED = 'vcard_published'
VCARD_ARRIVED = 'vcard_arrived'

import sys
import sha
import os
import time
import sre
import traceback
import select
import socket
import random
random.seed()
import signal
import base64
if os.name != 'nt':
	signal.signal(signal.SIGPIPE, signal.SIG_DFL)

from calendar import timegm

import common.xmpp

from common import helpers
from common import gajim
from common import GnuPG
import socks5
USE_GPG = GnuPG.USE_GPG

from common import i18n
_ = i18n._

HAS_IDLE = True
try:
	import common.idle as idle # when we launch gajim from sources
except:
	try:
		import idle # when Gajim is installed
	except:
		gajim.log.debug(_('Unable to load idle module'))
		HAS_IDLE = False

STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
	'invisible']

distro_info = {
	'Arch Linux': '/etc/arch-release',
	'Aurox Linux': '/etc/aurox-release',
	'Conectiva Linux': '/etc/conectiva-release',
	'CRUX': '/usr/bin/crux',
	'Debian GNU/Linux': '/etc/debian_release',
	'Debian GNU/Linux': '/etc/debian_version',
	'Fedora Linux': '/etc/fedora-release',
	'Gentoo Linux': '/etc/gentoo-release',
	'Linux from Scratch': '/etc/lfs-release',
	'Mandrake Linux': '/etc/mandrake-release',
	'Slackware Linux': '/etc/slackware-release',
	'Slackware Linux': '/etc/slackware-version',
	'Solaris/Sparc': '/etc/release',
	'Source Mage': '/etc/sourcemage_version',
	'SUSE Linux': '/etc/SuSE-release',
	'Sun JDS': '/etc/sun-release',
	'PLD Linux': '/etc/pld-release',
	'Yellow Dog Linux': '/etc/yellowdog-release',
	# many distros use the /etc/redhat-release for compatibility
	# so Redhat is the last
	'Redhat Linux': '/etc/redhat-release'
}

def get_os_info():
	if os.name == 'nt':
		ver = os.sys.getwindowsversion()
		ver_format = ver[3], ver[0], ver[1]
		win_version = {
			(1, 4, 0): '95',
			(1, 4, 10): '98',
			(1, 4, 90): 'ME',
			(2, 4, 0): 'NT',
			(2, 5, 0): '2000',
			(2, 5, 1): 'XP',
			(2, 5, 2): '2003'
		}
		if win_version.has_key(ver_format):
			return 'Windows' + ' ' + win_version[ver_format]
		else:
			return 'Windows'
	elif os.name == 'posix':
		executable = 'lsb_release'
		params = ' --id --codename --release --short'
		full_path_to_executable = helpers.is_in_path(executable, return_abs_path = True)
		if full_path_to_executable:
			command = executable + params
			child_stdin, child_stdout = os.popen2(command)
			output = helpers.temp_failure_retry(child_stdout.readline).strip()
			child_stdout.close()
			child_stdin.close()
			# some distros put n/a in places so remove them
			pattern = sre.compile(r' n/a', sre.IGNORECASE)
			output = sre.sub(pattern, '', output)
			return output

		# lsb_release executable not available, so parse files
		for distro_name in distro_info:
			path_to_file = distro_info[distro_name]
			if os.path.exists(path_to_file):
				if os.access(path_to_file, os.X_OK):
					# the file is executable (f.e. CRUX)
					# yes, then run it and get the first line of output.
					text = helpers.get_output_of_command(path_to_file)[0]
				else:
					fd = open(path_to_file)
					text = fd.readline().strip() # get only first line
					fd.close()
					if path_to_file.endswith('version'):
						# sourcemage_version has all the info we need
						if not os.path.basename(path_to_file).startswith('sourcemage'):
							text = distro_name + ' ' + text
					elif path_to_file.endswith('aurox-release'):
						# file doesn't have version
						text = distro_name
					elif path_to_file.endswith('lfs-release'): # file just has version
						text = distro_name + ' ' + text
				return text

		# our last chance, ask uname and strip it
		uname_output = helpers.get_output_of_command('uname -a | cut -d" " -f1,3')
		if uname_output is not None:
			return uname_output[0] # only first line
	return 'N/A'

class Connection:
	'''Connection class'''
	def __init__(self, name):
		self.name = name
		self.connected = 0 # offline
		self.connection = None # xmpppy instance
		self.gpg = None
		self.vcard_sha = None
		self.vcard_shas = {} # sha of contacts
		self.status = ''
		self.old_show = ''
		# increase/decrease default timeout for server responses
		self.try_connecting_for_foo_secs = 45
		# holds the actual hostname to which we are connected
		self.connected_hostname = None
		self.time_to_reconnect = None
		self.new_account_info = None
		self.bookmarks = []
		self.on_purpose = False
		self.last_io = time.time()
		self.last_sent = []
		self.files_props = {}
		self.last_history_line = {}
		self.password = gajim.config.get_per('accounts', name, 'password')
		self.server_resource = gajim.config.get_per('accounts', name, 'resource')
		if gajim.config.get_per('accounts', self.name, 'keep_alives_enabled'):
			self.keepalives = gajim.config.get_per('accounts', self.name,'keep_alive_every_foo_secs')
		else:
			self.keepalives = 0
		self.privacy_rules_supported = False
		# Do we continue connection when we get roster (send presence,get vcard...)
		self.continue_connect_info = None
		# List of IDs we are waiting answers for {id: (type_of_request, data), }
		self.awaiting_answers = {}
		# List of IDs that will produce a timeout is answer doesn't arrive
		# {time_of_the_timeout: (id, message to send to gui), }
		self.awaiting_timeouts = {}
		if USE_GPG:
			self.gpg = GnuPG.GnuPG()
			gajim.config.set('usegpg', True)
		else:
			gajim.config.set('usegpg', False)

		try:
			idle.init()
		except:
			HAS_IDLE = False
		self.on_connect_success = None
		self.retrycount = 0
	# END __init__

	def get_full_jid(self, iq_obj):
		'''return the full jid (with resource) from an iq as unicode'''
		return helpers.parse_jid(str(iq_obj.getFrom()))

	def get_jid(self, iq_obj):
		'''return the jid (without resource) from an iq as unicode'''
		jid = self.get_full_jid(iq_obj)
		return gajim.get_jid_without_resource(jid)

	def put_event(self, ev):
		if gajim.handlers.has_key(ev[0]):
			gajim.handlers[ev[0]](self.name, ev[1])

	def dispatch(self, event, data):
		'''always passes account name as first param'''
		self.put_event((event, data))

	def add_sha(self, p):
		c = p.setTag('x', namespace = common.xmpp.NS_VCARD_UPDATE)
		if self.vcard_sha is not None:
			c.setTagData('photo', self.vcard_sha)
		return p

	# this is in features.py but it is blocking
	def _discover(self, ns, jid, node = None):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get', to = jid, queryNS = ns)
		if node:
			iq.setQuerynode(node)
		self.connection.send(iq)

	def discoverItems(self, jid, node = None):
		'''According to JEP-0030: jid is mandatory,
		name, node, action is optional.'''
		self._discover(common.xmpp.NS_DISCO_ITEMS, jid, node)

	def discoverInfo(self, jid, node = None):
		'''According to JEP-0030:
			For identity: category, type is mandatory, name is optional.
			For feature: var is mandatory'''
		self._discover(common.xmpp.NS_DISCO_INFO, jid, node)

	def node_to_dict(self, node):
		dict = {}
		for info in node.getChildren():
			name = info.getName()
			if name in ('ADR', 'TEL', 'EMAIL'): # we can have several
				if not dict.has_key(name):
					dict[name] = []
				entry = {}
				for c in info.getChildren():
					 entry[c.getName()] = c.getData()
				dict[name].append(entry)
			elif info.getChildren() == []:
				dict[name] = info.getData()
			else:
				dict[name] = {}
				for c in info.getChildren():
					 dict[name][c.getName()] = c.getData()
		return dict

	def _vCardCB(self, con, vc):
		'''Called when we receive a vCard
		Parse the vCard and send it to plugins'''
		if not vc.getTag('vCard'):
			return
		frm_iq = vc.getFrom()
		our_jid = gajim.get_jid_from_account(self.name)
		resource = ''
		if frm_iq:
			who = self.get_full_jid(vc)
			frm, resource = gajim.get_room_and_nick_from_fjid(who)
		else:
			frm = our_jid
		if vc.getTag('vCard').getNamespace() == common.xmpp.NS_VCARD:
			card = vc.getChildren()[0]
			vcard = self.node_to_dict(card)
			photo_decoded = None
			if vcard.has_key('PHOTO') and isinstance(vcard['PHOTO'], dict) and \
			vcard['PHOTO'].has_key('BINVAL'):
				photo = vcard['PHOTO']['BINVAL']
				try:
					photo_decoded = base64.decodestring(photo)
					avatar_sha = sha.sha(photo_decoded).hexdigest()
				except:
					avatar_sha = ''
			else:
				avatar_sha = ''

			if avatar_sha:
				card.getTag('PHOTO').setTagData('SHA', avatar_sha)

			# Save it to file
			path_to_file = os.path.join(gajim.VCARD_PATH, frm)
			fil = open(path_to_file, 'w')
			fil.write(str(card))
			fil.close()
			# Save the decoded avatar to a separate file too, and generate files for dbus notifications
			if photo_decoded:
				avatar_file = os.path.join(gajim.AVATAR_PATH, frm + '_notif_size_colored.png')
				if frm == our_jid and avatar_sha != self.vcard_sha:
					gajim.interface.save_avatar_files(frm, photo_decoded)
				elif frm != our_jid and (not os.path.exists(avatar_file) or \
					not self.vcard_shas.has_key(frm) or \
					avatar_sha != self.vcard_shas[frm]):
					gajim.interface.save_avatar_files(frm, photo_decoded)
			else:
				for ext in ('.jpeg', '.png', '_notif_size_bw.png',
					'_notif_size_colored.png'):
					path = os.path.join(gajim.AVATAR_PATH, frm + ext)
					if os.path.isfile(path):
						os.remove(path)

			if frm != our_jid:
				if avatar_sha:
					self.vcard_shas[frm] = avatar_sha
				elif self.vcard_shas.has_key(frm):
					del self.vcard_shas[frm]

			vcard['jid'] = frm
			vcard['resource'] = resource
			if frm == our_jid:
				self.dispatch('MYVCARD', vcard)
				# we re-send our presence with sha if has changed and if we are
				# not invisible
				if self.vcard_sha == avatar_sha:
					return
				self.vcard_sha = avatar_sha
				if STATUS_LIST[self.connected] == 'invisible':
					return
				sshow = helpers.get_xmpp_show(STATUS_LIST[self.connected])
				prio = unicode(gajim.config.get_per('accounts', self.name,
					'priority'))
				p = common.xmpp.Presence(typ = None, priority = prio, show = sshow,
					status = self.status)
				p = self.add_sha(p)
				self.connection.send(p)
			else:
				self.dispatch('VCARD', vcard)

	def _gMailNewMailCB(self, con, gm):
		'''Called when we get notified of new mail messages in gmail account'''
		if not gm.getTag('new-mail'):
			return
		if gm.getTag('new-mail').getNamespace() == common.xmpp.NS_GMAILNOTIFY:
			# we'll now ask the server for the exact number of new messages
			jid = gajim.get_jid_from_account(self.name)
			gajim.log.debug('Got notification of new gmail e-mail on %s. Asking the server for more info.' % jid)
			iq = common.xmpp.Iq(typ = 'get')
			iq.setAttr('id', '13')
			query = iq.setTag('query')
			query.setNamespace(common.xmpp.NS_GMAILNOTIFY)
			self.connection.send(iq)
			raise common.xmpp.NodeProcessed

	def _gMailQueryCB(self, con, gm):
		'''Called when we receive results from Querying the server for mail messages in gmail account'''
		if not gm.getTag('mailbox'):
			return
		if gm.getTag('mailbox').getNamespace() == common.xmpp.NS_GMAILNOTIFY:
			newmsgs = gm.getTag('mailbox').getAttr('total-matched')
			if newmsgs != '0':
				# there are new messages
				jid = gajim.get_jid_from_account(self.name)
				gajim.log.debug(('You have %s new gmail e-mails on %s.') % (newmsgs, jid))
				self.dispatch('GMAIL_NOTIFY', (jid, newmsgs))
			raise common.xmpp.NodeProcessed

	def _messageCB(self, con, msg):
		'''Called when we receive a message'''
		msgtxt = msg.getBody()
		mtype = msg.getType()
		subject = msg.getSubject() # if not there, it's None
		tim = msg.getTimestamp()
		tim = time.strptime(tim, '%Y%m%dT%H:%M:%S')
		tim = time.localtime(timegm(tim))
		frm = self.get_full_jid(msg)
		jid = self.get_jid(msg)
		no_log_for = gajim.config.get_per('accounts', self.name, 'no_log_for')
		encrypted = False
		chatstate = None
		encTag = msg.getTag('x', namespace = common.xmpp.NS_ENCRYPTED)
		decmsg = ''
		# invitations
		invite = None
		if not encTag:
			invite = msg.getTag('x', namespace = common.xmpp.NS_MUC_USER)
			if invite and not invite.getTag('invite'):
				invite = None
		delayed = msg.getTag('x', namespace = common.xmpp.NS_DELAY) != None
		msg_id = None
		composing_jep = None
		# FIXME: Msn transport (CMSN1.2.1 and PyMSN0.10) do NOT RECOMMENDED
		# invitation
		# stanza (MUC JEP) remove in 2007, as we do not do NOT RECOMMENDED
		xtags = msg.getTags('x')
		for xtag in xtags:
			if xtag.getNamespace() == common.xmpp.NS_CONFERENCE and not invite:
				room_jid = xtag.getAttr('jid')
				self.dispatch('GC_INVITATION', (room_jid, frm, '', None))
				return
		# chatstates - look for chatstate tags in a message if not delayed
		if not delayed:
			composing_jep = False
			children = msg.getChildren()
			for child in children:
				if child.getNamespace() == 'http://jabber.org/protocol/chatstates':
					chatstate = child.getName()
					composing_jep = 'JEP-0085'
					break
			# No JEP-0085 support, fallback to JEP-0022
			if not chatstate:
				chatstate_child = msg.getTag('x', namespace = common.xmpp.NS_EVENT)
				if chatstate_child:
					chatstate = 'active'
					composing_jep = 'JEP-0022'
					if not msgtxt and chatstate_child.getTag('composing'):
 						chatstate = 'composing'
						
		if encTag and USE_GPG:
			#decrypt
			encmsg = encTag.getData()

			keyID = gajim.config.get_per('accounts', self.name, 'keyid')
			if keyID:
				decmsg = self.gpg.decrypt(encmsg, keyID)
		if decmsg:
			msgtxt = decmsg
			encrypted = True
		if mtype == 'error':
			self.dispatch('MSGERROR', (frm, msg.getErrorCode(), msg.getError(),
				msgtxt, tim))
		elif mtype == 'groupchat':
			if subject:
				self.dispatch('GC_SUBJECT', (frm, subject, msgtxt))
			else:
				if not msg.getTag('body'): #no <body>
					return
				# Ignore message from room in which we are not
				if not self.last_history_line.has_key(jid):
					return
				self.dispatch('GC_MSG', (frm, msgtxt, tim))
				if self.name not in no_log_for and jid in self.last_history_line \
					and not int(float(time.mktime(tim))) <= \
					self.last_history_line[jid]:
					gajim.logger.write('gc_msg', frm, msgtxt, tim = tim)
		elif mtype == 'chat': # it's type 'chat'
			if not msg.getTag('body') and chatstate is None: #no <body>
				return
			if msg.getTag('body') and self.name not in no_log_for and jid not in\
				no_log_for:
				gajim.logger.write('chat_msg_recv', frm, msgtxt, tim = tim, subject = subject)
			self.dispatch('MSG', (frm, msgtxt, tim, encrypted, mtype, subject,
				chatstate, msg_id, composing_jep))
		else: # it's single message
			if self.name not in no_log_for and jid not in no_log_for:
				gajim.logger.write('single_msg_recv', frm, msgtxt, tim = tim, subject = subject)
			if invite is not None:
				item = invite.getTag('invite')
				jid_from = item.getAttr('from')
				reason = item.getTagData('reason')
				item = invite.getTag('password')
				password = invite.getTagData('password')
				self.dispatch('GC_INVITATION',(frm, jid_from, reason, password))
			else:
				self.dispatch('MSG', (frm, msgtxt, tim, encrypted, 'normal',
					subject, chatstate, msg_id, composing_jep))
	# END messageCB

	def _presenceCB(self, con, prs):
		'''Called when we receive a presence'''
		ptype = prs.getType()
		if ptype == 'available':
			ptype = None
		gajim.log.debug('PresenceCB: %s' % ptype)
		is_gc = False # is it a GC presence ?
		sigTag = None
		avatar_sha = None
		xtags = prs.getTags('x')
		for x in xtags:
			if x.getNamespace().startswith(common.xmpp.NS_MUC):
				is_gc = True
			if x.getNamespace() == common.xmpp.NS_SIGNED:
				sigTag = x
			if x.getNamespace() == common.xmpp.NS_VCARD_UPDATE:
				avatar_sha = x.getTagData('photo')

		who = self.get_full_jid(prs)
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		no_log_for = gajim.config.get_per('accounts', self.name, 'no_log_for')
		status = prs.getStatus()
		show = prs.getShow()
		if not show in STATUS_LIST:
			show = '' # We ignore unknown show
		if not ptype and not show:
			show = 'online'
		elif ptype == 'unavailable':
			show = 'offline'

		prio = prs.getPriority()
		try:
			prio = int(prio)
		except:
			prio = 0
		keyID = ''
		if sigTag and USE_GPG:
			#verify
			sigmsg = sigTag.getData()
			keyID = self.gpg.verify(status, sigmsg)

		if is_gc:
			if ptype == 'error':
				errmsg = prs.getError()
				errcode = prs.getErrorCode()
				if errcode == '502': # Internal Timeout:
					self.dispatch('NOTIFY', (jid_stripped, 'error', errmsg, resource,
						prio, keyID))
				elif errcode == '401': # password required to join
					self.dispatch('ERROR', (_('Unable to join room'),
						_('A password is required to join this room.')))
				elif errcode == '403': # we are banned
					self.dispatch('ERROR', (_('Unable to join room'),
						_('You are banned from this room.')))
				elif errcode == '404': # room does not exist
					self.dispatch('ERROR', (_('Unable to join room'),
						_('Such room does not exist.')))
				elif errcode == '405':
					self.dispatch('ERROR', (_('Unable to join room'),
						_('Room creation is restricted.')))
				elif errcode == '406':
					self.dispatch('ERROR', (_('Unable to join room'),
						_('Your registered nickname must be used.')))
				elif errcode == '407':
					self.dispatch('ERROR', (_('Unable to join room'),
						_('You are not in the members list.')))
				elif errcode == '409': # nick conflict
					# the jid_from in this case is FAKE JID: room_jid/nick
					# resource holds the bad nick so propose a new one
					proposed_nickname = resource + \
						gajim.config.get('gc_proposed_nick_char')
					room_jid = gajim.get_room_from_fjid(who)
					self.dispatch('ASK_NEW_NICK', (room_jid, _('Unable to join room'),
		_('Your desired nickname is in use or registered by another occupant.\nPlease specify another nickname below:'), proposed_nickname))
				else:	# print in the window the error
					self.dispatch('ERROR_ANSWER', ('', jid_stripped,
						errmsg, errcode))
			if not ptype or ptype == 'unavailable':
				if gajim.config.get('log_contact_status_changes') and self.name\
					not in no_log_for and jid_stripped not in no_log_for:
					gajim.logger.write('gcstatus', who, status, show)
				self.dispatch('GC_NOTIFY', (jid_stripped, show, status, resource,
					prs.getRole(), prs.getAffiliation(), prs.getJid(),
					prs.getReason(), prs.getActor(), prs.getStatusCode(),
					prs.getNewNick()))
			return

		if ptype == 'subscribe':
			gajim.log.debug('subscribe request from %s' % who)
			if gajim.config.get('alwaysauth') or who.find("@") <= 0:
				if self.connection:
					p = common.xmpp.Presence(who, 'subscribed')
					p = self.add_sha(p)
					self.connection.send(p)
				if who.find("@") <= 0:
					self.dispatch('NOTIFY',
						(jid_stripped, 'offline', 'offline', resource, prio, keyID))
			else:
				if not status:
					status = _('I would like to add you to my roster.')
				self.dispatch('SUBSCRIBE', (who, status))
		elif ptype == 'subscribed':
			self.dispatch('SUBSCRIBED', (jid_stripped, resource))
			# BE CAREFUL: no con.updateRosterItem() in a callback
			gajim.log.debug(_('we are now subscribed to %s') % who)
		elif ptype == 'unsubscribe':
			gajim.log.debug(_('unsubscribe request from %s') % who)
		elif ptype == 'unsubscribed':
			gajim.log.debug(_('we are now unsubscribed from %s') % who)
			self.dispatch('UNSUBSCRIBED', jid_stripped)
		elif ptype == 'error':
			errmsg = prs.getError()
			errcode = prs.getErrorCode()
			if errcode == '502': # Internal Timeout:
				self.dispatch('NOTIFY', (jid_stripped, 'error', errmsg, resource,
					prio, keyID))
			else:	# print in the window the error
				self.dispatch('ERROR_ANSWER', ('', jid_stripped,
					errmsg, errcode))

		if avatar_sha and ptype != 'error':
			if self.vcard_shas.has_key(jid_stripped):
				if avatar_sha != self.vcard_shas[jid_stripped]:
					# avatar has been updated
					self.request_vcard(jid_stripped)
			else:
				self.vcard_shas[jid_stripped] = avatar_sha
		if not ptype or ptype == 'unavailable':
			if gajim.config.get('log_contact_status_changes') and self.name\
				not in no_log_for and jid_stripped not in no_log_for:
				gajim.logger.write('status', jid_stripped, status, show)
			self.dispatch('NOTIFY', (jid_stripped, show, status, resource, prio,
				keyID))
	# END presenceCB

	def _disconnectedCB(self):
		'''Called when we are disconnected'''
		gajim.log.debug('disconnectedCB')
		if not self.connection:
			return
		self.connected = 0
		self.dispatch('STATUS', 'offline')
		self.connection = None
		if not self.on_purpose:
			self.dispatch('ERROR',
			(_('Connection with account "%s" has been lost') % self.name,
			_('To continue sending and receiving messages, you will need to reconnect.')))
		self.on_purpose = False

	# END disconenctedCB

	def _reconnect(self):
		# Do not try to reco while we are already trying
		self.time_to_reconnect = None
		gajim.log.debug('reconnect')
		self.retrycount += 1
		signed = self.get_signed_msg(self.status)
		self.on_connect_auth = self._init_roster
		self.connect_and_init(self.old_show, self.status, signed)

		if self.connected < 2: #connection failed
			if self.retrycount > 10:
				self.connected = 0
				self.dispatch('STATUS', 'offline')
				self.dispatch('ERROR',
				(_('Connection with account "%s" has been lost') % self.name,
				_('To continue sending and receiving messages, you will need to reconnect.')))
				self.retrycount = 0
				return
			if self.retrycount > 5:
				self.time_to_reconnect = 20
			else:
				self.time_to_reconnect = 10
			gajim.idlequeue.set_alarm(self._reconnect_alarm, self.time_to_reconnect)
		else:
			# reconnect succeeded
			self.time_to_reconnect = None
			self.retrycount = 0

	def _disconnectedReconnCB(self):
		'''Called when we are disconnected'''
		gajim.log.debug('disconnectedReconnCB')
		if not self.connection:
			return
		self.old_show = STATUS_LIST[self.connected]
		self.connected = 0
		self.dispatch('STATUS', 'offline')
		self.connection = None
		if not self.on_purpose:
			if gajim.config.get_per('accounts', self.name, 'autoreconnect'):
				self.connected = 1
				self.dispatch('STATUS', 'connecting')
				self.time_to_reconnect = 10
				gajim.idlequeue.set_alarm(self._reconnect_alarm, 10)
			else:
				self.dispatch('ERROR',
				(_('Connection with account "%s" has been lost') % self.name,
				_('To continue sending and receiving messages, you will need to reconnect.')))
		self.on_purpose = False
	# END disconenctedReconnCB

	def _bytestreamErrorCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamErrorCB')
		id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		jid = self.get_jid(iq_obj)
		id = id[3:]
		if not self.files_props.has_key(id):
			return
		file_props = self.files_props[id]
		file_props['error'] = -4
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props))
		raise common.xmpp.NodeProcessed

	def _bytestreamSetCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamSetCB')
		target = unicode(iq_obj.getAttr('to'))
		id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		sid = unicode(query.getAttr('sid'))
		file_props = gajim.socks5queue.get_file_props(
			self.name, sid)
		streamhosts=[]
		for item in query.getChildren():
			if item.getName() == 'streamhost':
				host_dict={
					'state': 0,
					'target': target,
					'id': id,
					'sid': sid,
					'initiator': self.get_full_jid(iq_obj)
				}
				for attr in item.getAttrs():
					host_dict[attr] = item.getAttr(attr)
				streamhosts.append(host_dict)
		if file_props is None:
			if self.files_props.has_key(sid):
				file_props = self.files_props[sid]
				file_props['fast'] = streamhosts
				if file_props['type'] == 's': # FIXME: remove fast xmlns
					# only psi do this

					if file_props.has_key('streamhosts'):
						file_props['streamhosts'].extend(streamhosts)
					else:
						file_props['streamhosts'] = streamhosts
					if not gajim.socks5queue.get_file_props(self.name, sid):
						gajim.socks5queue.add_file_props(self.name, file_props)
					gajim.socks5queue.connect_to_hosts(self.name, sid,
						self.send_success_connect_reply, None)
				raise common.xmpp.NodeProcessed

		file_props['streamhosts'] = streamhosts
		if file_props['type'] == 'r':
			gajim.socks5queue.connect_to_hosts(self.name, sid,
				self.send_success_connect_reply, self._connect_error)
		raise common.xmpp.NodeProcessed

	def send_success_connect_reply(self, streamhost):
		''' send reply to the initiator of FT that we
		made a connection
		'''
		if streamhost is None:
			return None
		iq = common.xmpp.Iq(to = streamhost['initiator'], typ = 'result',
			frm = streamhost['target'])
		iq.setAttr('id', streamhost['id'])
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		stream_tag = query.setTag('streamhost-used')
		stream_tag.setAttr('jid', streamhost['jid'])
		self.connection.send(iq)

	def _connect_error(self, to, _id, sid, code = 404):
		msg_dict = {
			404: 'Could not connect to given hosts',
			405: 'Cancel',
			406: 'Not acceptable',
		}
		msg = msg_dict[code]
		iq = None
		iq = common.xmpp.Protocol(name = 'iq', to = to,
			typ = 'error')
		iq.setAttr('id', _id)
		err = iq.setTag('error')
		err.setAttr('code', unicode(code))
		err.setData(msg)
		self.connection.send(iq)
		if code == 404:
			file_props = gajim.socks5queue.get_file_props(self.name, sid)
			if file_props is not None:
				self.disconnect_transfer(file_props)
				file_props['error'] = -3
				self.dispatch('FILE_REQUEST_ERROR', (to, file_props))

	def _bytestreamResultCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamResultCB')
		frm = self.get_full_jid(iq_obj)
		real_id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		streamhost = None
		try:
			streamhost = query.getTag('streamhost')
		except:
			pass
		if streamhost is not None: # this is a result for proxy request
			jid = None
			try:
				jid = streamhost.getAttr('jid')
			except:
				raise common.xmpp.NodeProcessed
			proxyhosts = []
			for item in query.getChildren():
				if item.getName() == 'streamhost':
					host = item.getAttr('host')
					port = item.getAttr('port')
					jid = item.getAttr('jid')
					conf = gajim.config
					conf.add_per('ft_proxies65_cache', jid)
					conf.set_per('ft_proxies65_cache', jid,
						'host', unicode(host))
					conf.set_per('ft_proxies65_cache', jid,
						'port', int(port))
					conf.set_per('ft_proxies65_cache', jid,
						'jid', unicode(jid))
			raise common.xmpp.NodeProcessed
		try:
			streamhost =  query.getTag('streamhost-used')
		except: # this bytestream result is not what we need
			pass
		id = real_id[3:]
		if self.files_props.has_key(id):
			file_props = self.files_props[id]
		else:
			raise common.xmpp.NodeProcessed
		if streamhost is None:
			# proxy approves the activate query
			if real_id[:3] == 'au_':
				id = real_id[3:]
				if not file_props.has_key('streamhost-used') or \
					file_props['streamhost-used'] is False:
					raise common.xmpp.NodeProcessed
				if not file_props.has_key('proxyhosts'):
					raise common.xmpp.NodeProcessed
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and \
					unicode(query.getAttr('sid')) == file_props['sid']:
						gajim.socks5queue.activate_proxy(host['idx'])
						break
			raise common.xmpp.NodeProcessed
		jid = streamhost.getAttr('jid')
		if file_props.has_key('streamhost-used') and \
			file_props['streamhost-used'] is True:
			raise common.xmpp.NodeProcessed

		if real_id[:3] == 'au_':
			gajim.socks5queue.send_file(file_props, self.name)
			raise common.xmpp.NodeProcessed

		proxy = None
		if file_props.has_key('proxyhosts'):
			for proxyhost in file_props['proxyhosts']:
				if proxyhost['jid'] == jid:
					proxy = proxyhost

		if proxy != None:
			file_props['streamhost-used'] = True
			if not file_props.has_key('streamhosts'):
				file_props['streamhosts'] = []
			file_props['streamhosts'].append(proxy)
			file_props['is_a_proxy'] = True
			receiver = socks5.Socks5Receiver(gajim.idlequeue, proxy, file_props['sid'], file_props)
			gajim.socks5queue.add_receiver(self.name, receiver)
			proxy['idx'] = receiver.queue_idx
			gajim.socks5queue.on_success = self.proxy_auth_ok
			raise common.xmpp.NodeProcessed

		else:
			gajim.socks5queue.send_file(file_props, self.name)
			if file_props.has_key('fast'):
				fasts = file_props['fast']
				if len(fasts) > 0:
					self._connect_error(frm, fasts[0]['id'], file_props['sid'],
						code = 406)

		raise common.xmpp.NodeProcessed

	def remove_all_transfers(self):
		''' stops and removes all active connections from the socks5 pool '''
		for file_props in self.files_props.values():
			self.remove_transfer(file_props, remove_from_list = False)
		del(self.files_props)
		self.files_props = {}

	def remove_transfer(self, file_props, remove_from_list = True):
		if file_props is None:
			return
		self.disconnect_transfer(file_props)
		sid = file_props['sid']
		gajim.socks5queue.remove_file_props(self.name, sid)

		if remove_from_list:
			if self.files_props.has_key('sid'):
				del(self.files_props['sid'])

	def disconnect_transfer(self, file_props):
		if file_props is None:
			return
		if file_props.has_key('hash'):
			gajim.socks5queue.remove_sender(file_props['hash'])

		if file_props.has_key('streamhosts'):
			for host in file_props['streamhosts']:
				if host.has_key('idx') and host['idx'] > 0:
					gajim.socks5queue.remove_receiver(host['idx'])
					gajim.socks5queue.remove_sender(host['idx'])

	def proxy_auth_ok(self, proxy):
		'''cb, called after authentication to proxy server '''
		file_props = self.files_props[proxy['sid']]
		iq = common.xmpp.Protocol(name = 'iq', to = proxy['initiator'],
		typ = 'set')
		auth_id = "au_" + proxy['sid']
		iq.setID(auth_id)
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('sid',  proxy['sid'])
		activate = query.setTag('activate')
		activate.setData(file_props['proxy_receiver'])
		iq.setID(auth_id)
		self.connection.send(iq)

	def _discoGetCB(self, con, iq_obj):
		''' get disco info '''
		frm = self.get_full_jid(iq_obj)
		to = unicode(iq_obj.getAttr('to'))
		id = unicode(iq_obj.getAttr('id'))
		iq = common.xmpp.Iq(to = frm, typ = 'result', queryNS =\
			common.xmpp.NS_DISCO, frm = to)
		iq.setAttr('id', id)
		query = iq.setTag('query')
		# bytestream transfers
		feature = common.xmpp.Node('feature')
		feature.setAttr('var', common.xmpp.NS_BYTESTREAM)
		query.addChild(node=feature)
		# si methods
		feature = common.xmpp.Node('feature')
		feature.setAttr('var', common.xmpp.NS_SI)
		query.addChild(node=feature)
		# filetransfers transfers
		feature = common.xmpp.Node('feature')
		feature.setAttr('var', common.xmpp.NS_FILE)
		query.addChild(node=feature)

		self.connection.send(iq)
		raise common.xmpp.NodeProcessed

	def _siResultCB(self, con, iq_obj):
		gajim.log.debug('_siResultCB')
		id = iq_obj.getAttr('id')
		if not self.files_props.has_key(id):
			# no such jid
			return
		file_props = self.files_props[id]
		if file_props is None:
			# file properties for jid is none
			return
		file_props['receiver'] = self.get_full_jid(iq_obj)
		si = iq_obj.getTag('si')
		file_tag = si.getTag('file')
		range_tag = None
		if file_tag:
			range_tag = file_tag.getTag('range')
		if range_tag:
			offset = range_tag.getAttr('offset')
			if offset:
				file_props['offset'] = int(offset)
			length = range_tag.getAttr('length')
			if length:
				file_props['length'] = int(length)
		feature = si.setTag('feature')
		if feature.getNamespace() != common.xmpp.NS_FEATURE:
			return
		form_tag = feature.getTag('x')
		form = common.xmpp.DataForm(node=form_tag)
		field = form.getField('stream-method')
		if field.getValue() != common.xmpp.NS_BYTESTREAM:
			return
		self.send_socks5_info(file_props, fast = True)
		raise common.xmpp.NodeProcessed

	def _get_sha(self, sid, initiator, target):
		return sha.new("%s%s%s" % (sid, initiator, target)).hexdigest()

	def result_socks5_sid(self, sid, hash_id):
		''' store the result of sha message from auth  '''
		if not self.files_props.has_key(sid):
			return
		file_props = self.files_props[sid]
		file_props['hash'] = hash_id
		return

	def get_cached_proxies(self, proxy):
		''' get cached entries for proxy and request the cache again '''
		host = gajim.config.get_per('ft_proxies65_cache', proxy, 'host')
		port = gajim.config.get_per('ft_proxies65_cache', proxy, 'port')
		jid = gajim.config.get_per('ft_proxies65_cache', proxy, 'jid')

		iq = common.xmpp.Protocol(name = 'iq', to = proxy, typ = 'get')
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		# FIXME bad logic - this should be somewhere else!
		# this line should be put somewhere else
		# self.connection.send(iq)
		# ensure that we don;t return empty vars
		if None not in (host, port, jid) or '' not in (host, port, jid):
			return (host, port, jid)
		return (None, None, None)

	def send_socks5_info(self, file_props, fast = True, receiver = None,
		sender = None):
		''' send iq for the present streamhosts and proxies '''
		if type(self.peerhost) != tuple:
			return
		port = gajim.config.get('file_transfers_port')
		ft_override_host_to_send = gajim.config.get('ft_override_host_to_send')
		cfg_proxies = gajim.config.get_per('accounts', self.name,
			'file_transfer_proxies')
		if receiver is None:
			receiver = file_props['receiver']
		if sender is None:
			sender = file_props['sender']
		proxyhosts = []
		if fast and cfg_proxies:
			proxies = map(lambda e:e.strip(), cfg_proxies.split(','))
			for proxy in proxies:
				(host, _port, jid) = self.get_cached_proxies(proxy)
				if host is None:
					continue
				host_dict={
					'state': 0,
					'target': unicode(receiver),
					'id': file_props['sid'],
					'sid': file_props['sid'],
					'initiator': proxy,
					'host': host,
					'port': unicode(_port),
					'jid': jid
				}
				proxyhosts.append(host_dict)
		sha_str = self._get_sha(file_props['sid'], sender,
			receiver)
		file_props['sha_str'] = sha_str
		if not ft_override_host_to_send:
			ft_override_host_to_send = self.peerhost[0]
		ft_override_host_to_send = socket.gethostbyname(ft_override_host_to_send)
		listener = gajim.socks5queue.start_listener(self.peerhost[0], port,
			sha_str, self.result_socks5_sid, file_props['sid'])
		if listener == None:
			file_props['error'] = -5
			self.dispatch('FILE_REQUEST_ERROR', (unicode(receiver), file_props))
			self._connect_error(unicode(receiver), file_props['sid'],
				file_props['sid'], code = 406)
			return

		iq = common.xmpp.Protocol(name = 'iq', to = unicode(receiver),
			typ = 'set')
		file_props['request-id'] = 'id_' + file_props['sid']
		iq.setID(file_props['request-id'])
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('mode', 'tcp')
		query.setAttr('sid', file_props['sid'])
		streamhost = query.setTag('streamhost')
		streamhost.setAttr('port', unicode(port))
		streamhost.setAttr('host', ft_override_host_to_send)
		streamhost.setAttr('jid', sender)
		if fast and proxyhosts != []:
			file_props['proxy_receiver'] = unicode(receiver)
			file_props['proxy_sender'] = unicode(sender)
			file_props['proxyhosts'] = proxyhosts
			for proxyhost in proxyhosts:
				streamhost = common.xmpp.Node(tag = 'streamhost')
				query.addChild(node=streamhost)
				streamhost.setAttr('port', proxyhost['port'])
				streamhost.setAttr('host', proxyhost['host'])
				streamhost.setAttr('jid', proxyhost['jid'])

				# don't add the proxy child tag for streamhosts, which are proxies
				# proxy = streamhost.setTag('proxy')
				# proxy.setNamespace(common.xmpp.NS_STREAM)
		self.connection.send(iq)

	def _siSetCB(self, con, iq_obj):
		gajim.log.debug('_siSetCB')
		jid = self.get_jid(iq_obj)
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		mime_type = si.getAttr('mime-type')
		if profile != common.xmpp.NS_FILE:
			return
		file_tag = si.getTag('file')
		file_props = {'type': 'r'}
		for attribute in file_tag.getAttrs():
			if attribute in ('name', 'size', 'hash', 'date'):
				val = file_tag.getAttr(attribute)
				if val is None:
					continue
				file_props[attribute] = val
		file_desc_tag = file_tag.getTag('desc')
		if file_desc_tag is not None:
			file_props['desc'] = file_desc_tag.getData()

		if mime_type is not None:
			file_props['mime-type'] = mime_type
		our_jid = gajim.get_jid_from_account(self.name)
		resource = self.server_resource
		file_props['receiver'] = our_jid + '/' + resource
		file_props['sender'] = self.get_full_jid(iq_obj)
		file_props['request-id'] = unicode(iq_obj.getAttr('id'))
		file_props['sid'] = unicode(si.getAttr('id'))
		gajim.socks5queue.add_file_props(self.name, file_props)
		self.dispatch('FILE_REQUEST', (jid, file_props))
		raise common.xmpp.NodeProcessed

	def _siErrorCB(self, con, iq_obj):
		gajim.log.debug('_siErrorCB')
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		if profile != common.xmpp.NS_FILE:
			return
		id = iq_obj.getAttr('id')
		if not self.files_props.has_key(id):
			# no such jid
			return
		file_props = self.files_props[id]
		if file_props is None:
			# file properties for jid is none
			return
		jid = self.get_jid(iq_obj)
		file_props['error'] = -3
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props))
		raise common.xmpp.NodeProcessed

	def send_file_rejection(self, file_props):
		''' informs sender that we refuse to download the file '''
		iq = common.xmpp.Protocol(name = 'iq',
			to = unicode(file_props['sender']), typ = 'error')
		iq.setAttr('id', file_props['request-id'])
		err = common.xmpp.ErrorNode(code = '406', typ = 'auth', name =
			'not-acceptable')
		iq.addChild(node=err)
		self.connection.send(iq)

	def send_file_approval(self, file_props):
		''' comfirm that we want to download the file '''
		iq = common.xmpp.Protocol(name = 'iq',
			to = unicode(file_props['sender']), typ = 'result')
		iq.setAttr('id', file_props['request-id'])
		si = iq.setTag('si')
		si.setNamespace(common.xmpp.NS_SI)
		file_tag = si.setTag('file')
		file_tag.setNamespace(common.xmpp.NS_FILE)
		if file_props.has_key('offset') and file_props['offset']:
			range_tag = file_tag.setTag('range')
			range_tag.setAttr('offset', file_props['offset'])
		feature = si.setTag('feature')
		feature.setNamespace(common.xmpp.NS_FEATURE)
		_feature = common.xmpp.DataForm(typ='submit')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.delAttr('type')
		field.setValue(common.xmpp.NS_BYTESTREAM)
		self.connection.send(iq)

	def send_file_request(self, file_props):
		our_jid = gajim.get_jid_from_account(self.name)
		resource = self.server_resource
		frm = our_jid + '/' + resource
		file_props['sender'] = frm
		fjid = file_props['receiver'].jid + '/' + file_props['receiver'].resource
		iq = common.xmpp.Protocol(name = 'iq', to = fjid,
			typ = 'set')
		iq.setID(file_props['sid'])
		self.files_props[file_props['sid']] = file_props
		si = iq.setTag('si')
		si.setNamespace(common.xmpp.NS_SI)
		si.setAttr('profile', common.xmpp.NS_FILE)
		si.setAttr('id', file_props['sid'])
		file_tag = si.setTag('file')
		file_tag.setNamespace(common.xmpp.NS_FILE)
		file_tag.setAttr('name', file_props['name'])
		file_tag.setAttr('size', file_props['size'])
		desc = file_tag.setTag('desc')
		if file_props.has_key('desc'):
			desc.setData(file_props['desc'])
		file_tag.setTag('range')
		feature = si.setTag('feature')
		feature.setNamespace(common.xmpp.NS_FEATURE)
		_feature = common.xmpp.DataForm(typ='form')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.setAttr('type', 'list-single')
		field.addOption(common.xmpp.NS_BYTESTREAM)
		self.connection.send(iq)

	def _rosterSetCB(self, con, iq_obj):
		gajim.log.debug('rosterSetCB')
		for item in iq_obj.getTag('query').getChildren():
			jid  = helpers.parse_jid(item.getAttr('jid'))
			name = item.getAttr('name')
			sub  = item.getAttr('subscription')
			ask  = item.getAttr('ask')
			groups = []
			for group in item.getTags('group'):
				groups.append(group.getData())
			self.dispatch('ROSTER_INFO', (jid, name, sub, ask, groups))
		raise common.xmpp.NodeProcessed

	def _DiscoverItemsErrorCB(self, con, iq_obj):
		gajim.log.debug('DiscoverItemsErrorCB')
		jid = self.get_full_jid(iq_obj)
		self.dispatch('AGENT_ERROR_ITEMS', (jid))

	def _DiscoverItemsCB(self, con, iq_obj):
		gajim.log.debug('DiscoverItemsCB')
		q = iq_obj.getTag('query')
		node = q.getAttr('node')
		if not node:
			node = ''
		qp = iq_obj.getQueryPayload()
		items = []
		if not qp:
			qp = []
		for i in qp:
			# CDATA payload is not processed, only nodes
			if not isinstance(i, common.xmpp.simplexml.Node):
				continue
			attr = {}
			for key in i.getAttrs():
				attr[key] = i.getAttrs()[key]
			items.append(attr)
		jid = self.get_full_jid(iq_obj)
		self.dispatch('AGENT_INFO_ITEMS', (jid, node, items))

	def _DiscoverInfoGetCB(self, con, iq_obj):
		gajim.log.debug('DiscoverInfoGetCB')
		iq = iq_obj.buildReply('result')
		q = iq.getTag('query')
		q.addChild('identity', attrs = {'type': 'pc',
						'category': 'client',
						'name': 'Gajim'})
		q.addChild('feature', attrs = {'var': common.xmpp.NS_BYTESTREAM})
		q.addChild('feature', attrs = {'var': common.xmpp.NS_SI})
		q.addChild('feature', attrs = {'var': common.xmpp.NS_FILE})
		q.addChild('feature', attrs = {'var': common.xmpp.NS_MUC})
		self.connection.send(iq)
		raise common.xmpp.NodeProcessed

	def _DiscoverInfoErrorCB(self, con, iq_obj):
		gajim.log.debug('DiscoverInfoErrorCB')
		jid = self.get_full_jid(iq_obj)
		self.dispatch('AGENT_ERROR_INFO', (jid))

	def _DiscoverInfoCB(self, con, iq_obj):
		gajim.log.debug('DiscoverInfoCB')
		# According to JEP-0030:
		# For identity: category, type is mandatory, name is optional.
		# For feature: var is mandatory
		identities, features, data = [], [], []
		q = iq_obj.getTag('query')
		node = q.getAttr('node')
		if not node:
			node = ''
		qc = iq_obj.getQueryChildren()
		if not qc:
			qc = []
		for i in qc:
			if i.getName() == 'identity':
				attr = {}
				for key in i.getAttrs().keys():
					attr[key] = i.getAttr(key)
				identities.append(attr)
			elif i.getName() == 'feature':
				features.append(i.getAttr('var'))
			elif i.getName() == 'x' and i.getAttr('xmlns') == common.xmpp.NS_DATA:
				data.append(common.xmpp.DataForm(node=i))
		jid = self.get_full_jid(iq_obj)
		if identities: #if not: an error occured
			self.dispatch('AGENT_INFO_INFO', (jid, node, identities,
				features, data))

	def _VersionCB(self, con, iq_obj):
		gajim.log.debug('VersionCB')
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.getTag('query')
		qp.setTagData('name', 'Gajim')
		qp.setTagData('version', gajim.version)
		send_os = gajim.config.get('send_os_info')
		if send_os:
			qp.setTagData('os', get_os_info())
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _LastCB(self, con, iq_obj):
		gajim.log.debug('IdleCB')
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.getTag('query')
		if not HAS_IDLE:
			qp.attrs['seconds'] = '0';
		else:
			qp.attrs['seconds'] = idle.getIdleSec()

		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _LastResultCB(self, con, iq_obj):
		gajim.log.debug('LastResultCB')
		qp = iq_obj.getTag('query')
		seconds = qp.getAttr('seconds')
		status = qp.getData()
		try:
			seconds = int(seconds)
		except:
			return
		who = self.get_full_jid(iq_obj)
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		self.dispatch('LAST_STATUS_TIME', (jid_stripped, resource, seconds, status))

	def _VersionResultCB(self, con, iq_obj):
		gajim.log.debug('VersionResultCB')
		client_info = ''
		os_info = ''
		qp = iq_obj.getTag('query')
		if qp.getTag('name'):
			client_info += qp.getTag('name').getData()
		if qp.getTag('version'):
			client_info += ' ' + qp.getTag('version').getData()
		if qp.getTag('os'):
			os_info += qp.getTag('os').getData()
		who = self.get_full_jid(iq_obj)
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		self.dispatch('OS_INFO', (jid_stripped, resource, client_info, os_info))

	def parse_data_form(self, node):
		dic = {}
		tag = node.getTag('title')
		if tag:
			dic['title'] = tag.getData()
		tag = node.getTag('instructions')
		if tag:
			dic['instructions'] = tag.getData()
		i = 0
		for child in node.getChildren():
			if child.getName() != 'field':
				continue
			var = child.getAttr('var')
			ctype = child.getAttr('type')
			label = child.getAttr('label')
			if not var and ctype != 'fixed': # We must have var if type != fixed
				continue
			dic[i] = {}
			if var:
				dic[i]['var'] = var
			if ctype:
				dic[i]['type'] = ctype
			if label:
				dic[i]['label'] = label
			tags = child.getTags('value')
			if len(tags):
				dic[i]['values'] = []
				for tag in tags:
					data = tag.getData()
					if ctype == 'boolean':
						if data in ('yes', 'true', 'assent', '1'):
							data = True
						else:
							data = False
					dic[i]['values'].append(data)
			tag = child.getTag('desc')
			if tag:
				dic[i]['desc'] = tag.getData()
			option_tags = child.getTags('option')
			if len(option_tags):
				dic[i]['options'] = {}
				j = 0
				for option_tag in option_tags:
					dic[i]['options'][j] = {}
					label = option_tag.getAttr('label')
					tags = option_tag.getTags('value')
					dic[i]['options'][j]['values'] = []
					for tag in tags:
						dic[i]['options'][j]['values'].append(tag.getData())
					if not label:
						label = dic[i]['options'][j]['values'][0]
					dic[i]['options'][j]['label'] = label
					j += 1
				if not dic[i].has_key('values'):
					dic[i]['values'] = [dic[i]['options'][0]['values'][0]]
			i += 1
		return dic

	def _MucOwnerCB(self, con, iq_obj):
		gajim.log.debug('MucOwnerCB')
		qp = iq_obj.getQueryPayload()
		node = None
		for q in qp:
			if q.getNamespace() == common.xmpp.NS_DATA:
				node = q
		if not node:
			return
		dic = self.parse_data_form(node)
		self.dispatch('GC_CONFIG', (self.get_full_jid(iq_obj), dic))

	def _MucAdminCB(self, con, iq_obj):
		gajim.log.debug('MucAdminCB')
		items = iq_obj.getTag('query', namespace = common.xmpp.NS_MUC_ADMIN).getTags('item')
		list = {}
		affiliation = ''
		for item in items:
			if item.has_attr('jid') and item.has_attr('affiliation'):
				jid = item.getAttr('jid')
				affiliation = item.getAttr('affiliation')
				list[jid] = {'affiliation': affiliation}
				if item.has_attr('nick'):
					list[jid]['nick'] = item.getAttr('nick')
				if item.has_attr('role'):
					list[jid]['role'] = item.getAttr('role')
				reason = item.getTagData('reason')
				if reason:
					list[jid]['reason'] = reason

		self.dispatch('GC_AFFILIATION', (self.get_full_jid(iq_obj), affiliation, list))

	def _MucErrorCB(self, con, iq_obj):
		gajim.log.debug('MucErrorCB')
		jid = self.get_full_jid(iq_obj)
		errmsg = iq_obj.getError()
		errcode = iq_obj.getErrorCode()
		self.dispatch('MSGERROR', (jid, errcode, errmsg))

	def _getRosterCB(self, con, iq_obj):
		if not self.connection:
			return
		self.connection.getRoster(self._on_roster_set)

	def _on_roster_set(self, roster):
		raw_roster = roster.getRaw()
		roster = {}
		for jid in raw_roster:
			try:
				j = helpers.parse_jid(jid)
			except:
				print >> sys.stderr, _('JID %s is not RFC compliant. It will not be added to your roster. Use roster management tools such as http://jru.jabberstudio.org/ to remove it') % jid
			else:
				roster[j] = raw_roster[jid]

		# Remove or jid
		our_jid = helpers.parse_jid(gajim.get_jid_from_account(self.name))
		if roster.has_key(our_jid):
			del roster[our_jid]

		self.dispatch('ROSTER', roster)

		# continue connection
		if self.connected > 1 and self.continue_connect_info:
			show = self.continue_connect_info[0]
			msg = self.continue_connect_info[1]
			signed = self.continue_connect_info[2]
			self.connected = STATUS_LIST.index(show)
			sshow = helpers.get_xmpp_show(show)
			# send our presence
			if show == 'invisible':
				self.send_invisible_presence(msg, signed, True)
				return
			prio =  unicode(gajim.config.get_per('accounts', self.name,
				'priority'))
			vcard = self.get_cached_vcard(jid)
			if vcard and vcard.has_key('PHOTO') and vcard['PHOTO'].has_key('SHA'):
				self.vcard_sha = vcard['PHOTO']['SHA']
			p = common.xmpp.Presence(typ = None, priority = prio, show = sshow)
			p = self.add_sha(p)
			if msg:
				p.setStatus(msg)
			if signed:
				p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)

			if self.connection:
				self.connection.send(p)
			self.dispatch('STATUS', show)
			# ask our VCard
			self.request_vcard(None)

			# Get bookmarks from private namespace
			self.get_bookmarks()

			# If it's a gmail account,
			# inform the server that we want e-mail notifications
			if gajim.get_server_from_jid(our_jid) == 'gmail.com':
				gajim.log.debug(('%s is a gmail account. Setting option '
					'to get e-mail notifications on the server.') % (our_jid))
				iq = common.xmpp.Iq(typ = 'set', to = our_jid)
				iq.setAttr('id', 'MailNotify')
				query = iq.setTag('usersetting')
				query.setNamespace(common.xmpp.NS_GTALKSETTING)
				query = query.setTag('mailnotifications')
				query.setAttr('value', 'true')
				self.connection.send(iq)
				# Ask how many messages there are now
				iq = common.xmpp.Iq(typ = 'get')
				iq.setAttr('id', '13')
				query = iq.setTag('query')
				query.setNamespace(common.xmpp.NS_GMAILNOTIFY)
				self.connection.send(iq)

			#Inform GUI we just signed in
			self.dispatch('SIGNED_IN', ())
		self.continue_connect_info = None

	def _PrivateCB(self, con, iq_obj):
		'''
		Private Data (JEP 048 and 049)
		'''
		gajim.log.debug('PrivateCB')
		query = iq_obj.getTag('query')
		storage = query.getTag('storage')
		if storage:
			ns = storage.getNamespace()
			if ns == 'storage:bookmarks':
				# Bookmarked URLs and Conferences
				# http://www.jabber.org/jeps/jep-0048.html
				confs = storage.getTags('conference')
				for conf in confs:
					autojoin_val = conf.getAttr('autojoin')
					if autojoin_val is None: # not there (it's optional)
						autojoin_val = False
					bm = { 'name': conf.getAttr('name'),
						   'jid': conf.getAttr('jid'),
						   'autojoin': autojoin_val,
						   'password': conf.getTagData('password'),
					   	'nick': conf.getTagData('nick') }

					self.bookmarks.append(bm)
				self.dispatch('BOOKMARKS', self.bookmarks)

		gajim_tag = query.getTag('gajim')
		if gajim_tag:
			ns = gajim_tag.getNamespace()
			if ns == 'gajim:metacontacts':
				# Meta contacts list
				children_list = {}
				for child in gajim_tag.getChildren():
					parent_jid = child.getAttr('name')
					if not parent_jid:
						continue
					children_list[parent_jid] = []
					for cchild in child.getChildren():
						children_list[parent_jid].append(cchild.getAttr('name'))
				self.dispatch('META_CONTACTS', children_list)
				# We can now continue connection by requesting the roster
				self.connection.initRoster()

			elif ns == 'gajim:prefs':
				# Preferences data
				# http://www.jabber.org/jeps/jep-0049.html
				#TODO: implement this
				pass

	def _PrivateErrorCB(self, con, iq_obj):
		gajim.log.debug('PrivateErrorCB')
		query = iq_obj.getTag('query')
		gajim_tag = query.getTag('gajim')
		if gajim_tag:
			ns = gajim_tag.getNamespace()
			if ns == 'gajim:metacontacts':
				# Private XML Storage (JEP49) is not supported by server
				# Continue connecting
				self.connection.initRoster()

	def build_http_auth_answer(self, iq_obj, answer):
		if answer == 'yes':
			iq = iq_obj.buildReply('result')
		elif answer == 'no':
			iq = iq_obj.buildReply('error')
			iq.setError('not-authorized', 401)
		self.connection.send(iq)

	def _HttpAuthCB(self, con, iq_obj):
		gajim.log.debug('HttpAuthCB')
		opt = gajim.config.get_per('accounts', self.name, 'http_auth')
		if opt in ('yes', 'no'):
			self.build_http_auth_answer(iq_obj, opt)
		else:
			id = iq_obj.getTagAttr('confirm', 'id')
			method = iq_obj.getTagAttr('confirm', 'method')
			url = iq_obj.getTagAttr('confirm', 'url')
			self.dispatch('HTTP_AUTH', (method, url, id, iq_obj));
		raise common.xmpp.NodeProcessed

	def _ErrorCB(self, con, iq_obj):
		errmsg = iq_obj.getError()
		errcode = iq_obj.getErrorCode()
		jid_from = self.get_full_jid(iq_obj)
		id = unicode(iq_obj.getID())
		self.dispatch('ERROR_ANSWER', (id, jid_from, errmsg, errcode))

	def _StanzaArrivedCB(self, con, obj):
		self.last_io = time.time()

	def _IqCB(self, con, iq_obj):
		id = iq_obj.getID()

		# Check if we were waiting a timeout for this id
		found_tim = None
		for tim in self.awaiting_timeouts:
			if id == self.awaiting_timeouts[tim][0]:
				found_tim = tim
				break
		if found_tim:
			del self.awaiting_timeouts[found_tim]

		if id not in self.awaiting_answers:
			return
		if self.awaiting_answers[id][0] == VCARD_PUBLISHED:
			if iq_obj.getType() == 'result':
				self.dispatch('VCARD_PUBLISHED', ())
				vcard_iq = self.awaiting_answers[id][1]
				# Save vcard to HD
				if vcard_iq.getTag('PHOTO') and vcard_iq.getTag('PHOTO').getTag('SHA'):
					new_sha = vcard_iq.getTag('PHOTO').getTagData('SHA')
				else:
					new_sha = ''

				# Save it to file
				our_jid = gajim.get_jid_from_account(self.name)
				path_to_file = os.path.join(gajim.VCARD_PATH, our_jid)
				fil = open(path_to_file, 'w')
				fil.write(str(vcard_iq))
				fil.close()

				# Send new presence if sha changed and we are not invisible
				if self.vcard_sha != new_sha and STATUS_LIST[self.connected] != \
					'invisible':
					self.vcard_sha = new_sha
					sshow = helpers.get_xmpp_show(STATUS_LIST[self.connected])
					prio = unicode(gajim.config.get_per('accounts', self.name,
						'priority'))
					p = common.xmpp.Presence(typ = None, priority = prio,
						show = sshow, status = self.status)
					p = self.add_sha(p)
					self.connection.send(p)
			elif iq_obj.getType() == 'error':
				self.dispatch('VCARD_NOT_PUBLISHED', ())
		elif self.awaiting_answers[id][0] == VCARD_ARRIVED:
			# If vcard is empty, we send to the interface an empty vcard so that
			# it knows it arrived
			if not iq_obj.getTag('vCard'):
				jid = self.awaiting_answers[id][1]
				our_jid = gajim.get_jid_from_account(self.name)
				if jid and jid != our_jid:
					self.dispatch('VCARD', {'jid': jid})
					jid = gajim.get_jid_without_resource(jid)
					# Write an empty file
					path_to_file = os.path.join(gajim.VCARD_PATH, jid)
					fil = open(path_to_file, 'w')
					fil.close()
				elif jid == our_jid:
					self.dispatch('MYVCARD', {'jid': jid})
		del self.awaiting_answers[id]

	def _event_dispatcher(self, realm, event, data):
		if realm == common.xmpp.NS_REGISTER:
			if event == common.xmpp.features_nb.REGISTER_DATA_RECEIVED:
				# data is (agent, DataFrom, is_form)
				if self.new_account_info and\
				self.new_account_info['hostname'] == data[0]:
					#it's a new account
					req = data[1].asDict()
					req['username'] = self.new_account_info['name']
					req['password'] = self.new_account_info['password']
					def _on_register_result(result):
						if not result:
							self.dispatch('ACC_NOT_OK', (self.connection.lastErr))
							return
						self.connected = 0
						self.password = self.new_account_info['password']
						if USE_GPG:
							self.gpg = GnuPG.GnuPG()
							gajim.config.set('usegpg', True)
						else:
							gajim.config.set('usegpg', False)
						gajim.connections[self.name] = self
						self.dispatch('ACC_OK', (self.new_account_info))
						self.new_account_info = None
						self.connection = None
					common.xmpp.features_nb.register(self.connection, data[0],
						req, _on_register_result)
					return
				is_form = data[2]
				if is_form:
					conf = self.parse_data_form(data[1])
				else:
					conf = data[1].asDict()
				self.dispatch('REGISTER_AGENT_INFO', (data[0], conf, is_form))
		elif realm == '':
			if event == common.xmpp.transports.DATA_RECEIVED:
				self.dispatch('STANZA_ARRIVED', unicode(data, errors = 'ignore'))
			elif event == common.xmpp.transports.DATA_SENT:
				self.dispatch('STANZA_SENT', unicode(data))

	def select_next_host(self, hosts):
		hosts_best_prio = []
		best_prio = 65535
		sum_weight = 0
		for h in hosts:
			if h['prio'] < best_prio:
				hosts_best_prio = [h]
				best_prio = h['prio']
				sum_weight = h['weight']
			elif h['prio'] == best_prio:
				hosts_best_prio.append(h)
				sum_weight += h['weight']
		if len(hosts_best_prio) == 1:
			return hosts_best_prio[0]
		r = random.randint(0, sum_weight)
		min_w = sum_weight
		# We return the one for which has the minimum weight and weight >= r
		for h in hosts_best_prio:
			if h['weight'] >= r:
				if h['weight'] <= min_w:
					min_w = h['weight']
		return h

	def connect(self, data = None):
		''' Start a connection to the Jabber server.
		Returns connection, and connection type ('tls', 'ssl', 'tcp', '')
		data MUST contain name, hostname, resource, usessl, proxy,
		use_custom_host, custom_host (if use_custom_host), custom_port (if
		use_custom_host), '''
		if self.connection:
			return self.connection, ''

		if data:
			name = data['name']
			hostname = data['hostname']
			resource = data['resource']
			usessl = data['usessl']
			self.try_connecting_for_foo_secs = 45
			p = data['proxy']
			use_srv = True
			use_custom = data['use_custom_host']
			if use_custom:
				custom_h = data['custom_host']
				custom_p = data['custom_port']
		else:
			name = gajim.config.get_per('accounts', self.name, 'name')
			hostname = gajim.config.get_per('accounts', self.name, 'hostname')
			resource = gajim.config.get_per('accounts', self.name, 'resource')
			usessl = gajim.config.get_per('accounts', self.name, 'usessl')
			self.try_connecting_for_foo_secs = gajim.config.get_per('accounts',
				self.name, 'try_connecting_for_foo_secs')
			p = gajim.config.get_per('accounts', self.name, 'proxy')
			use_srv = gajim.config.get_per('accounts', self.name, 'use_srv')
			use_custom = gajim.config.get_per('accounts', self.name,
				'use_custom_host')
			custom_h = gajim.config.get_per('accounts', self.name, 'custom_host')
			custom_p = gajim.config.get_per('accounts', self.name, 'custom_port')

		#create connection if it doesn't already exist
		self.connected = 1
		if p and p in gajim.config.get_per('proxies'):
			proxy = {'host': gajim.config.get_per('proxies', p, 'host')}
			proxy['port'] = gajim.config.get_per('proxies', p, 'port')
			proxy['user'] = gajim.config.get_per('proxies', p, 'user')
			proxy['password'] = gajim.config.get_per('proxies', p, 'pass')
		else:
			proxy = None

		h = hostname
		p = 5222
		# autodetect [for SSL in 5223/443 and for TLS if broadcasted]
		secur = None
		if usessl:
			p = 5223
			secur = 1 # 1 means force SSL no matter what the port will be
			use_srv = False # wants ssl? disable srv lookup
		if use_custom:
			h = custom_h
			p = custom_p
			use_srv = False

		hosts = []
		# SRV resolver
		self._proxy = proxy
		self._secure = secur
		self._hosts = [ {'host': h, 'port': p, 'prio': 10, 'weight': 10} ]
		self._hostname = hostname
		if use_srv:
			# add request for srv query to the resolve, on result '_on_resolve' will be called
			gajim.resolver.resolve('_xmpp-client._tcp.' + h.encode('utf-8'), self._on_resolve)
		else:
			self._on_resolve('', [])

	def _on_resolve(self, host, result_array):
		# SRV query returned at least one valid result, we put it in hosts dict
		if len(result_array) != 0:
			self._hosts = [i for i in result_array]
		self.connect_to_next_host()

	def connect_to_next_host(self):
		if len(self._hosts):
			if gajim.verbose:
				con = common.xmpp.NonBlockingClient(self._hostname, caller = self,
					on_connect = self.on_connect_success,
					on_connect_failure = self.connect_to_next_host)
			else:
				con = common.xmpp.NonBlockingClient(self._hostname, debug = [], caller = self,
					on_connect = self.on_connect_success,
					on_connect_failure = self.connect_to_next_host)
			# increase default timeout for server responses
			common.xmpp.dispatcher_nb.DEFAULT_TIMEOUT_SECONDS = self.try_connecting_for_foo_secs
			con.set_idlequeue(gajim.idlequeue)
			host = self.select_next_host(self._hosts)
			self._current_host = host
			self._hosts.remove(host)
			res = con.connect((host['host'], host['port']), proxy = self._proxy,
				secure = self._secure)
			return
		else:
			self._connect_failure(None)

	def _connect_failure(self, con_type):
		if not con_type:
			# we are not retrying, and not conecting
			if not self.retrycount and self.connected != 0:
				self.connected = 0
				self.dispatch('STATUS', 'offline')
				self.dispatch('ERROR', (_('Could not connect to "%s"') % self._hostname,
					_('Check your connection or try again later.')))

	def _connect_success(self, con, con_type):
		if not self.connected: # We went offline during connecting process
			return None, ''
		self.hosts = []
		if not con_type:
			gajim.log.debug('Could not connect to %s:%s' % (self._current_host['host'],
				self._current_host['port']))
		self.connected_hostname = self._current_host['host']
		con.RegisterDisconnectHandler(self._disconnectedReconnCB)
		gajim.log.debug(_('Connected to server %s:%s with %s') % (self._current_host['host'],
			self._current_host['port'], con_type))
		# Ask meta_contacts before roster
		self.get_meta_contacts()
		self._register_handlers(con, con_type)
		return True

	def _register_handlers(self, con, con_type):
		self.peerhost = con.get_peerhost()
		# notify the gui about con_type
		self.dispatch('CON_TYPE', con_type)

		con.RegisterHandler('message', self._messageCB)
		con.RegisterHandler('presence', self._presenceCB)
		con.RegisterHandler('iq', self._vCardCB, 'result',
			common.xmpp.NS_VCARD)
		con.RegisterHandler('iq', self._rosterSetCB, 'set',
			common.xmpp.NS_ROSTER)
		con.RegisterHandler('iq', self._siSetCB, 'set',
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._siErrorCB, 'error',
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._siResultCB, 'result',
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._discoGetCB, 'get',
			common.xmpp.NS_DISCO)
		con.RegisterHandler('iq', self._bytestreamSetCB, 'set',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._bytestreamResultCB, 'result',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._bytestreamErrorCB, 'error',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._DiscoverItemsCB, 'result',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._DiscoverItemsErrorCB, 'error',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._DiscoverInfoCB, 'result',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._DiscoverInfoErrorCB, 'error',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._VersionCB, 'get',
			common.xmpp.NS_VERSION)
		con.RegisterHandler('iq', self._LastCB, 'get',
			common.xmpp.NS_LAST)
		con.RegisterHandler('iq', self._LastResultCB, 'result',
			common.xmpp.NS_LAST)
		con.RegisterHandler('iq', self._VersionResultCB, 'result',
			common.xmpp.NS_VERSION)
		con.RegisterHandler('iq', self._MucOwnerCB, 'result',
			common.xmpp.NS_MUC_OWNER)
		con.RegisterHandler('iq', self._MucAdminCB, 'result',
			common.xmpp.NS_MUC_ADMIN)
		con.RegisterHandler('iq', self._getRosterCB, 'result',
			common.xmpp.NS_ROSTER)
		con.RegisterHandler('iq', self._PrivateCB, 'result',
			common.xmpp.NS_PRIVATE)
		con.RegisterHandler('iq', self._PrivateErrorCB, 'error',
			common.xmpp.NS_PRIVATE)
		con.RegisterHandler('iq', self._HttpAuthCB, 'get',
			common.xmpp.NS_HTTP_AUTH)
		con.RegisterHandler('iq', self._gMailNewMailCB, 'set',
			common.xmpp.NS_GMAILNOTIFY)
		con.RegisterHandler('iq', self._gMailQueryCB, 'result',
			common.xmpp.NS_GMAILNOTIFY)
		con.RegisterHandler('iq', self._DiscoverInfoGetCB, 'get',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._ErrorCB, 'error')
		con.RegisterHandler('iq', self._IqCB)
		con.RegisterHandler('iq', self._StanzaArrivedCB)
		con.RegisterHandler('presence', self._StanzaArrivedCB)
		con.RegisterHandler('message', self._StanzaArrivedCB)

		name = gajim.config.get_per('accounts', self.name, 'name')
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		resource = gajim.config.get_per('accounts', self.name, 'resource')
		self.connection = con
		con.auth(name, self.password, resource, 1, self.__on_auth)

	def __on_auth(self, con, auth):
		if not con:
			self.connected = 0
			self.dispatch('STATUS', 'offline')
			self.dispatch('ERROR', (_('Could not connect to "%s"') % self._hostname,
				_('Check your connection or try again later')))
			if self.on_connect_auth:
				self.on_connect_auth(None)
				self.on_connect_auth = None
				return
		if not self.connected: # We went offline during connecting process
			if self.on_connect_auth:
				self.on_connect_auth(None)
				self.on_connect_auth = None
				return
		if hasattr(con, 'Resource'):
			self.server_resource = con.Resource
		if auth:
			self.last_io = time.time()
			self.connected = 2
			if self.on_connect_auth:
				self.on_connect_auth(con)
				self.on_connect_auth = None
		else:
			# Forget password if needed
			if not gajim.config.get_per('accounts', self.name, 'savepass'):
				self.password = None
			gajim.log.debug("Couldn't authenticate to %s" % self._hostname)
			self.connected = 0
			self.dispatch('STATUS', 'offline')
			self.dispatch('ERROR', (_('Authentication failed with "%s"') % self._hostname,
				_('Please check your login and password for correctness.')))
			if self.on_connect_auth:
				self.on_connect_auth(None)
				self.on_connect_auth = None
	# END connect

	def quit(self, kill_core):
		if kill_core:
			if self.connected > 1:
				self.connected = 0
				self.connection.disconnect()
				self.time_to_reconnect = None
			return

	def build_privacy_rule(self, name, action):
		'''Build a Privacy rule stanza for invisibility'''
		iq = common.xmpp.Iq('set', common.xmpp.NS_PRIVACY, xmlns = '')
		l = iq.getTag('query').setTag('list', {'name': name})
		i = l.setTag('item', {'action': action, 'order': '1'})
		i.setTag('presence-out')
		return iq

	def activate_privacy_rule(self, name):
		'''activate a privacy rule'''
		iq = common.xmpp.Iq('set', common.xmpp.NS_PRIVACY, xmlns = '')
		iq.getTag('query').setTag('active', {'name': name})
		self.connection.send(iq)

	def send_invisible_presence(self, msg, signed, initial = False):
		# try to set the privacy rule
		iq = self.build_privacy_rule('invisible', 'deny')
		self.connection.SendAndCallForResponse(iq, self._continue_invisible,
			{'msg': msg, 'signed': signed, 'initial': initial})

	def _continue_invisible(self, con, iq_obj, msg, signed, initial):
		ptype = ''
		show = ''
		# FIXME: JEP 126 need some modifications (see http://lists.jabber.ru/pipermail/ejabberd/2005-July/001252.html). So I disable it for the moment
		if 1 or iq_obj.getType() == 'error': #server doesn't support privacy lists
			# We use the old way which is not xmpp complient
			ptype = 'invisible'
			show = 'invisible'
		else:
			# active the privacy rule
			self.privacy_rules_supported = True
			self.activate_privacy_rule('invisible')
		prio = unicode(gajim.config.get_per('accounts', self.name, 'priority'))
		p = common.xmpp.Presence(typ = ptype, priority = prio, show = show)
		p = self.add_sha(p)
		if msg:
			p.setStatus(msg)
		if signed:
			p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)
		self.connection.send(p)
		self.dispatch('STATUS', 'invisible')
		if initial:
			#ask our VCard
			self.request_vcard(None)

			#Get bookmarks from private namespace
			self.get_bookmarks()

			#Inform GUI we just signed in
			self.dispatch('SIGNED_IN', ())

	def test_gpg_passphrase(self, password):
		self.gpg.passphrase = password
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		signed = self.gpg.sign('test', keyID)
		self.gpg.password = None
		return signed != 'BAD_PASSPHRASE'

	def get_signed_msg(self, msg):
		signed = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		if keyID and USE_GPG:
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			if self.connected < 2 and self.gpg.passphrase is None and \
				not use_gpg_agent:
				# We didn't set a passphrase
				self.dispatch('ERROR', (_('OpenPGP passphrase was not given'),
					#%s is the account name here
					_('You will be connected to %s without OpenPGP.') % self.name))
			elif self.gpg.passphrase is not None or use_gpg_agent:
				signed = self.gpg.sign(msg, keyID)
				if signed == 'BAD_PASSPHRASE':
					signed = ''
					if self.connected < 2:
						self.dispatch('BAD_PASSPHRASE', ())
		return signed

	def connect_and_auth(self):
		self.on_connect_success = self._connect_success
		self.connect()

	def connect_and_init(self, show, msg, signed):
		self.continue_connect_info = [show, msg, signed]
		self.on_connect_auth = self._init_roster
		self.connect_and_auth()

	def _init_roster(self, con):
		self.connection = con
		if self.connection:
			con.set_send_timeout(self.keepalives, self.send_keepalive)
			self.connection.onreceive(None)
			# Ask meta_contacts before roster
			self.get_meta_contacts()

	def change_status(self, show, msg, sync = False, auto = False):
		self.change_status2(show, msg, auto)

	def change_status2(self, show, msg, auto = False):
		if not show in STATUS_LIST:
			return -1
		sshow = helpers.get_xmpp_show(show)
		if not msg:
			msg = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		if keyID and USE_GPG and not msg:
			lowered_uf_status_msg = helpers.get_uf_show(show).lower()
			# do not show I'm invisible!
			if lowered_uf_status_msg == _('invisible'):
				lowered_uf_status_msg = _('offline')
			msg = _("I'm %s") % lowered_uf_status_msg
		signed = ''
		if not auto and not show == 'offline':
			signed = self.get_signed_msg(msg)
		self.status = msg
		if show != 'offline' and not self.connected:
			self.connect_and_init(show, msg, signed)

		elif show == 'offline' and self.connected:
			self.connected = 0
			if self.connection:
				self.on_purpose = True
				p = common.xmpp.Presence(typ = 'unavailable')
				p = self.add_sha(p)
				if msg:
					p.setStatus(msg)
				self.remove_all_transfers()
				self.time_to_reconnect = None
				self.connection.start_disconnect(p, self._on_disconnected)
			else:
				self.time_to_reconnect = None
				self._on_disconnected()

		elif show != 'offline' and self.connected:
			was_invisible = self.connected == STATUS_LIST.index('invisible')
			self.connected = STATUS_LIST.index(show)
			if show == 'invisible':
				self.send_invisible_presence(msg, signed)
				return
			if was_invisible and self.privacy_rules_supported:
				iq = self.build_privacy_rule('visible', 'allow')
				self.connection.send(iq)
				self.activate_privacy_rule('visible')
			prio = unicode(gajim.config.get_per('accounts', self.name,
				'priority'))
			p = common.xmpp.Presence(typ = None, priority = prio, show = sshow)
			p = self.add_sha(p)
			if msg:
				p.setStatus(msg)
			if signed:
				p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)
			if self.connection:
				self.connection.send(p)
			self.dispatch('STATUS', show)

	def _on_disconnected(self):
		''' called when a disconnect request has completed successfully'''
		self.dispatch('STATUS', 'offline')
		self.connection = None

	def get_status(self):
		return STATUS_LIST[self.connected]

	def send_motd(self, jid, subject = '', msg = ''):
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(to = jid, body = msg, subject = subject)
		self.connection.send(msg_iq)

	def send_message(self, jid, msg, keyID, type = 'chat', subject='',
					 chatstate = None, msg_id = None, composing_jep = None):
		if not self.connection:
			return
		if not msg and chatstate is None:
			return
		msgtxt = msg
		msgenc = ''
		if keyID and USE_GPG:
			#encrypt
			msgenc = self.gpg.encrypt(msg, [keyID])
			if msgenc:
				msgtxt = '[This message is encrypted]'
				lang = os.getenv('LANG')
				if lang is not None or lang != 'en': # we're not english
					msgtxt = _('[This message is encrypted]') +\
						' ([This message is encrypted])' # one  in locale and one en
		if type == 'chat':
			msg_iq = common.xmpp.Message(to = jid, body = msgtxt, typ = type)
		else:
			if subject:
				msg_iq = common.xmpp.Message(to = jid, body = msgtxt,
					typ = 'normal', subject = subject)
			else:
				msg_iq = common.xmpp.Message(to = jid, body = msgtxt,
					typ = 'normal')
		if msgenc:
			msg_iq.setTag(common.xmpp.NS_ENCRYPTED + ' x').setData(msgenc)

		# chatstates - if peer supports jep85 or jep22, send chatstates
		# please note that the only valid tag inside a message containing a <body>
		# tag is the active event
		if chatstate is not None:
			if composing_jep == 'JEP-0085' or not composing_jep:
				# JEP-0085
				msg_iq.setTag(chatstate, namespace = common.xmpp.NS_CHATSTATES)
			if composing_jep == 'JEP-0022' or not composing_jep:
				# JEP-0022
				chatstate_node = msg_iq.setTag('x', namespace = common.xmpp.NS_EVENT)
				if not msgtxt: # when no <body>, add <id>
					if not msg_id: # avoid putting 'None' in <id> tag
						msg_id = ''
					chatstate_node.setTagData('id', msg_id)
				# when msgtxt, requests JEP-0022 composing notification
				if chatstate is 'composing' or msgtxt: 
					chatstate_node.addChild(name = 'composing') 

		self.connection.send(msg_iq)
		no_log_for = gajim.config.get_per('accounts', self.name, 'no_log_for')
		ji = gajim.get_jid_without_resource(jid)
		if self.name not in no_log_for and ji not in no_log_for:
			log_msg = msg
			if subject:
				log_msg = _('Subject: %s\n%s') % (subject, msg)
			if log_msg:
				if type == 'chat':
					kind = 'chat_msg_sent'
				else:
					kind = 'single_msg_sent'
				gajim.logger.write(kind, jid, log_msg)
		self.dispatch('MSGSENT', (jid, msg, keyID))

	def send_stanza(self, stanza):
		''' send a stanza untouched '''
		if not self.connection:
			return
		self.connection.send(stanza)

	def ack_subscribed(self, jid):
		if not self.connection:
			return
		gajim.log.debug('ack\'ing subscription complete for %s' % jid)
		p = common.xmpp.Presence(jid, 'subscribe')
		self.connection.send(p)

	def ack_unsubscribed(self, jid):
		if not self.connection:
			return
		gajim.log.debug('ack\'ing unsubscription complete for %s' % jid)
		p = common.xmpp.Presence(jid, 'unsubscribe')
		self.connection.send(p)

	def request_subscription(self, jid, msg, name = '', groups = []):
		if not self.connection:
			return
		gajim.log.debug('subscription request for %s' % jid)
		# RFC 3921 section 8.2
		infos = {'jid': jid}
		if name:
			infos['name'] = name
		iq = common.xmpp.Iq('set', common.xmpp.NS_ROSTER)
		q = iq.getTag('query')
		item = q.addChild('item', attrs = infos)
		for g in groups:
			item.addChild('group').setData(g)
		self.connection.send(iq)

		p = common.xmpp.Presence(jid, 'subscribe')
		p = self.add_sha(p)
		if not msg:
			msg = _('I would like to add you to my roster.')
		p.setStatus(msg)
		self.connection.send(p)

	def send_authorization(self, jid):
		if not self.connection:
			return
		p = common.xmpp.Presence(jid, 'subscribed')
		p = self.add_sha(p)
		self.connection.send(p)

	def refuse_authorization(self, jid):
		if not self.connection:
			return
		p = common.xmpp.Presence(jid, 'unsubscribed')
		p = self.add_sha(p)
		self.connection.send(p)

	def unsubscribe(self, jid, remove_auth = True):
		if not self.connection:
			return
		if remove_auth:
			self.connection.getRoster().delItem(jid)
		else:
			self.connection.getRoster().Unsubscribe(jid)
			self.update_contact(jid, '', [])

	def _continue_unsubscribe(self, con, iq_obj, agent):
		if iq_obj.getTag('error'):
			# error, probably not a real agent
			return
		self.connection.getRoster().delItem(agent)

	def unsubscribe_agent(self, agent):
		if not self.connection:
			return
		iq = common.xmpp.Iq('set', common.xmpp.NS_REGISTER, to = agent)
		iq.getTag('query').setTag('remove')
		self.connection.SendAndCallForResponse(iq, self._continue_unsubscribe,
			{'agent': agent})
		return

	def update_contact(self, jid, name, groups):
		'''update roster item on jabber server'''
		if self.connection:
			self.connection.getRoster().setItem(jid = jid, name = name,
				groups = groups)

	def _ReceivedRegInfo(self, con, resp, agent):
		common.xmpp.features_nb._ReceivedRegInfo(con, resp, agent)
		self._IqCB(con, resp)

	def request_register_agent_info(self, agent):
		if not self.connection:
			return None
		iq=common.xmpp.Iq('get', common.xmpp.NS_REGISTER, to=agent)
		id = self.connection.getAnID()
		iq.setID(id)
		# Wait the answer during 30 secondes
		self.awaiting_timeouts[time.time() + 30] = (id,
			_('Registration information for transport %s has not arrived in time' % \
			agent))
		self.connection.SendAndCallForResponse(iq, self._ReceivedRegInfo,
			{'agent': agent})

	def register_agent(self, agent, info, is_form = False):
		if not self.connection:
			return
		if is_form:
			iq = common.xmpp.Iq('set', common.xmpp.NS_REGISTER, to = agent)
			query = iq.getTag('query')
			self.build_data_from_dict(query, info)
			self.connection.send(iq)
		else:
			# fixed: blocking
			common.xmpp.features_nb.register(self.connection, agent, info, None)

	def new_account(self, name, config, sync = False):
		self.new_account2(name, config)

	def new_account2(self, name, config):
		# If a connection already exist we cannot create a new account
		if self.connection:
			return
		self._hostname = config['hostname']
		self.new_account_info = config
		self.name = name
		self.on_connect_success = self._on_new_account
		self.connect(config)

	def _on_new_account(self,con, con_type):
		if not con_type:
			self.dispatch('ACC_NOT_OK',
				(_('Could not connect to "%s"') % self._hostname))
			return
		self.connection = con
		common.xmpp.features_nb.getRegInfo(con, self._hostname)

	def account_changed(self, new_name):
		self.name = new_name

	def request_last_status_time(self, jid, resource):
		if not self.connection:
			return
		to_whom_jid = jid
		if resource:
			to_whom_jid += '/' + resource
		iq = common.xmpp.Iq(to = to_whom_jid, typ = 'get', queryNS =\
			common.xmpp.NS_LAST)
		self.connection.send(iq)

	def request_os_info(self, jid, resource):
		if not self.connection:
			return
		to_whom_jid = jid
		if resource:
			to_whom_jid += '/' + resource
		iq = common.xmpp.Iq(to = to_whom_jid, typ = 'get', queryNS =\
			common.xmpp.NS_VERSION)
		self.connection.send(iq)

	def get_cached_vcard(self, fjid):
		'''return the vcard as a dict
		return {} if vcard was too old
		return None if we don't have cached vcard'''
		jid = gajim.get_jid_without_resource(fjid)
		path_to_file = os.path.join(gajim.VCARD_PATH, jid)
		if os.path.isfile(path_to_file):
			# We have the vcard cached
			f = open(path_to_file)
			c = f.read()
			f.close()
			card = common.xmpp.Node(node = c)
			vcard = self.node_to_dict(card)
			if vcard.has_key('PHOTO'):
				if not isinstance(vcard['PHOTO'], dict):
					del vcard['PHOTO']
				elif vcard['PHOTO'].has_key('SHA'):
					cached_sha = vcard['PHOTO']['SHA']
					if self.vcard_shas.has_key(jid) and self.vcard_shas[jid] != \
						cached_sha:
						# user change his vcard so don't use the cached one
						return {}
			vcard['jid'] = jid
			vcard['resource'] = gajim.get_resource_from_jid(fjid)
			return vcard
		return None

	def request_vcard(self, jid = None):
		'''request the VCARD'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get')
		if jid:
			iq.setTo(jid)
		iq.setTag(common.xmpp.NS_VCARD + ' vCard')

		id = self.connection.getAnID()
		iq.setID(id)
		self.awaiting_answers[id] = (VCARD_ARRIVED, jid)
		self.connection.send(iq)
			#('VCARD', {entry1: data, entry2: {entry21: data, ...}, ...})

	def send_vcard(self, vcard):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set')
		iq2 = iq.setTag(common.xmpp.NS_VCARD + ' vCard')
		for i in vcard:
			if i == 'jid':
				continue
			if isinstance(vcard[i], dict):
				iq3 = iq2.addChild(i)
				for j in vcard[i]:
					iq3.addChild(j).setData(vcard[i][j])
			elif type(vcard[i]) == type([]):
				for j in vcard[i]:
					iq3 = iq2.addChild(i)
					for k in j:
						iq3.addChild(k).setData(j[k])
			else:
				iq2.addChild(i).setData(vcard[i])

		id = self.connection.getAnID()
		iq.setID(id)
		self.connection.send(iq)

		# Add the sha of the avatar
		if vcard.has_key('PHOTO') and isinstance(vcard['PHOTO'], dict) and \
		vcard['PHOTO'].has_key('BINVAL'):
			photo = vcard['PHOTO']['BINVAL']
			photo_decoded = base64.decodestring(photo)
			avatar_sha = sha.sha(photo_decoded).hexdigest()
			iq2.getTag('PHOTO').setTagData('SHA', avatar_sha)

		self.awaiting_answers[id] = (VCARD_PUBLISHED, iq2)

	def get_settings(self):
		''' Get Gajim settings as described in JEP 0049 '''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='gajim', namespace='gajim:prefs')
		self.connection.send(iq)

	def get_bookmarks(self):
		'''Get Bookmarks from storage as described in JEP 0048'''
		self.bookmarks = [] #avoid multiple bookmarks when re-connecting
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq2.addChild(name='storage', namespace='storage:bookmarks')
		self.connection.send(iq)

	def store_bookmarks(self):
		''' Send bookmarks to the storage namespace '''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='set')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='storage', namespace='storage:bookmarks')
		for bm in self.bookmarks:
			iq4 = iq3.addChild(name = "conference")
			iq4.setAttr('jid', bm['jid'])
			iq4.setAttr('autojoin', bm['autojoin'])
			iq4.setAttr('name', bm['name'])
			# Only add optional elements if not empty
			# Note: need to handle both None and '' as empty
			#   thus shouldn't use "is not None"
			if bm['nick']:
				iq5 = iq4.setTagData('nick', bm['nick'])
			if bm['password']:
				iq5 = iq4.setTagData('password', bm['password'])
		self.connection.send(iq)

	def get_meta_contacts(self):
		'''Get meta_contacts list from storage as described in JEP 0049'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq2.addChild(name='gajim', namespace='gajim:metacontacts')
		self.connection.send(iq)

	def store_meta_contacts(self, children_list):
		''' Send meta contacts to the storage namespace '''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='set')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='gajim', namespace='gajim:metacontacts')
		for parent_jid in children_list:
			parent_tag = iq3.addChild(name='parent', attrs = {'name': parent_jid})
			for child_jid in children_list[parent_jid]:
				parent_tag.addChild(name='child', attrs = {'name': child_jid})
		self.connection.send(iq)

	def send_agent_status(self, agent, ptype):
		if not self.connection:
			return
		p = common.xmpp.Presence(to = agent, typ = ptype)
		p = self.add_sha(p)
		self.connection.send(p)

	def join_gc(self, nick, room, server, password):
		if not self.connection:
			return
		show = helpers.get_xmpp_show(STATUS_LIST[self.connected])
		p = common.xmpp.Presence(to = '%s@%s/%s' % (room, server, nick),
			show = show, status = self.status)
		if gajim.config.get('send_sha_in_gc_presence'):
			p = self.add_sha(p)
		t = p.setTag(common.xmpp.NS_MUC + ' x')
		if password:
			t.setTagData('password', password)
		self.connection.send(p)
		#last date/time in history to avoid duplicate
		# FIXME: This JID needs to be normalized; see #1364
		jid='%s@%s' % (room, server)
		last_log = gajim.logger.get_last_date_that_has_logs(jid)
		if last_log is None:
			last_log = 0
		self.last_history_line[jid]= last_log

	def send_gc_message(self, jid, msg):
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(jid, msg, typ = 'groupchat')
		self.connection.send(msg_iq)
		self.dispatch('MSGSENT', (jid, msg))

	def send_gc_subject(self, jid, subject):
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(jid,typ = 'groupchat', subject = subject)
		self.connection.send(msg_iq)

	def request_gc_config(self, room_jid):
		iq = common.xmpp.Iq(typ = 'get', queryNS = common.xmpp.NS_MUC_OWNER,
			to = room_jid)
		self.connection.send(iq)

	def change_gc_nick(self, room_jid, nick):
		if not self.connection:
			return
		p = common.xmpp.Presence(to = '%s/%s' % (room_jid, nick))
		p = self.add_sha(p)
		self.connection.send(p)

	def send_gc_status(self, nick, jid, show, status):
		if not self.connection:
			return
		ptype = None
		if show == 'offline':
			ptype = 'unavailable'
		show = helpers.get_xmpp_show(show)
		p = common.xmpp.Presence(to = '%s/%s' % (jid, nick), typ = ptype,
			show = show, status = status)
		if gajim.config.get('send_sha_in_gc_presence'):
			p = self.add_sha(p)
		# send instantly so when we go offline, status is sent to gc before we
		# disconnect from jabber server
		self.connection.send(p)

	def gc_set_role(self, room_jid, nick, role, reason = ''):
		'''role is for all the life of the room so it's based on nick'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query').setTag('item')
		item.setAttr('nick', nick)
		item.setAttr('role', role)
		if reason:
			item.addChild(name = 'reason', payload = reason)
		self.connection.send(iq)

	def gc_set_affiliation(self, room_jid, jid, affiliation, reason = ''):
		'''affiliation is for all the life of the room so it's based on jid'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query').setTag('item')
		item.setAttr('jid', jid)
		item.setAttr('affiliation', affiliation)
		if reason:
			item.addChild(name = 'reason', payload = reason)
		self.connection.send(iq)

	def send_gc_affiliation_list(self, room_jid, list):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS = \
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query')
		for jid in list:
			item_tag = item.addChild('item', {'jid': jid,
				'affiliation': list[jid]['affiliation']})
			if list[jid].has_key('reason') and list[jid]['reason']:
				item_tag.setTagData('reason', list[jid]['reason'])
		self.connection.send(iq)

	def get_affiliation_list(self, room_jid, affiliation):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get', to = room_jid, queryNS = \
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query').setTag('item')
		item.setAttr('affiliation', affiliation)
		self.connection.send(iq)

	def build_data_from_dict(self, query, config):
		x = query.setTag(common.xmpp.NS_DATA + ' x', attrs = {'type': 'submit'})
		i = 0
		while config.has_key(i):
			if not config[i].has_key('type'):
				i += 1
				continue
			if config[i]['type'] == 'fixed':
				i += 1
				continue
			tag = x.addChild('field')
			if config[i].has_key('var'):
				tag.setAttr('var', config[i]['var'])
			if config[i].has_key('values'):
				for val in config[i]['values']:
					if val == False:
						val = '0'
					elif val == True:
						val = '1'
					# Force to create a new child
					tag.addChild('value').addData(val)
			i += 1

	def send_gc_config(self, room_jid, config):
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_OWNER)
		query = iq.getTag('query')
		self.build_data_from_dict(query, config)
		self.connection.send(iq)

	def gpg_passphrase(self, passphrase):
		if USE_GPG:
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			if use_gpg_agent:
				self.gpg.passphrase = None
			else:
				self.gpg.passphrase = passphrase

	def ask_gpg_keys(self):
		if USE_GPG:
			keys = self.gpg.get_keys()
			return keys
		return None

	def ask_gpg_secrete_keys(self):
		if USE_GPG:
			keys = self.gpg.get_secret_keys()
			return keys
		return None

	def change_password(self, password):
		if not self.connection:
			return
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		username = gajim.config.get_per('accounts', self.name, 'name')
		iq = common.xmpp.Iq(typ = 'set', to = hostname)
		q = iq.setTag(common.xmpp.NS_REGISTER + ' query')
		q.setTagData('username',username)
		q.setTagData('password',password)
		self.connection.send(iq)

	def unregister_account(self, on_remove_success):
		# no need to write this as a class method and keep the value of on_remove_success
		# as a class property as pass it as an argument
		def _on_unregister_account_connect(con):
			self.on_connect_auth = None
			if self.connected > 1:
				hostname = gajim.config.get_per('accounts', self.name, 'hostname')
				iq = common.xmpp.Iq(typ = 'set', to = hostname)
				q = iq.setTag(common.xmpp.NS_REGISTER + ' query').setTag('remove')
				con.send(iq)
				on_remove_success(True)
				return
			on_remove_success(False)
		if self.connected == 0:
			self.on_connect_auth = _on_unregister_account_connect
			self.connect_and_auth()
		else:
			_on_unregister_account_connect(self.connection)

	def send_invite(self, room, to, reason=''):
		'''sends invitation'''
		message=common.xmpp.Message(to = room)
		c = message.addChild(name = 'x', namespace = common.xmpp.NS_MUC_USER)
		c = c.addChild(name = 'invite', attrs={'to' : to})
		if reason != '':
			c.setTagData('reason', reason)
		self.connection.send(message)

	def send_keepalive(self):
		# nothing received for the last foo seconds (60 secs by default)
		if self.connection:
			self.connection.send(' ')

	def _reconnect_alarm(self):
		if self.time_to_reconnect:
			if self.connected < 2:
				self._reconnect()
			else:
				self.time_to_reconnect = None

# END Connection
