##   transports_nb.py
##       based on transports.py
##  
##   Copyright (C) 2003-2004 Alexey "Snake" Nezhdanov
##       modified by Dimitur Kirov <dkirov@gmail.com>
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

import socket,base64

from simplexml import ustr
from client import PlugIn
from idlequeue import IdleObject
from protocol import *

import sys
import os
import errno
import time

import traceback

import logging
log = logging.getLogger('gajim.c.x.transports_nb')
consoleloghandler = logging.StreamHandler()
consoleloghandler.setLevel(logging.DEBUG)
consoleloghandler.setFormatter(
	logging.Formatter('%(levelname)s: %(message)s')
)
log.setLevel(logging.DEBUG)
log.addHandler(consoleloghandler)
log.propagate = False


def urisplit(self, uri):
	'''
	Function for splitting URI string to tuple (protocol, host, path).
	e.g. urisplit('http://httpcm.jabber.org/webclient') returns
	('http', 'httpcm.jabber.org', '/webclient')
	'''
	import re
	regex = '(([^:/]+)(://))?([^/]*)(/?.*)'
	grouped = re.match(regex, uri).groups()
	proto, host, path = grouped[1], grouped[3], grouped[4]
	return proto, host, path

# timeout to connect to the server socket, it doesn't include auth 
CONNECT_TIMEOUT_SECONDS = 30

# how long to wait for a disconnect to complete
DISCONNECT_TIMEOUT_SECONDS = 10

# size of the buffer which reads data from server
# if lower, more stanzas will be fragmented and processed twice
RECV_BUFSIZE = 32768 # 2x maximum size of ssl packet, should be plenty
#RECV_BUFSIZE = 16 # FIXME: (#2634) gajim breaks with this setting: it's inefficient but should work.

DATA_RECEIVED='DATA RECEIVED'
DATA_SENT='DATA SENT'


DISCONNECTED ='DISCONNECTED' 	
CONNECTING ='CONNECTING'  
CONNECTED ='CONNECTED' 
DISCONNECTING ='DISCONNECTING' 

