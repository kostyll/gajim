## common/contacts.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
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

import common.gajim

class Contact:
	'''Information concerning each contact'''
	def __init__(self, jid='', name='', groups=[], show='', status='', sub='',
			ask='', resource='', priority=5, keyID='', our_chatstate=None,
			chatstate=None, last_status_time=None):
		self.jid = jid
		self.name = name
		self.groups = groups
		self.show = show
		self.status = status
		self.sub = sub
		self.ask = ask
		self.resource = resource
		self.priority = priority
		self.keyID = keyID

		# please read jep-85 http://www.jabber.org/jeps/jep-0085.html
		# we keep track of jep85 support by the peer by three extra states:
		# None, False and 'ask'
		# None if no info about peer
		# False if peer does not support jep85
		# 'ask' if we sent the first 'active' chatstate and are waiting for reply
		# this holds what WE SEND to contact (our current chatstate)
		self.our_chatstate = our_chatstate
		self.msg_id = None
		# this is contact's chatstate
		self.chatstate = chatstate
		self.last_status_time = last_status_time

	def get_full_jid(self):
		if self.resource:
			return self.jid + '/' + self.resource
		return self.jid

	def get_shown_name(self):
		if self.name:
			return self.name
		return self.jid.split('@')[0]

class GC_Contact:
	'''Information concerning each groupchat contact'''
	def __init__(self, room_jid='', name='', show='', status='', role='',
			affiliation='', jid = '', resource = ''):
		self.room_jid = room_jid
		self.name = name
		self.show = show
		self.status = status
		self.role = role
		self.affiliation = affiliation
		self.jid = jid
		self.resource = resource

	def get_full_jid(self):
		return self.room_jid + '/' + self.name

	def get_shown_name(self):
		return self.name

