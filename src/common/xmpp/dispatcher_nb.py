##   dispatcher_nb.py
##       based on dispatcher.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
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


'''
Main xmpppy mechanism. Provides library with methods to assign different handlers
to different XMPP stanzas.
Contains one tunable attribute: DefaultTimeout (25 seconds by default). It defines time that 
Dispatcher.SendAndWaitForResponce method will wait for reply stanza before giving up.
'''

import simplexml, sys, locale
from xml.parsers.expat import ExpatError
from protocol import *
from client import PlugIn

import logging
log = logging.getLogger('gajim.c.x.dispatcher_nb')
log.setLevel(logging.INFO)

# default timeout to wait for response for our id
DEFAULT_TIMEOUT_SECONDS = 25
ID = 0

STREAM_TERMINATOR = '</stream:stream>'
XML_DECLARATION = '<?xml version=\'1.0\'?>'




# FIXME: ugly
class Dispatcher():
# Why is this here - I needed to redefine Dispatcher for BOSH and easiest way
# was to inherit original Dispatcher (now renamed to XMPPDispatcher). Trouble
# is that reference used to access dispatcher instance is in Client attribute
# named by __class__.__name__ of the dispatcher instance .. long story short:
# I wrote following to avoid changing each client.Dispatcher.whatever() in xmpp/

# If having two kinds of dispatcher will go well, I will rewrite the 
	def PlugIn(self, client_obj, after_SASL=False):
		if client_obj.protocol_type == 'XMPP':
			XMPPDispatcher().PlugIn(client_obj)
		elif client_obj.protocol_type == 'BOSH':
			BOSHDispatcher().PlugIn(client_obj, after_SASL)



