-- Esquema de app.db (versión 1).

CREATE TABLE proyectos (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    archivo_original TEXT NOT NULL,
    archivo TEXT NOT NULL,
    hoja TEXT,
    sha256 TEXT NOT NULL,
    objetivo TEXT,
    etapa_actual TEXT,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);

CREATE TABLE etapas (
    proyecto_id TEXT NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    etapa TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('vigente', 'desactualizada')),
    actualizada_en TEXT NOT NULL,
    PRIMARY KEY (proyecto_id, etapa)
);

CREATE TABLE trabajos (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('recomendacion', 'pc')),
    estado TEXT NOT NULL CHECK (
        estado IN ('pendiente', 'en_curso', 'completado', 'cancelado', 'fallido', 'interrumpido')
    ),
    completadas INTEGER NOT NULL DEFAULT 0,
    total INTEGER,
    fallidas INTEGER NOT NULL DEFAULT 0,
    segundos REAL NOT NULL DEFAULT 0,
    mensaje TEXT,
    parametros TEXT NOT NULL DEFAULT '{}',
    inicio TEXT,
    fin TEXT,
    error TEXT,
    actualizado_en TEXT NOT NULL
);

-- Un solo trabajo activo por proyecto.
CREATE UNIQUE INDEX un_trabajo_activo ON trabajos(proyecto_id)
    WHERE estado IN ('pendiente', 'en_curso');

CREATE INDEX trabajos_por_proyecto ON trabajos(proyecto_id, inicio);
