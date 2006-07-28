##	gtkgui_helpers.py
##
## Copyright (C) 2003-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2004-2005 Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <nkour@jabber.org>
## Copyright (C) 2005 Dimitur Kirov <dkirov@gmail.com>
## Copyright (C) 2005 Travis Shirk <travis@pobox.com>
## Copyright (C) 2005 Norman Rasmussen <norman@rasmussen.co.za>
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

import xml.sax.saxutils
import gtk
import gtk.glade
import gobject
import pango
import os
import sys

import vcard
import dialogs


HAS_PYWIN32 = True
if os.name == 'nt':
	try:
		import win32file
		import win32con
		import pywintypes
	except ImportError:
		HAS_PYWIN32 = False

from common import i18n
from common import gajim
from common import helpers

gtk.glade.bindtextdomain(i18n.APP, i18n.DIR) 
gtk.glade.textdomain(i18n.APP)

screen_w = gtk.gdk.screen_width()
screen_h = gtk.gdk.screen_height()

GLADE_DIR = os.path.join('..', 'data', 'glade')
def get_glade(file_name, root = None):
	file_path = os.path.join(GLADE_DIR, file_name)
	return gtk.glade.XML(file_path, root=root, domain=i18n.APP)

def get_completion_liststore(entry):
	''' create a completion model for entry widget
	completion list consists of (Pixbuf, Text) rows'''
	completion = gtk.EntryCompletion()
	liststore = gtk.ListStore(gtk.gdk.Pixbuf, str)
	
	render_pixbuf = gtk.CellRendererPixbuf()
	completion.pack_start(render_pixbuf, expand = False)
	completion.add_attribute(render_pixbuf, 'pixbuf', 0)
	
	render_text = gtk.CellRendererText()
	completion.pack_start(render_text, expand = True)
	completion.add_attribute(render_text, 'text', 1)
	completion.set_property('text_column', 1)
	completion.set_model(liststore)
	entry.set_completion(completion)
	return liststore
	
	
def popup_emoticons_under_button(menu, button, parent_win):
	''' pops emoticons menu under button, which is in parent_win'''
	window_x1, window_y1 = parent_win.get_origin()
	def position_menu_under_button(menu):
		# inline function, which will not keep refs, when used as CB
		button_x, button_y = button.allocation.x, button.allocation.y
		
		# now convert them to X11-relative
		window_x, window_y = window_x1, window_y1
		x = window_x + button_x
		y = window_y + button_y

		menu_width, menu_height = menu.size_request()

		## should we pop down or up?
		if (y + button.allocation.height + menu_height
			< gtk.gdk.screen_height()):
			# now move the menu below the button
			y += button.allocation.height
		else:
			# now move the menu above the button
			y -= menu_height

		# push_in is True so all the menuitems are always inside screen
		push_in = True
		return (x, y, push_in)

	menu.popup(None, None, position_menu_under_button, 1, 0)
	
def get_theme_font_for_option(theme, option):
	'''return string description of the font, stored in
	theme preferences'''
	font_name = gajim.config.get_per('themes', theme, option)
	font_desc = pango.FontDescription()
	font_prop_str =  gajim.config.get_per('themes', theme, option + 'attrs')
	if font_prop_str:
		if font_prop_str.find('B') != -1:
			font_desc.set_weight(pango.WEIGHT_BOLD)
		if font_prop_str.find('I') != -1:
			font_desc.set_style(pango.STYLE_ITALIC)
	fd = pango.FontDescription(font_name)
	fd.merge(font_desc, True)
	return fd.to_string()
	
