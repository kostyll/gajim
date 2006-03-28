#!/bin/sh
''':'
exec python -OOt "$0" ${1+"$@"}
' '''
##	gajim.py
##
## Contributors for this file:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Nikos Kouremenos <kourem@gmail.com>
## - Dimitur Kirov <dkirov@gmail.com>
## - Travis Shirk <travis@pobox.com>
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

import sys
import os

import message_control

from chat_control import ChatControlBase

from common import exceptions
from common import i18n
i18n.init()
_ = i18n._

try:
	import gtk
except RuntimeError, msg:
	if str(msg) == 'could not open display':
		print >> sys.stderr, _('Gajim needs Xserver to run. Quiting...')
		sys.exit()
pritext = ''
if gtk.pygtk_version < (2, 6, 0):
	pritext = _('Gajim needs PyGTK 2.6 or above')
	sectext = _('Gajim needs PyGTK 2.6 or above to run. Quiting...')
elif gtk.gtk_version < (2, 6, 0):
	pritext = _('Gajim needs GTK 2.6 or above')
	sectext = _('Gajim needs GTK 2.6 or above to run. Quiting...')

try:
	import gtk.glade # check if user has libglade (in pygtk and in gtk)
except ImportError:
	pritext = _('GTK+ runtime is missing libglade support')
	if os.name == 'nt':
		sectext = _('Please remove your current GTK+ runtime and install the latest stable version from %s') % 'http://gladewin32.sourceforge.net'
	else:
		sectext = _('Please make sure that GTK+ and PyGTK have libglade support in your system.')

try:
	from common import check_paths
except exceptions.PysqliteNotAvailable, e:
	pritext = _('Gajim needs PySQLite2 to run')
	sectext = str(e)

if pritext:
	dlg = gtk.MessageDialog(None, 
				gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
				gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, message_format = pritext)

	dlg.format_secondary_text(sectext)
	dlg.run()
	dlg.destroy()
	sys.exit()

path = os.getcwd()
if '.svn' in os.listdir(path) or '_svn' in os.listdir(path):
	# import gtkexcepthook only for those that run svn
	# those than run with --verbose run from terminal so no need to care
	# about those
	import gtkexcepthook
del path

import gobject

import sre
import signal
import getopt
import time
import threading

import gtkgui_helpers
import notify

import common.sleepy

from common.xmpp import idlequeue
from common import nslookup
from common import proxy65_manager
from common import socks5
from common import gajim
from common import helpers
from common import optparser

profile = ''
try:
	opts, args = getopt.getopt(sys.argv[1:], 'hvp:', ['help', 'verbose',
		'profile=', 'sm-config-prefix=', 'sm-client-id='])
except getopt.error, msg:
	print msg
	print 'for help use --help'
	sys.exit(2)
for o, a in opts:
	if o in ('-h', '--help'):
		print 'gajim [--help] [--verbose] [--profile name]'
		sys.exit()
	elif o in ('-v', '--verbose'):
		gajim.verbose = True
	elif o in ('-p', '--profile'): # gajim --profile name
		profile = a

config_filename = os.path.expanduser('~/.gajim/config')
if os.name == 'nt':
	try:
		# Documents and Settings\[User Name]\Application Data\Gajim\logs
		config_filename = os.environ['appdata'] + '/Gajim/config'
	except KeyError:
		# win9x so ./config
		config_filename = 'config'

if profile:
	config_filename += '.%s' % profile

parser = optparser.OptionsParser(config_filename)

import roster_window
import systray
import dialogs
import vcard
import config

GTKGUI_GLADE = 'gtkgui.glade'


class GlibIdleQueue(idlequeue.IdleQueue):
	''' 
	Extends IdleQueue to use glib io_add_wath, instead of select/poll
	In another, `non gui' implementation of Gajim IdleQueue can be used safetly.
	'''
	def init_idle(self):
		''' this method is called at the end of class constructor.
		Creates a dict, which maps file/pipe/sock descriptor to glib event id'''
		self.events = {}
		if gtk.pygtk_version >= (2, 8, 0):
			# time() is already called in glib, we just get the last value 
			# overrides IdleQueue.current_time()
			self.current_time = lambda: gobject.get_current_time()
			
	def add_idle(self, fd, flags):
		''' this method is called when we plug a new idle object.
		Start listening for events from fd
		'''
		res = gobject.io_add_watch(fd, flags, self.process_events, 
										priority=gobject.PRIORITY_LOW)
		# store the id of the watch, so that we can remove it on unplug
		self.events[fd] = res
	
	def remove_idle(self, fd):
		''' this method is called when we unplug a new idle object.
		Stop listening for events from fd
		'''
		gobject.source_remove(self.events[fd])
		del(self.events[fd])
	
	def process(self):
		self.check_time_events()
	
