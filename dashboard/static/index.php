<?php
$route = (empty($_GET['rt'])) ? '' : $_GET['rt'];
$page_body = 'index.php';
$current_page = '';

$output_type = 'page';

if (empty($route)) {
		$page_body = 'pages/clients.php';
		$current_page = 'overview';

} else if (match_extension($route, '.json')) {
		$output_type = 'data';

} else {

	## get the parts of the route
	$parts = explode('/', $route);
	
	switch ($parts[0]) {
		
		case 'clients':
			$page_body = 'pages/clients.php';
			$current_page = 'clients';
			print($parts[1]);
			break;

		case 'jobs':
			$page_body = 'pages/jobs.php';
			$current_page = 'jobs';
			print($parts[1]);
			break;

		case 'shots':
			$page_body = 'pages/shots.php';
			$current_page = 'shots';
			print($parts[1]);
			break;
		
		case 'sequences':
			$page_body = 'pages/sequences.php';
			$current_page = 'sequences';
			print($parts[1]);
			break;	

		case 'projects':
			$page_body = 'pages/projects.php';
			$current_page = 'projects';
			print($parts[1]);
			break;	

		default: 
			$page_body = 'pages/404.php';
			$current_page = '';
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
	#require('pages/json_io.php');

	$item = $_GET["item"];
	$action = $_GET["action"];
	if (isset($_GET["filters"])) {
		$filters = $_GET["filters"];
	} else {
		$filters = '""';
	}
	if (isset($_GET["values"])) {
		$values = $_GET["values"];
	} else {
		$values = '""';
	}

	//echo $item . $action . $filters;
	//echo('{"item": "' . $item . '", "action": "' . $action . '", "filters": "' . $filters . '", "values":"' . $values . '"}');

	$json_string = stripslashes('{"item": "' . $item . '", "action": "' . $action . '", "filters": ' . $filters . ', "values":' . $values . '}');

	//echo $json_string;
	ask_server($json_string);


	//echo ('{"item":"client","action":"read","actions":"{""}","filters":""}');
}

## echo($route);
?>