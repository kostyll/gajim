##	dialogs.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
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

from vcard import VcardWindow
from gajim_themes_window import GajimThemesWindow
from advanced import AdvancedConfigurationWindow
from gajim import User
from common import gajim
from common import helpers
from common import i18n
from common import helpers

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

GTKGUI_GLADE = 'gtkgui.glade'

class EditGroupsDialog:
	'''Class for the edit group dialog window'''
	def __init__(self, user, account, plugin):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'edit_groups_dialog', APP)
		self.dialog = self.xml.get_widget('edit_groups_dialog')
		self.plugin = plugin
		self.account = account
		self.user = user
		self.changes_made = False
		self.list = self.xml.get_widget('groups_treeview')
		self.xml.get_widget('nickname_label').set_markup(
			_("Contact's name: <i>%s</i>") % user.name)
		self.xml.get_widget('jid_label').set_markup(
			_('JID: <i>%s</i>') % user.jid)
		self.xml.signal_autoconnect(self)
		self.dialog.show_all()
		self.init_list()

	def run(self):
		self.dialog.run()
		self.dialog.destroy()
		if self.changes_made:
			gajim.connections[self.account].update_user(self.user.jid,
				self.user.name, self.user.groups)

	def update_user(self):
		self.plugin.roster.remove_user(self.user, self.account)
		self.plugin.roster.add_user_to_roster(self.user.jid, self.account)

	def on_add_button_clicked(self, widget):
		group = self.xml.get_widget('group_entry').get_text()
		if not group:
			return
		# check if it already exists
		model = self.list.get_model()
		iter = model.get_iter_root()
		while iter:
			if model.get_value(iter, 0) == group:
				return
			iter = model.iter_next(iter)
		self.changes_made = True
		model.append((group, True))
		self.user.groups.append(group)
		self.update_user()

	def group_toggled_cb(self, cell, path):
		self.changes_made = True
		model = self.list.get_model()
		if model[path][1] and len(self.user.groups) == 1: # we try to remove 
																		  # the last group
			ErrorDialog(_("Can't remove last group"),
					_('At least one contact group must be present.')).get_response()
			return
		model[path][1] = not model[path][1]
		if model[path][1]:
			self.user.groups.append(model[path][0])
		else:
			self.user.groups.remove(model[path][0])
		self.update_user()

	def init_list(self):
		store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
		self.list.set_model(store)
		for g in self.plugin.roster.groups[self.account].keys():
			if g in ['Transports', 'not in the roster']:
				continue
			iter = store.append()
			store.set(iter, 0, g)
			if g in self.user.groups:
				store.set(iter, 1, True)
			else:
				store.set(iter, 1, False)
		column = gtk.TreeViewColumn(_('Group'))
		self.list.append_column(column)
		renderer = gtk.CellRendererText()
		column.pack_start(renderer)
		column.set_attributes(renderer, text = 0)
		
		column = gtk.TreeViewColumn(_('In the group'))
		self.list.append_column(column)
		renderer = gtk.CellRendererToggle()
		column.pack_start(renderer)
		renderer.set_property('activatable', True)
		renderer.connect('toggled', self.group_toggled_cb)
		column.set_attributes(renderer, active = 1)

class PassphraseDialog:
	'''Class for Passphrase dialog'''
	def run(self):
		'''Wait for OK button to be pressed and return passphrase/password'''
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			passphrase = self.passphrase_entry.get_text()
		else:
			passphrase = -1
		save_passphrase_checkbutton = self.xml.\
			get_widget('save_passphrase_checkbutton')
		self.window.destroy()
		return passphrase, save_passphrase_checkbutton.get_active()

	def __init__(self, titletext, labeltext, checkbuttontext):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'passphrase_dialog', APP)
		self.window = self.xml.get_widget('passphrase_dialog')
		self.passphrase_entry = self.xml.get_widget('passphrase_entry')
		self.passphrase = -1
		self.window.set_title(titletext)
		self.xml.get_widget('message_label').set_text(labeltext)
		self.xml.get_widget('save_passphrase_checkbutton').set_label(checkbuttontext)
		self.xml.signal_autoconnect(self)
		self.window.show_all()

