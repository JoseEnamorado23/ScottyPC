# Verificación de realismo

n = 3000, semilla = 2026

| Meta | Rango objetivo | Valor | Estado |
|---|---|---|---|
| Permanencia | 78 – 85 % | 80.4% | OK |
| Promedio: media | ≈ 3,5 | 3.57 | OK |
| Promedio: desviación | ≈ 0,6 | 0.64 | OK |
| Promedio < 3,0 | 15 – 20 % | 19.3% | OK |
| AUC regresión logística (CV 5) | 0,78 – 0,88 | 0.811 ± 0.014 | OK |
| Asistencia +10: efecto en subgrupo en riesgo | +3 a +12 pp | +6.0 pp | OK |
| Mejor acción sola: efecto máx. en riesgo | no extremo | +12.3 pp | OK |
| Mejor acción sola: % de riesgo que llega a P≥0,8 | pocos | 0.0% | OK |
| |ρ| genero – permanece | < 0,05 | -0.021 | OK |
| |ρ| vive_con_familia – permanece | < 0,05 | +0.011 | OK |
| Máx. |ρ Spearman| entre columnas | < 0,90 (nada determinista) | 0.59 (puntaje_saber11–promedio_semestre) | OK |
| Acumulación en límites (peor columna) | < 5 % | 0.8% (creditos_matriculados) | OK |
| Faltantes puntaje_saber11 | ≈ 5 % | 5.0% | OK |
| Faltantes horas_trabajo_semana | ≈ 3 % | 2.8% | OK |
| No trabaja (horas = 0) | ≈ 55 % | 56.3% | OK |
| Mujeres | ≈ 52 % | 50.1% | OK |
| Estratos 1–6 | 35/35/18/7/3/2 % | 35/35/18/8/3/2 | OK |
| Puntaje Saber 11: media / desv. | ≈ 250 / ≈ 45 | 251 / 44 | OK |
| Subgrupo en riesgo (P<0,5) | informativo | 288 estudiantes (9.6%) | OK |
| efectos_verdaderos.json: hash del modelo | = hash actual | coincide | OK |
| efectos_verdaderos.json: valores recalculados | diferencia < 1e-9 | 0.0e+00 | OK |

## Efectos verdaderos sobre P(permanece), en puntos porcentuales

| Intervención | Población | Subgrupo en riesgo | Afectados (pob.) | Efecto en afectados |
|---|---|---|---|---|
| asistencia_pct_mas_10_puntos | +2.1 | +6.0 | 3000 | +2.1 |
| horas_estudio_semana_mas_5_h | +4.1 | +12.3 | 2998 | +4.1 |
| tutorias_asistidas_mas_2 | +2.2 | +5.4 | 3000 | +2.2 |
| creditos_matriculados_de_21_a_16 | +0.2 | +0.4 | 56 | +9.7 |
| creditos_matriculados_bajar_a_16_los_que_tienen_mas | +0.8 | +2.3 | 1037 | +2.4 |
| apoyo_bienestar_0_a_1 | +3.2 | +6.8 | 2293 | +4.2 |
| apoyo_financiero_0_a_1 | +3.9 | +8.9 | 1906 | +6.2 |
| horas_trabajo_semana_menos_10_h | +2.9 | +10.3 | 1317 | +6.6 |
