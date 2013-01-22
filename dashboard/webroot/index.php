<?php
$route = (empty($_GET['rt'])) ? '' : $_GET['rt'];
$page_body = 'index.php';
$is_fluid = '';

$output_type = 'page';

if (empty($route)) {
		$page_body = 'pages/clients.php';
		$is_fluid = '';

} else if (match_extension($route, '.json')) {
		$output_type = 'data';

} else {

	## get the parts of the route
	$parts = explode('/', $route);
	
	switch ($parts[0]) {
		
		case 'clients':
			$page_body = 'pages/clients.php';
			$is_fluid = '';
			print($parts[1]);
			break;
			
		default: 
			$page_body = 'pages/404.php';
			$is_fluid = '';
			break;
	}
	
	if(isset( $parts[1])) {
		#$this->action = $parts[1];
	}
}

##  This is where the page is generated (header - body - footer)

if ($output_type == 'page') {

	require('tpl/header.php');
	require($page_body);
	require('tpl/footer.php');

} else if ($output_type == 'data') {

	ask_server("clients\n");
}

## echo($route);
?>