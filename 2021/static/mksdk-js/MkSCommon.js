function MkSCommon () {
	self = this;
	
	this.MakeSenseDomain = "127.0.0.1";
	this.MakeSenseServerUrl = "http://" + this.MakeSenseDomain + ":8080/";
  	
  	this.UserDEVKey = "ac6de837-7863-72a9-c789-a0aae7e9d93e" || localStorage.getItem("key");
  	this.UserId = 1 || localStorage.getItem("userId");
	
	return this;
}

MkSCommon.prototype.AjaxPostRequest = function (url, request, data_type, data, callback) {
	console.log("MkSCommon", url, request, data_type, data);
	$.ajax({
		url: url + request,
		type: "POST",
		dataType: data_type,
		data: data,
		async: true,
		success: function (response) {
			callback(response);
		},
		error: function(xhr, error){
			console.log("Ajax error");
			callback({
				error:"connection error",
				data: ""
			});
		}
	});
}

MkSCommon.prototype.AjaxGetRequest = function (url, callback) {
	console.log("MkSCommon AjaxGetRequest", url);
	$.ajax({
		url: url,
		type: "GET",
		async: true,
		success: function (response) {
			callback(response);
		},
		error: function(xhr, error){
			console.log("Ajax error");
			callback({
				error:"connection error",
				data: ""
			});
		}
	});
}

MkSCommon.prototype.StoryUserKeyLocalStorage = function (key, id) {
	localStorage.setItem("key", key);
	localStorage.setItem("userId", id);
}

MkSCommon.prototype.CheckUserLocalStorage = function () {
	var uuid = localStorage.getItem("key");
	if (uuid == null) {
		return false;
	} else {
		return true;
	}
}

var MkSCommonBuilder = (function () {
	var Instance;

	function CreateInstance () {
		var obj = new MkSCommon();
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

var MkSGlobal = MkSCommonBuilder.GetInstance();
console.log("MkSCommon", MkSGlobal.MakeSenseDomain);

/*var MakeSenseServerUrl 	= "http://ec2-18-236-253-240.us-west-2.compute.amazonaws.com:8080/";
var MakeSenseDomain 	= "ec2-18-236-253-240.us-west-2.compute.amazonaws.com";
var UserDEVKey 			= localStorage.getItem("key");

function LogoutHandler() {
	$("#logout").click(function() {
		localStorage.removeItem("key");
		window.location.href = "../index.html";
	});
}

function GetServerUrl() {
	return MakeSenseServerUrl;
}

function GetUserKey() {
	return UserDEVKey;
}

function MkSGetUrlParameter(name) {
    name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
    var regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
    var results = regex.exec(location.search);
    return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
};*/
