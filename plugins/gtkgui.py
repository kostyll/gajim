#!/usr/bin/env python
##	plugins/gtkgui.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@tuxfamily.org>
## 	- David Ferlier <david@yazzy.org>
##
##	Copyright (C) 2003 Gajim Team
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

import pygtk
pygtk.require('2.0')
import gtk
from gtk import TRUE, FALSE
import gtk.glade
import gobject
import string
import common.optparser
CONFPATH = "~/.gajimrc"
Wbrowser = 0

class user:
	def __init__(self, *args):
		if len(args) == 0:
			self.jid = ''
			self.name = ''
			self.groups = []
			self.show = ''
			self.status = ''
			self.sub == ''
		elif len(args) == 6:
			self.jid = args[0]
			self.name = args[1]
			self.groups = args[2]
			self.show = args[3]
			self.status = args[4]
			self.sub = args[5]
#		elif ((len(args)) and (type (args[0]) == type (self)) and
#			(self.__class__ == args[0].__class__)):
#			self.name = args[0].name
#			self.groups = args[0].groups
#			self.show = args[0].show
#			self.status = args[0].status
#			self.sub = args[0].sub
		else: raise TypeError, 'bad arguments'

class add:
	def delete_event(self, widget):
		self.Wadd.destroy()

	def on_subscribe(self, widget):
		who = self.xml.get_widget("entry_who").get_text()
		buf = self.xml.get_widget("textview_sub").get_buffer()
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		txt = buf.get_text(start_iter, end_iter, 0)
		self.r.req_sub(self, who, txt)
		self.delete_event(self)
		
	def __init__(self, roster, jid=None):
		self.r = roster
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Add')
		if jid:
			 self.xml.get_widget('entry_who').set_text(jid)
		self.Wadd = self.xml.get_widget("Add")
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_button_sub_clicked', self.on_subscribe)

class about:
	def delete_event(self, widget):
		self.Wabout.destroy()
		
	def __init__(self):
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'About')
		self.Wabout = self.xml.get_widget("About")
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)

class accounts:
	def delete_event(self, widget):
		self.window.destroy()
		
	def __init__(self):
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Accounts')
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)

class confirm:
	def delete_event(self, widget):
		self.window.destroy()
		
	def req_usub(self, widget):
		self.r.queueOUT.put(('UNSUB', self.jid))
		del self.r.l_contact[self.jid]
		self.r.treestore.remove(self.iter)
		self.delete_event(self)
	
	def __init__(self, roster, iter):
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Confirm')
		self.window = self.xml.get_widget('Confirm')
		self.r = roster
		self.iter = iter
		self.jid = self.r.treestore.get_value(iter, 2)
		self.xml.get_widget('label_confirm').set_text('Are you sure you want to remove ' + self.jid + ' from your roster ?')
		self.xml.signal_connect('on_okbutton_clicked', self.req_usub)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)

class authorize:
	def delete_event(self, widget):
		self.window.destroy()
		
	def auth(self, widget):
		self.r.queueOUT.put(('AUTH', self.jid))
		self.delete_event(self)
		add(self.r, self.jid)
	
	def deny(self, widget):
		self.r.queueOUT.put(('DENY', self.jid))
		self.delete_event(self)
	
	def __init__(self, roster, jid):
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Sub_req')
		self.window = self.xml.get_widget('Sub_req')
		self.r = roster
		self.jid = jid
		self.xml.get_widget('label').set_text('Subscription request from ' + self.jid)
		self.xml.signal_connect('on_button_auth_clicked', self.auth)
		self.xml.signal_connect('on_button_deny_clicked', self.deny)
		self.xml.signal_connect('on_button_close_clicked', self.delete_event)

class browser:
	def delete_event(self, widget):
		global Wbrowser
		Wbrowser = 0
		self.window.destroy()

	def browse(self):
		self.r.queueOUT.put(('REQ_AGENTS', None))
	
	def agents(self, agents):
		for jid in agents.keys():
			iter = self.model.append()
			self.model.set(iter, 0, agents[jid]['name'], 1, jid)

	def on_refresh(self, widget):
		self.model.clear()
		self.browse()
		
	def __init__(self, roster):
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'browser')
		self.window = self.xml.get_widget('browser')
		self.treeview = self.xml.get_widget('treeview')
		self.r = roster
		self.model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.treeview.set_model(self.model)
		#columns
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 0)
		self.treeview.insert_column_with_attributes(-1, 'Name', renderer, text=0)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		self.treeview.insert_column_with_attributes(-1, 'JID', renderer, text=1)
		
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_refresh_clicked', self.on_refresh)
		#TODO: Si connect�
		self.browse()

class message:
	def delete_event(self, widget):
		del self.roster.tab_messages[self.user.jid]
		self.window.destroy()
	
	def print_conversation(self, txt, contact = None):
		end_iter = self.convTxtBuffer.get_end_iter()
		if contact:
			self.convTxtBuffer.insert_with_tags_by_name(end_iter, '<moi> ', 'outgoing')
		else:
			self.convTxtBuffer.insert_with_tags_by_name(end_iter, '<' + self.user.name + '> ', 'incoming')
		self.convTxtBuffer.insert(end_iter, txt+'\n')
		self.conversation.scroll_to_mark(\
			self.convTxtBuffer.get_mark('end'), 0.1, 0, 0, 0)

	def on_msg_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Return:
			if (event.state & gtk.gdk.SHIFT_MASK):
				return 0
			txt_buffer = widget.get_buffer()
			start_iter = txt_buffer.get_start_iter()
			end_iter = txt_buffer.get_end_iter()
			txt = txt_buffer.get_text(start_iter, end_iter, 0)
			self.roster.queueOUT.put(('MSG',(self.user.jid, txt)))
			txt_buffer.set_text('', -1)
			self.print_conversation(txt, self.user.jid)
			widget.grab_focus()
			return 1
		return 0

	def __init__(self, user, roster):
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.cfgParser.parseCfgFile()
		self.user = user
		self.roster = roster
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Chat')
		self.window = self.xml.get_widget('Chat')
		self.window.set_title('Chat with ' + user.name)
		self.xml.get_widget('label_contact').set_text(user.name + ' <'\
			+ user.jid + '>')
#+ '/' + user.resource + '>')
		self.message = self.xml.get_widget('message')
		self.conversation = self.xml.get_widget('conversation')
		self.convTxtBuffer = self.conversation.get_buffer()
		end_iter = self.convTxtBuffer.get_end_iter()
		self.convTxtBuffer.create_mark('end', end_iter, 0)
		self.window.show()
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_msg_key_press_event', self.on_msg_key_press_event)
		self.tag = self.convTxtBuffer.create_tag("incoming")
		color = self.cfgParser.GtkGui_inmsgcolor
		if not color:
			color = red
		self.tag.set_property("foreground", color)
		self.tag = self.convTxtBuffer.create_tag("outgoing")
		color = self.cfgParser.GtkGui_outmsgcolor
		if not color:
			color = blue
		self.tag.set_property("foreground", color)

class roster:
	def get_icon_pixbuf(self, stock):
		return self.tree.render_icon(stock, size = gtk.ICON_SIZE_MENU, detail = None)

	def mkroster(self, tab):
		""" l_contact = {jid:{'user':_, 'iter':[iter1, ...]] """
		self.l_contact = {}
		""" l_group = {name:iter} """
		self.l_group = {}
		self.treestore.clear()
		for jid in tab.keys():
			name = tab[jid]['name']
			if not name:
				name = ''
			show = tab[jid]['show']
			if not show:
				show = 'offline'
			user1 = user(jid, name, tab[jid]['groups'], show, tab[jid]['status'], tab[jid]['sub'])
			self.l_contact[user1.jid] = {'user': user1, 'iter': []}
			if user1.groups == []:
				user1.groups.append('general')
			for g in user1.groups:
				if not self.l_group.has_key(g):
					iterG = self.treestore.append(None, (None, g, 'group', FALSE))
					self.l_group[g] = iterG
				if user1.show != 'offline' or self.showOffline:
					iterU = self.treestore.append(self.l_group[g], (self.pixbufs[user1.show], user1.name, user1.jid, TRUE))
					self.l_contact[user1.jid]['iter'].append(iterU)

	def update_iter(self, widget, path, iter, data):
		jid = self.treestore.get_value(iter, 2)
		if jid == data[0]:
			if data[1] == 'offline':
				self.treestore.remove(iter)
				if not self.showOffline:
					self.found = 1
			else:
				self.treestore.set_value(iter, 0, self.pixbufs[data[1]])
				self.found = 1
			return 1
		return 0
	
	def chg_status(self, jid, show, status):
		u = self.l_contact[jid]['user']
		if self.l_contact[jid]['iter'] == []:
			for g in u.groups:
				if not self.l_group.has_key(g):
					iterG = self.treestore.append(None, (None, g, 'group', FALSE))
					self.l_group[u.group] = iterG
				iterU = self.treestore.append(self.l_group[g], (self.pixbufs[show], u.name, u.jid, TRUE))
				self.l_contact[u.jid]['iter'].append(iterU)
		else:
			if show == 'offline' and not self.showOffline:
				for i in self.l_contact[jid]['iter']:
					self.treestore.remove(i)
				self.l_contact[jid]['iter'] = []
			else:
				for i in self.l_contact[jid]['iter']:
					self.treestore.set_value(i, 0, self.pixbufs[show])
		u.show = show
		u.status = status
	
	def mk_menu_c(self, event, iter):
		jid = self.treestore.get_value(iter, 2)
		path = self.treestore.get_path(iter)
		self.menu_c = gtk.Menu()
		item = gtk.MenuItem("Start chat")
		self.menu_c.append(item)
		item.connect("activate", self.on_row_activated, path)
		item = gtk.MenuItem("Rename")
		self.menu_c.append(item)
