# -*- coding: utf-8 -*-
##	normal_control.py
##
## Copyright (C) 2007 Yann Leboulanger <asterix@lagaule.org>
## Copyright (C) 2007 David Danier <goliath.mailinglist@gmx.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

import gtk
import gobject
import os

import gtkgui_helpers
import vcard
import conversation_textview
import message_control
import dataforms_widget

try:
	import gtkspell
	HAS_GTK_SPELL = True
except:
	HAS_GTK_SPELL = False

# those imports are not used in this file, but in files that 'import dialogs'
# so they can do dialog.GajimThemesWindow() for example
from filetransfers_window import FileTransfersWindow
from gajim_themes_window import GajimThemesWindow
from advanced import AdvancedConfigurationWindow

from chat_control import ChatControlBase
from common import gajim
from common import helpers
from common import dataforms
from common.exceptions import GajimGeneralException


class NormalControl(ChatControlBase):
	'''NormalControl can send or show a received
	singled message depending on action argument which can be 'send'
	or 'receive'.
	'''
	TYPE_ID = message_control.TYPE_NORMAL
	def __init__(self, parent_win, account, to='', action='', from_whom='',
	subject='', message='', resource='', session=None, form_node=None,
	encrypted=None):
		#FIXME: we need to create a contact if none exists
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
			'normal_child_vbox', None, account, resource)

		self.action = action
		self.subject = subject
		self.message = message
		self.to = to
		self.from_whom = from_whom

		self.set_session(session)

		widget = self.xml.get_widget('normal_window_actions_button')
		id = widget.connect('clicked', self.on_actions_button_clicked)
		self.handlers[id] = widget

		#FIXME: Window is not usable without buttons ...
#		compact_view = gajim.config.get('compact_view')
#		self.chat_buttons_set_visible(compact_view)
		self.widget_set_visible(self.xml.get_widget('banner_eventbox'),
			gajim.config.get('hide_chat_banner'))

		# keep timeout id and window obj for possible big avatar
		# it is on enter-notify and leave-notify so no need to be per jid
		self.show_bigger_avatar_timeout_id = None
		self.bigger_avatar_window = None
		self.show_avatar(self.contact.resource)

		widget = self.xml.get_widget('avatar_eventbox')
		id = widget.connect('enter-notify-event',
			self.on_avatar_eventbox_enter_notify_event)
		self.handlers[id] = widget

		id = widget.connect('leave-notify-event',
			self.on_avatar_eventbox_leave_notify_event)
		self.handlers[id] = widget

		id = widget.connect('button-press-event',
			self.on_avatar_eventbox_button_press_event)
		self.handlers[id] = widget

		widget = self.xml.get_widget('gpg_togglebutton')
		id = widget.connect('clicked', self.on_gpg_togglebutton_toggled)
		self.handlers[id] = widget

		if encrypted is None:
			jid = to
			# cannot use self.get_contact(), as self.to_entry does not exist yet
			contact = None
			if '@' in jid:
				if '/' in jid:
					jid, resource = jid.split('/', 1)
				else:
					resource = self.resource
				contact = gajim.contacts.get_contact(self.account, jid, resource)
			if contact: # only load if we have a valid contact
				encrypted = gajim.config.get_per('contacts', contact.jid,
					'gpg_enabled')
		if encrypted is None:
			encrypted = False
		self.encrypted = encrypted
		self.next_count = 0

		self.status_tooltip = gtk.Tooltips()
		self.update_ui()
		#TODO:
		# restore previous conversation
		self.restore_conversation()

		self.count_chars_label = self.xml.get_widget('count_chars_label')
		self.from_entry = self.xml.get_widget('from_entry')
		self.to_entry = self.xml.get_widget('to_entry')
		self.subject_entry = self.xml.get_widget('subject_entry')

		self.form_widget = None
		parent_box = self.xml.get_widget('conversation_scrolledwindow').\
			get_parent()
		if form_node:
			dataform = dataforms.ExtendForm(node = form_node)
			self.form_widget = dataforms_widget.DataFormWidget(dataform)
			self.form_widget.show_all()
			parent_box.add(self.form_widget)
			parent_box.child_set_property(self.form_widget, 'position',
				parent_box.child_get_property(self.xml.get_widget(
				'conversation_scrolledwindow'), 'position'))
			self.action = 'form'

		self.send_button = self.xml.get_widget('send_button')
		self.quote_button = self.xml.get_widget('quote_button')
		self.reply_button = self.xml.get_widget('reply_button')
		self.next_button = self.xml.get_widget('next_button')
		self.next_count_label = self.xml.get_widget('next_count_label')
		self.send_and_close_button = self.xml.get_widget('send_and_close_button')
