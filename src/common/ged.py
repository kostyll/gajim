# -*- coding: utf-8 -*-

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

'''
Global Events Dispatcher module.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 8th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

from plugins.helpers import log

PRECORE = 30
CORE = 40
POSTCORE = 50

class GlobalEventsDispatcher(object):
	
	def __init__(self):
		self.handlers = {}
	
	def register_event_handler(self, event_name, priority, handler):
		if event_name in self.handlers:
			handlers_list = self.handlers[event_name]
			i = 0
			if len(handlers_list) > 0:
				while priority > handlers_list[i][0]: # sorting handlers by priority
					i += 1
			
			handlers_list.insert(i, (priority, handler))
		else:
			self.handlers[event_name] = [(priority, handler)]
	
	def remove_event_handler(self, event_name, priority, handler):
		if event_name in self.handlers:
			try:
				self.handlers[event_name].remove((priority, handler))
			except ValueError, error:
				log.debug('''Function (%s) with priority "%s" never registered 
				as handler of event "%s". Couldn\'t remove. Error: %s'''
						  %(handler, priority, event_name, error))
	
	def raise_event(self, event_name, *args):
		#log.debug('[GED] Event: %s\nArgs: %s'%(event_name, str(args)))
		if event_name in self.handlers:
			for priority, handler in self.handlers[event_name]:
				handler(args)
	