#		item.connect("activate", self.on_rename, iter)
		item = gtk.MenuItem()
		self.menu_c.append(item)
		item = gtk.MenuItem("Subscription")
		self.menu_c.append(item)
		
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem("Resend authorization to")
		menu_sub.append(item)
		item.connect("activate", self.authorize, jid)
		item = gtk.MenuItem("Rerequest authorization from")
		menu_sub.append(item)
		item.connect("activate", self.req_sub, jid, 'I would like to add you to my contact list, please.')
		
		item = gtk.MenuItem()
		self.menu_c.append(item)
		item = gtk.MenuItem("Remove")
		self.menu_c.append(item)
		item.connect("activate", self.on_req_usub, iter)
		self.menu_c.popup(None, None, None, event.button, event.time)
		self.menu_c.show_all()

	def mk_menu_g(self, event):
		self.menu_c = gtk.Menu()
		item = gtk.MenuItem("grp1")
		self.menu_c.append(item)
		item = gtk.MenuItem("grp2")
		self.menu_c.append(item)
		item = gtk.MenuItem("grp3")
		self.menu_c.append(item)
		self.menu_c.popup(None, None, None, event.button, event.time)
		self.menu_c.show_all()
	
	def authorize(self, widget, jid):
		self.queueOUT.put(('AUTH', jid))

	def rename(self, widget, jid, name):
		u = self.r.l_contact[jid]['user']
		u.name = name
		for i in self.r.l_contact[jid]['iter']:
			self.r.treestore.set_value(i, 1, name)
	
	def req_sub(self, widget, jid, txt):
		self.queueOUT.put(('SUB', (jid, txt)))
		if not self.l_contact.has_key(jid):
			user1 = user(jid, jid, ['general'], 'requested', 'requested', 'sub')
			if not self.l_group.has_key('general'):
				iterG = self.treestore.append(None, (None, 'general', 'group'))
				self.l_group['general'] = iterG
			iterU = self.treestore.append(self.l_group['general'], (self.pixbufs['requested'], jid, jid, TRUE))
			self.l_contact[jid] = {'user':user1, 'iter':[iterU]}

	def on_treeview_event(self, widget, event):
		if (event.button == 3) & (event.type == gtk.gdk.BUTTON_PRESS):
			try:
				path, column, x, y = self.tree.get_path_at_pos(int(event.x), int(event.y))
			except TypeError:
				return
			iter = self.treestore.get_iter(path)
			data = self.treestore.get_value(iter, 2)
			if data == 'group':
				self.mk_menu_g(event)
			else:
				self.mk_menu_c(event, iter)
			return gtk.TRUE
		return gtk.FALSE
	
	def on_req_usub(self, widget, iter):
		window_confirm = confirm(self, iter)

	def on_status_changed(self, widget):
		self.queueOUT.put(('STATUS',widget.name))
		if not self.showOffline:
			self.treestore.clear()

	def on_add(self, widget):
		window_add = add(self)

	def on_about(self, widget):
		window_about = about()

	def on_accounts(self, widget):
		window_accounts = accounts()
	
	def on_quit(self, widget):
		self.queueOUT.put(('QUIT',''))
		gtk.mainquit()

	def on_row_activated(self, widget, path, col=0):
		iter = self.treestore.get_iter(path)
		jid = self.treestore.get_value(iter, 2)
		if self.tab_messages.has_key(jid):
			#TODO: NE FONCTIONNE PAS !
			self.tab_messages[jid].window.grab_focus()
		elif self.l_contact.has_key(jid):
			self.tab_messages[jid] = message(self.l_contact[jid]['user'], self)

	def on_cell_edited (self, cell, row, new_text):
		iter = self.treestore.get_iter_from_string(row)
		jid = self.treestore.get_value(iter, 2)
		old_text = self.l_contact[jid]['user'].name
		if old_text == new_text:
			if self.tab_messages.has_key(jid):
				#TODO: NE FONCTIONNE PAS !
				self.tab_messages[jid].window.grab_focus()
			elif self.l_contact.has_key(jid):
				self.tab_messages[jid] = message(self.l_contact[jid]['user'], self)
		else:
			self.treestore.set_value(iter, 1, new_text)
			self.l_contact[jid]['user'].name = new_text
			self.queueOUT.put(('UPDUSER', (jid, new_text, self.l_contact[jid]['user'].groups)))
		
	def on_browse(self, widget):
		global Wbrowser
		if not Wbrowser:
			Wbrowser = browser(self)

	def __init__(self, queueOUT):
		#initialisation des variables
		# FIXME : handle no file ...
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.cfgParser.parseCfgFile()
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Gajim')
		self.tree = self.xml.get_widget('treeview')
		self.treestore = gtk.TreeStore(gtk.gdk.Pixbuf, str, str, gobject.TYPE_BOOLEAN)
		add_pixbuf = self.get_icon_pixbuf(gtk.STOCK_ADD)
		remove_pixbuf = self.get_icon_pixbuf(gtk.STOCK_REMOVE)
		requested_pixbuf = self.get_icon_pixbuf(gtk.STOCK_QUIT)
		self.pixbufs = { "online": add_pixbuf, \
				"away": remove_pixbuf, \
				"xa": remove_pixbuf, \
				"dnd": remove_pixbuf, \
				"offline": remove_pixbuf, \
				"requested": requested_pixbuf}
		self.tree.set_model(self.treestore)
		self.queueOUT = queueOUT
		self.optionmenu = self.xml.get_widget('optionmenu')
		self.optionmenu.set_history(6)
		self.tab_messages = {}

		showOffline = self.cfgParser.GtkGui_showoffline
		if showOffline:
			self.showOffline = string.atoi(showOffline)
		else:
			self.showOffline = 0

		#colonnes
		self.col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		self.col.pack_start(render_pixbuf, expand = False)
		self.col.add_attribute(render_pixbuf, 'pixbuf', 0)