class ChooseGPGKeyDialog:
	'''Class for GPG key dialog'''
	def run(self):
		'''Wait for Ok button to be pressed and return the selected key'''
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			selection = self.keys_treeview.get_selection()
			(model, iter) = selection.get_selected()
			keyID = [model.get_value(iter, 0), model.get_value(iter, 1)]
		else:
			keyID = -1
		self.window.destroy()
		return keyID

	def fill_tree(self, list, selected):
		model = self.keys_treeview.get_model()
		for keyID in list.keys():
			iter = model.append((keyID, list[keyID]))
			if keyID == selected:
				path = model.get_path(iter)
				self.keys_treeview.set_cursor(path)
	
	def __init__(self, title_text, prompt_text, secret_keys, selected = None):
		#list : {keyID: userName, ...}
		xml = gtk.glade.XML(GTKGUI_GLADE, 'choose_gpg_key_dialog', APP)
		self.window = xml.get_widget('choose_gpg_key_dialog')
		self.window.set_title(title_text)
		self.keys_treeview = xml.get_widget('keys_treeview')
		prompt_label = xml.get_widget('prompt_label')
		prompt_label.set_text(prompt_text)
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.keys_treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		self.keys_treeview.insert_column_with_attributes(-1, _('KeyID'),
			renderer, text = 0)
		renderer = gtk.CellRendererText()
		self.keys_treeview.insert_column_with_attributes(-1, _('User name'),
			renderer, text = 1)
		self.fill_tree(secret_keys, selected)

		self.window.show_all()

class ChangeStatusMessageDialog:
	def __init__(self, plugin, show):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'change_status_message_dialog', APP)
		self.window = self.xml.get_widget('change_status_message_dialog')
		uf_show = helpers.get_uf_show(show)
		self.window.set_title(_('%s Status Message') % uf_show)
		
		message_textview = self.xml.get_widget('message_textview')
		self.message_buffer = message_textview.get_buffer()
		self.message_buffer.set_text(gajim.config.get('last_status_msg'))
		self.values = {'':''} # have an empty string selectable, so user can clear msg
		for msg in gajim.config.get_per('statusmsg'):
			self.values[msg] = gajim.config.get_per('statusmsg', msg, 'message')
		sorted_keys_list = helpers.get_sorted_keys(self.values)
		liststore = gtk.ListStore(str, str)
		message_comboboxentry = self.xml.get_widget('message_comboboxentry')
		message_comboboxentry.set_model(liststore)
		message_comboboxentry.set_text_column(0)
		for val in sorted_keys_list:
			message_comboboxentry.append_text(val)
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def run(self):
		'''Wait for OK button to be pressed and return status messsage'''
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			beg, end = self.message_buffer.get_bounds()
			message = self.message_buffer.get_text(beg, end, 0).strip()
			#FIXME: support more than one line
			gajim.config.set('last_status_msg', message)
		else:
			message = -1
		self.window.destroy()
		return message

	def on_message_comboboxentry_changed(self, widget, data = None):
		model = widget.get_model()
		active = widget.get_active()
		if active < 0:
			return None
		name = model[active][0]
		self.message_buffer.set_text(self.values[name])
	
	def on_change_status_message_dialog_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Return or \
		event.keyval == gtk.keysyms.KP_Enter:  # catch CTRL+ENTER
			if (event.state & gtk.gdk.CONTROL_MASK):
				self.window.response(gtk.RESPONSE_OK)

