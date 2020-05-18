function getParameterByName(name, url) {
    if (!url) url = window.location.href;
    name = name.replace(/[\[\]]/g, '\\$&');
    var regex = new RegExp('[?&]' + name + '(=([^&#]*)|&|#|$)'),
        results = regex.exec(url);
    if (!results) return null;
    if (!results[2]) return '';
    return decodeURIComponent(results[2].replace(/\+/g, ' '));
}

$(document).ready(function() {
	GlobalIpAddress = GlobalIP + ":" + GlobalPort;
	var appId = getParameterByName('id');

	var RequestData = {
		request: "get_app_html",
		json: `{ "id":"` + appId + `"}`
	};

	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/app_html/ykiveish',
	    type: "POST",
	    dataType: "html",
	    data: RequestData,
		async: true,
	    success: function (html) {
	    	// Prepare your page structure
	    	var newPage = $(html);
	    	// Append the new page into pageContainer
	    	newPage.appendTo($.mobile.pageContainer);
	    	// Move to this page by ID '#main' (Each app must have id="main")
	    	$.mobile.changePage('#main');

	    	$.ajax({
		        url: 'http://' + GlobalIpAddress + '/get/app_js/ykiveish',
				type: "POST",
		        dataType: "script",
		        data: RequestData,
		        async: true,
		        success: function (js) {
		        	console.log("JS Loaded");
		        }
		    });
	    }
	});
});