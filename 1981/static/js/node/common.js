var GlobalIpAddress = "0.0.0.0:0";

function Common () {
	this.GetNodeInfo = function(key, callback) {
		$.ajax({
		    url: 'http://' + GlobalIpAddress + '/get/node_info/' + key,
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

function Modal () {
	this.ModalID 		= "#idMakesenseModal";
	this.ModalIDContent = "idMakesenseModalContent";

	this.Create = function (content) {
		document.getElementById(this.ModalIDContent).innerHTML = content;
		$(this.ModalID).modal({
			keyboard: false,
			backdrop: "static"
		});
	}

	this.Show = function () {
		$(this.ModalID).modal('show');
	}

	this.Hide = function () {
		$(this.ModalID).modal('hide');
	}

	this.Remove = function () {
		$(this.ModalID).modal('dispose');
	}

	return this;
}

// ModalBuilder is a SingleTone class.
var ModalBuilder = (function () {
	var Instance;

	ModalHTML = `
		<div class="modal fade" id="idMakesenseModal" tabindex="-1" role="dialog" aria-labelledby="exampleModalCenterTitle" aria-hidden="true">
			<div class="modal-dialog modal-dialog-centered" role="document">
				<div class="modal-content">
					<div class="modal-header">
						<h5 class="modal-title" id="exampleModalCenterTitle">Information</h5>
						<button type="button" class="close" data-dismiss="modal" aria-label="Close">
							<span aria-hidden="true">&times;</span>
						</button>
					</div>
					<div class="modal-body" id="idMakesenseModalContent"></div>
					<div id="idMakeSenseModalFooter"></div>
				</div>
			</div>
		</div>
	`;

	ModalFooterHTML = `
		<div class="modal-footer">
			<button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
			<button type="button" class="btn btn-primary">Save changes</button>
		</div>
	`;

	function CreateInstance () {
		document.getElementById('idModalSection').innerHTML = ModalHTML;
		var obj = new Modal();
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
