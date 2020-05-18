
var ApplicationCard = `
	<div class="card border-primary text-center" style="width: 96px;">
		<div class="card-body">
			<img src="data:image/png;base64,[URL]" style="width:50px;height:50px;" onClick="GetApplication([ID]);">
		</div>
	</div>
`;

function Redirect(url) {
	window.location.href = url;
}

function GetApplication(id) {
	Redirect('http://' + GlobalIpAddress + '/mobile?id=' + id);
}

function GetApps() {
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/app_list/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	var width = $(window).width();
	    	var itemsCounter = 1;
	    	var itemsInWidth = width / 96;
	    	var translationTable = [0,0,2,3,4,4,5,5,6,7,8,8,8,9,9,10,11,12,12,13,14];
	    	var itemsInRow = translationTable[itemsInWidth];
	    	var html = "<table><tr>"
	    	data.apps.forEach(function(element) {
	    		if (itemsCounter > itemsInRow) {
	    			html += "</tr><tr>"
	    			itemsCounter = 1;
	    		}

	    		card = ApplicationCard;
	    		card = card.split("[URL]").join(element.image);
	    		card = card.split("[ID]").join(element.id);
	    		html += "<td>" + card + "</td>";
	    		itemsCounter++;
	    	});
	    	html += "</tr></table>"

	    	document.getElementById('idMkSApplications').innerHTML = html;
	    }
	});
}

$(document).ready(function() {
	GlobalIpAddress = GlobalIP + ":" + GlobalPort;
	GetApps();
});