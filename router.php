<?php
$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

// Handle API requests
if (strpos($uri, '/api/') === 0) {
    $path = substr($uri, 5);
    $file = __DIR__ . '/api/' . $path . '.php';
    if (file_exists($file)) {
        require $file;
        exit;
    }
}

// Emulate Vercel rewrite: /path -> /dashboard/path
if (strpos($uri, '/dashboard/') !== 0) {
    $dashboardFile = __DIR__ . '/dashboard' . $uri;

    // If it's a directory, look for index.html
    if (is_dir($dashboardFile)) {
        $dashboardFile = rtrim($dashboardFile, '/') . '/index.html';
    }

    if (file_exists($dashboardFile)) {
        // Determine Content-Type
        $ext = pathinfo($dashboardFile, PATHINFO_EXTENSION);
        $mimes = [
            'html' => 'text/html',
            'js'   => 'application/javascript',
            'css'  => 'text/css',
            'png'  => 'image/png',
            'jpg'  => 'image/jpeg',
            'ico'  => 'image/x-icon'
        ];
        if (isset($mimes[$ext])) {
            header("Content-Type: " . $mimes[$ext]);
        }
        readfile($dashboardFile);
        exit;
    }
}

return false; // serve requested resource as-is
?>
