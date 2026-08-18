<?php
/**
 * =====================================================================
 * GUARDAR PENDIENTE (guardar_pendiente.php)
 * Crea un registro "Analizando" en la BD antes de que la IA procese.
 * Recibe los archivos como base64 dentro del payload JSON.
 * Los decodifica y los almacena como MEDIUMBLOB en MySQL.
 * =====================================================================
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

require_once 'db.php';

$json = file_get_contents('php://input');
$data = json_decode($json, true);

if (!$data) {
    echo json_encode(["success" => false, "message" => "Datos inválidos."]);
    exit;
}

// Decodificar archivos desde base64
$curp_bytes = !empty($data['curp_b64']) ? base64_decode($data['curp_b64']) : null;
$acta_bytes = !empty($data['acta_b64']) ? base64_decode($data['acta_b64']) : null;

try {
    $sql = "INSERT INTO alumnos (
                nombre, edad, carrera,
                curp_nombre_archivo, curp_estado, curp_obs, curp_archivo, curp_mime,
                acta_nombre_archivo, acta_estado, acta_obs, acta_archivo, acta_mime,
                estatus_admin
            ) VALUES (
                :nombre, :edad, :carrera,
                :curp_nombre, 'PROCESANDO', 'Análisis de IA en proceso...', :curp_archivo, :curp_mime,
                :acta_nombre, 'PROCESANDO', 'Análisis de IA en proceso...', :acta_archivo, :acta_mime,
                'Analizando'
            )";

    $stmt = $pdo->prepare($sql);
    $stmt->bindParam(':nombre',       $data['nombre']);
    $stmt->bindParam(':edad',         $data['edad'],    PDO::PARAM_INT);
    $stmt->bindParam(':carrera',      $data['carrera']);
    $stmt->bindParam(':curp_nombre',  $data['curp_nombre']);
    $stmt->bindParam(':curp_archivo', $curp_bytes,      PDO::PARAM_LOB);
    $stmt->bindParam(':curp_mime',    $data['curp_mime']);
    $stmt->bindParam(':acta_nombre',  $data['acta_nombre']);
    $stmt->bindParam(':acta_archivo', $acta_bytes,      PDO::PARAM_LOB);
    $stmt->bindParam(':acta_mime',    $data['acta_mime']);
    $stmt->execute();

    $id = $pdo->lastInsertId();
    echo json_encode(["success" => true, "id" => (int)$id]);

} catch (PDOException $e) {
    echo json_encode(["success" => false, "message" => "Error SQL: " . $e->getMessage()]);
}
?>