def get_default_font():
	'''Get the desktop setting for application font
	first check for GNOME, then XFCE and last KDE
	it returns None on failure or else a string 'Font Size' '''
	
	try:
		import gconf
		# in try because daemon may not be there
		client = gconf.client_get_default()

		return helpers.ensure_unicode_string(
			client.get_string('/desktop/gnome/interface/font_name'))
	except:
		pass

	# try to get xfce default font
	# Xfce 4.2 adopts freedesktop.org's Base Directory Specification
	# see http://www.xfce.org/~benny/xfce/file-locations.html
	# and http://freedesktop.org/Standards/basedir-spec
	xdg_config_home = os.environ.get('XDG_CONFIG_HOME', '')
	if xdg_config_home == '':
		xdg_config_home = os.path.expanduser('~/.config') # default	
	xfce_config_file = os.path.join(xdg_config_home, 'xfce4/mcs_settings/gtk.xml')
	
	kde_config_file = os.path.expanduser('~/.kde/share/config/kdeglobals')
	
	if os.path.exists(xfce_config_file):
		try:
			for line in file(xfce_config_file):
				if line.find('name="Gtk/FontName"') != -1:
					start = line.find('value="') + 7
					return helpers.ensure_unicode_string(
						line[start:line.find('"', start)])
		except:
			#we talk about file
			print >> sys.stderr, _('Error: cannot open %s for reading') % xfce_config_file
	
	elif os.path.exists(kde_config_file):
		try:
			for line in file(kde_config_file):
				if line.find('font=') == 0: # font=Verdana,9,other_numbers
					start = 5 # 5 is len('font=')
					line = line[start:]
					values = line.split(',')
					font_name = values[0]
					font_size = values[1]
					font_string = '%s %s' % (font_name, font_size) # Verdana 9
					return helpers.ensure_unicode_string(font_string)
		except:
			#we talk about file
			print >> sys.stderr, _('Error: cannot open %s for reading') % kde_config_file
	
	return None
	
def reduce_chars_newlines(text, max_chars = 0, max_lines = 0):
	'''Cut the chars after 'max_chars' on each line
	and show only the first 'max_lines'.
	If any of the params is not present (None or 0) the action
	on it is not performed'''

	def _cut_if_long(str):
		if len(str) > max_chars:
			str = str[:max_chars - 3] + '...'
		return str
	
	if max_lines == 0:
		lines = text.split('\n')
	else:
		lines = text.split('\n', max_lines)[:max_lines]
	if max_chars > 0:
		if lines:
			lines = map(lambda e: _cut_if_long(e), lines)
	if lines:
		reduced_text = reduce(lambda e, e1: e + '\n' + e1, lines)
	else:
		reduced_text = ''
	return reduced_text

def escape_for_pango_markup(string):
	# escapes < > & ' "
	# for pango markup not to break
	if string is None:
		return
	if gtk.pygtk_version >= (2, 8, 0) and gtk.gtk_version >= (2, 8, 0):
		escaped_str = gobject.markup_escape_text(string)
	else:
		escaped_str = xml.sax.saxutils.escape(string, {"'": '&apos;',
			'"': '&quot;'})
	
	return escaped_str

def autodetect_browser_mailer():
	# recognize the environment for appropriate browser/mailer
	if os.path.isdir('/proc'):
		# under Linux: checking if 'gnome-session' or
		# 'startkde' programs were run before gajim, by
		# checking /proc (if it exists)
		#
		# if something is unclear, read `man proc`;
		# if /proc exists, directories that have only numbers
		# in their names contain data about processes.
		# /proc/[xxx]/exe is a symlink to executable started
		# as process number [xxx].
		# filter out everything that we are not interested in:
		files = os.listdir('/proc')

		# files that doesn't have only digits in names...
		files = filter(str.isdigit, files)

		# files that aren't directories...
		files = filter(lambda f:os.path.isdir('/proc/' + f), files)

		# processes owned by somebody not running gajim...
		# (we check if we have access to that file)
		files = filter(lambda f:os.access('/proc/' + f +'/exe', os.F_OK), files)

		# be sure that /proc/[number]/exe is really a symlink
		# to avoid TBs in incorrectly configured systems
		files = filter(lambda f:os.path.islink('/proc/' + f + '/exe'), files)

		# list of processes
		processes = [os.path.basename(os.readlink('/proc/' + f +'/exe')) for f in files]
		if 'gnome-session' in processes:
			gajim.config.set('openwith', 'gnome-open')
		elif 'startkde' in processes:
			gajim.config.set('openwith', 'kfmclient exec')
		else:
			gajim.config.set('openwith', 'custom')