class NonBlockingTcp(PlugIn, IdleObject):
	'''
	Non-blocking TCP socket wrapper
	'''
	def __init__(self, on_disconnect):
		'''
		Class constructor.
		'''

		PlugIn.__init__(self)
		IdleObject.__init__(self)

		self.on_disconnect = on_disconnect

		self.on_connect = None
		self.on_connect_failure = None
		self.sock = None
		self.idlequeue = None
		self.on_receive = None
		self.DBG_LINE='socket'
		self.state = DISCONNECTED

		# writable, readable  -  keep state of the last pluged flags
		# This prevents replug of same object with the same flags
		self.writable = True
		self.readable = False

		# queue with messages to be send 
		self.sendqueue = []

		# time to wait for SOME stanza to come and then send keepalive
		self.sendtimeout = 0

		# in case we want to something different than sending keepalives
		self.on_timeout = None
		
		# bytes remained from the last send message
		self.sendbuff = ''
		self._exported_methods=[self.disconnect, self.onreceive, self.set_send_timeout, 
			self.set_timeout, self.remove_timeout]

	def plugin(self, owner):
		print 'plugin called'
		owner.Connection=self
		self.idlequeue = owner.idlequeue

	def plugout(self):
		self._owner.Connection = None
		self._owner = None


	def get_fd(self):
		try:
			tmp = self._sock.fileno()
			return tmp
		except:
			return 0

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		'''
		Creates and connects socket to server and port defined in conn_5tupe which
		should be list item returned from getaddrinfo.
		:param conn_5tuple: 5-tuple returned from getaddrinfo
		:param on_connect: callback called on successful tcp connection
		:param on_connect_failure: callback called on failure when estabilishing tcp 
			connection
		'''
		self.on_connect = on_connect
		self.on_connect_failure = on_connect_failure
		(self.server, self.port) = conn_5tuple[4]
		log.debug('NonBlocking Connect :: About tot connect to %s:%s' % conn_5tuple[4])
		try:
			self._sock = socket.socket(*conn_5tuple[:3])
		except socket.error, (errnum, errstr):
			on_connect_failure('NonBlockingTcp: Error while creating socket: %s %s' % (errnum, errstr))
			return

		self._send = self._sock.send
		self._recv = self._sock.recv
		self.fd = self._sock.fileno()
		self.idlequeue.plug_idle(self, True, False)

		errnum = 0
		''' variable for errno symbol that will be found from exception raised from connect() '''
	
		# set timeout for TCP connecting - if nonblocking connect() fails, pollend
		# is called. If if succeeds pollout is called.
		self.idlequeue.set_read_timeout(self.get_fd(), CONNECT_TIMEOUT_SECONDS)

		try: 
			self._sock.setblocking(False)
			self._sock.connect((self.server,self.port))
		except Exception, (errnum, errstr):
			pass

		if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
			# connecting in progress
			self.set_state(CONNECTING)
			log.debug('After connect. "%s" raised => CONNECTING' % errstr)
			# on_connect/failure will be called from self.pollin/self.pollout
			return
		elif errnum in (0, 10056, errno.EISCONN):
			# already connected - this branch is very unlikely, nonblocking connect() will
			# return EINPROGRESS exception in most cases. When here, we don't need timeout
			# on connected descriptor and success callback can be called.
			log.debug('After connect. "%s" raised => CONNECTED' % errstr)
			self._on_connect(self)
			return

		# if there was some other error, call failure callback and unplug transport
		# which will also remove read_timeouts for descriptor
		self._on_connect_failure('Exception while connecting to %s:%s - %s %s' % 
			(self.server, self.port, errnum, errstr))
			
	def _on_connect(self, data):
		''' preceeds call of on_connect callback '''
		self.set_state(CONNECTED)
		self.idlequeue.remove_timeout(self.get_fd())
		self.on_connect()


	def set_state(self, newstate):
		assert(newstate in [DISCONNECTED, CONNECTING, CONNECTED, DISCONNECTING])
		if (self.state, newstate) in [(CONNECTING, DISCONNECTING), (DISCONNECTED, DISCONNECTING)]:
			log.info('strange move: %s -> %s' % (self.state, newstate))
		self.state = newstate


	def _on_connect_failure(self,err_message):
		''' preceeds call of on_connect_failure callback '''
		# In case of error while connecting we need to close socket
		# but we don't want to call DisconnectHandlers from client,
		# thus the do_callback=False
		self.disconnect(do_callback=False)
		self.on_connect_failure(err_message=err_message)

		

	def pollin(self):
		'''called when receive on plugged socket is possible '''
		log.debug('pollin called, state == %s' % self.state)
		self._do_receive() 

	def pollout(self):
		'''called when send to plugged socket is possible'''
		log.debug('pollout called, state == %s' % self.state)

		if self.state==CONNECTING:
			self._on_connect(self)
			return
		self._do_send()

	def pollend(self):
		log.debug('pollend called, state == %s' % self.state)

		if self.state==CONNECTING:
			self._on_connect_failure('Error during connect to %s:%s' % 
				(self.server, self.port))
		else :
			self.disconnect()

	def disconnect(self, do_callback=True):
		if self.state == DISCONNECTED:
			return
		self.idlequeue.unplug_idle(self.get_fd())
		try:
			self._sock.shutdown(socket.SHUT_RDWR)
			self._sock.close()
		except socket.error, (errnum, errstr):
			log.error('Error disconnecting a socket: %s %s' % (errnum,errstr))
		self.set_state(DISCONNECTED)
		if do_callback:
			# invoke callback given in __init__
			self.on_disconnect()

	def read_timeout(self):
		'''
		Implemntation of IdleObject function called on timeouts from IdleQueue.
		'''
		log.debug('read_timeout called, state == %s' % self.state)
		if self.state==CONNECTING:
			# if read_timeout is called during connecting, connect() didn't end yet
			# thus we have to call the tcp failure callback
			self._on_connect_failure('Error during connect to %s:%s' % 
				(self.server, self.port))
		else:
			if self.on_timeout:
				self.on_timeout()
			self.renew_send_timeout()

	def renew_send_timeout(self):
		if self.on_timeout and self.sendtimeout > 0:
			self.set_timeout(self.sendtimeout)
		else:
			self.remove_timeout()
	
	def set_send_timeout(self, timeout, on_timeout):
		self.sendtimeout = timeout
		if self.sendtimeout > 0:
			self.on_timeout = on_timeout
		else:
			self.on_timeout = None
	
	def set_timeout(self, timeout):
		if self.state in [CONNECTING, CONNECTED] and self.get_fd() > 0:
			self.idlequeue.set_read_timeout(self.get_fd(), timeout)

	def remove_timeout(self):
		if self.get_fd():
			self.idlequeue.remove_timeout(self.get_fd())

	def send(self, raw_data, now=False):
		'''Append raw_data to the queue of messages to be send. 
		If supplied data is unicode string, encode it to utf-8.
		'''

		if self.state not in [CONNECTED, DISCONNECTING]:
			log.error('Trying to send %s when transport is %s.' % 
				(raw_data, self.state))
			return
		r = raw_data
		if isinstance(r, unicode): 
			r = r.encode('utf-8')
		elif not isinstance(r, str): 
			r = ustr(r).encode('utf-8')
		if now:
			self.sendqueue.insert(0, r)
			self._do_send()
		else:
			self.sendqueue.append(r)
		self._plug_idle()



	def _plug_idle(self):
		# readable if socket is connected or disconnecting
		readable = self.state != DISCONNECTED
		# writeable if sth to send
		if self.sendqueue or self.sendbuff:
			writable = True
		else:
			writable = False
		print 'About to plug fd %d, W:%s, R:%s' % (self.get_fd(), writable, readable)
		if self.writable != writable or self.readable != readable:
			print 'Really plugging fd %d, W:%s, R:%s' % (self.get_fd(), writable, readable)
			self.idlequeue.plug_idle(self, writable, readable)
		else: 
			print 'Not plugging - is already plugged'



	def _do_send(self):
		if not self.sendbuff:
			if not self.sendqueue:
				return None # nothing to send
			self.sendbuff = self.sendqueue.pop(0)
		try:
			send_count = self._send(self.sendbuff)
			if send_count:
				sent_data = self.sendbuff[:send_count]
				self.sendbuff = self.sendbuff[send_count:]
				self._plug_idle()
				self._raise_event(DATA_SENT, sent_data)

		except socket.error, e:
			log.error('_do_send:', exc_info=True)
			traceback.print_exc()
			self.disconnect()

	def _raise_event(self, event_type, data):
		if data and data.strip():
			log.debug('raising event from transport: %s %s' % (event_type,data))
			if hasattr(self._owner, 'Dispatcher'):
				self._owner.Dispatcher.Event('', event_type, data)

	def onreceive(self, recv_handler):
		''' Sets the on_receive callback. Do not confuse it with
		on_receive() method, which is the callback itself.'''
		if not recv_handler:
			if hasattr(self._owner, 'Dispatcher'):
				self.on_receive = self._owner.Dispatcher.ProcessNonBlocking
			else:
				self.on_receive = None
			return
		log.debug('setting onreceive on %s' % recv_handler)
		self.on_receive = recv_handler


	def _do_receive(self):
		''' Reads all pending incoming data. Calls owner's disconnected() method if appropriate.'''
		ERR_DISCONN = -2 # Misc error signifying that we got disconnected
		received = None
		errnum = 0
		errstr = 'No Error Set'

		try: 
			# get as many bites, as possible, but not more than RECV_BUFSIZE
			received = self._recv(RECV_BUFSIZE)
		except (socket.error, socket.herror, socket.gaierror), (errnum, errstr):
			# save exception number and message to errnum, errstr
			log.debug("_do_receive: got %s:" % received , exc_info=True)
		
		if received == '':
			errnum = ERR_DISCONN
			errstr = "Connection closed unexpectedly"

		if errnum in (ERR_DISCONN, errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN):
			# ECONNRESET - connection you are trying to access has been reset by the peer
			# ENOTCONN - Transport endpoint is not connected
			# ESHUTDOWN  - shutdown(2) has been called on a socket to close down the
			# sending end of the transmision, and then data was attempted to be sent
			log.error("Connection to %s lost: %s %s" % ( self.server, errnum, errstr))
			self.disconnect()
			return

		if received is None:
			# in case of some other exception
			# FIXME: is this needed?? 
			if errnum != 0:
				log.error("CConnection to %s lost: %s %s" % (self.server, errnum, errstr))
				self.disconnect()
				return
			received = ''

		# we have received some bytes, stop the timeout!
		self.renew_send_timeout()
		# pass received data to owner
		#self.
		if self.on_receive:
			self._raise_event(DATA_RECEIVED, received)
			self._on_receive(received)
		else:
			# This should never happen, so we need the debug. (If there is no handler
			# on receive spacified, data are passed to Dispatcher.ProcessNonBlocking)
			log.error('SOCKET Unhandled data received: %s' % received)
			self.disconnect()

	def _on_receive(self, data):
		# Overriding this method allows modifying received data before it is passed
		# to owner's callback. 
		log.debug('About to call on_receive which is %s' % self.on_receive)
		self.on_receive(data)





