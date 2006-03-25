##	roster_window.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
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

import gtk
import gtk.glade
import gobject
import os
import time

import common.sleepy
import history_window
import dialogs
import vcard
import config
import disco
import gtkgui_helpers
import cell_renderer_image
import tooltips
import message_control

from common import gajim
from common import helpers
from common import i18n
from message_window import MessageWindowMgr
from chat_control import ChatControl
from groupchat_control import GroupchatControl
from groupchat_control import PrivateChatControl

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

#(icon, name, type, jid, account, editable, second pixbuf)
(
C_IMG, # image to show state (online, new message etc)
C_NAME, # cellrenderer text that holds contact nickame
C_TYPE, # account, group or contact?
C_JID, # the jid of the row
C_ACCOUNT, # cellrenderer text that holds account name
C_EDITABLE, # cellrenderer text that holds name editable or not?
C_SECPIXBUF, # secondary_pixbuf (holds avatar or padlock)
) = range(7)


GTKGUI_GLADE = 'gtkgui.glade'

DEFAULT_ICONSET = 'dcraven'

class RosterWindow:
	'''Class for main window of gtkgui interface'''

	def get_account_iter(self, name):
		model = self.tree.get_model()
		if model is None:
			return
		account_iter = model.get_iter_root()
		if self.regroup:
			return account_iter
		while account_iter:
			account_name = model[account_iter][C_NAME].decode('utf-8')
			if name == account_name:
				break
			account_iter = model.iter_next(account_iter)
		return account_iter

	def get_group_iter(self, name, account):
		model = self.tree.get_model()
		root = self.get_account_iter(account)
		group_iter = model.iter_children(root)
		# C_NAME column contacts the pango escaped group name
		name = gtkgui_helpers.escape_for_pango_markup(name)
		while group_iter:
			group_name = model[group_iter][C_NAME].decode('utf-8')
			if name == group_name:
				break
			group_iter = model.iter_next(group_iter)
		return group_iter

	def get_contact_iter(self, jid, account):
		model = self.tree.get_model()
		acct = self.get_account_iter(account)
		found = []
		if model is None: # when closing Gajim model can be none (async pbs?)
			return found
		group_iter = model.iter_children(acct)
		while group_iter:
			contact_iter = model.iter_children(group_iter)
			while contact_iter:
				if jid == model[contact_iter][C_JID].decode('utf-8') and \
					account == model[contact_iter][C_ACCOUNT].decode('utf-8'):
					found.append(contact_iter)
				# find next contact iter
				if model.iter_has_child(contact_iter):
					# his first child if it has some
					contact_iter = model.iter_children(contact_iter)
				else:
					next_contact_iter = model.iter_next(contact_iter)
					if not next_contact_iter:
						# now we need to go up
						parent_iter = model.iter_parent(contact_iter)
						parent_type = model[parent_iter][C_TYPE]
						while parent_type != 'group':
							contact_iter = model.iter_next(parent_iter)
							if contact_iter:
								break
							else:
								parent_iter = model.iter_parent(parent_iter)
								parent_type = model[parent_iter][C_TYPE]
						else:
							# we tested all contacts in this group
							contact_iter = None
					else:
						# his brother if he has
						contact_iter = next_contact_iter
			group_iter = model.iter_next(group_iter)
		return found

	def add_account_to_roster(self, account):
		model = self.tree.get_model()
		if self.get_account_iter(account):
			return

		if self.regroup:
			show = helpers.get_global_show()
			model.append(None, [self.jabber_state_images['16'][show],
				_('Merged accounts'), 'account', '', 'all', False, None])
			return

		show = gajim.SHOW_LIST[gajim.connections[account].connected]

		tls_pixbuf = None
		if gajim.con_types.has_key(account) and \
			gajim.con_types[account] in ('tls', 'ssl'):
			tls_pixbuf = self.window.render_icon(gtk.STOCK_DIALOG_AUTHENTICATION,
				gtk.ICON_SIZE_MENU) # the only way to create a pixbuf from stock

		our_jid = gajim.get_jid_from_account(account)

		model.append(None, [self.jabber_state_images['16'][show],
			gtkgui_helpers.escape_for_pango_markup(account),
			'account', our_jid, account, False, tls_pixbuf])

	def draw_account(self, account):
		model = self.tree.get_model()
		iter = self.get_account_iter(account)
		if gajim.con_types.has_key(account) and \
		gajim.con_types[account] in ('tls', 'ssl'):
			tls_pixbuf = self.window.render_icon(gtk.STOCK_DIALOG_AUTHENTICATION,
				gtk.ICON_SIZE_MENU) # the only way to create a pixbuf from stock
			model[iter][C_SECPIXBUF] = tls_pixbuf
		else:
			model[iter][C_SECPIXBUF] = None

	def remove_newly_added(self, jid, account):
		if jid in gajim.newly_added[account]:
			gajim.newly_added[account].remove(jid)
			self.draw_contact(jid, account)

	def add_contact_to_roster(self, jid, account):
		'''Add a contact to the roster and add groups if they aren't in roster
		force is about	force to add it, even if it is offline and show offline
		is False, because it has online children, so we need to show it.
		If add_children is True, we also add all children, even if they were not
		already drawn'''
		showOffline = gajim.config.get('showoffline')
		model = self.tree.get_model()
		contact = gajim.contacts.get_first_contact_from_jid(account, jid)
		if not contact:
			return
		# If contact already in roster, do not add it
		if len(self.get_contact_iter(jid, account)):
			return
		if contact.jid.find('@') <= 0:
			# if not '@' or '@' starts the jid ==> agent
			contact.groups = [_('Transports')]

		# JEP-0162
		hide = True
		if contact.sub in ('both', 'to'):
			hide = False
		elif contact.ask == 'subscribe':
			hide = False
		elif contact.name or len(contact.groups):
			hide = False

		observer = False
		if hide:
			if contact.sub == 'from':
				observer = True
			else:
				return

		if observer:
			# if he has a tag, remove it
			tag = gajim.contacts.get_metacontacts_tag(account, jid)
			if tag:
				gajim.contacts.remove_metacontact(account, jid)

		# family is [{'account': acct, 'jid': jid, 'priority': prio}, ]
		# 'priority' is optional
		family = gajim.contacts.get_metacontacts_family(account, jid)

		shown_family = [] # family members that are in roster.
		if family:
			for data in family:
				_jid = data['jid']
				_account = data['account']
				if self.get_contact_iter(_jid, _account):
					shown_family.append(data)
				if _jid == jid:
					our_data = data
			shown_family.append(our_data)
			big_brother_data = gajim.contacts.get_metacontacts_big_brother(
				shown_family)
			big_brother_jid = big_brother_data['jid']
			big_brother_account = big_brother_data['account']
			if big_brother_jid != jid:
				# We are adding a child contact
				if contact.show in ('offline', 'error') and \
				not showOffline and not gajim.awaiting_events[account].has_key(jid):
					return
				parent_iters = self.get_contact_iter(big_brother_jid,
					big_brother_account)
				name = contact.get_shown_name()
				for i in parent_iters:
					# we add some values here. see draw_contact for more
					model.append(i, (None, name, 'contact', jid, account,
						False, None))
				self.draw_contact(jid, account)
				self.draw_avatar(jid, account)
				# Redraw parent to change icon
				self.draw_contact(big_brother_jid, big_brother_account)
				return

		if (contact.show in ('offline', 'error') or hide) and \
			not showOffline and (not _('Transports') in contact.groups or \
			gajim.connections[account].connected < 2) and \
			not gajim.awaiting_events[account].has_key(jid):
			return

		# Remove brother contacts that are already in roster to add them
		# under this iter
		for data in shown_family:
			contacts = gajim.contacts.get_contact(data['account'],
				data['jid'])
			for c in contacts:
				self.remove_contact(c, data['account'])
		groups = contact.groups
		if observer:
			groups = [_('Observers')]
		elif not groups:
			groups = [_('General')]
		for g in groups:
			iterG = self.get_group_iter(g, account)
			if not iterG:
				IterAcct = self.get_account_iter(account)
				iterG = model.append(IterAcct, [
					self.jabber_state_images['16']['closed'],
					gtkgui_helpers.escape_for_pango_markup(g), 'group', g, account,
					False, None])
			if not gajim.groups[account].has_key(g): # It can probably never append
				if account + g in self.collapsed_rows:
					ishidden = False
				else:
					ishidden = True
				gajim.groups[account][g] = { 'expand': ishidden }
			if not account in self.collapsed_rows:
				self.tree.expand_row((model.get_path(iterG)[0]), False)

			typestr = 'contact'
			if g == _('Transports'):
				typestr = 'agent'

			name = contact.get_shown_name()
			# we add some values here. see draw_contact for more
			model.append(iterG, (None, name, typestr, contact.jid, account,
				False, None))

			if gajim.groups[account][g]['expand']:
				self.tree.expand_row(model.get_path(iterG), False)
		self.draw_contact(jid, account)
		self.draw_avatar(jid, account)
		# put the children under this iter
		for data in shown_family:
			contacts = gajim.contacts.get_contact(data['account'],
				data['jid'])
			self.add_contact_to_roster(data['jid'], data['account'])

	def add_transport_to_roster(self, account, transport):
		c = gajim.contacts.create_contact(jid = transport, name = transport,
			groups = [_('Transports')], show = 'offline', status = 'offline',
			sub = 'from')
		gajim.contacts.add_contact(account, c)
		gajim.interface.roster.add_contact_to_roster(transport, account)

	def really_remove_contact(self, contact, account):
		if contact.jid in gajim.newly_added[account]:
			return
		if contact.jid.find('@') < 1 and gajim.connections[account].connected > 1:
			# It's an agent
			return
		if contact.jid in gajim.to_be_removed[account]:
			gajim.to_be_removed[account].remove(contact.jid)
		self.remove_contact(contact, account)

	def remove_contact(self, contact, account):
		'''Remove a contact from the roster'''
		if contact.jid in gajim.to_be_removed[account]:
			return
		model = self.tree.get_model()
		iters = self.get_contact_iter(contact.jid, account)
		if not iters:
			return
		parent_iter = model.iter_parent(iters[0])
		parent_type = model[parent_iter][C_TYPE]
		# remember children to re-add them
		children = []
		child_iter = model.iter_children(iters[0])
		while child_iter:
			c_jid = model[child_iter][C_JID].decode('utf-8')
			c_account = model[child_iter][C_ACCOUNT].decode('utf-8')
			children.append((c_jid, c_account))
			child_iter = model.iter_next(child_iter)
		
		# Remove iters and group iter if they are empty
		for i in iters:
			parent_i = model.iter_parent(i)
			model.remove(i)
			if parent_type == 'group':
				group = model[parent_i][C_JID].decode('utf-8')
				if model.iter_n_children(parent_i) == 0:
					model.remove(parent_i)
					# We need to check all contacts, even offline contacts
					for jid in gajim.contacts.get_jid_list(account):
						if group in gajim.contacts.get_contact_with_highest_priority(
							account, jid).groups:
							break
					else:
						if gajim.groups[account].has_key(group):
							del gajim.groups[account][group]

		# re-add children
		for child in children:
			self.add_contact_to_roster(child[0], child[1])
		# redraw parent
		if parent_type == 'contact':
			parent_jid = model[parent_iter][C_JID].decode('utf-8')
			parent_account = model[parent_iter][C_ACCOUNT].decode('utf-8')
			self.draw_contact(parent_jid, parent_account)

	def get_appropriate_state_images(self, jid, size = '16',
		icon_name = 'online'):
		'''check jid and return the appropriate state images dict for
		the demanded size. icon_name is taken into account when jis is from
		transport: transport iconset doesn't contain all icons, so we fall back
		to jabber one'''
		transport = gajim.get_transport_name_from_jid(jid)
		if transport and icon_name in \
			self.transports_state_images[size][transport]:
			return self.transports_state_images[size][transport]
		return self.jabber_state_images[size]

	def draw_contact(self, jid, account, selected = False, focus = False):
		'''draw the correct state image, name BUT not avatar'''
		# focus is about if the roster window has toplevel-focus or not
		model = self.tree.get_model()
		iters = self.get_contact_iter(jid, account)
		if len(iters) == 0:
			return
		contact_instances = gajim.contacts.get_contact(account, jid)
		contact = gajim.contacts.get_highest_prio_contact_from_contacts(
			contact_instances)
		if not contact:
			return
		name = gtkgui_helpers.escape_for_pango_markup(contact.get_shown_name())

		if len(contact_instances) > 1:
			name += ' (' + unicode(len(contact_instances)) + ')'

		# FIXME: remove when we use metacontacts
		# show (account_name) if there are 2 contact with same jid in merged mode
		if self.regroup:
			add_acct = False
			# look through all contacts of all accounts
			for a in gajim.connections:
				for j in gajim.contacts.get_jid_list(a):
					# [0] cause it'fster than highest_prio
					c = gajim.contacts.get_first_contact_from_jid(a, j)
					if c.name == contact.name and (j, a) != (jid, account):
						add_acct = True
						break
				if add_acct:
					# No need to continue in other account if we already found one
					break
			if add_acct:
				name += ' (' + account + ')'

		# add status msg, if not empty, under contact name in the treeview
		if contact.status and gajim.config.get('show_status_msgs_in_roster'):
			status = contact.status.strip()
			if status != '':
				status = gtkgui_helpers.reduce_chars_newlines(status, max_lines = 1)
				# escape markup entities and make them small italic and fg color
				color = gtkgui_helpers._get_fade_color(self.tree, selected, focus)
				colorstring = "#%04x%04x%04x" % (color.red, color.green, color.blue)
				name += '\n<span size="small" style="italic" foreground="%s">%s</span>'\
					% (colorstring, gtkgui_helpers.escape_for_pango_markup(status))

		iter = iters[0] # choose the icon with the first iter
		icon_name = helpers.get_icon_name_to_show(contact, account)
		path = model.get_path(iter)
		if model.iter_has_child(iter):
			if not self.tree.row_expanded(path) and icon_name != 'message':
				child_iter = model.iter_children(iter)
				if icon_name in ('error', 'offline'):
					# get the icon from the first child as they are sorted by show
					child_jid = model[child_iter][C_JID].decode('utf-8')
					child_contact = gajim.contacts.get_contact_with_highest_priority(
						account, child_jid)
					child_icon_name = helpers.get_icon_name_to_show(child_contact, account)
					if child_icon_name not in ('error', 'not in roster'):
						icon_name = child_icon_name
				while child_iter:
					# a child has awaiting messages ?
					child_jid = model[child_iter][C_JID].decode('utf-8')
					if gajim.awaiting_events[account].has_key(child_jid):
						icon_name = 'message'
						break
					child_iter = model.iter_next(child_iter)
			if self.tree.row_expanded(path):
				state_images = self.get_appropriate_state_images(jid,
					size = 'opened', icon_name = icon_name)
			else:
				state_images = self.get_appropriate_state_images(jid,
					size = 'closed', icon_name = icon_name)
		else:
			# redraw parent
			self.draw_parent_contact(jid, account)
			state_images = self.get_appropriate_state_images(jid,
				icon_name = icon_name)
	
		img = state_images[icon_name]

		for iter in iters:
			model[iter][C_IMG] = img
			model[iter][C_NAME] = name

	def draw_parent_contact(self, jid, account):
		model = self.tree.get_model()
		iters = self.get_contact_iter(jid, account)
		if not len(iters):
			return
		parent_iter = model.iter_parent(iters[0])
		if model[parent_iter][C_TYPE] != 'contact':
			# parent is not a contact
			return
		parent_jid = model[parent_iter][C_JID].decode('utf-8')
		self.draw_contact(parent_jid, account)

	def draw_avatar(self, jid, account):
		'''draw the avatar'''
		model = self.tree.get_model()
		iters = self.get_contact_iter(jid, account)
		if gajim.config.get('show_avatars_in_roster'):
			pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid)
			if pixbuf in ('ask', None):
				scaled_pixbuf = None
			else:
				scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'roster')
		else:
			scaled_pixbuf = None
		for iter in iters:
			model[iter][C_SECPIXBUF] = scaled_pixbuf

	def join_gc_room(self, account, room_jid, nick, password):
		'''joins the room immediatelly'''
		if gajim.interface.msg_win_mgr.has_window(room_jid, account) and \
				gajim.gc_connected[account][room_jid]:
			win = gajim.interface.msg_win_mgr.get_window(room_jid,  account)
			win.window.present()
			win.set_active_tab(room_jid,  account)
			dialogs.ErrorDialog(_('You are already in room %s') % room_jid
				).get_response()
			return
		invisible_show = gajim.SHOW_LIST.index('invisible')
		if gajim.connections[account].connected == invisible_show:
			dialogs.ErrorDialog(_('You cannot join a room while you are invisible')
				).get_response()
			return
		room, server = room_jid.split('@')
		if not gajim.interface.msg_win_mgr.has_window(room_jid, account):
			self.new_room(room_jid, nick, account)
		gc_win = gajim.interface.msg_win_mgr.get_window(room_jid, account)
		gc_win.set_active_tab(room_jid, account)
		gc_win.window.present()
		gajim.connections[account].join_gc(nick, room, server, password)
		if password:
			gajim.gc_passwords[room_jid] = password

	def on_actions_menuitem_activate(self, widget):
		self.make_menu()

	def on_bookmark_menuitem_activate(self, widget, account, bookmark):
		self.join_gc_room(account, bookmark['jid'], bookmark['nick'],
			bookmark['password'])

	def on_bm_header_changed_state(self, widget, event):
		widget.set_state(gtk.STATE_NORMAL) #do not allow selected_state

	def on_send_server_message_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/online'
		dialogs.SingleMessageWindow(account, server, 'send')

	def on_xml_console_menuitem_activate(self, widget, account):
		if gajim.interface.instances[account].has_key('xml_console'):
			gajim.interface.instances[account]['xml_console'].window.present()
		else:
			gajim.interface.instances[account]['xml_console'].window.show_all()

	def on_set_motd_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/motd'
		dialogs.SingleMessageWindow(account, server, 'send')

	def on_update_motd_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/motd/update'
		dialogs.SingleMessageWindow(account, server, 'send')

	def on_delete_motd_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/motd/delete'
		gajim.connections[account].send_motd(server)

	def on_history_manager_menuitem_activate(self, widget):
		if os.name == 'nt': # FIXME: test it actually works..
			try:
				os.startfile('history_manager.exe') # if pywin32 is installed we open
			except: # FIXME: fallback (for windows svn users) to py
				pass
		else:
			os.system('python history_manager.py &')

	def get_and_connect_advanced_menuitem_menu(self, account):
		'''adds FOR ACCOUNT options'''
		xml = gtk.glade.XML(GTKGUI_GLADE, 'advanced_menuitem_menu', APP)
		advanced_menuitem_menu = xml.get_widget('advanced_menuitem_menu')

		send_single_message_menuitem = xml.get_widget(
			'send_single_message_menuitem')
		xml_console_menuitem = xml.get_widget('xml_console_menuitem')
		administrator_menuitem = xml.get_widget('administrator_menuitem')
		send_server_message_menuitem = xml.get_widget(
			'send_server_message_menuitem')
		set_motd_menuitem = xml.get_widget('set_motd_menuitem')
		update_motd_menuitem = xml.get_widget('update_motd_menuitem')
		delete_motd_menuitem = xml.get_widget('delete_motd_menuitem')

		send_single_message_menuitem.connect('activate',
			self.on_send_single_message_menuitem_activate, account)

		xml_console_menuitem.connect('activate',
			self.on_xml_console_menuitem_activate, account)

		send_server_message_menuitem.connect('activate',
			self.on_send_server_message_menuitem_activate, account)

		set_motd_menuitem.connect('activate',
			self.on_set_motd_menuitem_activate, account)

		update_motd_menuitem.connect('activate',
			self.on_update_motd_menuitem_activate, account)

		delete_motd_menuitem.connect('activate',
			self.on_delete_motd_menuitem_activate, account)

		advanced_menuitem_menu.show_all()

		return advanced_menuitem_menu

	def make_menu(self):
		'''create the main window's menus'''
		if not self.actions_menu_needs_rebuild:
			return
		new_message_menuitem = self.xml.get_widget('new_message_menuitem')
		join_gc_menuitem = self.xml.get_widget('join_gc_menuitem')
		add_new_contact_menuitem = self.xml.get_widget('add_new_contact_menuitem')
		service_disco_menuitem = self.xml.get_widget('service_disco_menuitem')
		advanced_menuitem = self.xml.get_widget('advanced_menuitem')
		show_offline_contacts_menuitem = self.xml.get_widget(
			'show_offline_contacts_menuitem')

		# make it sensitive. it is insensitive only if no accounts are *available*
		advanced_menuitem.set_sensitive(True)


		if self.add_new_contact_handler_id:
			add_new_contact_menuitem.handler_disconnect(
				self.add_new_contact_handler_id)
			self.add_new_contact_handler_id = None

		if self.service_disco_handler_id:
			service_disco_menuitem.handler_disconnect(
				self.service_disco_handler_id)
			self.service_disco_handler_id = None

		if self.new_message_menuitem_handler_id:
			new_message_menuitem.handler_disconnect(
				self.new_message_menuitem_handler_id)
			self.new_message_menuitem_handler_id = None

		# remove the existing submenus
		add_new_contact_menuitem.remove_submenu()
		service_disco_menuitem.remove_submenu()
		join_gc_menuitem.remove_submenu()
		new_message_menuitem.remove_submenu()
		advanced_menuitem.remove_submenu()

		# remove the existing accelerator
		if self.have_new_message_accel:
			ag = gtk.accel_groups_from_object(self.window)[0]
			new_message_menuitem.remove_accelerator(ag, gtk.keysyms.n,
				gtk.gdk.CONTROL_MASK)
			self.have_new_message_accel = False

		# join gc
		sub_menu = gtk.Menu()
		join_gc_menuitem.set_submenu(sub_menu)
		at_least_one_account_connected = False
		multiple_accounts = len(gajim.connections) >= 2 #FIXME: stop using bool var here
		for account in gajim.connections:
			if gajim.connections[account].connected <= 1: # if offline or connecting
				continue
			if not at_least_one_account_connected:
				at_least_one_account_connected = True
			if multiple_accounts:
				label = gtk.Label()
				label.set_markup('<u>' + account.upper() +'</u>')
				label.set_use_underline(False)
				item = gtk.MenuItem()
				item.add(label)
				item.connect('state-changed', self.on_bm_header_changed_state)
				sub_menu.append(item)

			item = gtk.MenuItem(_('_Join New Room'))
			item.connect('activate', self.on_join_gc_activate, account)
			sub_menu.append(item)

			for bookmark in gajim.connections[account].bookmarks:
				item = gtk.MenuItem(bookmark['name'], False) # Do not use underline
				item.connect('activate', self.on_bookmark_menuitem_activate,
					account, bookmark)
				sub_menu.append(item)

		if at_least_one_account_connected: #FIXME: move this below where we do this check
			#and make sure it works
			newitem = gtk.SeparatorMenuItem() # separator
			sub_menu.append(newitem)

			newitem = gtk.ImageMenuItem(_('Manage Bookmarks...'))
			img = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES,
				gtk.ICON_SIZE_MENU)
			newitem.set_image(img)
			newitem.connect('activate', self.on_manage_bookmarks_menuitem_activate)
			sub_menu.append(newitem)
			sub_menu.show_all()

		if multiple_accounts: # 2 or more accounts? make submenus
			#add
			sub_menu = gtk.Menu()
			for account in gajim.connections:
				if gajim.connections[account].connected <= 1:
					#if offline or connecting
					continue
				item = gtk.MenuItem(_('to %s account') % account, False)
				sub_menu.append(item)
				item.connect('activate', self.on_add_new_contact, account)
			add_new_contact_menuitem.set_submenu(sub_menu)
			sub_menu.show_all()

			#disco
			sub_menu = gtk.Menu()
			for account in gajim.connections:
				if gajim.connections[account].connected <= 1:
					#if offline or connecting
					continue
				item = gtk.MenuItem(_('using %s account') % account, False)
				sub_menu.append(item)
				item.connect('activate', self.on_service_disco_menuitem_activate,
					account)

			service_disco_menuitem.set_submenu(sub_menu)
			sub_menu.show_all()

			#new message
			sub_menu = gtk.Menu()
			for account in gajim.connections:
				if gajim.connections[account].connected <= 1:
					#if offline or connecting
					continue
				item = gtk.MenuItem(_('using account %s') % account, False)
				sub_menu.append(item)
				item.connect('activate', self.on_new_message_menuitem_activate,
									account)

			new_message_menuitem.set_submenu(sub_menu)
			sub_menu.show_all()

			#Advanced Actions
			sub_menu = gtk.Menu()
			for account in gajim.connections:
				item = gtk.MenuItem(_('for account %s') % account, False)
				sub_menu.append(item)
				advanced_menuitem_menu = self.get_and_connect_advanced_menuitem_menu(
					account)
				item.set_submenu(advanced_menuitem_menu)
			
			self._add_history_manager_menuitem(sub_menu)
			
			advanced_menuitem.set_submenu(sub_menu)
			sub_menu.show_all()

		else:
			if len(gajim.connections) == 1: # user has only one account
				#add
				if not self.add_new_contact_handler_id:
					self.add_new_contact_handler_id = add_new_contact_menuitem.connect(
						'activate', self.on_add_new_contact, gajim.connections.keys()[0])
				#disco
				if not self.service_disco_handler_id:
					self.service_disco_handler_id = service_disco_menuitem.connect(
						'activate', self.on_service_disco_menuitem_activate,
						gajim.connections.keys()[0])
				#new msg
				if not self.new_message_menuitem_handler_id:
					self.new_message_menuitem_handler_id = new_message_menuitem.\
						connect('activate', self.on_new_message_menuitem_activate,
						gajim.connections.keys()[0])
				#new msg accel
				if not self.have_new_message_accel:
					ag = gtk.accel_groups_from_object(self.window)[0]
					new_message_menuitem.add_accelerator('activate', ag,
						gtk.keysyms.n,	gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
					self.have_new_message_accel = True

				account = gajim.connections.keys()[0]
				advanced_menuitem_menu = self.get_and_connect_advanced_menuitem_menu(
					account)

				self._add_history_manager_menuitem(advanced_menuitem_menu)

				advanced_menuitem.set_submenu(advanced_menuitem_menu)
				advanced_menuitem_menu.show_all()
			elif len(gajim.connections) == 0: # user has no accounts
				advanced_menuitem.set_sensitive(False)

		if at_least_one_account_connected:
			new_message_menuitem.set_sensitive(True)
			join_gc_menuitem.set_sensitive(True)
			add_new_contact_menuitem.set_sensitive(True)
			service_disco_menuitem.set_sensitive(True)
			show_offline_contacts_menuitem.set_sensitive(True)
		else:
			# make the menuitems insensitive
			new_message_menuitem.set_sensitive(False)
			join_gc_menuitem.set_sensitive(False)
			add_new_contact_menuitem.set_sensitive(False)
			service_disco_menuitem.set_sensitive(False)
			show_offline_contacts_menuitem.set_sensitive(False)

		self.actions_menu_needs_rebuild = False

	def _add_history_manager_menuitem(self, menu):
		'''adds a seperator and History Manager menuitem BELOW for account 
		menuitems'''
		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)
		
		# History manager
		item = gtk.ImageMenuItem(_('History Manager'))
		icon = gtk.image_new_from_stock(gtk.STOCK_JUSTIFY_FILL,
			gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		item.connect('activate', self.on_history_manager_menuitem_activate)

	def _change_style(self, model, path, iter, option):
		if option is None:
			model[iter][C_NAME] = model[iter][C_NAME]
		elif model[iter][C_TYPE] == 'account':
			if option == 'account':
				model[iter][C_NAME] = model[iter][C_NAME]
		elif model[iter][C_TYPE] == 'group':
			if option == 'group':
				model[iter][C_NAME] = model[iter][C_NAME]
		elif model[iter][C_TYPE] == 'contact':
			if option == 'contact':
				model[iter][C_NAME] = model[iter][C_NAME]

	def change_roster_style(self, option):
		model = self.tree.get_model()
		model.foreach(self._change_style, option)
		for win in gajim.interface.msg_win_mgr.windows():
			win.repaint_themed_widgets()
		# update gc's roster
		for ctrl in gajim.interface.msg_win_mgr.controls():
			if ctrl.type_id == message_control.TYPE_GC:
				ctrl.update_ui()
			
	def draw_roster(self):
		'''Clear and draw roster'''
		# clear the model, only if it is not empty
		if self.tree.get_model():
			self.tree.get_model().clear()
		for acct in gajim.connections:
			self.add_account_to_roster(acct)
			self.add_account_contacts(acct)
	
	def add_account_contacts(self, account):
		for jid in gajim.contacts.get_jid_list(account):
			self.add_contact_to_roster(jid, account)

	def fill_contacts_and_groups_dicts(self, array, account):
		'''fill gajim.contacts and gajim.groups'''
		if account not in gajim.contacts.get_accounts():
			gajim.contacts.add_account(account)
		if not gajim.groups.has_key(account):
			gajim.groups[account] = {}
		for jid in array.keys():
			jids = jid.split('/')
			#get jid
			ji = jids[0]
			#get resource
			resource = ''
			if len(jids) > 1:
				resource = '/'.join(jids[1:])
			#get name
			name = array[jid]['name']
			if not name:
				name = ''
			show = 'offline' # show is offline by default
			status = '' #no status message by default

			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact1 = gajim.contacts.create_contact(jid = ji, name = name,
				groups = array[jid]['groups'], show = show, status = status,
				sub = array[jid]['subscription'], ask = array[jid]['ask'],
				resource = resource, keyID = keyID)
			gajim.contacts.add_contact(account, contact1)

			# when we draw the roster, we avoid having the same contact
			# more than once (f.e. we avoid showing it twice when 2 resources)
			for g in array[jid]['groups']:
				if g in gajim.groups[account].keys():
					continue

				if account + g in self.collapsed_rows:
					ishidden = False
				else:
					ishidden = True
				gajim.groups[account][g] = { 'expand': ishidden }
			if gajim.config.get('ask_avatars_on_startup'):
				pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(ji)
				if pixbuf == 'ask':
					jid_with_resource = contact1.jid
					if contact1.resource:
						jid_with_resource += '/' + contact1.resource
					gajim.connections[account].request_vcard(jid_with_resource)
			# If we already have a chat window opened, update it with new contact
			# instance
			chat_control = gajim.interface.msg_win_mgr.get_control(ji, account)
			if chat_control:
				chat_control.contact = contact1

	def chg_contact_status(self, contact, show, status, account):
		'''When a contact changes his or her status'''
		showOffline = gajim.config.get('showoffline')
		contact_instances = gajim.contacts.get_contact(account, contact.jid)
		contact.show = show
		contact.status = status
		if show in ('offline', 'error') and \
		not gajim.awaiting_events[account].has_key(contact.jid):
			if len(contact_instances) > 1:
				# if multiple resources
				gajim.contacts.remove_contact(account, contact)
		self.remove_contact(contact, account)
		self.add_contact_to_roster(contact.jid, account)
		# print status in chat window and update status/GPG image
		for j in (contact.jid, contact.get_full_jid()):
			if gajim.interface.msg_win_mgr.has_window(j, account):
				jid = contact.jid
				win = gajim.interface.msg_win_mgr.get_window(j, account)
				ctrl = win.get_control(j, account)
				ctrl.update_ui()
				win.redraw_tab(ctrl)

				name = contact.get_shown_name()
				if contact.resource != '':
					name += '/' + contact.resource
				uf_show = helpers.get_uf_show(show)
				if status: 
					ctrl.print_conversation(_('%s is now %s (%s)') % (name, uf_show,
						status), 'status')
				else: # No status message
					ctrl.print_conversation(_('%s is now %s') % (name, uf_show),
						'status')
				if contact == gajim.contacts.get_contact_with_highest_priority(
				account, contact.jid):
					ctrl.draw_banner()

	def on_info(self, widget, contact, account):
		'''Call vcard_information_window class to display contact's information'''
		info = gajim.interface.instances[account]['infos']
		if info.has_key(contact.jid):
			info[contact.jid].window.present()
		else:
			info[contact.jid] = vcard.VcardWindow(contact, account)

	def show_tooltip(self, contact):
		pointer = self.tree.get_pointer()
		props = self.tree.get_path_at_pos(pointer[0], pointer[1])
		# check if the current pointer is at the same path
		# as it was before setting the timeout
		if props and self.tooltip.id == props[0]:
			# bounding rectangle of coordinates for the cell within the treeview
			rect = self.tree.get_cell_area(props[0], props[1])
			
			# position of the treeview on the screen
			position = self.tree.window.get_origin()
			self.tooltip.show_tooltip(contact, rect.height, position[1] + rect.y)
		else:
			self.tooltip.hide_tooltip()

	def on_roster_treeview_leave_notify_event(self, widget, event):
		model = widget.get_model()
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id == props[0]:
				self.tooltip.hide_tooltip()

	def on_roster_treeview_motion_notify_event(self, widget, event):
		model = widget.get_model()
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id != props[0]:
				self.tooltip.hide_tooltip()
		if props:
			[row, col, x, y] = props
			iter = None
			try:
				iter = model.get_iter(row)
			except:
				self.tooltip.hide_tooltip()
				return
			if model[iter][C_TYPE] == 'contact':
				# we're on a contact entry in the roster
				account = model[iter][C_ACCOUNT].decode('utf-8')
				jid = model[iter][C_JID].decode('utf-8')
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					contacts = gajim.contacts.get_contact(account, jid)
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, contacts)
			elif model[iter][C_TYPE] == 'account':
				# we're on an account entry in the roster
				account = model[iter][C_ACCOUNT].decode('utf-8')
				if account == 'all':
					if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
						self.tooltip.id = row
						self.tooltip.timeout = gobject.timeout_add(500,
							self.show_tooltip, [])
					return
				jid = gajim.get_jid_from_account(account)
				contacts = []
				connection = gajim.connections[account]
				# get our current contact info
				contact = gajim.contacts.create_contact(jid = jid, name = account,
					show = connection.get_status(), sub = '',
					status = connection.status,
					resource = gajim.config.get_per('accounts', connection.name,
						'resource'),
					priority = gajim.config.get_per('accounts', connection.name,
						'priority'),
					keyID = gajim.config.get_per('accounts', connection.name,
						'keyid'))
				contacts.append(contact)
				# if we're online ...
				if connection.connection:
					roster = connection.connection.getRoster()
					# in threadless connection when no roster stanza is sent, 'roster' is None
					if roster and roster.getItem(jid):
						resources = roster.getResources(jid)
						# ...get the contact info for our other online resources
						for resource in resources:
							show = roster.getShow(jid+'/'+resource)
							if not show:
								show = 'online'
							contact = gajim.contacts.create_contact(jid = jid,
								name = account, show = show,
								status = roster.getStatus(jid+'/'+resource),
								resource = resource,
								priority = roster.getPriority(jid+'/'+resource))
							contacts.append(contact)
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, contacts)

	def on_agent_logging(self, widget, jid, state, account):
		'''When an agent is requested to log in or off'''
		gajim.connections[account].send_agent_status(jid, state)

	def on_edit_agent(self, widget, contact, account):
		'''When we want to modify the agent registration'''
		gajim.connections[account].request_register_agent_info(contact.jid)

	def on_remove_agent(self, widget, contact, account):
		'''When an agent is requested to log in or off'''
		if gajim.config.get_per('accounts', account, 'hostname') == contact.jid:
			# We remove the server contact
			# remove it from treeview
			self.remove_contact(contact, account)
			gajim.contacts.remove_contact(account, contact)
			return

		window = dialogs.ConfirmationDialog(_('Transport "%s" will be removed') % contact.jid, _('You will no longer be able to send and receive messages to contacts from this transport.'))
		if window.get_response() == gtk.RESPONSE_OK:
			gajim.connections[account].unsubscribe_agent(contact.jid + '/' \
																		+ contact.resource)
			# remove transport from treeview
			self.remove_contact(contact, account)
			# remove transport's contacts from treeview
			jid_list = gajim.contacts.get_jid_list(account)
			for jid in jid_list:
				if jid.endswith('@' + contact.jid):
					c = gajim.contacts.get_first_contact_from_jid(account, jid)
					gajim.log.debug(
					'Removing contact %s due to unregistered transport %s'\
						% (jid, contact.jid))
					gajim.connections[account].unsubscribe(c.jid)
					# Transport contacts can't have 2 resources
					gajim.contacts.remove_jid(account, c.jid)
					self.remove_contact(c, account)
			gajim.contacts.remove_jid(account, contact.jid)
			gajim.contacts.remove_contact(account, contact)

	def on_rename(self, widget, iter, path):
		# this function is called either by F2 or by Rename menuitem
		# to display that menuitem we show a menu, that does focus-out
		# we then select Rename and focus-in
		# focus-in callback checks on this var and if is NOT None
		# it redraws the selected contact resulting in stopping our rename
		# procedure. So set this to None to stop that
		self._last_selected_contact = None
		model = self.tree.get_model()

		row_type = model[iter][C_TYPE]
		jid = model[iter][C_JID].decode('utf-8')
		account = model[iter][C_ACCOUNT].decode('utf-8')
		if row_type == 'contact':
			# it's jid
			# Remove resource indicator (Name (2))
			contact = gajim.contacts.get_first_contact_from_jid(account, jid)
			name = contact.name
			model[iter][C_NAME] = gtkgui_helpers.escape_for_pango_markup(name)

		model[iter][C_EDITABLE] = True # set 'editable' to True
		self.tree.set_cursor(path, self.tree.get_column(0), True)

	def on_assign_pgp_key(self, widget, contact, account):
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		keys = {}
		keyID = 'None'
		for i in xrange(0, len(attached_keys)/2):
			keys[attached_keys[2*i]] = attached_keys[2*i+1]
			if attached_keys[2*i] == contact.jid:
				keyID = attached_keys[2*i+1]
		public_keys = gajim.connections[account].ask_gpg_keys()
		public_keys['None'] = 'None'
		instance = dialogs.ChooseGPGKeyDialog(_('Assign OpenPGP Key'),
			_('Select a key to apply to the contact'), public_keys, keyID)
		keyID = instance.run()
		if keyID is None:
			return
		if keyID[0] == 'None':
			if contact.jid in keys:
				del keys[contact.jid]
		else:
			keys[contact.jid] = keyID[0]
			for u in gajim.contacts.get_contact(account, contact.jid):
				u.keyID = keyID[0]
			if gajim.interface.msg_win_mgr.has_window(contact.jid, account):
				ctrl = gajim.interface.msg_win_mgr.get_control(contact.jid, account)
				ctrl.update_ui()
		keys_str = ''
		for jid in keys:
			keys_str += jid + ' ' + keys[jid] + ' '
		gajim.config.set_per('accounts', account, 'attached_gpg_keys', keys_str)

	def on_edit_groups(self, widget, contact, account):
		dlg = dialogs.EditGroupsDialog(contact, account)
		dlg.run()

	def on_history(self, widget, contact, account):
		'''When history menuitem is activated: call log window'''
		if gajim.interface.instances['logs'].has_key(contact.jid):
			gajim.interface.instances['logs'][contact.jid].window.present()
		else:
			gajim.interface.instances['logs'][contact.jid] = history_window.\
				HistoryWindow(contact.jid, account)

	def on_send_single_message_menuitem_activate(self, widget, account,
	contact = None):
		if contact is None:
			dialogs.SingleMessageWindow(account, action = 'send')
		else:
			dialogs.SingleMessageWindow(account, contact.jid, 'send')

	def on_send_file_menuitem_activate(self, widget, account, contact):
		gajim.interface.instances['file_transfers'].show_file_send_request(
			account, contact)
	
	def on_add_special_notification_menuitem_activate(self, widget, jid):
		dialogs.AddSpecialNotificationDialog(jid)

	def mk_menu_user(self, event, iter):
		'''Make contact's popup menu'''
		model = self.tree.get_model()
		jid = model[iter][C_JID].decode('utf-8')
		path = model.get_path(iter)
		account = model[iter][C_ACCOUNT].decode('utf-8')
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)

		xml = gtk.glade.XML(GTKGUI_GLADE, 'roster_contact_context_menu',
			APP)
		roster_contact_context_menu = xml.get_widget(
			'roster_contact_context_menu')
		#childs = roster_contact_context_menu.get_children()

		start_chat_menuitem = xml.get_widget('start_chat_menuitem')
		send_single_message_menuitem = xml.get_widget('send_single_message_menuitem')
		rename_menuitem = xml.get_widget('rename_menuitem')
		edit_groups_menuitem = xml.get_widget('edit_groups_menuitem')
		# separator has with send file, assign_openpgp_key_menuitem, etc..
		above_send_file_separator = xml.get_widget('above_send_file_separator')
		send_file_menuitem = xml.get_widget('send_file_menuitem')
		assign_openpgp_key_menuitem = xml.get_widget('assign_openpgp_key_menuitem')
		add_special_notification_menuitem = xml.get_widget(
			'add_special_notification_menuitem')
		
		add_special_notification_menuitem.hide()
		add_special_notification_menuitem.set_no_show_all(True)

		#skip a separator
		subscription_menuitem = xml.get_widget('subscription_menuitem')
		send_auth_menuitem, ask_auth_menuitem, revoke_auth_menuitem =\
			subscription_menuitem.get_submenu().get_children()
		add_to_roster_menuitem = xml.get_widget('add_to_roster_menuitem')
		remove_from_roster_menuitem = xml.get_widget('remove_from_roster_menuitem')
		#skip a separator
		information_menuitem = xml.get_widget('information_menuitem')
		history_menuitem = xml.get_widget('history_menuitem')

		contacts = gajim.contacts.get_contact(account, jid)
		if len(contacts) > 1: # sevral resources
			sub_menu = gtk.Menu()
			start_chat_menuitem.set_submenu(sub_menu)

			iconset = gajim.config.get('iconset')
			if not iconset:
				iconset = DEFAULT_ICONSET
			path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
			for c in contacts:
				# icon MUST be different instance for every item
				state_images = self.load_iconset(path)
				item = gtk.ImageMenuItem(c.resource + ' (' + str(c.priority) + ')')
				icon_name = helpers.get_icon_name_to_show(c, account)
				icon = state_images[icon_name]
				item.set_image(icon)
				sub_menu.append(item)
				item.connect('activate', self.on_open_chat_window, c, account,
					c.resource)

		else: # one resource
			start_chat_menuitem.connect('activate',
				self.on_roster_treeview_row_activated, path)

		if contact.resource:
			send_file_menuitem.connect('activate',
				self.on_send_file_menuitem_activate, account, contact)
		else: # if we do not have resource we cannot send file
			send_file_menuitem.hide()
			send_file_menuitem.set_no_show_all(True)

		send_single_message_menuitem.connect('activate',
			self.on_send_single_message_menuitem_activate, account, contact)
		rename_menuitem.connect('activate', self.on_rename, iter, path)
		remove_from_roster_menuitem.connect('activate', self.on_req_usub,
			contact, account)
		information_menuitem.connect('activate', self.on_info, contact,
			account)
		history_menuitem.connect('activate', self.on_history, contact,
			account)

		if _('Not in Roster') not in contact.groups:
			#contact is in normal group
			edit_groups_menuitem.set_no_show_all(False)
			assign_openpgp_key_menuitem.set_no_show_all(False)
			add_to_roster_menuitem.hide()
			add_to_roster_menuitem.set_no_show_all(True)
			edit_groups_menuitem.connect('activate', self.on_edit_groups, contact,
				account)

			if gajim.config.get('usegpg'):
				assign_openpgp_key_menuitem.connect('activate',
					self.on_assign_pgp_key, contact, account)

			if contact.sub in ('from', 'both'):
				send_auth_menuitem.set_sensitive(False)
			else:
				send_auth_menuitem.connect('activate', self.authorize, jid, account)
			if contact.sub in ('to', 'both'):
				ask_auth_menuitem.set_sensitive(False)
				add_special_notification_menuitem.connect('activate',
					self.on_add_special_notification_menuitem_activate, jid)
			else:
				ask_auth_menuitem.connect('activate', self.req_sub, jid,
					_('I would like to add you to my roster'), account)
			if contact.sub in ('to', 'none'):
				revoke_auth_menuitem.set_sensitive(False)
			else:
				revoke_auth_menuitem.connect('activate', self.revoke_auth, jid,
					account)

		else: # contact is in group 'Not in Roster'
			add_to_roster_menuitem.set_no_show_all(False)
			edit_groups_menuitem.hide()
			edit_groups_menuitem.set_no_show_all(True)
			# hide first of the two consecutive separators
			above_send_file_separator.hide()
			above_send_file_separator.set_no_show_all(True)
			assign_openpgp_key_menuitem.hide()
			assign_openpgp_key_menuitem.set_no_show_all(True)

			add_to_roster_menuitem.connect('activate',
				self.on_add_to_roster, contact, account)

		#TODO create menu for sub contacts

		event_button = self.get_possible_button_event(event)

		roster_contact_context_menu.popup(None, None, None, event_button,
			event.time)
		roster_contact_context_menu.show_all()

	def mk_menu_g(self, event, iter):
		'''Make group's popup menu'''
		model = self.tree.get_model()
		path = model.get_path(iter)

		menu = gtk.Menu()

		rename_item = gtk.ImageMenuItem(_('Re_name'))
		rename_icon = gtk.image_new_from_stock(gtk.STOCK_REFRESH,
			gtk.ICON_SIZE_MENU)
		rename_item.set_image(rename_icon)
		menu.append(rename_item)
		rename_item.connect('activate', self.on_rename, iter, path)

		event_button = self.get_possible_button_event(event)

		menu.popup(None, None, None, event_button, event.time)
		menu.show_all()

	def mk_menu_agent(self, event, iter):
		'''Make agent's popup menu'''
		model = self.tree.get_model()
		jid = model[iter][C_JID].decode('utf-8')
		path = model.get_path(iter)
		account = model[iter][C_ACCOUNT].decode('utf-8')
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		menu = gtk.Menu()

		item = gtk.ImageMenuItem(_('_Log on'))
		icon = gtk.image_new_from_stock(gtk.STOCK_YES, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		show = contact.show
		if show != 'offline' and show != 'error':
			item.set_sensitive(False)
		item.connect('activate', self.on_agent_logging, jid, None, account)

		item = gtk.ImageMenuItem(_('Log _off'))
		icon = gtk.image_new_from_stock(gtk.STOCK_NO, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		if show in ('offline', 'error'):
			item.set_sensitive(False)
		item.connect('activate', self.on_agent_logging, jid, 'unavailable',
							account)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		item = gtk.ImageMenuItem(_('_Edit'))
		icon = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		item.connect('activate', self.on_edit_agent, contact, account)

		item = gtk.ImageMenuItem(_('_Remove from Roster'))
		icon = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		item.connect('activate', self.on_remove_agent, contact, account)

		event_button = self.get_possible_button_event(event)

		menu.popup(None, None, None, event_button, event.time)
		menu.show_all()

	def on_edit_account(self, widget, account):
		if gajim.interface.instances[account].has_key('account_modification'):
			gajim.interface.instances[account]['account_modification'].window.present()
		else:
			gajim.interface.instances[account]['account_modification'] = \
				config.AccountModificationWindow(account)

	def get_possible_button_event(self, event):
		'''mouse or keyboard caused the event?'''
		if event.type == gtk.gdk.KEY_PRESS:
			event_button = 0 # no event.button so pass 0
		else: # BUTTON_PRESS event, so pass event.button
			event_button = event.button

		return event_button

	def on_change_status_message_activate(self, widget, account):
		show = gajim.SHOW_LIST[gajim.connections[account].connected]
		dlg = dialogs.ChangeStatusMessageDialog(show)
		message = dlg.run()
		if message is not None: # None is if user pressed Cancel
			self.send_status(account, show, message)

	def build_account_menu(self, account):
		#FIXME: make most menuitems of this menu insensitive if account is offline

		# we have to create our own set of icons for the menu
		# using self.jabber_status_images is poopoo
		iconset = gajim.config.get('iconset')
		if not iconset:
			iconset = DEFAULT_ICONSET
		path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
		state_images = self.load_iconset(path)

		xml = gtk.glade.XML(GTKGUI_GLADE, 'account_context_menu', APP)
		account_context_menu = xml.get_widget('account_context_menu')
		childs = account_context_menu.get_children()

		status_menuitem = childs[0]
		# we skip the separator
		# skip advanced_actions_menuitem, childs[2]
		xml_console_menuitem = xml.get_widget('xml_console_menuitem')
		set_motd_menuitem = xml.get_widget('set_motd_menuitem')
		update_motd_menuitem = xml.get_widget('update_motd_menuitem')
		delete_motd_menuitem = xml.get_widget('delete_motd_menuitem')
		edit_account_menuitem = childs[3]
		service_discovery_menuitem = childs[4]
		add_contact_menuitem = childs[5]
		join_group_chat_menuitem = childs[6]
		new_message_menuitem = childs[7]

		sub_menu = gtk.Menu()
		status_menuitem.set_submenu(sub_menu)

		for show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible'):
			uf_show = helpers.get_uf_show(show, use_mnemonic = True)
			item = gtk.ImageMenuItem(uf_show)
			icon = state_images[show]
			item.set_image(icon)
			sub_menu.append(item)
			item.connect('activate', self.change_status, account, show)

		item = gtk.SeparatorMenuItem()
		sub_menu.append(item)

		item = gtk.ImageMenuItem(_('_Change Status Message'))
		path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'rename.png')
		img = gtk.Image()
		img.set_from_file(path)
		item.set_image(img)
		sub_menu.append(item)
		item.connect('activate', self.on_change_status_message_activate, account)
		if gajim.connections[account].connected < 2:
			item.set_sensitive(False)

		item = gtk.SeparatorMenuItem()
		sub_menu.append(item)

		uf_show = helpers.get_uf_show('offline', use_mnemonic = True)
		item = gtk.ImageMenuItem(uf_show)
		icon = state_images['offline']
		item.set_image(icon)
		sub_menu.append(item)
		item.connect('activate', self.change_status, account, 'offline')

		xml_console_menuitem.connect('activate',
			self.on_xml_console_menuitem_activate, account)
		set_motd_menuitem.connect('activate', self.on_set_motd_menuitem_activate,
			account)
		update_motd_menuitem.connect('activate',
			self.on_update_motd_menuitem_activate, account)
		delete_motd_menuitem.connect('activate',
			self.on_delete_motd_menuitem_activate, account)
		edit_account_menuitem.connect('activate', self.on_edit_account, account)
		service_discovery_menuitem.connect('activate',
			self.on_service_disco_menuitem_activate, account)
		add_contact_menuitem.connect('activate', self.on_add_new_contact, account)
		join_group_chat_menuitem.connect('activate',
			self.on_join_gc_activate, account)
		new_message_menuitem.connect('activate',
			self.on_new_message_menuitem_activate, account)
		return account_context_menu

	def mk_menu_account(self, event, iter):
		'''Make account's popup menu'''
		model = self.tree.get_model()
		account = model[iter][C_ACCOUNT].decode('utf-8')


		if account != 'all':
			menu = self.build_account_menu(account)
		else:
			menu = gtk.Menu()
			iconset = gajim.config.get('iconset')
			if not iconset:
				iconset = DEFAULT_ICONSET
			path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
			for account in gajim.connections:
				state_images = self.load_iconset(path)
				item = gtk.ImageMenuItem(account)
				show = gajim.SHOW_LIST[gajim.connections[account].connected]
				icon = state_images[show]
				item.set_image(icon)
				account_menu = self.build_account_menu(account)
				item.set_submenu(account_menu)
				menu.append(item)

		event_button = self.get_possible_button_event(event)

		menu.popup(None, self.tree, None, event_button, event.time)
		menu.show_all()

	def on_add_to_roster(self, widget, contact, account):
		dialogs.AddNewContactWindow(account, contact.jid)

	def authorize(self, widget, jid, account):
		'''Authorize a contact (by re-sending auth menuitem)'''
		gajim.connections[account].send_authorization(jid)
		dialogs.InformationDialog(_('Authorization has been sent'),
			_('Now "%s" will know your status.') %jid)

	def req_sub(self, widget, jid, txt, account, group = None, pseudo = None,
	auto_auth = False):
		'''Request subscription to a contact'''
		if group:
			group = [group]
		else:
			group = []
		gajim.connections[account].request_subscription(jid, txt, pseudo, group,
			auto_auth)
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if not contact:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact = gajim.contacts.create_contact(jid = jid, name = pseudo,
				groups = group, show = 'requested', status = '', ask = 'none',
				sub = 'subscribe', keyID = keyID)
			gajim.contacts.add_contact(account, contact)
		else:
			if not _('Not in Roster') in contact.groups:
				dialogs.InformationDialog(_('Subscription request has been sent'),
_('If "%s" accepts this request you will know his or her status.') % jid)
				return
			contact.groups = group
			if pseudo:
				contact.name = pseudo
			self.remove_contact(contact, account)
		self.add_contact_to_roster(jid, account)

	def revoke_auth(self, widget, jid, account):
		'''Revoke a contact's authorization'''
		gajim.connections[account].refuse_authorization(jid)
		dialogs.InformationDialog(_('Authorization has been removed'),
			_('Now "%s" will always see you as offline.') %jid)

	def on_roster_treeview_scroll_event(self, widget, event):
		self.tooltip.hide_tooltip()

	def on_roster_treeview_key_press_event(self, widget, event):
		'''when a key is pressed in the treeviews'''
		self.tooltip.hide_tooltip()
		if event.keyval == gtk.keysyms.Menu:
			self.show_treeview_menu(event)
			return True
		elif event.keyval == gtk.keysyms.Escape:
			self.tree.get_selection().unselect_all()
		elif event.keyval == gtk.keysyms.F2:
			treeselection = self.tree.get_selection()
			model, iter = treeselection.get_selected()
			if not iter:
				return
			type = model[iter][C_TYPE]
			if type in ('contact', 'group'):
				path = model.get_path(iter)
				self.on_rename(widget, iter, path)

		elif event.keyval == gtk.keysyms.Delete:
			treeselection = self.tree.get_selection()
			model, iter = treeselection.get_selected()
			if not iter:
				return
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			type = model[iter][C_TYPE]
			if type in ('account', 'group'):
				return
			contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
			if type == 'contact':
				self.on_req_usub(widget, contact, account)
			elif type == 'agent':
				self.on_remove_agent(widget, contact, account)

	def show_appropriate_context_menu(self, event, iter):
		model = self.tree.get_model()
		type = model[iter][C_TYPE]
		if type == 'group':
			self.mk_menu_g(event, iter)
		elif type == 'agent':
			self.mk_menu_agent(event, iter)
		elif type == 'contact':
			self.mk_menu_user(event, iter)
		elif type == 'account':
			self.mk_menu_account(event, iter)

	def show_treeview_menu(self, event):
		try:
			store, iter = self.tree.get_selection().get_selected()
		except TypeError:
			self.tree.get_selection().unselect_all()
			return
		model = self.tree.get_model()
		path = model.get_path(iter)
		self.tree.get_selection().select_path(path)

		self.show_appropriate_context_menu(event, iter)

		return True

	def on_roster_treeview_button_press_event(self, widget, event):
		# hide tooltip, no matter the button is pressed
		self.tooltip.hide_tooltip()
		if event.button == 3: # Right click
			try:
				path, column, x, y = self.tree.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				self.tree.get_selection().unselect_all()
				return
			self.tree.get_selection().select_path(path)
			model = self.tree.get_model()
			iter = model.get_iter(path)
			self.show_appropriate_context_menu(event, iter)
			return True

		elif event.button == 2: # Middle click
			try:
				path, column, x, y = self.tree.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				self.tree.get_selection().unselect_all()
				return
			self.tree.get_selection().select_path(path)
			model = self.tree.get_model()
			iter = model.get_iter(path)
			type = model[iter][C_TYPE]
			if type in ('agent', 'contact'):
				account = model[iter][C_ACCOUNT].decode('utf-8')
				jid = model[iter][C_JID].decode('utf-8')
				win = None
				c = gajim.contacts.get_contact_with_highest_priority(account, jid)
				if gajim.interface.msg_win_mgr.has_window(c.jid, account):
					win = gajim.interface.msg_win_mgr.get_window(c.jid, account)
				elif c:
					self.new_chat(c, account)
					win = gajim.interface.msg_win_mgr.get_window(jid, account)
				win.set_active_tab(jid, account)
				win.window.present()
			elif type == 'account':
				account = model[iter][C_ACCOUNT].decode('utf-8')
				if account != 'all':
					show = gajim.connections[account].connected
					if show > 1: # We are connected
						self.on_change_status_message_activate(widget, account)
					return True
				show = helpers.get_global_show()
				if show == 'offline':
					return True
				dlg = dialogs.ChangeStatusMessageDialog(show)
				message = dlg.run()
				if not message:
					return True
				for acct in gajim.connections:
					if not gajim.config.get_per('accounts', acct,
						'sync_with_global_status'):
						continue
					current_show = gajim.SHOW_LIST[gajim.connections[acct].connected]
					self.send_status(acct, current_show, message)
			return True

		elif event.button == 1: # Left click
			try:
				path, column, x, y = self.tree.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				self.tree.get_selection().unselect_all()
				return False
			model = self.tree.get_model()
			iter = model.get_iter(path)
			type = model[iter][C_TYPE]
			if type in ('group', 'contact'):
				if x < 27: # first cell in 1st column (the arrow SINGLE clicked)
					if (self.tree.row_expanded(path)):
						self.tree.collapse_row(path)
					else:
						self.tree.expand_row(path, False)

	def on_req_usub(self, widget, contact, account):
		'''Remove a contact'''
		window = dialogs.ConfirmationDialogCheck(
			_('Contact "%s" will be removed from your roster') % (
			contact.get_shown_name()),
			_('By removing this contact you also by default remove authorization resulting in him or her always seeing you as offline.'),
			_('I want this contact to know my status after removal'))
		# maybe use 2 optionboxes from which the contact can select? (better)
		if window.get_response() == gtk.RESPONSE_OK:
			remove_auth = True
			if window.is_checked():
				remove_auth = False
			gajim.connections[account].unsubscribe(contact.jid, remove_auth)
			for u in gajim.contacts.get_contact(account, contact.jid):
				self.remove_contact(u, account)
			gajim.contacts.remove_jid(account, u.jid)
			if not remove_auth:
				contact.name = ''
				contact.groups = []
				contact.sub = 'from'
				gajim.contacts.add_contact(account, contact)
				self.add_contact_to_roster(contact.jid, account)
			elif gajim.interface.msg_win_mgr.has_window(contact.jid, account):
				c = gajim.contacts.create_contact(jid = contact.jid,
					name = '', groups = [_('Not in Roster')],
					show = 'not in roster', status = '', ask = 'none',
					keyID = contact.keyID)
				gajim.contacts.add_contact(account, c)
				self.add_contact_to_roster(contact.jid, account)

	def forget_gpg_passphrase(self, keyid):
		if self.gpg_passphrase.has_key(keyid):
			del self.gpg_passphrase[keyid]
		return False

	def set_connecting_state(self, account):
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if accountIter:
			model[accountIter][0] =	self.jabber_state_images['16']['connecting']
		if gajim.interface.systray_enabled:
			gajim.interface.systray.change_status('connecting')

	def send_status(self, account, status, txt, sync = False, auto = False):
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if status != 'offline':
			if gajim.connections[account].connected < 2:
				self.set_connecting_state(account)

				if not gajim.connections[account].password:
					passphrase = ''
					w = dialogs.PassphraseDialog(
						_('Password Required'),
						_('Enter your password for account %s') % account,
						_('Save password'))
					passphrase, save = w.run()
					if passphrase == -1:
						if accountIter:
							model[accountIter][0] =	self.jabber_state_images['16']\
								['offline']
						if gajim.interface.systray_enabled:
							gajim.interface.systray.change_status('offline')
						self.update_status_combobox()
						return
					gajim.connections[account].password = passphrase
					if save:
						gajim.config.set_per('accounts', account, 'savepass', True)
						gajim.config.set_per('accounts', account, 'password',
							passphrase)

			keyid = None
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			# we don't need to bother with the passphrase if we use the agent
			if use_gpg_agent:
				save_gpg_pass = False
			else:
				save_gpg_pass = gajim.config.get_per('accounts', account,
					'savegpgpass')
			keyid = gajim.config.get_per('accounts', account, 'keyid')
			if keyid and gajim.connections[account].connected < 2 and \
				gajim.config.get('usegpg'):

				if use_gpg_agent:
					self.gpg_passphrase[keyid] = None
				else:
					if save_gpg_pass:
						passphrase = gajim.config.get_per('accounts', account, 'gpgpassword')
					else:
						if self.gpg_passphrase.has_key(keyid):
							passphrase = self.gpg_passphrase[keyid]
							save = False
						else:
							password_ok = False
							count = 0
							title = _('Passphrase Required')
							second = _('Enter GPG key passphrase for account %s.') % \
								account
							while not password_ok and count < 3:
								count += 1
								w = dialogs.PassphraseDialog(title, second,
									_('Save passphrase'))
								passphrase, save = w.run()
								if passphrase == -1:
									passphrase = None
									password_ok = True
								else:
									password_ok = gajim.connections[account].\
										test_gpg_passphrase(passphrase)
									title = _('Wrong Passphrase')
									second = _('Please retype your GPG passphrase or press Cancel.')
							if passphrase != None:
								self.gpg_passphrase[keyid] = passphrase
								gobject.timeout_add(30000, self.forget_gpg_passphrase, keyid)
						if save:
							gajim.config.set_per('accounts', account, 'savegpgpass', True)
							gajim.config.set_per('accounts', account, 'gpgpassword',
														passphrase)
					gajim.connections[account].gpg_passphrase(passphrase)

		for gc_control in gajim.interface.msg_win_mgr.get_controls(message_control.TYPE_GC):
			if gc_control.account == account:
				gajim.connections[account].send_gc_status(gc_control.nick,
					gc_control.room_jid, status, txt)
		gajim.connections[account].change_status(status, txt, sync, auto)
		if status == 'online' and gajim.interface.sleeper.getState() != \
			common.sleepy.STATE_UNKNOWN:
			gajim.sleeper_state[account] = 'online'
		else:
			gajim.sleeper_state[account] = 'off'

	def get_status_message(self, show):
		if (show == 'online' and not gajim.config.get('ask_online_status')) or \
			(show == 'offline' and not gajim.config.get('ask_offline_status')) or \
			show == 'invisible':
			return ''
		dlg = dialogs.ChangeStatusMessageDialog(show)
		message = dlg.run()
		return message

	def connected_rooms(self, account):
		if True in gajim.gc_connected[account].values():
			return True
		return False

	def change_status(self, widget, account, status):
		if status == 'invisible':
			if self.connected_rooms(account):
				dialog = dialogs.ConfirmationDialog(
		_('You are participating in one or more group chats'),
		_('Changing your status to invisible will result in disconnection from those group chats. Are you sure you want to go invisible?'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return
		message = self.get_status_message(status)
		if message is None: # user pressed Cancel to change status message dialog
			return
		self.send_status(account, status, message)

	def on_status_combobox_changed(self, widget):
		'''When we change our status via the combobox'''
		model = self.status_combobox.get_model()
		active = self.status_combobox.get_active()
		if active == -1: # no active item
			return
		if not self.combobox_callback_active:
			self.previous_status_combobox_active = active
			return
		accounts = gajim.connections.keys()
		if len(accounts) == 0:
			dialogs.ErrorDialog(_('No account available'),
		_('You must create an account before you can chat with other contacts.')
		).get_response()
			self.update_status_combobox()
			return
		status = model[active][2].decode('utf-8')
		one_connected = helpers.one_account_connected()
		if active == 7: # We choose change status message (7 is that)
			# do not change show, just show change status dialog
			status = model[self.previous_status_combobox_active][2].decode('utf-8')
			dlg = dialogs.ChangeStatusMessageDialog(status)
			message = dlg.run()
			if message is not None: # None if user pressed Cancel
				for acct in accounts:
					if not gajim.config.get_per('accounts', acct,
						'sync_with_global_status'):
						continue
					current_show = gajim.SHOW_LIST[gajim.connections[acct].connected]
					self.send_status(acct, current_show, message)
			self.combobox_callback_active = False
			self.status_combobox.set_active(self.previous_status_combobox_active)
			self.combobox_callback_active = True
			return
		# we are about to change show, so save this new show so in case
		# after user chooses "Change status message" menuitem
		# we can return to this show
		self.previous_status_combobox_active = active
		if status == 'invisible':
			bug_user = False
			for acct in accounts:
				if not one_connected or gajim.connections[acct].connected > 1:
					if not gajim.config.get_per('accounts', acct,
							'sync_with_global_status'):
						continue
					# We're going to change our status to invisible
					if self.connected_rooms(acct):
						bug_user = True
						break
			if bug_user:
				dialog = dialogs.ConfirmationDialog(
		_('You are participating in one or more group chats'),
		_('Changing your status to invisible will result in disconnection from those group chats. Are you sure you want to go invisible?'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					self.update_status_combobox()
					return
		message = self.get_status_message(status)
		if message is None: # user pressed Cancel to change status message dialog
			self.update_status_combobox()
			return
		for acct in accounts:
			if not gajim.config.get_per('accounts', acct, 'sync_with_global_status'):
				continue
			# we are connected (so we wanna change show and status)
			# or no account is connected and we want to connect with new show and status
			if not one_connected or gajim.connections[acct].connected > 1:
				self.send_status(acct, status, message)
		self.update_status_combobox()

	def update_status_combobox(self):
		# table to change index in connection.connected to index in combobox
		table = {'offline':9, 'connecting':9, 'online':0, 'chat':1, 'away':2,
			'xa':3, 'dnd':4, 'invisible':5}
		show = helpers.get_global_show()
		# temporarily block signal in order not to send status that we show
		# in the combobox
		self.combobox_callback_active = False
		self.status_combobox.set_active(table[show])
		self.combobox_callback_active = True
		if gajim.interface.systray_enabled:
			gajim.interface.systray.change_status(show)

	def on_status_changed(self, account, status):
		'''the core tells us that our status has changed'''
		if account not in gajim.contacts.get_accounts():
			return
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if accountIter:
			model[accountIter][0] = self.jabber_state_images['16'][status]
		if status == 'offline':
			if accountIter:
				model[accountIter][6] = None
			for jid in gajim.contacts.get_jid_list(account):
				lcontact = gajim.contacts.get_contact(account, jid)
				lcontact_copy = []
				for contact in lcontact:
					lcontact_copy.append(contact)
				for contact in lcontact_copy:
					self.chg_contact_status(contact, 'offline', '', account)
			self.actions_menu_needs_rebuild = True
		self.update_status_combobox()

	def new_chat(self, contact, account, private_chat = False, resource = None):
		# Get target window, create a control, and associate it with the window
		if not private_chat:
			type = message_control.TYPE_CHAT
		else:
			type = message_control.TYPE_PM

		fjid = contact.jid
		if resource:
			fjid += '/' + resource
		mw = gajim.interface.msg_win_mgr.get_window(fjid, account)
		if not mw:
			mw = gajim.interface.msg_win_mgr.create_window(contact, account, type)

		if not private_chat:
			chat_control = ChatControl(mw, contact, account, resource)
		else:
			chat_control = PrivateChatControl(mw, contact, account)

		mw.new_tab(chat_control)

		if gajim.awaiting_events[account].has_key(fjid):
			# We call this here to avoid race conditions with widget validation
			chat_control.read_queue()

	def new_chat_from_jid(self, account, jid):
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if not contact:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact = gajim.contacts.create_contact(jid = jid,
				name = jid.split('@')[0], groups = [_('Not in Roster')],
				show = 'not in roster', status = '', sub = 'none',
				keyID = keyID)
			gajim.contacts.add_contact(account, contact)
			self.add_contact_to_roster(contact.jid, account)

		if not gajim.interface.msg_win_mgr.has_window(contact.jid, account):
			self.new_chat(contact, account)
		mw = gajim.interface.msg_win_mgr.get_window(contact.jid, account)
		mw.set_active_tab(jid, account)
		mw.window.present()

	def new_room(self, room_jid, nick, account):
		# Get target window, create a control, and associate it with the window
		contact = gajim.contacts.create_contact(jid = room_jid, name = nick)
		mw = gajim.interface.msg_win_mgr.get_window(contact.jid, account)
		if not mw:
			mw = gajim.interface.msg_win_mgr.create_window(contact, account,
								GroupchatControl.TYPE_ID)
		gc_control = GroupchatControl(mw, contact, account)
		mw.new_tab(gc_control)

	def on_message(self, jid, msg, tim, account, encrypted = False,
			msg_type = '', subject = None, resource = ''):
		'''when we receive a message'''
		contact = None
		# if chat window will be for specific resource
		resource_for_chat = resource
		# Try to catch the contact with correct resource
		if resource:
			fjid = jid + '/' + resource
			contact = gajim.contacts.get_contact(account, jid, resource)
		# Default to highest prio
		highest_contact = gajim.contacts.get_contact_with_highest_priority(
			account, jid)
		if not contact:
			fjid = jid
			resource_for_chat = None
			contact = highest_contact
		if not contact:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact = gajim.contacts.create_contact(jid = jid,
				name = jid.split('@')[0], groups = [_('Not in Roster')],
				show = 'not in roster', status = '', ask = 'none',
				keyID = keyID, resource = resource)
			gajim.contacts.add_contact(account, contact)
			self.add_contact_to_roster(jid, account)

		iters = self.get_contact_iter(jid, account)
		if iters:
			path = self.tree.get_model().get_path(iters[0])
		else:
			path = None
		autopopup = gajim.config.get('autopopup')
		autopopupaway = gajim.config.get('autopopupaway')

		# Look for a chat control that has the given resource
		ctrl = gajim.interface.msg_win_mgr.get_control(fjid, account)
		if not ctrl:
			# if not, if message comes from highest prio, get control or open one
			# without resource
			if highest_contact and contact.resource == highest_contact.resource:
				ctrl = gajim.interface.msg_win_mgr.get_control(jid, account)
				fjid = jid
				resource_for_chat = None

		# Do we have a queue?
		qs = gajim.awaiting_events[account]
		no_queue = True
		if qs.has_key(fjid):
			no_queue = False
		popup = False
		if autopopup and (autopopupaway or gajim.connections[account].connected \
			in (1, 2)):
			popup = True

		if msg_type == 'normal' and popup: # it's single message to be autopopuped
			dialogs.SingleMessageWindow(account, contact.jid,
				action = 'receive', from_whom = jid, subject = subject,
				message = msg, resource = resource)
			return

		# We print if window is opened and it's not a single message
		if ctrl and msg_type != 'normal':
			typ = ''
			if msg_type == 'error':
				typ = 'status'
			ctrl.print_conversation(msg, typ, tim = tim, encrypted = encrypted,
						subject = subject)
			return

		# We save it in a queue
		if no_queue:
			qs[fjid] = []
		kind = 'chat'
		if msg_type == 'normal':
			kind = 'normal'
		qs[fjid].append((kind, (msg, subject, msg_type, tim, encrypted,
			resource)))
		self.nb_unread += 1
		if popup:
			if not ctrl:
				self.new_chat(contact, account, resource = resource_for_chat)
				if path:
					self.tree.expand_row(path[0:1], False)
					self.tree.expand_row(path[0:2], False)
					self.tree.scroll_to_cell(path)
					self.tree.set_cursor(path)
		else:
			if no_queue: # We didn't have a queue: we change icons
				self.draw_contact(jid, account)
				# Redraw parent too
				self.draw_parent_contact(jid, account)
			if gajim.interface.systray_enabled:
				gajim.interface.systray.add_jid(jid, account, kind)
			self.show_title() # we show the * or [n]
			if not path:
				self.add_contact_to_roster(jid, account)
				iters = self.get_contact_iter(jid, account)
				path = self.tree.get_model().get_path(iters[0])
			self.tree.expand_row(path[0:1], False)
			self.tree.expand_row(path[0:2], False)
			self.tree.scroll_to_cell(path)
			self.tree.set_cursor(path)

	def on_preferences_menuitem_activate(self, widget):
		if gajim.interface.instances.has_key('preferences'):
			gajim.interface.instances['preferences'].window.present()
		else:
			gajim.interface.instances['preferences'] = config.PreferencesWindow()

	def on_add_new_contact(self, widget, account):
		dialogs.AddNewContactWindow(account)

	def on_join_gc_activate(self, widget, account):
		'''when the join gc menuitem is clicked, show the join gc window'''
		invisible_show = gajim.SHOW_LIST.index('invisible')
		if gajim.connections[account].connected == invisible_show:
			dialogs.ErrorDialog(_('You cannot join a room while you are invisible')
				).get_response()
			return
		if gajim.interface.instances[account].has_key('join_gc'):
			gajim.interface.instances[account]['join_gc'].window.present()
		else:
			# c http://nkour.blogspot.com/2005/05/pythons-init-return-none-doesnt-return.html
			try:
				gajim.interface.instances[account]['join_gc'] = \
					dialogs.JoinGroupchatWindow(account)
			except RuntimeError:
				pass

	def on_new_message_menuitem_activate(self, widget, account):
		dialogs.NewMessageDialog(account)

	def on_contents_menuitem_activate(self, widget):
		helpers.launch_browser_mailer('url', 'http://trac.gajim.org/wiki')

	def on_faq_menuitem_activate(self, widget):
		helpers.launch_browser_mailer('url', 'http://trac.gajim.org/wiki/GajimFaq')

	def on_about_menuitem_activate(self, widget):
		dialogs.AboutDialog()

	def on_accounts_menuitem_activate(self, widget):
		if gajim.interface.instances.has_key('accounts'):
			gajim.interface.instances['accounts'].window.present()
		else:
			gajim.interface.instances['accounts'] = config.AccountsWindow()

	def on_file_transfers_menuitem_activate(self, widget):
		if gajim.interface.instances['file_transfers'].window.get_property('visible'):
			gajim.interface.instances['file_transfers'].window.present()
		else:
			gajim.interface.instances['file_transfers'].window.show_all()

	def on_manage_bookmarks_menuitem_activate(self, widget):
		config.ManageBookmarksWindow()

	def close_all(self, dic):
		'''close all the windows in the given dictionary'''
		for w in dic.values():
			if type(w) == type({}):
				self.close_all(w)
			else:
				w.window.destroy()

	def on_roster_window_delete_event(self, widget, event):
		'''When we want to close the window'''
		if gajim.interface.systray_enabled and not gajim.config.get('quit_on_roster_x_button'):
			self.tooltip.hide_tooltip()
			self.window.hide()
		else:
			accounts = gajim.connections.keys()
			get_msg = False
			for acct in accounts:
				if gajim.connections[acct].connected:
					get_msg = True
					break
			if get_msg:
				message = self.get_status_message('offline')
				if message is None: # user pressed Cancel to change status message dialog
					message = ''
				for acct in accounts:
					if gajim.connections[acct].connected:
						self.send_status(acct, 'offline', message, True)
			self.quit_gtkgui_interface()
		return True # do NOT destory the window

	def on_roster_window_focus_in_event(self, widget, event):
		# roster received focus, so if we had urgency REMOVE IT
		# NOTE: we do not have to read the message to remove urgency
		# so this functions does that
		gtkgui_helpers.set_unset_urgency_hint(widget, False)

		# if a contact row is selected, update colors (eg. for status msg)
		# because gtk engines may differ in bg when window is selected
		# or not
		if self._last_selected_contact is not None:
			jid, account = self._last_selected_contact
			self.draw_contact(jid, account, selected = True,
					focus = True)

	def on_roster_window_focus_out_event(self, widget, event):
		# if a contact row is selected, update colors (eg. for status msg)
		# because gtk engines may differ in bg when window is selected
		# or not
		if self._last_selected_contact is not None:
			jid, account = self._last_selected_contact
			self.draw_contact(jid, account, selected = True,
					focus = False)

	def on_roster_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			treeselection = self.tree.get_selection()
			model, iter = treeselection.get_selected()
			if not iter and gajim.interface.systray_enabled and not gajim.config.get('quit_on_roster_x_button'):
				self.tooltip.hide_tooltip()
				self.window.hide()

	def quit_gtkgui_interface(self):
		'''When we quit the gtk interface :
		tell that to the core and exit gtk'''
		if gajim.config.get('saveposition'):
			# in case show_roster_on_start is False and roster is never shown
			# window.window is None
			if self.window.window is not None:
				x, y = self.window.window.get_root_origin()
				gajim.config.set('roster_x-position', x)
				gajim.config.set('roster_y-position', y)
				width, height = self.window.get_size()
				gajim.config.set('roster_width', width)
				gajim.config.set('roster_height', height)

		gajim.interface.msg_win_mgr.shutdown()

		gajim.config.set('collapsed_rows', '\t'.join(self.collapsed_rows))
		gajim.interface.save_config()
		for account in gajim.connections:
			gajim.connections[account].quit(True)
		self.close_all(gajim.interface.instances)
		if gajim.interface.systray_enabled:
			gajim.interface.hide_systray()
		gtk.main_quit()

	def on_quit_menuitem_activate(self, widget):
		accounts = gajim.connections.keys()
		get_msg = False
		for acct in accounts:
			if gajim.connections[acct].connected:
				get_msg = True
				break
		if get_msg:
			message = self.get_status_message('offline')
			if message is None: # user pressed Cancel to change status message dialog
				return
			# check if we have unread or recent mesages
			unread = False
			recent = False
			if self.nb_unread > 0:
				unread = True
			for win in gajim.interface.msg_win_mgr.windows():
				unrd = 0
				for ctrl in win.controls():
					if ctrl.type_id == message_control.TYPE_GC:
						if gajim.config.get('notify_on_all_muc_messages'):
							unrd += ctrl.nb_unread
						else:
							if ctrl.attention_flag:
								unrd += 1
				if unrd:
					unread = True
					break

				for ctrl in win.controls():
					fjid = ctrl.get_full_jid()
					if gajim.last_message_time[acct].has_key(fjid):
						if time.time() - gajim.last_message_time[acct][fjid] < 2:
							recent = True
							break
			if unread:
				dialog = dialogs.ConfirmationDialog(_('You have unread messages'),
					_('Messages will only be available for reading them later if you have history enabled.'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return

			if recent:
				dialog = dialogs.ConfirmationDialog(_('You have unread messages'),
					_('Messages will only be available for reading them later if you have history enabled.'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return
			for acct in accounts:
				if gajim.connections[acct].connected:
					# send status asynchronously
					self.send_status(acct, 'offline', message, True)
		self.quit_gtkgui_interface()

	def open_event(self, account, jid, event):
		'''If an event was handled, return True, else return False'''
		typ = event[0]
		data = event[1]
		ft = gajim.interface.instances['file_transfers']
		if typ == 'normal':
			dialogs.SingleMessageWindow(account, jid,
				action = 'receive', from_whom = jid, subject = data[1],
				message = data[0], resource = data[5])
			gajim.interface.remove_first_event(account, jid, typ)
			return True
		elif typ == 'file-request':
			contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
			gajim.interface.remove_first_event(account, jid, typ)
			ft.show_file_request(account, contact, data)
			return True
		elif typ in ('file-request-error', 'file-send-error'):
			gajim.interface.remove_first_event(account, jid, typ)
			ft.show_send_error(data)
			return True
		elif typ in ('file-error', 'file-stopped'):
			gajim.interface.remove_first_event(account, jid, typ)
			ft.show_stopped(jid, data)
			return True
		elif typ == 'file-completed':
			gajim.interface.remove_first_event(account, jid, typ)
			ft.show_completed(jid, data)
			return True
		return False

	def on_open_chat_window(self, widget, contact, account, resource = None):
		# Get the window containing the chat
		fjid = contact.jid
		if resource:
			fjid += '/' + resource
		win = gajim.interface.msg_win_mgr.get_window(fjid, account)
		if not win:
			self.new_chat(contact, account, resource = resource)
			win = gajim.interface.msg_win_mgr.get_window(fjid, account)
			ctrl = win.get_control(fjid, account)
			# last message is long time ago
			gajim.last_message_time[account][ctrl.get_full_jid()] = 0
		win.set_active_tab(fjid, account)
		win.window.present()

	def on_roster_treeview_row_activated(self, widget, path, col = 0):
		'''When an iter is double clicked: open the first event window'''
		model = self.tree.get_model()
		account = model[path][C_ACCOUNT].decode('utf-8')
		type = model[path][C_TYPE]
		jid = model[path][C_JID].decode('utf-8')
		iter = model.get_iter(path)
		if type in ('group', 'account'):
			if self.tree.row_expanded(path):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, False)
		else:
			first_ev = gajim.get_first_event(account, jid)
			if not first_ev and model.iter_has_child(iter):
				child_iter = model.iter_children(iter)
				while not first_ev and child_iter:
					child_jid = model[child_iter][C_JID].decode('utf-8')
					first_ev = gajim.get_first_event(account, child_jid)
					if first_ev:
						jid = child_jid
					else:
						child_iter = model.iter_next(child_iter)
			if first_ev:
				if self.open_event(account, jid, first_ev):
					return
			c = gajim.contacts.get_contact_with_highest_priority(account, jid)
			self.on_open_chat_window(widget, c, account)

	def on_roster_treeview_row_expanded(self, widget, iter, path):
		'''When a row is expanded change the icon of the arrow'''
		model = self.tree.get_model()
		if gajim.config.get('mergeaccounts'):
			accounts = gajim.connections.keys()
		else:
			accounts = [model[iter][C_ACCOUNT].decode('utf-8')]
		type = model[iter][C_TYPE]
		if type == 'group':
			model.set_value(iter, 0, self.jabber_state_images['16']['opened'])
			jid = model[iter][C_JID].decode('utf-8')
			for account in accounts:
				if gajim.groups[account].has_key(jid): # This account has this group
					gajim.groups[account][jid]['expand'] = True
					if account + jid in self.collapsed_rows:
						self.collapsed_rows.remove(account + jid)
		elif type == 'account':
			account = accounts[0] # There is only one cause we don't use merge
			if account in self.collapsed_rows:
				self.collapsed_rows.remove(account)
			for g in gajim.groups[account]:
				groupIter = self.get_group_iter(g, account)
				if groupIter and gajim.groups[account][g]['expand']:
					pathG = model.get_path(groupIter)
					self.tree.expand_row(pathG, False)
		elif type == 'contact':
			jid =  model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			self.draw_contact(jid, account)

	def on_roster_treeview_row_collapsed(self, widget, iter, path):
		'''When a row is collapsed :
		change the icon of the arrow'''
		model = self.tree.get_model()
		if gajim.config.get('mergeaccounts'):
			accounts = gajim.connections.keys()
		else:
			accounts = [model[iter][C_ACCOUNT].decode('utf-8')]
		type = model[iter][C_TYPE]
		if type == 'group':
			model.set_value(iter, 0, self.jabber_state_images['16']['closed'])
			jid = model[iter][C_JID].decode('utf-8')
			for account in accounts:
				if gajim.groups[account].has_key(jid): # This account has this group
					gajim.groups[account][jid]['expand'] = False
					if not account + jid in self.collapsed_rows:
						self.collapsed_rows.append(account + jid)
		elif type == 'account':
			account = accounts[0] # There is only one cause we don't use merge
			if not account in self.collapsed_rows:
				self.collapsed_rows.append(account)
		elif type == 'contact':
			jid =  model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			self.draw_contact(jid, account)

	def on_editing_started(self, cell, event, row):
		''' start editing a cell in the tree'''
		path = self.tree.get_cursor()[0]
		self.editing_path = path

	def on_editing_canceled(self, cell):
		'''editing has been canceled'''
		path = self.tree.get_cursor()[0]
		# do not set new name if row order has changed
		if path != self.editing_path:
			self.editing_path = None
			return
		self.editing_path = None
		model = self.tree.get_model()
		iter = model.get_iter(path)
		account = model[iter][C_ACCOUNT].decode('utf-8')
		jid = model[iter][C_JID].decode('utf-8')
		type = model[iter][C_TYPE]
		# restore the number of resources string at the end of contact name
		contacts = gajim.contacts.get_contact(account, jid)
		if type == 'contact' and len(contacts) > 1:
			self.draw_contact(jid, account)
		# reset editable to False
		model[iter][C_EDITABLE] = False

	def on_cell_edited(self, cell, row, new_text):
		'''When an iter is edited:
		if text has changed, rename the contact'''
		model = self.tree.get_model()
		# if this is a last item in the group, row is invalid
		try:
			iter = model.get_iter_from_string(row)
		except:
			self.editing_path = None
			return
		path = model.get_path(iter)
		# do not set new name if row order has changed
		if path != self.editing_path:
			self.editing_path = None
			return
		self.editing_path = None
		new_text = new_text.decode('utf-8')
		account = model[iter][C_ACCOUNT].decode('utf-8')
		jid = model[iter][C_JID].decode('utf-8')
		type = model[iter][C_TYPE]
		if type == 'contact':
			old_text = gajim.contacts.get_contact_with_highest_priority(account,
				jid).name
			if old_text != new_text:
				for u in gajim.contacts.get_contact(account, jid):
					u.name = new_text
				gajim.connections[account].update_contact(jid, new_text, u.groups)
			self.draw_contact(jid, account)
			# Update opened chat
			ctrl = gajim.interface.msg_win_mgr.get_control(jid, account)
			if ctrl:
				ctrl.update_ui()
				win = gajim.interface.msg_win_mgr.get_window(jid, account)
				win.redraw_tab(ctrl)
				win.show_title()
		elif type == 'group':
			# in C_JID cilumn it's not escaped
			old_name = model[iter][C_JID].decode('utf-8')
			# Groups maynot change name from or to 'Not in Roster'
			if _('Not in Roster') in (new_text, old_name):
				return
			# get all contacts in that group
			for jid in gajim.contacts.get_jid_list(account):
				contact = gajim.contacts.get_contact_with_highest_priority(account,
					jid)
				if old_name in contact.groups:
					#set them in the new one and remove it from the old
					self.remove_contact(contact, account)
					contact.groups.remove(old_name)
					contact.groups.append(new_text)
					self.add_contact_to_roster(contact.jid, account)
					gajim.connections[account].update_contact(contact.jid,
						contact.name, contact.groups)
		model.set_value(iter, 5, False)

	def on_service_disco_menuitem_activate(self, widget, account):
		server_jid = gajim.config.get_per('accounts', account, 'hostname')
		if gajim.interface.instances[account]['disco'].has_key(server_jid):
			gajim.interface.instances[account]['disco'][server_jid].\
				window.present()
		else:
			try:
				# Object will add itself to the window dict
				disco.ServiceDiscoveryWindow(account, address_entry = True)
			except RuntimeError:
				pass

	def load_iconset(self, path, pixbuf2 = None, transport = False):
		'''load an iconset from the given path, and add pixbuf2 on top left of
		each static images'''
		imgs = {}
		path += '/'
		if transport:
			list = ('online', 'chat', 'away', 'xa', 'dnd', 'offline',
				'not in roster')
		else:
			list = ('connecting', 'online', 'chat', 'away', 'xa', 'dnd',
				'invisible', 'offline', 'error', 'requested', 'message', 'opened',
				'closed', 'not in roster', 'muc_active', 'muc_inactive')
			if pixbuf2:
				list = ('connecting', 'online', 'chat', 'away', 'xa', 'dnd',
					'offline', 'error', 'requested', 'message', 'not in roster')
		for state in list:
			# try to open a pixfile with the correct method
			state_file = state.replace(' ', '_')
			files = []
			files.append(path + state_file + '.gif')
			files.append(path + state_file + '.png')
			image = gtk.Image()
			image.show()
			imgs[state] = image
			for file in files: # loop seeking for either gif or png
				if os.path.exists(file):
					image.set_from_file(file)
					if pixbuf2 and image.get_storage_type() == gtk.IMAGE_PIXBUF:
						# add pixbuf2 on top-left corner of image
						pixbuf1 = image.get_pixbuf()
						pixbuf2.composite(pixbuf1, 0, 0,
							pixbuf2.get_property('width'),
							pixbuf2.get_property('height'), 0, 0, 1.0, 1.0,
							gtk.gdk.INTERP_HYPER, 255)
						image.set_from_pixbuf(pixbuf1)
					break
		return imgs

	def make_jabber_state_images(self):
		'''initialise jabber_state_images dict'''
		iconset = gajim.config.get('iconset')
		if not iconset:
			iconset = 'dcraven'
		path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '32x32')
		self.jabber_state_images['32'] = self.load_iconset(path)

		path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
		self.jabber_state_images['16'] = self.load_iconset(path)
		pixo = gtk.gdk.pixbuf_new_from_file(os.path.join(path, 'opened.png'))
		self.jabber_state_images['opened'] = self.load_iconset(path, pixo)
		pixc = gtk.gdk.pixbuf_new_from_file(os.path.join(path, 'closed.png'))
		self.jabber_state_images['closed'] = self.load_iconset(path, pixc)

		# update opened and closed transport iconsets
		t_path = os.path.join(gajim.DATA_DIR, 'iconsets', 'transports')
		folders = os.listdir(t_path)
		for transport in folders:
			if transport == '.svn':
				continue
			folder = os.path.join(t_path, transport, '16x16')
			self.transports_state_images['opened'][transport] = self.load_iconset(
				folder, pixo, transport = True)
			self.transports_state_images['closed'][transport] = self.load_iconset(
				folder, pixc, transport = True)

	def reload_jabber_state_images(self):
		self.make_jabber_state_images()
		# Update the roster
		self.draw_roster()
		# Update the status combobox
		model = self.status_combobox.get_model()
		iter = model.get_iter_root()
		while iter:
			if model[iter][2] != '':
				# If it's not change status message iter
				# eg. if it has show parameter not ''
				model[iter][1] = self.jabber_state_images['16'][model[iter][2]]
			iter = model.iter_next(iter)
		# Update the systray
		if gajim.interface.systray_enabled:
			gajim.interface.systray.set_img()

		for win in gajim.interface.msg_win_mgr.windows():
			for ctrl in gajim.interface.msg_win_mgr.controls():
				ctrl.update_ui()
				win.redraw_tab(ctrl)

		self.update_status_combobox()

	def repaint_themed_widgets(self):
		'''Notify windows that contain themed widgets to repaint them'''
		for win in gajim.interface.msg_win_mgr.windows():
			win.repaint_themed_widgets()
		for account in gajim.connections:
			for addr in gajim.interface.instances[account]['disco']:
				gajim.interface.instances[account]['disco'][addr].paint_banner()

	def on_show_offline_contacts_menuitem_activate(self, widget):
		'''when show offline option is changed:
		redraw the treeview'''
		gajim.config.set('showoffline', not gajim.config.get('showoffline'))
		self.draw_roster()

	def iconCellDataFunc(self, column, renderer, model, iter, data = None):
		'''When a row is added, set properties for icon renderer'''
		theme = gajim.config.get('roster_theme')
		if model[iter][C_TYPE] == 'account':
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
			renderer.set_property('xalign', 0)
		elif model[iter][C_TYPE] == 'group':
			color = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
			renderer.set_property('xalign', 0.2)
		else:
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background', '#adc3c6')
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background', '#ab6161')
			else:
				color = gajim.config.get_per('themes', theme, 'contactbgcolor')
				if color:
					renderer.set_property('cell-background', color)
				else:
					renderer.set_property('cell-background', None)
			parent_iter = model.iter_parent(iter)
			if model[parent_iter][C_TYPE] == 'contact':
				renderer.set_property('xalign', 1)
			else:
				renderer.set_property('xalign', 0.4)
		renderer.set_property('width', 26)

	def nameCellDataFunc(self, column, renderer, model, iter, data = None):
		'''When a row is added, set properties for name renderer'''
		theme = gajim.config.get('roster_theme')
		if model[iter][C_TYPE] == 'account':
			color = gajim.config.get_per('themes', theme, 'accounttextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				renderer.set_property('foreground', None)
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'accountfont'))
			renderer.set_property('xpad', 0)
			renderer.set_property('width', 3)
		elif model[iter][C_TYPE] == 'group':
			color = gajim.config.get_per('themes', theme, 'grouptextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				renderer.set_property('foreground', None)
			color = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'groupfont'))
			renderer.set_property('xpad', 4)
		else:
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			color = gajim.config.get_per('themes', theme, 'contacttextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				renderer.set_property('foreground', None)
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background', '#adc3c6')
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background', '#ab6161')
			else:
				color = gajim.config.get_per('themes', theme, 'contactbgcolor')
				if color:
					renderer.set_property('cell-background', color)
				else:
					renderer.set_property('cell-background', None)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'contactfont'))
			parent_iter = model.iter_parent(iter)
			if model[parent_iter][C_TYPE] == 'contact':
				renderer.set_property('xpad', 16)
			else:
				renderer.set_property('xpad', 8)

	def fill_secondary_pixbuf_rederer(self, column, renderer, model, iter, data=None):
		'''When a row is added, set properties for secondary renderer (avatar or padlock)'''
		theme = gajim.config.get('roster_theme')
		if model[iter][C_TYPE] == 'account':
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
		elif model[iter][C_TYPE] == 'group':
			color = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
		else: # contact
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background', '#adc3c6')
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background', '#ab6161')
			else:
				color = gajim.config.get_per('themes', theme, 'contactbgcolor')
				if color:
					renderer.set_property('cell-background', color)
				else:
					renderer.set_property('cell-background', None)
		renderer.set_property('xalign', 1) # align pixbuf to the right

	def get_show(self, lcontact):
		prio = lcontact[0].priority
		show = lcontact[0].show
		for u in lcontact:
			if u.priority > prio:
				prio = u.priority
				show = u.show
		return show

	def compareIters(self, model, iter1, iter2, data = None):
		'''Compare two iters to sort them'''
		name1 = model[iter1][C_NAME]
		name2 = model[iter2][C_NAME]
		if not name1 or not name2:
			return 0
		name1 = name1.decode('utf-8')
		name2 = name2.decode('utf-8')
		type1 = model[iter1][C_TYPE]
		type2 = model[iter2][C_TYPE]
		if type1 == 'group':
			if name1 == _('Transports'):
				return 1
			if name2 == _('Transports'):
				return -1
			if name1 == _('Not in Roster'):
				return 1
			if name2 == _('Not in Roster'):
				return -1
		account1 = model[iter1][C_ACCOUNT]
		account2 = model[iter2][C_ACCOUNT]
		if not account1 or not account2:
			return 0
		account1 = account1.decode('utf-8')
		account2 = account2.decode('utf-8')
		jid1 = model[iter1][C_JID].decode('utf-8')
		jid2 = model[iter2][C_JID].decode('utf-8')
		if type1 == 'contact':
			lcontact1 = gajim.contacts.get_contact(account1, jid1)
			contact1 = gajim.contacts.get_first_contact_from_jid(account1, jid1)
			if not contact1:
				return 0
			name1 = contact1.get_shown_name()
		if type2 == 'contact':
			lcontact2 = gajim.contacts.get_contact(account2, jid2)
			contact2 = gajim.contacts.get_first_contact_from_jid(account2, jid2)
			if not contact2:
				return 0
			name2 = contact2.get_shown_name()
		# We first compare by show if sort_by_show is True or if it's a child
		# contact
		if type1 == 'contact' and type2 == 'contact' and \
		gajim.config.get('sort_by_show'):
			cshow = {'online':0, 'chat': 1, 'away': 2, 'xa': 3, 'dnd': 4,
				'invisible': 5, 'offline': 6, 'not in roster': 7, 'error': 8}
			s = self.get_show(lcontact1)
			if s in cshow:
				show1 = cshow[s]
			else:
				show1 = 9
			s = self.get_show(lcontact2)
			if s in cshow:
				show2 = cshow[s]
			else:
				show2 = 9
			if show1 < show2:
				return -1
			elif show1 > show2:
				return 1
		# We compare names
		if name1.lower() < name2.lower():
			return -1
		if name2.lower() < name1.lower():
			return 1
		if type1 == 'contact' and type2 == 'contact':
			# We compare account names
			if account1.lower() < account2.lower():
				return -1
			if account2.lower() < account1.lower():
				return 1
			# We compare jids
			if jid1.lower() < jid2.lower():
				return -1
			if jid2.lower() < jid1.lower():
				return 1
		return 0

	def drag_data_get_data(self, treeview, context, selection, target_id, etime):
		treeselection = treeview.get_selection()
		model, iter = treeselection.get_selected()
		path = model.get_path(iter)
		data = ''
		if len(path) >= 3:
			data = model[iter][C_JID]
		selection.set(selection.target, 8, data)

	def on_drop_in_contact(self, widget, account, c_source, c_dest, context,
		etime):
		# children must take the new tag too, so remember old tag
		old_tag = gajim.contacts.get_metacontacts_tag(account, c_source.jid)
		# remove the source row
		self.remove_contact(c_source, account)
		# brother inherite big brother groups
		c_source.groups = []
		for g in c_dest.groups:
			c_source.groups.append(g)
		gajim.contacts.add_metacontact(account, c_dest.jid, account, c_source.jid)
		# add children too
		all_jid = gajim.contacts.get_metacontacts_jids(old_tag)
		for _account in all_jid:
			for _jid in all_data[_account]:
				gajim.contacts.add_metacontact(account, c_dest.jid, _account, _jid)
				self.add_contact_to_roster(_jid, _account)
				self.draw_contact(_jid, _account)
		self.add_contact_to_roster(c_source.jid, account)
		self.draw_contact(c_dest.jid, account)

		context.finish(True, True, etime)

	def on_drop_in_group(self, widget, account, c_source, grp_dest, context,
		etime, grp_source = None):
		if grp_source:
			self.remove_contact_from_group(account, c_source, grp_source)
		# remove tag
		gajim.contacts.remove_metacontact(account, c_source.jid)
		self.add_contact_to_group(account, c_source, grp_dest)
		if context.action in (gtk.gdk.ACTION_MOVE, gtk.gdk.ACTION_COPY):
			context.finish(True, True, etime)

	def add_contact_to_group(self, account, contact, group):
		model = self.tree.get_model()
		if not group in contact.groups:
			contact.groups.append(group)
		# Remove all rows because add_contact_to_roster doesn't add it if one
		# is already in roster
		for i in self.get_contact_iter(contact.jid, account):
			model.remove(i)
		self.add_contact_to_roster(contact.jid, account)
		gajim.connections[account].update_contact(contact.jid, contact.name,
			contact.groups)

	def remove_contact_from_group(self, account, contact, group):
		if not group in contact.groups:
			return
		model = self.tree.get_model()
		# Make sure contact was in the group
		contact.groups.remove(group)
		self.remove_contact(contact, account)

	def drag_data_received_data(self, treeview, context, x, y, selection, info,
		etime):
		model = treeview.get_model()
		if not selection.data:
			return
		data = selection.data
		drop_info = treeview.get_dest_row_at_pos(x, y)
		if not drop_info:
			return
		path_dest, position = drop_info
		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2 \
			and path_dest[1] == 0: # dropped before the first group
			return
		iter_dest = model.get_iter(path_dest)
		type_dest = model[iter_dest][C_TYPE].decode('utf-8')
		jid_dest = model[iter_dest][C_JID].decode('utf-8')

		if info == self.TARGET_TYPE_URI_LIST:
			# User dropped a file on the roster
			if len(path_dest) < 3:
				return
			if type_dest != 'contact':
				return
			account = model[iter_dest][C_ACCOUNT].decode('utf-8')
			c_dest = gajim.contacts.get_contact_with_highest_priority(account,
				jid_dest)
			uri = data.strip()
			uri_splitted = uri.split() # we may have more than one file dropped
			for uri in uri_splitted:
				path = helpers.get_file_path_from_dnd_dropped_uri(uri)
				if os.path.isfile(path): # is it file?
					gajim.interface.instances['file_transfers'].send_file(account,
						c_dest, path)
			return

		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2:
			# dropped before a group : we drop it in the previous group
			path_dest = (path_dest[0], path_dest[1]-1)
		iter_source = treeview.get_selection().get_selected()[1]
		path_source = model.get_path(iter_source)
		type_source = model[iter_source][C_TYPE]
		if type_dest == 'account': # dropped on an account
			return
		if type_source != 'contact': # source is not a contact
			return
		account = model[iter_source][C_ACCOUNT].decode('utf-8')
		if type_dest == 'contact':
			dest_account = model[iter_dest][C_ACCOUNT].decode('utf-8')
			if account != dest_account: # dropped on a contact from another account
				return
		it = iter_source
		while model[it][C_TYPE] == 'contact':
			it = model.iter_parent(it)
		iter_group_source = it
		grp_source = model[it][C_JID].decode('utf-8')
		if grp_source == _('Transports') or grp_source == _('Not in Roster'):
			return
		jid_source = data.decode('utf-8')
		c_source = gajim.contacts.get_contact_with_highest_priority(account,
			jid_source)
		# Get destination group
		if type_dest == 'group':
			grp_dest = model[iter_dest][C_JID].decode('utf-8')
			if grp_dest == _('Transports') or grp_dest == _('Not in Roster'):
				return
			if context.action == gtk.gdk.ACTION_COPY:
				self.on_drop_in_group(None, account, c_source, grp_dest, context,
					etime)
				return
			self.on_drop_in_group(None, account, c_source, grp_dest, context,
				etime, grp_source)
			return
		else:
			it = iter_dest
			while model[it][C_TYPE] != 'group':
				it = model.iter_parent(it)
			grp_dest = model[it][C_JID].decode('utf-8')
		if grp_dest == _('Transports') or grp_dest == _('Not in Roster'):
			return
		if jid_source == jid_dest:
			if grp_source == grp_dest:
				return
			if context.action == gtk.gdk.ACTION_COPY:
				self.on_drop_in_group(None, account, c_source, grp_dest, context,
					etime)
				return
			self.on_drop_in_group(None, account, c_source, grp_dest, context,
				etime, grp_source)
			return
		if grp_source == grp_dest:
			# Add meta contact
			#FIXME: doesn't work under windows: http://bugzilla.gnome.org/show_bug.cgi?id=329797
#			if context.action == gtk.gdk.ACTION_COPY:
#				# Keep only MOVE
#				return
			c_dest = gajim.contacts.get_contact_with_highest_priority(account,
				jid_dest)
			self.on_drop_in_contact(treeview, account, c_source, c_dest, context,
				etime)
			return
		# We upgrade only the first user because user2.groups is a pointer to
		# user1.groups
		if context.action == gtk.gdk.ACTION_COPY:
			self.on_drop_in_group(None, account, c_source, grp_dest, context,
				etime)
		else:
			menu = gtk.Menu()
			item = gtk.MenuItem(_('Drop %s in group %s') % (c_source.name,
				grp_dest))
			item.connect('activate', self.on_drop_in_group, account, c_source,
				grp_dest, context, etime, grp_source)
			menu.append(item)
			c_dest = gajim.contacts.get_contact_with_highest_priority(account,
				jid_dest)
			item = gtk.MenuItem(_('Make %s and %s metacontacts') % (c_source.name,
				c_dest.name))
			item.connect('activate', self.on_drop_in_contact, account, c_source,
				c_dest, context, etime)
			menu.append(item)

			menu.popup(None, None, None, 1, etime)
			menu.show_all()

	def show_title(self):
		change_title_allowed = gajim.config.get('change_roster_title')
		if change_title_allowed:
			start = ''
			if self.nb_unread > 1:
				start = '[' + str(self.nb_unread) + ']  '
			elif self.nb_unread == 1:
				start = '*  '
			self.window.set_title(start + 'Gajim')

		gtkgui_helpers.set_unset_urgency_hint(self.window, self.nb_unread)

	def iter_is_separator(self, model, iter):
		if model[iter][0] == 'SEPARATOR':
			return True
		return False

	def iter_contact_rows(self):
		'''iterate over all contact rows in the tree model'''
		model = self.tree.get_model()
		account_iter = model.get_iter_root()
		while account_iter:
			group_iter = model.iter_children(account_iter)
			while group_iter:
				contact_iter = model.iter_children(group_iter)
				while contact_iter:
					yield model[contact_iter]
					contact_iter = model.iter_next(contact_iter)
				group_iter = model.iter_next(group_iter)
			account_iter = model.iter_next(account_iter)

	def on_roster_treeview_style_set(self, treeview, style):
		'''When style (theme) changes, redraw all contacts'''
		for contact in self.iter_contact_rows():
			self.draw_contact(contact[C_JID].decode('utf-8'),
				contact[C_ACCOUNT].decode('utf-8'))

	def _on_treeview_selection_changed(self, selection):
		model, selected_iter = selection.get_selected()
		if self._last_selected_contact is not None:
			# update unselected row
			jid, account = self._last_selected_contact
			self.draw_contact(jid, account)
		if selected_iter is None:
			self._last_selected_contact = None
			return
		contact_row = model[selected_iter]
		if contact_row[C_TYPE] != 'contact':
			return
		jid = contact_row[C_JID].decode('utf-8')
		account = contact_row[C_ACCOUNT].decode('utf-8')
		self._last_selected_contact = (jid, account)
		self.draw_contact(jid, account, selected = True)

	def __init__(self):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'roster_window', APP)
		self.window = self.xml.get_widget('roster_window')
		gajim.interface.msg_win_mgr = MessageWindowMgr()
		if gajim.config.get('roster_window_skip_taskbar'):
			self.window.set_property('skip-taskbar-hint', True)
		self.tree = self.xml.get_widget('roster_treeview')
		self.tree.get_selection().connect('changed',
			self._on_treeview_selection_changed)

		self._last_selected_contact = None # None or holds jid, account tupple
		self.jabber_state_images = {'16': {}, '32': {}, 'opened': {},
			'closed': {}}
		self.transports_state_images = {'16': {}, '32': {}, 'opened': {},
			'closed': {}}
		
		self.nb_unread = 0 # number of unread messages
		self.last_save_dir = None
		self.editing_path = None  # path of row with cell in edit mode
		self.add_new_contact_handler_id = False
		self.service_disco_handler_id = False
		self.new_message_menuitem_handler_id = False
		self.actions_menu_needs_rebuild = True
		self.regroup = gajim.config.get('mergeaccounts')
		if len(gajim.connections) < 2: # Do not merge accounts if only one exists
			self.regroup = False
		#FIXME: When list_accel_closures will be wrapped in pygtk
		# no need of this variable
		self.have_new_message_accel = False # Is the "Ctrl+N" shown ?
		if gajim.config.get('saveposition'):
			gtkgui_helpers.move_window(self.window,
				gajim.config.get('roster_x-position'),
				gajim.config.get('roster_y-position'))
			gtkgui_helpers.resize_window(self.window,
				gajim.config.get('roster_width'),
				gajim.config.get('roster_height'))

		self.popups_notification_height = 0
		self.popup_notification_windows = []
		self.gpg_passphrase = {}

		#(icon, name, type, jid, account, editable, secondary_pixbuf)
		model = gtk.TreeStore(gtk.Image, str, str, str, str, bool, gtk.gdk.Pixbuf)

		model.set_sort_func(1, self.compareIters)
		model.set_sort_column_id(1, gtk.SORT_ASCENDING)
		self.tree.set_model(model)
		self.make_jabber_state_images()

		path = os.path.join(gajim.DATA_DIR, 'iconsets', 'transports')
		folders = os.listdir(path)
		for transport in folders:
			if transport == '.svn':
				continue
			folder = os.path.join(path, transport, '32x32')
			self.transports_state_images['32'][transport] = self.load_iconset(
				folder, transport = True)
			folder = os.path.join(path, transport, '16x16')
			self.transports_state_images['16'][transport] = self.load_iconset(
				folder, transport = True)

		# uf_show, img, show, sensitive
		liststore = gtk.ListStore(str, gtk.Image, str, bool)
		self.status_combobox = self.xml.get_widget('status_combobox')

		cell = cell_renderer_image.CellRendererImage(0, 1)
		self.status_combobox.pack_start(cell, False)

		# img to show is in in 2nd column of liststore
		self.status_combobox.add_attribute(cell, 'image', 1)
		# if it will be sensitive or not it is in the fourth column
		# all items in the 'row' must have sensitive to False
		# if we want False (so we add it for img_cell too)
		self.status_combobox.add_attribute(cell, 'sensitive', 3)

		cell = gtk.CellRendererText()
		cell.set_property('xpad', 5) # padding for status text
		self.status_combobox.pack_start(cell, True)
		# text to show is in in first column of liststore
		self.status_combobox.add_attribute(cell, 'text', 0)
		# if it will be sensitive or not it is in the fourth column
		self.status_combobox.add_attribute(cell, 'sensitive', 3)

		self.status_combobox.set_row_separator_func(self.iter_is_separator)

		for show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible'):
			uf_show = helpers.get_uf_show(show)
			liststore.append([uf_show, self.jabber_state_images['16'][show], show, True])
		# Add a Separator (self.iter_is_separator() checks on string SEPARATOR)
		liststore.append(['SEPARATOR', None, '', True])

		path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'rename.png')
		img = gtk.Image()
		img.set_from_file(path)
		# sensitivity to False because by default we're offline
		self.status_message_menuitem_iter = liststore.append(
			[_('Change Status Message...'), img, '', False])
		# Add a Separator (self.iter_is_separator() checks on string SEPARATOR)
		liststore.append(['SEPARATOR', None, '', True])

		uf_show = helpers.get_uf_show('offline')
		liststore.append([uf_show, self.jabber_state_images['16']['offline'],
			'offline', True])

		status_combobox_items = ['online', 'chat', 'away', 'xa', 'dnd', 'invisible',
			'separator1', 'change_status_msg', 'separator2', 'offline']
		self.status_combobox.set_model(liststore)

		# default to offline
		number_of_menuitem = status_combobox_items.index('offline')
		self.status_combobox.set_active(number_of_menuitem)

		# holds index to previously selected item so if "change status message..."
		# is selected we can fallback to previously selected item and not stay
		# with that item selected
		self.previous_status_combobox_active = number_of_menuitem

		showOffline = gajim.config.get('showoffline')
		self.xml.get_widget('show_offline_contacts_menuitem').set_active(
			showOffline)

		# columns

		# this col has 3 cells:
		# first one img, second one text, third is sec pixbuf
		col = gtk.TreeViewColumn()

		render_image = cell_renderer_image.CellRendererImage(0, 0) # show img or +-
		col.pack_start(render_image, expand = False)
		col.add_attribute(render_image, 'image', C_IMG)
		col.set_cell_data_func(render_image, self.iconCellDataFunc, None)

		render_text = gtk.CellRendererText() # contact or group or account name
		render_text.connect('edited', self.on_cell_edited)
		render_text.connect('editing-canceled', self.on_editing_canceled)
		render_text.connect('editing-started', self.on_editing_started)
		col.pack_start(render_text, expand = True)
		col.add_attribute(render_text, 'markup', C_NAME) # where we hold the name
		col.add_attribute(render_text, 'editable', C_EDITABLE) # where we hold if the row is editable
		col.set_cell_data_func(render_text, self.nameCellDataFunc, None)

		render_pixbuf = gtk.CellRendererPixbuf() # tls or avatar img
		col.pack_start(render_pixbuf, expand = False)
		col.add_attribute(render_pixbuf, 'pixbuf', C_SECPIXBUF)
		col.set_cell_data_func(render_pixbuf, self.fill_secondary_pixbuf_rederer,
			None)

		self.tree.append_column(col)

		#do not show gtk arrows workaround
		col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand = False)
		self.tree.append_column(col)
		col.set_visible(False)
		self.tree.set_expander_column(col)
		
		#signals
		self.TARGET_TYPE_URI_LIST = 80
		TARGETS = [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)]
		TARGETS2 = [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),
					('text/uri-list', 0, self.TARGET_TYPE_URI_LIST)]
		self.tree.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, TARGETS,
			gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
		self.tree.enable_model_drag_dest(TARGETS2, gtk.gdk.ACTION_DEFAULT)
		self.tree.connect('drag_data_get', self.drag_data_get_data)
		self.tree.connect('drag_data_received', self.drag_data_received_data)
		self.xml.signal_autoconnect(self)
		self.combobox_callback_active = True

		self.collapsed_rows = gajim.config.get('collapsed_rows').split('\t')
		self.tooltip = tooltips.RosterTooltip()
		self.draw_roster()

		if gajim.config.get('show_roster_on_startup'):
			self.window.show_all()
		else:
			if not gajim.config.get('trayicon'):
				# cannot happen via GUI, but I put this incase user touches
				# config. without trayicon, he or she should see the roster!
				self.window.show_all()
				gajim.config.set('show_roster_on_startup', True)

		if len(gajim.connections) == 0: # if we have no account
			gajim.interface.instances['account_creation_wizard'] = \
				config.AccountCreationWizardWindow()

