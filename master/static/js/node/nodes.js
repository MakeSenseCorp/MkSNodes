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

function Redirect(url) {
	window.location.href = url;
}

function SendActionToMaster(node_uuid, action_id) {
	console.log(node_uuid + ", " + action_id);

	var action = "None";
	switch(action_id) {
		case 0: 
			return;
		case 1:
			action = "Start"
			break;
		case 2:
			action = "Pause"
			break;
		case 3:
			action = "Stop"
			break;
	}

	var RequestData = {
		request: "set_node_status",
		json: `{ "uuid":"` + node_uuid + `",
				"action":"` + action + `"}`
	};

	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/set/node_action/ykiveish',
	    type: "POST",
	    dataType: "json",
	    data: RequestData,
		async: true,
	    success: function (data) {
	    }
	});
}

var GetShellTextInterval = 0;
function ExitShell() {
	clearInterval(GetShellTextInterval);
}

function GetShellText(node_uuid) {
	var RequestData = {
		request: "set_node_status",
		json: `{ "uuid":"` + node_uuid + `",
				"action":"shell"}`
	};

	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/set/node_action/ykiveish',
	    type: "POST",
	    dataType: "json",
	    data: RequestData,
		async: true,
	    success: function (data) {
	    	if (data.shell != null) {
	    		var objNodeShell = document.getElementById('idMasterShellModalText');
		    	data.shell.forEach(function(item) {
					objNodeShell.value += item;
					objNodeShell.scrollTop = objNodeShell.scrollHeight;
				});
		    	
	    	}
	    }
	});
}

function OpenRealTimeTrace(node_uuid, status) {
	if (status) {
		var instance = ModalBuilder.GetInstance();
		var html = `
			<form role="form">
				<div class="form-group">
					<textarea class="form-control" style="background-color: black;font-size: 1em;font-family: Verdana, Arial, Helvetica, sans-serif;color:White;" rows="15" id="idMasterShellModalText" disabled></textarea>
				</div>
			</div>
		`;
		instance.Create(html);
		instance.RegisterCloseEvent(ExitShell);
		instance.SetTitle("Node's Shell");
		instance.Show();

		GetShellTextInterval = setInterval(GetShellText, 1000, node_uuid);
	}
}

function GetNodes() {
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/node_list/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	console.log(data);
	    	var jsonData = JSON.parse(data);
	    	objSocketTable.CreateHead(["UUID","Type","IP","Port","Action","View","Status"]);

	    	var objList = [];
	    	jsonData.payload.list.forEach(function(item) {
	    		if (1 == item.type) {
	    			var edit = `
		    			<span data-feather=\"shield\" onClick=\"\"></span>
		    		`;
	    		} else {
		    		var edit = `
		    			<span data-feather=\"play-circle\" onClick=\"SendActionToMaster('`+item.uuid+`',1);\"></span>
		    			<span data-feather=\"pause-circle\" onClick=\"SendActionToMaster('`+item.uuid+`',2);\"></span>
		    			<span data-feather=\"stop-circle\" onClick=\"SendActionToMaster('`+item.uuid+`',3);\"></span>
		    			<span data-feather=\"terminal\" onClick=\"OpenRealTimeTrace('`+item.uuid+`',`+((item.status == "Running") ? 1 : 0)+`);\"></span>
		    		`;
	    		}

	    		if ("Stopped" == item.status) {
	    			color = "red";
	    		} else {
	    			color = "green";
	    		}

	    		objList.push([item.uuid, item.type, item.ip, item.port, edit, "<span data-feather=\"eye\" onClick=\"Redirect('http://" + item.ip + ":80" + item.widget_port + "');\"></span>", "<span style=\"color:" + color + "\">" + item.status + "</span>"])
	    	});

	    	objSocketTable.CreateBody(objList);
	    	document.getElementById('idNodeList').innerHTML = objSocketTable.CreateTable();
	    	feather.replace();
	    }
	});
}

var aIntervalGetSockets = setInterval (GetNodes, 5000);

$(document).ready(function() {
	GlobalIpAddress = GlobalIP + ":" + GlobalPort;
	GetNodes();
});