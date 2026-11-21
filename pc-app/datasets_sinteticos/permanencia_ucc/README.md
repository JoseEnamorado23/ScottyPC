# permanencia_ucc — dataset sintético de permanencia estudiantil

> **Datos sintéticos generados con fines de validación y demostración. No representan estudiantes reales de ninguna institución.**

3000 estudiantes universitarios colombianos simulados a partir de un modelo causal **conocido** (el grafo verdadero está en
`salidas/`). Sirve para dos cosas: (1) validar Scotty PC contra una verdad conocida y (2) tener un modelo de demostración
con variables locales (promedio 0–5, Saber 11, estrato, créditos…).

## Contenido

| Archivo | Qué es |
|---|---|
| `generador.py` | Modelo causal verdadero, generación, do-operator y salidas. |
| `verificar_realismo.py` | Verifica las metas de realismo, dibuja `distribuciones.png` y comprueba que `efectos_verdaderos.json` corresponde a la versión actual del generador (hash). |
| `revisar_con_nucleo.py` | Carga el CSV y corre solo la revisión del núcleo (sin PC). |
| `comparar_con_verdad.py` | Compara una exportación de Scotty PC con la verdad (ver «Comparar con la verdad»). |
| `verificar_prescripcion_rapida.py` | Prescribe en lote con el núcleo sobre 800 filas y comprueba rejilla, límites y el comparador (ver «Verificación rápida sin la app»). |
| `probar_comparador.py` | Prueba el comparador con un PC falso (verdad menos 3 aristas, 1 invertida). |
| `generar_diccionario.py` | Genera `salidas/diccionario_portal.json`. |
| `salidas/permanencia_ucc.csv` | **El dataset** (coma, UTF-8, sin id ni `motivacion`). |
| `salidas/grafo_verdadero.csv` / `.png` | Aristas verdaderas entre variables observadas / dibujo por niveles. |
| `salidas/grafo_verdadero_con_latente.csv` | Igual, con la latente `motivacion`. |
| `salidas/ecuaciones.md` | Cada ecuación estructural con sus coeficientes y su ruido. |
| `salidas/efectos_verdaderos.json` | Efecto causal verdadero de cada acción sobre P(permanece) (do-operator) y hash del modelo. |
| `salidas/diccionario_portal.json` | Textos en español sencillo para estudiantes (objetivo y las 16 variables; `como_mejorar` en las 7 modificables). |
| `salidas/verificacion_rapida/` | `prescripciones.csv` (formato de la app), `comparacion.md` y entrada de esa verificación. |
| `salidas/prueba_comparador/` | Entrada y resultado de la prueba del comparador (PC falso). |
| `salidas/verificacion.md`, `distribuciones.png`, `revision_nucleo.json` | Metas de realismo, histogramas, hallazgos de la revisión. |

## Regenerar

```bash
python generador.py                       # semilla 2026, n = 3000 (los valores por defecto)
python generador.py --semilla 7 --n 5000  # otra muestra
python verificar_realismo.py              # tabla de verificación; falla si algo se sale de las metas
```

Con la misma semilla y `n` el CSV es idéntico. Las semillas 1–4 también cumplen todas las metas.

## Columnas

Todas numéricas; encabezados en `snake_case` sin tildes.

