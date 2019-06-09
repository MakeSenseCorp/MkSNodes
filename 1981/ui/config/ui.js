
// Gey makesense api instanse.
var api = MkSAPIBuilder.GetInstance();

/* *************************
** *** COMMON **************
** *************************/ 

var GlobalIpAddress = "0.0.0.0:0";

function Modal () {
	this.ModalID 		= "#idMakesenseModal";
	this.ModalIDContent = "idMakesenseModalContent";

	this.Create = function (content) {
		document.getElementById(this.ModalIDContent).innerHTML = content;
		$(this.ModalID).modal({
			keyboard: false,
			backdrop: "static"
		});
	}

	this.Show = function () {
		$(this.ModalID).modal('show');
	}

	this.Hide = function () {
		$(this.ModalID).modal('hide');
	}

	this.Remove = function () {
		$(this.ModalID).modal('dispose');
	}

	return this;
}

// ModalBuilder is a SingleTone class.
var ModalBuilder = (function () {
	var Instance;

	ModalHTML = `
		<div class="modal fade" id="idMakesenseModal" tabindex="-1" role="dialog" aria-labelledby="exampleModalCenterTitle" aria-hidden="true">
			<div class="modal-dialog modal-dialog-centered" role="document">
				<div class="modal-content">
					<div class="modal-header">
						<h5 class="modal-title" id="exampleModalCenterTitle">Information</h5>
						<button type="button" class="close" data-dismiss="modal" aria-label="Close">
							<span aria-hidden="true">&times;</span>
						</button>
					</div>
					<div class="modal-body" id="idMakesenseModalContent"></div>
					<div id="idMakeSenseModalFooter"></div>
				</div>
			</div>
		</div>
	`;

	ModalFooterHTML = `
		<div class="modal-footer">
			<button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
			<button type="button" class="btn btn-primary">Save changes</button>
		</div>
	`;

	function CreateInstance () {
		document.getElementById('idModalSection').innerHTML = ModalHTML;
		var obj = new Modal();
		return obj;
	}

	return {
		GetInstance: function () {
			if (!Instance) {
				Instance = CreateInstance();
			}

			return Instance;
		}
	};
})();

function DOMTableContainer(name) {
	this.Name = name;

	this.DOMTable = `
					<div class='table-responsive'>
						<table class='table table-striped table-sm'>
							<thead>[HEAD]</thead>
							<tbody id="idMakeSense` + this.Name + `">[BODY]</tbody>
						</table>
					</div>
					`;
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

		this.HTML = this.HTML.split("[HEAD]").join(this.HEAD);
		this.HTML = this.HTML.split("[BODY]").join(this.BODY);

		return this.HTML;
	}

	this.UpdateTable = function(items) {
		html = "";

		for (i = 0; i < items.length; i++) {
			item = items[i];
			html += "<tr>";
			for (j = 0; j < item.length; j++) {
				html += "<td>" + item[j] + "</td>";
			}
			html += "</tr>";
		}

		document.getElementById("idMakeSense" + this.Name).innerHTML += html;
	}

	return this;
}

function N_1981_Object_BLL (key) {
	this.Key 			= key;
	this.SwitchesState	= {};

	this.GetNodeInformation = function (callback) {
		api.GetNodeSensorsInfo(NodeUUID, function(res){
			callback(res.data.payload);
		});
	}

	this.TriggerSwitch = function (id, callback) {
		sw = this.SwitchesState[id];
		sw.value = (sw.value == "0") ? "1" : "0";
		var payload = {
			sensors: [
				{
					action: "trigger_switch",
					id: sw.id,
					value: sw.value,
					type: sw.type
				}
			]
		}
		api.SetNodeSensorsInfo(NodeUUID, payload, function(res){
			callback(res.data.payload);
		});
		document.getElementById("switch_id_" + id).style.color = ("0" == sw.value) ? "Red" : "Green";
	}

	this.UpdateSwitchInformation = function(id, info, callback) {
		sw = this.SwitchesState[id];
		var payload = {
			sensors: [
				{
					action: "update_sensor_info",
					name: info.name,
					is_private: info.is_private,
					is_triggered_by_luminance: info.is_triggered_by_luminance,
					is_triggered_by_movement: info.is_triggered_by_movement,
					id: sw.id,
					value: sw.value,
					type: sw.type
				}
			]
		}
		api.SetNodeSensorsInfo(NodeUUID, payload, function(res){
			callback(res.data.payload);
		});
	}

	return this;
}

