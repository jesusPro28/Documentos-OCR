<?php
/**
 * =====================================================================
 * CONFIGURACIÓN DE CONEXIÓN A BASE DE DATOS (db.php)
 * Conexión mediante PDO segura para MySQL en Hostinger
 * =====================================================================
 */

// Credenciales por defecto de XAMPP local
$host = "localhost"; 
$dbname = "validacion_documental";
$username = "root";
$password = "";

try {
    // Establecemos conexión con codificación UTF-8 para soporte de eñes y acentos
    $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
} catch (PDOException $e) {
    // Retornamos el error en formato JSON por si falla desde el frontend
    header('Content-Type: application/json');
    echo json_encode(["error" => "Fallo de conexión: " . $e->getMessage()]);
    exit;
}
?>
