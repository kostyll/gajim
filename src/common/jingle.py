##
## Copyright (C) 2006 Gajim Team
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
''' Handles the jingle signalling protocol. '''

#TODO:
# * things in XEP 0166, including:
#   - 'senders' attribute of 'content' element
#   - security preconditions
#   * actions:
#     - content-accept, content-reject, content-add, content-modify
#     - description-info, session-info
#     - security-info
#     - transport-accept, transport-reject
#   * sid/content related:
#      - tiebreaking
#      - if there already is a session, use it
# * things in XEP 0176, including:
#      - http://xmpp.org/extensions/xep-0176.html#protocol-restarts
#      - http://xmpp.org/extensions/xep-0176.html#fallback
# * XEP 0177 (raw udp)

# * UI:
#   - hang up button!
#   - make state and codec informations available to the user
#   * config:
#     - codecs
#     - STUN
# * DONE: figure out why it doesn't work with pidgin:
#     That's a bug in pidgin: http://xmpp.org/extensions/xep-0176.html#protocol-checks
# * destroy sessions when user is unavailable, see handle_event_notify?
# * timeout
# * video
# * security (see XEP 0166)

# * split this file in several modules
#   For example, a file dedicated for XEP0166, one for XEP0176,
#   and one for each media of XEP0167

# * handle different kinds of sink and src elements

import gajim
import gobject
import xmpp

import farsight, gst

def get_first_gst_element(elements):
	''' Returns, if it exists, the first available element of the list. '''
	for name in elements:
		factory = gst.element_factory_find(name)
		if factory:
			return factory.create()

#FIXME: Move it to JingleSession.States?
class JingleStates(object):
	''' States in which jingle session may exist. '''
	ended=0
	pending=1
	active=2

#FIXME: Move it to JingleTransport.Type?
class TransportType(object):
	''' Possible types of a JingleTransport '''
	datagram = 1
	streaming = 2

class Error(Exception): pass
class WrongState(Error): pass

class OutOfOrder(Exception):
	''' Exception that should be raised when an action is received when in the wrong state. '''

