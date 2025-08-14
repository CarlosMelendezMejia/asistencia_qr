CREATE DATABASE IF NOT EXISTS asistenciaqr CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE asistenciaqr;

-- Tabla de eventos
CREATE TABLE IF NOT EXISTS evento (
  id INT AUTO_INCREMENT PRIMARY KEY,
  slug VARCHAR(100) NOT NULL UNIQUE,
  titulo VARCHAR(200) NOT NULL,
  fecha_inicio DATETIME NULL,
  fecha_fin DATETIME NULL,
  lugar VARCHAR(200) NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Tabla de registros/asistencia (uno por persona por evento)
CREATE TABLE IF NOT EXISTS registro (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  id_evento INT NOT NULL,
  nombre VARCHAR(100) NOT NULL,
  apellidos VARCHAR(120) NOT NULL,
  email VARCHAR(180) NOT NULL,
  telefono VARCHAR(30) NULL,
  institucion VARCHAR(180) NULL,
  carrera_o_area VARCHAR(180) NULL,
  consentimiento TINYINT(1) NOT NULL DEFAULT 0,
  asistencia_marcarda_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ip VARCHAR(45) NULL,
  user_agent TEXT NULL,
  creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_evento_email (id_evento, email),
  INDEX idx_evento (id_evento),
  CONSTRAINT fk_registro_evento FOREIGN KEY (id_evento) REFERENCES evento(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Evento de ejemplo
INSERT IGNORE INTO evento (slug, titulo, fecha_inicio, lugar)
VALUES ('ponencia-ia-ago2025', 'Ponencia: IA aplicada', '2025-08-20 10:00:00', 'Auditorio Principal');
