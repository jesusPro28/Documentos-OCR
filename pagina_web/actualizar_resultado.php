<?php
/**
 * =====================================================================
 * ACTUALIZAR RESULTADO (actualizar_resultado.php)
 * Recibe el veredicto final de la IA (desde la tarea de fondo de Python)
 * y actualiza el registro del alumno en la BD con los resultados reales.
 * =====================================================================
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

require_once 'db.php';

$json = file_get_contents('php://input');
$data = json_decode($json, true);

if (!$data || !isset($data['id'])) {
    echo json_encode(["success" => false, "message" => "Datos inválidos o ID faltante."]);
    exit;
}

try {
    $sql = "UPDATE alumnos SET
                curp_estado     = :curp_estado,
                curp_confianza  = :curp_confianza,
                curp_obs        = :curp_obs,
                acta_estado     = :acta_estado,
                acta_confianza  = :acta_confianza,
                acta_obs        = :acta_obs,
                estatus_admin   = 'Pendiente'
            WHERE id = :id";

    $stmt = $pdo->prepare($sql);
    $stmt->execute([
        ':id'             => (int)$data['id'],
        ':curp_estado'    => $data['curp']['estado'],
        ':curp_confianza' => $data['curp']['confianza'] ?? null,
        ':curp_obs'       => $data['curp']['obs'],
        ':acta_estado'    => $data['acta']['estado'],
        ':acta_confianza' => $data['acta']['confianza'] ?? null,
        ':acta_obs'       => $data['acta']['obs']
    ]);

    echo json_encode(["success" => true, "message" => "Registro actualizado con resultados de IA."]);

} catch (PDOException $e) {
    echo json_encode(["success" => false, "message" => "Error SQL: " . $e->getMessage()]);
}
?>