class AddNewContactWindow:
	'''Class for AddNewContactWindow'''
	def __init__(self, plugin, account, jid = None):
		if gajim.connections[account].connected < 2:
			ErrorDialog(_('You are not connected to the server.'), \
					_('Without a connection, you can not add a contact')).get_response()
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'add_new_contact_window', APP)
		self.window = self.xml.get_widget('add_new_contact_window')
		self.uid_entry = self.xml.get_widget('uid_entry')
		self.protocol_combobox = self.xml.get_widget('protocol_combobox')
		self.jid_entry = self.xml.get_widget('jid_entry')
		self.nickname_entry = self.xml.get_widget('nickname_entry')
		self.xml.get_widget('title_label').set_text('Fill in the data for the contact you want to add in contact ' + account)
		self.old_uid_value = ''
		liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		liststore.append(['Jabber', ''])
		self.agents = ['Jabber']
		jid_agents = []
		for j in self.plugin.roster.contacts[account]:
			user = self.plugin.roster.contacts[account][j][0]
			if 'Transports' in user.groups and user.show != 'offline' and \
					user.show != 'error':
				jid_agents.append(j)
		for a in jid_agents:
			if a.find('aim') > -1:
				name = 'AIM'
			elif a.find('icq') > -1:
				name = 'ICQ'
			elif a.find('msn') > -1:
				name = 'MSN'
			elif a.find('yahoo') > -1:
				name = 'Yahoo!'
			else:
				name = a
			iter = liststore.append([name, a])
			self.agents.append(name)
		
		self.protocol_combobox.set_model(liststore)
		self.protocol_combobox.set_active(0)
		self.fill_jid()
		if jid:
			self.jid_entry.set_text(jid)
			jid_splited = jid.split('@')
			if jid_splited[1] in jid_agents:
				uid = jid_splited[0].replace('%', '@')
				self.uid_entry.set_text(uid)
				self.protocol_combobox.set_active(jid_agents.index(jid_splited[1]) + 1)
			else:
				self.uid_entry.set_text(jid)
				self.protocol_combobox.set_active(0)
			self.set_nickname()

		self.group_comboboxentry = self.xml.get_widget('group_comboboxentry')
		liststore = gtk.ListStore(str)
		self.group_comboboxentry.set_model(liststore)
		for g in self.plugin.roster.groups[account].keys():
			if g != 'not in the roster' and g != 'Transports':
				self.group_comboboxentry.append_text(g)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_add_new_contact_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.window.destroy()

	def on_cancel_button_clicked(self, widget):
		'''When Cancel button is clicked'''
		self.window.destroy()

	def on_subscribe_button_clicked(self, widget):
		'''When Subscribe button is clicked'''
		jid = self.jid_entry.get_text()
		nickname = self.nickname_entry.get_text()
		if not jid:
			return
		if jid.find('@') < 0:
			ErrorDialog(_("Invalid user name"),
_('User names must be of the form "user@servername".')).get_response()
			return
		message_buffer = self.xml.get_widget('message_textview').get_buffer()
		start_iter = message_buffer.get_start_iter()
		end_iter = message_buffer.get_end_iter()
		message = message_buffer.get_text(start_iter, end_iter, 0)
		group = self.group_comboboxentry.child.get_text()
		self.plugin.roster.req_sub(self, jid, message, self.account, group,
			nickname)
		if self.xml.get_widget('auto_authorize_checkbutton').get_active():
			gajim.connections[self.account].send_authorization(jid)
		self.window.destroy()
		
	def fill_jid(self):
		model = self.protocol_combobox.get_model()
		index = self.protocol_combobox.get_active()
		jid = self.uid_entry.get_text().strip()
		if index > 0: # it's not jabber but a transport
			jid = jid.replace('@', '%')
		agent = model[index][1]
		if agent:
			jid += '@' + agent
		self.jid_entry.set_text(jid)

	def on_protocol_combobox_changed(self, widget):
		self.fill_jid()

	def guess_agent(self):
		uid = self.uid_entry.get_text()
		model = self.protocol_combobox.get_model()
		
		#If login contains only numbers, it's probably an ICQ number
		if uid.isdigit():
			if 'ICQ' in self.agents:
				self.protocol_combobox.set_active(self.agents.index('ICQ'))
				return

	def set_nickname(self):
		uid = self.uid_entry.get_text()
		nickname = self.nickname_entry.get_text()
		if nickname == self.old_uid_value:
			self.nickname_entry.set_text(uid.split('@')[0])
			
	def on_uid_entry_changed(self, widget):
		uid = self.uid_entry.get_text()
		self.guess_agent()
		self.set_nickname()
		self.fill_jid()
		self.old_uid_value = uid.split('@')[0]