function N_1981_Object_UI (bll) {
	this.BLL 			= bll;
	this.Switches 		= {};
	this.Groups 		= {};
	// this.Timer 			= new TimerBuilder();
	this.Defines 		= {
								ROWSIZE: 		12,
								NOGROUP: 		255,
								ON: 			1,
								OFF: 			0,
								DIRECTION_UP: 	1,
								DIRECTION_DOWN: 2,
	};
	this.ConfigHTML = `
		<form>
			<div class="form-group">
				<label for="exampleInputEmail1">Name</label>
				<input id="idName_1981_Sensor" type="text" class="form-control" aria-describedby="emailHelp" placeholder="Name">
			</div>
			<form>
				<div class="form-group">
					<label for="exampleInputEmail1">Accesability & Privacy</label>
					<small id="email" class="form-text text-muted">How do you want these sensors to be viewed by others.</small>
				</div>
				<div class="custom-control custom-checkbox my-1 mr-sm-2">
					<input type="checkbox" class="custom-control-input" id="idNode1981Private">
					<label class="custom-control-label" for="idNode1981Private">Private (Don't expose to others)</label>
				</div>
				<div class="custom-control custom-checkbox my-1 mr-sm-2">
					<input type="checkbox" class="custom-control-input" id="idNode1981LuminaceSensor">
					<label class="custom-control-label" for="idNode1981LuminaceSensor">Allow trigger on luminance</label>
				</div>
				<div class="custom-control custom-checkbox my-1 mr-sm-2">
					<input type="checkbox" class="custom-control-input" id="idNode1981MovementSensor">
					<label class="custom-control-label" for="idNode1981MovementSensor">Allow trigger on movement</label>
				</div>
			</form>
			<div class="form-group">
				<button type="button" class="btn btn-outline-primary my-1" onClick="N_1981_UI.UpdateSwitchInfo([ID]);">Update</button>
			</div>
		</form>
		<div id="idTimer1981"></div>
	`;

	this.Init = function() {
		this.BLL.GetNodeInformation(function(data) {
			console.log(data);
			this.GetNodeInfoHandler(data);
		});
	}

	this.Run = function () {

	}

	this.GetNodeInfoHandler = function(data) {
		if (data === null)
			return;

		var objSocketTable = new DOMTableContainer("Switches");
		objSocketTable.CreateHead(["Name","ID","Description","Type","Action","Config"]);

		var objList = [];
		data.forEach(function(element) {
			this.Switches[element.id] = element;

			var color = ("0" == element.value) ? "Red" : "Green";
			objList.push([element.name, element.id, element.description, element.type, "<span id=\"switch_id_" + element.id + "\" style=\"cursor: pointer;color: " + color + "\" data-feather=\"power\" onClick=\"N_1981_BLL.TriggerSwitch(" + element.id + ");\"></span>","<span style=\"cursor: pointer;\" data-feather=\"settings\" onClick=\"N_1981_UI.SettingsHandler(" + element.id + "," + element.group + ");\"></span>"])

			// Add to group.
			if (element.group != this.Defines.NOGROUP) {
				if (!(element.group in this.Groups)) {
					this.Groups[element.group] = {
												items: [element]
											};
				} else {
					item = this.Groups[element.group];
					item.items.push(element);
					this.Groups[element.group] = item;
				}
			}

			this.BLL.SwitchesState[element.id] = { 	
													id: element.id,
													value: element.value,
													type: element.type
												 };
		});

		objSocketTable.CreateBody(objList);
		html = objSocketTable.CreateTable();

		// Update UI.
		document.getElementById('idConfig').innerHTML = html;

		feather.replace();
	}

	this.SettingsHandler = function(id, group) {
		console.log(id + ", " + group);

		if (group != this.Defines.NOGROUP) {
			// Dual switch.
		} else {
			// Single switch.
		}

		var Sensor = this.Switches[id];
		var instance = ModalBuilder.GetInstance();

		html = this.ConfigHTML.split("[ID]").join(id);
		instance.Create(html); // Passing content of modal window.

		// this.Timer.Create("idTimer1981", "N_1981_UI.Timer"); // Passing id of a container & class path to timer object.
		// this.Timer.Load(this.Key, id);

		console.log(Sensor);
		document.getElementById('idName_1981_Sensor').value 		= Sensor.name;
		document.getElementById("idNode1981Private").checked 		= ("true" == Sensor.is_private.toLowerCase()) ? true : false;
		document.getElementById("idNode1981LuminaceSensor").checked = ("true" == Sensor.is_triggered_by_luminance.toLowerCase()) ? true : false;
		document.getElementById("idNode1981MovementSensor").checked = ("true" == Sensor.is_triggered_by_movement.toLowerCase()) ? true : false;

		instance.Show();
	}

	this.UpdateSwitchInfo = function(id) {
		var name 					= document.getElementById("idName_1981_Sensor").value;
		var isPrivate 				= document.getElementById("idNode1981Private").checked;
		var isTriggeredByLuminance 	= document.getElementById("idNode1981LuminaceSensor").checked;
		var isTriggeredByMovement 	= document.getElementById("idNode1981MovementSensor").checked;

		var RequestData = {
				name: name,
				is_private:isPrivate,
				is_triggered_by_luminance:isTriggeredByLuminance,
				is_triggered_by_movement:isTriggeredByMovement
		};

		console.log(id);

		this.BLL.UpdateSwitchInformation(id, RequestData, function(res) {

		});
	}

	return this;
}

var N_1981_BLL 	= N_1981_Object_BLL("ykiveish");
var N_1981_UI 	= N_1981_Object_UI(N_1981_BLL);

api.ConnectGateway(function() {
	console.log("Connection to Gateway was established.");

	N_1981_UI.Init();
});