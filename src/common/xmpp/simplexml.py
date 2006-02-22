##   simplexml.py based on Mattew Allum's xmlstream.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
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

# $Id: simplexml.py,v 1.27 2005/04/30 07:20:27 snakeru Exp $

"""Simplexml module provides xmpppy library with all needed tools to handle XML nodes and XML streams.
I'm personally using it in many other separate projects. It is designed to be as standalone as possible."""

import xml.parsers.expat

def XMLescape(txt):
	"""Returns provided string with symbols & < > " replaced by their respective XML entities."""
	# replace also FORM FEED and ESC, because they are not valid XML chars
	return txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace(u'\x0C', "").replace(u'\x1B', "")

ENCODING='utf-8'
def ustr(what):
	"""Converts object "what" to unicode string using it's own __str__ method if accessible or unicode method otherwise."""
	if type(what) == type(u''): return what
	try: r=what.__str__()
	except AttributeError: r=str(what)
	if type(r)<>type(u''): return unicode(r,ENCODING)
	return r

class Node:
	""" Node class describes syntax of separate XML Node. It have a constructor that permits node creation
		from set of "namespace name", attributes and payload of text strings and other nodes.
		It does not natively support building node from text string and uses NodeBuilder class for that purpose.
		After creation node can be mangled in many ways so it can be completely changed.
		Also node can be serialised into string in one of two modes: default (where the textual representation
		of node describes it exactly) and "fancy" - with whitespace added to make indentation and thus make
		result more readable by human.

		Node class have attribute FORCE_NODE_RECREATION that is defaults to False thus enabling fast node
		replication from the some other node. The drawback of the fast way is that new node shares some
		info with the "original" node that is changing the one node may influence the other. Though it is
		rarely needed (in xmpppy it is never needed at all since I'm usually never using original node after
		replication (and using replication only to move upwards on the classes tree).
	"""
	FORCE_NODE_RECREATION=0
	def __init__(self, tag=None, attrs={}, payload=[], parent=None, node=None):
		""" Takes "tag" argument as the name of node (prepended by namespace, if needed and separated from it
			by a space), attrs dictionary as the set of arguments, payload list as the set of textual strings
			and child nodes that this node carries within itself and "parent" argument that is another node
			that this one will be the child of. Also the __init__ can be provided with "node" argument that is 
			either a text string containing exactly one node or another Node instance to begin with. If both
			"node" and other arguments is provided then the node initially created as replica of "node"
			provided and then modified to be compliant with other arguments."""
		if node:
			if self.FORCE_NODE_RECREATION and type(node)==type(self): 
				node=str(node)
			if type(node)<>type(self): 
				node=NodeBuilder(node,self)
			else:
				self.name,self.namespace,self.attrs,self.data,self.kids,self.parent = node.name,node.namespace,{},[],[],node.parent
				for key  in node.attrs.keys(): self.attrs[key]=node.attrs[key]
				for data in node.data: self.data.append(data)
				for kid  in node.kids: self.kids.append(kid)
		else: self.name,self.namespace,self.attrs,self.data,self.kids,self.parent = 'tag','',{},[],[],None

		if tag: self.namespace, self.name = ([self.namespace]+tag.split())[-2:]
		if parent: self.parent = parent
		if self.parent and not self.namespace: self.namespace=self.parent.namespace
		for attr in attrs.keys():
			self.attrs[attr]=attrs[attr]
		if type(payload) in (type(''),type(u'')): payload=[payload]
		for i in payload:
			if type(i)==type(self): self.addChild(node=i)
			else: self.data.append(ustr(i))

	def __str__(self,fancy=0):
		""" Method used to dump node into textual representation.
			if "fancy" argument is set to True produces indented output for readability."""
		s = (fancy-1) * 2 * ' ' + "<" + self.name
		if self.namespace:
			if not self.parent or self.parent.namespace!=self.namespace:
				s = s + ' xmlns="%s"'%self.namespace
		for key in self.attrs.keys():
			val = ustr(self.attrs[key])
			s = s + ' %s="%s"' % ( key, XMLescape(val) )
		s = s + ">"
		cnt = 0 
		if self.kids:
			if fancy: s = s + "\n"
			for a in self.kids:
				if not fancy and (len(self.data)-1)>=cnt: s=s+XMLescape(self.data[cnt])
				elif (len(self.data)-1)>=cnt: s=s+XMLescape(self.data[cnt].strip())
				s = s + a.__str__(fancy and fancy+1)
				cnt=cnt+1
		if not fancy and (len(self.data)-1) >= cnt: s = s + XMLescape(self.data[cnt])
		elif (len(self.data)-1) >= cnt: s = s + XMLescape(self.data[cnt].strip())
		if not self.kids and s[-1:]=='>':
			s=s[:-1]+' />'
			if fancy: s = s + "\n"
		else:
			if fancy and not self.data: s = s + (fancy-1) * 2 * ' '
			s = s + "</" + self.name + ">"
			if fancy: s = s + "\n"
		return s
	def addChild(self, name=None, attrs={}, payload=[], namespace=None, node=None):
		""" If "node" argument is provided, adds it as child node. Else creates new node from
			the other arguments' values and adds it as well."""
		if namespace: name=namespace+' '+name
		if node:
			newnode=node
			node.parent = self
		else: newnode=Node(tag=name, parent=self, attrs=attrs, payload=payload)
		self.kids.append(newnode)
		return newnode
	def addData(self, data):
		""" Adds some CDATA to node. """
		self.data.append(ustr(data))
	def clearData(self):
		""" Removes all CDATA from the node. """
		self.data=[]
	def delAttr(self, key):
		""" Deletes an attribute "key" """
		del self.attrs[key]
	def delChild(self, node, attrs={}):
		""" Deletes the "node" from the node's childs list, if "node" is an instance.
			Else deletes the first node that have specified name and (optionally) attributes. """
		if type(node)<>type(self): node=self.getTag(node,attrs)
		self.kids.remove(node)
		return node
	def getAttrs(self):
		""" Returns all node's attributes as dictionary. """
		return self.attrs
	def getAttr(self, key):
		""" Returns value of specified attribute. """
		try: return self.attrs[key]
		except: return None
	def getChildren(self):
		""" Returns all node's child nodes as list. """
		return self.kids
	def getData(self):
		""" Returns all node CDATA as string (concatenated). """
		return ''.join(self.data)
	def getName(self):
		""" Returns the name of node """
		return self.name
	def getNamespace(self):
		""" Returns the namespace of node """
		return self.namespace
	def getParent(self):
		""" Returns the parent of node (if present). """
		return self.parent
	def getPayload(self):
		""" Return the payload of node i.e. list of child nodes and CDATA entries.
			F.e. for "<node>text1<nodea/><nodeb/> text2</node>" will be returned list:
			['text1', <nodea instance>, <nodeb instance>, ' text2']. """
		ret=[]
		for i in range(len(self.kids)+len(self.data)+1):
			try:
				if self.data[i]: ret.append(self.data[i])
			except IndexError: pass
			try: ret.append(self.kids[i])
			except IndexError: pass
		return ret
	def getTag(self, name, attrs={}, namespace=None): 
		""" Filters all child nodes using specified arguments as filter.
			Returns the first found or None if not found. """
		return self.getTags(name, attrs, namespace, one=1)
	def getTagAttr(self,tag,attr):
		""" Returns attribute value of the child with specified name (or None if no such attribute)."""
		try: return self.getTag(tag).attrs[attr]
		except: return None
	def getTagData(self,tag):
		""" Returns cocatenated CDATA of the child with specified name."""
		try: return self.getTag(tag).getData()
		except: return None
	def getTags(self, name, attrs={}, namespace=None, one=0):
		""" Filters all child nodes using specified arguments as filter.
			Returns the list of nodes found. """
		nodes=[]
		for node in self.kids:
			if namespace and namespace<>node.getNamespace(): continue
			if node.getName() == name:
				for key in attrs.keys():
				   if not node.attrs.has_key(key) or node.attrs[key]<>attrs[key]: break
				else: nodes.append(node)
			if one and nodes: return nodes[0]
		if not one: return nodes
	def setAttr(self, key, val):
		""" Sets attribute "key" with the value "val". """
		self.attrs[key]=val
	def setData(self, data):
		""" Sets node's CDATA to provided string. Resets all previous CDATA!"""
		self.data=[ustr(data)]
	def setName(self,val):
		""" Changes the node name. """
		self.name = val
	def setNamespace(self, namespace):
		""" Changes the node namespace. """
		self.namespace=namespace
	def setParent(self, node): 
		""" Sets node's parent to "node". WARNING: do not checks if the parent already present 
			and not removes the node from the list of childs of previous parent. """
		self.parent = node
	def setPayload(self,payload,add=0):
		""" Sets node payload according to the list specified. WARNING: completely replaces all node's
			previous content. If you wish just to add child or CDATA - use addData or addChild methods. """
		if type(payload) in (type(''),type(u'')): payload=[payload]
		if add: self.kids+=payload
		else: self.kids=payload
	def setTag(self, name, attrs={}, namespace=None):
		""" Same as getTag but if the node with specified namespace/attributes not found, creates such
			node and returns it. """
		node=self.getTags(name, attrs, namespace=namespace, one=1)
		if node: return node
		else: return self.addChild(name, attrs, namespace=namespace)
	def setTagAttr(self,tag,attr,val):
		""" Creates new node (if not already present) with name "tag"
			and sets it's attribute "attr" to value "val". """
		try: self.getTag(tag).attrs[attr]=val
		except: self.addChild(tag,attrs={attr:val})
	def setTagData(self,tag,val,attrs={}):
		""" Creates new node (if not already present) with name "tag" and (optionally) attributes "attrs"
			and sets it's CDATA to string "val". """
		try: self.getTag(tag,attrs).setData(ustr(val))
		except: self.addChild(tag,attrs,payload=[ustr(val)])
	def has_attr(self,key):
		""" Checks if node have attribute "key"."""
		return self.attrs.has_key(key)
	def __getitem__(self,item):
		""" Returns node's attribute "item" value. """
		return self.getAttr(item)
	def __setitem__(self,item,val):
		""" Sets node's attribute "item" value. """
		return self.setAttr(item,val)
	def __delitem__(self,item):
		""" Deletes node's attribute "item". """
		return self.delAttr(item,val)
	def __getattr__(self,attr):
		""" Reduce memory usage caused by T/NT classes - use memory only when needed. """
		if attr=='T':
			self.T=T(self)
			return self.T
		if attr=='NT':
			self.NT=NT(self)
			return self.NT
		raise AttributeError