class AboutDialog:
	'''Class for about dialog'''
	def __init__(self):
		if gtk.pygtk_version < (2, 6, 0) or gtk.gtk_version < (2, 6, 0):
			InformationDialog(_('Gajim - a GTK+ Jabber client'),
				_('Version %s') % gajim.version).get_response()
			return

		dlg = gtk.AboutDialog()
		dlg.set_name('Gajim')
		dlg.set_version(gajim.version)
		s = u'Copyright \xa9 2003-2005 Gajim Team'
		dlg.set_copyright(s)
		text = open('../COPYING').read()
		dlg.set_license(text)

		dlg.set_comments(_('A GTK jabber client'))
		dlg.set_website('http://www.gajim.org')

		authors = ['Yann Le Boulanger <asterix@lagaule.org>', 'Vincent Hanquez <tab@snarc.org>', 'Nikos Kouremenos <kourem@gmail.com>', 'Alex Podaras <bigpod@gmail.com>', 'Gajim patchers <http://www.gajim.org/dev.php>']
		dlg.set_authors(authors)

		pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(gajim.DATA_DIR, 'pixmaps/gajim_about.png'))			

		dlg.set_logo(pixbuf)
		dlg.set_translator_credits(_('translator_credits'))

		rep = dlg.run()
		dlg.destroy()

class Dialog(gtk.Dialog):
	def __init__(self, parent, title, buttons, default = None):
		gtk.Dialog.__init__(self, title, parent, gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL | gtk.DIALOG_NO_SEPARATOR)

		self.set_border_width(6)
		self.vbox.set_spacing(12)
		self.set_resizable(False)

		for stock, response in buttons:
			self.add_button(stock, response)

		if default is not None:
			self.set_default_response(default)
		else:
			self.set_default_response(buttons[-1][1])

	def get_button(self, index):
		buttons = self.action_area.get_children()
		return index < len(buttons) and buttons[index] or None


class HigDialog(Dialog):
	def __init__(self, parent, pritext, sectext, stockimage, buttons, default = None):
		"""GNOME higified version of the Dialog object. Inherit
		from here if possible when you need a new dialog."""
		Dialog.__init__(self, parent, "", buttons, default)

		# hbox separating dialog image and contents
		hbox = gtk.HBox()
		hbox.set_spacing(12)
		hbox.set_border_width(6)
		self.vbox.pack_start(hbox)

		# set up image
		if stockimage is not None:
			image = gtk.Image()
			image.set_from_stock(stockimage, gtk.ICON_SIZE_DIALOG)
			image.set_alignment(0.5, 0)
			hbox.pack_start(image, False, False)

		# set up main content area
		self.contents = gtk.VBox()
		self.contents.set_spacing(10)
		hbox.pack_start(self.contents)

		label = gtk.Label()
		label.set_markup("<span size=\"larger\" weight=\"bold\">" + pritext + "</span>\n\n" + sectext)
		label.set_line_wrap(True)
		label.set_alignment(0, 0)
		label.set_selectable(True)
		self.contents.pack_start(label)

	def get_response(self):
		self.show_all()
		response = gtk.Dialog.run(self)
		self.destroy()
		return response

class ConfirmationDialog(HigDialog):
	"""HIG compliant confirmation dialog."""
	def __init__(self, pritext, sectext=''):
		HigDialog.__init__(self, None, pritext, sectext,
			gtk.STOCK_DIALOG_WARNING, [ [gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL],
			[ gtk.STOCK_OK, gtk.RESPONSE_OK ] ])

class WarningDialog(HigDialog):
	def __init__(self, pritext, sectext=''):
		"""HIG compliant warning dialog."""
		HigDialog.__init__(
			self, None, pritext, sectext, gtk.STOCK_DIALOG_WARNING,
			[ [ gtk.STOCK_OK, gtk.RESPONSE_OK ] ]
		)

class InformationDialog(HigDialog):
	def __init__(self, pritext, sectext=''):
		"""HIG compliant info dialog."""
		HigDialog.__init__(
			self, None, pritext, sectext, gtk.STOCK_DIALOG_INFO,
			[ [ gtk.STOCK_OK, gtk.RESPONSE_OK ] ]
		)

