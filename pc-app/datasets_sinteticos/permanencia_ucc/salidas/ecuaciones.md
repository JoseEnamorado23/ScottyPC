# Ecuaciones estructurales del generador (verdad conocida)

> Datos sintéticos generados con fines de validación y demostración. No representan estudiantes reales de ninguna institución.

Generado con `generador.py` (n = 3000, semilla = 2026). Cada variable se calcula a partir de sus padres más un ruido
propio e independiente. `σ(x) = 1/(1+e^-x)`. «Bernoulli(p)» significa que la variable vale 1 con probabilidad p (se
sortea con un uniforme propio). `ε ~ N(0,1)` es un ruido normal estándar distinto en cada ecuación.
`motivacion ~ N(0,1)` es la variable **latente**: afecta a varias variables y **no** está en el CSV.

## Nivel 0 — características al ingresar (no modificables)

- **estrato**: categórica con probabilidades 0.35, 0.35, 0.18, 0.07, 0.03, 0.02 para los estratos 1 a 6. Sin padres.
- **genero**: Bernoulli(0.52) (1 = mujer). Sin padres y **sin efecto sobre nada**: variable de control para falsos positivos.
- **edad_ingreso**: 16 + Gamma(forma=2.2, escala=1.1), redondeada a 0,1 y limitada a 16–30. Sesgada a 17–19. Sin padres.
- **primera_generacion** ~ Bernoulli(σ(0.5 -0.44·(estrato−1))). A mayor estrato, menos probable ser primera generación.
- **vive_con_familia** ~ Bernoulli(σ(1.6 -0.3·(edad_ingreso−18))). **Sin efecto sobre el objetivo**: control.
- **puntaje_saber11** = redondeo(232 +12·estrato -14·primera_generacion + 41·ε), limitado a 0–500. Ruido normal.
- **horas_trabajo_semana**: primero «¿trabaja?» ~ Bernoulli(σ(-0.2 -0.3·(estrato−2) +0.22·(edad_ingreso−18,4))).
  Si trabaja: horas = redondeo(4 + exp(2.6 -0.1·(estrato−2) +0.04·(edad_ingreso−18,4) + 0.45·ε)), tope 48. Si no, 0. Ruido lognormal.

## Variable latente (no va en el CSV)

- **motivacion** ~ N(0, 1). Es un confusor no observado a propósito: afecta a asistencia, horas de estudio, tutorías y promedio.

## Nivel 1 — comportamientos y apoyos del semestre (modificables)

- **asistencia_pct** = redondeo(30 + 70·σ(z)), con z = 1.5 -0.022·horas_trabajo +0.4·motivacion + 0.55·ε. Forma sigmoide: rango 30–100 sin cortes bruscos. Ruido normal en el índice.
- **horas_estudio_semana** = redondeo a 0,5 de exp(1.85 -0.01·horas_trabajo +0.28·motivacion -0.2·primera_generacion + 0.45·ε), tope 30. Ruido lognormal.
- **tutorias_asistidas** ~ Poisson(λ), λ = exp(-0.15 +0.3·primera_generacion +0.18·motivacion), tope 8. Efectos pequeños.
- **creditos_matriculados** = redondeo(16.2 -0.07·horas_trabajo + 2.2·ε), limitado a 8–22. Ruido normal.
- **apoyo_bienestar** ~ Bernoulli(σ(-1.7 +0.75·primera_generacion)).
- **apoyo_financiero** ~ Bernoulli(σ(-0.55 -0.4·(estrato−2) +0.012·(puntaje_saber11−250))).

## Nivel 2 — resultados académicos

- **promedio_semestre** = suavizado(bruto), con
  bruto = 3.8 +0.0085·(saber11−250) +1.8·[g(asistencia)−g(85)] +0.3·[ln(1+horas_estudio)−ln(8)] +0.05·(tutorias−1) -0.012·(creditos−15.5)² -0.008·horas_trabajo +0.18·motivacion + 0.34·ε.
  - `g(a) = 1 − exp(−(a−30)/30)`: **saturante**, sube rápido con asistencia baja y casi nada por encima de ~85 %.
  - `ln(1+horas_estudio)`: **rendimientos decrecientes**.
  - `(creditos−15.5)²` con coeficiente negativo: **U invertida**, óptimo ≈ 15–16 créditos.
  - «suavizado» comprime con tanh por encima de 4,3 y por debajo de 0,8, para que no se acumulen notas en 0 ni en 5. Se redondea a 2 decimales (rango 0–5).
- **materias_reprobadas** ~ Poisson(λ), λ = exp(-1.1 -0.85·(promedio−3,5) +0.07·(creditos−15,5)), tope 6. Es un conteo ruidoso, no una función determinista del promedio.

## Nivel 3 — objetivo

- **permanece** ~ Bernoulli(σ(η)), con
  η = 1.7 +1.6·(promedio−3,5) -0.7·máx(0, 3,0−promedio) -0.3·reprobadas -0.04·reprobadas² +0.55·apoyo_financiero +0.4·apoyo_bienestar +0.28·ln(estrato) -0.01·horas_trabajo -0.0004·horas_trabajo² + 0.3·ε.
  Términos no lineales: quiebre en el promedio (más pendiente bajo 3,0), reprobadas y horas de trabajo cuadráticas, estrato logarítmico, más un ruido normal en el logit. No hay umbral exacto.

## Faltantes (se aplican después de generar, solo en el CSV)

- **puntaje_saber11**: 5% al azar (MCAR).
- **horas_trabajo_semana**: ≈3 %, con probabilidad σ(-3.6 +0.15·(edad_ingreso−18,4) -0.04·(asistencia_pct−85)).
  Es **MAR**: depende de columnas observadas (edad y asistencia), que son las que se asocian con trabajar muchas horas; no depende del propio valor faltante.
- Ninguna otra columna tiene faltantes.

## Efectos verdaderos

Ver `efectos_verdaderos.json`: se calculan con el operador do sobre estas mismas ecuaciones (mismo ruido, descendientes regenerados), sin faltantes.
