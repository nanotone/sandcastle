import json
import subprocess

import tornado.ioloop
import tornado.web
import tornado.websocket

# temporarily allow draft76 while browsers catch up
tornado.websocket.WebSocketHandler.allow_draft76 = (lambda self: True)

import tornadio


class SocketHandler(tornadio.SocketConnection):
	def on_open(self, request, **kwargs):
		print "OPEN", repr(self)
		self.started = False
		self.proc = None
		self.procFd = 0
	def start(self, clientScript=None):
		cmd = ['python', 'sandbox.py']
		if clientScript:
			cmd.append(clientScript)
		self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
		self.procFd = self.proc.stdout.fileno()
		globalLoop.add_handler(self.procFd, self.procEvent, globalLoop.READ)
		self.started = True
	def procEvent(self, fd, events):
		assert fd == self.procFd
		try:
			self.send(self.proc.stdout.readline())
		except (EOFError, IOError, ValueError):
			self.on_close()
			# TODO: inform browser
	def on_message(self, message):
		if isinstance(message, basestring):
			print "received %r" % message
			if not self.started:
				self.start(message)
				return
			try:
				self.proc.stdin.write(message + '\n')
				self.proc.stdin.flush()
			except IOError:
				print "IOError... broken pipe?"
				if self.procFd:
					try:
						globalLoop.remove_handler(self.procFd)  # do this early
					finally:
						self.procFd = None
				try:
					self.proc.kill()
				finally:
					self.proc = None  # TODO: inform browser
		else:
			print "unknown msg", repr(message)
	def on_close(self):
		print "CLOSE", repr(self)
		if self.procFd:
			globalLoop.remove_handler(self.procFd)
			self.procFd = None
		if self.proc:
			self.on_message('.')
			self.proc = None # leave it for gc

application = tornado.web.Application([ tornadio.get_router(SocketHandler).route() ])
application.listen(5413)

globalLoop = tornado.ioloop.IOLoop.instance()
globalLoop.start()
