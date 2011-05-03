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
		buf = [None]
		queueLock = threading.Lock()
		def flushStr():
			with queueLock:
				if buf[0]:
					writeObj({'msg': 'eval', 'result': buf[0].getvalue()})
					buf[0] = None
		class Stdout(object):
			def write(self, s):
				if type(s) not in (str, unicode, buffer):
					raise TypeError("argument 1 must be string or read-only character buffer, not " + type(s).__name__)
				with queueLock:
					if not buf[0]:
						threading.Timer(0.010, flushStr).start()
						buf[0] = StringIO.StringIO()
					buf[0].write(s)
		class Stderr(object):
			def write(self, s):
				if type(s) not in (str, unicode, buffer):
					raise TypeError("argument 1 must be string or read-only character buffer, not " + type(s).__name__)
				with queueLock:
					if buf[0]:
						writeObj({'msg': 'eval', 'result': buf[0].getvalue()})
						buf[0] = None
				writeObj({'msg': 'error', 'str': s})
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