class JingleSession(object):
	''' This represents one jingle session. '''
	def __init__(self, con, weinitiate, jid, sid=None):
		''' con -- connection object,
			 weinitiate -- boolean, are we the initiator?
			 jid - jid of the other entity'''
		self.contents = {} # negotiated contents
		self.connection = con # connection to use
		# our full jid
		self.ourjid = gajim.get_jid_from_account(self.connection.name) + '/' + \
			con.server_resource
		self.peerjid = jid # jid we connect to
		# jid we use as the initiator
		self.initiator = weinitiate and self.ourjid or self.peerjid
		# jid we use as the responder
		self.responder = weinitiate and self.peerjid or self.ourjid
		# are we an initiator?
		self.weinitiate = weinitiate
		# what state is session in? (one from JingleStates)
		self.state = JingleStates.ended
		if not sid:
			sid = con.connection.getAnID()
		self.sid = sid # sessionid

		self.accepted = True # is this session accepted by user

		# callbacks to call on proper contents
		# use .prepend() to add new callbacks, especially when you're going
		# to send error instead of ack
		self.callbacks={
			'content-accept':	[self.__contentAcceptCB, self.__defaultCB],
			'content-add':		[self.__defaultCB], #TODO
			'content-modify':	[self.__defaultCB], #TODO
			'content-reject':	[self.__defaultCB], #TODO
			'content-remove':	[self.__defaultCB, self.__contentRemoveCB],
			'description-info':	[self.__defaultCB], #TODO
			'security-info':	[self.__defaultCB], #TODO
			'session-accept':	[self.__sessionAcceptCB, self.__contentAcceptCB,
				self.__broadcastCB, self.__defaultCB],
			'session-info':		[self.__sessionInfoCB, self.__broadcastCB],
			'session-initiate':	[self.__sessionInitiateCB, self.__broadcastCB,
				self.__defaultCB],
			'session-terminate':	[self.__sessionTerminateCB, self.__broadcastAllCB,
				self.__defaultCB],
			'transport-info':	[self.__broadcastCB, self.__defaultCB],
			'transport-replace':	[self.__broadcastCB, self.__transportReplaceCB], #TODO
			'transport-accept':	[self.__defaultCB], #TODO
			'transport-reject':	[self.__defaultCB], #TODO
			'iq-result':		[],
			'iq-error':		[self.__errorCB],
		}

	''' Interaction with user '''
	def approveSession(self):
		''' Called when user accepts session in UI (when we aren't the initiator).
		'''
		self.accepted = True
		self.acceptSession()

	def declineSession(self):
		''' Called when user declines session in UI (when we aren't the initiator)
		'''
		reason = xmpp.Node('reason')
		reason.addChild('decline')
		self.__sessionTerminate(reason)

	def end_session(self):
		reason = xmpp.Node('reason')
		if self.state == JingleStates.active:
			reason.addChild('success')
		else:
			reason.addChild('cancel')
		self.__sessionTerminate(reason)

	''' Middle-level functions to manage contents. Handle local content
	cache and send change notifications. '''
	def addContent(self, name, content, creator='we'):
		''' Add new content to session. If the session is active,
		this will send proper stanza to update session. 
		The protocol prohibits changing that when pending.
		Creator must be one of ('we', 'peer', 'initiator', 'responder')'''
		assert creator in ('we', 'peer', 'initiator', 'responder')

		if self.state == JingleStates.pending:
			raise WrongState

		if (creator == 'we' and self.weinitiate) or (creator == 'peer' and \
		not self.weinitiate):
			creator = 'initiator'
		elif (creator == 'peer' and self.weinitiate) or (creator == 'we' and \
		not self.weinitiate):
			creator = 'responder'
		content.creator = creator
		content.name = name
		self.contents[(creator,name)] = content

		if self.state == JingleStates.active:
			pass # TODO: send proper stanza, shouldn't be needed now

	def removeContent(self, creator, name):
		''' We do not need this now '''
		pass

	def modifyContent(self, creator, name, *someother):
		''' We do not need this now '''
		pass

	def acceptSession(self):
		''' Check if all contents and user agreed to start session. '''
		if not self.weinitiate and self.accepted and \
		all((i.candidates_ready for i in self.contents.itervalues())) and \
		all((i.p2psession.get_property('codecs-ready') for i in self.contents.itervalues())):
			self.__sessionAccept()

	''' Middle-level function to do stanza exchange. '''
	def startSession(self):
		''' Start session. '''
		if self.weinitiate and \
		all((i.candidates_ready for i in self.contents.itervalues())) and \
		all((i.p2psession.get_property('codecs-ready') for i in self.contents.itervalues())):
			self.__sessionInitiate()

	def sendSessionInfo(self): pass

	def sendContentAccept(self, content):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__makeJingle('content-accept')
		jingle.addChild(node=content)
		self.connection.connection.send(stanza)

	def sendTransportInfo(self, content):
		assert self.state!=JingleStates.ended
		stanza, jingle = self.__makeJingle('transport-info')
		jingle.addChild(node=content)
		self.connection.connection.send(stanza)

	''' Session callbacks. '''
	def stanzaCB(self, stanza):
		''' A callback for ConnectionJingle. It gets stanza, then
		tries to send it to all internally registered callbacks.
		First one to raise xmpp.NodeProcessed breaks function.'''
		jingle = stanza.getTag('jingle')
		error = stanza.getTag('error')
		if error:
			# it's an iq-error stanza
			action = 'iq-error'
		elif jingle:
			# it's a jingle action
			action = jingle.getAttr('action')
			if action not in self.callbacks:
				self.__send_error('bad_request')
				return
			#FIXME: If we aren't initiated and it's not a session-initiate...
			if action != 'session-initiate' and self.state == JingleStates.ended:
				self.__send_error('item-not-found', 'unknown-session')
				return
		else:
			# it's an iq-result (ack) stanza
			action = 'iq-result'

		callables = self.callbacks[action]

		try:
			for callable in callables:
				callable(stanza=stanza, jingle=jingle, error=error, action=action)
		except xmpp.NodeProcessed:
			pass
		except OutOfOrder:
			self.__send_error('unexpected-request', 'out-of-order')#FIXME

	def __defaultCB(self, stanza, jingle, error, action):
		''' Default callback for action stanzas -- simple ack
		and stop processing. '''
		response = stanza.buildReply('result')
		self.connection.connection.send(response)

	def __errorCB(self, stanza, jingle, error, action):
		#FIXME
		text = error.getTagData('text')
		jingle_error = None
		xmpp_error = None
		for child in error.getChildren():
			if child.getNamespace() == xmpp.NS_JINGLE_ERRORS:
				jingle_error = child.getName()
			elif child.getNamespace() == xmpp.NS_STANZAS:
				xmpp_error = child.getName()
		self.__dispatch_error(xmpp_error, jingle_error, text)
		#FIXME: Not sure if we would want to do that... not yet...
		#self.connection.deleteJingle(self)

	def __transportReplaceCB(self, stanza, jingle, error, action):
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']
			if (creator, name) in self.contents:
				transport_ns = content.getTag('transport').getNamespace()
				if transport_ns == xmpp.JINGLE_ICE_UDP:
					#FIXME: We don't manage anything else than ICE-UDP now...
					#What was the previous transport?!?
					#Anyway, content's transport is not modifiable yet
					pass
				else:
					stanza, jingle = self.__makeJingle('transport-reject')
					c = jingle.setTag('content', attrs={'creator': creator,
						'name': name})
					c.setTag('transport', namespace=transport_ns)
					self.connection.connection.send(stanza)
					raise xmpp.NodeProcessed
			else:
				#FIXME: This ressource is unknown to us, what should we do?
				#For now, reject the transport
				stanza, jingle = self.__makeJingle('transport-reject')
				c = jingle.setTag('content', attrs={'creator': creator,
					'name': name})
				c.setTag('transport', namespace=transport_ns)
				self.connection.connection.send(stanza)
				raise xmpp.NodeProcessed

	def __sessionInfoCB(self, stanza, jingle, error, action):
		payload = jingle.getPayload()
		if len(payload) > 0:
			self.__send_error('feature-not-implemented', 'unsupported-info')
			raise xmpp.NodeProcessed

	def __contentRemoveCB(self, stanza, jingle, error, action):
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']
			if (creator, name) in self.contents:
				del self.contents[(creator, name)]
		if len(self.contents) == 0:
			reason = xmpp.Node('reason')
			reason.setTag('success') #FIXME: Is it the good one?
			self.__sessionTerminate(reason)

	def __sessionAcceptCB(self, stanza, jingle, error, action):
		if self.state != JingleStates.pending: #FIXME
			raise OutOfOrder
		self.state = JingleStates.active

	def __contentAcceptCB(self, stanza, jingle, error, action):
		''' Called when we get content-accept stanza or equivalent one
		(like session-accept).'''
		# check which contents are accepted
		for content in jingle.iterTags('content'):
			creator = content['creator']
			name = content['name']#TODO...

	def __sessionInitiateCB(self, stanza, jingle, error, action):
		''' We got a jingle session request from other entity,
		therefore we are the receiver... Unpack the data,
		inform the user. '''
		if self.state != JingleStates.ended: #FIXME
			raise OutOfOrder

		self.initiator = jingle['initiator']
		self.responder = self.ourjid
		self.peerjid = self.initiator
		self.accepted = False	# user did not accept this session yet

		# TODO: If the initiator is unknown to the receiver (e.g., via presence
		# subscription) and the receiver has a policy of not communicating via
		# Jingle with unknown entities, it SHOULD return a <service-unavailable/>
		# error.

		# Lets check what kind of jingle session does the peer want
		contents = []
		contents_ok = False
		transports_ok = False
		for element in jingle.iterTags('content'):
			# checking what kind of session this will be
			desc_ns = element.getTag('description').getNamespace()
			media = element.getTag('description')['media']
			tran_ns = element.getTag('transport').getNamespace()
			if desc_ns == xmpp.NS_JINGLE_RTP and media in ('audio', 'video'):
				contents_ok = True
				if tran_ns == xmpp.NS_JINGLE_ICE_UDP:
					# we've got voip content
					if media == 'audio':
						self.addContent(element['name'], JingleVoIP(self), 'peer')
					else:
						self.addContent(element['name'], JingleVideo(self), 'peer')
					contents.append((media,))
					transports_ok = True

		# If there's no content we understand...
		if not contents_ok:
			# TODO: http://xmpp.org/extensions/xep-0166.html#session-terminate
			reason = xmpp.Node('reason')
			reason.setTag('unsupported-applications')
			self.__defaultCB(stanza, jingle, error, action)
			self.__sessionTerminate(reason)
			raise xmpp.NodeProcessed

		if not transports_ok:
			# TODO: http://xmpp.org/extensions/xep-0166.html#session-terminate
			reason = xmpp.Node('reason')
			reason.setTag('unsupported-transports')
			self.__defaultCB(stanza, jingle, error, action)
			self.__sessionTerminate(reason)
			raise xmpp.NodeProcessed

		self.state = JingleStates.pending

		# Send event about starting a session
		self.connection.dispatch('JINGLE_INCOMING', (self.initiator, self.sid,
			contents))

	def __broadcastCB(self, stanza, jingle, error, action):
		''' Broadcast the stanza contents to proper content handlers. '''
		for content in jingle.iterTags('content'):
			name = content['name']
			creator = content['creator']
			cn = self.contents[(creator, name)]
			cn.stanzaCB(stanza, content, error, action)

	def __sessionTerminateCB(self, stanza, jingle, error, action):
		self.connection.deleteJingle(self)
		reason, text = self.__reason_from_stanza(jingle)
		if reason not in ('success', 'cancel', 'decline'):
			self.__dispatch_error(reason, reason, text)
		if text:
			text = '%s (%s)' % (reason, text)
		else:
			text = reason#TODO
		self.connection.dispatch('JINGLE_DISCONNECTED', (self.peerjid, self.sid, text))

	def __send_error(self, stanza, error, jingle_error=None, text=None):
		err = xmpp.Error(stanza, error)
		err.setNamespace(xmpp.NS_STANZAS)
		if jingle_error:
			err.setTag(jingle_error, namespace=xmpp.NS_JINGLE_ERRORS)
		if text:
			err.setTagData('text', text)
		self.connection.connection.send(err)
		self.__dispatch_error(error, jingle_error, text)

	def __dispatch_error(error, jingle_error=None, text=None):
		if jingle_error:
			error = jingle_error
		if text:
			text = '%s (%s)' % (error, text)
		else:
			text = error
		self.connection.dispatch('JINGLE_ERROR', (self.peerjid, self.sid, text))

	def __broadcastAllCB(self, stanza, jingle, error, action):
		''' Broadcast the stanza to all content handlers. '''
		for content in self.contents.itervalues():
			content.stanzaCB(stanza, None, error, action)

	def __reason_from_stanza(self, stanza):
		reason = 'success'
		reasons = ['success', 'busy', 'cancel', 'connectivity-error',
			'decline', 'expired', 'failed-application', 'failed-transport',
			'general-error', 'gone', 'incompatible-parameters', 'media-error',
			'security-error', 'timeout', 'unsupported-applications',
			'unsupported-transports']
		tag = stanza.getTag('reason')
		if tag:
			text = tag.getTagData('text')
			for r in reasons:
				if tag.getTag(r):
					reason = r
					break
		return (reason, text)

	''' Methods that make/send proper pieces of XML. They check if the session
	is in appropriate state. '''
	def __makeJingle(self, action):
		stanza = xmpp.Iq(typ='set', to=xmpp.JID(self.peerjid))
		attrs = {'action': action,
			'sid': self.sid}
		if action == 'session-initiate':
			attrs['initiator'] = self.initiator
		elif action == 'session-accept':
			attrs['responder'] = self.responder
		jingle = stanza.addChild('jingle', attrs=attrs, namespace=xmpp.NS_JINGLE)
		return stanza, jingle

	def __appendContent(self, jingle, content):
		''' Append <content/> element to <jingle/> element,
		with (full=True) or without (full=False) <content/>
		children. '''
		jingle.addChild('content',
			attrs={'name': content.name, 'creator': content.creator})

	def __appendContents(self, jingle):
		''' Append all <content/> elements to <jingle/>.'''
		# TODO: integrate with __appendContent?
		# TODO: parameters 'name', 'content'?
		for content in self.contents.values():
			self.__appendContent(jingle, content)

	def __sessionInitiate(self):
		assert self.state==JingleStates.ended
		stanza, jingle = self.__makeJingle('session-initiate')
		self.__appendContents(jingle)
		self.__broadcastCB(stanza, jingle, None, 'session-initiate-sent')
		self.connection.connection.send(stanza)
		self.state = JingleStates.pending

	def __sessionAccept(self):
		assert self.state==JingleStates.pending
		stanza, jingle = self.__makeJingle('session-accept')
		self.__appendContents(jingle)
		self.__broadcastCB(stanza, jingle, None, 'session-accept-sent')
		self.connection.connection.send(stanza)
		self.state = JingleStates.active

	def __sessionInfo(self, payload=None):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__makeJingle('session-info')
		if payload:
			jingle.addChild(node=payload)
		self.connection.connection.send(stanza)

	def __sessionTerminate(self, reason=None):
		assert self.state != JingleStates.ended
		stanza, jingle = self.__makeJingle('session-terminate')
		if reason is not None:
			jingle.addChild(node=reason)
		self.__broadcastAllCB(stanza, jingle, None, 'session-terminate-sent')
		self.connection.connection.send(stanza)
		reason, text = self.__reason_from_stanza(jingle)
		if reason not in ('success', 'cancel', 'decline'):
			self.__dispatch_error(reason, reason, text)
		if text:
			text = '%s (%s)' % (reason, text)
		else:
			text = reason
		self.connection.dispatch('JINGLE_DISCONNECTED', (self.peerjid, self.sid, text))
		self.connection.deleteJingle(self)

	def __contentAdd(self):
		assert self.state == JingleStates.active

	def __contentAccept(self):
		assert self.state != JingleStates.ended

	def __contentModify(self):
		assert self.state != JingleStates.ended

	def __contentRemove(self):
		assert self.state != JingleStates.ended

	def content_negociated(self, media):
		self.connection.dispatch('JINGLE_CONNECTED', (self.peerjid, self.sid,
			media))