def move_window(window, x, y):
	'''moves the window but also checks if out of screen'''
	if x < 0:
		x = 0
	if y < 0:
		y = 0
	window.move(x, y)

def resize_window(window, w, h):
	'''resizes window but also checks if huge window or negative values'''
	if not w or not h:
		return
	if w > screen_w:
		w = screen_w
	if h > screen_h:
		h = screen_h
	window.resize(abs(w), abs(h))

class TagInfoHandler(xml.sax.ContentHandler):
	def __init__(self, tagname1, tagname2):
		xml.sax.ContentHandler.__init__(self)
		self.tagname1 = tagname1
		self.tagname2 = tagname2
		self.servers = []

	def startElement(self, name, attributes):
		if name == self.tagname1:
			for attribute in attributes.getNames():
				if attribute == 'jid':
					jid = attributes.getValue(attribute)
					# we will get the port next time so we just set it 0 here
					self.servers.append([jid, 0])
		elif name == self.tagname2:
			for attribute in attributes.getNames():
				if attribute == 'port':
					port = attributes.getValue(attribute)
					# we received the jid last time, so we now assign the port
					# number to the last jid in the list
					self.servers[-1][1] = port

	def endElement(self, name):
		pass

def parse_server_xml(path_to_file):
	try:
		handler = TagInfoHandler('item', 'active')
		xml.sax.parse(path_to_file, handler)
		return handler.servers
	# handle exception if unable to open file
	except IOError, message:
		print >> sys.stderr, _('Error reading file:'), message
	# handle exception parsing file
	except xml.sax.SAXParseException, message:
		print >> sys.stderr, _('Error parsing file:'), message

def set_unset_urgency_hint(window, unread_messages_no):
	'''sets/unsets urgency hint in window argument
	depending if we have unread messages or not'''
	if gtk.gtk_version >= (2, 8, 0) and gtk.pygtk_version >= (2, 8, 0) and \
		gajim.config.get('use_urgency_hint'):
		if unread_messages_no > 0:
			window.props.urgency_hint = True
		else:
			window.props.urgency_hint = False

def get_abspath_for_script(scriptname, want_type = False):
	'''checks if we are svn or normal user and returns abspath to asked script
	if want_type is True we return 'svn' or 'install' '''
	if os.path.isdir('.svn'): # we are svn user
		type = 'svn'
		cwd = os.getcwd() # it's always ending with src

		if scriptname == 'gajim-remote':
			path_to_script = cwd + '/gajim-remote.py'
		
		elif scriptname == 'gajim':
			script = '#!/bin/sh\n' # the script we may create
			script += 'cd %s' % cwd
			path_to_script = cwd + '/../scripts/gajim_sm_script'
				
			try:
				if os.path.exists(path_to_script):
					os.remove(path_to_script)

				f = open(path_to_script, 'w')
				script += '\nexec python -OOt gajim.py $0 $@\n'
				f.write(script)
				f.close()
				os.chmod(path_to_script, 0700)
			except OSError: # do not traceback (could be a permission problem)
				#we talk about a file here
				s = _('Could not write to %s. Session Management support will not work') % path_to_script
				print >> sys.stderr, s

	else: # normal user (not svn user)
		type = 'install'
		# always make it like '/usr/local/bin/gajim'
		path_to_script = helpers.is_in_path(scriptname, True)
		
	
	if want_type:
		return path_to_script, type
	else:
		return path_to_script

def get_pixbuf_from_data(file_data, want_type = False):
	'''Gets image data and returns gtk.gdk.Pixbuf
	if want_type is True it also returns 'jpeg', 'png' etc'''
	pixbufloader = gtk.gdk.PixbufLoader()
	try:
		pixbufloader.write(file_data)
		pixbufloader.close()
		pixbuf = pixbufloader.get_pixbuf()
	except gobject.GError: # 'unknown image format'
		pixbuf = None

	if want_type:
		typ = pixbufloader.get_format()['name']
		return pixbuf, typ
	else:
		return pixbuf

def get_invisible_cursor():
	pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
	color = gtk.gdk.Color()
	cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)
	return cursor

