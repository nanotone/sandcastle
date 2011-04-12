import json
import struct

def _writeObj():
	sys = __import__('sys') # hide the persistent sys in a closure
	def writeObj(obj):
		bytes = json.dumps(obj, ensure_ascii=False).encode('utf-8')
		if '--pipe' in sys.argv:
			sys.__stdout__.write(struct.pack('!H', len(bytes)))
			sys.__stdout__.write(bytes)
		else:
			sys.__stdout__.write(bytes)
			sys.__stdout__.write('\n')
		sys.__stdout__.flush()
	return writeObj

writeObj = _writeObj()

del _writeObj
