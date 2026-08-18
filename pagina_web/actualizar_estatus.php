<?php
/**
 * =====================================================================
 * ACTUALIZAR ESTATUS (actualizar_estatus.php)
 * Modifica el estatus asignado por Control Escolar en la BD
 * =====================================================================
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit;
}

require_once 'db.php';

$json = file_get_contents('php://input');
$data = json_decode($json, true);

if (!isset($data['id']) || !isset($data['estatus_admin'])) {
    echo json_encode(["success" => false, "message" => "Parámetros incompletos."]);
    exit;
}

try {
    $sql = "UPDATE alumnos SET estatus_admin = :estatus WHERE id = :id";
    $stmt = $pdo->prepare($sql);
    $stmt->execute([
        ':estatus' => $data['estatus_admin'],
        ':id' => $data['id']
    ]);

    echo json_encode(["success" => true, "message" => "Estatus actualizado con éxito."]);

} catch (PDOException $e) {
    echo json_encode(["success" => false, "message" => "Error SQL: " . $e->getMessage()]);
}
?>