| Columna | Tipo | Valores / unidad | Qué representa |
|---|---|---|---|
| `estrato` | ordinal | 1–6 | Estrato socioeconómico (sesgado a 1–3). |
| `genero` | binaria | 0 hombre, 1 mujer | **Control**: no causa nada. |
| `edad_ingreso` | continua | años, 16–30 (1 decimal) | Edad al ingresar. |
| `primera_generacion` | binaria | 1 = primero de su familia en la universidad | |
| `vive_con_familia` | binaria | 0/1 | **Control**: no afecta la permanencia. |
| `puntaje_saber11` | continua (entero) | puntos, 0–500; ~5 % faltante | Puntaje Saber 11. |
| `horas_trabajo_semana` | continua (entero) | horas, 0–48; 0 = no trabaja (~55 %); ~3 % faltante | Horas de trabajo remunerado. |
| `asistencia_pct` | continua (entero) | %, 30–100 | Asistencia a clases en el semestre. |
| `horas_estudio_semana` | continua | horas, 0–30, a media hora | Estudio independiente. |
| `tutorias_asistidas` | ordinal (conteo) | 0–8 | Tutorías a las que asistió. |
| `creditos_matriculados` | ordinal | créditos, 8–22 | Carga académica del semestre. |
| `apoyo_bienestar` | binaria | 1 = usó acompañamiento psicosocial | |
| `apoyo_financiero` | binaria | 1 = beca o crédito institucional | |
| `promedio_semestre` | continua | nota 0,00–5,00 | Promedio del semestre. |
| `materias_reprobadas` | ordinal (conteo) | 0–6 | Materias reprobadas. |
| `permanece` | binaria, **objetivo** | 1 = se matricula el semestre siguiente | ~80 % son 1. |

La variable latente `motivacion` afecta a asistencia, horas de estudio, tutorías y promedio, y **no está en el CSV**:
es un confusor no observado a propósito.

## Guía para correrlo en Scotty PC

### Qué hace Scotty PC con cada tipo de variable (lea esto primero)

Verificado con el núcleo sobre este CSV (`verificar_prescripcion_rapida.py`, ver más abajo): ningún valor prescrito queda fuera de su
rejilla ni de sus límites.

| Tipo de variable | Cómo se prescribe | ¿Valores válidos? |
|---|---|---|
| **Binarias 0/1** (`apoyo_bienestar`, `apoyo_financiero`) | La preparación las marca `binaria` sola; la prescripción las enumera como **estados 0 y 1**. | **Sí**, sin hacer nada. |
| **Ordinales con pocos niveles (≤ 10)** (`estrato`, `tutorias_asistidas`, `materias_reprobadas`) | Una ordinal se prescribe como **estados discretos**; respeta `estados_permitidos`, `direccion` y `cambio_maximo`. | **Sí**, si la marca como ordinal (paso 1 abajo). |
| **Ordinales con más de 10 niveles** (`creditos_matriculados`: 15 niveles) | Se optimiza como continua y el resultado se **ajusta a la rejilla de sus niveles** (redondeo hacia la mejora, búsqueda local y recorte). | **Sí.** Si el objetivo solo se alcanzaría con un valor intermedio, el caso sale «Alcanzable solo con cambios intermedios». |
| **Enteras o continuas con `paso`** (`asistencia_pct`, `horas_estudio_semana`, `horas_trabajo_semana`) | Continuas con límites, cambio máximo y **paso**: solo se proponen múltiplos del paso. | **Sí.** El paso por defecto es 1 si la variable solo toma enteros; para `horas_estudio_semana` póngalo en 0,5. |

Cómo se escriben las restricciones de una ordinal: **siempre en valores originales**. Para `creditos_matriculados`, «mínimo 14» son 14
créditos y «cambio máximo 6» son 6 créditos (no la posición del nivel). Si las etiquetas de la ordinal no son números (p. ej. bajo,
medio, alto), los límites se cuentan en niveles desde 0. Las configuraciones guardadas con límites en posiciones se convierten solas al
abrirlas, y la pantalla avisa de lo que haya cambiado.

En el modelo causal solo hay dos tipos de mecanismo: binario y continuo. Una ordinal como hijo se modela como continua sobre su código;
solo la **prescripción** la discretiza. En PC (prueba de independencia), una ordinal con más de 10 niveles se trata como numérica.

### 1. Revisión y Decisiones

- Cargue `salidas/permanencia_ucc.csv`, objetivo `permanece`. La revisión da 10 hallazgos, ninguno bloqueante (ver `salidas/revision_nucleo.json`).
- Acciones sugeridas que conviene dejar: `valores_faltantes` de `puntaje_saber11` y `horas_trabajo_semana` → imputar (mediana, o
  multivariada si se quiere probar). `ceros_sospechosos:horas_trabajo_semana` → **conservar** (el 0 es «no trabaja», real).
  `desbalance_clases` es informativo (19,6 % vs umbral 20 %).
