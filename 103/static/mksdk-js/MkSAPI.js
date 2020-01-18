function MkSAPI (key) {
	self = this;
	
	this.Key		= key;
	this.Gateway 	= null;
	this.Webface 	= MkSWebfaceBuilder.GetInstance();
	this.Database 	= null;
	
	return this;
}

MkSAPI.prototype.SetUserKey = function (key) {
	this.Key = key;
}

MkSAPI.prototype.ConnectGateway = function (callback) {
	this.Gateway = MkSGatewayBuilder.GetInstance(this.Key);
	if (!this.Gateway.IsConnected()) {
		this.Gateway.Connect(callback);
	} else {
		callback();
	}
}

MkSAPI.prototype.GetNodeInfo = function (uuid, callback) {
	this.Gateway.Send("DIRECT", uuid, "get_node_info", "", "", callback);
}

MkSAPI.prototype.GetNodeSensorsInfo = function (uuid, callback) {
	this.Gateway.Send("DIRECT", uuid, "get_sensor_info", "", "", callback);
}

MkSAPI.prototype.SetNodeSensorsInfo = function (uuid, sensors, callback) {
	this.Gateway.Send("DIRECT", uuid, "set_sensor_info", sensors, "", callback);
}

MkSAPI.prototype.GetFileContent = function (uuid, payload, callback) {
	this.Gateway.Send("DIRECT", uuid, "get_file", payload, "", callback);
}

MkSAPI.prototype.UploadFileContent = function (uuid, payload, callback) {
	this.Gateway.Send("DIRECT", uuid, "upload_file", payload, "", callback);
}

MkSAPI.prototype.SendCustomCommand = function (uuid, command, payload, callback) {
	this.Gateway.Send("DIRECT", uuid, command, payload, "", callback);
}

MkSAPI.prototype.RegisterOnNodeChange = function (uuid, callback) {
	this.Gateway.Send("DIRECT", uuid, "register_on_node_change", {"item_type":2}, "", callback);
}

MkSAPI.prototype.SetGlobalGatewayIP = function (ip) {
	MkSGlobal.MakeSenseDomain = ip;
}

var MkSAPIBuilder = (function () {
	var Instance;

	function CreateInstance () {
		if (MkSGlobal.CheckUserLocalStorage) {
			return new MkSAPI(MkSGlobal.UserDEVKey);
		} else {
			return null;
		}
	}

	return {
		GetInstance: function () {
			if (!Instance) {
				console.log("Create API instance");
				Instance = CreateInstance();
			}

			console.log("Return API instance");
			return Instance;
		}
	};
})();
