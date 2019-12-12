function GetNodeInfo() {
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/node_info/ykiveish',
	    type: "POST",
	    data: {name:"amit",id:1},
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	console.log(data);
	    }
	});
}

function GetNodeWidget() {
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/node_widget/ykiveish',
	    type: "GET",
	    dataType: "script",
		async: false,
	    success: function (data) {    	
	    }
	});
}

var ConvertHEXtoString = function(hexx) {
	var hex = hexx.toString();//force conversion
	var str = '';
	for (var i = 0; (i < hex.length && hex.substr(i, 2) !== '00'); i += 2) {
		str += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
	}
	return str;
}

$(document).ready(function() {
	GlobalIpAddress = GlobalIP + ":" + GlobalPort;

	// Gey makesense api instanse.
	var api = MkSAPIBuilder.GetInstance();
	api.SetGlobalGatewayIP(GlobalIP);

	api.ConnectGateway(function() {
		console.log("Connection to Gateway was established.");
		api.SendCustomCommand(NodeUUID, "get_file", {
			ui_type: "config",
			file_type: "html",
			file_name: ""
		}, function(res) {
			iframe = document.getElementById("id_context");
			iframe.srcdoc = ConvertHEXtoString(res.data.payload.content);
		});
	});
});