- **Binarias** (`genero`, `primera_generacion`, `vive_con_familia`, `apoyo_bienestar`, `apoyo_financiero`): no hay nada que marcar;
  la preparación las detecta como `binaria` sola. Compruébelo en la pantalla Preparación (tipo `binaria`).
- **Ordinales** (`estrato`, `tutorias_asistidas`, `materias_reprobadas`, `creditos_matriculados`): se marcan **desde la pantalla
  Decisiones, sin tocar JSON**.
  1. Los hallazgos `posible_variable_ordinal` de `estrato`, `tutorias_asistidas` y `materias_reprobadas` traen como acción sugerida
     `usar_orden_sugerido`: déjela, y ahora sí crea la codificación ordinal con el orden sugerido.
  2. Para cualquier otra columna entera (aquí, `creditos_matriculados`), use el selector **«Variables ordinales»** de la pantalla
     Decisiones, elija la columna y, si hace falta, ajuste su orden con el editor que aparece en «Codificaciones».
  3. Compruebe en la tarjeta «Codificaciones» que aparezcan, p. ej., `tutorias_asistidas: ordinal (0 < 1 < …)`, y en Preparación que las
     columnas figuren como `ordinal`.
  - Solo `tutorias_asistidas` y `creditos_matriculados` son modificables, así que solo ellas afectan a la prescripción. `estrato` y
    `materias_reprobadas` afectan a PC (con `chisq` una ordinal conserva sus niveles; una con más de 10 niveles pasa a numérica).
- **`creditos_matriculados`**: puede marcarla ordinal (15 niveles). Con eso la prescripción propone créditos reales (14, 15, …), no
  16,3, y los límites de la tabla de abajo se escriben en créditos.
- No excluya columnas: `genero` y `vive_con_familia` **deben quedarse**; son los controles para detectar falsos positivos.
- Prueba de independencia: la que recomiende la app. Con datos mixtos y faltantes imputados, `mv_fisherz`/`fisherz` o `chisq` son
  las candidatas; anote cuál usó (la comparación de Paso 5 lo agradece). Si la recomendación trae varios motivos, la pantalla los
  muestra todos.

### 2. Niveles temporales

| Nivel | Variables |
|---|---|
| 0 | `estrato`, `genero`, `edad_ingreso`, `primera_generacion`, `vive_con_familia`, `puntaje_saber11`, `horas_trabajo_semana` |
| 1 | `asistencia_pct`, `horas_estudio_semana`, `tutorias_asistidas`, `creditos_matriculados`, `apoyo_bienestar`, `apoyo_financiero` |
| 2 | `promedio_semestre`, `materias_reprobadas` |
| 3 | `permanece` |

`horas_trabajo_semana` está en el nivel 0 (es una característica previa al semestre) pero **también se marca modificable**: son
dos cosas independientes en la app (nivel = orden temporal; modificable = se puede prescribir).

### 3. Objetivo

`permanece`, clase positiva **1**, dirección **subir**. (La sugerencia automática de la app puede decir «bajar» si considera la 1
minoritaria; aquí la 1 es la mayoritaria, 80 %, y es lo deseable.)

### 4. Variables modificables y restricciones

Todo en **valores originales** (en las ordinales también: créditos, no posiciones de nivel). La columna «Paso» es la del campo
**Paso** de la pantalla de configuración de la prescripción; las que ya vienen con 1 (enteras y ordinales) no hay que tocarlas.

