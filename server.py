import struct
import subprocess

import tornado.ioloop
import tornado.web

import tornadio


class SocketHandler(tornadio.SocketConnection):
	def on_open(self, request, **kwargs):
		print "OPEN", repr(self)
		self.started = False
		self.proc = None
		self.procFd = 0
	def start(self, clientScript=None):
		cmd = ['python', 'sandbox.py', '--interactive', '--pipe']
		if clientScript:
			cmd.append(clientScript)
		self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
		self.procFd = self.proc.stdout.fileno()
		globalLoop.add_handler(self.procFd, self.procEvent, globalLoop.READ)
		self.started = True
	def procEvent(self, fd, events):
		assert fd == self.procFd
		try:
			msgLen = self.proc.stdout.read(2)
			if len(msgLen) != 2: raise EOFError
			msgLen = struct.unpack('!H', msgLen)[0]
			msg = self.proc.stdout.read(msgLen)
			if len(msg) != msgLen: raise EOFError
			msg = msg.decode('utf-8')
			print "sending", msg
			self.send(msg)
		except EOFError:
			self.on_close()
			# TODO: inform browser
	def on_message(self, message):
		if type(message) is unicode:
			message = message.encode('utf-8')
		if type(message) is str:
			print "received %r" % message
			if not self.started:
				self.start(message)
				return
			try:
				self.proc.stdin.write(struct.pack('!H', len(message)))
				self.proc.stdin.write(message)
				self.proc.stdin.flush()
			except IOError:
				print "IOError... broken pipe?"
				globalLoop.remove_handler(self.procFd) # do this early
				self.procFd = None
				try:
					self.proc.kill()
					self.proc = None
				finally:
					pass # TODO: inform browser
		else:
			print "unknown msg", repr(message)
	def on_close(self):
		print "CLOSE", repr(self)
		if self.procFd:
			globalLoop.remove_handler(self.procFd)
			self.procFd = None
		if self.proc:
			self.on_message('0')
			self.proc = None # leave it for gc

application = tornado.web.Application([ tornadio.get_router(SocketHandler).route() ])
application.listen(5413)

globalLoop = tornado.ioloop.IOLoop.instance()
globalLoop.start()
