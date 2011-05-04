import weakref as _weakref

import protocol as _protocol


_elements = _weakref.WeakValueDictionary()
def _eventHandlerHook(msg):
	try:
		_elements[msg['id']].triggerEvent(msg['type'])
	except: pass
_protocol.addMessageHook('event', _eventHandlerHook)


class _Element(object):
	_nextId = 0

	def __init__(self, **kwargs):
		assert self.__class__ is not _Element
		self.id = _Element._nextId
		self.parent = None
		self.eventListeners = None
		_Element._nextId += 1
		_elements[self.id] = self
		if self.id:
			_protocol.writeObj({'msg': 'create', 'id': self.id, 'type': self.__class__.__name__})
		if not kwargs.get('detached'):
			_defaultContainer.children.append(self)

	def __del__(self):
		_protocol.writeObj({'msg': 'del', 'id': self.id})

	def __repr__(self):
		return "<%s Element %d>" % (self.__class__.__name__, self.id)

	def click(self, cb):
		if not callable(cb):
			raise TypeError()
		if not self.eventListeners:
			self.eventListeners = {'click': [cb]}
			_protocol.writeObj({'msg': 'listen', 'id': self.id})
		else:
			listeners = self.eventListeners.get('click')
			if not listeners:
				self.eventListeners['click'] = listeners = [cb]
			elif cb not in listeners: listeners.append(cb)

	def triggerEvent(self, eventType):
		for cb in self.eventListeners.get(eventType, ()): cb()

	def removeEventListener(self, eventType, cb=None):
		eventListeners = self.eventListeners.get(eventType)
		if not eventListeners: return # no listeners for eventType
		if not cb:
			del self.eventListeners[eventType]
		else:
			try:
				eventListeners.remove(cb)
			except: return
			if not eventListeners:
				del self.eventListeners[eventType]
		if not self.eventListeners:
			_protocol.writeObj({'msg': 'unlisten', 'id': self.id})

	def removeFromParent(self):
		self.parent.children.remove(self)
		return self


class _Simple(_Element):

	def __init__(self, text=None, **kwargs):
		_Element.__init__(self, **kwargs)
		self._text = u""
		self.text(text)

	def text(self, text=None):
		if text is not None:
			try:
				self._text = unicode(text)
			except UnicodeDecodeError:
				self._text = text.decode('latin-1')
			_protocol.writeObj({'msg': 'text', 'id': self.id, 'text': self._text})
		return self._text

	def __repr__(self):
		text = self._text.encode('ascii', 'replace')
		if len(text) > 8: text = text[:8] + '...'
		return "<%s %r>" % (type(self).__name__, text)


