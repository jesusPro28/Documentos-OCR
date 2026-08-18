<?php
/**
 * =====================================================================
 * VER DOCUMENTO (ver_documento.php)
 * Lee el archivo PDF/imagen almacenado como BLOB en MySQL y lo sirve
 * directamente al navegador para visualización inline (sin descarga).
 * Parámetros GET: id (int), tipo ("curp" | "acta")
 * =====================================================================
 */

require_once 'db.php';

$id   = isset($_GET['id'])   ? (int)$_GET['id']   : 0;
$tipo = isset($_GET['tipo']) && $_GET['tipo'] === 'acta' ? 'acta' : 'curp';

if ($id <= 0) {
    http_response_code(400);
    exit('ID inválido.');
}

try {
    $col_archivo = $tipo . '_archivo';
    $col_mime    = $tipo . '_mime';
    $col_nombre  = $tipo . '_nombre_archivo';

    $stmt = $pdo->prepare(
        "SELECT `{$col_archivo}`, `{$col_mime}`, `{$col_nombre}` FROM alumnos WHERE id = ?"
    );
    $stmt->execute([$id]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$row || empty($row[$col_archivo])) {
        http_response_code(404);
        exit('Archivo no encontrado en la base de datos.');
    }

    $mime   = $row[$col_mime]    ?: 'application/pdf';
    $nombre = $row[$col_nombre]  ?: 'documento.pdf';

    // Servir el archivo directamente — el navegador lo abre inline (no descarga)
    header("Content-Type: {$mime}");
    header("Content-Disposition: inline; filename=\"{$nombre}\"");
    header("Content-Length: " . strlen($row[$col_archivo]));
    header("Cache-Control: private, max-age=3600");

    echo $row[$col_archivo];

} catch (PDOException $e) {
    http_response_code(500);
    exit('Error al leer la base de datos.');
}
?>
