# -*- coding: utf-8 -*-
## src/common/location_listener.py
##
## Copyright (C) 2009 Yann Leboulanger <asterix AT lagaule.org>
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

from common import gajim
from common import pep
from common import dbus_support
if dbus_support.supported:
	import dbus
	import dbus.glib

class LocationListener:
	_instance = None
	@classmethod
	def get(cls):
		if cls._instance is None:
			cls._instance = cls()
		return cls._instance

	def __init__(self):
		self._data = {}

	def get_data(self):
		self._get_address()
		self._get_position()

	def _get_address(self):
		bus = dbus.SessionBus()
		if 'org.freedesktop.Geoclue.Master' not in bus.list_names():
			self._on_geoclue_address_changed(0, {}, 0)
			return
		obj = bus.get_object('org.freedesktop.Geoclue.Master',
			'/org/freedesktop/Geoclue/Master')
		# get MasterClient path
		path = obj.Create()
		# get MasterClient
		cli = bus.get_object('org.freedesktop.Geoclue.Master', path)
		cli.AddressStart()
		# Check that there is a provider
		name, description, service, path = cli.GetAddressProvider()
		if path:
			timestamp, address, accuracy = cli.GetAddress()
			self._on_geoclue_address_changed(timestamp, address, accuracy)

	def _get_position(self):
		bus = dbus.SessionBus()
		if 'org.freedesktop.Geoclue.Master' not in bus.list_names():
			self._on_geoclue_position_changed([], 0, None, None, 0)
			return
		obj = bus.get_object('org.freedesktop.Geoclue.Master',
			'/org/freedesktop/Geoclue/Master')
		# get MasterClient path
		path = obj.Create()
		# get MasterClient
		cli = bus.get_object('org.freedesktop.Geoclue.Master', path)
		cli.PositionStart()
		# Check that there is a provider
		name, description, service, path = cli.GetPositionProvider()
		if path:
			fields, timestamp, lat, lon, accuray = cli.GetPosition()
			self._on_geoclue_position_changed(fields, timestamp, lat, lon,
				accuracy)

	def start(self):
		bus = dbus.SessionBus()
		# Geoclue
		bus.add_signal_receiver(self._on_geoclue_address_changed,
			'AddressChanged', 'org.freedesktop.Geoclue.Address')
		bus.add_signal_receiver(self._on_geoclue_address_changed,
			'PositionChanged', 'org.freedesktop.Geoclue.Position')

	def shut_down(self):
		pass

	def _on_geoclue_address_changed(self, timestamp, address, accuracy):
		# update data with info we just received
		for field in pep.LOCATION_DATA:
			self._data[field] = address.get(field, self._data.get(field, None))
		self._send_location()

	def _on_geoclue_position_changed(self, fields, timestamp, lat, lon,
	accuracy):
		# update data with info we just received
		if lat:
			self._data['lat'] = lat
		if lon:
			self._data['lon'] = lon
		self._send_location()

	def _send_location(self):
		accounts = gajim.connections.keys()
		for acct in accounts:
			if not gajim.account_is_connected(acct):
				continue
			if not gajim.config.get_per('accounts', acct, 'publish_location'):
				continue
			if gajim.connections[acct].location_info == self._data:
				continue
			gajim.connections[acct].send_location(self._data)
			gajim.connections[acct].location_info = self._data