class XMPPDispatcher(PlugIn):
	''' Ancestor of PlugIn class. Handles XMPP stream, i.e. aware of stream headers.
		Can be plugged out/in to restart these headers (used for SASL f.e.). '''

	
	def __init__(self):
		PlugIn.__init__(self)
		self.handlers={}
		self._expected={}
		self._defaultHandler=None
		self._pendingExceptions=[]
		self._eventHandler=None
		self._cycleHandlers=[]
		self._exported_methods=[self.RegisterHandler, self.RegisterDefaultHandler, \
		self.RegisterEventHandler, self.UnregisterCycleHandler, self.RegisterCycleHandler, \
		self.RegisterHandlerOnce, self.UnregisterHandler, self.RegisterProtocol, \
		self.SendAndWaitForResponse, self.StreamTerminate, \
		self.SendAndCallForResponse, self.getAnID, self.Event, self.send]

	def getAnID(self):
		global ID
		ID += 1
		return `ID`

	def dumpHandlers(self):
		''' Return set of user-registered callbacks in it's internal format.
			Used within the library to carry user handlers set over Dispatcher replugins. '''
		return self.handlers
	
	def restoreHandlers(self, handlers):
		''' Restores user-registered callbacks structure from dump previously obtained via dumpHandlers.
			Used within the library to carry user handlers set over Dispatcher replugins. '''
		self.handlers = handlers

	def _init(self):
		''' Registers default namespaces/protocols/handlers. Used internally.  '''
		self.RegisterNamespace('unknown')
		self.RegisterNamespace(NS_STREAMS)
		self.RegisterNamespace(self._owner.defaultNamespace)
		self.RegisterProtocol('iq', Iq)
		self.RegisterProtocol('presence', Presence)
		self.RegisterProtocol('message', Message)
		self.RegisterDefaultHandler(self.returnStanzaHandler)
		self.RegisterEventHandler(self._owner._caller._event_dispatcher)
		self.on_responses = {}
		
	def plugin(self, owner):
		''' Plug the Dispatcher instance into Client class instance and send initial stream header. Used internally.'''
		self._init()
		self._owner.lastErrNode = None
		self._owner.lastErr = None
		self._owner.lastErrCode = None
		self.StreamInit()
	
	def plugout(self):
		''' Prepares instance to be destructed. '''
		self.Stream.dispatch = None
		self.Stream.features = None
		self.Stream.destroy()
		self._owner = None
		self.Stream = None

	def StreamInit(self):
		''' Send an initial stream header. '''
		self.Stream = simplexml.NodeBuilder()
		self.Stream.dispatch = self.dispatch
		self.Stream._dispatch_depth = 2
		self.Stream.stream_header_received = self._check_stream_start
		self.Stream.features = None
		self._metastream = Node('stream:stream')
		self._metastream.setNamespace(self._owner.Namespace)
		self._metastream.setAttr('version', '1.0')
		self._metastream.setAttr('xmlns:stream', NS_STREAMS)
		self._metastream.setAttr('to', self._owner.Server)
		if locale.getdefaultlocale()[0]:
			self._metastream.setAttr('xml:lang',
				locale.getdefaultlocale()[0].split('_')[0])
		self._owner.send("%s%s>" % (XML_DECLARATION,str(self._metastream)[:-2]))

	def StreamTerminate(self):
		''' Send a stream terminator. '''
		self._owner.send(STREAM_TERMINATOR)

	def _check_stream_start(self, ns, tag, attrs):
		if ns<>NS_STREAMS or tag<>'stream':
			raise ValueError('Incorrect stream start: (%s,%s). Terminating.' % (tag, ns))

	def ProcessNonBlocking(self, data=None):
		''' Check incoming stream for data waiting. If "timeout" is positive - block for as max. this time.
			Returns:
			1) length of processed data if some data were processed;
			2) '0' string if no data were processed but link is alive;
			3) 0 (zero) if underlying connection is closed.'''
		for handler in self._cycleHandlers: 
			handler(self)
		if len(self._pendingExceptions) > 0:
			_pendingException = self._pendingExceptions.pop()
			raise _pendingException[0], _pendingException[1], _pendingException[2]
		try:
			self.Stream.Parse(data)
			# end stream:stream tag received
			if self.Stream and self.Stream.has_received_endtag():
				# FIXME call client method
				self._owner.Connection.disconnect()
				return 0
		except ExpatError:
			log.error('Invalid XML received from server. Forcing disconnect.')
			self._owner.Connection.disconnect()
			return 0
		if len(self._pendingExceptions) > 0:
			 _pendingException = self._pendingExceptions.pop()
			 raise _pendingException[0], _pendingException[1], _pendingException[2]
		if len(data) == 0: return '0'
		return len(data)
	
	def RegisterNamespace(self, xmlns, order='info'):
		''' Creates internal structures for newly registered namespace.
			You can register handlers for this namespace afterwards. By default one namespace
			already registered (jabber:client or jabber:component:accept depending on context. '''
		log.debug('Registering namespace "%s"' % xmlns)
		self.handlers[xmlns]={}
		self.RegisterProtocol('unknown', Protocol, xmlns=xmlns)
		self.RegisterProtocol('default', Protocol, xmlns=xmlns)

	def RegisterProtocol(self, tag_name, Proto, xmlns=None, order='info'):
		''' Used to declare some top-level stanza name to dispatcher.
		   Needed to start registering handlers for such stanzas.
		   Iq, message and presence protocols are registered by default. '''
		if not xmlns: xmlns=self._owner.defaultNamespace
		log.debug('Registering protocol "%s" as %s(%s)' %(tag_name, Proto, xmlns))
		self.handlers[xmlns][tag_name]={type:Proto, 'default':[]}

	def RegisterNamespaceHandler(self, xmlns, handler, typ='', ns='', makefirst=0, system=0):
		''' Register handler for processing all stanzas for specified namespace. '''
		self.RegisterHandler('default', handler, typ, ns, xmlns, makefirst, system)

	def RegisterHandler(self, name, handler, typ='', ns='', xmlns=None, makefirst=0, system=0):
		'''Register user callback as stanzas handler of declared type. Callback must take
			(if chained, see later) arguments: dispatcher instance (for replying), incomed
			return of previous handlers.
			The callback must raise xmpp.NodeProcessed just before return if it want preven
			callbacks to be called with the same stanza as argument _and_, more importantly
			library from returning stanza to sender with error set (to be enabled in 0.2 ve
			Arguments:
				"name" - name of stanza. F.e. "iq".
				"handler" - user callback.
				"typ" - value of stanza's "type" attribute. If not specified any value match
				"ns" - namespace of child that stanza must contain.
				"chained" - chain together output of several handlers.
				"makefirst" - insert handler in the beginning of handlers list instead of
				adding it to the end. Note that more common handlers (i.e. w/o "typ" and "
				will be called first nevertheless.
				"system" - call handler even if NodeProcessed Exception were raised already.
			'''
		if not xmlns: 
			xmlns=self._owner.defaultNamespace
		log.debug('Registering handler %s for "%s" type->%s ns->%s(%s)' % 
								(handler, name, typ, ns, xmlns))
		if not typ and not ns: 
			typ='default'
		if not self.handlers.has_key(xmlns): 
			self.RegisterNamespace(xmlns,'warn')
		if not self.handlers[xmlns].has_key(name): 
			self.RegisterProtocol(name,Protocol,xmlns,'warn')
		if not self.handlers[xmlns][name].has_key(typ+ns): 
			self.handlers[xmlns][name][typ+ns]=[]
		if makefirst: 
			self.handlers[xmlns][name][typ+ns].insert(0,{'func':handler,'system':system})
		else: 
			self.handlers[xmlns][name][typ+ns].append({'func':handler,'system':system})

	def RegisterHandlerOnce(self,name,handler,typ='',ns='',xmlns=None,makefirst=0, system=0):
		''' Unregister handler after first call (not implemented yet). '''
		if not xmlns: 
			xmlns=self._owner.defaultNamespace
		self.RegisterHandler(name, handler, typ, ns, xmlns, makefirst, system)

	def UnregisterHandler(self, name, handler, typ='', ns='', xmlns=None):
		''' Unregister handler. "typ" and "ns" must be specified exactly the same as with registering.'''
		if not xmlns: 
			xmlns=self._owner.defaultNamespace
		if not typ and not ns: 
			typ='default'
		if not self.handlers.has_key(xmlns):
			return
		if not self.handlers[xmlns].has_key(name): 
			return
		if not self.handlers[xmlns][name].has_key(typ+ns): 
			return
		for pack in self.handlers[xmlns][name][typ+ns]:
			if handler==pack['func']: 
				break
		else: 
			pack=None
		try: 
			self.handlers[xmlns][name][typ+ns].remove(pack)
		except ValueError: 
			pass

	def RegisterDefaultHandler(self,handler):
		''' Specify the handler that will be used if no NodeProcessed exception were raised.
			This is returnStanzaHandler by default. '''
		self._defaultHandler=handler

	def RegisterEventHandler(self,handler):
		''' Register handler that will process events. F.e. "FILERECEIVED" event. '''
		self._eventHandler=handler

	def returnStanzaHandler(self,conn,stanza):
		''' Return stanza back to the sender with <feature-not-implemennted/> error set. '''
		if stanza.getType() in ['get','set']:
			conn._owner.send(Error(stanza,ERR_FEATURE_NOT_IMPLEMENTED))

	def streamErrorHandler(self,conn,error):
		name,text='error',error.getData()
		for tag in error.getChildren():
			if tag.getNamespace()==NS_XMPP_STREAMS:
				if tag.getName()=='text': 
					text=tag.getData()
				else: 
					name=tag.getName()
		if name in stream_exceptions.keys(): 
			exc=stream_exceptions[name]
		else: 
			exc=StreamError
		raise exc((name,text))

	def RegisterCycleHandler(self, handler):
		''' Register handler that will be called on every Dispatcher.Process() call. '''
		if handler not in self._cycleHandlers: 
			self._cycleHandlers.append(handler)

	def UnregisterCycleHandler(self, handler):
		''' Unregister handler that will is called on every Dispatcher.Process() call.'''
		if handler in self._cycleHandlers: 
			self._cycleHandlers.remove(handler)
	
	def Event(self, realm, event, data):
		''' Raise some event. Takes three arguments:
			1) "realm" - scope of event. Usually a namespace. 
			2) "event" - the event itself. F.e. "SUCESSFULL SEND".
			3) data that comes along with event. Depends on event.'''
		if self._eventHandler: self._eventHandler(realm,event,data)

	def dispatch(self, stanza, session=None, direct=0):
		''' Main procedure that performs XMPP stanza recognition and calling apppropriate handlers for it.
			Called internally. '''
		#log.info('dispatch called: stanza = %s, session = %s, direct= %s' % (stanza, session, direct))
		if not session: 
			session = self
		session.Stream._mini_dom = None
		name = stanza.getName()

		if name=='features': 
			session.Stream.features=stanza
		
		xmlns=stanza.getNamespace()

		#log.info('in dispatch, getting ns for %s, and the ns is %s' % (stanza, xmlns))
		if not self.handlers.has_key(xmlns):
			log.warn("Unknown namespace: " + xmlns)
			xmlns='unknown'
		if not self.handlers[xmlns].has_key(name):
			log.warn("Unknown stanza: " + name)
			name='unknown'
		else:
			log.debug("Got %s/%s stanza" % (xmlns, name))

		if stanza.__class__.__name__=='Node': 
			stanza=self.handlers[xmlns][name][type](node=stanza)
		
		typ=stanza.getType()
		if not typ: typ=''
		stanza.props=stanza.getProperties()
		ID=stanza.getID()
		
		list=['default']                                                     # we will use all handlers:
		if self.handlers[xmlns][name].has_key(typ): list.append(typ)                # from very common...
		for prop in stanza.props:
			if self.handlers[xmlns][name].has_key(prop): list.append(prop)
			if typ and self.handlers[xmlns][name].has_key(typ+prop): list.append(typ+prop)  # ...to very particular
		
		chain=self.handlers[xmlns]['default']['default']
		for key in list:
			if key: chain = chain + self.handlers[xmlns][name][key]
		
		output=''
		if session._expected.has_key(ID):
			user=0
			if type(session._expected[ID]) == type(()):
				cb,args = session._expected[ID]
				log.debug("Expected stanza arrived. Callback %s(%s) found!" % (cb, args))
				try: 
					cb(session,stanza,**args)
				except Exception, typ:
					if typ.__class__.__name__ <>'NodeProcessed': raise
			else:
				log.debug("Expected stanza arrived!")
				session._expected[ID]=stanza
		else: 
			user=1
		for handler in chain:
			if user or handler['system']:
				try:
					handler['func'](session,stanza)
				except Exception, typ:
					if typ.__class__.__name__ <> 'NodeProcessed':
						self._pendingExceptions.insert(0, sys.exc_info())
						return
					user=0
		if user and self._defaultHandler: 
			self._defaultHandler(session, stanza)
	
	def WaitForData(self, data):
		if data is None:
			return
		res = self.ProcessNonBlocking(data)
		# 0 result indicates that we have closed the connection, e.g.
		# we have released dispatcher, so self._owner has no methods
		if not res:
			return
		self._owner.remove_timeout()
		if self._expected[self._witid] is None:
			return
		if self.on_responses.has_key(self._witid):
			i = self._witid # copy id cause it can change in resp() call
			self._owner.onreceive(None)
			resp, args = self.on_responses[self._witid]
			del(self.on_responses[self._witid])
			if args is None:
				resp(self._expected[self._witid])
			else:
				resp(self._owner, self._expected[self._witid], **args)
			del self._expected[i]
	
	def SendAndWaitForResponse(self, stanza, timeout=None, func=None, args=None):
		''' Put stanza on the wire and wait for recipient's response to it. '''
		if timeout is None: 
			timeout = DEFAULT_TIMEOUT_SECONDS
		self._witid = self._owner.send(stanza)
		if func:
			self.on_responses[self._witid] = (func, args)
		if timeout:
			self._owner.set_timeout(timeout)
		self._owner.onreceive(self.WaitForData)
		self._expected[self._witid] = None
		return self._witid
	
	def SendAndCallForResponse(self, stanza, func=None, args=None):
		''' Put stanza on the wire and call back when recipient replies.
			Additional callback arguments can be specified in args. '''
		self.SendAndWaitForResponse(stanza, 0, func, args)

	def send(self, stanza, now=False):
		id = None
		if type(stanza) not in [type(''), type(u'')]: 
			if isinstance(stanza, Protocol):
				id = stanza.getID()
				if id is None:
					stanza.setID(self.getAnID())
					id = stanza.getID()
				if self._owner._registered_name and not stanza.getAttr('from'): 
					stanza.setAttr('from', self._owner._registered_name)
		self._owner.Connection.send(stanza, now)	
		return id
	
