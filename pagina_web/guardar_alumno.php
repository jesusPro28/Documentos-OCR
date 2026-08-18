<?php
/**
 * =====================================================================
 * GUARDAR ALUMNO (guardar_alumno.php)
 * Recibe datos del alumno y veredicto de IA, y los guarda en la BD
 * =====================================================================
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *'); // Habilita peticiones cruzadas
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit; // Manejo preliminar para CORS
}

require_once 'db.php';

// Leemos el payload JSON enviado por JavaScript
$json = file_get_contents('php://input');
$data = json_decode($json, true);

if (!$data) {
    echo json_encode(["success" => false, "message" => "No se recibieron datos válidos."]);
    exit;
}

try {
    $sql = "INSERT INTO alumnos (
                nombre, edad, carrera, 
                curp_nombre_archivo, curp_estado, curp_confianza, curp_obs, 
                acta_nombre_archivo, acta_estado, acta_confianza, acta_obs, 
                estatus_admin
            ) VALUES (
                :nombre, :edad, :carrera, 
                :curp_nombre, :curp_estado, :curp_confianza, :curp_obs, 
                :acta_nombre, :acta_estado, :acta_confianza, :acta_obs, 
                'Pendiente'
            )";

    $stmt = $pdo->prepare($sql);
    
    // Vinculamos parámetros sanitizados
    $stmt->execute([
        ':nombre' => $data['nombre'],
        ':edad' => $data['edad'],
        ':carrera' => $data['carrera'],
        ':curp_nombre' => $data['curp']['nombre_archivo'],
        ':curp_estado' => $data['curp']['estado'],
        ':curp_confianza' => ($data['curp']['conf_ocr'] !== "N/D") ? $data['curp']['conf_ocr'] : null,
        ':curp_obs' => $data['curp']['obs'],
        ':acta_nombre' => $data['acta']['nombre_archivo'],
        ':acta_estado' => $data['acta']['estado'],
        ':acta_confianza' => ($data['acta']['conf_ocr'] !== "N/D") ? $data['acta']['conf_ocr'] : null,
        ':acta_obs' => $data['acta']['obs']
    ]);

    echo json_encode(["success" => true, "message" => "Registro guardado en base de datos."]);

} catch (PDOException $e) {
    echo json_encode(["success" => false, "message" => "Error SQL: " . $e->getMessage()]);
}
?>