class InputDialog:
	'''Class for Input dialog'''
	def __init__(self, title, label_str, input_str = None):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'input_dialog', APP)
		self.dialog = xml.get_widget('input_dialog')
		label = xml.get_widget('label')
		self.input_entry = xml.get_widget('input_entry')
		self.dialog.set_title(title)
		label.set_text(label_str)
		if input_str:
			self.input_entry.set_text(input_str)
			self.input_entry.select_region(0, -1) # select all	
	
class ErrorDialog(HigDialog):
	def __init__(self, pritext, sectext=''):
		"""HIG compliant error dialog."""
		HigDialog.__init__(
			self, None, pritext, sectext, gtk.STOCK_DIALOG_ERROR,
			[ [ gtk.STOCK_OK, gtk.RESPONSE_OK ] ]
		)


class SubscriptionRequestWindow:
	def __init__(self, plugin, jid, text, account):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'subscription_request_window', APP)
		self.window = xml.get_widget('subscription_request_window')
		self.plugin = plugin
		self.jid = jid
		self.account = account
		xml.get_widget('from_label').set_text(
			_('Subscription request for account %s from %s') % (account, self.jid))
		xml.get_widget('message_textview').get_buffer().set_text(text)
		xml.signal_autoconnect(self)
		self.window.show_all()

	def on_close_button_clicked(self, widget):
		self.window.destroy()
		
	def on_authorize_button_clicked(self, widget):
		'''accept the request'''
		gajim.connections[self.account].send_authorization(self.jid)
		self.window.destroy()
		if not self.plugin.roster.contacts[self.account].has_key(self.jid):
			AddNewContactWindow(self.plugin, self.account, self.jid)

	def on_contact_info_button_clicked(self, widget):
		'''ask vcard'''
		if self.plugin.windows[self.account]['infos'].has_key(self.jid):
			self.plugin.windows[self.account]['infos'][self.jid].window.present()
		else:
			self.plugin.windows[self.account]['infos'][self.jid] = \
				VcardWindow(self.jid, self.plugin, self.account, True)
			#remove the publish / retrieve buttons
			vcard_xml = self.plugin.windows[self.account]['infos'][self.jid].xml
			hbuttonbox = vcard_xml.get_widget('information_hbuttonbox')
			children = hbuttonbox.get_children()
			hbuttonbox.remove(children[0])
			hbuttonbox.remove(children[1])
			vcard_xml.get_widget('nickname_label').set_text(self.jid)
			gajim.connections[self.account].request_vcard(self.jid)
	
	def on_deny_button_clicked(self, widget):
		'''refuse the request'''
		gajim.connections[self.account].refuse_authorization(self.jid)
		self.window.destroy()

