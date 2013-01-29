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

	var clientsTable = $('#clients').dataTable({
		"bProcessing": true,
		"iDisplayLength": 25,
		//"sAjaxSource": '/json_source_2.txt'
		"sAjaxSource": '/data.json',
		"fnServerParams": function (aoData) {
      		aoData.push( 
      			{"name": "item", "value": "client"}, 
      			{"name": "action", "value": "read"});
      	},
		"fnRowCallback": function( nRow, aData, iDisplayIndex, iDisplayIndexFull ) {
			if (aData[1] == "enabled"){
				$('td:eq(1)', nRow).html('<span class="status-toggle btn btn-mini btn-success">enabled</span>');
			} else if (aData[1] == "disabled"){
				$('td:eq(1)', nRow).html('<span class="status-toggle btn btn-mini btn-warning">disabled</span>');
			}
			if (aData[2] == "offline"){
				$('td:eq(2)', nRow).html('<span class="label label-important">offline</apn>');
			} else if (aData[2] == "online"){
				$('td:eq(2)', nRow).html('<span class="label label-success">online</apn>');
			}
    	}
	});

	$(".status-toggle").on("click",function() {

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

});
