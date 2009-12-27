# -*- coding:utf-8 -*-
## src/features_window.py
##
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
##                    Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2007-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import os
import sys
import gtk
import gtkgui_helpers

from common import gajim
from common import helpers
from common import kwalletbinding

class FeaturesWindow:
	"""
	Class for features window
	"""

	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('features_window.glade')
		self.window = self.xml.get_widget('features_window')
		treeview = self.xml.get_widget('features_treeview')
		self.desc_label = self.xml.get_widget('feature_desc_label')

		# {name: (available_function, unix_text, windows_text)}
		self.features = {
			_('SSL certificat validation'): (self.pyopenssl_available,
				_('A library used to validate server certificates to ensure a secure connection.'),
				_('Requires python-pyopenssl.'),
				_('Requires python-pyopenssl.')),
			_('Bonjour / Zeroconf'): (self.zeroconf_available,
				_('Serverless chatting with autodetected clients in a local network.'),
				_('Requires python-avahi.'),
				_('Requires pybonjour (http://o2s.csail.mit.edu/o2s-wiki/pybonjour).')),
			_('Command line'): (self.dbus_available,
				_('A script to control Gajim via commandline.'),
				_('Requires python-dbus.'),
				_('Feature not available under Windows.')),
			_('OpenGPG message encryption'): (self.gpg_available,
				_('Encrypting chat messages with gpg keys.'),
				_('Requires gpg and python-GnuPGInterface.'),
				_('Feature not available under Windows.')),
			_('Network-manager'): (self.network_manager_available,
				_('Autodetection of network status.'),
				_('Requires gnome-network-manager and python-dbus.'),
				_('Feature not available under Windows.')),
			_('Session Management'): (self.session_management_available,
				_('Gajim session is stored on logout and restored on login.'),
				_('Requires python-gnome2.'),
				_('Feature not available under Windows.')),
			_('Password encryption'): (self.some_keyring_available,
				_('Passwords can be stored securely and not just in plaintext.'),
				_('Requires gnome-keyring and python-gnome2-desktop, or kwalletcli.'),
				_('Feature not available under Windows.')),
			_('SRV'): (self.srv_available,
				_('Ability to connect to servers which are using SRV records.'),
				_('Requires dnsutils.'),
				_('Requires nslookup to use SRV records.')),
			_('Spell Checker'): (self.speller_available,
				_('Spellchecking of composed messages.'),
				_('Requires libgtkspell.'),
				_('Feature not available under Windows.')),
			_('Notification'): (self.notification_available,
				_('Passive popups notifying for new events.'),
				_('Requires python-notify or instead python-dbus in conjunction with notification-daemon.'),
				_('Feature not available under Windows.')),
			_('Automatic status'): (self.idle_available,
				_('Ability to measure idle time, in order to set auto status.'),
				_('Requires libxss library.'),
				_('Requires python2.5.')),
			_('LaTeX'): (self.latex_available,
				_('Transform LaTeX expressions between $$ $$.'),
				_('Requires texlive-latex-base and dvipng. You have to set \'use_latex\' to True in the Advanced Configuration Editor.'),
				_('Requires texlive-latex-base and dvipng (All is in MikTeX). You have to set \'use_latex\' to True in the Advanced Configuration Editor.')),
			_('End to End message encryption'): (self.pycrypto_available,
				_('Encrypting chat messages.'),
				_('Requires python-crypto.'),
				_('Requires python-crypto.')),
			_('RST Generator'): (self.docutils_available,
				_('Generate XHTML output from RST code (see http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html).'),
				_('Requires python-docutils.'),
				_('Requires python-docutils.')),
			_('Banners and clickable links'): (self.pysexy_available,
				_('Ability to have clickable URLs in chat and groupchat window banners.'),
				_('Requires python-sexy.'),
				_('Requires python-sexy.')),
			_('Audio / Video'): (self.farsight_available,
				_('Ability to start audio and video chat.'),
				_('Requires python-farsight.'),
				_('Feature not available under Windows.')),
		}

		# name, supported
		self.model = gtk.ListStore(str, bool)
		treeview.set_model(self.model)

		col = gtk.TreeViewColumn(_('Available'))
		treeview.append_column(col)
		cell = gtk.CellRendererToggle()
		cell.set_property('radio', True)
		col.pack_start(cell)
		col.set_attributes(cell, active = 1)

		col = gtk.TreeViewColumn(_('Feature'))
		treeview.append_column(col)
		cell = gtk.CellRendererText()
		col.pack_start(cell, expand = True)
		col.add_attribute(cell, 'text', 0)

		# Fill model
		for feature in self.features:
			func = self.features[feature][0]
			rep = func()
			self.model.append([feature, rep])

		self.model.set_sort_column_id(0, gtk.SORT_ASCENDING)

		self.xml.signal_autoconnect(self)
		self.window.show_all()
		self.xml.get_widget('close_button').grab_focus()

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_features_treeview_cursor_changed(self, widget):
		selection = widget.get_selection()
		if not selection:
			return
		rows = selection.get_selected_rows()[1]
		if not rows:
			return
		path = rows[0]
		feature = self.model[path][0].decode('utf-8')
		text = self.features[feature][1] + '\n'
		if os.name == 'nt':
			text = text + self.features[feature][3]
		else:
			text = text + self.features[feature][2]
		self.desc_label.set_text(text)

	def pyopenssl_available(self):
		try:
			import OpenSSL.SSL
			import OpenSSL.crypto
		except Exception:
			return False
		return True

	def zeroconf_available(self):
		try:
			import avahi
		except Exception:
			try:
				import pybonjour
			except Exception:
				return False
		return True

	def dbus_available(self):
		if os.name == 'nt':
			return False
		from common import dbus_support
		return dbus_support.supported

	def gpg_available(self):
		if os.name == 'nt':
			return False
		return gajim.HAVE_GPG

	def network_manager_available(self):
		if os.name == 'nt':
			return False
		import network_manager_listener
		return network_manager_listener.supported

	def session_management_available(self):
		if os.name == 'nt':
			return False
		try:
			import gnome.ui
		except Exception:
			return False
		return True

	def some_keyring_available(self):
		if os.name == 'nt':
			return False
		if kwalletbinding.kwallet_available():
			return True
		try:
			import gnomekeyring
		except Exception:
			return False
		return True

	def srv_available(self):
		return helpers.is_in_path('nslookup')

	def speller_available(self):
		if os.name == 'nt':
			return False
		try:
			import gtkspell
		except ImportError:
			return False
		return True

	def notification_available(self):
		if os.name == 'nt':
			return False
		from common import dbus_support
		if self.dbus_available() and dbus_support.get_notifications_interface():
			return True
		try:
			import pynotify
		except Exception:
			return False
		return True

	def idle_available(self):
		from common import sleepy
		return sleepy.SUPPORTED

	def latex_available(self):
		from common import latex
		return latex.check_for_latex_support()

	def pycrypto_available(self):
		return gajim.HAVE_PYCRYPTO

	def docutils_available(self):
		try:
			import docutils
		except Exception:
			return False
		return True

	def pysexy_available(self):
		return gajim.HAVE_PYSEXY

	def farsight_available(self):
		return gajim.HAVE_FARSIGHT

# vim: se ts=3:
