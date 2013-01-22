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

	$('#clients').dataTable( {
		"bProcessing": true,
		"iDisplayLength": 25,
		"sAjaxSource": '/clients/list.json'
	} );

});