class Interface:
	def handle_event_roster(self, account, data):
		#('ROSTER', account, array)
		self.roster.fill_contacts_and_groups_dicts(data, account)
		self.roster.add_account_contacts(account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Roster', (account, data))

	def handle_event_warning(self, unused, data):
		#('WARNING', account, (title_text, section_text))
		dialogs.WarningDialog(data[0], data[1]).get_response()

	def handle_event_error(self, unused, data):
		#('ERROR', account, (title_text, section_text))
		dialogs.ErrorDialog(data[0], data[1]).get_response()

	def handle_event_information(self, unused, data):
		#('INFORMATION', account, (title_text, section_text))
		dialogs.InformationDialog(data[0], data[1])
		
	def handle_event_ask_new_nick(self, account, data):
		#('ASK_NEW_NICK', account, (room_jid, title_text, prompt_text, proposed_nick))
		room_jid = data[0]
		title = data[1]
		prompt = data[2]
		proposed_nick = data[3]
		gc_control = self.msg_win_mgr.get_control(room_jid, account)
		if gc_control: # user may close the window before we are here
			gc_control.show_change_nick_input_dialog(title, prompt, proposed_nick)

	def handle_event_http_auth(self, account, data):
		#('HTTP_AUTH', account, (method, url, transaction_id, iq_obj))
		dialog = dialogs.ConfirmationDialog(_('HTTP (%s) Authorization for %s (id: %s)') \
			% (data[0], data[1], data[2]), _('Do you accept this request?'))
		if dialog.get_response() == gtk.RESPONSE_OK:
			answer = 'yes'
		else:
			answer = 'no'
		gajim.connections[account].build_http_auth_answer(data[3], answer)

	def handle_event_error_answer(self, account, array):
		#('ERROR_ANSWER', account, (id, jid_from. errmsg, errcode))
		id, jid_from, errmsg, errcode = array
		if unicode(errcode) in ('403', '406') and id:
			# show the error dialog
			ft = self.instances['file_transfers']
			sid = id
			if len(id) > 3 and id[2] == '_':
				sid = id[3:]
			if ft.files_props['s'].has_key(sid):
				file_props = ft.files_props['s'][sid]
				file_props['error'] = -4
				self.handle_event_file_request_error(account, 
					(jid_from, file_props))
				conn = gajim.connections[account]
				conn.disconnect_transfer(file_props)
				return
		elif unicode(errcode) == '404':
			conn = gajim.connections[account]
			sid = id
			if len(id) > 3 and id[2] == '_':
				sid = id[3:]
			if conn.files_props.has_key(sid):
				file_props = conn.files_props[sid]
				self.handle_event_file_send_error(account, 
					(jid_from, file_props))
				conn.disconnect_transfer(file_props)
				return
		ctrl = self.msg_win_mgr.get_control(jid_from, account)
		if ctrl and ctrl.type_id == message_control.TYPE_GC:
			ctrl.print_conversation('Error %s: %s' % (array[2], array[1]))

	def handle_event_con_type(self, account, con_type):
		# ('CON_TYPE', account, con_type) which can be 'ssl', 'tls', 'tcp'
		gajim.con_types[account] = con_type
		self.roster.draw_account(account)

	def unblock_signed_in_notifications(self, account):
		gajim.block_signed_in_notifications[account] = False

	def handle_event_status(self, account, status): # OUR status
		#('STATUS', account, status)
		model = self.roster.status_combobox.get_model()
		if status == 'offline':
			# sensitivity for this menuitem
			model[self.roster.status_message_menuitem_iter][3] = False
			gajim.block_signed_in_notifications[account] = True
		else:
			# 30 seconds after we change our status to sth else than offline
			# we stop blocking notifications of any kind
			# this prevents from getting the roster items as 'just signed in'
			# contacts. 30 seconds should be enough time
			gobject.timeout_add(30000, self.unblock_signed_in_notifications, account)
			# sensitivity for this menuitem
			model[self.roster.status_message_menuitem_iter][3] = True

		# Inform all controls for this account of the connection state change
		for ctrl in self.msg_win_mgr.get_controls(
			type = message_control.TYPE_GC):
			if ctrl.account == account:
				if status == 'offline':
					ctrl.got_disconnected()
				else:
					# Other code rejoins all GCs, so we don't do it here
					if not ctrl.type_id == message_control.TYPE_GC:
						ctrl.got_connected()
				ctrl.parent_win.redraw_tab(ctrl)

		self.roster.on_status_changed(account, status)
		if account in self.show_vcard_when_connect:
			jid = gajim.get_jid_from_account(account)
			if not self.instances[account]['infos'].has_key(jid):
				self.instances[account]['infos'][jid] = \
					vcard.VcardWindow(jid, account, True)
				gajim.connections[account].request_vcard(jid)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('AccountPresence', (status, account))
	
	def handle_event_notify(self, account, array):
		#('NOTIFY', account, (jid, status, message, resource, priority, keyID))
		# if we're here it means contact changed show
		statuss = ['offline', 'error', 'online', 'chat', 'away', 'xa', 'dnd',
			'invisible']
		old_show = 0
		new_show = statuss.index(array[1])
		jid = array[0].split('/')[0]
		keyID = array[5]
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		if jid in attached_keys:
			keyID = attached_keys[attached_keys.index(jid) + 1]
		resource = array[3]
		if not resource:
			resource = ''
		priority = array[4]
		if gajim.jid_is_transport(jid):
			# It must be an agent
			ji = jid.replace('@', '')
		else:
			ji = jid

		# Update contact
		jid_list = gajim.contacts.get_jid_list(account)
		if ji in jid_list:
			lcontact = gajim.contacts.get_contacts_from_jid(account, ji)
			contact1 = None
			resources = []
			for c in lcontact:
				resources.append(c.resource)
				if c.resource == resource:
					contact1 = c
					break
			if contact1:
				if contact1.show in statuss:
					old_show = statuss.index(contact1.show)
				if old_show == new_show and contact1.status == array[2] and \
					contact1.priority == priority: # no change
					return
			else:
				contact1 = gajim.contacts.get_first_contact_from_jid(account, ji)
				if contact1.show in statuss:
					old_show = statuss.index(contact1.show)
				if (resources != [''] and (len(lcontact) != 1 or 
					lcontact[0].show != 'offline')) and jid.find('@') > 0:
					old_show = 0
					contact1 = gajim.contacts.copy_contact(contact1)
					lcontact.append(contact1)
				contact1.resource = resource
			if contact1.jid.find('@') > 0 and len(lcontact) == 1: # It's not an agent
				if old_show == 0 and new_show > 1:
					if not contact1.jid in gajim.newly_added[account]:
						gajim.newly_added[account].append(contact1.jid)
					if contact1.jid in gajim.to_be_removed[account]:
						gajim.to_be_removed[account].remove(contact1.jid)
					gobject.timeout_add(5000, self.roster.remove_newly_added,
						contact1.jid, account)
				elif old_show > 1 and new_show == 0 and gajim.connections[account].\
					connected > 1:
					if not contact1.jid in gajim.to_be_removed[account]:
						gajim.to_be_removed[account].append(contact1.jid)
					if contact1.jid in gajim.newly_added[account]:
						gajim.newly_added[account].remove(contact1.jid)
					self.roster.draw_contact(contact1.jid, account)
					if not gajim.awaiting_events[account].has_key(jid):
						gobject.timeout_add(5000, self.roster.really_remove_contact,
							contact1, account)
			contact1.show = array[1]
			contact1.status = array[2]
			contact1.priority = priority
			contact1.keyID = keyID
			if contact1.jid not in gajim.newly_added[account]:
				contact1.last_status_time = time.localtime()
		if gajim.jid_is_transport(jid):
			# It must be an agent
			if ji in jid_list:
				# Update existing iter
				self.roster.draw_contact(ji, account)
		elif jid == gajim.get_jid_from_account(account):
			# It's another of our resources.  We don't need to see that!
			return
		elif ji in jid_list:
			# It isn't an agent
			# reset chatstate if needed:
			# (when contact signs out or has errors)
			if array[1] in ('offline', 'error'):
				contact1.our_chatstate = contact1.chatstate = contact1.composing_jep = None
				gajim.connections[account].remove_transfers_for_contact(contact1)
			self.roster.chg_contact_status(contact1, array[1], array[2], account)
			# play sound
			if old_show < 2 and new_show > 1:
				if gajim.config.get_per('soundevents', 'contact_connected',
					'enabled') and not gajim.block_signed_in_notifications[account]:
					helpers.play_sound('contact_connected')
				if not gajim.awaiting_events[account].has_key(jid) and \
					gajim.config.get('notify_on_signin') and \
					not gajim.block_signed_in_notifications[account]:
					if helpers.allow_showing_notification(account):
						transport_name = gajim.get_transport_name_from_jid(jid)
						img = None
						if transport_name:
							img = os.path.join(gajim.DATA_DIR, 'iconsets',
								'transports', transport_name, '48x48',
								'online.png')
						if not img or not os.path.isfile(img):
							iconset = gajim.config.get('iconset')
							img = os.path.join(gajim.DATA_DIR, 'iconsets',
									iconset, '48x48', 'online.png')
						path = gtkgui_helpers.get_path_to_generic_or_avatar(img,
							jid = jid, suffix = '_notif_size_colored.png')
						notify.notify(_('Contact Signed In'), jid, account,
							path_to_image = path)

				if self.remote_ctrl:
					self.remote_ctrl.raise_signal('ContactPresence',
						(account, array))
				
			elif old_show > 1 and new_show < 2:
				if gajim.config.get_per('soundevents', 'contact_disconnected',
						'enabled'):
					helpers.play_sound('contact_disconnected')
				if not gajim.awaiting_events[account].has_key(jid) and \
					gajim.config.get('notify_on_signout'):
					if helpers.allow_showing_notification(account):
						transport_name = gajim.get_transport_name_from_jid(jid)
						img = None
						if transport_name:
							img = os.path.join(gajim.DATA_DIR, 'iconsets',
								'transports', transport_name, '48x48',
								'offline.png')
						if not img or not os.path.isfile(img):
							iconset = gajim.config.get('iconset')
							img = os.path.join(gajim.DATA_DIR, 'iconsets',
									iconset, '48x48', 'offline.png')
						path = gtkgui_helpers.get_path_to_generic_or_avatar(img,
							jid = jid, suffix = '_notif_size_bw.png')
						notify.notify(_('Contact Signed Out'), jid, account,
							path_to_image = path)

				if self.remote_ctrl:
					self.remote_ctrl.raise_signal('ContactAbsence', (account, array))
				# FIXME: stop non active file transfers
		else:
			# FIXME: Msn transport (CMSN1.2.1 and PyMSN0.10) doesn't follow the JEP
			# remove in 2007
			# It's maybe a GC_NOTIFY (specialy for MSN gc)
			self.handle_event_gc_notify(account, (jid, array[1], array[2],
				array[3], None, None, None, None, None, None, None))
			

	def handle_event_msg(self, account, array):
		# ('MSG', account, (jid, msg, time, encrypted, msg_type, subject,
		# chatstate))
		

		jid = gajim.get_jid_without_resource(array[0])
		resource = gajim.get_resource_from_jid(array[0])
		fjid = array[0]
		msg_type = array[4]
		chatstate = array[6]
		msg_id = array[7]
		composing_jep = array[8]
		if gajim.jid_is_transport(jid):
			jid = jid.replace('@', '')
		
		chat_control = self.msg_win_mgr.get_control(jid, account)

		# Handle chat states  
		contact = gajim.contacts.get_first_contact_from_jid(account, jid)
		if contact:
			contact.composing_jep = composing_jep
		if chat_control and chat_control.type_id == message_control.TYPE_CHAT:
			if chatstate is not None:
				# other peer sent us reply, so he supports jep85 or jep22
				contact.chatstate = chatstate
				if contact.our_chatstate == 'ask': # we were jep85 disco?
					contact.our_chatstate = 'active' # no more
				chat_control.handle_incoming_chatstate()
			elif contact.chatstate != 'active':
				# got no valid jep85 answer, peer does not support it
				contact.chatstate = False
		elif contact and chatstate == 'active':
			# Brand new message, incoming.  
			contact.our_chatstate = chatstate
			contact.chatstate = chatstate
			if msg_id: # Do not overwrite an existing msg_id with None
				contact.msg_id = msg_id

		# THIS MUST BE AFTER chatstates handling
		# AND BEFORE playsound (else we here sounding on chatstates!)
		if not array[1]: # empty message text
			return

		first = False
		pm = False
		if not chat_control and not gajim.awaiting_events[account].has_key(jid):
			# It's a first message and not a Private Message
			first = True
		elif chat_control and chat_control.type_id == message_control.TYPE_GC: 
			# It's a Private message
			pm = True
			if not self.msg_win_mgr.has_window(fjid, account) and \
				not gajim.awaiting_events[account].has_key(fjid):
					first =True
		if gajim.config.get_per('soundevents', 'first_message_received',
			'enabled') and first:
			helpers.play_sound('first_message_received')
		elif gajim.config.get_per('soundevents', 'next_message_received',
			'enabled'):
			helpers.play_sound('next_message_received')

		jid_of_control = jid
		if pm:
			room_jid, nick = gajim.get_room_and_nick_from_fjid(fjid)
			if first:
				if helpers.allow_showing_notification(account):
					room_name,t = gajim.get_room_name_and_server_from_room_jid(
						room_jid)
					txt = _('%(nickname)s in room %(room_name)s has sent you a new '
						'message.') % {'nickname': nick, 'room_name': room_name}
					img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
						'priv_msg_recv.png')
					path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
					notify.notify(_('New Private Message'), fjid, account, 'pm',
						path_to_image = path, text = txt)

			chat_control.on_private_message(nick, array[1], array[2])
			return
				
		# THIS HAS TO BE AFTER PM handling so we can get PMs
		if gajim.config.get('ignore_unknown_contacts') and \
			not gajim.contacts.get_contact(account, jid):
			return

		highest_contact = gajim.contacts.get_contact_with_highest_priority(
			account, jid)
		# Look for a chat control that has the given resource, or default to one
		# without resource
		ctrl = self.msg_win_mgr.get_control(fjid, account)
		if ctrl:
			chat_control = ctrl
		elif not highest_contact or not highest_contact.resource:
			# unknow contact or offline message
			chat_control = None
			jid_of_control = jid
		elif resource != highest_contact.resource:
			chat_control = None
			jid_of_control = fjid
		
		if first:
			if gajim.config.get('notify_on_new_message'):
				if helpers.allow_showing_notification(account):
					txt = _('%s has sent you a new message.') % gajim.get_name_from_jid(account, jid)
					if msg_type == 'normal': # single message
						img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
							'single_msg_recv.png')
						path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
						notify.notify(_('New Single Message'), jid_of_control,
							account, msg_type, path_to_image = path, text = txt)
					else: # chat message
						img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
							'chat_msg_recv.png')
						path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
						notify.notify(_('New Message'), jid_of_control, account,
							msg_type, path_to_image = path, text = txt)

		# array: (contact, msg, time, encrypted, msg_type, subject)
		self.roster.on_message(jid, array[1], array[2], account, array[3],
			msg_type, array[5], resource)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('NewMessage', (account, array))

	def handle_event_msgerror(self, account, array):
		#('MSGERROR', account, (jid, error_code, error_msg, msg, time))
		fjid = array[0]
		jids = fjid.split('/', 1)
		jid = jids[0]
		gcs = self.msg_win_mgr.get_controls(message_control.TYPE_GC)
		for gc_control in gcs:
			if jid == gc_control.contact.jid:
				if len(jids) > 1: # it's a pm
					nick = jids[1]
					if not self.msg_win_mgr.get_control(fjid, account):
						tv = gc_control.list_treeview
						model = tv.get_model()
						i = gc_control.get_contact_iter(nick)
						if i:
							show = model[i][3]
						else:
							show = 'offline'
						gc_c = gajim.contacts.create_gc_contact(room_jid = jid,
							name = nick, show = show)
						c = gajim.contacts.contact_from_gc_contact(gc_c)
						self.roster.new_chat(c, account, private_chat = True)
					ctrl = self.msg_win_mgr.get_control(fjid, account)
					ctrl.print_conversation('Error %s: %s' % (array[1], array[2]),
								'status')
					return
	
				gc_control.print_conversation('Error %s: %s' % (array[1], array[2]))
				if gc_control.parent_win.get_active_jid() == jid:
					gc_control.set_subject(gc_control.subject)
				return

		if gajim.jid_is_transport(jid):
			jid = jid.replace('@', '')
		self.roster.on_message(jid, _('error while sending') + \
			' \"%s\" ( %s )' % (array[3], array[2]), array[4], account, \
			msg_type='error')
		
	def handle_event_msgsent(self, account, array):
		#('MSGSENT', account, (jid, msg, keyID))
		msg = array[1]
		# do not play sound when standalone chatstate message (eg no msg)
		if msg and gajim.config.get_per('soundevents', 'message_sent', 'enabled'):
			helpers.play_sound('message_sent')
		
	def handle_event_subscribe(self, account, array):
		#('SUBSCRIBE', account, (jid, text))
		dialogs.SubscriptionRequestWindow(array[0], array[1], account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Subscribe', (account, array))

	def handle_event_subscribed(self, account, array):
		#('SUBSCRIBED', account, (jid, resource))
		jid = array[0]
		if jid in gajim.contacts.get_jid_list(account):
			c = gajim.contacts.get_first_contact_from_jid(account, jid)
			c.resource = array[1]
			self.roster.remove_contact(c, account)
			if _('Not in Roster') in c.groups:
				c.groups.remove(_('Not in Roster'))
			self.roster.add_contact_to_roster(c.jid, account)
		else:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			name = jid.split('@', 1)[0]
			name = name.split('%', 1)[0]
			contact1 = gajim.contacts.create_contact(jid = jid, name = name,
				groups = [], show = 'online', status = 'online',
				ask = 'to', resource = array[1], keyID = keyID)
			gajim.contacts.add_contact(account, contact1)
			self.roster.add_contact_to_roster(jid, account)
		dialogs.InformationDialog(_('Authorization accepted'),
				_('The contact "%s" has authorized you to see his or her status.')
				% jid)
		gajim.connections[account].ack_subscribed(jid)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Subscribed', (account, array))

	def handle_event_unsubscribed(self, account, jid):
		dialogs.InformationDialog(_('Contact "%s" removed subscription from you') % jid,
				_('You will always see him or her as offline.'))
		# FIXME: Per RFC 3921, we can "deny" ack as well, but the GUI does not show deny
		gajim.connections[account].ack_unsubscribed(jid)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('Unsubscribed', (account, jid))
	
	def handle_event_agent_info_error(self, account, agent):
		#('AGENT_ERROR_INFO', account, (agent))
		try:
			gajim.connections[account].services_cache.agent_info_error(agent)
		except AttributeError:
			return
	
	def handle_event_agent_items_error(self, account, agent):
		#('AGENT_ERROR_INFO', account, (agent))
		try:
			gajim.connections[account].services_cache.agent_items_error(agent)
		except AttributeError:
			return

	def handle_event_register_agent_info(self, account, array):
		#('REGISTER_AGENT_INFO', account, (agent, infos, is_form))
		if array[1].has_key('instructions'):
			config.ServiceRegistrationWindow(array[0], array[1], account,
				array[2])
		else:
			dialogs.ErrorDialog(_('Contact with "%s" cannot be established'\
% array[0]), _('Check your connection or try again later.')).get_response()

	def handle_event_agent_info_items(self, account, array):
		#('AGENT_INFO_ITEMS', account, (agent, node, items))
		try:
			gajim.connections[account].services_cache.agent_items(array[0],
				array[1], array[2])
		except AttributeError:
			return

	def handle_event_agent_info_info(self, account, array):
		#('AGENT_INFO_INFO', account, (agent, node, identities, features, data))
		try:
			gajim.connections[account].services_cache.agent_info(array[0],
				array[1], array[2], array[3], array[4])
		except AttributeError:
			return

	def handle_event_acc_ok(self, account, array):
		#('ACC_OK', account, (config))
		if self.instances.has_key('account_creation_wizard'):
			self.instances['account_creation_wizard'].acc_is_ok(array)

		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('NewAccount', (account, array))

	def handle_event_acc_not_ok(self, account, array):
		#('ACC_NOT_OK', account, (reason))
		if self.instances.has_key('account_creation_wizard'):
			self.instances['account_creation_wizard'].acc_is_not_ok(array)

	def handle_event_quit(self, p1, p2):
		self.roster.quit_gtkgui_interface()

	def handle_event_myvcard(self, account, array):
		nick = ''
		if array.has_key('NICKNAME'):
			nick = array['NICKNAME']
			if nick:
				gajim.nicks[account] = nick
		if self.instances[account]['infos'].has_key(array['jid']):
			win = self.instances[account]['infos'][array['jid']]
			win.set_values(array)
			if account in self.show_vcard_when_connect:
				win.xml.get_widget('information_notebook').set_current_page(-1)
				win.xml.get_widget('set_avatar_button').clicked()
				self.show_vcard_when_connect.remove(account)

	def handle_event_vcard(self, account, vcard):
		# ('VCARD', account, data)
		'''vcard holds the vcard data'''
		jid = vcard['jid']
		resource = ''
		if vcard.has_key('resource'):
			resource = vcard['resource']
		
		# vcard window
		win = None
		if self.instances[account]['infos'].has_key(jid):
			win = self.instances[account]['infos'][jid]
		elif resource and self.instances[account]['infos'].has_key(
			jid + '/' + resource):
			win = self.instances[account]['infos'][jid + '/' + resource]
		if win:
			win.set_values(vcard)

		# show avatar in chat
		win = None
		ctrl = None
		if resource and self.msg_win_mgr.has_window(
		jid + '/' + resource, account):
			win = self.msg_win_mgr.get_window(jid + '/' + resource,
				account)
			ctrl = win.get_control(jid + '/' + resource, account)
		elif self.msg_win_mgr.has_window(jid, account):
			win = self.msg_win_mgr.get_window(jid, account)
			ctrl = win.get_control(jid, account)
		if win and ctrl.type_id != message_control.TYPE_GC:
			ctrl.show_avatar()

		# Show avatar in roster or gc_roster
		gc_ctrl = self.msg_win_mgr.get_control(jid, account)
		if gc_ctrl and gc_ctrl.type_id == message_control.TYPE_GC:
			gc_ctrl.draw_avatar(resource)
		else:
			self.roster.draw_avatar(jid, account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('VcardInfo', (account, vcard))

	def handle_event_last_status_time(self, account, array):
		# ('LAST_STATUS_TIME', account, (jid, resource, seconds, status))
		win = None
		if self.instances[account]['infos'].has_key(array[0]):
			win = self.instances[account]['infos'][array[0]]
		elif self.instances[account]['infos'].has_key(array[0] + '/' + array[1]):
			win = self.instances[account]['infos'][array[0] + '/' + array[1]]
		if win:
			c = gajim.contacts.get_contact(account, array[0], array[1])
			# c is a list when no resource is given. it probably means that contact
			# is offline, so only on Contact instance
			if isinstance(c, list):
				c = c[0]
			if c: # c can be none if it's a gc contact
				c.last_status_time = time.localtime(time.time() - array[2])
				if array[3]:
					c.status = array[3]
				win.set_last_status_time()
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('LastStatusTime', (account, array))

	def handle_event_os_info(self, account, array):
		win = None
		if self.instances[account]['infos'].has_key(array[0]):
			win = self.instances[account]['infos'][array[0]]
		elif self.instances[account]['infos'].has_key(array[0] + '/' + array[1]):
			win = self.instances[account]['infos'][array[0] + '/' + array[1]]
		if win:
			win.set_os_info(array[1], array[2], array[3])
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('OsInfo', (account, array))

	def handle_event_gc_notify(self, account, array):
		#('GC_NOTIFY', account, (room_jid, show, status, nick,
		# role, affiliation, jid, reason, actor, statusCode, newNick))
		nick = array[3]
		if not nick:
			return
		room_jid = array[0]
		fjid = room_jid + '/' + nick
		show = array[1]
		status = array[2]
		# print status in chat window and update status/GPG image
		if self.msg_win_mgr.has_window(fjid, account):
			ctrl = self.msg_win_mgr.get_control(fjid, account)
			contact = ctrl.contact
			contact.show = show
			contact.status = status
			ctrl.update_ui()
			uf_show = helpers.get_uf_show(show)
			ctrl.print_conversation(_('%s is now %s (%s)') % (nick, uf_show, status),
						'status')
			ctrl.draw_banner()

		# Get the window and control for the updated status, this may be a PrivateChatControl
		control = self.msg_win_mgr.get_control(room_jid, account)
		if control:
			control.chg_contact_status(nick, show, status, array[4], array[5], array[6],
						array[7], array[8], array[9], array[10])
			# Find any PM chat through this room, and tell it to update.
			pm_control = self.msg_win_mgr.get_control(fjid, account)
			if pm_control:
				pm_control.parent_win.redraw_tab(pm_control)
			if self.remote_ctrl:
				self.remote_ctrl.raise_signal('GCPresence', (account, array))

	def handle_event_gc_msg(self, account, array):
		# ('GC_MSG', account, (jid, msg, time))
		jids = array[0].split('/', 1)
		room_jid = jids[0]
		gc_control = self.msg_win_mgr.get_control(room_jid, account)
		if not gc_control:
			return
		if len(jids) == 1:
			# message from server
			nick = ''
		else:
			# message from someone
			nick = jids[1]
		gc_control.on_message(nick, array[1], array[2])
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('GCMessage', (account, array))

	def handle_event_gc_subject(self, account, array):
		#('GC_SUBJECT', account, (jid, subject, body))
		jids = array[0].split('/', 1)
		jid = jids[0]
		gc_control = self.msg_win_mgr.get_control(jid, account)
		if not gc_control:
			return
		gc_control.set_subject(array[1])
		# We can receive a subject with a body that contains "X has set the subject to Y" ...
		if array[2]:
			gc_control.print_conversation(array[2])
		# ... Or the message comes from the occupant who set the subject
		elif len(jids) > 1:
			gc_control.print_conversation('%s has set the subject to %s' % (jids[1], array[1]))

	def handle_event_gc_config(self, account, array):
		#('GC_CONFIG', account, (jid, config))  config is a dict
		jid = array[0].split('/')[0]
		if not self.instances[account]['gc_config'].has_key(jid):
			self.instances[account]['gc_config'][jid] = \
			config.GroupchatConfigWindow(account, jid, array[1])

	def handle_event_gc_affiliation(self, account, array):
		#('GC_AFFILIATION', account, (room_jid, affiliation, list)) list is list
		room_jid = array[0]
		if self.instances[account]['gc_config'].has_key(room_jid):
			self.instances[account]['gc_config'][room_jid].\
				affiliation_list_received(array[1], array[2])

	def handle_event_gc_invitation(self, account, array):
		#('GC_INVITATION', (room_jid, jid_from, reason, password))
		jid = gajim.get_jid_without_resource(array[1])
		room_jid = array[0]
		if helpers.allow_popup_window(account) or not self.systray_enabled:
			dialogs.InvitationReceivedDialog(account, room_jid, jid, array[3],
				array[2])
			return

		self.add_event(account, jid, 'gc-invitation', (room_jid, array[2],
			array[3]))

		if helpers.allow_showing_notification(account):
			path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
				'gc_invitation.png')
			path = gtkgui_helpers.get_path_to_generic_or_avatar(path)
			notify.notify(_('Groupchat Invitation'),
				jid, account, 'gc-invitation', path, room_jid)

	def handle_event_bad_passphrase(self, account, array):
		use_gpg_agent = gajim.config.get('use_gpg_agent')
		if use_gpg_agent:
		  return
		keyID = gajim.config.get_per('accounts', account, 'keyid')
		self.roster.forget_gpg_passphrase(keyID)
		dialogs.WarningDialog(_('Your passphrase is incorrect'),
			_('You are currently connected without your OpenPGP key.')).get_response()

	def handle_event_roster_info(self, account, array):
		#('ROSTER_INFO', account, (jid, name, sub, ask, groups))
		jid = array[0]
		if not jid in gajim.contacts.get_jid_list(account):
			return
		contacts = gajim.contacts.get_contacts_from_jid(account, jid)
		# contact removes us.
		name = array[1]
		sub = array[2]
		ask = array[3]
		groups = array[4]
		if (not sub or sub == 'none') and (not ask or ask == 'none') and \
		not name and not groups:
			self.roster.remove_contact(contacts[0], account)
			gajim.contacts.remove_jid(account, jid)
			#FIXME if it was the only one in its group, remove the group
			return
		for contact in contacts:
			if not name:
				name = ''
			contact.name = name
			contact.sub = sub
			contact.ask = ask
			if groups:
				contact.groups = groups
		self.roster.draw_contact(jid, account)
		if self.remote_ctrl:
			self.remote_ctrl.raise_signal('RosterInfo', (account, array))

	def handle_event_bookmarks(self, account, bms):
		# ('BOOKMARKS', account, [{name,jid,autojoin,password,nick}, {}])
		# We received a bookmark item from the server (JEP48)
		# Auto join GC windows if neccessary
		
		self.roster.actions_menu_needs_rebuild = True
		invisible_show = gajim.SHOW_LIST.index('invisible')
		# do not autojoin if we are invisible
		if gajim.connections[account].connected == invisible_show:
			return

		# join autojoinable rooms
		for bm in bms:
			if bm['autojoin'] in ('1', 'true'):
				self.roster.join_gc_room(account, bm['jid'], bm['nick'],
					bm['password'])
								
	def handle_event_file_send_error(self, account, array):
		jid = array[0]
		file_props = array[1]
		ft = self.instances['file_transfers']
		ft.set_status(file_props['type'], file_props['sid'], 'stop')

		if helpers.allow_popup_window(account):
			ft.show_send_error(file_props)
			return

		self.add_event(account, jid, 'file-send-error', file_props)

		if helpers.allow_showing_notification(account):
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events', 'ft_error.png')
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
			notify.notify(_('File Transfer Error'),
				jid, account, 'file-send-error', path, file_props['name'])

	def handle_event_gmail_notify(self, account, array):
		jid = array[0]
		gmail_new_messages = int(array[1])
		if gajim.config.get('notify_on_new_gmail_email'):
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
				'single_msg_recv.png') #FIXME: find a better image
			txt = i18n.ngettext('You have %d new E-mail message', 'You have %d new E-mail messages', gmail_new_messages, gmail_new_messages, gmail_new_messages)
			txt = _('%(new_mail_gajim_ui_msg)s on %(gmail_mail_address)s') % {'new_mail_gajim_ui_msg': txt, 'gmail_mail_address': jid}
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
			notify.notify(_('New E-mail'), jid, account, 'gmail', path_to_image = path, text = txt)

	def save_avatar_files(self, jid, photo_decoded, puny_nick = None):
		'''Save the decoded avatar to a separate file, and generate files for dbus notifications'''
		puny_jid = helpers.sanitize_filename(jid)
		path_to_file = os.path.join(gajim.AVATAR_PATH, puny_jid)
		if puny_nick:
			path_to_file = os.path.join(path_to_file, puny_nick)
		# remove old avatars
		for typ in ('jpeg', 'png'):
			path_to_original_file = path_to_file + '.' + typ
			if os.path.isfile(path_to_original_file):
				os.remove(path_to_original_file)
		pixbuf, typ = gtkgui_helpers.get_pixbuf_from_data(photo_decoded,
			want_type = True)
		if pixbuf is None:
			return
		if typ not in ('jpeg', 'png'):
			gajim.log.debug('gtkpixbuf cannot save other than jpeg and png formats. saving %s\'avatar as png file (originaly %s)' % (jid, typ))
			typ = 'png'
		path_to_original_file = path_to_file + '.' + typ
		pixbuf.save(path_to_original_file, typ)
		# Generate and save the resized, color avatar
		path_to_normal_file = path_to_file + '_notif_size_colored.png'
		pixbuf = gtkgui_helpers.get_scaled_pixbuf(
			gtkgui_helpers.get_pixbuf_from_data(photo_decoded), 'notification')
		pixbuf.save(path_to_normal_file, 'png')
		# Generate and save the resized, black and white avatar
		path_to_bw_file = path_to_file + '_notif_size_bw.png'
		bwbuf = gtkgui_helpers.get_scaled_pixbuf(
			gtkgui_helpers.make_pixbuf_grayscale(pixbuf), 'notification')
		bwbuf.save(path_to_bw_file, 'png')

	def add_event(self, account, jid, typ, args):
		'''add an event to the awaiting_events var'''
		# We add it to the awaiting_events queue
		# Do we have a queue?
		jid = gajim.get_jid_without_resource(jid)
		qs = gajim.awaiting_events[account]
		no_queue = False
		if not qs.has_key(jid):
			no_queue = True
			qs[jid] = []
		qs[jid].append((typ, args))
		self.roster.nb_unread += 1

		self.roster.show_title()
		if no_queue: # We didn't have a queue: we change icons
			self.roster.draw_contact(jid, account)
		if self.systray_enabled:
			self.systray.add_jid(jid, account, typ)

	def redraw_roster_systray(self, account, jid, typ = None):
		self.roster.nb_unread -= 1
		self.roster.show_title()
		self.roster.draw_contact(jid, account)
		if self.systray_enabled:
			self.systray.remove_jid(jid, account, typ)

	def remove_first_event(self, account, jid, typ = None):
		qs = gajim.awaiting_events[account]
		event = gajim.get_first_event(account, jid, typ)
		qs[jid].remove(event)
		# Is it the last event?
		if not len(qs[jid]):
			del qs[jid]
		self.redraw_roster_systray(account, jid, typ)

	def remove_event(self, account, jid, event):
		qs = gajim.awaiting_events[account]
		if not event in qs[jid]:
			return
		qs[jid].remove(event)
		# Is it the last event?
		if not len(qs[jid]):
			del qs[jid]
		self.redraw_roster_systray(account, jid, event[0])

	def handle_event_file_request_error(self, account, array):
		jid = array[0]
		file_props = array[1]
		ft = self.instances['file_transfers']
		ft.set_status(file_props['type'], file_props['sid'], 'stop')
		errno = file_props['error']

		if helpers.allow_popup_window(account):
			if errno in (-4, -5):
				ft.show_stopped(jid, file_props)
			else:
				ft.show_request_error(file_props)
			return

		if errno in (-4, -5):
			msg_type = 'file-error'
		else:
			msg_type = 'file-request-error'

		self.add_event(account, jid, msg_type, file_props)

		if helpers.allow_showing_notification(account):
			# check if we should be notified
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events', 'ft_error.png')
			
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
			notify.notify(_('File Transfer Error'),
				jid, account, msg_type, path, file_props['name'])

	def handle_event_file_request(self, account, array):
		jid = array[0]
		if jid not in gajim.contacts.get_jid_list(account):
			return
		file_props = array[1]
		contact = gajim.contacts.get_first_contact_from_jid(account, jid)

		if helpers.allow_popup_window(account):
			self.instances['file_transfers'].show_file_request(account, contact,
				file_props)
			return

		self.add_event(account, jid, 'file-request', file_props)

		if helpers.allow_showing_notification(account):
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
				'ft_request.png')
			txt = _('%s wants to send you a file.') % gajim.get_name_from_jid(account, jid)
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
			notify.notify(_('File Transfer Request'), jid, account, 'file-request', path_to_image = path, text = txt)

	def handle_event_file_progress(self, account, file_props):
		self.instances['file_transfers'].set_progress(file_props['type'], 
			file_props['sid'], file_props['received-len'])
			
	def handle_event_file_rcv_completed(self, account, file_props):
		ft = self.instances['file_transfers']
		if file_props['error'] == 0:
			ft.set_progress(file_props['type'], file_props['sid'], 
				file_props['received-len'])
		else:
			ft.set_status(file_props['type'], file_props['sid'], 'stop')
		if file_props.has_key('stalled') and file_props['stalled'] or \
			file_props.has_key('paused') and file_props['paused']:
			return
		if file_props['type'] == 'r': # we receive a file
			jid = unicode(file_props['sender'])
		else: # we send a file
			jid = unicode(file_props['receiver'])

		if helpers.allow_popup_window(account):
			if file_props['error'] == 0:
				if gajim.config.get('notify_on_file_complete'):
					ft.show_completed(jid, file_props)
			elif file_props['error'] == -1:
				ft.show_stopped(jid, file_props)
			return

		msg_type = ''
		event_type = ''
		if file_props['error'] == 0 and gajim.config.get('notify_on_file_complete'):
			msg_type = 'file-completed'
			event_type = _('File Transfer Completed')
		elif file_props['error'] == -1:
			msg_type = 'file-stopped'
			event_type = _('File Transfer Stopped')
		
		if event_type == '': 
			# FIXME: ugly workaround (this can happen Gajim sent, Gaim recvs)
			# this should never happen but it does. see process_result() in socks5.py
			# who calls this func (sth is really wrong unless this func is also registered
			# as progress_cb
			return

		if msg_type:
			self.add_event(account, jid, msg_type, file_props)
			
		if file_props is not None:
			if file_props['type'] == 'r':
				# get the name of the sender, as it is in the roster
				sender = unicode(file_props['sender']).split('/')[0]
				name = gajim.contacts.get_first_contact_from_jid(account,
					sender).get_shown_name()
				filename = os.path.basename(file_props['file-name'])
				if event_type == _('File Transfer Completed'):
					txt = _('You successfully received %(filename)s from %(name)s.')\
						% {'filename': filename, 'name': name}
					img = 'ft_done.png'
				else: # ft stopped
					txt = _('File transfer of %(filename)s from %(name)s stopped.')\
						% {'filename': filename, 'name': name}
					img = 'ft_stopped.png'
			else:
				receiver = file_props['receiver']
				if hasattr(receiver, 'jid'):
					receiver = receiver.jid
				receiver = receiver.split('/')[0]
				# get the name of the contact, as it is in the roster
				name = gajim.contacts.get_first_contact_from_jid(account,
					receiver).get_shown_name()
				filename = os.path.basename(file_props['file-name'])
				if event_type == _('File Transfer Completed'):
					txt = _('You successfully sent %(filename)s to %(name)s.')\
						% {'filename': filename, 'name': name}
					img = 'ft_done.png'
				else: # ft stopped
					txt = _('File transfer of %(filename)s to %(name)s stopped.')\
						% {'filename': filename, 'name': name}
					img = 'ft_stopped.png'
			img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events', img)
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img)
		else:
			txt = ''

		if gajim.config.get('notify_on_file_complete') and \
			(gajim.config.get('autopopupaway') or \
			gajim.connections[account].connected in (2, 3)):
			# we want to be notified and we are online/chat or we don't mind
			# bugged when away/na/busy
			notify.notify(event_type, jid, account, msg_type, path_to_image = path, text = txt)

	def handle_event_stanza_arrived(self, account, stanza):
		if not self.instances.has_key(account):
			return
		if self.instances[account].has_key('xml_console'):
			self.instances[account]['xml_console'].print_stanza(stanza, 'incoming')

	def handle_event_stanza_sent(self, account, stanza):
		if not self.instances.has_key(account):
			return
		if self.instances[account].has_key('xml_console'):
			self.instances[account]['xml_console'].print_stanza(stanza, 'outgoing')

	def handle_event_vcard_published(self, account, array):
		dialogs.InformationDialog(_('vCard publication succeeded'), _('Your personal information has been published successfully.'))

	def handle_event_vcard_not_published(self, account, array):
		dialogs.InformationDialog(_('vCard publication failed'), _('There was an error while publishing your personal information, try again later.'))

	def handle_event_signed_in(self, account, empty):
		'''SIGNED_IN event is emitted when we sign in, so handle it'''
		# join already open groupchats
		self.roster.actions_menu_needs_rebuild = True
		for gc_control in self.msg_win_mgr.get_controls(message_control.TYPE_GC):
			if account != gc_control.account:
				continue
			room_jid = gc_control.room_jid
			if gajim.gc_connected[account].has_key(room_jid) and\
					gajim.gc_connected[account][room_jid]:
				continue
			room, server = gajim.get_room_name_and_server_from_room_jid(room_jid)
			nick = gc_control.nick
			password = ''
			if gajim.gc_passwords.has_key(room_jid):
				password = gajim.gc_passwords[room_jid]
			gajim.connections[account].join_gc(nick, room, server, password)

	def handle_event_metacontacts(self, account, tags_list):
		gajim.contacts.define_metacontacts(account, tags_list)

	def read_sleepy(self):	
		'''Check idle status and change that status if needed'''
		if not self.sleeper.poll():
			# idle detection is not supported in that OS
			return False # stop looping in vain
		state = self.sleeper.getState()
		for account in gajim.connections:
			if not gajim.sleeper_state.has_key(account) or \
					not gajim.sleeper_state[account]:
				continue
			if state == common.sleepy.STATE_AWAKE and \
				gajim.sleeper_state[account] in ('autoaway', 'autoxa'):
				#we go online
				self.roster.send_status(account, 'online',
					gajim.status_before_autoaway[account])
				gajim.sleeper_state[account] = 'online'
			elif state == common.sleepy.STATE_AWAY and \
				gajim.sleeper_state[account] == 'online' and \
				gajim.config.get('autoaway'):
				#we save out online status
				gajim.status_before_autoaway[account] = \
					gajim.connections[account].status
				#we go away (no auto status) [we pass True to auto param]
				self.roster.send_status(account, 'away',
					gajim.config.get('autoaway_message'), auto=True)
				gajim.sleeper_state[account] = 'autoaway'
			elif state == common.sleepy.STATE_XA and (\
				gajim.sleeper_state[account] == 'autoaway' or \
				gajim.sleeper_state[account] == 'online') and \
				gajim.config.get('autoxa'):
				#we go extended away [we pass True to auto param]
				self.roster.send_status(account, 'xa',
					gajim.config.get('autoxa_message'), auto=True)
				gajim.sleeper_state[account] = 'autoxa'
		return True # renew timeout (loop for ever)

	def autoconnect(self):
		'''auto connect at startup'''
		ask_message = False
		for a in gajim.connections:
			if gajim.config.get_per('accounts', a, 'autoconnect'):
				ask_message = True
				break
		if ask_message:
			message = self.roster.get_status_message('online')
			if message == None:
				return
			for a in gajim.connections:
				if gajim.config.get_per('accounts', a, 'autoconnect'):
					self.roster.send_status(a, 'online', message)
		return False

	def show_systray(self):
		self.systray.show_icon()
		self.systray_enabled = True

	def hide_systray(self):
		self.systray.hide_icon()
		self.systray_enabled = False
	
	def image_is_ok(self, image):
		if not os.path.exists(image):
			return False
		img = gtk.Image()
		try:
			img.set_from_file(image)
		except:
			return False
		t = img.get_storage_type()
		if t != gtk.IMAGE_PIXBUF and t != gtk.IMAGE_ANIMATION:
			return False
		return True
		
	def make_regexps(self):
		# regexp meta characters are:  . ^ $ * + ? { } [ ] \ | ( )
		# one escapes the metachars with \
		# \S matches anything but ' ' '\t' '\n' '\r' '\f' and '\v'
		# \s matches any whitespace character
		# \w any alphanumeric character
		# \W any non-alphanumeric character
		# \b means word boundary. This is a zero-width assertion that
		# 					matches only at the beginning or end of a word.
		# ^ matches at the beginning of lines
		#
		# * means 0 or more times
		# + means 1 or more times
		# ? means 0 or 1 time
		# | means or
		# [^*] anything but '*'   (inside [] you don't have to escape metachars)
		# [^\s*] anything but whitespaces and '*'
		# (?<!\S) is a one char lookbehind assertion and asks for any leading whitespace
		# and mathces beginning of lines so we have correct formatting detection
		# even if the the text is just '*foo*'
		# (?!\S) is the same thing but it's a lookahead assertion
		# \S*[^\s\W] --> in the matching string don't match ? or ) etc.. if at the end
		# so http://be) will match http://be and http://be)be) will match http://be)be

		prefixes = (r'http://', r'https://', r'gopher://', r'news://', r'ftp://', 
			r'ed2k://', r'irc://', r'magnet:', r'sip:', r'www\.', r'ftp\.')
		# NOTE: it's ok to catch www.gr such stuff exist!
		
		#FIXME: recognize xmpp: and treat it specially
		
		prefix_pattern = ''
		for prefix in prefixes:
			prefix_pattern += prefix + '|'
		
		prefix_pattern = prefix_pattern[:-1] # remove last |
		prefix_pattern = '(' + prefix_pattern + ')'
			
		links = r'\b' + prefix_pattern + r'\S*[\w\/\=]|'
		#2nd one: at_least_one_char@at_least_one_char.at_least_one_char
		mail = r'\bmailto:\S*[^\s\W]|' r'\b\S+@\S+\.\S*[^\s\W]'

		#detects eg. *b* *bold* *bold bold* test *bold* *bold*! (*bold*)
		#doesn't detect (it's a feature :P) * bold* *bold * * bold * test*bold*
		formatting = r'|(?<!\w)' r'\*[^\s*]' r'([^*]*[^\s*])?' r'\*(?!\w)|'\
			r'(?<!\w|\<)' r'/[^\s/]' r'([^/]*[^\s/])?' r'/(?!\w)|'\
			r'(?<!\w)' r'_[^\s_]' r'([^_]*[^\s_])?' r'_(?!\w)'

		basic_pattern = links + mail
		if gajim.config.get('ascii_formatting'):
			basic_pattern += formatting
		self.basic_pattern_re = sre.compile(basic_pattern, sre.IGNORECASE)
		
		emoticons_pattern = ''
		if gajim.config.get('emoticons_theme'):
			# When an emoticon is bordered by an alpha-numeric character it is NOT
			# expanded.  e.g., foo:) NO, foo :) YES, (brb) NO, (:)) YES, etc.
			# We still allow multiple emoticons side-by-side like :P:P:P
			# sort keys by length so :qwe emot is checked before :q
			keys = self.emoticons.keys()
			keys.sort(self.on_emoticon_sort)
			emoticons_pattern_prematch = ''
			emoticons_pattern_postmatch = ''
			emoticon_length = 0
			for emoticon in keys: # travel thru emoticons list
				emoticon_escaped = sre.escape(emoticon) # espace regexp metachars
				emoticons_pattern += emoticon_escaped + '|'# | means or in regexp
				if (emoticon_length != len(emoticon)):
					# Build up expressions to match emoticons next to other emoticons
					emoticons_pattern_prematch  = emoticons_pattern_prematch[:-1]  + ')|(?<='
					emoticons_pattern_postmatch = emoticons_pattern_postmatch[:-1] + ')|(?='
					emoticon_length = len(emoticon)
				emoticons_pattern_prematch += emoticon_escaped  + '|'
				emoticons_pattern_postmatch += emoticon_escaped + '|'
			# We match from our list of emoticons, but they must either have
			# whitespace, or another emoticon next to it to match successfully
			# [\w.] alphanumeric and dot (for not matching 8) in (2.8))
			emoticons_pattern = '|' + \
				'(?:(?<![\w.]' + emoticons_pattern_prematch[:-1]   + '))' + \
				'(?:'       + emoticons_pattern[:-1]            + ')'  + \
				'(?:(?![\w.]'  + emoticons_pattern_postmatch[:-1]  + '))'
		
		# because emoticons match later (in the string) they need to be after
		# basic matches that may occur earlier
		emot_and_basic_pattern = basic_pattern + emoticons_pattern
		self.emot_and_basic_re = sre.compile(emot_and_basic_pattern, sre.IGNORECASE)
		
		# at least one character in 3 parts (before @, after @, after .)
		self.sth_at_sth_dot_sth_re = sre.compile(r'\S+@\S+\.\S*[^\s)?]')
		
		sre.purge() # clear the regular expression cache

	def on_emoticon_sort(self, emot1, emot2):
		len1 = len(emot1)
		len2 = len(emot2)
		if len1 < len2:
			return 1
		elif len1 > len2:
			return -1
		return 0

	def on_launch_browser_mailer(self, widget, url, kind):
		helpers.launch_browser_mailer(kind, url)

	def init_emoticons(self):
		if not gajim.config.get('emoticons_theme'):
			return

		#initialize emoticons dictionary and unique images list
		self.emoticons_images = list()
		self.emoticons = dict()

		emot_theme = gajim.config.get('emoticons_theme')
		if not emot_theme:
			return
		path = os.path.join(gajim.DATA_DIR, 'emoticons', emot_theme)
		if not os.path.exists(path):
			# It's maybe a user theme
			path = os.path.join(gajim.MY_EMOTS_PATH, emot_theme)
			if not os.path.exists(path): # theme doesn't exists
				return
		sys.path.append(path)
		from emoticons import emoticons as emots
		for emot in emots:
			emot_file = os.path.join(path, emots[emot])
			if not self.image_is_ok(emot_file):
				continue
			# This avoids duplicated emoticons with the same image eg. :) and :-)
			if not emot_file in self.emoticons.values():
				if emot_file.endswith('.gif'):
					pix = gtk.gdk.PixbufAnimation(emot_file)
				else:
					pix = gtk.gdk.pixbuf_new_from_file(emot_file)
				self.emoticons_images.append((emot, pix))
			self.emoticons[emot.upper()] = emot_file
		sys.path.remove(path)
		del emots
	
	def register_handlers(self):
		self.handlers = {
			'ROSTER': self.handle_event_roster,
			'WARNING': self.handle_event_warning,
			'ERROR': self.handle_event_error,
			'INFORMATION': self.handle_event_information,
			'ERROR_ANSWER': self.handle_event_error_answer,
			'STATUS': self.handle_event_status,
			'NOTIFY': self.handle_event_notify,
			'MSG': self.handle_event_msg,
			'MSGERROR': self.handle_event_msgerror,
			'MSGSENT': self.handle_event_msgsent,
			'SUBSCRIBED': self.handle_event_subscribed,
			'UNSUBSCRIBED': self.handle_event_unsubscribed,
			'SUBSCRIBE': self.handle_event_subscribe,
			'AGENT_ERROR_INFO': self.handle_event_agent_info_error,
			'AGENT_ERROR_ITEMS': self.handle_event_agent_items_error,
			'REGISTER_AGENT_INFO': self.handle_event_register_agent_info,
			'AGENT_INFO_ITEMS': self.handle_event_agent_info_items,
			'AGENT_INFO_INFO': self.handle_event_agent_info_info,
			'QUIT': self.handle_event_quit,
			'ACC_OK': self.handle_event_acc_ok,
			'ACC_NOT_OK': self.handle_event_acc_not_ok,
			'MYVCARD': self.handle_event_myvcard,
			'VCARD': self.handle_event_vcard,
			'LAST_STATUS_TIME': self.handle_event_last_status_time,
			'OS_INFO': self.handle_event_os_info,
			'GC_NOTIFY': self.handle_event_gc_notify,
			'GC_MSG': self.handle_event_gc_msg,
			'GC_SUBJECT': self.handle_event_gc_subject,
			'GC_CONFIG': self.handle_event_gc_config,
			'GC_INVITATION': self.handle_event_gc_invitation,
			'GC_AFFILIATION': self.handle_event_gc_affiliation,
			'BAD_PASSPHRASE': self.handle_event_bad_passphrase,
			'ROSTER_INFO': self.handle_event_roster_info,
			'BOOKMARKS': self.handle_event_bookmarks,
			'CON_TYPE': self.handle_event_con_type,
			'FILE_REQUEST': self.handle_event_file_request,
			'GMAIL_NOTIFY': self.handle_event_gmail_notify,
			'FILE_REQUEST_ERROR': self.handle_event_file_request_error,
			'FILE_SEND_ERROR': self.handle_event_file_send_error,
			'STANZA_ARRIVED': self.handle_event_stanza_arrived,
			'STANZA_SENT': self.handle_event_stanza_sent,
			'HTTP_AUTH': self.handle_event_http_auth,
			'VCARD_PUBLISHED': self.handle_event_vcard_published,
			'VCARD_NOT_PUBLISHED': self.handle_event_vcard_not_published,
			'ASK_NEW_NICK': self.handle_event_ask_new_nick,
			'SIGNED_IN': self.handle_event_signed_in,
			'METACONTACTS': self.handle_event_metacontacts,
		}
		gajim.handlers = self.handlers

	def process_connections(self):
		''' called each foo (200) miliseconds. Check for idlequeue timeouts.
		'''
		gajim.idlequeue.process()
		return True # renew timeout (loop for ever)

	def save_config(self):
		err_str = parser.write()
		if err_str is not None:
			print >> sys.stderr, err_str
			# it is good to notify the user
			# in case he or she cannot see the output of the console
			dialogs.ErrorDialog(_('Could not save your settings and preferences'),
				err_str).get_response()
			sys.exit()

	def handle_event(self, account, jid, typ):
		w = None
		fjid = jid
		resource = gajim.get_resource_from_jid(jid)
		jid = gajim.get_jid_without_resource(jid)
		if typ == message_control.TYPE_GC:
			w = self.msg_win_mgr.get_window(jid, account)
		elif typ == message_control.TYPE_CHAT:
			if self.msg_win_mgr.has_window(fjid, account):
				w = self.msg_win_mgr.get_window(fjid, account)
			else:
				contact = gajim.contacts.get_contact(account, jid, resource)
				if isinstance(contact, list):
					contact = gajim.contacts.get_first_contact_from_jid(account, jid)
				self.roster.new_chat(contact, account, resource = resource)
				w = self.msg_win_mgr.get_window(fjid, account)
				gajim.last_message_time[account][jid] = 0 # long time ago
		elif typ == message_control.TYPE_PM:
			if self.msg_win_mgr.has_window(fjid, account):
				w = self.msg_win_mgr.get_window(fjid, account)
			else:
				room_jid = jid
				nick = resource
				gc_contact = gajim.contacts.get_gc_contact(account, room_jid,
										nick)
				if gc_contact:
					show = gc_contact.show
				else:
					show = 'offline'
					gc_contact = gajim.contacts.create_gc_contact(room_jid = room_jid,
						name = nick, show = show)
				c = gajim.contacts.contact_from_gc_contact(gc_contact)
				self.roster.new_chat(c, account, private_chat = True)
				w = self.msg_win_mgr.get_window(fjid, account)
		elif typ in ('normal', 'file-request', 'file-request-error',
			'file-send-error', 'file-error', 'file-stopped', 'file-completed'):
			# Get the first single message event
			ev = gajim.get_first_event(account, jid, typ)
			# Open the window
			self.roster.open_event(account, jid, ev)
		elif typ == 'gmail':
			if gajim.config.get_per('accounts', account, 'savepass'):
				url = ('http://www.google.com/accounts/ServiceLoginAuth?service=mail&Email=%s&Passwd=%s&continue=https://mail.google.com/mail') % (gajim.config.get_per('accounts', account, 'name'),gajim.config.get_per('accounts', account, 'password'))
			else:
				url = ('http://mail.google.com/')
			helpers.launch_browser_mailer('url', url)
		elif typ == 'gc-invitation':
			ev = gajim.get_first_event(account, jid, typ)
			data = ev[1]
			dialogs.InvitationReceivedDialog(account, data[0], jid, data[2],
				data[1])
			self.remove_first_event(account, jid, typ)
		if w:
			w.set_active_tab(fjid, account)
			w.window.present()
			w.window.window.focus()
			ctrl = w.get_control(fjid, account)
			# Using isinstance here because we want to catch all derived types
			if isinstance(ctrl, ChatControlBase):
				tv = ctrl.conv_textview
				tv.scroll_to_end()

	def __init__(self):
		gajim.interface = self
		# This is the manager and factory of message windows set by the module
		self.msg_win_mgr = None
		self.default_values = {
			'inmsgcolor': gajim.config.get('inmsgcolor'),
			'outmsgcolor': gajim.config.get('outmsgcolor'),
			'statusmsgcolor': gajim.config.get('statusmsgcolor'),
			'urlmsgcolor': gajim.config.get('urlmsgcolor'),
		}

		parser.read()
		# Do not set gajim.verbose to False if -v option was given
		if gajim.config.get('verbose'):
			gajim.verbose = True
		#add default status messages if there is not in the config file
		if len(gajim.config.get_per('statusmsg')) == 0:
			for msg in gajim.config.statusmsg_default:
				gajim.config.add_per('statusmsg', msg)
				gajim.config.set_per('statusmsg', msg, 'message', 
					gajim.config.statusmsg_default[msg])
		#add default themes if there is not in the config file
		theme = gajim.config.get('roster_theme')
		if not theme in gajim.config.get_per('themes'):
			gajim.config.set('roster_theme', 'gtk+')
		if len(gajim.config.get_per('themes')) == 0:
			d = ['accounttextcolor', 'accountbgcolor', 'accountfont',
				'accountfontattrs', 'grouptextcolor', 'groupbgcolor', 'groupfont',
				'groupfontattrs', 'contacttextcolor', 'contactbgcolor', 
				'contactfont', 'contactfontattrs', 'bannertextcolor',
				'bannerbgcolor']
			
			default = gajim.config.themes_default
			for theme_name in default:
				gajim.config.add_per('themes', theme_name)
				theme = default[theme_name]
				for o in d:
					gajim.config.set_per('themes', theme_name, o,
						theme[d.index(o)])
			
		if gajim.config.get('autodetect_browser_mailer'):
			gtkgui_helpers.autodetect_browser_mailer()

		if gajim.verbose:
			gajim.log.setLevel(gajim.logging.DEBUG)
		else:
			gajim.log.setLevel(None)
		
		# pygtk2.8 on win, breaks io_add_watch. We use good old select.select()
		if os.name == 'nt' and gtk.pygtk_version > (2, 8, 0):
			gajim.idlequeue = idlequeue.SelectIdleQueue()
		else:
			# in a nongui implementation, just call:
			# gajim.idlequeue = IdleQueue() , and
			# gajim.idlequeue.process() each foo miliseconds
			gajim.idlequeue = GlibIdleQueue()
		# resolve and keep current record of resolved hosts
		gajim.resolver = nslookup.Resolver(gajim.idlequeue)
		gajim.socks5queue = socks5.SocksQueue(gajim.idlequeue,
			self.handle_event_file_rcv_completed, 
			self.handle_event_file_progress)
		gajim.proxy65_manager = proxy65_manager.Proxy65Manager(gajim.idlequeue)
		self.register_handlers()
		for account in gajim.config.get_per('accounts'):
			gajim.connections[account] = common.connection.Connection(account)
															
		gtk.about_dialog_set_email_hook(self.on_launch_browser_mailer, 'mail')
		gtk.about_dialog_set_url_hook(self.on_launch_browser_mailer, 'url')
		
		self.instances = {'logs': {}}
		
		for a in gajim.connections:
			self.instances[a] = {'infos': {}, 'disco': {}, 'chats': {},
				'gc': {}, 'gc_config': {}}
			gajim.contacts.add_account(a)
			gajim.groups[a] = {}
			gajim.gc_connected[a] = {}
			gajim.newly_added[a] = []
			gajim.to_be_removed[a] = []
			gajim.awaiting_events[a] = {}
			gajim.nicks[a] = gajim.config.get_per('accounts', a, 'name')
			gajim.block_signed_in_notifications[a] = True
			gajim.sleeper_state[a] = 0
			gajim.encrypted_chats[a] = []
			gajim.last_message_time[a] = {}
			gajim.status_before_autoaway[a] = ''

		self.roster = roster_window.RosterWindow()
		
		if gajim.config.get('remote_control'):
			try:
				import remote_control
				self.remote_ctrl = remote_control.Remote()
			except:
				self.remote_ctrl = None
		else:
			self.remote_ctrl = None

		self.show_vcard_when_connect = []

		path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps/gajim.png')
		pix = gtk.gdk.pixbuf_new_from_file(path_to_file)
		gtk.window_set_default_icon(pix) # set the icon to all newly opened windows
		self.roster.window.set_icon_from_file(path_to_file) # and to roster window
		self.sleeper = common.sleepy.Sleepy(
			gajim.config.get('autoawaytime') * 60, # make minutes to seconds
			gajim.config.get('autoxatime') * 60)

		self.systray_enabled = False
		self.systray_capabilities = False
		
		if os.name == 'nt':
			try:
				import systraywin32
			except: # user doesn't have trayicon capabilities
				pass
			else:
				self.systray_capabilities = True
				self.systray = systraywin32.SystrayWin32()
		else:
			self.systray_capabilities = systray.HAS_SYSTRAY_CAPABILITIES
			if self.systray_capabilities:
			    self.systray = systray.Systray()

		if self.systray_capabilities and gajim.config.get('trayicon'):
			self.show_systray()

		self.init_emoticons()
		self.make_regexps()
		
		# get instances for windows/dialogs that will show_all()/hide()
		self.instances['file_transfers'] = dialogs.FileTransfersWindow()
		
		for account in gajim.connections:
			self.instances[account]['xml_console'] = dialogs.XMLConsoleWindow(
				account)

		gobject.timeout_add(100, self.autoconnect)
		gobject.timeout_add(200, self.process_connections)
		gobject.timeout_add(500, self.read_sleepy)

