
var ApplicationCard = `
	<div class="card border-primary text-center" style="width: 6rem;">
		<div class="card-body">
			<img src="data:image/png;base64,[URL]" style="width:50px;height:50px;" onClick="GetApplication([ID]);">
		</div>
	</div>
`;

function Redirect(url) {
	console.log(url);
	window.location.href = url;
}

function GetApplication(id) {
	var instance = ModalBuilder.GetInstance();
	instance.Create("<iframe src='http://" + GlobalIpAddress + "/mobile?id=" + id + "' frameborder='0' style='position: relative; height: 600px; width: 100%;'></iframe>");
	// instance.RegisterCloseEvent(ExitShell);
	// instance.SetTitle("Node's Shell");
	instance.Show();

	// Redirect('http://' + GlobalIpAddress + '/mobile');
}

function GetApps() {
	$.ajax({
	    url: 'http://' + GlobalIpAddress + '/get/app_list/ykiveish',
	    type: "GET",
	    dataType: "json",
		async: true,
	    success: function (data) {
	    	//var size = data.apps.length / 20;
	    	var html = ""
	    	data.apps.forEach(function(element) {
	    		// html += "<div class=\"col-xs-" + size + "\">";
	    		card = ApplicationCard;
	    		card = card.split("[URL]").join(element.image);
	    		card = card.split("[ID]").join(element.id);
	    		html += card;
	    		//html += "</div>";
	    	});

	    	document.getElementById('idApplicationList').innerHTML = html;
	    }
	});
}

$(document).ready(function() {
	GlobalIpAddress = GlobalIP + ":" + GlobalPort;
	GetApps();
});