| Variable | Dirección | Cambio máx. | Límites / estados | Paso | Costo | Nota |
|---|---|---|---|---|---|---|
| `asistencia_pct` | subir | 20 puntos | máx. 100 | 1 (por defecto) | 1 | Continua entera. |
| `horas_estudio_semana` | subir | 8 h | máx. 30 | **0,5** (escríbalo) | 1 | Continua; media hora. |
| `tutorias_asistidas` | subir | 4 | niveles 0–7 | 1 nivel (por defecto) | 1 | Ordinal (≤ 10 niveles: estados discretos). |
| `creditos_matriculados` | bajar | **6 créditos** | **mínimo 14 créditos** (no 10) | 1 nivel (por defecto) | 1 | Ordinal de 15 niveles: rejilla de créditos. |
| `apoyo_bienestar` | subir | — | estados 0, 1 | — | 1 | Binaria: 0→1. |
| `apoyo_financiero` | subir | — | estados 0, 1 | — | **3** (alto) | Binaria: 0→1. |
| `horas_trabajo_semana` | bajar | 10 h | mínimo 0 | 1 (por defecto) | 1 | Continua entera. |

Cambios respecto a lo propuesto, y por qué (calculado con el generador verdadero, do-operator):

- **Créditos: mínimo 14, no 10.** El efecto verdadero de los créditos es en U invertida con óptimo ≈ 15–16. Bajar de 12 a 10
  créditos **reduce** P(permanece) en 6 pp; de 14 a 12, −2,4 pp; solo ayuda bajar desde 18 o más (+2,0 pp de 18 a 16, +7,6 de 22 a 20).
  Con mínimo 10 y cambio 6, la acción aplicada a todo el subgrupo en riesgo da **−6,7 pp**; con mínimo 14, **+2,1 pp**.
  El modelo de Scotty PC debería aprender la U con splines; si propone bajar créditos a quien tiene 14 o menos, es una señal
  de que no la aprendió.
- **Costo del apoyo financiero = 3.** En el problema de prescripción, cambiar de estado cuesta su `costo`, mientras que mover una
  continua a lo largo de todo su rango cuesta 1 (`prescripcion/problema.py`). 3 hace que la beca sea el último recurso.
- Los demás cambios máximos se mantienen: son coherentes con los rangos observados (asistencia mediana ~85 %, estudio mediana ~6 h).

Efecto verdadero de cada acción sola, con las restricciones de la tabla, sobre P(permanece) del subgrupo en riesgo (P < 0,5;
288 estudiantes): estudio +8 h → +16,6 pp; tutorías +4 → +10,8; trabajo −10 h → +10,3; asistencia +20 → +9,9; apoyo financiero → +8,9;
apoyo bienestar → +6,8; créditos (mínimo 14) → +2,1. Los efectos de las demás magnitudes (+10 puntos de asistencia, +5 h de estudio,
+2 tutorías, etc.) están en `salidas/efectos_verdaderos.json`.

### 5. Meta del plan

**P(permanece) ≥ 0,80.** La media poblacional es 0,81; el subgrupo en riesgo parte de una P media de 0,31, así que 0,80 es una meta
exigente para ellos. Según la verdad del generador, ninguna acción sola lleva a nadie del subgrupo en riesgo a 0,80 (con +5 h de estudio, 0 %),
pero **todas las acciones al máximo permitido de la tabla** lo logran para el 80 % del subgrupo (y el 96 % llega a 0,65). Es el
techo realista: si la app promete llegar a 0,80 en casi todos los casos en riesgo con una o dos acciones, desconfíe. Compárela con el
umbral de decisión que calcula la app.

### 6. Qué esperar de PC

Causas verdaderas directas del objetivo: `promedio_semestre`, `materias_reprobadas`, `apoyo_financiero`, `apoyo_bienestar`,
`estrato` y `horas_trabajo_semana`. Indirectas: `puntaje_saber11`, `asistencia_pct`, `horas_estudio_semana`, `tutorias_asistidas`,
`creditos_matriculados`, `primera_generacion`, `edad_ingreso`. No son causa de nada del objetivo: `genero` (aislada) y
`vive_con_familia` (solo se relaciona con `edad_ingreso`).

Probablemente encuentre (efectos grandes, relaciones sin ambigüedad): `estrato`→`puntaje_saber11`, `estrato`→`primera_generacion`,
`puntaje_saber11`→`promedio_semestre`, `promedio_semestre`→`materias_reprobadas`, `promedio_semestre`→`permanece`,
`horas_trabajo_semana`→`asistencia_pct`.

Probablemente falle o confunda:

