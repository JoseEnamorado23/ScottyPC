# Comparación de corridas de PC contra la verdad (permanencia_ucc)

| Métrica | v1 | v2 | v3 | v4 |
|---|---|---|---|---|
| Prueba / umbral | chisq / 0.60 | chisq / 0.60 | fisherz / 0.60 | fisherz / 0.50 |
| Aristas encontradas (verdad: 28) | 13 | 13 | 26 | 26 |
| Precisión | 1.00 | 1.00 | 0.88 | 0.88 |
| Recall | 0.46 | 0.46 | 0.82 | 0.82 |
| F1 | 0.63 | 0.63 | 0.85 | 0.85 |
| Orientadas bien / invertidas / sin orientar | 9 / 3 / 1 | 13 / 0 / 0 | 22 / 0 / 1 | 22 / 0 / 1 |
| Exactitud de orientación | 0.75 | 1.00 | 1.00 | 1.00 |
| SHD | 19 | 15 | 9 | 9 |
| Aristas falsas (sobrantes) | 0 | 0 | 3 | 3 |
|   · explicadas por la latente `motivacion` | 0 | 0 | 2: asistencia_pct—horas_estudio_semana, asistencia_pct—tutorias_asistidas | 2: asistencia_pct—horas_estudio_semana, asistencia_pct—tutorias_asistidas |
|   · otras | 0 | 0 | 1: asistencia_pct—edad_ingreso (indirecta: hay un camino causal verdadero entre las dos (efecto mediado)) | 1: asistencia_pct—edad_ingreso (indirecta: hay un camino causal verdadero entre las dos (efecto mediado)) |
| `apoyo_financiero → permanece` | no | no | sí, bien orientada | sí, bien orientada |
| `promedio_semestre → materias_reprobadas` | no | no | sí, bien orientada | sí, bien orientada |
| Aristas hacia `permanece` (verdad: 6) | 2: materias_reprobadas, promedio_semestre | 2: materias_reprobadas, promedio_semestre | 3: apoyo_financiero, materias_reprobadas, promedio_semestre | 3: apoyo_financiero, materias_reprobadas, promedio_semestre |
| Variables prescriptivas resultantes | 3: horas_trabajo_semana, asistencia_pct, horas_estudio_semana | 3: horas_trabajo_semana, asistencia_pct, horas_estudio_semana | 6: horas_trabajo_semana, asistencia_pct, horas_estudio_semana, tutorias_asistidas, creditos_matriculados, apoyo_financiero | 6: horas_trabajo_semana, asistencia_pct, horas_estudio_semana, tutorias_asistidas, creditos_matriculados, apoyo_financiero |
