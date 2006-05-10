##	notify.py
##
## Copyright (C) 2005-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005-2006 Andrew Sayman <lorien420@myrealbox.com>
##
## DBUS/libnotify connection code:
## Copyright (C) 2005 by Sebastian Estienne
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

import os
import time
import dialogs
import gtkgui_helpers

from common import gajim
from common import i18n
from common import helpers
i18n.init()
_ = i18n._

import dbus_support
if dbus_support.supported:
	import dbus
	if dbus_support.version >= (0, 41, 0):
		import dbus.glib
		import dbus.service

def notify(event, jid, account, parameters):
	'''Check what type of notifications we want, depending on basic configuration
	of notifications and advanced one and do these notifications'''
	# First, find what notifications we want
	do_popup = False
	do_sound = False
	if (event == 'status_change'):
		new_show = parameters[0]
		status_message = parameters[1]
		# Default : No popup for status change
	elif  (event == 'contact_connected'):
		status_message = parameters
		if gajim.config.get('notify_on_signin') and \
			not gajim.block_signed_in_notifications[account]\
			and helpers.allow_showing_notification(account):
			do_popup = True
		if gajim.config.get_per('soundevents', 'contact_connected',
			'enabled') and not gajim.block_signed_in_notifications[account]:
			do_sound = True
	elif (event == 'contact_disconnected'):
		status_message = parameters
		if gajim.config.get('notify_on_signout') \
			and helpers.allow_showing_notification(account):
			do_popup = True
		if gajim.config.get_per('soundevents', 'contact_disconnected',
			'enabled'):
			do_sound = True
	
	# Do the wanted notifications	
	if (do_popup):
		if (event == 'contact_connected' or event == 'contact_disconnected' or \
			event == 'status_change'): # Common code for popup for these 3 events
			if (event == 'contact_disconnected'):
				show_image = 'offline.png'
				suffix = '_notif_size_bw.png'
			else: #Status Change or Connected
				# TODO : for status change, we don't always 'online.png', but we 
				# first need 48x48 for all status
				show_image = 'online.png'
				suffix = '_notif_size_colored.png'	
			transport_name = gajim.get_transport_name_from_jid(jid)
			img = None
			if transport_name:
				img = os.path.join(gajim.DATA_DIR, 'iconsets',
					'transports', transport_name, '48x48', show_image) 
			if not img or not os.path.isfile(img):
				iconset = gajim.config.get('iconset')
				img = os.path.join(gajim.DATA_DIR, 'iconsets',
						iconset, '48x48', show_image)
			path = gtkgui_helpers.get_path_to_generic_or_avatar(img,
				jid = jid, suffix = suffix)
			if (event == 'status_change'):
				title = _('%(nick)s Changed Status') % \
					{'nick': gajim.get_name_from_jid(account, jid)}
				text = _('%(nick)s is now %(status)s') % \
					{'nick': gajim.get_name_from_jid(account, jid),\
					'status': helpers.get_uf_show(gajim.SHOW_LIST[new_show])}
				if status_message:
					text =  text + " : " + status_message
				popup(_('Contact Changed Status'), jid, account,
					path_to_image = path, title = title, text = text)
			elif (event == 'contact_connected'):
				title = _('%(nickname)s Signed In') % \
					{'nickname': gajim.get_name_from_jid(account, jid)}
				text = ''
				if status_message:
					text = status_message
				popup(_('Contact Signed In'), jid, account,
					path_to_image = path, title = title, text = text)
			elif (event == 'contact_disconnected'):
				title = _('%(nickname)s Signed Out') % \
					{'nickname': gajim.get_name_from_jid(account, jid)}
				text = ''
				if status_message:
					text = status_message
				popup(_('Contact Signed Out'), jid, account,
					path_to_image = path, title = title, text = text)
			else:
				print 'Event not implemeted yet'
	if (do_sound):
		helpers.play_sound(event)	
	 

def popup(event_type, jid, account, msg_type = '', path_to_image = None,
	title = None, text = None):
	'''Notifies a user of an event. It first tries to a valid implementation of
	the Desktop Notification Specification. If that fails, then we fall back to
	the older style PopupNotificationWindow method.'''
	text = gtkgui_helpers.escape_for_pango_markup(text)
	title = gtkgui_helpers.escape_for_pango_markup(title)
	if gajim.config.get('use_notif_daemon') and dbus_support.supported:
		try:
			DesktopNotification(event_type, jid, account, msg_type, path_to_image,
				title, text)
			return
		except dbus.dbus_bindings.DBusException, e:
			# Connection to D-Bus failed, try popup
			gajim.log.debug(str(e))
		except TypeError, e:
			# This means that we sent the message incorrectly
			gajim.log.debug(str(e))
	instance = dialogs.PopupNotificationWindow(event_type, jid, account, msg_type, \
		path_to_image, title, text)
	gajim.interface.roster.popup_notification_windows.append(instance)