class JoinGroupchatWindow:
	def __init__(self, plugin, account, server = '', room = ''):
		self.plugin = plugin
		self.account = account
		if gajim.connections[account].connected < 2:
			ErrorDialog(_('You are not connected to the server'),
_('You can not join a group chat unless you are connected.')).get_response()
			raise RuntimeError, 'You must be connected to join a groupchat'

		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'join_groupchat_window', APP)
		self.window = self.xml.get_widget('join_groupchat_window')
		self.xml.get_widget('server_entry').set_text(server)
		self.xml.get_widget('room_entry').set_text(room)
		self.xml.get_widget('nickname_entry').set_text(
						self.plugin.nicks[self.account])
		self.xml.signal_autoconnect(self)
		self.plugin.windows[account]['join_gc'] = self #now add us to open windows
		our_jid = gajim.config.get_per('accounts', self.account, 'name') + '@' + \
			gajim.config.get_per('accounts', self.account, 'hostname')
		if len(gajim.connections) > 1:
			title = _('Join Groupchat as ') + our_jid
		else:
			title = _('Join Groupchat')
		self.window.set_title(title)

		self.recently_combobox = self.xml.get_widget('recently_combobox')
		liststore = gtk.ListStore(str)
		self.recently_combobox.set_model(liststore)
		cell = gtk.CellRendererText()
		self.recently_combobox.pack_start(cell, True)
		self.recently_combobox.add_attribute(cell, 'text', 0)
		self.recently_groupchat = gajim.config.get('recently_groupchat').split()
		for g in self.recently_groupchat:
			self.recently_combobox.append_text(g)
		if len(self.recently_groupchat):
			self.recently_combobox.set_active(0)
			self.xml.get_widget('room_entry').select_region(0, -1)

		self.window.show_all()

	def on_join_groupchat_window_destroy(self, widget):
		'''close window'''
		del self.plugin.windows[self.account]['join_gc'] # remove us from open windows

	def on_join_groupchat_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			widget.destroy()

	def on_recently_combobox_changed(self, widget):
		model = widget.get_model()
		iter = widget.get_active_iter()
		gid = model.get_value(iter, 0)
		self.xml.get_widget('room_entry').set_text(gid.split('@')[0])
		self.xml.get_widget('server_entry').set_text(gid.split('@')[1])

	def on_cancel_button_clicked(self, widget):
		'''When Cancel button is clicked'''
		self.window.destroy()

	def on_join_button_clicked(self, widget):
		'''When Join button is clicked'''
		nickname = self.xml.get_widget('nickname_entry').get_text()
		room = self.xml.get_widget('room_entry').get_text()
		server = self.xml.get_widget('server_entry').get_text()
		password = self.xml.get_widget('password_entry').get_text()
		jid = '%s@%s' % (room, server)
		if jid in self.recently_groupchat:
			self.recently_groupchat.remove(jid)
		self.recently_groupchat.insert(0, jid)
		if len(self.recently_groupchat) > 10:
			self.recently_groupchat = self.recently_groupchat[0:10]
		gajim.config.set('recently_groupchat', ' '.join(self.recently_groupchat))
		
		self.plugin.roster.join_gc_room(self.account, jid, nickname, password)

		self.window.destroy()

class NewMessageDialog:
	def __init__(self, plugin, account):
		if gajim.connections[account].connected < 2:
			ErrorDialog(_('You are not connected to the server'),
				_('Without a connection, you can not send messages.')).get_response()
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'new_message_dialog', APP)
		self.window = self.xml.get_widget('new_message_dialog')
		self.jid_entry = self.xml.get_widget('jid_entry')

		our_jid = gajim.config.get_per('accounts', self.account, 'name') + '@' + \
			gajim.config.get_per('accounts', self.account, 'hostname')
		if len(gajim.connections) > 1:
			title = _('New Message as ') + our_jid
		else:
			title = _('New Message')
		self.window.set_title(title)
		
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_cancel_button_clicked(self, widget):
		'''When Cancel button is clicked'''
		self.window.destroy()

	def on_chat_button_clicked(self, widget):
		'''When Chat button is clicked'''
		jid = self.jid_entry.get_text()
		if jid.find('@') == -1: # if no @ was given
			ErrorDialog(_('Invalid user ID'),
_('User ID must be of the form "username@servername".')).get_response()
			return
		self.window.destroy()
		# use User class, new_chat expects it that way
		# is it in the roster?
		if self.plugin.roster.contacts[self.account].has_key(jid):
			user = self.plugin.roster.contacts[self.account][jid][0]
		else:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', self.account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			user = User(jid, jid, ['not in the roster'], 'not in the roster',
				'not in the roster', 'none', None, '', 0, keyID)
			self.plugin.roster.contacts[self.account][jid] = [user]
			self.plugin.roster.add_user_to_roster(user.jid, self.account)			

		if not self.plugin.windows[self.account]['chats'].has_key(jid):
			self.plugin.roster.new_chat(user, self.account)
		self.plugin.windows[self.account]['chats'][jid].set_active_tab(jid)
		self.plugin.windows[self.account]['chats'][jid].window.present()

