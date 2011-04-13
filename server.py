import os.path
import subprocess

import tornado.ioloop
import tornado.web

import tornadio

class MainHandler(tornado.web.RequestHandler):
	def get(self):
		self.write("""<html><head>
<link rel="stylesheet" href="static/style.css" type="text/css" />
<script type="text/javascript" src="http://ajax.googleapis.com/ajax/libs/jquery/1.5.1/jquery.min.js"></script>
<script type="text/javascript" src="/static/Socket.IO/socket.io.js"></script>
<script type="text/javascript" src="/static/sandcastle.js"></script>
</head><body><pre id="log"></pre><form id="cmd"><input /></form></body></html>
""")

import struct

class SocketHandler(tornadio.SocketConnection):
	def on_open(self, request, **kwargs):
		print "OPEN", repr(self)
		self.proc = subprocess.Popen(['python', 'sandbox.py', '--interactive', '--pipe'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
		self.procFd = self.proc.stdout.fileno()
		globalLoop.add_handler(self.procFd, self.procEvent, globalLoop.READ)
	def procEvent(self, fd, events):
		assert fd == self.procFd
		try:
			msgLen = self.proc.stdout.read(2)
			if len(msgLen) != 2: raise EOFError
			msgLen = struct.unpack('!H', msgLen)[0]
			msg = self.proc.stdout.read(msgLen)
			if len(msg) != msgLen: raise EOFError
			msg = msg.decode('utf-8')
			print "sending", msg, "to client"
			self.send(msg)
		except EOFError:
			self.on_close()
			# TODO: inform client
	def on_message(self, message):
		if type(message) is unicode:
			message = message.encode('utf-8')
		if type(message) is str:
			try:
				self.proc.stdin.write(struct.pack('!H', len(message)))
				self.proc.stdin.write(message)
				self.proc.stdin.flush()
			except IOError:
				print "IOError... broken pipe?"
				try:
					self.proc.kill()
					self.proc = None
				finally:
					self.cleanup()
		else:
			print "unknown msg", repr(message)
	def on_close(self):
		print "CLOSE"
		self.cleanup()
	def cleanup(self):
		if self.proc:
			self.on_message('0')
			if self.proc:
				self.proc.communicate()
				self.proc = None
		if self.procFd:
			globalLoop.remove_handler(self.procFd)
			self.procFd = None

application = tornado.web.Application([
	(r'/sandcastle', MainHandler),
	tornadio.get_router(SocketHandler).route(),
],
	static_path=os.path.join(os.path.dirname(__file__), 'static'),
)
application.listen(5413)


globalLoop = tornado.ioloop.IOLoop.instance()
globalLoop.start()
