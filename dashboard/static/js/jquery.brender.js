$(document).ready(function() {      
	$(window).scroll(function() {
	    var topOfWindow = $(window).scrollTop();
	    if (10 < topOfWindow) {
	        $(".navbar").addClass("shadow");          
	    }
	    else {
	        $(".navbar").removeClass("shadow");
	    }
	});
	
	$.ajaxSetup ({
		cache: false
	});	

	

	$(document).on("click", ".status-toggle", function() {
		var status = $(this).html();
		var tableRow = $(this).parents("tr");
		var rowPosition = clientsTable.fnGetPosition(tableRow[0]);
		var clientId = tableRow.attr("id").split("_")[1];

		if (status == 'enabled') {
			clientsTable.fnUpdate('disabled', rowPosition ,1);
			query = 'item=client&action=update&filters={"id":' + clientId +'}&values={"status":"disabled"}' ;
			$.getJSON('ajax/test.json', query, function() {
				console.log('Client is now disabled');
			});
		} else if (status == 'disabled') {
			clientsTable.fnUpdate('enabled', rowPosition ,1);
			query = 'item=client&action=update&filters={"id":' + clientId +'}&values={"status":"enabled"}' ;
			$.getJSON('ajax/test.json', query, function() {
				console.log('Client is now enabled');
			});
		}
	});

	$('#clients-disable-all').on("click",function() {
		$.ajax({
			url: "/data.json",
			data: {
				item: "client", 
				action: "update", 
				values: '{"status": "disabled"}'
			}
		}).done(function() {
			location.reload();
			/*
			if ($('.status-toggle').hasClass('btn-success')) {
				$('.status-toggle').removeClass('btn-success').addClass('btn-warning');
			}
			clientsTable.fnUpdate('Example update',0 ,0);
			*/
		});
	});

	$('#clients-enable-all').on("click",function() {
		$.ajax({
			url: "/data.json",
			data: {
				item: "client", 
				action: "update", 
				filters: '{"status": "disabled"}',
				values: '{"status": "enabled"}'
			}
		}).done(function() {
			location.reload();
			/*
			if ($('.status-toggle').hasClass('btn-warning')) {
				$('.status-toggle').removeClass('btn-warning').addClass('btn-success');
			}
			*/
		});
	});


	var shotsTable = $('#shots').dataTable({
		"bProcessing": true,
		"iDisplayLength": 25,
		"sAjaxSource": '/data.json',
		"fnServerParams": function (aoData) {
			aoData.push( 
				{"name": "item", "value": "shot"}, 
				{"name": "action", "value": "read"});
		}
	});

	var jobsTable = $('#jobs').dataTable({
		"bProcessing": true,
		"iDisplayLength": 25,
		"sAjaxSource": '/data.json',
		"fnServerParams": function (aoData) {
			aoData.push( 
				{"name": "item", "value": "job"}, 
				{"name": "action", "value": "read"});
		}
	});



});
