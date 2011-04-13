def _namespace():
	import json
	import struct
	import sys
	def writeObj(obj):
		bytes = json.dumps(obj, ensure_ascii=False).encode('utf-8')
		if '--pipe' in sys.argv:
			sys.__stdout__.write(struct.pack('!H', len(bytes)))
			sys.__stdout__.write(bytes)
		else:
			sys.__stdout__.write(bytes)
			sys.__stdout__.write('\n')
		sys.__stdout__.flush()
	class Stdout(object):
		def write(self, s): writeObj({'msg': 'eval', 'result': s})
	class Stderr(object):
		def write(self, s): writeObj({'msg': 'error', 'str': s})
	sys.stdout = Stdout()
	sys.stderr = Stderr()
	g = globals()
	g['writeObj'] = writeObj

_namespace()
del _namespace
