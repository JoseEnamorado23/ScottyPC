# Comparación de Scotty PC con la verdad (`v3`)

## 1. Esqueleto (sin dirección)

| Métrica | Valor |
|---|---|
| Aristas verdaderas | 28 |
| Aristas encontradas por PC | 26 |
| Acertadas | 23 |
| Precisión | 0.88 |
| Exhaustividad (recall) | 0.82 |
| F1 | 0.85 |

## 2. Orientación y SHD

| Métrica | Valor |
|---|---|
| Orientadas correctamente | 22 |
| Invertidas | 0 |
| Encontradas sin orientar | 1 |
| Exactitud de orientación (sobre las orientadas) | 1.00 |
| **SHD** (faltantes + sobrantes + invertidas + sin orientar) | **9** |

## 3. Diferencias

### Faltantes (5)

- apoyo_bienestar — permanece
- creditos_matriculados — promedio_semestre
- estrato — permanece
- horas_estudio_semana — horas_trabajo_semana
- horas_trabajo_semana — permanece

### Sobrantes (3)

- asistencia_pct — edad_ingreso — indirecta: hay un camino causal verdadero entre las dos (efecto mediado)
- asistencia_pct — horas_estudio_semana — explicada por la variable latente `motivacion` (ambas son hijas suyas)
- asistencia_pct — tutorias_asistidas — explicada por la variable latente `motivacion` (ambas son hijas suyas)

### Invertidas (0)

- ninguna

### Encontradas sin orientar (1)

- primera_generacion — puntaje_saber11 (verdad: primera_generacion → puntaje_saber11)

## 4. Variables de control

No deben afectar a `permanece` (son ruido por construcción).

| Variable | Aristas con cualquier variable | ¿Conectada al objetivo? |
|---|---|---|
| genero | — (verdad: —) | no |
| vive_con_familia | edad_ingreso (verdad: edad_ingreso) | no |

## 5. Prescripciones

No hay `prescripciones.csv` en la carpeta; se omite esta sección.