#		self.cancel_button = self.xml.get_widget('cancel_button')
#		self.close_button = self.xml.get_widget('close_button')
		msg_tv_buffer = self.msg_textview.get_buffer()
		msg_tv_buffer.connect('changed', self.update_char_counter)
		if type(to) == type([]):
			jid = ', '.join( [i[0].jid + '/' + i[0].resource for i in to])
			self.to_entry.set_text(jid)
			self.to_entry.set_sensitive(False)
		else:
			if resource and not '/' in to:
				self.to_entry.set_text(to + '/' + resource)
			else:
				self.to_entry.set_text(to)

		if gajim.config.get('use_speller') and HAS_GTK_SPELL and action == 'send':
			try:
				spell1 = gtkspell.Spell(self.conversation_textview.tv)
				spell2 = gtkspell.Spell(self.message_textview)
				lang = gajim.config.get('speller_language')
				if lang:
					spell1.set_language(lang)
					spell2.set_language(lang)
			except gobject.GError, msg:
				AspellDictError(lang)

		self.prepare_widgets_for(self.action)

		gajim.events.event_added_subscribe(self.on_event_added)
		gajim.events.event_removed_subscribe(self.on_event_removed)
		if self.action == 'receive':
			self.update_next_count()

		# set_text(None) raises TypeError exception
		if self.subject is None:
			self.subject = ''
		self.subject_entry.set_text(self.subject)


		if to == '':
			liststore = gtkgui_helpers.get_completion_liststore(self.to_entry)
			self.completion_dict = helpers.get_contact_dict_for_account(account)
			keys = self.completion_dict.keys()
			keys.sort()
			for jid in keys:
				contact = self.completion_dict[jid]
				img = gajim.interface.roster.jabber_state_images['16'][
						contact.show]
				liststore.append((img.get_pixbuf(), jid))
		else:
			self.completion_dict = {}
		self.xml.signal_autoconnect(self)

		if gajim.config.get('saveposition'):
			# get window position and size from config
			# Makes absolutely no sense when dealing with multiple windows
			# (for example when hitting "reply" the orig window stays)
			#gtkgui_helpers.move_window(self.window,
			#	gajim.config.get('single-msg-x-position'),
			#	gajim.config.get('single-msg-y-position'))
			gtkgui_helpers.resize_window(self.window,
				gajim.config.get('single-msg-width'),
				gajim.config.get('single-msg-height'))
		self.window.show_all()

	def on_single_message_window_destroy(self, widget):
		pass

	def set_cursor_to_end(self):
			end_iter = self.message_tv_buffer.get_end_iter()
			self.message_tv_buffer.place_cursor(end_iter)

	def save_pos(self):
		if gajim.config.get('saveposition'):
			# save the window size and position
			x, y = self.window.get_position()
			gajim.config.set('single-msg-x-position', x)
			gajim.config.set('single-msg-y-position', y)
			width, height = self.window.get_size()
			gajim.config.set('single-msg-width', width)
			gajim.config.set('single-msg-height', height)
			gajim.interface.save_config()

	def on_single_message_window_delete_event(self, window, ev):
		self.save_pos()

	def prepare_widgets_for(self, action):
		if len(gajim.connections) > 1:
			if action == 'send':
				title = _('Single Message using account %s') % self.account
			else:
				title = _('Single Message in account %s') % self.account
		else:
			title = _('Single Message')

		if action == 'send': # prepare UI for Sending
			title = _('Send %s') % title
			self.send_button.show()
			self.send_and_close_button.show()
			self.to_label.show()
			self.to_entry.show()
			self.to_status_image.show()
			self.to_name.show()
			self.reply_button.hide()
			self.quote_button.hide()
			self.next_button.hide()
			self.from_label.hide()
			self.from_entry.hide()
			self.from_status_image.hide()
			self.from_name.hide()
			self.conversation_scrolledwindow.hide()
			self.message_scrolledwindow.show()
			self.gpg_togglebutton.show()
			if type(self.to) == type([]):
				self.gpg_togglebutton.set_property('sensitive', False)
				self.gpg_togglebutton.set_active(False)
			else:
				self.gpg_togglebutton.set_property('sensitive', True)
				self.gpg_togglebutton.set_active(self.encrypted)
			self.gpg_togglebutton_separator.show()

			if self.message: # we come from a reply?
				self.message_textview.grab_focus()
				self.cancel_button.hide()
				self.close_button.show()
				self.message_tv_buffer.set_text(self.message)
				gobject.idle_add(self.set_cursor_to_end)
			else: # we write a new message (not from reply)
				self.close_button.hide()
				if self.to: # do we already have jid?
					# Most of the time users skip the subject
					#self.subject_entry.grab_focus()
					self.message_textview.grab_focus()
				else:
					self.to_entry.grab_focus()
			self.update_to_information()

		elif action == 'receive': # prepare UI for Receiving
			title = _('Received %s') % title
			self.reply_button.show()
			self.quote_button.show()
			self.next_button.show()
			self.from_label.show()
			self.from_entry.show()
			self.from_status_image.show()
			self.from_name.show()
			self.send_button.hide()
			self.send_and_close_button.hide()
			self.to_label.hide()
			self.to_entry.hide()
			self.to_status_image.hide()
			self.to_name.hide()
			self.conversation_scrolledwindow.show()
			self.message_scrolledwindow.hide()
			self.gpg_togglebutton.show()
			self.gpg_togglebutton.set_active(self.encrypted)
			self.gpg_togglebutton_separator.show()

			if self.message:
				self.conversation_textview.print_real_text(self.message)
			fjid = self.from_whom 
			if self.resource:
				fjid += '/' + self.resource # Full jid of sender (with resource)
			self.from_entry.set_text(fjid)
			self.from_entry.set_property('editable', False)
			self.subject_entry.set_property('editable', False)
			self.reply_button.grab_focus()
			self.cancel_button.hide()
			self.close_button.show()
			self.update_from_information()
			
		elif action == 'form': # prepare UI for Receiving
			title = _('Form %s') % title 
			self.send_button.show() 
			self.send_and_close_button.show() 
			self.to_label.show() 
			self.to_entry.show() 
			self.to_status_image.show()
			self.to_name.show()
			self.reply_button.hide() 
			self.from_label.hide() 
			self.from_entry.hide() 
			self.from_status_image.hide()
			self.from_name.hide()
			self.conversation_scrolledwindow.hide() 
			self.message_scrolledwindow.hide() 
			self.gpg_togglebutton.hide()
			self.gpg_togglebutton_separator.hide()
			self.update_to_information()

		self.window.set_title(title)

	def on_to_entry_changed(self, widget):
		self.update_to_information()

	def update_to_information(self):
		jid, resource, contact = self.get_jid_resource_and_contact()
		if contact:
			if contact.keyID:
				self.gpg_togglebutton.set_property('sensitive', True)
			else:
				self.gpg_togglebutton.set_property('sensitive', False)
			self.to_status_image.show()
			roster = gajim.interface.roster
			show = contact.show
			img = roster.get_appropriate_state_images(jid, icon_name=show)
			status_image = img[show]
			if status_image.get_storage_type() == gtk.IMAGE_ANIMATION:
				self.to_status_image.set_from_animation(status_image.get_animation())
			else:
				pix = status_image.get_pixbuf()
				if pix is not None:
					self.to_status_image.set_from_pixbuf(pix)
			self.to_name.show()
			self.to_name.set_text(contact.get_shown_name())
		else:
			self.to_status_image.hide()
			self.to_name.hide()

	def update_from_information(self):
		jid = self.from_whom
		contact = None
		if '@' in jid:
			if '/' in jid:
				jid, resource = jid.split('/', 1)
			else:
				resource = self.resource
			contact = gajim.contacts.get_contact(self.account, jid, resource)
		if contact:
			if contact.keyID:
				self.gpg_togglebutton.set_property('sensitive', True)
			else:
				self.gpg_togglebutton.set_property('sensitive', False)
			self.from_status_image.show()
			roster = gajim.interface.roster
			show = contact.show
			img = roster.get_appropriate_state_images(jid, icon_name=show)
			status_image = img[show]
			if status_image.get_storage_type() == gtk.IMAGE_ANIMATION:
				self.from_status_image.set_from_animation(status_image.get_animation())
			else:
				pix = status_image.get_pixbuf()
				if pix is not None:
					self.from_status_image.set_from_pixbuf(pix)
			self.from_name.show()
			self.from_name.set_text(contact.get_shown_name())
		else:
			self.from_status_image.hide()
			self.from_name.hide()

	def on_actions_button_clicked(self, widget):
		'''popup action menu'''
		menu = self.prepare_context_menu()
		menu.show_all()
		gtkgui_helpers.popup_emoticons_under_button(menu, widget, self.window.window)

	def get_jid_and_resource(self):
		if self.action == 'receive':
			jid = self.from_whom
		elif self.action == 'send':
			jid = self.to_entry.get_text()
		else:
			jid = self.to
		if '/' in jid:
			jid, resource = jid.split('/', 1)
		else:
			resource = self.resource
		return jid, resource

	def get_contact(self):
		jid, resource = self.get_jid_and_resource()
		if '@' in jid:
			return gajim.contacts.get_contact(self.account, jid, self.resource)
		else:
			return None

	def get_jid_resource_and_contact(self):
		jid, resource = self.get_jid_and_resource()
		if '@' in jid:
			return jid, resource, gajim.contacts.get_contact(self.account, jid, self.resource)
		else:
			return jid, resource, None

	def prepare_context_menu(self):
		'''sets compact view menuitem active state
		sets active and sensitivity state for toggle_gpg_menuitem
		sets sensitivity for history_menuitem (False for transports)
		and file_transfer_menuitem
		and hide()/show() for add_to_roster_menuitem
		'''
		xml = gtkgui_helpers.get_glade('chat_control_popup_menu.glade')
		menu = xml.get_widget('chat_control_popup_menu')

		history_menuitem = xml.get_widget('history_menuitem')
		toggle_gpg_menuitem = xml.get_widget('toggle_gpg_menuitem')
		toggle_e2e_menuitem = xml.get_widget('toggle_e2e_menuitem')
		add_to_roster_menuitem = xml.get_widget('add_to_roster_menuitem')
		send_file_menuitem = xml.get_widget('send_file_menuitem')
		information_menuitem = xml.get_widget('information_menuitem')
		convert_to_gc_menuitem = xml.get_widget('convert_to_groupchat')
		muc_icon = gajim.interface.roster.load_icon('muc_active')
		if muc_icon:
			convert_to_gc_menuitem.set_image(muc_icon) 

		jid, resource, contact = self.get_jid_resource_and_contact()

		# check if gpg capabitlies or else make gpg toggle insensitive
		gpg_btn = self.gpg_togglebutton
		isactive = gpg_btn.get_active()
		is_sensitive = gpg_btn.get_property('sensitive')
		toggle_gpg_menuitem.set_active(isactive)
		toggle_gpg_menuitem.set_property('sensitive', is_sensitive)

		# TODO: support this, if possible
		toggle_e2e_menuitem.set_sensitive(False)

		# If we don't have resource, we can't do file transfer
		# in transports, contact holds our info we need to disable it too
		if jid and resource:
			send_file_menuitem.set_sensitive(True)
		elif contact and contact.resource and contact.jid.find('@') != -1:
			send_file_menuitem.set_sensitive(True)
		else:
			send_file_menuitem.set_sensitive(False)

		# check if it's possible to convert to groupchat
		if gajim.get_transport_name_from_jid(jid) or \
		gajim.connections[self.account].is_zeroconf:
			convert_to_gc_menuitem.set_sensitive(False)

		# add_to_roster_menuitem
		if contact and _('Not in Roster') in contact.groups:
			add_to_roster_menuitem.show()
			add_to_roster_menuitem.set_no_show_all(False)
		else:
			add_to_roster_menuitem.hide()
			add_to_roster_menuitem.set_no_show_all(True)

		# connect signals
		history_menuitem.connect('activate', 
			self.on_history_menuitem_activate)
		send_file_menuitem.connect('activate', 
			self.on_send_file_menuitem_activate)
		add_to_roster_menuitem.connect('activate', 
			self.on_add_to_roster_menuitem_activate)
		toggle_gpg_menuitem.connect('activate', 
			self.on_toggle_gpg_menuitem_activate)
		#toggle_e2e_menuitem.connect('activate', 
		#	self.on_toggle_e2e_menuitem_activate)
		information_menuitem.connect('activate', 
			self.on_contact_information_menuitem_activate)
		convert_to_gc_menuitem.connect('activate',
			self.on_convert_to_gc_menuitem_activate)
		menu.connect('selection-done', self.destroy_menu)
		return menu

	def destroy_menu(self, menu):
		# destroy menu
		menu.destroy()

	def on_history_menuitem_activate(self, widget):
		'''When history menuitem is pressed: call history window'''
		import history_window
		jid, resource = self.get_jid_and_resource()

		if gajim.interface.instances.has_key('logs'):
			gajim.interface.instances['logs'].window.present()
			gajim.interface.instances['logs'].open_history(jid, self.account)
		else:
			gajim.interface.instances['logs'] = \
				history_window.HistoryWindow(jid, self.account)

	def on_send_file_menuitem_activate(self, widget):
		contact = self.get_contact()
		if contact:
			gajim.interface.instances['file_transfers'].show_file_send_request( 
				self.account, contact)

	def on_add_to_roster_menuitem_activate(self, widget):
		jid, resource = self.get_jid_and_resource()
		AddNewContactWindow(self.account, jid)

	def on_toggle_gpg_menuitem_activate(self, widget):
		if self.gpg_togglebutton.get_active():
			self.gpg_togglebutton.set_active(False)
		else:
			self.gpg_togglebutton.set_active(True)
		self.gpg_togglebutton.toggled()

	def on_gpg_togglebutton_toggled(self, widget):
		self.encrypted = self.gpg_togglebutton.get_active()
		contact = self.get_contact()
		if contact: # only save if we have a valid contact
			gajim.config.set_per('contacts', contact.jid, 'gpg_enabled',
				self.encrypted)

	def on_contact_information_menuitem_activate(self, widget):
		contact = self.get_contact()
		if contact:
			gajim.interface.roster.on_info(widget, contact, self.account)

	def on_convert_to_gc_menuitem_activate(self, widget):
		'''user want to invite some friends to chat'''
		jid, resource = self.get_jid_and_resource()
		TransformChatToMUC(self.account, [jid])

	def on_single_message_window_destroy(self, widget):
		gajim.events.event_added_unsubscribe(self.on_event_added)
		gajim.events.event_removed_unsubscribe(self.on_event_removed)

	def update_next_count(self):
		# gajim.get_jid_without_resource(self.from_jid)?
		self.next_count = len(gajim.events.get_events(self.account, \
			self.from_whom, types=('normal',)))
		self.next_count_label.set_label("(%d)" % self.next_count)
		if self.next_count == 0:
			self.next_button.set_property('sensitive', False)
		else:
			self.next_button.set_property('sensitive', True)

	def on_event_added(self, event):
		if event.type_ == 'normal':
			self.update_next_count()

	def on_event_removed(self, event_list):
		for event in event_list:
			if event.type_ == 'normal':
				self.update_next_count()
				return

	def on_next_button_clicked(self, widget):
		if self.next_count == 0:
			return
		next_event = gajim.events.get_first_event(self.account, self.from_whom, 'normal')
		#if not next_event:
		#	next_event = gajim.events.get_first_event(self.account, self.from_whom, 'chat')
		if not next_event:
			return
		# parameters:
		# message, subject, kind, time, encrypted, resource,
		# msg_id
		self.action = 'receive'
		self.subject = next_event.parameters[1]
		self.message = next_event.parameters[0]
		self.resource = next_event.parameters[5]
		self.session = next_event.parameters[8]
		form_node = next_event.parameters[9]
		
		parent_box = self.xml.get_widget('conversation_scrolledwindow').get_parent()
		if form_node:
			dataform = dataforms.ExtendForm(node = form_node)
			self.form_widget = dataforms_widget.DataFormWidget(dataform)
			self.form_widget.show_all()
			parent_box.add(self.form_widget)
			parent_box.child_set_property(self.form_widget, 'position',
				parent_box.child_get_property(self.xml.get_widget('conversation_scrolledwindow'), 'position'))
			self.action = 'form'
		elif self.form_widget:
			self.form_widget.hide()
			parent_box.remove(self.form_widget)
			self.form_widget = None

		self.conversation_textview.clear()
		self.prepare_widgets_for(self.action)

		# set_text(None) raises TypeError exception
		if self.subject is None:
			self.subject = ''
		self.subject_entry.set_text(self.subject)

		gajim.interface.remove_first_event(self.account, self.from_whom, next_event.type_)
		self.update_next_count()

	def on_cancel_button_clicked(self, widget):
		self.save_pos()
		self.window.destroy()

	def on_close_button_clicked(self, widget):
		self.save_pos()
		self.window.destroy()

	def update_char_counter(self, widget):
		characters_no = self.message_tv_buffer.get_char_count()
		self.count_chars_label.set_text(unicode(characters_no))

	def send_single_message(self):
		if gajim.connections[self.account].connected <= 1:
			# if offline or connecting
			ErrorDialog(_('Connection not available'),
		_('Please make sure you are connected with "%s".') % self.account)
			return
		if type(self.to) == type([]):
			sender_list = [i[0].jid + '/' + i[0].resource for i in self.to]
		else:
			sender_list = [self.to_entry.get_text().decode('utf-8')]

		for to_whom_jid in sender_list:
			if self.completion_dict.has_key(to_whom_jid):
				to_whom_jid = self.completion_dict[to_whom_jid].jid
			subject = self.subject_entry.get_text().decode('utf-8')
			begin, end = self.message_tv_buffer.get_bounds()
			message = self.message_tv_buffer.get_text(begin, end).decode('utf-8')

			if to_whom_jid.find('/announce/') != -1:
				gajim.connections[self.account].send_motd(to_whom_jid, subject,
					message)
				return

			if self.session:
				session = self.session
			else:
				session = gajim.connections[self.account].make_new_session(to_whom_jid)

			if self.form_widget:
				form_node = self.form_widget.data_form
			else:
				form_node = None
			keyID = None
			if self.encrypted:
				contact = self.get_contact()
				keyID = contact.keyID
			gajim.connections[self.account].send_message(to_whom_jid, message,
				keyID=keyID, type='normal', subject=subject, session=session,
				form_node=form_node)

		self.subject_entry.set_text('') # we sent ok, clear the subject
		self.message_tv_buffer.set_text('') # we sent ok, clear the textview

	def on_send_button_clicked(self, widget):
		self.send_single_message()
	
	def on_child_window_destroy(self, widget):
		# TODO: Only close window if child send a message
		if self.next_count == 0:
			self.save_pos()
			self.window.destroy()

	def on_reply_button_clicked(self, widget, quote=False):
		# we create a new blank window to send and we preset RE: and to jid
		if self.subject:
			subject = _('RE: %s') % self.subject
		else:
			subject = ''
		if quote:
			message = _('%s wrote:\n') % self.from_whom + self.message
			# add > at the begining of each line
			message = message.replace('\n', '\n> ') + '\n\n'
		else:
			message = ''
		smw = SingleMessageWindow(self.account, to = self.from_whom,
			action = 'send',	from_whom = self.from_whom, subject = subject,
			message = message, session = self.session,
			encrypted=self.encrypted, resource=self.resource)
		smw.window.connect('destroy',
			self.on_child_window_destroy)

	def on_quote_button_clicked(self, widget):
		self.on_reply_button_clicked(widget, quote=True)

	def on_send_and_close_button_clicked(self, widget):
		self.send_single_message()
		self.save_pos()
		self.window.destroy()

	def on_single_message_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.save_pos()
			self.window.destroy()