class JingleTransport(object):
	''' An abstraction of a transport in Jingle sessions. '''
	#TODO: Complete
	def __init__(self):
		pass#TODO: Complete


class JingleContent(object):
	''' An abstraction of content in Jingle sessions. '''
	def __init__(self, session, node=None):
		self.session = session
		# will be filled by JingleSession.add_content()
		# don't uncomment these lines, we will catch more buggy code then
		# (a JingleContent not added to session shouldn't send anything)
		#self.creator = None
		#self.name = None
		self.negotiated = False		# is this content already negotiated?
		self.candidates = [] # Local transport candidates

		self.senders = 'both' #FIXME
		self.allow_sending = True # Used for stream direction, attribute 'senders'

		self.callbacks = {
			# these are called when *we* get stanzas
			'content-accept': [],
			'content-add': [],
			'content-modify': [],
			'content-remove': [],
			'session-accept': [self.__transportInfoCB],
			'session-info': [],
			'session-initiate': [self.__transportInfoCB],
			'session-terminate': [],
			'transport-info': [self.__transportInfoCB],
			'iq-result': [],
			'iq-error': [],
			# these are called when *we* sent these stanzas
			'session-initiate-sent': [self.__fillJingleStanza],
			'session-accept-sent': [self.__fillJingleStanza],
			'session-terminate-sent': [],
		}

	def stanzaCB(self, stanza, content, error, action):
		''' Called when something related to our content was sent by peer. '''
		if action in self.callbacks:
			for callback in self.callbacks[action]:
				callback(stanza, content, error, action)

	def __transportInfoCB(self, stanza, content, error, action):
		''' Got a new transport candidate. '''
		candidates = []
		transport = content.getTag('transport')
		for candidate in transport.iterTags('candidate'):
			cand = farsight.Candidate()
			cand.component_id = int(candidate['component'])
			cand.ip = str(candidate['ip'])
			cand.port = int(candidate['port'])
			cand.foundation = str(candidate['foundation'])
			#cand.type = farsight.CANDIDATE_TYPE_LOCAL
			cand.priority = int(candidate['priority'])

			if candidate['protocol'] == 'udp':
				cand.proto=farsight.NETWORK_PROTOCOL_UDP
			else:
				# we actually don't handle properly different tcp options in jingle
				cand.proto = farsight.NETWORK_PROTOCOL_TCP

			cand.username = str(transport['ufrag'])
			cand.password = str(transport['pwd'])

			#FIXME: huh?
			types = {'host': farsight.CANDIDATE_TYPE_HOST,
						'srflx': farsight.CANDIDATE_TYPE_SRFLX,
						'prflx': farsight.CANDIDATE_TYPE_PRFLX,
						'relay': farsight.CANDIDATE_TYPE_RELAY,
						'multicast': farsight.CANDIDATE_TYPE_MULTICAST}
			if 'type' in candidate and candidate['type'] in types:
				cand.type = types[candidate['type']]
			candidates.append(cand)
		#FIXME: connectivity should not be etablished yet
		# Instead, it should be etablished after session-accept!
		if len(candidates) > 0:
			self.p2pstream.set_remote_candidates(candidates)

	def __content(self, payload=[]):
		''' Build a XML content-wrapper for our data. '''
		return xmpp.Node('content',
			attrs={'name': self.name, 'creator': self.creator},
			payload=payload)

	def __candidate(self, candidate):
		types = {farsight.CANDIDATE_TYPE_HOST: 'host',
			farsight.CANDIDATE_TYPE_SRFLX: 'srlfx',
			farsight.CANDIDATE_TYPE_PRFLX: 'prlfx',
			farsight.CANDIDATE_TYPE_RELAY: 'relay',
			farsight.CANDIDATE_TYPE_MULTICAST: 'multicast'}
		attrs={
			'component': candidate.component_id,
			'foundation': '1', # hack
			'generation': '0',
			'ip': candidate.ip,
			'network': '0',
			'port': candidate.port,
			'priority': int(candidate.priority), # hack
		}
		if candidate.type in types:
			attrs['type'] = types[candidate.type]
		if candidate.proto==farsight.NETWORK_PROTOCOL_UDP:
			attrs['protocol'] = 'udp'
		else:
			# we actually don't handle properly different tcp options in jingle
			attrs['protocol'] = 'tcp'
		return xmpp.Node('candidate', attrs=attrs)

	def iterCandidates(self):
		for candidate in self.candidates:
			yield self.__candidate(candidate)

	def send_candidate(self, candidate):
		c = self.__content()
		t = c.addChild(xmpp.NS_JINGLE_ICE_UDP + ' transport')

		if candidate.username: t['ufrag'] = candidate.username
		if candidate.password: t['pwd'] = candidate.password

		t.addChild(node=self.__candidate(candidate))
		self.session.sendTransportInfo(c)

	def __fillJingleStanza(self, stanza, content, error, action):
		''' Add our things to session-initiate stanza. '''
		self._fillContent(content)

		if self.candidates and self.candidates[0].username and \
		self.candidates[0].password:
			attrs = {'ufrag': self.candidates[0].username,
				'pwd': self.candidates[0].password}
		else:
			attrs = {}
		content.addChild(xmpp.NS_JINGLE_ICE_UDP + ' transport', attrs=attrs,
			payload=self.iterCandidates())