class ChangePasswordDialog:
	def __init__(self, plugin, account):
		if gajim.connections[account].connected < 2:
			ErrorDialog(_('You are not connected to the server'),
_('Without a connection, you can not change your password.')).get_response()
			return
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'change_password_dialog', APP)
		self.dialog = self.xml.get_widget('change_password_dialog')
		self.password1_entry = self.xml.get_widget('password1_entry')
		self.password2_entry = self.xml.get_widget('password2_entry')

		self.dialog.show_all()

	def run(self):
		'''Wait for OK button to be pressed and return new password'''
		end = False
		while not end:
			rep = self.dialog.run()
			if rep == gtk.RESPONSE_OK:
				password1 = self.password1_entry.get_text()
				if not password1:
					ErrorDialog(_('Invalid password.'), \
							_('You must enter a password.')).get_response()
					continue
				password2 = self.password2_entry.get_text()
				if password1 != password2:
					ErrorDialog(_("Passwords don't match."), \
							_('The passwords typed in both fields must be identical.')).get_response()
					continue
				message = password1
			else:
				message = -1
			end = True
		self.dialog.destroy()
		return message


class PopupNotificationWindow:
	def __init__(self, plugin, event_type, jid, account):
		self.plugin = plugin
		self.account = account
		self.jid = jid
		
		xml = gtk.glade.XML(GTKGUI_GLADE, 'popup_notification_window', APP)
		self.window = xml.get_widget('popup_notification_window')
		close_button = xml.get_widget('close_button')
		event_type_label = xml.get_widget('event_type_label')
		event_description_label = xml.get_widget('event_description_label')
		eventbox = xml.get_widget('eventbox')
		
		event_type_label.set_markup('<b>' + event_type + '</b>')

		if self.jid in self.plugin.roster.contacts[account]:
			txt = self.plugin.roster.contacts[account][self.jid][0].name
		else:
			txt = self.jid

		event_description_label.set_text(txt)
		
		# set colors [ http://www.w3schools.com/html/html_colornames.asp ]
		self.window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
		if event_type == _('Contact Signed In'):
			close_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('limegreen'))
			eventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('limegreen'))
		elif event_type == _('Contact Signed Out'):
			close_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('red'))
			eventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('red'))
		elif event_type == _('New Message'):
			close_button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('dodgerblue'))
			eventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('dodgerblue'))
			txt = _('From %s') % txt
	
		# position the window to bottom-right of screen
		window_width, self.window_height = self.window.get_size()
		self.plugin.roster.popups_notification_height += self.window_height
		self.window.move(gtk.gdk.screen_width() - window_width,
			gtk.gdk.screen_height() - self.plugin.roster.popups_notification_height)
		
		xml.signal_autoconnect(self)
		self.window.show_all()
		gobject.timeout_add(5000, self.on_timeout)

	def on_close_button_clicked(self, widget):
		self.adjust_height_and_move_popup_notification_windows()

	def on_timeout(self):
		self.adjust_height_and_move_popup_notification_windows()
		
	def adjust_height_and_move_popup_notification_windows(self):
		#remove
		self.plugin.roster.popups_notification_height -= self.window_height
		self.window.destroy()
		
		if len(self.plugin.roster.popup_notification_windows) > 0:
			# we want to remove the first window added in the list
			self.plugin.roster.popup_notification_windows.pop(0) # remove 1st item
		
		# move the rest of popup windows
		self.plugin.roster.popups_notification_height = 0
		for window_instance in self.plugin.roster.popup_notification_windows:
			window_width, window_height = window_instance.window.get_size()
			self.plugin.roster.popups_notification_height += window_height
			window_instance.window.move(gtk.gdk.screen_width() - window_width,
					gtk.gdk.screen_height() - self.plugin.roster.popups_notification_height)

	def on_popup_notification_window_button_press_event(self, widget, event):
		# use User class, new_chat expects it that way
		# is it in the roster?
		if self.plugin.roster.contacts[self.account].has_key(self.jid):
			user = self.plugin.roster.contacts[self.account][self.jid][0]
		else:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', self.account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			user = User(self.jid, self.jid, ['not in the roster'],
				'not in the roster', 'not in the roster', 'none', None, '', 0,
				keyID)
			self.plugin.roster.contacts[self.account][self.jid] = [user]
			self.plugin.roster.add_user_to_roster(user.self.jid, self.account)			

		self.plugin.roster.new_chat(user, self.account)
		chats_window = self.plugin.windows[self.account]['chats'][self.jid]
		chats_window.set_active_tab(self.jid)
		chats_window.window.present()
		self.adjust_height_and_move_popup_notification_windows()
