##   client_nb.py
##	   based on client.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##	   modified by Dimitur Kirov <dkirov@gmail.com>
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.

# $Id: client.py,v 1.52 2006/01/02 19:40:55 normanr Exp $

import socket

import transports_nb, dispatcher_nb, auth_nb, roster_nb, protocol, bosh
from client import *

from protocol import NS_TLS

import logging
log = logging.getLogger('gajim.c.x.client_nb')


class NonBlockingClient:
	''' 
	Client class is XMPP connection mountpoint. Objects for authentication,
	network communication, roster, xml parsing ... are plugged to client object.
	Client implements the abstract behavior - mostly negotioation and callbacks
	handling, whereas underlying modules take care of feature-specific logic.
	'''
	def __init__(self, domain, idlequeue, caller=None):
		'''
		Caches connection data:
		:param domain: domain - for to: attribute (from account info)
		:param idlequeue: processing idlequeue
		:param caller: calling object - it has to implement method _event_dispatcher
		'''
		self.Namespace = protocol.NS_CLIENT
		self.defaultNamespace = self.Namespace
		
		self.idlequeue = idlequeue
		self.disconnect_handlers = []

		self.Server = domain
		
		# caller is who initiated this client, it is needed to register the EventDispatcher
		self._caller = caller
		self._owner = self
		self._registered_name = None
		self.connected = ''
		self.socket = None
		self.on_connect = None
		self.on_proxy_failure = None
		self.on_connect_failure = None
		self.proxy = None
		self.got_features = False
		self.stream_started = False
		self.disconnecting = False
		self.protocol_type = 'XMPP'
		
	
	def disconnect(self, message=''):
		'''
		Called on disconnection - disconnect callback is picked based on state of the
		client.
		'''

		# to avoid recursive calls
		if self.disconnecting: return

		log.warn('Disconnecting NBClient: %s' % message)

		if self.__dict__.has_key('NonBlockingRoster'):
			self.NonBlockingRoster.PlugOut()
		if self.__dict__.has_key('NonBlockingBind'):
			self.NonBlockingBind.PlugOut()
		if self.__dict__.has_key('NonBlockingNonSASL'):
			self.NonBlockingNonSASL.PlugOut()
		if self.__dict__.has_key('SASL'):
			self.SASL.PlugOut()
		if self.__dict__.has_key('NonBlockingTCP'):
			self.NonBlockingTCP.PlugOut()
		if self.__dict__.has_key('NonBlockingHTTP'):
			self.NonBlockingHTTP.PlugOut()
		if self.__dict__.has_key('NonBlockingBOSH'):
			self.NonBlockingBOSH.PlugOut()

		connected = self.connected
		stream_started = self.stream_started

		self.connected = ''
		self.stream_started = False

		self.disconnecting = True

		log.debug('Client disconnected..')
		if connected == '':
			# if we're disconnecting before connection to XMPP sever is opened, we don't
			# call disconnect handlers but on_connect_failure callback
			if self.proxy:
				# with proxy, we have different failure callback
				log.debug('calling on_proxy_failure cb')
				self.on_proxy_failure(reason=message)
			else:
				log.debug('ccalling on_connect_failure cb')
				self.on_connect_failure()
		else:
			# we are connected to XMPP server
			if not stream_started:
				# if error occur before XML stream was opened, e.g. no response on init
				# request, we call the on_connect_failure callback because proper
				# connection is not estabilished yet and it's not a proxy issue
				log.debug('calling on_connect_failure cb')
				self.on_connect_failure()
			else:
				# with open connection, we are calling the disconnect handlers
				for i in reversed(self.disconnect_handlers):
					log.debug('Calling disconnect handler %s' % i)
					i()
		self.disconnecting = False



	def connect(self, on_connect, on_connect_failure, hostname=None, port=5222, 
		on_proxy_failure=None, proxy=None, secure_tuple=None):
		''' 
		Open XMPP connection (open XML streams in both directions).
		:param hostname: hostname of XMPP server from SRV request 
		:param port: port number of XMPP server
		:param on_connect: called after stream is successfully opened
		:param on_connect_failure: called when error occures during connection
		:param on_proxy_failure: called if error occurres during TCP connection to
			proxy server or during proxy connecting process
		:param proxy: dictionary with proxy data. It should contain at least values
			for keys 'host' and 'port' - connection details for proxy server and
			optionally keys 'user' and 'pass' as proxy credentials
		:param secure_tuple: tuple of (desired connection type, cacerts and mycerts)
			connection type can be 'ssl' - TLS estabilished after TCP connection,
			'tls' - TLS estabilished after negotiation with starttls, or 'plain'.
			cacerts, mycerts - see tls_nb.NonBlockingTLS constructor for more details
		'''
		self.on_connect = on_connect
		self.on_connect_failure=on_connect_failure
		self.on_proxy_failure = on_proxy_failure
		self.secure, self.cacerts, self.mycerts = secure_tuple
		self.Connection = None
		self.Port = port
		self.proxy = proxy

		if hostname:
			xmpp_hostname = hostname
		else:
			xmpp_hostname = self.Server

		estabilish_tls = self.secure == 'ssl'
		certs = (self.cacerts, self.mycerts)

		proxy_dict = {}
		tcp_host=xmpp_hostname
		tcp_port=self.Port

		if proxy:
			# with proxies, client connects to proxy instead of directly to
			# XMPP server ((hostname, port))
			# tcp_host is hostname of machine used for socket connection
			# (DNS request will be done for proxy or BOSH CM hostname)
			tcp_host, tcp_port, proxy_user, proxy_pass = \
				transports_nb.get_proxy_data_from_dict(proxy)

		
			if proxy['type'] == 'bosh':
				self.socket = bosh.NonBlockingBOSH(
					on_disconnect = self.disconnect,
					raise_event = self.raise_event,
					idlequeue = self.idlequeue,
					estabilish_tls = estabilish_tls,
					certs = certs,
					proxy_creds = (proxy_user, proxy_pass),
					xmpp_server = (xmpp_hostname, self.Port),
					domain = self.Server,
					bosh_dict = proxy)
				self.protocol_type = 'BOSH'
				self.wait_for_restart_response = proxy['bosh_wait_for_restart_response']

			else:
				proxy_dict['type'] = proxy['type']
				proxy_dict['xmpp_server'] = (xmpp_hostname, self.Port)
				proxy_dict['credentials'] = (proxy_user, proxy_pass)

		if not proxy or proxy['type'] != 'bosh': 
			self.socket = transports_nb.NonBlockingTCP(
				on_disconnect = self.disconnect,
				raise_event = self.raise_event,
				idlequeue = self.idlequeue,
				estabilish_tls = estabilish_tls,
				certs = certs,
				proxy_dict = proxy_dict)

		self.socket.PlugIn(self)

		self._resolve_hostname(
			hostname=tcp_host,
			port=tcp_port,
			on_success=self._try_next_ip)
			

	def _resolve_hostname(self, hostname, port, on_success):
		''' wrapper for getaddinfo call. FIXME: getaddinfo blocks'''
		try:
			self.ip_addresses = socket.getaddrinfo(hostname,port,
				socket.AF_UNSPEC,socket.SOCK_STREAM)
		except socket.gaierror, (errnum, errstr):
			self.disconnect(message= 'Lookup failure for %s:%s, hostname: %s - %s' % 
				 (self.Server, self.Port, hostname, errstr))
		else:
			on_success()
		
		
	
	def _try_next_ip(self, err_message=None):
		'''iterates over IP addresses from getaddrinfo'''
		if err_message:
			log.debug('While looping over DNS A records: %s' % err_message)
		if self.ip_addresses == []:
			msg = 'Run out of hosts for name %s:%s.' % (self.Server, self.Port)
			msg = msg + ' Error for last IP: %s' % err_message
			self.disconnect(msg)
		else:
                        self.current_ip = self.ip_addresses.pop(0)
                        self.socket.connect(
				conn_5tuple=self.current_ip,
				on_connect=lambda: self._xmpp_connect(socket_type='plain'),
				on_connect_failure=self._try_next_ip)


	def incoming_stream_version(self):
		''' gets version of xml stream'''
		if self.Dispatcher.Stream._document_attrs.has_key('version'):
			return self.Dispatcher.Stream._document_attrs['version']
		else:
			return None

	def _xmpp_connect(self, socket_type):
		'''
		Starts XMPP connecting process - opens the XML stream. Is called after TCP
		connection is estabilished or after switch to TLS when successfully
		negotiated with <starttls>.
		'''
		if socket_type == 'plain' and self.Connection.ssl_lib: socket_type = 'ssl'
		self.connected = socket_type
		self._xmpp_connect_machine()


	def _xmpp_connect_machine(self, mode=None, data=None):
		'''
		Finite automaton taking care of stream opening and features tag
		handling. Calls _on_stream_start when stream is started, and disconnect() 
		on failure.
		'''
		log.info('-------------xmpp_connect_machine() >> mode: %s, data: %s...' % (mode,str(data)[:20] ))

		def on_next_receive(mode):
			log.info('setting %s on next receive' % mode)
			if mode is None:
				self.onreceive(None)
			else:
				self.onreceive(lambda _data:self._xmpp_connect_machine(mode, _data))

		if not mode:
			# starting state
			if self.__dict__.has_key('Dispatcher'): 
				self.Dispatcher.PlugOut()
				self.got_features = False
			d=dispatcher_nb.Dispatcher().PlugIn(self)
			on_next_receive('RECEIVE_DOCUMENT_ATTRIBUTES')

		elif mode == 'FAILURE':
			self.disconnect('During XMPP connect: %s' % data)

		elif mode == 'RECEIVE_DOCUMENT_ATTRIBUTES':
			if data:
				self.Dispatcher.ProcessNonBlocking(data)
			if not hasattr(self, 'Dispatcher') or \
				self.Dispatcher.Stream._document_attrs is None:
				self._xmpp_connect_machine(
					mode='FAILURE',
					data='Error on stream open')
			if self.incoming_stream_version() == '1.0':
				if not self.got_features: 
					on_next_receive('RECEIVE_STREAM_FEATURES')
				else:
					log.info('got STREAM FEATURES in first recv')
					self._xmpp_connect_machine(mode='STREAM_STARTED')

			else:
				log.info('incoming stream version less than 1.0')
				self._xmpp_connect_machine(mode='STREAM_STARTED')

		elif mode == 'RECEIVE_STREAM_FEATURES':
			if data:
				# sometimes <features> are received together with document
				# attributes and sometimes on next receive...
				self.Dispatcher.ProcessNonBlocking(data)
			if not self.got_features: 
				self._xmpp_connect_machine(
					mode='FAILURE',
					data='Missing <features> in 1.0 stream')
			else:
				log.info('got STREAM FEATURES in second recv')
				self._xmpp_connect_machine(mode='STREAM_STARTED')

		elif mode == 'STREAM_STARTED':
			self._on_stream_start()

	def _on_stream_start(self):
		'''
		Called after XMPP stream is opened.
		TLS negotiation may follow after esabilishing a stream.
		'''
		self.stream_started = True
		self.onreceive(None)
		if self.connected == 'plain':
			if self.secure == 'plain':
				# if we want plain connection, we're done now
				self._on_connect()
				return 
			if not self.Dispatcher.Stream.features.getTag('starttls'): 
				# if server doesn't advertise TLS in init response, we can't do more
				log.warn('While connecting with type = "tls": TLS unsupported by remote server')
				self._on_connect()
				return 
			if self.incoming_stream_version() != '1.0':
				# if stream version is less than 1.0, we can't do more 
				log.warn('While connecting with type = "tls": stream version is less than 1.0')
				self._on_connect()
				return
			# otherwise start TLS negotioation
			self.stream_started = False
			log.info("TLS supported by remote server. Requesting TLS start.")
			self._tls_negotiation_handler()
		elif self.connected in ['ssl', 'tls']:
			self._on_connect()


	def _tls_negotiation_handler(self, con=None, tag=None):
		''' takes care of TLS negotioation with <starttls> '''
		log.info('-------------tls_negotiaton_handler() >> tag: %s' % tag)
		if not con and not tag:
			# starting state when we send the <starttls>
			self.RegisterHandlerOnce('proceed', self._tls_negotiation_handler,
					xmlns=NS_TLS)
			self.RegisterHandlerOnce('failure', self._tls_negotiation_handler,
					xmlns=NS_TLS)
			self.send('<starttls xmlns="%s"/>' % NS_TLS)
		else:
			# we got <proceed> or <failure>
			if tag.getNamespace() <> NS_TLS: 
				self.disconnect('Unknown namespace: %s' % tag.getNamespace())
				return
			tagname = tag.getName()
			if tagname == 'failure':
				self.disconnect('TLS <failure>  received: %s' % tag)
				return
			log.info('Got starttls proceed response. Switching to TLS/SSL...')
			# following call wouldn't work for BOSH transport but it doesn't matter
			# because <starttls> negotiation with BOSH is forbidden
			self.Connection.tls_init(
				on_succ = lambda: self._xmpp_connect(socket_type='tls'),
				on_fail = lambda: self.disconnect('error while etabilishing TLS'))



	def _on_connect(self):
		''' preceeds call of on_connect callback '''
		self.onreceive(None)
		self.on_connect(self, self.connected)

	def raise_event(self, event_type, data):
		'''
		raises event to connection instance - DATA_SENT and DATA_RECIVED events are
		used in XML console to show XMPP traffic
		'''
		log.info('raising event from transport: >>>>>%s<<<<<\n_____________\n%s\n_____________\n' % (event_type,data))
		if hasattr(self, 'Dispatcher'):
			self.Dispatcher.Event('', event_type, data)
		
	

	# follows code for authentication, resource bind, session and roster download
	# 
	def auth(self, user, password, resource = '', sasl = 1, on_auth = None):
		'''
		Authenticate connnection and bind resource. If resource is not provided
		random one or library name used. 
		'''
		self._User, self._Password, self._Resource, self._sasl = user, password, resource, sasl
		self.on_auth = on_auth
		self._on_doc_attrs()
		return
	
	def _on_old_auth(self, res):
		if res:
			self.connected += '+old_auth'
			self.on_auth(self, 'old_auth')
		else:
			self.on_auth(self, None)

	def _on_doc_attrs(self):
		if self._sasl: 
			auth_nb.SASL(self._User, self._Password, self._on_start_sasl).PlugIn(self)
		if not self._sasl or self.SASL.startsasl == 'not-supported':
			if not self._Resource: 
				self._Resource = 'xmpppy'
			auth_nb.NonBlockingNonSASL(self._User, self._Password, self._Resource, self._on_old_auth).PlugIn(self)
			return
		self.SASL.auth()
		return True
		
	def _on_start_sasl(self, data=None):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if not self.__dict__.has_key('SASL'): 
			# SASL is pluged out, possible disconnect 
			return
		if self.SASL.startsasl == 'in-process': 
			return
		self.onreceive(None)
		if self.SASL.startsasl == 'failure': 
			# wrong user/pass, stop auth
			self.connected = None
			self._on_sasl_auth(None)
		elif self.SASL.startsasl == 'success':
			auth_nb.NonBlockingBind().PlugIn(self)
			if self.protocol_type == 'BOSH':
				if self.wait_for_restart_response:
					self.onreceive(self._on_auth_bind)
				else:
					self._on_auth_bind(None)
				return

			elif self.protocol_type == 'XMPP':
				auth_nb.NonBlockingBind().PlugIn(self)
				self.onreceive(self._on_auth_bind)
				return
		return 


	def _on_auth_bind(self, data):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if self.NonBlockingBind.bound is None: 
			return
		self.NonBlockingBind.NonBlockingBind(self._Resource, self._on_sasl_auth)
		return True
	
	def _on_sasl_auth(self, res):
		self.onreceive(None)
		if res:
			self.connected += '+sasl'
			self.on_auth(self, 'sasl')
		else:
			self.on_auth(self, None)


	def initRoster(self):
		''' Plug in the roster. '''
		if not self.__dict__.has_key('NonBlockingRoster'): 
			roster_nb.NonBlockingRoster().PlugIn(self)

	def getRoster(self, on_ready = None):
		''' Return the Roster instance, previously plugging it in and
			requesting roster from server if needed. '''
		if self.__dict__.has_key('NonBlockingRoster'):
			return self.NonBlockingRoster.getRoster(on_ready)
		return None

	def sendPresence(self, jid=None, typ=None, requestRoster=0):
		''' Send some specific presence state.
			Can also request roster from server if according agrument is set.'''
		if requestRoster: roster_nb.NonBlockingRoster().PlugIn(self)
		self.send(dispatcher_nb.Presence(to=jid, typ=typ))


		

	# following methods are moved from blocking client class from xmpppy:
	def RegisterDisconnectHandler(self,handler):
		''' Register handler that will be called on disconnect.'''
		self.disconnect_handlers.append(handler)

	def UnregisterDisconnectHandler(self,handler):
		''' Unregister handler that is called on disconnect.'''
		self.disconnect_handlers.remove(handler)

	def DisconnectHandler(self):
		'''
		Default disconnect handler. Just raises an IOError. If you choosed to use
		this class in your production client, override this method or at least 
		unregister it.
		'''
		raise IOError('Disconnected from server.')

	def get_connect_type(self):
		''' Returns connection state. F.e.: None / 'tls' / 'plain+non_sasl'. '''
		return self.connected

	def get_peerhost(self):
		'''
		Gets the ip address of the account, from which is made connection to the
		server , (e.g. IP and port of gajim's socket. We will create listening socket
		on the same ip
		'''
		# FIXME: tuple (ip, port) is expected (and checked for) but port num is 
		# useless
		return self.socket.peerhost
