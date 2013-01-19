<?php
$site_path = realpath(dirname(__FILE__));
define ('__SITE_PATH', $site_path);
 

define ('__WWW_PATH', ''); //leave empty if website sits on root
define ('__WEB_ROOT', __WWW_PATH . '/webroot');

if (!defined('JS')) {
		define('JS', __WEB_ROOT . '/js');
}

if (!defined('CSS')) {
		define('CSS', __WEB_ROOT . '/css');
}

if (!defined('ICO')) {
		define('ICO', __WEB_ROOT . '/ico');
}

if (!defined('IMG')) {
		define('IMG', __WEB_ROOT . '/img');
}

require('config.php');
require('lib/functions.php');
require('webroot/index.php');
?>