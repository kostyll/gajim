# -*- coding:utf-8 -*-
## src/dock.py
##
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
from common import gajim
from common import helpers

HAS_SYSTRAY_CAPABILITIES = True
DOCK_IMAGES = {}

try:
	from AppKit import *
except ImportError:
	pass

class Dock:
	'''Class for icon in the OS X dock'''

	def __init__(self):
		self.status = 'offline'

		try:
			for img in ['online', 'chat', 'away', 'xa', 'dnd', 'invisible',
			'offline', 'connecting', 'event']:
				DOCK_IMAGES[img] = NSImage.alloc().initByReferencingFile_(
					os.path.join(gajim.DATA_DIR, 'pixmaps', 'dock_icns',
					img + '.icns'))
		except NameError:
			pass

		gajim.events.event_added_subscribe(self.on_event_added)
		gajim.events.event_removed_subscribe(self.on_event_removed)

	def on_event_added(self, event):
		'''Called when an event is added to the event list'''
		self.set_img()

	def on_event_removed(self, event_list):
		'''Called when one or more events are removed from the event list'''
		self.set_img()

	def set_img(self):
		# FIXME: Using badging instead would be nicer
		if gajim.events.get_nb_systray_events():
			state = 'event'
		else:
			state = self.status

		try:
			NSApp.setApplicationIconImage_(DOCK_IMAGES[state])
		except NameError:
			pass

	def change_status(self, global_status):
		''' set tray image to 'global_status' '''
		# change image and status, only if it is different
		if global_status is not None and self.status != global_status:
			self.status = global_status
		self.set_img()

	def bounce(self):
		try:
			NSApp.requestUserAttention_(NSInformationalRequest)
		except NameError:
			pass

# vim: se ts=3:
