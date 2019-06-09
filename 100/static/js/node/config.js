
function GetNodeConfig() {
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/node_config/ykiveish',
	    type: "GET",
	    dataType: "script",
		async: true,
	    success: function (data) {    	
	    }
	});
}

$(document).ready(function() {
	GlobalIpAddress = GlobalIP + ":" + GlobalPort;
	GetNodeConfig();
});