def get_current_desktop(window):
	'''returns the current virtual desktop for given window
	NOTE: window is GDK window'''
	prop = window.property_get('_NET_CURRENT_DESKTOP')
	if prop is None: # it means it's normal window (not root window)
		# so we look for it's current virtual desktop in another property
		prop = window.property_get('_NET_WM_DESKTOP')

	if prop is not None:
		# f.e. prop is ('CARDINAL', 32, [0]) we want 0 or 1.. from [0]
		current_virtual_desktop_no = prop[2][0]
		return current_virtual_desktop_no

def possibly_move_window_in_current_desktop(window):
	'''moves GTK window to current virtual desktop if it is not in the
	current virtual desktop
	window is GTK window'''
	if os.name == 'nt':
		return

	root_window = gtk.gdk.screen_get_default().get_root_window()
	# current user's vd
	current_virtual_desktop_no = get_current_desktop(root_window)
	
	# vd roster window is in
	window_virtual_desktop = get_current_desktop(window.window)

	# if one of those is None, something went wrong and we cannot know
	# VD info, just hide it (default action) and not show it afterwards
	if None not in (window_virtual_desktop, current_virtual_desktop_no):
		if current_virtual_desktop_no != window_virtual_desktop:
			# we are in another VD that the window was
			# so show it in current VD
			window.present()

def file_is_locked(path_to_file):
	'''returns True if file is locked (WINDOWS ONLY)'''
	if os.name != 'nt': # just in case
		return
	
	if not HAS_PYWIN32:
		return
	
	secur_att = pywintypes.SECURITY_ATTRIBUTES()
	secur_att.Initialize()
	
	try:
		# try make a handle for READING the file
		hfile = win32file.CreateFile(
			path_to_file,					# path to file
			win32con.GENERIC_READ,			# open for reading
			0,								# do not share with other proc
			secur_att,
			win32con.OPEN_EXISTING,			# existing file only
			win32con.FILE_ATTRIBUTE_NORMAL,	# normal file
			0								# no attr. template
		)
	except pywintypes.error, e:
		return True
	else: # in case all went ok, close file handle (go to hell WinAPI)
		hfile.Close()
		return False

def _get_fade_color(treeview, selected, focused):
	'''get a gdk color that is between foreground and background in 0.3
	0.7 respectively colors of the cell for the given treeview'''
	style = treeview.style
	if selected:
		if focused: # is the window focused?
			state = gtk.STATE_SELECTED
		else: # is it not? NOTE: many gtk themes change bg on this
			state = gtk.STATE_ACTIVE
	else:
		state = gtk.STATE_NORMAL
	bg = style.base[state]
	fg = style.text[state]

	p = 0.3 # background
	q = 0.7 # foreground # p + q should do 1.0
	return gtk.gdk.Color(int(bg.red*p + fg.red*q),
			      int(bg.green*p + fg.green*q),
			      int(bg.blue*p + fg.blue*q))

def get_scaled_pixbuf(pixbuf, kind):
	'''returns scaled pixbuf, keeping ratio etc or None
	kind is either "chat" or "roster" or "notification" or "tooltip"'''
	
	# resize to a width / height for the avatar not to have distortion
	# (keep aspect ratio)
	width = gajim.config.get(kind + '_avatar_width')
	height = gajim.config.get(kind + '_avatar_height')
	if width < 1 or height < 1:
		return None

	# Pixbuf size
	pix_width = pixbuf.get_width()
	pix_height = pixbuf.get_height()
	# don't make avatars bigger than they are
	if pix_width < width and pix_height < height:
		return pixbuf # we don't want to make avatar bigger

	ratio = float(pix_width) / float(pix_height)
	if ratio > 1:
		w = width
		h = int(w / ratio)
	else:
		h = height
		w = int(h * ratio)
	scaled_buf = pixbuf.scale_simple(w, h, gtk.gdk.INTERP_HYPER)
	return scaled_buf

