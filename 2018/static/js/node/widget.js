// TODO - Must follow code convention.
var html_1982 = `
	<div class="input-group input-group-sm mb-3">
		<div class="input-group-prepend">
			<span class="input-group-text">Song</span>
		</div>
		<input id="id-widget-1981-url" type="text" class="form-control" aria-label="" aria-describedby="inputGroup-sizing-sm">
		<span data-feather="arrow-right-circle" onClick="F_1982_SetUrl();"></span>
	</div>
	<div>
		<span data-feather="pause-circle" onClick="F_1982_Pause();"></span>
		<span data-feather="play-circle" onClick="F_1982_Play();"></span>
		<span data-feather="stop-circle" onClick="F_1982_Stop();"></span>
		<span data-feather="volume-1" onClick="F_1982_VolDown();"></span>
		<span id="id-widget-1982-vol" class="badge badge-light">0%</span>
		<span data-feather="volume-2" onClick="F_1982_VolUp();"></span>
	</div>
`;

// ID of DOM component we mast recieve on init
document.getElementById('idWidget').innerHTML = html_1982;

function F_1982_Init() {
	feather.replace();
}

function F_1982_SetUrl() {
	console.log("SetUrl");
	playerUrl = document.getElementById('id-widget-1982-url').value;

	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/player/set_url/ykiveish',
	    type: "POST",
	    data: {url: playerUrl},
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	console.log(data);
	    }
	});
}

function F_1982_Play() {
	console.log("Play");
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/player/play/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	console.log(data);
	    }
	});
}

function F_1982_Stop() {
	console.log("Stop");
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/player/stop/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	console.log(data);
	    }
	});
}

function F_1982_Pause() {
	console.log("Pause");
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/player/pause/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	console.log(data);
	    }
	});
}

function F_1982_VolUp() {
	console.log("Volume Up");
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/player/vol_up/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	document.getElementById('id-widget-1982-vol').innerHTML = data.vol + "%";
	    }
	});
}

function F_1982_VolDown() {
	console.log("Volume Down");
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/player/vol_down/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	document.getElementById('id-widget-1982-vol').innerHTML = data.vol + "%";
	    }
	});
}

F_1982_Init();