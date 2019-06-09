function N_1981_Object_BLL (key) {
	this.Lib 			= Common();
	this.Key 			= key;

	this.GetNodeInformation = function (callback) {
		this.Lib.GetNodeInfo(this.Key, function(data) {
			callback(data);
		});
	}

	this.TriggerSwitch = function (item, callback) {
		$.ajax({
		    url: 'http://' + GlobalIpAddress + '/set/node_sensor_info/' + this.Key + '/' + item.id + '/' + item.value,
		    type: "GET",
		    dataType: "json",
			async: true,
		    success: function (data) {
		    	callback(data);
		    }
		});
	}

	return this;
}

function TimerBuilder() {
	this.HTML = `
		<form>
			<div class="form-group">
				<label for="exampleInputEmail1">Timers</label>
				<div class="row">
					<div class="col">
						<input id="idMakeSenseStartTimer" type="text" class="form-control" placeholder="Time" data-date="" data-date-format="hh:ii" data-link-format="hh:ii>
						<span class="input-group-addon"><i class="glyphicon glyphicon-time"></i></span>
					</div>
					<div class="col">
						<div class="btn-group" role="group" aria-label="First group">
							<button id="idMakeSenseTimerDay_1" type="button" class="btn btn-secondary" onClick="[OBJECT].UpdateDaySelection(1);">San</button>
							<button id="idMakeSenseTimerDay_2" type="button" class="btn btn-secondary" onClick="[OBJECT].UpdateDaySelection(2);">Mon</button>
							<button id="idMakeSenseTimerDay_3" type="button" class="btn btn-secondary" onClick="[OBJECT].UpdateDaySelection(3);">Tue</button>
							<button id="idMakeSenseTimerDay_4" type="button" class="btn btn-secondary" onClick="[OBJECT].UpdateDaySelection(4);">Wed</button>
							<button id="idMakeSenseTimerDay_5" type="button" class="btn btn-secondary" onClick="[OBJECT].UpdateDaySelection(5);">Thu</button>
							<button id="idMakeSenseTimerDay_6" type="button" class="btn btn-secondary" onClick="[OBJECT].UpdateDaySelection(6);">Fri</button>
							<button id="idMakeSenseTimerDay_7" type="button" class="btn btn-secondary" onClick="[OBJECT].UpdateDaySelection(7);">Sat</button>
						</div>
					</div>
				</div>
			</div>
			<div class="custom-control custom-checkbox my-1 mr-sm-2">
				<input type="checkbox" class="custom-control-input" id="idMakeSenseSelectAllDays" onClick="[OBJECT].UpdateDaySelection(8);">
				<label class="custom-control-label" for="idMakeSenseSelectAllDays">Whole week</label>
			</div>
			<div id="idMakeSenseTimerActionContent" class="btn-group" role="group" aria-label="First group">
			</div>
			<div class="form-group">
				<button type="button" class="btn btn-outline-primary my-1" onClick="[OBJECT].AddNewTimer();">Add new timer</button>
			</div>
			<div class="form-group">
				<label for="exampleInputEmail1">Current timers list</label>
				<div id="[OBJECT]_table"></div>
			</div>
		</form>
	`;

	this.Days 					= {};
	this.ClassName 				= "";
	this.TimerTable 			= new DOMTableContainer("Timer");
	this.UUID 					= "";
	this.Key 					= "";
	this.Actions 				= null;
	this.SelectedActionIndex 	= -1;
	this.LastId 				= 0;

	this.SetActions = function(actions) {
		this.Actions = actions;
		var html = "";
		for (i = 0; i < actions.length; i++) {
			html += "<button id=\"idMakeSenseTimerAction_" + i + "\" type=\"button\" class=\"btn btn-secondary\" onClick=\"" + this.ClassName + ".UpdateActionSelection(" + i + ");\">" + actions[i] + "</button>";
		}
		document.getElementById("idMakeSenseTimerActionContent").innerHTML = html;
	}

	this.UpdateActionSelection = function(index) {
		// Select all unchecked
		for (i = 0; i < this.Actions.length; i++) {
			document.getElementById("idMakeSenseTimerAction_" + i).classList.remove('btn-danger');
			document.getElementById("idMakeSenseTimerAction_" + i).classList.add('btn-secondary');
		}

		document.getElementById("idMakeSenseTimerAction_" + index).classList.remove('btn-secondary');
		document.getElementById("idMakeSenseTimerAction_" + index).classList.add('btn-danger');

		this.SelectedActionIndex = index;
	}

	this.Create = function(id, className) {
		this.ClassName = className;
		html = this.HTML.split("[OBJECT]").join(this.ClassName);
		document.getElementById(id).innerHTML = html;

		this.Days[1] = ["idMakeSenseTimerDay_1", 0, "SAN"];
		this.Days[2] = ["idMakeSenseTimerDay_2", 0, "MON"];
		this.Days[3] = ["idMakeSenseTimerDay_3", 0, "TUE"];
		this.Days[4] = ["idMakeSenseTimerDay_4", 0, "WED"];
		this.Days[5] = ["idMakeSenseTimerDay_5", 0, "THU"];
		this.Days[6] = ["idMakeSenseTimerDay_6", 0, "FRI"];
		this.Days[7] = ["idMakeSenseTimerDay_7", 0, "SAT"];
		this.Days[8] = ["idMakeSenseTimerAllDays", 0];
	}

	// Load status of days.
	this.Load = function(key, id) {
		self = this;

		this.Key 	= key;
		this.UUID 	= id;

		$.ajax({
		    url: 'http://' + GlobalIpAddress + '/get/node_timer_items/' + self.Key + "/" + self.UUID,
		    type: "GET",
		    dataType: "json",
			async: true,
		    success: function (data) {
		    	console.log(data.timers);

		    	var objList = [];
		    	for (i = 0; i < data.timers.length; i++) {
		    		var enabled = "Enabled";
		    		if ("0" == data.timers[i].enabled) {
		    			enabled = "Disabled";
		    		}

		    		if ("All" == data.timers[i].days) {
		    			days = "All";
		    		} else {
		    			days = data.timers[i].days.join("<br>");
		    		}

		    		objList.push([data.timers[i].start, days, data.timers[i].action, enabled,"<span data-feather=\"delete\" onClick=\"" + self.ClassName + ".RemoveTimer(this, " + data.timers[i].id + ");\"></span>"]);
		    		if (self.LastId < data.timers[i].id) {
		    			self.LastId = data.timers[i].id;
		    		}
		    	}

		    	self.TimerTable.CreateHead(["Start","Days","Action","Status",""]);
				self.TimerTable.CreateBody(objList);
				html = self.TimerTable.CreateTable();
				document.getElementById(self.ClassName + "_table").innerHTML = html;
				feather.replace();

				$('#idMakeSenseStartTimer').datetimepicker({
					language:  'uk',
        			weekStart: 1,
			        todayBtn:  1,
					autoclose: 1,
					todayHighlight: 1,
					startView: 1,
					minView: 0,
					maxView: 1,
					forceParse: 0
				});

				self.SetActions(data.actions);
		    }
		});
	}

	this.UpdateDaySelection = function(day) {
		if (8 == day) {
			for (i = 1; i < 8; i++) {
				if (0 == this.Days[day][1]) {
					document.getElementById(this.Days[i][0]).classList.remove('btn-secondary');
					document.getElementById(this.Days[i][0]).classList.add('btn-success');
					this.Days[i][1] = 1;
				} else {
					document.getElementById(this.Days[i][0]).classList.remove('btn-success');
					document.getElementById(this.Days[i][0]).classList.add('btn-secondary');
					this.Days[i][1] = 0;
				}
			}

			this.Days[day][1] = 1 - this.Days[day][1];

			return;
		}

		document.getElementById("idMakeSenseSelectAllDays").classList.remove("checked");
		document.getElementById("idMakeSenseSelectAllDays").checked = false;
		this.Days[8][1] = 0;

		if (0 == this.Days[day][1]) {
			document.getElementById(this.Days[day][0]).classList.remove('btn-secondary');
			document.getElementById(this.Days[day][0]).classList.add('btn-success');
			this.Days[day][1] = 1;
		} else {
			document.getElementById(this.Days[day][0]).classList.remove('btn-success');
			document.getElementById(this.Days[day][0]).classList.add('btn-secondary');
			this.Days[day][1] = 0;
		}		
	}

	this.AddNewTimer = function() {
		var SelectedDaysHtml 	= "";
		var SelectedDays  		= "[";
		var SelectedAction 		= this.Actions[this.SelectedActionIndex];
		var SelectedStart 		= document.getElementById("idMakeSenseStartTimer").value;

		if ("" == SelectedStart) {
			return;
		}

		if (-1 == this.SelectedActionIndex) {
			return;
		}

		if (1 == this.Days[8][1]) {
			SelectedDaysHtml = "\"All\"";
		} else {
			for (i = 1; i < 8; i++) {
				if (1 == this.Days[i][1]) {
					SelectedDaysHtml += this.Days[i][2] + "<br>";
					SelectedDays += "\"" + this.Days[i][2] + "\",";
				}
			}
			SelectedDays = SelectedDays.slice(0, -1);
			SelectedDays += "]"

			if ("" == SelectedDaysHtml) {
				return;
			}
		}

		this.TimerTable.UpdateTable([[SelectedStart, SelectedDaysHtml, SelectedAction, "Enabled", "<span data-feather=\"delete\" onClick=\"" + this.ClassName + ".RemoveTimer(this, " + this.LastId + ");\"></span>"]]);
		feather.replace();

		this.LastId = this.LastId + 1;
		var RequestData = {
			request: "add",
			json: `{ "id":` + this.LastId + `,
				"start":"` + SelectedStart + `",
				"days":` + SelectedDays + `,
				"action":"` + SelectedAction + `",
				"enabled": "1" }`
		};

		$.ajax({
		    url: 'http://' + GlobalIpAddress + '/set/node_timer_item/' + this.Key + "/" + this.UUID,
		    type: "POST",
		    dataType: "json",
		    data: RequestData,
			async: true,
		    success: function (data) {
		    }
		});
	}

	this.RemoveTimer = function(self, id) {
		var element = self.parentNode.parentNode; // TR
		element.parentNode.removeChild(element);

		var RequestData = {
			request: "remove",
			json: `{ "id":"` + id + `"}`
		};

		$.ajax({
		    url: 'http://' + GlobalIpAddress + '/set/node_timer_item/' + this.Key + "/" + this.UUID,
		    type: "POST",
		    dataType: "json",
		    data: RequestData,
			async: true,
		    success: function (data) {
		    }
		});
	}

	return this;
}