#		self.col.add_attribute(render_pixbuf, 'pixbuf-expander-closed', 0)
#		self.col.add_attribute(render_pixbuf, 'pixbuf-expander-open', 0)
		render_text = gtk.CellRendererText()
		render_text.connect('edited', self.on_cell_edited)
		self.col.pack_start(render_text, expand = True)
		self.col.add_attribute(render_text, 'text', 1)
		self.col.add_attribute(render_text, 'editable', 3)
		self.tree.append_column(self.col)

		#signals
		self.xml.signal_connect('gtk_main_quit', self.on_quit)
		self.xml.signal_connect('on_accounts_activate', self.on_accounts)
		self.xml.signal_connect('on_browse_agents_activate', self.on_browse)
		self.xml.signal_connect('on_add_activate', self.on_add)
		self.xml.signal_connect('on_about_activate', self.on_about)
		self.xml.signal_connect('on_quit_activate', self.on_quit)
		self.xml.signal_connect('on_treeview_event', self.on_treeview_event)
		self.xml.signal_connect('on_status_changed', self.on_status_changed)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
#		self.mk_menu_c()

class plugin:
	def read_queue(self):
		global Wbrowser
		while self.queueIN.empty() == 0:
			ev = self.queueIN.get()
#			print ev
			if ev[0] == 'ROSTER':
				self.r.mkroster(ev[1])
			elif ev[0] == 'NOTIFY':
				if self.r.l_contact.has_key(ev[1][0]):
					self.r.chg_status(ev[1][0], ev[1][1], ev[1][2])
			elif ev[0] == 'MSG':
				if not self.r.tab_messages.has_key(ev[1][0]):
					#FIXME:message d'un inconne
					self.r.tab_messages[ev[1][0]] = message(self.r.l_contact[ev[1][0]]['user'], self.r)
				self.r.tab_messages[ev[1][0]].print_conversation(ev[1][1])
			elif ev[0] == 'SUBSCRIBE':
				authorize(self.r, ev[1])
			elif ev[0] == 'SUBSCRIBED':
				u = self.r.l_contact[ev[1]['jid']]['user']
				u.name = ev[1]['nom']
				for i in self.r.l_contact[u.jid]['iter']:
					self.r.treestore.set_value(i, 1, u.name)
			elif ev[0] == 'AGENTS':
				if Wbrowser:
					Wbrowser.agents(ev[1])
		return 1

	def __init__(self, quIN, quOUT):
		gtk.threads_init()
		gtk.threads_enter()
		self.queueIN = quIN
		self.r = roster(quOUT)
		self.time = gtk.timeout_add(200, self.read_queue)
		gtk.main()
		gtk.threads_leave()

if __name__ == "__main__":
	plugin(None, None)

print "plugin gtkgui loaded"
