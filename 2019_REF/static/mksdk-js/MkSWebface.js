function MkSWebface () {
	self = this;
	
	this.RestAPIPort 		= 8080;
	this.RestAPIUrl 		= "http://" + MkSGlobal.MakeSenseDomain;
	this.RestAPIFullUrl 	= this.RestAPIUrl.concat(":", this.RestAPIPort);
	this.WSState 			= "DISCONN";
	
	return this;
}

MkSWebface.prototype.Login = function (usr, pwd, callback) {
	var RequestData = {
		request: "login",
		data: {
			user: usr,
			pwd:  pwd
		}
	};
	MkSGlobal.AjaxPostRequest(this.RestAPIFullUrl, "/api/login", "json", RequestData, function(response) {
		callback(response);
	});
}

MkSWebface.prototype.GetUserNodeList = function (callback) {
	var RequestData = {
		request: "get_user_node_list",
		data: {
			key: MkSGlobal.UserDEVKey,
			user_id: MkSGlobal.UserId
		}
	};
	console.log(RequestData);
	MkSGlobal.AjaxPostRequest(this.RestAPIFullUrl, "/api/get/nodes", "json", RequestData, function(response) {
		callback(response);
	});
}

var MkSWebfaceBuilder = (function () {
	var Instance;

	function CreateInstance () {
		var obj = new MkSWebface();
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
