var objTerminal = document.getElementById('idTerminalCommandScreen');
var objInput 	= document.getElementById('idTerminalCommand');

function SendTerminalCommand() {
	cmd = objInput.value;

	var RequestData = {
		request: "get_node_shell_cmd",
		json: `{ "cmd":"` + cmd + `"}`
	};

	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/node_shell_cmd/ykiveish',
	    type: "POST",
	    dataType: "json",
	    data: RequestData,
		async: true,
	    success: function (data) {
	    	console.log(data.shell);
	    	if (data.shell != null) {
	    		objTerminal.value += "> " + objInput.value + "\n";
				data.shell.forEach(function(item) {
					objTerminal.value += item + "\n";
				});
				objTerminal.scrollTop = objTerminal.scrollHeight;
				objInput.value = "";
	    	}
	    }
	});
}

function TerminalKeyPress(e) {
	if (e.keyCode == 13) {
		cmd = objInput.value;
		if (cmd == "") {
			// Check if input is empty
			objTerminal.value += "> \n";
			objTerminal.scrollTop = objTerminal.scrollHeight;
		} else {
			SendTerminalCommand();
		}
		
		return false;
	}
}

var GetMachineInfoInterval = 0;

function GetMachineInfo () {
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/node_config_info/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	if (data != null) {
	    		document.getElementById("idCpuArchitecture").innerHTML 	= data.cpu.arch;
	    		document.getElementById("idHddRatio").innerHTML 		= data.hdd.capacity_ratio;
	    		document.getElementById("idRamRatio").innerHTML 		= data.ram.capacity_ratio;
	    		document.getElementById("idCpuTemperature").innerHTML 	= (data.sensors.temp / 1000) + "C";
	    		document.getElementById("idCpuFrequency").innerHTML 	= data.sensors.freq;
	    		document.getElementById("idMachineIp").innerHTML 		= data.network.ip;
	    	}
	    }
	});
}

$(document).ready(function() {
	GlobalIpAddress = GlobalIP + ":" + GlobalPort;
	objTerminal.value = "";

	GetMachineInfo();
	GetMachineInfoInterval = setInterval(GetMachineInfo, 5000);
});