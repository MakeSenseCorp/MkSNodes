console.log("Hello from Node config");

function Utils() {
	this.SetCheckboxState = function(id, val) {
		elem = document.getElementById(id);
		if (elem === null) {
			return;
		}

		if (val == 1) {
			elem.checked = true;
		} else if (val == 0) {
			elem.checked = false;
		}
	}
	
	return this;
}

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
				</div>
				<div class="row">
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

		this.Days[1] = ["idMakeSenseTimerDay_1", 0, "SUN"];
		this.Days[2] = ["idMakeSenseTimerDay_2", 0, "MON"];
		this.Days[3] = ["idMakeSenseTimerDay_3", 0, "TUE"];
		this.Days[4] = ["idMakeSenseTimerDay_4", 0, "WED"];
		this.Days[5] = ["idMakeSenseTimerDay_5", 0, "THU"];
		this.Days[6] = ["idMakeSenseTimerDay_6", 0, "FRI"];
		this.Days[7] = ["idMakeSenseTimerDay_7", 0, "SAT"];
		this.Days[8] = ["idMakeSenseTimerAllDays", 0];

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
	}

	// Load status of days.
	this.Load = function(id) {
		self = this;
		this.UUID 	= id;

		api.SendCustomCommand(NodeUUID, "get_timer", {
			id: id
		}, function(res) {
			var payload = res.data.payload;
			console.log("TIMERS", payload);

			if (payload.timers !== undefined) {
				var objList = [];
				for (i = 0; i < payload.timers.length; i++) {
					var enabled = "Enabled";
					if ("0" == payload.timers[i].enabled) {
						enabled = "Disabled";
					}

					if ("All" == payload.timers[i].days) {
						days = "All";
					} else {
						days = payload.timers[i].days.join("<br>");
					}

					objList.push([payload.timers[i].start, days, payload.timers[i].action, enabled,"<span data-feather=\"delete\" onClick=\"" + self.ClassName + ".RemoveTimer(this, " + payload.timers[i].id + ");\"></span>"]);
					if (self.LastId < payload.timers[i].id) {
						self.LastId = payload.timers[i].id;
					}
				}

				self.TimerTable.CreateHead(["Start","Days","Action","Status",""]);
				self.TimerTable.CreateBody(objList);
				html = self.TimerTable.CreateTable();
				document.getElementById(self.ClassName + "_table").innerHTML = html;
				feather.replace();

				self.SetActions(payload.actions);
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
		var SelectedDays  		= [];
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
			for (i = 1; i < 8; i++) {
				SelectedDays.push(this.Days[i][2]);
			}
		} else {
			for (i = 1; i < 8; i++) {
				if (1 == this.Days[i][1]) {
					SelectedDaysHtml += this.Days[i][2] + "<br>";
					SelectedDays.push(this.Days[i][2]);
				}
			}

			if ("" == SelectedDaysHtml) {
				return;
			}
		}

		this.TimerTable.UpdateTable([[SelectedStart, SelectedDaysHtml, SelectedAction, "Enabled", "<span data-feather=\"delete\" onClick=\"" + this.ClassName + ".RemoveTimer(this, " + this.LastId + ");\"></span>"]]);
		feather.replace();

		this.LastId += 1;
		api.SendCustomCommand(NodeUUID, "append_timer", {
			addr: this.UUID,
			timer: {
				id: this.LastId,
				start: SelectedStart,
				days: SelectedDays,
				action: SelectedAction,
				enabled: 1
			}
		}, function(res) {
			console.log("APPEND TIMER");
		});
	}

	this.RemoveTimer = function(self, id) {
		var element = self.parentNode.parentNode; // TR
		element.parentNode.removeChild(element);
		api.SendCustomCommand(NodeUUID, "remove_timer", {
			addr: this.UUID,
			id: this.LastId
		}, function(res) {
			console.log("REMOVE TIMER");
		});
	}

	return this;
}

var UploadModalContent = `
	<div class="row">
		<div class="col-lg-12">
			<div class="card">
				<div class="card-body">
					<form>
						<div class="form-group">
							<label for="id_package_path">Please select package (MP3 File)</label>
							<input type="file" class="form-control-file" id="id_package_path">
						</div>
					</form>
					<button type="button" id="id_install_button" class="btn btn-primary" onclick="OnInstallClick();">Upload</button>
				</div>
			</div>
		</div>
	</div>
	<div class="row d-none" id="id_progress">
		<div class="col-lg-12">
			<div class="card">
				<div class="card-body">
					<div class="progress">
						<div id="id_progress_bar" class="progress-bar progress-bar-striped" style="min-width: 20px;"></div>
					</div>
					<div>
						<span class="text-muted" id="id_progress_item">0%</span>
					</div>
				</div>
			</div>
		</div>
	</div>
`;

var UploadModalFooter = `
	<h6 class="d-flex justify-content-between align-items-center mb-3">
		<span class="text-muted"><a href="#" onclick="$('#id-gen-modal').modal('hide');">Close</a></span>
	</h6>
`;

var OpenModal = function (action) {
	switch(action) {
		case "upload":
			document.getElementById("id-gen-modalLabel").innerHTML	= "Upload Song";
			document.getElementById("id_modal_content").innerHTML	= UploadModalContent;
			document.getElementById("id_modal_footer").innerHTML	= UploadModalFooter;
			break;
		default:
			break;
	}
	
	$('#id-gen-modal').modal('show');
}

var fileName = "";
var fileSize = 0;
var reader = new FileReader();
reader.onload = function(e) {
	var data    		= reader.result;
	var MAX_CHUNK_SIZE  = 4096;
	var buffer  		= new Uint8Array(data);
	var chunks  		= parseInt(fileSize / MAX_CHUNK_SIZE);

	// console.log(buffer, fileSize / MAX_CHUNK_SIZE, chunks);
	if (fileSize % MAX_CHUNK_SIZE != 0) {
		// Append last chunk.
		chunks++;
	}

	start = 0;
	end   = 0;
	percCunck = parseInt(100 / chunks);
	for (i = 0; i < chunks; i++) {
		if ( (fileSize - i * MAX_CHUNK_SIZE) < MAX_CHUNK_SIZE ) {
			// We are at last packet
			start = i * MAX_CHUNK_SIZE;
			end   = fileSize;
		} else {
			start = i * MAX_CHUNK_SIZE;
			end   = start + MAX_CHUNK_SIZE;
		}

		if (start < end) {
			var arrayData = buffer.subarray(start, end);

			var dataToSend = [];
			for (idx = 0; idx < arrayData.length; idx++) {
				dataToSend.push(arrayData[idx]);
			}

			// console.log("send chunk", i+1, start, end, fileSize, dataToSend.length);
			var payload = {
				upload: {
					action: "upload",
					file: fileName,
					size: fileSize,
					content: dataToSend,
					chunk: i+1,
					chunk_size: (end - start),
					chunks: chunks
				}
			}
			// console.log(payload);
			node.API.UploadFileContent(NodeUUID, payload, function(res) {
				if (res) {
					status = res.data.payload.status;
					if (status == "accept") {
						console.log("Uploaded " + res.data.payload.chunk + " " + percCunck * res.data.payload.chunk);
					}
				}
			});
		}
	}
}

var ReadImage = function(file) {
	// Check if the file is zip file.
	if (file.type && file.type.indexOf('audio/mpeg') === -1) {
		console.log('File is not an image.', file.type, file);
		return;
	}

	console.log("READ FILE");

	fileName = file.name;
	fileSize = file.size;
	reader.readAsArrayBuffer(file);
}

var OnInstallClick = function() {
	var fileObj = document.getElementById("id_package_path");
	// Show progress bar
	document.getElementById("id_progress").classList.remove("d-none");
	ReadImage(fileObj.files[0]);
}
