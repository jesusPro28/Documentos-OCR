<?php
/**
 * =====================================================================
 * OBTENER ALUMNOS (obtener_alumnos.php)
 * Lee los alumnos de la BD y los devuelve en JSON para el administrador
 * =====================================================================
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

require_once 'db.php';

try {
    // Obtenemos los alumnos del más reciente al más antiguo
    $stmt = $pdo->query("SELECT * FROM alumnos ORDER BY id DESC");
    $alumnos_raw = $stmt->fetchAll();
    
    // Mapeamos los campos planos de la BD al formato JSON estructurado que espera app.js
    $alumnos = [];
    foreach ($alumnos_raw as $row) {
        // Reconstruimos los semáforos de barreras desde el texto de observaciones guardado
        $curp_obs = $row['curp_obs'] ?? '';
        $acta_obs = $row['acta_obs'] ?? '';

        $alumnos[] = [
            'id' => (int)$row['id'],
            'nombre' => $row['nombre'],
            'edad' => (int)$row['edad'],
            'carrera' => $row['carrera'],
            'curp' => [
                'id'             => (int)$row['id'],
                'tipo'           => 'curp',
                'nombre_archivo' => $row['curp_nombre_archivo'],
                'estado'         => $row['curp_estado'],
                'conf_ocr'       => $row['curp_confianza'] !== null ? (float)$row['curp_confianza'] : "N/D",
                'obs'            => $curp_obs,
                'b1' => str_contains($curp_obs, 'B1: OK') ? true : (str_contains($curp_obs, 'B1:') ? false : null),
                'b2' => str_contains($curp_obs, 'B2: OK') ? true : (str_contains($curp_obs, 'B2:') ? false : null),
                'b3' => str_contains($curp_obs, 'B3: OK') || (str_contains($curp_obs, 'B3:') && !str_contains($curp_obs, 'Rechazado') && !str_contains($curp_obs, 'incorrecto')) ? true : (str_contains($curp_obs, 'B3:') ? false : null)
            ],
            'acta' => [
                'id'             => (int)$row['id'],
                'tipo'           => 'acta',
                'nombre_archivo' => $row['acta_nombre_archivo'],
                'estado'         => $row['acta_estado'],
                'conf_ocr'       => $row['acta_confianza'] !== null ? (float)$row['acta_confianza'] : "N/D",
                'obs'            => $acta_obs,
                'b1' => str_contains($acta_obs, 'B1: OK') ? true : (str_contains($acta_obs, 'B1:') ? false : null),
                'b2' => str_contains($acta_obs, 'B2: OK') ? true : (str_contains($acta_obs, 'B2:') ? false : null),
                'b3' => str_contains($acta_obs, 'B3: OK') || (str_contains($acta_obs, 'B3:') && !str_contains($acta_obs, 'Rechazado') && !str_contains($acta_obs, 'incorrecto')) ? true : (str_contains($acta_obs, 'B3:') ? false : null)
            ],
            'estatus_admin' => $row['estatus_admin']
        ];
    }

    echo json_encode($alumnos);

} catch (PDOException $e) {
    echo json_encode(["error" => "Error SQL: " . $e->getMessage()]);
}
?>
