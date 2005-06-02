##	plugins/tabbed_chat_window.py
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
import pango
import gobject
import time
import dialogs

try:
	import gtkspell
except:
	pass

from common import gajim
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class Chat:
	"""Class for chat/groupchat windows"""
	def __init__(self, plugin, account, widget_name):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, widget_name, APP)
		self.window = self.xml.get_widget(widget_name)
		self.widget_name = widget_name
		self.notebook = self.xml.get_widget('chat_notebook')
		self.notebook.remove_page(0)
		self.plugin = plugin
		self.account = account
		self.change_cursor = None
		self.xmls = {}
		self.tagIn = {}
		self.tagOut = {}
		self.tagStatus = {}
		self.nb_unread = {}
		self.last_message_time = {}
		self.print_time_timeout_id = {}
		self.names = {} # what is printed in the tab (eg. user.name)
		self.childs = {}

	def update_tags(self):
		for jid in self.tagIn:
			self.tagIn[jid].set_property('foreground',
					gajim.config.get('inmsgcolor'))
			self.tagOut[jid].set_property('foreground',
					gajim.config.get('outmsgcolor'))
			self.tagStatus[jid].set_property('foreground',
					gajim.config.get('statusmsgcolor'))

	def update_print_time(self):
		if gajim.config.get('print_time') != 'sometimes':
			list_jid = self.print_time_timeout_id.keys()
			for jid in list_jid:
				gobject.source_remove(self.print_time_timeout_id[jid])
				del self.print_time_timeout_id[jid]
		else:
			for jid in self.xmls:
				if self.print_time_timeout_id.has_key(jid):
					continue
				self.print_time_timeout(jid)
				self.print_time_timeout_id[jid] = \
						gobject.timeout_add(300000,
							self.print_time_timeout,
							jid)

	def show_title(self):
		"""redraw the window's title"""
		unread = 0
		for jid in self.nb_unread:
			unread += self.nb_unread[jid]
		start = ""
		if unread > 1:
			start = '[' + str(unread) + '] '
		elif unread == 1:
			start = '* '
		chat = self.names[jid]
		if len(self.xmls) > 1: # if more than one tab in the same window
			if self.widget_name == 'tabbed_chat_window':
				chat = 'Chat'
			elif self.widget_name == 'groupchat_window':
				chat = 'Groupchat'
		title = start + chat
		if len(gajim.connections) >= 2: # if we have 2 or more accounts
			title = title + _(' (account: ') + self.account + ')'

		self.window.set_title(title)

	def redraw_tab(self, jid):
		"""redraw the label of the tab"""
		start = ''
		if self.nb_unread[jid] > 1:
			start = '[' + str(self.nb_unread[jid]) + '] '
		elif self.nb_unread[jid] == 1:
			start = '* '

		child = self.childs[jid]
		if self.widget_name == 'tabbed_chat_window':
			nickname = self.notebook.get_tab_label(child).get_children()[1]
		elif self.widget_name == 'groupchat_window':
			nickname = self.notebook.get_tab_label(child).get_children()[0]

		#FIXME: when gtk2.4 is OOOOLD do it via glade2.10+
		if gtk.pygtk_version > (2, 6, 0) and gtk.gtk_version > (2, 6, 0):
			nickname.set_max_width_chars(15)

		nickname.set_text(start + self.names[jid])

	def on_window_destroy(self, widget, kind): #kind is 'chats' or 'gc'
		#clean self.plugin.windows[self.account][kind]
		for jid in self.xmls:
			if self.plugin.systray_enabled and self.nb_unread[jid] > 0:
				self.plugin.systray.remove_jid(jid, self.account)
			del self.plugin.windows[self.account][kind][jid]
			if self.print_time_timeout_id.has_key(jid):
				gobject.source_remove(self.print_time_timeout_id[jid])
		if self.plugin.windows[self.account][kind].has_key('tabbed'):
			del self.plugin.windows[self.account][kind]['tabbed']

	def get_active_jid(self):
		notebook = self.notebook
		active_child = notebook.get_nth_page(notebook.get_current_page())
		active_jid = ''
		for jid in self.xmls:
			if self.childs[jid] == active_child:
				active_jid = jid
				break
		return active_jid

	def on_close_button_clicked(self, button, jid):
		"""When close button is pressed: close a tab"""
		self.remove_tab(jid)

	def on_chat_window_focus_in_event(self, widget, event):
		"""When window gets focus"""
		jid = self.get_active_jid()
		textview = self.xmls[jid].get_widget('conversation_textview')
		buffer = textview.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = textview.get_iter_location(end_iter)
		visible_rect = textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			#we are at the end
			if self.nb_unread[jid] > 0:
				self.nb_unread[jid] = 0
				self.redraw_tab(jid)
				self.show_title()
				if self.plugin.systray_enabled:
					self.plugin.systray.remove_jid(jid, self.account)

	def on_chat_notebook_switch_page(self, notebook, page, page_num):
		new_child = notebook.get_nth_page(page_num)
		new_jid = ''
		for jid in self.xmls:
			if self.childs[jid] == new_child:
				new_jid = jid
				break

		conversation_textview = self.xmls[new_jid].get_widget(
			'conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		end_iter = conversation_buffer.get_end_iter()
		end_rect = conversation_textview.get_iter_location(end_iter)
		visible_rect = conversation_textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			#we are at the end
			if self.nb_unread[new_jid] > 0:
				self.nb_unread[new_jid] = 0
				self.redraw_tab(new_jid)
				self.show_title()
				if self.plugin.systray_enabled:
					self.plugin.systray.remove_jid(new_jid, self.account)
		
		if self.widget_name == 'tabbed_chat_window':
			nontabbed_status_image = self.xmls[jid].get_widget(
				'nontabbed_status_image')
			if len(self.xmls) > 1:
				nontabbed_status_image.hide()
			else:
				nontabbed_status_image.show()
		
		conversation_textview.grab_focus()

	def set_active_tab(self, jid):
		self.notebook.set_current_page(self.notebook.page_num(self.childs[jid]))

	def remove_tab(self, jid, kind): #kind is 'chats' or 'gc'
		if len(self.xmls) == 1:
			self.window.destroy()
			return
		if self.nb_unread[jid] > 0:
			self.nb_unread[jid] = 0
			self.show_title()
			if self.plugin.systray_enabled:
				self.plugin.systray.remove_jid(jid, self.account)
		if self.print_time_timeout_id.has_key(jid):
			gobject.source_remove(self.print_time_timeout_id[jid])
			del self.print_time_timeout_id[jid]
		self.notebook.remove_page(self.notebook.page_num(self.childs[jid]))
		if len(self.xmls) == 2:
			# one that remains and one that we'll remove, 1 tab remains
			self.notebook.set_show_tabs(False)

		del self.plugin.windows[self.account][kind][jid]
		del self.nb_unread[jid]
		del self.last_message_time[jid]
		del self.xmls[jid]
		del self.tagIn[jid]
		del self.tagOut[jid]
		del self.tagStatus[jid]
		self.show_title()

	def new_tab(self, jid):
		self.nb_unread[jid] = 0
		self.last_message_time[jid] = 0
		
		if gajim.config.get('use_speller') and 'gtkspell' in globals():
			message_textview = self.xmls[jid].get_widget('message_textview')
			try:
				gtkspell.Spell(message_textview)
			except gobject.GError, msg:
				dialogs.Error_dialog(str(msg) + '\n\n' + _('If that is not your language for which you want to highlight misspelled words, then please set your $LANG as appropriate. Eg. for French do export LANG=fr_FR or export LANG=fr_FR.UTF-8 in ~/.bash_profile or to make it global in /etc/profile.\n\nHighlighting misspelled words will not be used'))	
				gajim.config.set('use_speller', False)
		
		conversation_textview = self.xmls[jid].get_widget(
			'conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		end_iter = conversation_buffer.get_end_iter()
		
		conversation_buffer.create_mark('end', end_iter, False)
		
		self.tagIn[jid] = conversation_buffer.create_tag('incoming')
		color = gajim.config.get('inmsgcolor')
		self.tagIn[jid].set_property('foreground', color)
		self.tagOut[jid] = conversation_buffer.create_tag('outgoing')
		color = gajim.config.get('outmsgcolor')
		self.tagOut[jid].set_property('foreground', color)
		self.tagStatus[jid] = conversation_buffer.create_tag('status')
		color = gajim.config.get('statusmsgcolor')
		self.tagStatus[jid].set_property('foreground', color)
		
		tag = conversation_buffer.create_tag('time_sometimes')
		tag.set_property('foreground', '#9e9e9e')
		tag.set_property('scale', pango.SCALE_SMALL)
		tag.set_property('justification', gtk.JUSTIFY_CENTER)
		
		tag = conversation_buffer.create_tag('url')
		tag.set_property('foreground', '#0000ff')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)
		tag.connect('event', self.hyperlink_handler, 'url')

		tag = conversation_buffer.create_tag('mail')
		tag.set_property('foreground', '#0000ff')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)
		tag.connect('event', self.hyperlink_handler, 'mail')
		
		tag = conversation_buffer.create_tag('bold')
		tag.set_property('weight', pango.WEIGHT_BOLD)
		
		tag = conversation_buffer.create_tag('italic')
		tag.set_property('style', pango.STYLE_ITALIC)
		
		tag = conversation_buffer.create_tag('underline')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)
		
		self.xmls[jid].signal_autoconnect(self)
		conversation_scrolledwindow = self.xmls[jid].get_widget(
			'conversation_scrolledwindow')
		conversation_scrolledwindow.get_vadjustment().connect('value-changed',
			self.on_conversation_vadjustment_value_changed)
		
		child = self.childs[jid]
		self.notebook.append_page(child)
		

		if len(self.xmls) > 1:
			self.notebook.set_show_tabs(True)

		if self.widget_name == 'tabbed_chat_window':
			xm = gtk.glade.XML(GTKGUI_GLADE, 'chat_tab_hbox', APP)
			tab_hbox = xm.get_widget('chat_tab_hbox')
		elif self.widget_name == 'groupchat_window':
			xm = gtk.glade.XML(GTKGUI_GLADE, 'groupchat_tab_hbox', APP)
			tab_hbox = xm.get_widget('groupchat_tab_hbox')

		xm.signal_connect('on_close_button_clicked', 
			self.on_close_button_clicked, jid)
		self.notebook.set_tab_label(child, tab_hbox)

		self.show_title()

	def on_conversation_textview_key_press_event(self, widget, event):
		"""Do not block these events and send them to the notebook"""
		if event.state & gtk.gdk.CONTROL_MASK:
			if event.keyval == gtk.keysyms.Tab: # CTRL + TAB
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.ISO_Left_Tab: # CTRL + SHIFT + TAB
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.Page_Down: # CTRL + PAGE DOWN
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.Page_Up: # CTRL + PAGE UP
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.v: # CTRL + V
				jid = self.get_active_jid()
				message_textview = self.xmls[jid].get_widget('message_textview')
				if not message_textview.is_focus():
					message_textview.grab_focus()
				message_textview.emit('key_press_event', event)
				
	def on_chat_notebook_key_press_event(self, widget, event):
		st = '1234567890' # zero is here cause humans count from 1, pc from 0 :P
		jid = self.get_active_jid()
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			if self.widget_name == 'tabbed_chat_window':
				self.remove_tab(jid)
		elif event.keyval == gtk.keysyms.F4 and \
			(event.state & gtk.gdk.CONTROL_MASK): # CTRL + F4
				self.remove_tab(jid)
		elif event.string and event.string in st and \
			(event.state & gtk.gdk.MOD1_MASK): # alt + 1,2,3..
			self.notebook.set_current_page(st.index(event.string))
		elif event.keyval == gtk.keysyms.Page_Down:
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE DOWN
				current = self.notebook.get_current_page()
				if current > 0:
					self.notebook.set_current_page(current-1)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE DOWN
				conversation_textview = self.xmls[jid].\
					get_widget('conversation_textview')
				rect = conversation_textview.get_visible_rect()
				iter = conversation_textview.get_iter_at_location(rect.x,\
					rect.y + rect.height)
				conversation_textview.scroll_to_iter(iter, 0.1, True, 0, 0)
		elif event.keyval == gtk.keysyms.Page_Up: 
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE UP
				current = self.notebook.get_current_page()
				if current < (self.notebook.get_n_pages()-1):
					self.notebook.set_current_page(current + 1)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE UP
				conversation_textview = self.xmls[jid].\
					get_widget('conversation_textview')
				rect = conversation_textview.get_visible_rect()
				iter = conversation_textview.get_iter_at_location(rect.x, rect.y)
				conversation_textview.scroll_to_iter(iter, 0.1, True, 0, 1)
				# or event.keyval == gtk.keysyms.KP_Up
		elif event.keyval == gtk.keysyms.Up: 
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + UP
				conversation_scrolledwindow = self.xml.get_widget('conversation_scrolledwindow')
				conversation_scrolledwindow.emit('scroll-child',
					gtk.SCROLL_PAGE_BACKWARD, False)
		elif event.keyval == gtk.keysyms.ISO_Left_Tab: # SHIFT + TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + SHIFT + TAB
				current = self.notebook.get_current_page()
				if current > 0:
					self.notebook.set_current_page(current - 1)
				else:
					self.notebook.set_current_page(self.notebook.get_n_pages()-1)
		elif event.keyval == gtk.keysyms.Tab: # TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + TAB
				current = self.notebook.get_current_page()
				if current < (self.notebook.get_n_pages()-1):
					self.notebook.set_current_page(current + 1)
				else:
					self.notebook.set_current_page(0)
		elif event.keyval == gtk.keysyms.v:
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + V
				jid = self.get_active_jid()
				message_textview = self.xmls[jid].get_widget('message_textview')
				if not message_textview.is_focus():
					message_textview.grab_focus()
				message_textview.emit('key_press_event', event)
		elif event.state & gtk.gdk.CONTROL_MASK or \
			  (event.keyval == gtk.keysyms.Control_L) or \
			  (event.keyval == gtk.keysyms.Control_R):
			# we pressed a control key or ctrl+sth: we don't block
			# the event in order to let ctrl+c (copy text) and
			# others do their default work
			pass
		else: # it's a normal key press make sure message_textview has focus
			message_textview = self.xmls[jid].get_widget('message_textview')
			if not message_textview.is_focus():
				message_textview.grab_focus()
			message_textview.emit('key_press_event', event)

	def on_conversation_vadjustment_value_changed(self, widget):
		jid = self.get_active_jid()
		if not self.nb_unread[jid]:
			return
		textview = self.xmls[jid].get_widget('conversation_textview')
		buffer = textview.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = textview.get_iter_location(end_iter)
		visible_rect = textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height) and \
		   self.window.is_active():
			#we are at the end
			self.nb_unread[jid] = 0
			self.redraw_tab(jid)
			self.show_title()
			if self.plugin.systray_enabled:
				self.plugin.systray.remove_jid(jid, self.account)
	
	def on_conversation_textview_motion_notify_event(self, widget, event):
		"""change the cursor to a hand when we are on a mail or an url"""
		x, y, spam = widget.window.get_pointer()
		x, y = widget.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, x, y)
		tags = widget.get_iter_at_location(x, y).get_tags()
		if self.change_cursor:
			widget.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.XTERM))
			self.change_cursor = None
		tag_table = widget.get_buffer().get_tag_table()
		for tag in tags:
			if tag == tag_table.lookup('url') or tag == tag_table.lookup('mail'):
				widget.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
					gtk.gdk.Cursor(gtk.gdk.HAND2))
				self.change_cursor = tag
		return False

	def on_clear(self, widget, textview):
		'''clear text in the given textview'''
		buffer = textview.get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)

	def on_conversation_textview_populate_popup(self, textview, menu):
		item = gtk.MenuItem() # seperator
		menu.prepend(item)
		item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
		menu.prepend(item)
		item.connect('activate', self.on_clear, textview)
		menu.show_all()
			
	def on_conversation_textview_button_press_event(self, widget, event):
		# Do not open the standard popup menu, so we block right button
		# click on a taged text

		if event.button != 3:
			return False

		win = widget.get_window(gtk.TEXT_WINDOW_TEXT)
		x, y = widget.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,\
			int(event.x), int(event.y))
		iter = widget.get_iter_at_location(x, y)
		tags = iter.get_tags()

		if not tags:
			return False

		for tag in tags:
			tag_name = tag.get_property('name')
			if 'url' in tag_name or 'mail' in tag_name:
				return True
	
	def print_time_timeout(self, jid):
		if not jid in self.xmls.keys():
			return 0
		if gajim.config.get('print_time') == 'sometimes':
			textview = self.xmls[jid].get_widget('conversation_textview')
			buffer = textview.get_buffer()
			end_iter = buffer.get_end_iter()
			tim = time.localtime()
			tim_format = time.strftime('%H:%M', tim)
			buffer.insert_with_tags_by_name(end_iter,
						'\n' + tim_format,
						'time_sometimes')
			#scroll to the end of the textview
			end_rect = textview.get_iter_location(end_iter)
			visible_rect = textview.get_visible_rect()
			if end_rect.y <= (visible_rect.y + visible_rect.height):
				#we are at the end
				self.scroll_to_end(textview)
			return 1
		if self.print_time_timeout_id.has_key(jid):
			del self.print_time_timeout_id[jid]
		return 0

	def on_open_link_activate(self, widget, kind, text):
		self.plugin.launch_browser_mailer(kind, text)

	def on_copy_link_activate(self, widget, text):
		clip = gtk.clipboard_get()
		clip.set_text(text)

	def make_link_menu(self, event, kind, text):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'chat_context_menu', APP)
		menu = xml.get_widget('chat_context_menu')
		childs = menu.get_children()
		if kind == 'url':
			childs[0].connect('activate', self.on_copy_link_activate, text)
			childs[1].connect('activate', self.on_open_link_activate, kind, text)
			childs[2].hide() # copy mail address
			childs[3].hide() # open mail composer
		else: # It's a mail
			childs[2].connect('activate', self.on_copy_link_activate, text)
			childs[3].connect('activate', self.on_open_link_activate, kind, text)
			childs[0].hide() # copy link location
			childs[1].hide() # open link in browser

		menu.popup(None, None, None, event.button, event.time)
		menu.reposition()

	def hyperlink_handler(self, texttag, widget, event, iter, kind):
		if event.type == gtk.gdk.BUTTON_PRESS:
			begin_iter = iter.copy()
			#we get the begining of the tag
			while not begin_iter.begins_tag(texttag):
				begin_iter.backward_char()
			end_iter = iter.copy()
			#we get the end of the tag
			while not end_iter.ends_tag(texttag):
				end_iter.forward_char()
			word = begin_iter.get_text(end_iter)
			if event.button == 3: # right click
				self.make_link_menu(event, kind, word)
			else:
				#we launch the correct application
				self.plugin.launch_browser_mailer(kind, word)

	def print_with_tag_list(self, buffer, text, iter, tag_list):
		begin_mark = buffer.create_mark('begin_tag', iter, True)
		buffer.insert(iter, text)
		begin_tagged = buffer.get_iter_at_mark(begin_mark)
		for tag in tag_list:
			buffer.apply_tag_by_name(tag, begin_tagged, iter)
		buffer.delete_mark(begin_mark)

	def detect_and_print_special_text(self, otext, jid, other_tags,
						print_all_special):
		textview = self.xmls[jid].get_widget('conversation_textview')
		buffer = textview.get_buffer()
		
		start = 0
		end = 0
		index = 0
		
		# basic: links + mail + formatting is always checked (we like that)
		if gajim.config.get('useemoticons'): # search for emoticons & urls
			iterator = self.plugin.emot_and_basic_re.finditer(otext)
		else: # search for just urls + mail + formatting
			iterator = self.plugin.basic_pattern_re.finditer(otext)
		for match in iterator:
			start, end = match.span()
			special_text = otext[start:end]
			if start != 0:
				text_before_special_text = otext[index:start]
				end_iter = buffer.get_end_iter()
				if print_all_special:
					self.print_with_tag_list(buffer,
						text_before_special_text,
						end_iter, other_tags)
				else:
					buffer.insert(end_iter,
						text_before_special_text)
			if not print_all_special:
				other_tags = []
			index = end # update index
			
			#now print it
			self.print_special_text(special_text, other_tags,
								buffer)
					
		return index
		
	def print_special_text(self, special_text, other_tags, buffer):
		tags = []
		use_other_tags = True

		possible_emot_ascii_caps = special_text.upper() # emoticons keys are CAPS
		if possible_emot_ascii_caps in self.plugin.emoticons.keys():
			#it's an emoticon
			emot_ascii = possible_emot_ascii_caps
			end_iter = buffer.get_end_iter()
			buffer.insert_pixbuf(end_iter,
					self.plugin.emoticons[emot_ascii])
		elif special_text.startswith('mailto:'):
			#it's a mail
			tags.append('mail')
			use_other_tags = False
		elif self.plugin.sth_at_sth_dot_sth_re.match(special_text):
			#it's a mail
			tags.append('mail')
			use_other_tags = False
		elif special_text.startswith('*'): # it's a bold text
			tags.append('bold')
			if special_text[1] == '/': # it's also italic
				tags.append('italic')
				special_text = special_text[2:-2] # remove */ /*
			elif special_text[1] == '_': # it's also underlined
				tags.append('underline')
				special_text = special_text[2:-2] # remove *_ _*
			else:
				special_text = special_text[1:-1] # remove * *
		elif special_text.startswith('/'): # it's an italic text
			tags.append('italic')
			if special_text[1] == '*': # it's also bold
				tags.append('bold')
				special_text = special_text[2:-2] # remove /* */
			elif special_text[1] == '_': # it's also underlined
				tags.append('underline')
				special_text = special_text[2:-2] # remove /_ _/
			else:
				special_text = special_text[1:-1] # remove / /
		elif special_text.startswith('_'): # it's an underlined text
			tags.append('underline')
			if special_text[1] == '*': # it's also bold
				tags.append('bold')
				special_text = special_text[2:-2] # remove _* *_
			elif special_text[1] == '/': # it's also italic
				tags.append('italic')
				special_text = special_text[2:-2] # remove _/ /_
			else:
				special_text = special_text[1:-1] # remove _ _
		else:
			#it's a url
			tags.append('url')
			use_other_tags = False

		if len(tags) > 0:
			end_iter = buffer.get_end_iter()
			all_tags = tags[:]
			if use_other_tags:
				all_tags += other_tags
			self.print_with_tag_list(buffer, special_text,
						end_iter, all_tags)

	def scroll_to_end(self, textview):
		parent = textview.get_parent()
		buffer = textview.get_buffer()
		textview.scroll_to_mark(buffer.get_mark('end'), 0, True, 0, 1)
		adjustment = parent.get_hadjustment()
		adjustment.set_value(0)
		return False

	def print_conversation_line(self, text, jid, kind, name, tim,
						other_tags_for_name = []):
		textview = self.xmls[jid].get_widget('conversation_textview')
		buffer = textview.get_buffer()
		print_all_special = False
		at_the_end = False
		end_iter = buffer.get_end_iter()
		end_rect = textview.get_iter_location(end_iter)
		visible_rect = textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			at_the_end = True
		if not text:
			text = ''
		if buffer.get_char_count() > 0:
			buffer.insert(end_iter, '\n')
		if gajim.config.get('print_time') == 'always':
			if not tim:
				tim = time.localtime()
			before_str = gajim.config.get('before_time')
			after_str = gajim.config.get('after_time')
			format = before_str + '%H:%M:%S' + after_str
			tim_format = time.strftime(format, tim)
			buffer.insert(end_iter, tim_format + ' ')

		if kind == 'status':
			print_all_special = True
		elif text.startswith('/me ') or text.startswith('/me\n'):
			text = name + text[3:]
			print_all_special = True

		if kind == 'incoming':
			self.last_message_time[jid] = time.time()

		tags = other_tags_for_name[:] #create a new list
		tags.append(kind)
		if name and not print_all_special:
			before_str = gajim.config.get('before_nickname')
			after_str = gajim.config.get('after_nickname')
			format = before_str + name + after_str + ' ' 
			self.print_with_tag_list(buffer, format, end_iter, tags)
				
		# detect urls formatting and if the user has it on emoticons
		index = self.detect_and_print_special_text(text, jid,
						tags, print_all_special)

		# add the rest of text located in the index and after
		end_iter = buffer.get_end_iter()
		if print_all_special:
			buffer.insert_with_tags_by_name(end_iter,
							text[index:], kind)
		else:
			buffer.insert(end_iter, text[index:])

		#scroll to the end of the textview
		end = False
		if at_the_end or (kind == 'outgoing'):
			#we are at the end or we are sending something
			end = True
			# We scroll to the end after the scrollbar has appeared
			gobject.idle_add(self.scroll_to_end, textview)
		if (jid != self.get_active_jid() or \
		   not self.window.is_active() or \
		   not end) and kind == 'incoming':
			self.nb_unread[jid] += 1
			if self.plugin.systray_enabled:
				self.plugin.systray.add_jid(jid, self.account)
			self.redraw_tab(jid)
			self.show_title()
