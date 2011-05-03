import json

def _namespace():
	import struct
	import sys
	import threading
	try: import cStringIO as StringIO
	except ImportError: import StringIO
	if '--pipe' in sys.argv:
		def writeObj(obj):
			bytes = json.dumps(obj, ensure_ascii=False).encode('utf-8')
			sys.__stdout__.write(struct.pack('!H', len(bytes)))
			sys.__stdout__.write(bytes)
			sys.__stdout__.flush()
		buf = [StringIO.StringIO(), None]
		queueLock = threading.Lock()
		def queueStr(s, streamFd=1):
			with queueLock:
				if not buf[1]:
					threading.Timer(0.01, checkFlushStr).start()
				elif streamFd != buf[1]:
					flushStr()
				buf[0].write(s)
				buf[1] = streamFd
		def checkFlushStr():
			with queueLock: flushStr()
		def flushStr():
			if buf[1] == 1:
				writeObj({'msg': 'eval', 'result': buf[0].getvalue()})
			else:
				writeObj({'msg': 'error', 'str': buf[0].getvalue()})
			buf[0] = StringIO.StringIO()
			buf[1] = None
		class Stdout(object):
			def write(self, s):
				if type(s) not in (str, unicode, buffer):
					raise TypeError("argument 1 must be string or read-only character buffer, not " + type(s).__name__)
				queueStr(s)
		class Stderr(object):
			def write(self, s):
				if type(s) not in (str, unicode, buffer):
					raise TypeError("argument 1 must be string or read-only character buffer, not " + type(s).__name__)
				queueStr(s, 2)
		sys.stdout = Stdout()
		sys.stderr = Stderr()
	else:
		def writeObj(obj):
			print json.dumps(obj, ensure_ascii=False).encode('utf-8')


	messageHooks = {}
	def addMessageHook(msgType, hook):
		if not callable(hook): raise TypeError("'%s' object is not callable" % type(hook).__name__)
		hooks = messageHooks.get(msgType)
		if hooks is None:
			messageHooks[msgType] = hooks = [hook]
		elif hook not in hooks:
			hooks.append(hook)
	def removeMessageHook(msgType, hook):
		hooks = messageHooks.get(msgType)
		if hooks:
			try: hooks.remove(hook)
			except: pass
	def dispatchMessage(msg):
		for hook in messageHooks.get(msg.get('msg'), ()):
			hook(msg)

	g = globals()
	g['writeObj'] = writeObj
	g['addMessageHook'] = addMessageHook
	g['removeMessageHook'] = removeMessageHook
	g['dispatchMessage'] = dispatchMessage

_namespace()
del _namespace

