function DOMTableContainer() {
	self = this;

	this.DOMTable = "<div class='table-responsive'>" +
					"<table class='table table-striped table-sm'><thead>[HEAD]</thead><tbody>[BODY]</tbody></table></div>";
	this.HTML = "";
	this.HEAD = "";
	this.BODY = "";

	this.CreateHead = function(items) {
		this.HEAD = "<tr>";

		for (i = 0; i < items.length; i++) {
			this.HEAD += "<th>" + items[i] + "</th>";
		}

		this.HEAD += "</tr>"
	}

	this.CreateBody = function(items) {
		this.BODY = "";

		for (i = 0; i < items.length; i++) {
			item = items[i];
			this.BODY += "<tr>";
			for (j = 0; j < item.length; j++) {
				this.BODY += "<td>" + item[j] + "</td>";
			}
			this.BODY += "</tr>";
		}
	}

	this.CreateTable = function() {
		this.HTML = this.DOMTable;

		this.HTML = this.HTML.split("[HEAD]").join(self.HEAD);
		this.HTML = this.HTML.split("[BODY]").join(self.BODY);

		return HTML;
	}

	return this;
}

var objSocketTable = DOMTableContainer();

function GetSockets() {
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/socket_list/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	console.log(data);
	    	var jsonData = JSON.parse(data);
	    	objSocketTable.CreateHead(["Local Type","UUID","IP","Port","Type"]);

	    	var objList = [];
	    	jsonData.payload.list.forEach(function(item) {
	    		objList.push([item.local_type, item.uuid, item.ip, item.port, item.type])
	    	});

	    	objSocketTable.CreateBody(objList);
	    	document.getElementById('idConnectionsList').innerHTML = objSocketTable.CreateTable();
	    }
	});
}

var aIntervalGetSockets = setInterval (GetSockets, 5000);
$(document).ready(function() {
	console.log(navigator.userAgent);
	if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/.test(navigator.userAgent)) {
    	window.location.href = "mobile/app";
	}

	GlobalIpAddress = GlobalIP + ":" + GlobalPort;
	GetSockets();
});