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
		    url: 'http://' + GlobalIpAddress + '/set/node_sensor_info/' + this.Key+ '/' + item.id + '/' + item.value,
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

function N_1981_Object_UI (bll) {
	this.BLL 			= bll;
	this.SwitchesState 	= {};
	this.Defines 		= {
								ROWSIZE: 		12,
								NOGROUP: 		255,
								ON: 			1,
								OFF: 			0,
								DIRECTION_UP: 	1,
								DIRECTION_DOWN: 2,
	};

	this.HtmlSingleSwitch = `
		<div class="card border-primary text-center" style="width: 10rem;">
			<div class="card-header">[NAME]</div>
			<div class="card-body">
				<a href="#" class="btn btn-primary btn-block" id="N_1981_Switch_[ID]" onClick="N_1981_UI.SwitchClickHandler([ID]);">[STATE]</a>
			</div>
		</div>
	`;

	this.HtmlDualSwitch = `
		<div class="card border-primary text-center" style="width: 10rem;">
		<div class="card-header">[NAME]</div>
			<div class="card-body">
				<a href="#" class="btn btn-primary btn-block" id="N_1981_Switch_[ID_UP]" onClick="N_1981_UI.SwitchClickHandler([ID_UP]);">Up</a>
				<a href="#" class="btn btn-primary btn-block" id="N_1981_Switch_[ID_DOWN]" onClick="N_1981_UI.SwitchClickHandler([ID_DOWN]);">Down</a>
			</div>
		</div>
	`;

	this.Init = function() {
		this.BLL.GetNodeInformation(function(data) {
			this.GetNodeInfoHandler(data);
		});
	}

	this.Run = function () {

	}

	this.ConvertPreDefines = function(html, sensor) {
		html = html.split("[ID]").join(sensor.id);
		html = html.split("[NAME]").join(sensor.name);
		html = html.split("[DESCRIPTION]").join("Switch On/Off");

		if (this.Defines.OFF == sensor.value) {
			html = html.split("[STATE]").join("OFF");
		} else {
			html = html.split("[STATE]").join("ON");
		}

		if (this.Defines.DIRECTION_UP == sensor.direction) {
			html = html.split("[ID_UP]").join(sensor.id);
		} else {
			html = html.split("[ID_DOWN]").join(sensor.id);
		}

		return html;
	}

	this.GetNodeInfoHandler = function(data) {
		if (data === null)
			return;

		if (data.sensors === null)
			return;

		groups 	= {};
		size 	= data.sensors_count / this.Defines.ROWSIZE;
		html = "<div class=\"card-columns\">";

		data.sensors.forEach(function(element) {
			html += "<div class=\"col-xs-" + size + "\">";

			if (element.group == this.Defines.NOGROUP) {
				single = this.HtmlSingleSwitch;
				html += this.ConvertPreDefines(single, element);
			} else {
				if (!(element.group in groups)) {
					dual = this.HtmlDualSwitch;
					groups[element.group] = {
												html: this.ConvertPreDefines(dual, element),
												items: [element.id]
											};
				} else {
					item = groups[element.group];
					item.items.push(element.id);
					item.html = this.ConvertPreDefines(item.html, element);
					groups[element.group] = item;
				}
			}

			html += "</div>";

			itemsInGroup = null;
			if (groups[element.group] !== undefined) {
				itemsInGroup = groups[element.group].items;
			}

			this.SwitchesState[element.id] = { 	
												id: element.id,
												value: element.value, 
												group: element.group, 
												direction: element.direction,
												items: itemsInGroup
											 };
		});

		// Add all dual switches to UI.
		for (var index in groups) {
			element = groups[index];
			html += "<div class=\"col-xs-" + size + "\">";
			html += element.html;
			html += "</div>";
		}

		// Close row.
		html += "</div>";
		// Update UI.
		document.getElementById('idWidget').innerHTML = html;
	}

	this.SwitchClickHandler = function (id) {
		item = this.SwitchesState[id];
		item.value = this.Defines.ON - item.value;

		this.BLL.TriggerSwitch(item, function(data) {
		});

		if (this.Defines.NOGROUP == item.group) {
			if 	(this.Defines.OFF == item.value) {
				document.getElementById('N_1981_Switch_' + id).innerHTML = "OFF";
			} else {
				document.getElementById('N_1981_Switch_' + id).innerHTML = "ON";
			}
		} else {
			item.items.forEach(function(element) {
				if (id != element && this.Defines.ON == item.value) {
					secondSwitch = this.SwitchesState[element];
					secondSwitch.value = this.Defines.ON - item.value;
					this.SwitchesState[id] = secondSwitch;
				}
			});
		}
		
		this.SwitchesState[id] = item;
	}

	return this;
}

var N_1981_BLL 	= N_1981_Object_BLL("ykiveish");
var N_1981_UI 	= N_1981_Object_UI(N_1981_BLL);

N_1981_UI.Init();
N_1981_UI.Run();