class _NodeList(list):

	def __init__(self, owner):
		self._owner = owner

	def __delitem__(self, key):
		nodes = self.__getitem__(key)
		if type(key) is int: nodes = (nodes,)
		for node in nodes: node.parent = None
		list.__delitem__(self, key)
		_protocol.writeObj({'msg': 'setChildren', 'parent': self._owner.id, 'children': [node.id for node in self]})

	def __delslice__(self, i, j):
		return self.__delitem__(slice(i, j))

	def __iadd__(self, other):
		self.extend(other)
		return self

	def __imul__(self, other):
		self[:] = self * other
		return self

	def __setitem__(self, key, value):
		if type(key) is int:
			value = self._checkType(value)
			self._checkAncestor(value)
			try:
				oldNodes = [self.__getitem__(key)]
			except IndexError: raise IndexError("list assignment index out of range") # more accurate msg for setter
		else:
			value = [self._checkType(v) for v in value]
			for v in value: self._checkAncestor(v)
			oldNodes = self.__getitem__(key)
		nodeSet = set(self) - set(oldNodes)
		for v in ([value] if type(key) is int else value):
			if v in nodeSet:
				raise ValueError("Duplicate %r Element not allowed" % v)
			nodeSet.add(v)
		list.__setitem__(self, key, value)
		for node in oldNodes:
			node.parent = None
		for node in self:
			node.parent = self._owner
		_protocol.writeObj({'msg': 'setChildren', 'parent': self._owner.id, 'children': [node.id for node in self]})

	def __setslice__(self, i, j, sequence): # because py2.* is dumb, even though this is deprecated in 2.0
		return self.__setitem__(slice(i, j), sequence)

	def _checkAncestor(self, node):
		if isinstance(node, _Complex) and (self._owner is node or self._owner.hasAncestor(node)):
			raise ValueError("Cannot make %r a child of %r" % (node, self._owner))

	def _checkType(self, node):
		if type(node) in (str, unicode): return Text(node, detached=True)
		if isinstance(node, _Element): return node
		raise TypeError("%r must be a string or Element, not %s" % (node, type(node).__name__))

	def append(self, obj):
		self.insert(len(self), obj)
		#self[len(self):len(self)] = [obj] # pydoc: definition 5.6.4

	def extend(self, iterable):
		self[len(self):len(self)] = iterable # pydoc: definition 5.6.4

	def insert(self, index, obj):
		if type(index) is float:
			raise TypeError("integer argument expected, got float") # python 3 behavior
		try: index = int(index)
		except TypeError:
			raise TypeError("'%s' object cannot be interpreted as an integer" % type(index).__name__) # py3
		obj = self._checkType(obj)
		self._checkAncestor(obj)
		if obj in self:
			raise ValueError("Duplicate %r Element not allowed" % obj)
		if index < 0: index = 0
		elif index > len(self): index = len(self)
		list.insert(self, index, obj) # commit
		obj.parent = self._owner
		_protocol.writeObj({'msg': 'add', 'parent': self._owner.id, 'index': index, 'child': obj.id})
		#self[index:index] = obj # pydoc: definition 5.6.4

	def pop(self, index=-1):
		try: child = self[index]
		except IndexError: raise IndexError("pop index out of range")
		list.__delitem__(self, index)
		child.parent = None
		_protocol.writeObj({'msg': 'remove', 'id': child.id})
		return child

	def remove(self, value):
		try: self.pop(self.index(value))
		except ValueError: raise ValueError("list.remove(x): x not in list")
		#del self[self.index(value)] # pydoc: definition 5.6.4

	def reverse(self):
		list.reverse(self)
		_protocol.writeObj({'msg': 'setChildren', 'parent': self._owner.id, 'children': [node.id for node in self]})

	def sort(cmp=None, key=None, reverse=False):
		list.sort(cmp, key, reverse)
		_protocol.writeObj({'msg': 'setChildren', 'parent': self._owner.id, 'children': [node.id for node in self]})


class _Complex(_Element):

	def __init__(self, *nodes, **kwargs):
		_Element.__init__(self, **kwargs)
		object.__setattr__(self, 'children', _NodeList(self))
		self.children.extend(nodes) # TODO: initial self.add's can skip dupe checks

	def __enter__(self):
		global _defaultContainer
		object.__setattr__(self, '_defaultContainer', _defaultContainer)
		_defaultContainer = self

	def __exit__(self, exc_type, exc_value, tb):
		global _defaultContainer
		_defaultContainer = self._defaultContainer

	def __setattr__(self, name, value):
		if name == 'children':
			self.children[:] = value
		else:
			object.__setattr__(self, name, value)

	def add(self, node):
		try: self.children.remove(node)
		except: pass
		self.children.append(node)

	def remove(self, node):
		self.children.remove(node)

	def clear(self):
		if self.children: del self.children[:]

	def hasAncestor(self, obj):
		return self.parent and (self.parent is obj or self.parent.hasAncestor(obj))



for name in ("Button", "Field", "Link", "Text"):
	globals()[name] = type(name, (_Simple,), {})

for name in ("Stack", "Flow", "Emphasized", "Strong", "Huge", "Large", "Small", "Tiny"):
	globals()[name] = type(name, (_Complex,), {})


root = Stack(detached=True)
_defaultContainer = root



if __name__ == '__main__': pass
