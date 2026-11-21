# Informe de prescripción de PC contra la verdad (`pc`)

## 1. Grafo

| Métrica | Valor |
|---|---|
| Aristas encontradas (verdad: 28) | 26 |
| Precisión / recall / F1 | 0.88 / 0.82 / 0.85 |
| Orientadas bien / invertidas / sin orientar | 23 / 0 / 0 |
| SHD | 8 |
| Aristas falsas | 3: asistencia_pct — edad_ingreso (indirecta: hay un camino causal verdadero entre las dos (efecto mediado)); asistencia_pct — horas_estudio_semana (explicada por la variable latente `motivacion` (ambas son hijas suyas)); asistencia_pct — tutorias_asistidas (explicada por la variable latente `motivacion` (ambas son hijas suyas)) |
| ¿Mismo grafo que `v3`? | **NO**: [('primera_generacion', 'puntaje_saber11'), ('puntaje_saber11', 'primera_generacion')] |

Orientaciones manuales aplicadas en la app (el esqueleto y las 100 corridas son las mismas; solo cambia la orientación): primera_generacion → puntaje_saber11.

## 2. Prometida frente a verdadera

323 planes del lote (de 323 filas), evaluados en el generador con el do-operator y el ruido de cada estudiante. Meta: P ≥ 0.80.

| Métrica | Valor |
|---|---|
| Error medio (prometida − verdadera) | +4.6 pp |
| Error absoluto medio | 8.3 pp |
| Error medio / absoluto con valores redondeados | +4.6 pp / 8.3 pp |
| Mejora media prometida / verdadera | +21.5 pp / +16.1 pp |
| % de planes que el modelo promete llevar a 0.80 | 91% |
| **% de planes que DE VERDAD alcanzan 0.80** | **42%** (135 de 323) |
| % que alcanza con valores redondeados | 42% |
| Planes con valores fuera de los estados válidos | 0 de 323 |
| Casos sin correspondencia (ignorados) | 0 |

Planes que el modelo da por alcanzados: 295; no alcanzables: 28. Entre los alcanzados, de verdad llegan a la meta 43%.

## 3. Por tipo de acción

Las aristas falsas de v3 son todas hacia `asistencia_pct` (con `horas_estudio_semana`, `tutorias_asistidas` y `edad_ingreso`), por eso se separan los planes que usan tutorías u horas de estudio.

| Grupo | Planes | Error medio | Error abs. | Promete meta | Llega (tal cual) | Llega (redondeada) |
|---|---|---|---|---|---|---|
| Usan tutorías u horas de estudio | 319 | +4.7 pp | 8.4 pp | 92% | 41% | 41% |
| No las usan | 4 | -4.1 pp | 7.5 pp | 0% | 75% | 75% |
|   · usan además asistencia_pct | 135 | +8.4 pp | 10.2 pp | 83% | 24% | 24% |
|   · tutorías/horas sin asistencia | 184 | +2.0 pp | 7.0 pp | 99% | 54% | 54% |
| Usan asistencia_pct (con o sin lo anterior) | 135 | +8.4 pp | 10.2 pp | 83% | 24% | 24% |
| Todos | 323 | +4.6 pp | 8.3 pp | 91% | 42% | 42% |

Planes que tocan cada variable: `asistencia_pct` 135, `horas_estudio_semana` 319, `tutorias_asistidas` 33, `creditos_matriculados` 9, `apoyo_financiero` 46, `horas_trabajo_semana` 20.

## 4. Créditos

Planes que cambian `creditos_matriculados`: 9. Planes que bajan créditos a alguien con 14 o menos, o que dejan menos de 14: **0** (esperado: 0).

## 5. Casos «no alcanzables» frente a la verdad

Comprobación: el valor «antes» de 0 acciones del CSV difiere del valor del estudiante en el generador (esperado: 0).

Para cada uno de los 28 casos se buscó, de forma exhaustiva sobre la rejilla permitida (restricciones de controles.json del artefacto), la mayor P verdadera posible con el ruido de ese estudiante.