function N_1981_Object_UI (bll) {
	this.BLL 			= bll;
	this.Switches 		= {};
	this.Groups 		= {};
	this.Timer 			= new TimerBuilder();
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
				<button type="button" class="btn btn-outline-primary my-1" onClick="N_1981_UI.UpdateSwitchInfo([UUID]);">Update</button>
			</div>
		</form>
		<div id="idTimer1981"></div>
	`;

	this.Init = function() {
		this.BLL.GetNodeInformation(function(data) {
			this.GetNodeInfoHandler(data);
		});
	}

	this.Run = function () {

	}

	this.GetNodeInfoHandler = function(data) {
		if (data === null)
			return;

		if (data.sensors === null)
			return;

		var objSocketTable = new DOMTableContainer("Switches");
		objSocketTable.CreateHead(["Name","ID","Description","Type","Config"]);

		var objList = [];
		data.sensors.forEach(function(element) {
			this.Switches[element.id] = element;
			objList.push([element.name, element.id, element.description, element.type, "<span data-feather=\"settings\" onClick=\"N_1981_UI.SettingsHandler(" + element.id + "," + element.group + ");\"></span>"])

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

		html = this.ConfigHTML.split("[UUID]").join(id);
		instance.Create(html); // Passing content of modal window.
		this.Timer.Create("idTimer1981", "N_1981_UI.Timer"); // Passing id of a container & class path to timer object.

		this.Timer.Load(this.Key, id);

		console.log(Sensor);
		document.getElementById('idName_1981_Sensor').value 		= Sensor.name;
		document.getElementById("idNode1981Private").checked 		= ("true" == Sensor.is_private) ? true : false;
		document.getElementById("idNode1981LuminaceSensor").checked = ("true" == Sensor.is_triggered_by_luminance) ? true : false;
		document.getElementById("idNode1981MovementSensor").checked = ("true" == Sensor.is_triggered_by_movement) ? true : false;

		instance.Show();
	}

	this.UpdateSwitchInfo = function(id) {
		var name 					= document.getElementById("idName_1981_Sensor").value;
		var isPrivate 				= document.getElementById("idNode1981Private").checked;
		var isTriggeredByLuminance 	= document.getElementById("idNode1981LuminaceSensor").checked;
		var isTriggeredByMovement 	= document.getElementById("idNode1981MovementSensor").checked;

		var RequestData = {
			request: "update",
			json: `{ "name":"` + name + `",
					"is_private":"` + isPrivate + `",
					"is_triggered_by_luminance":"` + isTriggeredByLuminance + `",
					"is_triggered_by_movement":"` + isTriggeredByMovement + `"}`
		};

		$.ajax({
		    url: 'http://' + GlobalIpAddress + '/set/node_info/' + this.Key + "/" + id,
		    type: "POST",
		    dataType: "json",
		    data: RequestData,
			async: true,
		    success: function (data) {
		    }
		});
	}

	return this;
}

var N_1981_BLL 	= N_1981_Object_BLL("ykiveish");
var N_1981_UI 	= N_1981_Object_UI(N_1981_BLL);

N_1981_UI.Init();
N_1981_UI.Run();