class NBProxySocket(NonBlockingTcp):
	'''
	Interface for proxy socket wrappers - when tunnneling XMPP over proxies,
	some connecting process usually has to be done before opening stream.
	'''
	def __init__(self, on_disconnect, xmpp_server, proxy_creds=(None,None)):
		self.proxy_user, self.proxy_pass = proxy_creds
		self.xmpp_server = xmpp_server
		NonBlockingTcp.__init__(self, on_disconnect)
		

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		'''
		connect method is extended by proxy credentials and xmpp server hostname
		and port because those are needed for 
		The idea is to insert Proxy-specific mechanism after TCP connect and 
		before XMPP stream opening (which is done from client).
		'''

		self.after_proxy_connect = on_connect
		
		NonBlockingTcp.connect(self,
				conn_5tuple=conn_5tuple,
				on_connect =self._on_tcp_connect,
				on_connect_failure =on_connect_failure)

	def _on_tcp_connect(self):
		pass



class NBHTTPProxySocket(NBProxySocket):
	''' This class can be used instead of NonBlockingTcp
	HTTP (CONNECT) proxy connection class. Allows to use HTTP proxies like squid with
	(optionally) simple authentication (using login and password). 
	'''
		
	def _on_tcp_connect(self):
		''' Starts connection. Connects to proxy, supplies login and password to it
			(if were specified while creating instance). Instructs proxy to make
			connection to the target server. Returns non-empty sting on success. '''
		log.debug('Proxy server contacted, performing authentification')
		connector = ['CONNECT %s:%s HTTP/1.0' % self.xmpp_server,
			'Proxy-Connection: Keep-Alive',
			'Pragma: no-cache',
			'Host: %s:%s' % self.xmpp_server,
			'User-Agent: HTTPPROXYsocket/v0.1']
		if self.proxy_user and self.proxy_pass:
			credentials = '%s:%s' % (self.proxy_user, self.proxy_pass)
			credentials = base64.encodestring(credentials).strip()
			connector.append('Proxy-Authorization: Basic '+credentials)
		connector.append('\r\n')
		self.onreceive(self._on_headers_sent)
		self.send('\r\n'.join(connector))
		
	def _on_headers_sent(self, reply):
		if reply is None:
			return
		self.reply = reply.replace('\r', '')
		try: 
			proto, code, desc = reply.split('\n')[0].split(' ', 2)
		except: 
			log.error("_on_headers_sent:", exc_info=True)
			#traceback.print_exc()
			self._on_connect_failure('Invalid proxy reply')
			return
		if code <> '200':
			log.error('Invalid proxy reply: %s %s %s' % (proto, code, desc))
			self._on_connect_failure('Invalid proxy reply')
			return
		if len(reply) != 2:
			pass
		self.after_proxy_connect()
		#self.onreceive(self._on_proxy_auth)

	# FIXME: find out what it this method for
	def _on_proxy_auth(self, reply):
		if self.reply.find('\n\n') == -1:
			if reply is None:
				self._on_connect_failure('Proxy authentification failed')
				return
			if reply.find('\n\n') == -1:
				self.reply += reply.replace('\r', '')
				self._on_connect_failure('Proxy authentification failed')
				return
		log.debug('Authentification successfull. Jabber server contacted.')
		self._on_connect(self)


