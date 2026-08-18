-- =====================================================================
-- SCRIPT DE CREACIÓN DE TABLA EN HOSTINGER (crear_tabla.sql)
-- Pega este código en la pestaña SQL de phpMyAdmin
-- =====================================================================

CREATE TABLE alumnos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    edad INT NOT NULL,
    carrera VARCHAR(255) NOT NULL,
    
    -- Campos del documento CURP
    curp_nombre_archivo VARCHAR(255),
    curp_estado VARCHAR(50),
    curp_confianza FLOAT,
    curp_obs TEXT,
    
    -- Campos del documento Acta de Nacimiento
    acta_nombre_archivo VARCHAR(255),
    acta_estado VARCHAR(50),
    acta_confianza FLOAT,
    acta_obs TEXT,
    
    -- Estatus final del trámite administrativo
    estatus_admin VARCHAR(50) DEFAULT 'Pendiente',
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