class JingleRTPContent(JingleContent):
	def __init__(self, session, media, node=None):
		JingleContent.__init__(self, session, node)
		self.media = media
		self.farsight_media = {'audio': farsight.MEDIA_TYPE_AUDIO,
								'video': farsight.MEDIA_TYPE_VIDEO}[media]
		self.got_codecs = False

		self.candidates_ready = False # True when local candidates are prepared

		self.callbacks['content-accept'] += [self.__getRemoteCodecsCB]
		self.callbacks['session-accept'] += [self.__getRemoteCodecsCB]
		self.callbacks['session-initiate'] += [self.__getRemoteCodecsCB]
		self.callbacks['session-terminate'] += [self.__stop]
		self.callbacks['session-terminate-sent'] += [self.__stop]

	def setupStream(self):
		# pipeline and bus
		self.pipeline = gst.Pipeline()
		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.connect('message', self._on_gst_message)

		# conference
		self.conference = gst.element_factory_make('fsrtpconference')
		self.conference.set_property("sdes-cname", self.session.ourjid)
		self.pipeline.add(self.conference)
		self.funnel = None

		self.p2psession = self.conference.new_session(self.farsight_media)

		participant = self.conference.new_participant(self.session.peerjid)
		params = {'controlling-mode': self.session.weinitiate,# 'debug': False}
			'stun-ip': '69.0.208.27', 'debug': False}

		self.p2pstream = self.p2psession.new_stream(participant,
			farsight.DIRECTION_RECV, 'nice', params)

	def _fillContent(self, content):
		content.addChild(xmpp.NS_JINGLE_RTP + ' description',
			attrs={'media': self.media}, payload=self.iterCodecs())

	def _on_gst_message(self, bus, message):
		if message.type == gst.MESSAGE_ELEMENT:
			name = message.structure.get_name()
			#print name
			if name == 'farsight-new-active-candidate-pair':
				pass
			elif name == 'farsight-recv-codecs-changed':
				pass
			elif name == 'farsight-codecs-changed':
				self.session.acceptSession()
				self.session.startSession()
			elif name == 'farsight-local-candidates-prepared':
				self.candidates_ready = True
				self.session.acceptSession()
				self.session.startSession()
			elif name == 'farsight-new-local-candidate':
				candidate = message.structure['candidate']
				self.candidates.append(candidate)
				if self.candidates_ready:
					#FIXME: Is this case even possible?
					self.send_candidate(candidate)
			elif name == 'farsight-component-state-changed':
				state = message.structure['state']
				print message.structure['component'], state
				if state == farsight.STREAM_STATE_READY:
					self.negotiated = True
					#TODO: farsight.DIRECTION_BOTH only if senders='both'
					self.p2pstream.set_property('direction', farsight.DIRECTION_BOTH)
					self.session.content_negociated(self.media)
					#if not self.session.weinitiate: #FIXME: one more FIXME...
					#	self.session.sendContentAccept(self.__content((xmpp.Node(
					#		'description', payload=self.iterCodecs()),)))
			elif name == 'farsight-error':
				print 'Farsight error #%d!' % message.structure['error-no']
				print 'Message: %s' % message.structure['error-msg']
				print 'Debug: %s' % message.structure['debug-msg']
			else:
				print name

	def __getRemoteCodecsCB(self, stanza, content, error, action):
		''' Get peer codecs from what we get from peer. '''
		if self.got_codecs: return

		codecs = []
		for codec in content.getTag('description').iterTags('payload-type'):
			c = farsight.Codec(int(codec['id']), codec['name'],
				self.farsight_media, int(codec['clockrate']))
			if 'channels' in codec:
				c.channels = int(codec['channels'])
			else:
				c.channels = 1
			c.optional_params = [(str(p['name']), str(p['value'])) for p in \
				codec.iterTags('parameter')]
			codecs.append(c)
		if len(codecs) == 0: return

		#FIXME: Handle this case:
		# glib.GError: There was no intersection between the remote codecs and
		# the local ones
		self.p2pstream.set_remote_codecs(codecs)
		self.got_codecs = True

	def iterCodecs(self):
		codecs=self.p2psession.get_property('codecs')
		for codec in codecs:
			a = {'name': codec.encoding_name,
				'id': codec.id,
				'channels': codec.channels}
			if codec.clock_rate: a['clockrate']=codec.clock_rate
			if codec.optional_params:
				p = (xmpp.Node('parameter', {'name': name, 'value': value})
					for name, value in codec.optional_params)
			else:	p = ()
			yield xmpp.Node('payload-type', a, p)

	def __stop(self, *things):
		self.pipeline.set_state(gst.STATE_NULL)

	def __del__(self):
		self.__stop()