def test_migration(migration):
	if not migration.PROCESSING:
		dialog = gtk.Dialog()
		dialog = gtk.MessageDialog(None,
			gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
			gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
				message_format = _('GUI Migration failed'))

		dialog.format_secondary_text(
		_('Logs migration through graphical interface failed. The migration process will start in the background. Please wait a few minutes for Gajim to start.'))
		dialog.run()
		dialog.destroy()
		gtk.main_quit()

def wait_migration(migration):
	if not migration.DONE:
		return True # loop for ever
	dialog.done(_('Logs have been successfully migrated to the database.'))
	dialog.dialog.run()
	dialog.dialog.destroy()
	gtk.main_quit()

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application

	if os.name != 'nt':
		# Session Management support
		try:
			import gnome.ui
		except ImportError:
			print >> sys.stderr, _('Session Management support not available (missing gnome.ui module)')
		else:
			def die_cb(cli):
				gtk.main_quit()
			gnome.program_init('gajim', gajim.version)
			cli = gnome.ui.master_client()
			cli.connect('die', die_cb)
			
			path_to_gajim_script = gtkgui_helpers.get_abspath_for_script('gajim')
			
			if path_to_gajim_script:
				argv = [path_to_gajim_script]
				# FIXME: remove this typeerror catch when gnome python is old and
				# not bad patched by distro men [2.12.0 + should not need all that
				# NORMALLY]
				try:
					cli.set_restart_command(argv)
				except TypeError:
					cli.set_restart_command(len(argv), argv)
		
		gtkgui_helpers.possibly_set_gajim_as_xmpp_handler()
	
	# Migrate old logs if we have such olds logs
	from common import logger
	LOG_DB_PATH = logger.LOG_DB_PATH
	if not os.path.exists(LOG_DB_PATH):
		from common import migrate_logs_to_dot9_db
		if os.path.isdir(migrate_logs_to_dot9_db.PATH_TO_LOGS_BASE_DIR):
			import Queue
			q = Queue.Queue(100)
			m = migrate_logs_to_dot9_db.Migration()
			dialog = dialogs.ProgressDialog(_('Migrating Logs...'),
					_('Please wait while logs are being migrated...'), q)
			t = threading.Thread(target = m.migrate, args = (q,))
			t.start()
			id = gobject.timeout_add(500, wait_migration, m)
			# In 1 seconds, we test if migration began
			gobject.timeout_add(1000, test_migration, m)
			gtk.main()
			if not m.DONE:
				# stop test_migration handler
				gobject.source_remove(id)
				# destroy the migration window
				dialog.dialog.destroy()
				# Force GTK to really destroy the window
				while gtk.events_pending():
					gtk.main_iteration(False)
				# We can't use a SQLite object in another thread than the one in
				# which it was created, so create a new Migration instance
				del m
				m = migrate_logs_to_dot9_db.Migration()
				m.migrate()
			# Init logger values (self.con/cur, jid_already_in)
			gajim.logger.init_vars()
	check_paths.check_and_possibly_create_paths()

	Interface()
	gtk.main()
