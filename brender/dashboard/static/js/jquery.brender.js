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
