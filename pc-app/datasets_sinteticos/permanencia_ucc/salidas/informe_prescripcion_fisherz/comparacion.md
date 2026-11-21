# Comparación de Scotty PC con la verdad (`informe_prescripcion_fisherz`)

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
| Orientadas correctamente | 23 |
| Invertidas | 0 |
| Encontradas sin orientar | 0 |
| Exactitud de orientación (sobre las orientadas) | 1.00 |
| **SHD** (faltantes + sobrantes + invertidas + sin orientar) | **8** |

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

## 4. Variables de control

No deben afectar a `permanece` (son ruido por construcción).

| Variable | Aristas con cualquier variable | ¿Conectada al objetivo? |
|---|---|---|
| genero | — (verdad: —) | no |
| vive_con_familia | edad_ingreso (verdad: edad_ingreso) | no |

## 5. Prescripciones

Se evaluaron 323 casos aplicando las acciones en el generador verdadero (operador do, mismo ruido de cada estudiante). `caso` se interpreta como fila (desde 0) de `permanencia_ucc.csv`.

| Métrica | Valor |
|---|---|
| Error medio (prometida − verdadera), valores tal como los propone el optimizador | +4.6 pp |
| Error absoluto medio | 8.3 pp |
| Error medio con valores redondeados a estados válidos | +4.6 pp |
| Error absoluto medio con valores redondeados | 8.3 pp |
| Mejora media prometida (después − antes) | +21.5 pp |
| Mejora media verdadera | +16.1 pp |
| Meta | P ≥ 0.80 |
| % que el modelo promete llevar a la meta | 91% |
| % que realmente llega (valores tal cual) | 42% |
| % que realmente llega (valores redondeados) | 42% |
| Casos con valores fuera de los estados válidos (p. ej. 2,4 tutorías) | 0 de 323 |

Peores 5 casos (mayor sobrepromesa):

| caso | acciones | prometida | verdadera | redondeada |
|---|---|---|---|---|
| 2096 | horas_estudio_semana→13 | 0.80 | 0.40 | 0.40 |
| 171 | horas_estudio_semana→12.5; asistencia_pct→71 | 0.80 | 0.41 | 0.41 |
| 2533 | horas_estudio_semana→15; asistencia_pct→73 | 0.80 | 0.44 | 0.44 |
| 2779 | horas_estudio_semana→14.5; asistencia_pct→99; apoyo_financiero→1; tutorias_asistidas→3; horas_trabajo_semana→18 | 0.80 | 0.44 | 0.44 |
| 1201 | horas_estudio_semana→12; asistencia_pct→83 | 0.80 | 0.47 | 0.47 |
