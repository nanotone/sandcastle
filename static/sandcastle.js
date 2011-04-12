WEB_SOCKET_SWF_LOCATION = '/static/Socket.IO/lib/vendor/web-socket-js/WebSocketMain.swf';

var sock;
$(function() {
	sock = new io.Socket(window.location.hostname, {
		port: Number(window.location.port),
		transports: ['websocket',/*'flashsocket',*/'xhr-polling','jsonp-polling']
	});
	sock.on('message', function(data) {
		window.console.log("Received: " + data);
		data = JSON.parse(data);
		if (data.msg == 'eval') {
			pyLog(data.result);
		}
	});
	sock.connect();
	
	$('#cmd').submit(function() {
		var input = $(this).find('input');
		sock.send(JSON.stringify({msg:'eval', stmt:input.val()}));
		pyLog(">>> " + input.val() + "\n");
		input.val("");
		return false;
	});
});

function pyLog(s) {
	var log = $('#log');
	log.text(log.text() + s);
}