- **Aristas espurias por la latente `motivacion`** entre `asistencia_pct`, `horas_estudio_semana`, `tutorias_asistidas` y
  `promedio_semestre`: PC asume que no hay confusores ocultos y suele conectar a los hijos de una causa no observada
  (p. ej. `asistencia_pct`–`horas_estudio_semana`, `horas_estudio_semana`–`tutorias_asistidas`). Esas aristas no existen en el grafo verdadero.
- **Efectos débiles que pueden perderse:** `tutorias_asistidas`→`promedio_semestre` (0,05 puntos por tutoría), `apoyo_bienestar`→`permanece`,
  `estrato`→`permanece` (logarítmico) y `primera_generacion`→`tutorias_asistidas`.
- **Orientación** entre variables del mismo nivel (p. ej. dentro del nivel 1): los niveles no la fijan.
- Aristas no lineales (U invertida de créditos, saturación de asistencia): con `chisq` o con pruebas lineales pueden detectarse peor.

Esto es una expectativa razonada, no una medición: no corrí PC. Para medirlo, usa el comparador de la sección siguiente.

## 7. Comparar con la verdad

Tras exportar la corrida desde la app (carpeta con `aristas.csv`, `resultado.json` y, si prescribiste, `prescripciones.csv`):

```
python comparar_con_verdad.py RUTA_A_LA_EXPORTACION            # escribe comparacion.md dentro de esa carpeta
python comparar_con_verdad.py RUTA --umbral 0.6                # cuenta solo aristas con frecuencia >= 0.6
python comparar_con_verdad.py RUTA --dataset mi_train.csv      # si PC corrió sobre otro CSV (train/test)
```

Informa: precisión, recall y F1 del esqueleto (sin dirección); exactitud de orientación; SHD; aristas faltantes, sobrantes e
invertidas (marcando las explicables por la latente `motivacion` o por un camino verdadero indirecto); si `genero` o
`vive_con_familia` quedaron conectadas a `permanece`; y, con `prescripciones.csv`, el error entre la P(permanece) prometida y la
verdadera (do-operator con el ruido de cada estudiante) y el porcentaje que realmente llega a la meta, con los valores tal cual los
propone el optimizador y redondeados a estados válidos.

Verificado con el `prescripciones.csv` que escribe el núcleo (el mismo formato que exporta la app): `caso` es la posición de la fila en el CSV
original aunque se entrene sobre un subconjunto, así que no hace falta `--dataset` cuando se carga el CSV completo (`verificar_prescripcion_rapida.py`
lo comprueba: 0 casos ignorados). Supuestos: la columna `caso` es la fila (desde 0) de `permanencia_ucc.csv` (o del CSV pasado con `--dataset`); `antes`/`despues`/`deseado` son
probabilidades; las acciones se leen de las columnas `<variable> antes` / `<variable> despues`. Si la app numera los casos de otra
forma, el comparador lo dirá en «casos ignorados».

`python probar_comparador.py` lo valida con un PC falso (verdad menos 3 aristas, 1 invertida, 1 espuria por la latente y 1 control
conectado; prescripciones con +10 pp de sobrepromesa) y sale con error si no detecta exactamente lo sembrado.

### Verificación rápida sin la app

`python verificar_prescripcion_rapida.py` (requiere `pcapp_nucleo`; tarda unos 6 minutos) toma 800 filas, usa el grafo verdadero como
resultado de PC, marca las 4 ordinales, aplica la tabla de restricciones de arriba y prescribe en lote sobre los casos de test que no
cumplen la meta. Comprueba que ningún valor prescrito salga de su rejilla o de sus límites y que `comparar_con_verdad.py` lea el
`prescripciones.csv` sin «casos ignorados». Escribe `salidas/verificacion_rapida/`.

## 8. Diccionario para el portal

`salidas/diccionario_portal.json` (se regenera con `python generar_diccionario.py`) tiene el texto del objetivo («seguir estudiando el
próximo semestre») y, por variable, `etiqueta`, `descripcion`, `unidad`, `valores`, `modificable` y, solo en las 7 modificables, `como_mejorar`.
