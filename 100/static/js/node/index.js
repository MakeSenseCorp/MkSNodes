
function GetNodeWidget() {
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/node_widget/ykiveish',
	    type: "GET",
	    dataType: "script",
		async: true,
	    success: function (data) {    	
	    }
	});
}

$(document).ready(function() {
	GlobalIpAddress = GlobalIP + ":" + GlobalPort;
	GetNodeWidget();
});