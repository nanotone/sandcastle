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
		buffer = [StringIO.StringIO(), None]
		queueLock = threading.Lock()
		def queueStr(s, streamFd=1):
			with queueLock:
				if not buffer[1]:
					threading.Timer(0.01, checkFlushStr).start()
				elif streamFd != buffer[1]:
					flushStr()
				buffer[0].write(s)
				buffer[1] = streamFd
		def checkFlushStr():
			with queueLock: flushStr()
		def flushStr():
			if buffer[1] == 1:
				writeObj({'msg': 'eval', 'result': buffer[0].getvalue()})
			else:
				writeObj({'msg': 'error', 'str': buffer[0].getvalue()})
			buffer[0] = StringIO.StringIO()
			buffer[1] = None
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
	g = globals()
	g['writeObj'] = writeObj

_namespace()
del _namespace

