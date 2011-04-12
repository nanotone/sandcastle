import sys

import protocol

class Stdout(object):
	def write(self, s): protocol.writeObj({'msg': 'eval', 'result': s})
sys.stdout = Stdout()

class Stderr(object):
	def write(self, s): protocol.writeObj({'msg': 'error', 'str': s})
sys.stderr = Stderr()

del sys