class T:
	""" Auxiliary class used to quick access to node's child nodes. """
	def __init__(self,node): self.__dict__['node']=node
	def __getattr__(self,attr): return self.node.setTag(attr)
	def __setattr__(self,attr,val):
		if isinstance(val,Node): Node.__init__(self.node.setTag(attr),node=val)
		else: return self.node.setTagData(attr,val)
	def __delattr__(self,attr): return self.node.delChild(attr)

class NT(T):
	""" Auxiliary class used to quick create node's child nodes. """
	def __getattr__(self,attr): return self.node.addChild(attr)
	def __setattr__(self,attr,val):
		if isinstance(val,Node): self.node.addChild(attr,node=val)
		else: return self.node.addChild(attr,payload=[val])

DBG_NODEBUILDER = 'nodebuilder'
class NodeBuilder:
	""" Builds a Node class minidom from data parsed to it. This class used for two purposes:
		1. Creation an XML Node from a textual representation. F.e. reading a config file. See an XML2Node method.
		2. Handling an incoming XML stream. This is done by mangling 
		   the __dispatch_depth parameter and redefining the dispatch method.
		You do not need to use this class directly if you do not designing your own XML handler."""
	def __init__(self,data=None,initial_node=None):
		""" Takes two optional parameters: "data" and "initial_node".
			By default class initialised with empty Node class instance.
			Though, if "initial_node" is provided it used as "starting point".
			You can think about it as of "node upgrade".
			"data" (if provided) feeded to parser immidiatedly after instance init.
			"""
		self.DEBUG(DBG_NODEBUILDER, "Preparing to handle incoming XML stream.", 'start')
		self._parser = xml.parsers.expat.ParserCreate(namespace_separator=' ')
		self._parser.StartElementHandler       = self.starttag
		self._parser.EndElementHandler         = self.endtag
		self._parser.StartNamespaceDeclHandler = self.handle_namespace_start
		self._parser.CharacterDataHandler    = self.handle_cdata
		self.Parse = self._parser.Parse

		self.__depth = 0
		self._dispatch_depth = 1
		self._document_attrs = None
		self._mini_dom=initial_node
		self.last_is_data = 1
		self._ptr=None
		self.data_buffer = None
		self.namespaces={"http://www.w3.org/XML/1998/namespace":'xml:'}
		self.xmlns="http://www.w3.org/XML/1998/namespace"

		if data: 
			self._parser.Parse(data,1)
	
	def check_data_buffer(self):
		if self.data_buffer:
			self._ptr.data.append(''.join(self.data_buffer))
			del self.data_buffer[:]
			self.data_buffer = None
	
	def destroy(self):
		""" Method used to allow class instance to be garbage-collected. """
		self.check_data_buffer()
		self._parser.StartElementHandler       = None
		self._parser.EndElementHandler         = None
		self._parser.CharacterDataHandler      = None
		self._parser.StartNamespaceDeclHandler = None

	def starttag(self, tag, attrs):
		"""XML Parser callback. Used internally"""
		self.check_data_buffer()
		attlist=attrs.keys()       #
		for attr in attlist:       # FIXME: Crude hack. And it also slows down the whole library considerably.
			sp=attr.rfind(" ")     #
			if sp==-1: continue    #
			ns=attr[:sp]           #
			attrs[self.namespaces[ns]+attr[sp+1:]]=attrs[attr]
			del attrs[attr]        #
		self.__depth += 1
		self.DEBUG(DBG_NODEBUILDER, "DEPTH -> %i , tag -> %s, attrs -> %s" % (self.__depth, tag, `attrs`), 'down')
		if self.__depth == self._dispatch_depth:
			if not self._mini_dom : 
				self._mini_dom = Node(tag=tag, attrs=attrs)
			else: 
				Node.__init__(self._mini_dom,tag=tag, attrs=attrs)
			self._ptr = self._mini_dom
		elif self.__depth > self._dispatch_depth:
			self._ptr.kids.append(Node(tag=tag,parent=self._ptr,attrs=attrs))
			self._ptr = self._ptr.kids[-1]
		if self.__depth == 1:
			self._document_attrs = attrs
			ns, name = (['']+tag.split())[-2:]
			self.stream_header_received(ns, name, attrs)
		if not self.last_is_data and self._ptr.parent: 
			self._ptr.parent.data.append('')
		self.last_is_data = 0
	def endtag(self, tag ):
		"""XML Parser callback. Used internally"""
		self.DEBUG(DBG_NODEBUILDER, "DEPTH -> %i , tag -> %s" % (self.__depth, tag), 'up')
		self.check_data_buffer()
		if self.__depth == self._dispatch_depth:
			self.dispatch(self._mini_dom)
		elif self.__depth > self._dispatch_depth:
			self._ptr = self._ptr.parent
		else:
			self.DEBUG(DBG_NODEBUILDER, "Got higher than dispatch level. Stream terminated?", 'stop')
		self.__depth -= 1
		self.last_is_data = 0
		if self.__depth == 0: self.stream_footer_received()
	
	def handle_cdata(self, data):
		if self.last_is_data:
			if self.data_buffer:
				self.data_buffer.append(data)
		else:
			self.data_buffer = [data]
			self.last_is_data = 1
	
	def handle_namespace_start(self, prefix, uri):
		"""XML Parser callback. Used internally"""
		self.check_data_buffer()
		if prefix: self.namespaces[uri]=prefix+':'
		else: self.xmlns=uri
	def DEBUG(self, level, text, comment=None):
		""" Gets all NodeBuilder walking events. Can be used for debugging if redefined."""
	def getDom(self):
		""" Returns just built Node. """
		self.check_data_buffer()
		return self._mini_dom
	def dispatch(self,stanza):
		""" Gets called when the NodeBuilder reaches some level of depth on it's way up with the built
			node as argument. Can be redefined to convert incoming XML stanzas to program events. """
	def stream_header_received(self,ns,tag,attrs):
		""" Method called when stream just opened. """
		self.check_data_buffer()
	def stream_footer_received(self):
		""" Method called when stream just closed. """
		self.check_data_buffer()

def XML2Node(xml):
	""" Converts supplied textual string into XML node. Handy f.e. for reading configuration file.
		Raises xml.parser.expat.parsererror if provided string is not well-formed XML. """
	return NodeBuilder(xml).getDom()

def BadXML2Node(xml):
	""" Converts supplied textual string into XML node. Survives if xml data is cutted half way round.
		I.e. "<html>some text <br>some more text". Will raise xml.parser.expat.parsererror on misplaced
		tags though. F.e. "<b>some text <br>some more text</b>" will not work."""
	return NodeBuilder(xml).getDom()
