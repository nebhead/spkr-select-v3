// This script updates the status of the buttons on page load and every 1 second
var lastdata = [];  // Save state and only update if the data has changed 

function updatePage(data) {
	for(var index=0; index < data.length; index++){
		var object = data[index];
		
		var keyname = object['keyname'];
		var btnid = 'btn_' + keyname;
		//var cardid = 'card_' + keyname;
		var iconid = 'icon_' + keyname;
		var textid = 'text_' + keyname;

		if (keyname == 'spkr_pro') {
			if (object['state'] == 'on') {
				$('#protection').show();
			} else {
				$('#protection').hide();
			};
		} else {
			if (object['state'] == 'on') {
				document.getElementById(btnid).className = "btn btn-info btn-block shadow";
				//document.getElementById(cardid).className = "card bg-primary shadow mx-auto";
				document.getElementById(iconid).innerHTML = "<i class=\"fas fa-volume-up\"></i>";
				document.getElementById(textid).innerHTML = "ON";
			} else {
				document.getElementById(btnid).className = "btn btn-secondary btn-block shadow";
				//document.getElementById(cardid).className = "card bg-secondary shadow mx-auto";
				document.getElementById(iconid).innerHTML = "<i class=\"fas fa-volume-mute\"></i>";
				document.getElementById(textid).innerHTML = "OFF";
			};
		}

	};
};

function setupListeners(data) {
	for(var index=0; index < data.length; index++){
		(function (){

			var object = data[index];
			var keyname = object['keyname'];
			var btnid = 'btn_' + keyname;
			if (keyname != 'spkr_pro') {
				document.getElementById(btnid).addEventListener("click", function() {
					req = $.ajax({
						url : '/button',
						type : 'POST',
						data : { 'keyname' : keyname }
					});
					
					req.done(function(data) {
						if (data.result == 'success') {
							doUpdate();
						} else {
							alert('Error sending button press.');
						};
					});
				});
			};
		}()); // Required or else the listerners won't get created properly
	};
};

function doUpdate() {
	req = $.ajax({
		url : '/states',
		type : 'GET'
	});
	req.done(function(data) {
		// Setup Initial Dash Data
		var diff = 0;
		//console.log('lastdata: ' + lastdata);
		
		if (lastdata == '') {
			lastdata = data;
			updatePage(data);
			//console.log('Did an update.')
		};

		for(var index=0; index < data.length; index++){
			var lastobj = lastdata[index];
			var newobj = data[index];
			//console.log('lastobj: ' + lastobj);
			//console.log('newobj: ' + newobj);
			if(lastobj.state != newobj.state) {
				diff += 1;
				//console.log(lastdata[index]['name']+' is different')
			};
		};

		if(diff > 0) {
			lastdata = data;
			updatePage(data);
			//console.log('Did an update.')
		};
	});
};

// Update page data
$(document).ready(function(){
	// Get Intial Dash Data
    req = $.ajax({
		url : '/states',
		type : 'GET'
    });
    req.done(function(data) {
        // Setup Initial Dash Data
		updatePage(data);
		setupListeners(data);
	});

	document.getElementById('all_on').addEventListener("click", function() {
		req = $.ajax({
			url : '/button',
			type : 'POST',
			data : { 'all_on' : 'true' }
		});
		
		req.done(function(data) {
			if (data.result == 'success') {
				doUpdate();
			} else {
				alert('Error sending button press.');
			};
		});
	});

	document.getElementById('defaults').addEventListener("click", function() {
		req = $.ajax({
			url : '/button',
			type : 'POST',
			data : { 'defaults' : 'true' }
		});
		
		req.done(function(data) {
			if (data.result == 'success') {
				doUpdate();
			} else {
				alert('Error sending button press.');
			};
		});
	});


	setInterval(function(){
		doUpdate();
	}, 1000);
}); // End of Document Ready Function

