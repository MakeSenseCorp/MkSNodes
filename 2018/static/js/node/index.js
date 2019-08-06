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

$(document).ready(function() {
	GlobalIpAddress = GlobalIP + ":" + GlobalPort;
	GetNodeInfo();
	GetNodeWidget();
});