def get_avatar_pixbuf_from_cache(fjid, is_fake_jid = False):
	'''checks if jid has cached avatar and if that avatar is valid image
	(can be shown)
	returns None if there is no image in vcard
	returns 'ask' if cached vcard should not be used (user changed his vcard,
	so we have new sha) or if we don't have the vcard'''

	jid, nick = gajim.get_room_and_nick_from_fjid(fjid)
	if gajim.config.get('hide_avatar_of_transport') and\
		gajim.jid_is_transport(jid):
		# don't show avatar for the transport itself
		return None

	puny_jid = helpers.sanitize_filename(jid)
	if is_fake_jid:
		puny_nick = helpers.sanitize_filename(nick)
		path = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
	else:
		path = os.path.join(gajim.VCARD_PATH, puny_jid)
	if not os.path.isfile(path):
		return 'ask'

	vcard_dict = gajim.connections.values()[0].get_cached_vcard(fjid,
		is_fake_jid)
	if not vcard_dict: # This can happen if cached vcard is too old
		return 'ask'
	if not vcard_dict.has_key('PHOTO'):
		return None
	pixbuf = vcard.get_avatar_pixbuf_encoded_mime(vcard_dict['PHOTO'])[0]
	return pixbuf

def make_gtk_month_python_month(month):
	'''gtk start counting months from 0, so January is 0
	but python's time start from 1, so align to python
	month MUST be integer'''
	return month + 1

def make_python_month_gtk_month(month):
	return month - 1

def make_color_string(color):
	'''create #aabbcc color string from gtk color'''
	col = '#'
	for i in (color.red, color.green, color.blue):
		h = hex(i)[2:4]
		if len(h) == 1:
			h = '0' + h
		col += h
	return col

def make_pixbuf_grayscale(pixbuf):
	pixbuf2 = pixbuf.copy()
	pixbuf.saturate_and_pixelate(pixbuf2, 0.0, False)
	return pixbuf2

def get_path_to_generic_or_avatar(generic, jid = None, suffix = None):
	'''Chooses between avatar image and default image.
	Returns full path to the avatar image if it exists,
	otherwise returns full path to the image.'''
	if jid:
		puny_jid = helpers.sanitize_filename(jid)
		path_to_file = os.path.join(gajim.AVATAR_PATH, puny_jid) + suffix
		if os.path.exists(path_to_file):
			return path_to_file
	return os.path.abspath(generic)

def decode_filechooser_file_paths(file_paths):
	'''decode as UTF-8 under Windows and
	ask sys.getfilesystemencoding() in POSIX
	file_paths MUST be LIST'''
	file_paths_list = list()
	
	if os.name == 'nt': # decode as UTF-8 under Windows
		for file_path in file_paths:
			file_path = file_path.decode('utf8')
			file_paths_list.append(file_path)
	else:
		for file_path in file_paths:
			try:
				file_path = file_path.decode(sys.getfilesystemencoding())
			except:
				try:
					file_path = file_path.decode('utf-8')
				except:
					pass
			file_paths_list.append(file_path)
	
	return file_paths_list

def possibly_set_gajim_as_xmpp_handler():
	'''registers (by default only the first time) xmmp: to Gajim.'''
	try:
		import gconf
		# in try because daemon may not be there
		client = gconf.client_get_default()
	except:
		return
	
	
	path_to_dot_kde = os.path.expanduser('~/.kde')
	if os.path.exists(path_to_dot_kde):
		path_to_kde_file = os.path.join(path_to_dot_kde, 
			'share/services/xmpp.protocol')
		if not os.path.exists(path_to_kde_file):
			path_to_kde_file = None
	else:
		path_to_kde_file = None
	
	if gajim.config.get('set_xmpp://_handler_everytime'):
			# it's false by default
			we_set = True
	elif client.get_string('/desktop/gnome/url-handlers/xmpp/command') is None:
		# only the first time (GNOME/GCONF)
		we_set = True
	elif path_to_kde_file is not None and not os.path.exists(path_to_kde_file):
		# only the first time (KDE)
		we_set = True
	else:
		we_set = False
		
	if not we_set:
		return
	
	path_to_gajim_script, typ = get_abspath_for_script('gajim-remote', True)
	if path_to_gajim_script:
		if typ == 'svn':
			command = path_to_gajim_script + ' open_chat %s'
		else: # 'installed'
			command = 'gajim-remote open_chat %s'
		
		# setting for GNOME/Gconf
		client.set_bool('/desktop/gnome/url-handlers/xmpp/enabled', True)
		client.set_string('/desktop/gnome/url-handlers/xmpp/command', command)
		client.set_bool('/desktop/gnome/url-handlers/xmpp/needs_terminal', False)
		
		# setting for KDE
		if path_to_kde_file is not None: # user has run kde at least once
			f = open(path_to_kde_file, 'w')
			f.write('''\
[Protocol]
exec=%s "%%u"
protocol=xmpp
input=none
output=none
helper=true
listing=false
reading=false
writing=false
makedir=false
deleting=false
icon=gajim
Description=xmpp
''' % command)
			f.close()