class Contacts:
	'''Information concerning all contacts and groupchat contacts'''
	def __init__(self):
		self._contacts = {} # list of contacts {acct: {jid1: [C1, C2]}, } one Contact per resource
		self._gc_contacts = {} # list of contacts that are in gc {acct: {room_jid: {nick: C}}}

		# For meta contacts:
		self._children_meta_contacts = {}
		self._parent_meta_contacts = {}

	def change_account_name(self, old_name, new_name):
		self._contacts[new_name] = self._contacts[old_name]
		self._gc_contacts[new_name] = self._gc_contacts[old_name]
		self._children_meta_contacts[new_name] = self._children_meta_contacts[old_name]
		self._parent_meta_contacts[new_name] = self._parent_meta_contacts[old_name]
		del self._contacts[old_name]
		del self._gc_contacts[old_name]
		del self._children_meta_contacts[old_name]
		del self._parent_meta_contacts[old_name]

	def add_account(self, account):
		self._contacts[account] = {}
		self._gc_contacts[account] = {}
		if not self._children_meta_contacts.has_key(account):
			self._children_meta_contacts[account] = {}
			self._parent_meta_contacts[account] = {}

	def get_accounts(self):
		return self._contacts.keys()

	def remove_account(self, account):
		del self._contacts[account]
		del self._gc_contacts[account]
		del self._children_meta_contacts[account]
		del self._parent_meta_contacts[account]

	def create_contact(self, jid='', name='', groups=[], show='', status='',
		sub='', ask='', resource='', priority=5, keyID='', our_chatstate=None,
		chatstate=None, last_status_time=None):
		return Contact(jid, name, groups, show, status, sub, ask, resource,
			priority, keyID, our_chatstate, chatstate, last_status_time)
	
	def copy_contact(self, contact):
		return self.create_contact(jid = contact.jid, name = contact.name,
			groups = contact.groups, show = contact.show, status = contact.status,
			sub = contact.sub, ask = contact.ask, resource = contact.resource,
			priority = contact.priority, keyID = contact.keyID,
			our_chatstate = contact.our_chatstate, chatstate = contact.chatstate,
			last_status_time = contact.last_status_time)

	def add_contact(self, account, contact):
		# No such account before ?
		if not self._contacts.has_key(account):
			self._contacts[account] = {contact.jid : [contact]}
			return
		# No such jid before ?
		if not self._contacts[account].has_key(contact.jid):
			self._contacts[account][contact.jid] = [contact]
			return
		contacts = self._contacts[account][contact.jid]
		# We had only one that was offline, remove it
		if len(contacts) == 1 and contacts[0].show == 'offline':
			self.remove_contact(account, contacts[0])
		# If same JID with same resource already exists, use the new one
		for c in contacts:
			if c.resource == contact.resource:
				self.remove_contact(account, c)
				break
		contacts.append(contact)

	def remove_contact(self, account, contact):
		if not self._contacts.has_key(account):
			return
		if not self._contacts[account].has_key(contact.jid):
			return
		if contact in self._contacts[account][contact.jid]:
			self._contacts[account][contact.jid].remove(contact)

	def remove_jid(self, account, jid):
		'''Removes all contacts for a given jid'''
		if not self._contacts.has_key(account):
			return
		if not self._contacts[account].has_key(jid):
			return
		del self._contacts[account][jid]
		if self._parent_meta_contacts[account].has_key(jid):
			self.remove_subcontact(account, jid)
		if self._children_meta_contacts[account].has_key(jid):
			for cjid in self._children_meta_contacts[account][jid]:
				self.remove_subcontact(account, cjid)

	def get_contact(self, account, jid, resource = None):
		'''Returns the list of contact instances for this jid (one per resource)
		if no resource is given
		returns the contact instance for the given resource if it's given
		or None if there is not'''
		if jid in self._contacts[account]:
			contacts = self._contacts[account][jid]
			if not resource:
				return contacts
			for c in contacts:
				if c.resource == resource:
					return c
		return None

	def get_contacts_from_jid(self, account, jid):
		''' we may have two or more resources on that jid '''
		if jid in self._contacts[account]:
			contacts_instances = self._contacts[account][jid]
			return contacts_instances
		return []

	def get_highest_prio_contact_from_contacts(self, contacts):
		if not contacts:
			return None
		prim_contact = contacts[0]
		for contact in contacts[1:]:
			if int(contact.priority) > int(prim_contact.priority):
				prim_contact = contact
		return prim_contact

	def get_contact_with_highest_priority(self, account, jid):
		contacts = self.get_contacts_from_jid(account, jid)
		if not contacts and '/' in jid:
			# jid may be a nick jid, try it
			room, nick = jid.split('/')
			contact = self.get_gc_contact(account, room, nick)
			return contact or []
		return self.get_highest_prio_contact_from_contacts(contacts)

	def get_first_contact_from_jid(self, account, jid):
		if jid in self._contacts[account]:
			return self._contacts[account][jid][0]
		return None

	def define_meta_contacts(self, account, children_list):
		self._children_meta_contacts[account] = children_list
		self._parent_meta_contacts[account] = {}
		for parent_jid in children_list:
			for children_jid in children_list[parent_jid]:
				self._parent_meta_contacts[account][children_jid] = parent_jid
	
	def add_subcontact(self, account, parent_jid, child_jid):
		self._parent_meta_contacts[account][child_jid] = parent_jid
		if self._children_meta_contacts[account].has_key(parent_jid):
			self._children_meta_contacts[account][parent_jid].append(child_jid)
		else:
			self._children_meta_contacts[account][parent_jid] = [child_jid]
		common.gajim.connections[account].store_meta_contacts(
			self._children_meta_contacts[account])

	def remove_subcontact(self, account, child_jid):
		parent_jid = self._parent_meta_contacts[account][child_jid]
		self._children_meta_contacts[account][parent_jid].remove(child_jid)
		if len(self._children_meta_contacts[account][parent_jid]) == 0:
			del self._children_meta_contacts[account][parent_jid]
		del self._parent_meta_contacts[account][child_jid]
		common.gajim.connections[account].store_meta_contacts(
			self._children_meta_contacts[account])

	def is_subcontact(self, account, contact):
		jid = contact.jid
		if jid in self._parent_meta_contacts[account] and \
			self._contacts[account].has_key(
			self._parent_meta_contacts[account][jid]):
			return True

	def has_children(self, account, contact):
		jid = contact.jid
		if jid in self._children_meta_contacts[account]:
			for c in self._children_meta_contacts[account][jid]:
				if self._contacts[account].has_key(c):
					return True

	def get_children_contacts(self, account, contact):
		'''Returns the children contacts of contact if it's a parent-contact,
		else []'''
		jid = contact.jid
		if jid not in self._children_meta_contacts[account]:
			return []
		contacts = []
		for j in self._children_meta_contacts[account][jid]:
			c = self.get_contact_with_highest_priority(account, j)
			if c:
				contacts.append(c)
		return contacts

	def get_parent_contact(self, account, contact):
		'''Returns the parent contact of contact if it's a sub-contact,
		else contact'''
		if self.is_subcontact(account, contact):
			parent_jid = self._parent_meta_contacts[account][contact.jid]
			return self.get_contact_with_highest_priority(account, parent_jid)
		return contact

	def get_master_contact(self, account, contact):
		'''Returns the master contact of contact (parent of parent...) if it's a
		sub-contact, else contact'''
		while self.is_subcontact(account, contact):
			parent_jid = self._parent_meta_contacts[account][contact.jid]
			contact = self.get_contact_with_highest_priority(account, parent_jid)
		return contact

	def is_pm_from_jid(self, account, jid):
		'''Returns True if the given jid is a private message jid'''
		if jid in self._contacts[account]:
			return False
		return True

	def is_pm_from_contact(self, account, contact):
		'''Returns True if the given contact is a private message contact'''
		if isinstance(contact, Contact):
			return False
		return True

	def get_jid_list(self, account):
		return self._contacts[account].keys()

	def contact_from_gc_contact(self, gc_contact):
		'''Create a Contact instance from a GC_Contact instance'''
		jid = gc_contact.get_full_jid()
		return Contact(jid = jid, resource = '', name = gc_contact.name,
			groups = ['none'], show = gc_contact.show, status = gc_contact.status,
			sub = 'none')

	def create_gc_contact(self, room_jid='', name='', show='', status='',
		role='', affiliation='', jid='', resource=''):
		return GC_Contact(room_jid, name, show, status, role, affiliation, jid,
			resource)
	
	def add_gc_contact(self, account, gc_contact):
		# No such account before ?
		if not self._gc_contacts.has_key(account):
			self._contacts[account] = {gc_contact.room_jid : {gc_contact.name: \
				gc_contact}}
			return
		# No such room_jid before ?
		if not self._gc_contacts[account].has_key(gc_contact.room_jid):
			self._gc_contacts[account][gc_contact.room_jid] = {gc_contact.name: \
				gc_contact}
			return
		self._gc_contacts[account][gc_contact.room_jid][gc_contact.name] = \
				gc_contact

	def remove_gc_contact(self, account, gc_contact):
		if not self._gc_contacts.has_key(account):
			return
		if not self._gc_contacts[account].has_key(gc_contact.room_jid):
			return
		if not self._gc_contacts[account][gc_contact.room_jid].has_key(
			gc_contact.name):
			return
		del self._gc_contacts[account][gc_contact.room_jid][gc_contact.name]
		# It was the last nick in room ?
		if not len(self._gc_contacts[account][gc_contact.room_jid]):
			del self._gc_contacts[account][gc_contact.room_jid]

	def remove_room(self, account, room_jid):
		if not self._gc_contacts.has_key(account):
			return
		if not self._gc_contacts[account].has_key(room_jid):
			return
		del self._gc_contacts[account][room_jid]

	def get_gc_list(self, account):
		if not self._gc_contacts.has_key(account):
			return []
		return self._gc_contacts[account].keys()

	def get_nick_list(self, account, room_jid):
		gc_list = self.get_gc_list(account)
		if not room_jid in gc_list:
			return []
		return self._gc_contacts[account][room_jid].keys()

	def get_gc_contact(self, account, room_jid, nick):
		nick_list = self.get_nick_list(account, room_jid)
		if not nick in nick_list:
			return None
		return self._gc_contacts[account][room_jid][nick]
