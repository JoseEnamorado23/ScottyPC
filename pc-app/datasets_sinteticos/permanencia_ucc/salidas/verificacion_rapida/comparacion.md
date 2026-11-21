# Comparación de Scotty PC con la verdad (`rapida_800`)

## 1. Esqueleto (sin dirección)

| Métrica | Valor |
|---|---|
| Aristas verdaderas | 28 |
| Aristas encontradas por PC | 28 |
| Acertadas | 28 |
| Precisión | 1.00 |
| Exhaustividad (recall) | 1.00 |
| F1 | 1.00 |

## 2. Orientación y SHD

| Métrica | Valor |
|---|---|
| Orientadas correctamente | 28 |
| Invertidas | 0 |
| Encontradas sin orientar | 0 |
| Exactitud de orientación (sobre las orientadas) | 1.00 |
| **SHD** (faltantes + sobrantes + invertidas + sin orientar) | **0** |

## 3. Diferencias

### Faltantes (0)

- ninguna

### Sobrantes (0)

- ninguna

### Invertidas (0)

- ninguna

## 4. Variables de control

No deben afectar a `permanece` (son ruido por construcción).

| Variable | Aristas con cualquier variable | ¿Conectada al objetivo? |
|---|---|---|
| genero | — (verdad: —) | no |
| vive_con_familia | edad_ingreso (verdad: edad_ingreso) | no |

## 5. Prescripciones

Se evaluaron 87 casos aplicando las acciones en el generador verdadero (operador do, mismo ruido de cada estudiante). `caso` se interpreta como fila (desde 0) de `permanencia_ucc.csv`.

| Métrica | Valor |
|---|---|
| Error medio (prometida − verdadera), valores tal como los propone el optimizador | -6.4 pp |
| Error absoluto medio | 13.4 pp |
| Error medio con valores redondeados a estados válidos | -6.4 pp |
| Error absoluto medio con valores redondeados | 13.4 pp |
| Mejora media prometida (después − antes) | +20.3 pp |
| Mejora media verdadera | +6.9 pp |
| Meta | P ≥ 0.80 |
| % que el modelo promete llevar a la meta | 90% |
| % que realmente llega (valores tal cual) | 79% |
| % que realmente llega (valores redondeados) | 79% |
| Casos con valores fuera de los estados válidos (p. ej. 2,4 tutorías) | 0 de 87 |

Peores 5 casos (mayor sobrepromesa):

| caso | acciones | prometida | verdadera | redondeada |
|---|---|---|---|---|
| 365 | horas_estudio_semana→4 | 0.81 | 0.14 | 0.14 |
| 280 | horas_estudio_semana→4.5 | 0.81 | 0.37 | 0.37 |
| 736 | horas_estudio_semana→11; asistencia_pct→73 | 0.80 | 0.43 | 0.43 |
| 92 |  | 0.79 | 0.54 | 0.54 |
| 277 | horas_estudio_semana→10.5; asistencia_pct→89; horas_trabajo_semana→9; apoyo_bienestar→1; tutorias_asistidas→4; creditos_matriculados→14 | 0.72 | 0.51 | 0.51 |