| caso | P antes (verdad) | P prometida | P verdadera de su plan | **mejor P verdadera posible** | ¿alcanzable en la verdad? | mejor plan |
|---|---|---|---|---|---|---|
| 87 | 0.23 | 0.77 | 0.76 | 0.77 | no | horas_estudio_semana 3→11; tutorias_asistidas 1→5; asistencia_pct 85→98; creditos_matriculados 17→15; apoyo_financiero 0→1 |
| 129 | 0.35 | 0.80 | 0.72 | 0.86 | **sí** | horas_trabajo_semana 13→3; horas_estudio_semana 4→12; tutorias_asistidas 0→4; asistencia_pct 79→99; apoyo_financiero 0→1 |
| 326 | 0.15 | 0.79 | 0.73 | 0.73 | no | horas_trabajo_semana 15→5; horas_estudio_semana 2.5→10.5; tutorias_asistidas 2→6; asistencia_pct 69→89 |
| 479 | 0.61 | 0.80 | 0.71 | 0.92 | **sí** | horas_estudio_semana 8.5→16.5; tutorias_asistidas 0→4; asistencia_pct 88→99; creditos_matriculados 19→15; apoyo_financiero 0→1 |
| 513 | 0.05 | 0.72 | 0.60 | 0.60 | no | horas_trabajo_semana 18→8; horas_estudio_semana 2→10; tutorias_asistidas 0→4; asistencia_pct 71→91; apoyo_financiero 0→1 |
| 517 | 0.40 | 0.80 | 0.76 | 0.92 | **sí** | horas_trabajo_semana 24→14; horas_estudio_semana 2→10; tutorias_asistidas 0→4; asistencia_pct 68→88; creditos_matriculados 17→15; apoyo_financiero 0→1 |
| 820 | 0.45 | 0.79 | 0.77 | 0.89 | **sí** | horas_trabajo_semana 28→18; horas_estudio_semana 3→11; tutorias_asistidas 1→5; asistencia_pct 86→99; creditos_matriculados 17→15; apoyo_financiero 0→1 |
| 841 | 0.73 | 0.80 | 0.73 | 0.94 | **sí** | horas_trabajo_semana 16→6; horas_estudio_semana 4→12; tutorias_asistidas 1→5; asistencia_pct 91→99; apoyo_financiero 0→1 |
| 935 | 0.88 | 0.80 | 0.88 | 0.98 | **sí** | horas_estudio_semana 4.5→12.5; tutorias_asistidas 1→5; asistencia_pct 61→81; apoyo_financiero 0→1 |
| 943 | 0.62 | 0.80 | 0.80 | 0.91 | **sí** | horas_estudio_semana 4→12; tutorias_asistidas 1→5; asistencia_pct 85→99; creditos_matriculados 17→15; apoyo_financiero 0→1 |
| 1039 | 0.08 | 0.65 | 0.62 | 0.63 | no | horas_trabajo_semana 19→9; horas_estudio_semana 2.5→10.5; tutorias_asistidas 0→4; asistencia_pct 69→89; creditos_matriculados 19→15 |
| 1180 | 0.16 | 0.64 | 0.83 | 0.84 | **sí** | horas_estudio_semana 1.5→9.5; tutorias_asistidas 0→4; asistencia_pct 81→99; creditos_matriculados 20→15 |
| 1354 | 0.10 | 0.74 | 0.78 | 0.79 | no | horas_trabajo_semana 28→18; horas_estudio_semana 2→10; tutorias_asistidas 2→6; asistencia_pct 59→79; apoyo_financiero 0→1 |
| 1420 | 0.48 | 0.80 | 0.70 | 0.92 | **sí** | horas_estudio_semana 3.5→11.5; tutorias_asistidas 1→5; asistencia_pct 82→99; creditos_matriculados 20→15; apoyo_financiero 0→1 |
| 1824 | 0.25 | 0.79 | 0.76 | 0.76 | no | horas_trabajo_semana 22→12; horas_estudio_semana 3→11; tutorias_asistidas 1→5; asistencia_pct 69→89 |
| 1923 | 0.02 | 0.61 | 0.36 | 0.51 | no | horas_trabajo_semana 37→27; horas_estudio_semana 2→10; tutorias_asistidas 1→5; asistencia_pct 47→67; apoyo_financiero 0→1 |
| 2067 | 0.44 | 0.80 | 0.63 | 0.93 | **sí** | horas_trabajo_semana 18→8; horas_estudio_semana 4→12; tutorias_asistidas 1→5; asistencia_pct 82→99; creditos_matriculados 20→15; apoyo_financiero 0→1 |
| 2251 | 0.19 | 0.80 | 0.83 | 0.83 | **sí** | horas_trabajo_semana 19→9; horas_estudio_semana 3→11; tutorias_asistidas 0→4; asistencia_pct 79→99; creditos_matriculados 18→15; apoyo_financiero 0→1 |
| 2300 | 0.16 | 0.76 | 0.70 | 0.70 | no | horas_trabajo_semana 18→8; horas_estudio_semana 3.5→11.5; tutorias_asistidas 2→6; asistencia_pct 53→73 |
| 2380 | 0.86 | 0.80 | 0.89 | 0.99 | **sí** | horas_trabajo_semana 21→11; horas_estudio_semana 2.5→10.5; tutorias_asistidas 0→4; asistencia_pct 81→99; creditos_matriculados 17→15; apoyo_financiero 0→1 |
| 2527 | 0.15 | 0.75 | 0.67 | 0.67 | no | horas_trabajo_semana 32→22; horas_estudio_semana 2.5→10.5; tutorias_asistidas 1→5; asistencia_pct 85→99 |
| 2578 | 0.66 | 0.80 | 0.85 | 0.93 | **sí** | horas_estudio_semana 3→11; tutorias_asistidas 2→6; asistencia_pct 90→99; apoyo_financiero 0→1 |
| 2591 | 0.68 | 0.80 | 0.80 | 0.96 | **sí** | horas_estudio_semana 5.5→13.5; tutorias_asistidas 2→6; asistencia_pct 91→98; creditos_matriculados 22→16; apoyo_financiero 0→1 |
| 2661 | 0.59 | 0.80 | 0.74 | 0.88 | **sí** | horas_estudio_semana 2.5→10.5; tutorias_asistidas 2→6; asistencia_pct 90→98; apoyo_financiero 0→1 |
| 2681 | 0.85 | 0.80 | 0.85 | 0.96 | **sí** | horas_estudio_semana 7.5→15.5; tutorias_asistidas 0→4; asistencia_pct 90→99; creditos_matriculados 18→15; apoyo_financiero 0→1 |
| 2781 | 0.38 | 0.80 | 0.70 | 0.90 | **sí** | horas_trabajo_semana 40→30; horas_estudio_semana 5→13; tutorias_asistidas 1→5; asistencia_pct 77→97; apoyo_financiero 0→1 |
| 2789 | 0.53 | 0.80 | 0.70 | 0.85 | **sí** | horas_estudio_semana 5→13; tutorias_asistidas 2→6; asistencia_pct 84→99; apoyo_financiero 0→1 |
| 2986 | 0.43 | 0.80 | 0.74 | 0.88 | **sí** | horas_estudio_semana 5→13; tutorias_asistidas 0→4; asistencia_pct 60→80; creditos_matriculados 18→15; apoyo_financiero 0→1 |

**9 de 28** no eran alcanzables tampoco en la verdad con las mismas restricciones; **19** sí lo eran (el modelo no los encontró).