class JingleVoIP(JingleRTPContent):
	''' Jingle VoIP sessions consist of audio content transported
	over an ICE UDP protocol. '''
	def __init__(self, session, node=None):
		JingleRTPContent.__init__(self, session, 'audio', node)
		self.setupStream()


	''' Things to control the gstreamer's pipeline '''
	def setupStream(self):
		JingleRTPContent.setupStream(self)

		# Configure SPEEX
		#FIXME: codec ID is an important thing for psi (and pidgin?)
		# So, if it doesn't work with pidgin or psi, LOOK AT THIS
		codecs = [farsight.Codec(farsight.CODEC_ID_ANY, 'SPEEX',
			farsight.MEDIA_TYPE_AUDIO, 8000),
			farsight.Codec(farsight.CODEC_ID_ANY, 'SPEEX',
			farsight.MEDIA_TYPE_AUDIO, 16000)]
		self.p2psession.set_codec_preferences(codecs)

		# the local parts
		# TODO: use gconfaudiosink?
		# sink = get_first_gst_element(['alsasink', 'osssink', 'autoaudiosink'])
		sink = gst.element_factory_make('alsasink')
		sink.set_property('sync', False)
		#sink.set_property('latency-time', 20000)
		#sink.set_property('buffer-time', 80000)

		# TODO: use gconfaudiosrc?
		src_mic = gst.element_factory_make('alsasrc')
		src_mic.set_property('blocksize', 320)

		self.mic_volume = gst.element_factory_make('volume')
		self.mic_volume.set_property('volume', 1)

		# link gst elements
		self.pipeline.add(sink, src_mic, self.mic_volume)
		src_mic.link(self.mic_volume)

		def src_pad_added (stream, pad, codec):
			if not self.funnel:
				self.funnel = gst.element_factory_make('fsfunnel')
				self.pipeline.add(self.funnel)
				self.funnel.set_state (gst.STATE_PLAYING)
				sink.set_state (gst.STATE_PLAYING)
				self.funnel.link(sink)
			pad.link(self.funnel.get_pad('sink%d'))

		self.mic_volume.get_pad('src').link(self.p2psession.get_property(
			'sink-pad'))
		self.p2pstream.connect('src-pad-added', src_pad_added)

		# The following is needed for farsight to process ICE requests:
		self.pipeline.set_state(gst.STATE_PLAYING)