def escape_underscore(s):
	'''Escape underlines to prevent them from being interpreted
	as keyboard accelerators'''
	return s.replace('_', '__')

def get_state_image_from_file_path_show(file_path, show):
	state_file = show.replace(' ', '_')
	files = []
	files.append(os.path.join(file_path, state_file + '.png'))
	files.append(os.path.join(file_path, state_file + '.gif'))
	image = gtk.Image()
	image.set_from_pixbuf(None)
	for file_ in files:
		if os.path.exists(file_):
			image.set_from_file(file_)
			break

	return image

def get_possible_button_event(event):
	'''mouse or keyboard caused the event?'''
	if event.type == gtk.gdk.KEY_PRESS:
		event_button = 0 # no event.button so pass 0
	else: # BUTTON_PRESS event, so pass event.button
		event_button = event.button

	return event_button

def destroy_widget(widget):
	widget.destroy()

def on_avatar_save_as_menuitem_activate(widget, jid, account,
default_name = ''):
	def on_ok(widget):
		def on_ok2(widget, file_path, pixbuf):
			pixbuf.save(file_path, 'jpeg')
			dialog2.destroy()
			dialog.destroy()

		file_path = dialog.get_filename()
		file_path = decode_filechooser_file_paths((file_path,))[0]
		if os.path.exists(file_path):
			dialog2 = dialogs.FTOverwriteConfirmationDialog(
				_('This file already exists'), _('What do you want to do?'),
				False)
			dialog2.set_transient_for(dialog)
			dialog2.set_destroy_with_parent(True)
			response = dialog2.get_response()
			if response < 0:
				return

		# Get pixbuf
		pixbuf = None
		is_fake = False
		if account and gajim.contacts.is_pm_from_jid(account, jid):
			is_fake = True
		pixbuf = get_avatar_pixbuf_from_cache(jid, is_fake)
		ext = file_path.split('.')[-1]
		type_ = ''
		if not ext:
			# Silently save as Jpeg image
			file_path += '.jpeg'
			type_ = 'jpeg'
		elif ext == 'jpg':
			type_ = 'jpeg'
		else:
			type_ = ext

		# Save image
		try:
			pixbuf.save(file_path, type_)
		except:
			#XXX Check for permissions
			os.remove(file_path)
			new_file_path = '.'.join(file_path.split('.')[:-1]) + '.jpeg'
			dialog2 = dialogs.ConfirmationDialog(_('Extension not supported'),
				_('Image cannot be saved in %(type)s format. Save as %(new_filename)s?') % {'type': type_, 'new_filename': new_file_path},
				on_response_ok = (on_ok2, new_file_path, pixbuf))
		else:
			dialog.destroy()

	def on_cancel(widget):
		dialog.destroy()

	dialog = dialogs.FileChooserDialog(
		title_text = _('Save Image as...'), 
		action = gtk.FILE_CHOOSER_ACTION_SAVE, 
		buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
		gtk.STOCK_SAVE, gtk.RESPONSE_OK),
		default_response = gtk.RESPONSE_OK,
		current_folder = gajim.config.get('last_save_dir'),
		on_response_ok = on_ok,
		on_response_cancel = on_cancel)

	dialog.set_current_name(default_name)
	dialog.connect('delete-event', lambda widget, event:
		on_cancel(widget))