class BOSHDispatcher(XMPPDispatcher):

	def PlugIn(self, owner, after_SASL=False):
		self.after_SASL = after_SASL
		XMPPDispatcher.PlugIn(self, owner)

	def StreamInit(self):
		''' Send an initial stream header. '''
		self.Stream = simplexml.NodeBuilder()
		self.Stream.dispatch = self.dispatch
		self.Stream._dispatch_depth = 2
		self.Stream.stream_header_received = self._check_stream_start
		self.Stream.features = None

		self._metastream = Node('stream:stream')
		self._metastream.setNamespace(self._owner.Namespace)
		self._metastream.setAttr('version', '1.0')
		self._metastream.setAttr('xmlns:stream', NS_STREAMS)
		self._metastream.setAttr('to', self._owner.Server)
		if locale.getdefaultlocale()[0]:
			self._metastream.setAttr('xml:lang',
				locale.getdefaultlocale()[0].split('_')[0])
		
		self.restart = True
		if self.after_SASL:
			self._owner.Connection.send_http(self._owner.Connection.get_after_SASL_bodytag())
		else:
			self._owner.Connection.send_http(self._owner.Connection.get_initial_bodytag())



	def StreamTerminate(self):
		''' Send a stream terminator. '''
		self._owner.Connection.send_http(self._owner.Connection.get_closing_bodytag())

	def ProcessNonBlocking(self, data=None):

		if self.restart:
			fromstream = self._metastream
			fromstream.setAttr('from', fromstream.getAttr('to'))
			fromstream.delAttr('to')
			data = '%s%s>%s' % (XML_DECLARATION,str(fromstream)[:-2] ,data)
			self.restart = False

		return XMPPDispatcher.ProcessNonBlocking(self, data)

	def dispatch(self, stanza, session=None, direct=0):
		if stanza.getName()=='body' and stanza.getNamespace()==NS_HTTP_BIND:

			stanza_attrs = stanza.getAttrs()

			if stanza_attrs.has_key('authid'):
				# should be only in init response
				# auth module expects id of stream in document attributes
				self.Stream._document_attrs['id'] = stanza_attrs['authid']

			if stanza_attrs.has_key('sid'):
				# session ID should be only in init response
				self._owner.Connection.bosh_sid = stanza_attrs['sid']

			if stanza_attrs.has_key('terminate'):
				# staznas under body still should be passed to XMPP dispatcher
				self._owner.on_disconnect()

			if stanza_attrs.has_key('error'):
				# recoverable error
				pass
			
			children = stanza.getChildren()
		
			if children:
				for child in children:
					XMPPDispatcher.dispatch(self, child, session, direct)
		else:
			XMPPDispatcher.dispatch(self, stanza, session, direct)