class JingleVideo(JingleRTPContent):
	def __init__(self, session, node=None):
		JingleRTPContent.__init__(self, session, 'video', node)
		self.setupStream()

	''' Things to control the gstreamer's pipeline '''
	def setupStream(self):
		#TODO: Everything is not working properly:
		# sometimes, one window won't show up,
		# sometimes it'll freeze...
		JingleRTPContent.setupStream(self)
		# the local parts
		src_vid = gst.element_factory_make('videotestsrc')
		videoscale = gst.element_factory_make('videoscale')
		caps = gst.element_factory_make('capsfilter')
		caps.set_property('caps', gst.caps_from_string('video/x-raw-yuv, width=320, height=240'))
		colorspace = gst.element_factory_make('ffmpegcolorspace')

		self.pipeline.add(src_vid, videoscale, caps, colorspace)
		gst.element_link_many(src_vid, videoscale, caps, colorspace)

		def src_pad_added (stream, pad, codec):
			if not self.funnel:
				self.funnel = gst.element_factory_make('fsfunnel')
				self.pipeline.add(self.funnel)
				videosink = gst.element_factory_make('xvimagesink')
				self.pipeline.add(videosink)
				self.funnel.set_state (gst.STATE_PLAYING)
				videosink.set_state(gst.STATE_PLAYING)
				self.funnel.link(videosink)
			pad.link(self.funnel.get_pad('sink%d'))

		colorspace.get_pad('src').link(self.p2psession.get_property('sink-pad'))
		self.p2pstream.connect('src-pad-added', src_pad_added)

		# The following is needed for farsight to process ICE requests:
		self.pipeline.set_state(gst.STATE_PLAYING)