class NotificationResponseManager:
	'''Collects references to pending DesktopNotifications and manages there
	signalling. This is necessary due to a bug in DBus where you can't remove
	a signal from an interface once it's connected.'''
	def __init__(self):
		self.pending = {}
		self.received = []
		self.interface = None

	def attach_to_interface(self):
		if self.interface is not None:
			return
		self.interface = dbus_support.get_notifications_interface()
		self.interface.connect_to_signal('ActionInvoked', self.on_action_invoked)
		self.interface.connect_to_signal('NotificationClosed', self.on_closed)

	def on_action_invoked(self, id, reason):
		self.received.append((id, time.time(), reason))
		if self.pending.has_key(id):
			notification = self.pending[id]
			notification.on_action_invoked(id, reason)
			del self.pending[id]
		if len(self.received) > 20:
			curt = time.time()
			for rec in self.received:
				diff = curt - rec[1]
				if diff > 10:
					self.received.remove(rec)

	def on_closed(self, id, reason = None):
		if self.pending.has_key(id):
			del self.pending[id]

	def add_pending(self, id, object):
		# Check to make sure that we handle an event immediately if we're adding
		# an id that's already been triggered
		for rec in self.received:
			if rec[0] == id:
				object.on_action_invoked(id, rec[2])
				self.received.remove(rec)
				return
		if id not in self.pending:
			# Add it
			self.pending[id] = object
		else:
			# We've triggered an event that has a duplicate ID!
			gajim.log.debug('Duplicate ID of notification. Can\'t handle this.')

notification_response_manager = NotificationResponseManager()

class DesktopNotification:
	'''A DesktopNotification that interfaces with DBus via the Desktop
	Notification specification'''
	def __init__(self, event_type, jid, account, msg_type = '',
		path_to_image = None, title = None, text = None):
		self.path_to_image = path_to_image
		self.event_type = event_type
		self.title = title
		self.text = text
		'''0.3.1 is the only version of notification daemon that has no way to determine which version it is. If no method exists, it means they're using that one.'''
		self.default_version = '0.3.1'
		self.account = account
		self.jid = jid
		self.msg_type = msg_type

		if not text:
			# default value of text
			self.text = gajim.get_name_from_jid(account, jid)

		if not title:
			self.title = event_type # default value

		if event_type == _('Contact Signed In'):
			ntype = 'presence.online'
		elif event_type == _('Contact Signed Out'):
			ntype = 'presence.offline'
		elif event_type in (_('New Message'), _('New Single Message'),
			_('New Private Message')):
			ntype = 'im.received'
		elif event_type == _('File Transfer Request'):
			ntype = 'transfer'
		elif event_type == _('File Transfer Error'):
			ntype = 'transfer.error'
		elif event_type in (_('File Transfer Completed'), _('File Transfer Stopped')):
			ntype = 'transfer.complete'
		elif event_type == _('New E-mail'):
			ntype = 'email.arrived'
		elif event_type == _('Groupchat Invitation'):
			ntype = 'im.invitation'
		elif event_type == _('Contact Changed Status'):
			ntype = 'presence.status'
		else:
			# default failsafe values
			self.path_to_image = os.path.abspath(
				os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
					'chat_msg_recv.png')) # img to display
			ntype = 'im' # Notification Type

		self.notif = dbus_support.get_notifications_interface()
		if self.notif is None:
			raise dbus.dbus_bindings.DBusException()
		self.ntype = ntype

		self.get_version()

	def attempt_notify(self):
		version = self.version
		timeout = gajim.config.get('notification_timeout') # in seconds
		ntype = self.ntype
		if version.startswith('0.2'):
			try:
				self.notif.Notify(
					dbus.String(_('Gajim')),
					dbus.String(self.path_to_image),
					dbus.UInt32(0), 
					ntype, 
					dbus.Byte(0),
					dbus.String(self.title),
					dbus.String(self.text),
					[dbus.String(self.path_to_image)],
					{'default': 0}, 
					[''], 
					True,
					dbus.UInt32(timeout),
					reply_handler=self.attach_by_id,
					error_handler=self.notify_another_way)
			except AttributeError:
				version = '0.3.1' # we're actually dealing with the newer version
		if version.startswith('0.3'):
			if version >= ( 0, 3, 2):
				hints = {}
				hints['urgency'] = dbus.Byte(0) # Low Urgency
				hints['category'] = dbus.String(ntype)
				self.notif.Notify(
					dbus.String(_('Gajim')),
					dbus.UInt32(0), # this notification does not replace other
					dbus.String(self.path_to_image),
					dbus.String(self.title),
					dbus.String(self.text), 
					( dbus.String('default'), dbus.String(self.event_type) ),
					hints, 
					dbus.UInt32(timeout*1000),
					reply_handler=self.attach_by_id,
					error_handler=self.notify_another_way)
			else:
				self.notif.Notify(
					dbus.String(_('Gajim')),
					dbus.String(self.path_to_image), 
					dbus.UInt32(0),
					dbus.String(self.title),
					dbus.String(self.text),
					dbus.String(''),
					{},
					dbus.UInt32(timeout*1000),
					reply_handler=self.attach_by_id,
					error_handler=self.notify_another_way)

	def attach_by_id(self, id):
		self.id = id
		notification_response_manager.attach_to_interface()
		notification_response_manager.add_pending(self.id, self)

	def notify_another_way(self,e):
		gajim.log.debug(str(e))
		gajim.log.debug('Need to implement a new way of falling back')

	def on_action_invoked(self, id, reason):
		if self.notif is None:
			return
		self.notif.CloseNotification(dbus.UInt32(id))
		self.notif = None
		if not self.msg_type:
			self.msg_type = 'chat'
		gajim.interface.handle_event(self.account, self.jid, self.msg_type)

	def version_reply_handler(self, name, vendor, version, spec_version = None):
		self.version = version
		self.attempt_notify()

	def get_version(self):
		self.notif.GetServerInfo(
			reply_handler=self.version_reply_handler,
			error_handler=self.version_error_handler_2_x_try)

	def version_error_handler_2_x_try(self, e):
		self.notif.GetServerInformation(reply_handler=self.version_reply_handler,
			error_handler=self.version_error_handler_3_x_try)

	def version_error_handler_3_x_try(self, e):
		self.version = self.default_version
		self.attempt_notify()
