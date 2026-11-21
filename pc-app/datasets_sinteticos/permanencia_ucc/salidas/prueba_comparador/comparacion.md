# Comparación de Scotty PC con la verdad (`prueba_comparador`)

## 1. Esqueleto (sin dirección)

| Métrica | Valor |
|---|---|
| Aristas verdaderas | 28 |
| Aristas encontradas por PC | 27 |
| Acertadas | 25 |
| Precisión | 0.93 |
| Exhaustividad (recall) | 0.89 |
| F1 | 0.91 |

## 2. Orientación y SHD

| Métrica | Valor |
|---|---|
| Orientadas correctamente | 24 |
| Invertidas | 1 |
| Encontradas sin orientar | 0 |
| Exactitud de orientación (sobre las orientadas) | 0.96 |
| **SHD** (faltantes + sobrantes + invertidas + sin orientar) | **6** |

## 3. Diferencias

### Faltantes (3)

- apoyo_bienestar — permanece
- estrato — primera_generacion
- promedio_semestre — tutorias_asistidas

### Sobrantes (2)

- genero — permanece — sin explicación estructural (posible falso positivo)
- horas_estudio_semana — tutorias_asistidas — explicada por la variable latente `motivacion` (ambas son hijas suyas)

### Invertidas (1)

- PC dice promedio_semestre → asistencia_pct; la verdad es asistencia_pct → promedio_semestre — explicada por la variable latente `motivacion` (ambas son hijas suyas)

## 4. Variables de control

No deben afectar a `permanece` (son ruido por construcción).

| Variable | Aristas con cualquier variable | ¿Conectada al objetivo? |
|---|---|---|
| genero | permanece (verdad: —) | **SÍ — falso positivo** |
| vive_con_familia | edad_ingreso (verdad: edad_ingreso) | no |

## 5. Prescripciones

Se evaluaron 6 casos aplicando las acciones en el generador verdadero (operador do, mismo ruido de cada estudiante). `caso` se interpreta como fila (desde 0) de `permanencia_ucc.csv`.

| Métrica | Valor |
|---|---|
| Error medio (prometida − verdadera), valores tal como los propone el optimizador | +10.0 pp |
| Error absoluto medio | 10.0 pp |
| Error medio con valores redondeados a estados válidos | +10.4 pp |
| Error absoluto medio con valores redondeados | 10.4 pp |
| Mejora media prometida (después − antes) | +42.8 pp |
| Mejora media verdadera | +32.8 pp |
| Meta | P ≥ 0.80 |
| % que el modelo promete llevar a la meta | 67% |
| % que realmente llega (valores tal cual) | 17% |
| % que realmente llega (valores redondeados) | 17% |
| Casos con valores fuera de los estados válidos (p. ej. 2,4 tutorías) | 3 de 6 |

Peores 5 casos (mayor sobrepromesa):

| caso | acciones | prometida | verdadera | redondeada |
|---|---|---|---|---|
| 66 | asistencia_pct→100; tutorias_asistidas→2.4; apoyo_financiero→1 | 0.44 | 0.34 | 0.33 |
| 26 | asistencia_pct→100; tutorias_asistidas→3; apoyo_financiero→1 | 0.94 | 0.84 | 0.84 |
| 36 | asistencia_pct→100; tutorias_asistidas→2.4 | 0.78 | 0.68 | 0.68 |
| 39 | asistencia_pct→100; tutorias_asistidas→3; apoyo_financiero→1 | 0.86 | 0.76 | 0.76 |
| 42 | asistencia_pct→100; tutorias_asistidas→2.4; apoyo_financiero→1 | 0.85 | 0.75 | 0.74 |