class ConnectionJingle(object):
	''' This object depends on that it is a part of Connection class. '''
	def __init__(self):
		# dictionary: (jid, sessionid) => JingleSession object
		self.__sessions = {}

		# dictionary: (jid, iq stanza id) => JingleSession object,
		# one time callbacks
		self.__iq_responses = {}

	def addJingle(self, jingle):
		''' Add a jingle session to a jingle stanza dispatcher
		jingle - a JingleSession object.
		'''
		self.__sessions[(jingle.peerjid, jingle.sid)] = jingle

	def deleteJingle(self, jingle):
		''' Remove a jingle session from a jingle stanza dispatcher '''
		del self.__sessions[(jingle.peerjid, jingle.sid)]

	def _JingleCB(self, con, stanza):
		''' The jingle stanza dispatcher.
		Route jingle stanza to proper JingleSession object,
		or create one if it is a new session.
		TODO: Also check if the stanza isn't an error stanza, if so
		route it adequatelly.'''

		# get data
		jid = stanza.getFrom()
		id = stanza.getID()

		if (jid, id) in self.__iq_responses.keys():
			self.__iq_responses[(jid, id)].stanzaCB(stanza)
			del self.__iq_responses[(jid, id)]
			raise xmpp.NodeProcessed

		jingle = stanza.getTag('jingle')
		if not jingle: return
		sid = jingle.getAttr('sid')

		# do we need to create a new jingle object
		if (jid, sid) not in self.__sessions:
			newjingle = JingleSession(con=self, weinitiate=False, jid=jid, sid=sid)
			self.addJingle(newjingle)

		# we already have such session in dispatcher...
		self.__sessions[(jid, sid)].stanzaCB(stanza)

		raise xmpp.NodeProcessed

	def addJingleIqCallback(self, jid, id, jingle):
		self.__iq_responses[(jid, id)] = jingle

	def startVoIP(self, jid):
		jingle = JingleSession(self, weinitiate=True, jid=jid)
		self.addJingle(jingle)
		jingle.addContent('voice', JingleVoIP(jingle))
		jingle.startSession()
		return jingle.sid

	def getJingleSession(self, jid, sid):
		try:
			return self.__sessions[(jid, sid)]
		except KeyError:
			return None
