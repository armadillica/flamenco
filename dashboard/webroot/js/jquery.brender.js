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

	$('#clients').dataTable({
		"bProcessing": true,
		"iDisplayLength": 25,
		//"sAjaxSource": '/json_source_2.txt'
		"sAjaxSource": '/clients/list.json',
		"fnRowCallback": function( nRow, aData, iDisplayIndex, iDisplayIndexFull ) {
			if (aData[1] == "enabled"){
				$('td:eq(1)', nRow).html('<span class="btn btn-mini btn-success">enabled</span>');
			}
			if (aData[2] == "offline"){
				$('td:eq(2)', nRow).html('<span class="label label-important">offline</apn>');
			} else if (aData[2] == "online"){
				$('td:eq(2)', nRow).html('<span class="label label-success">online</apn>');
			}
    	}
	});

});