class NBSOCKS5ProxySocket(NBProxySocket):
	'''SOCKS5 proxy connection class. Uses TCPsocket as the base class
		redefines only connect method. Allows to use SOCKS5 proxies with
		(optionally) simple authentication (only USERNAME/PASSWORD auth). 
	'''
	# TODO: replace DEBUG with ordinrar logging, replace on_proxy_failure() with
	#	_on_connect_failure, at the end call _on_connect()

	def _on_tcp_connect(self):
		self.DEBUG('Proxy server contacted, performing authentification', 'start')
		if self.proxy.has_key('user') and self.proxy.has_key('password'):
			to_send = '\x05\x02\x00\x02'
		else:
			to_send = '\x05\x01\x00'
		self.onreceive(self._on_greeting_sent)
		self.send(to_send)

	def _on_greeting_sent(self, reply):
		if reply is None:
			return
		if len(reply) != 2:
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[0] != '\x05':
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[1] == '\x00':
			return self._on_proxy_auth('\x01\x00')
		elif reply[1] == '\x02':
			to_send = '\x01' + chr(len(self.proxy['user'])) + self.proxy['user'] +\
				chr(len(self.proxy['password'])) + self.proxy['password']
			self.onreceive(self._on_proxy_auth)
			self.send(to_send)
		else:
			if reply[1] == '\xff':
				self.DEBUG('Authentification to proxy impossible: no acceptable '
					'auth method', 'error')
				self._owner.disconnected()
				self.on_proxy_failure('Authentification to proxy impossible: no '
					'acceptable authentification method')
				return
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return

	def _on_proxy_auth(self, reply):
		if reply is None:
			return
		if len(reply) != 2:
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[0] != '\x01':
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[1] != '\x00':
			self.DEBUG('Authentification to proxy failed', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Authentification to proxy failed')
			return
		self.DEBUG('Authentification successfull. Jabber server contacted.','ok')
		# Request connection
		req = "\x05\x01\x00"
		# If the given destination address is an IP address, we'll
		# use the IPv4 address request even if remote resolving was specified.
		try:
			self.ipaddr = socket.inet_aton(self.server[0])
			req = req + "\x01" + self.ipaddr
		except socket.error:
			# Well it's not an IP number,  so it's probably a DNS name.
#			if self.__proxy[3]==True:
			# Resolve remotely
			self.ipaddr = None
			req = req + "\x03" + chr(len(self.server[0])) + self.server[0]
#			else:
#				# Resolve locally
#				self.ipaddr = socket.inet_aton(socket.gethostbyname(self.server[0]))
#				req = req + "\x01" + ipaddr
		req = req + struct.pack(">H",self.server[1])
		self.onreceive(self._on_req_sent)
		self.send(req)

	def _on_req_sent(self, reply):
		if reply is None:
			return
		if len(reply) < 10:
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[0] != '\x05':
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[1] != "\x00":
			# Connection failed
			self._owner.disconnected()
			if ord(reply[1])<9:
				errors = ['general SOCKS server failure',
					'connection not allowed by ruleset',
					'Network unreachable',
					'Host unreachable',
					'Connection refused',
					'TTL expired',
					'Command not supported',
					'Address type not supported'
				]
				txt = errors[ord(reply[1])-1]
			else:
				txt = 'Invalid proxy reply'
			self.DEBUG(txt, 'error')
			self.on_proxy_failure(txt)
			return
		# Get the bound address/port
		elif reply[3] == "\x01":
			begin, end = 3, 7
		elif reply[3] == "\x03":
			begin, end = 4, 4 + reply[4]
		else:
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return

		if self.on_connect_proxy:
			self.on_connect_proxy()

	def DEBUG(self, text, severity):
		''' Overwrites DEBUG tag to allow debug output be presented as "CONNECTproxy".'''
		return self._owner.DEBUG(DBG_CONNECT_PROXY, text, severity)



class NonBlockingHttpBOSH(NonBlockingTcp):
	'''
	Socket wrapper that makes HTTP message out of send data and peels-off 
	HTTP headers from incoming messages
	'''

	def __init__(self, bosh_uri, bosh_port, on_disconnect):
		self.bosh_protocol, self.bosh_host, self.bosh_path = self.urisplit(bosh_uri)
		if self.bosh_protocol is None:
			self.bosh_protocol = 'http'
		if self.bosh_path == '':
			bosh_path = '/'
		self.bosh_port = bosh_port
		
	def send(self, raw_data, now=False):

		NonBlockingTcp.send(
			self,
			self.build_http_message(raw_data),
			now)

	def _on_receive(self,data):
		'''Preceeds passing received data to Client class. Gets rid of HTTP headers
		and checks them.'''
		statusline, headers, httpbody = self.parse_http_message(data)
		if statusline[1] != '200':
			log.error('HTTP Error: %s %s' % (statusline[1], statusline[2]))
			self.disconnect()
		self.on_receive(httpbody)
	
		
	def build_http_message(self, httpbody):
		'''
		Builds bosh http message with given body.
		Values for headers and status line fields are taken from class variables.
		)  
		'''
		headers = ['POST %s HTTP/1.1' % self.bosh_path,
			'Host: %s:%s' % (self.bosh_host, self.bosh_port),
			'Content-Type: text/xml; charset=utf-8',
			'Content-Length: %s' % len(str(httpbody)),
			'\r\n']
		headers = '\r\n'.join(headers)
		return('%s%s\r\n' % (headers, httpbody))

	def parse_http_message(self, message):
		'''
		splits http message to tuple (
		  statusline - list of e.g. ['HTTP/1.1', '200', 'OK'],
		  headers - dictionary of headers e.g. {'Content-Length': '604',
		            'Content-Type': 'text/xml; charset=utf-8'},
		  httpbody - string with http body
		)  
		'''
		message = message.replace('\r','')
		(header, httpbody) = message.split('\n\n')
		header = header.split('\n')
		statusline = header[0].split(' ')
		header = header[1:]
		headers = {}
		for dummy in header:
			row = dummy.split(' ',1)
			headers[row[0][:-1]] = row[1]
		return (statusline, headers, httpbody)
