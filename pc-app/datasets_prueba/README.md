# Datasets de prueba

Datasets para comprobar el comportamiento del núcleo (`pcapp_nucleo`) con datos reales y
sintéticos. No forman parte del código del paquete.

- La prueba `test_datasets_reales_se_revisan_sin_errores` carga y revisa automáticamente
  todos los CSV y XLSX de esta carpeta (excepto los `*_train.csv` / `*_test.csv` generados
  por `preparar`). Comprueba que no fallen, que el DataFrame no se modifique y que el
  informe se pueda serializar a JSON.
- `nucleo/tests/test_aceptacion_datos_reales.py` comprueba los criterios de aceptación de
  cada dataset real (se omite si falta el archivo).
- `nucleo/tests/test_aceptacion_pc.py` ejecuta PC con bootstrap (100 corridas) en vino
  tinto, diabetes y salud fetal y comprueba sus causas directas. Es lento: se ejecuta con
  `pytest -m lento -s` desde `nucleo/`.
- `nucleo/tests/test_aceptacion_modelo_causal.py` ejecuta PC (100 corridas) con las
  configuraciones de `configuraciones/` y construye el modelo causal de diabetes, vino tinto
  y salud fetal (criterios en *Configuraciones de aceptación del modelo causal*). También es
  lenta (`pytest -m lento -s`).
- La CLI guarda aquí los archivos que genera (`_revision.json`, `_decisiones.json`,
  `_receta.json`, `_train.csv`, `_test.csv`, `_recomendacion.json`, `_pc.json` y la
  carpeta `_pc/`). Nunca sobrescribe un archivo existente: añade `_2`, `_3`, etc. Estos
  archivos están excluidos de git.
- `nucleo/tests/test_reagregacion.py` usa, si existen, `diabetes_pc/resultado.json` (un
  resultado de PC de la terminal anterior a las cuentas del bootstrap) y `diabetes_train.csv`
  para comprobar que un resultado migrado, reagregado con su umbral original, reproduce el
  original. Como están excluidos de git, la prueba se omite si faltan.

## Ejecución

Desde la raíz del repositorio (`pc-app/`), con el paquete instalado:

```bash
python -m pcapp_nucleo revisar datasets_prueba/dataset_prueba.csv --objetivo objetivo
python -m pcapp_nucleo plantilla datasets_prueba/diabetes.csv --objetivo Outcome
python -m pcapp_nucleo preparar datasets_prueba/diabetes.csv --objetivo Outcome --decisiones datasets_prueba/diabetes_decisiones.json
python -m pcapp_nucleo sugerir-prueba datasets_prueba/diabetes_receta.json
```

Para XLSX con varias hojas, indique la hoja con `--hoja <nombre>`.

## Dataset sintético

| Archivo | Objetivo | Detectores que ejercita |
|---|---|---|
| `dataset_prueba.csv` | `objetivo` (binario, ≈11 % «si») | Filas duplicadas, faltantes reales y centinela (`?`), posible identificador (`id`), texto libre (`observacion`), fecha como texto (`fecha`), categórica y ordinal (`nivel`), variable derivada (`ancho = maximo - minimo`), correlación casi perfecta / transformación lineal (`altura`, `altura_m`), distribución del objetivo y desbalance. También produce una advertencia de ceros sospechosos en `minimo` (tiene ceros legítimos entre 40 valores distintos). |

Se genera con `construir_dataset_prueba()` de `nucleo/tests/datos_sinteticos.py` (semilla
fija). La prueba end-to-end de la CLI usa la misma función.

## Datasets reales

| Archivo | Objetivo sugerido | Qué permite comprobar |
|---|---|---|
| `Dengue Dataset 2023-2025.xlsx` | `Outcome` (multiclase) | Fecha `dd.mm.yy` en `Date` (ofrece división temporal), posible mezcla de unidades en `Temp` (°C y °F), binaria derivada real (`Platelet_Risk = 0 si Platelete >= 100000`), recodificación uno a uno y correlación casi perfecta. |
| `MASTER_CHART_F1000Research.xlsx` (dengue pediátrico) | `GROUPS: DENGUE FEVER OR COMPLICATED DENGUE ` (binario) | Faltantes de `FERRITIN` que dependen del objetivo (44 % en una clase, 10 % en la otra), grupo redundante `HB`–`PCV`, tamaño efectivo insuficiente (63 casos para 24 variables), asimetría fuerte y nombres de columna con espacios. |
| `fetal_health.csv` | `fetal_health` (multiclase 1/2/3) | Relaciones en U con el objetivo (p. ej. `mean_value_of_short_term_variability`) → se recomienda `chisq`; agrupación de clases `{1: 0, 2: 1, 3: 1}`; duplicados, ceros sospechosos y variable derivada. |
| `winequality-red.csv` | `quality` (multiclase) | Separador `;`, filas duplicadas; relaciones monótonas → se recomienda `fisherz`. |
| `winequality-white.csv` | `quality` (multiclase) | Relaciones no monótonas reales (`citric acid`, `residual sugar`, `free sulfur dioxide`) → se recomienda `chisq`. |
| `xAPI-Edu-Data.csv` | `Class` (multiclase: L/M/H) | Muchas variables categóricas de texto (one-hot), agrupación `{"L": 0, "M": 1, "H": 1}` y ceros sospechosos en conteos. |
| `diabetes.csv` (Pima Indians, fuente: plotly/datasets) | `Outcome` (binario) | Ceros sospechosos en `Glucose`, `BloodPressure`, `SkinThickness`, `Insulin` y `BMI` (son faltantes). Marcados como faltantes sin imputar → `mv_fisherz`; imputados → `fisherz`. |
| `NSW_AFDC_CS.csv` (NSW/Lalonde, programa de empleo) | `nodegree` (binario) para el flujo completo | `re78` y `treated` tienen faltantes, por lo que la validación los rechaza como objetivo (código 2). Muchas variables binarias y faltantes. Con `nodegree` se recomienda `chisq` (`moa` y `redif` no monótonas). |

Notas:

- En `MASTER_CHART_F1000Research.xlsx` el nombre del objetivo termina en un espacio: debe
  escribirse entre comillas e incluir ese espacio:
  `--objetivo "GROUPS: DENGUE FEVER OR COMPLICATED DENGUE "`.
- `NSW_AFDC_CS.csv` es un dataset público del programa de empleo National Supported
  Work (NSW), estudiado por LaLonde (1986); por sus columnas (`afdc75`, `nchildren75`,
  `sample_lalonde`, `sample_dw`...) corresponde a la muestra de beneficiarias de AFDC.
  Está incluido en el repositorio para que las pruebas que lo usan funcionen en
  cualquier computador.

## Configuraciones de aceptación del modelo causal

`configuraciones/<nombre>.json` guarda todo lo necesario para reproducir el análisis sin
editar nada a mano: `dataset`, `hoja`, `objetivo`, las **decisiones completas** (la plantilla
del revisor con los ajustes indicados) y la **configuración de PC** (prueba, niveles,
umbral y orientaciones manuales con su justificación; el resto toma los valores por
defecto). A diferencia de `*_decisiones.json` y `*_pc.json` (salidas de la CLI, excluidas de
git), estos archivos sí se versionan.

| Archivo | Dataset y objetivo | Decisiones | PC | Criterios que comprueba |
|---|---|---|---|---|
| `diabetes.json` | `diabetes.csv`, `Outcome` | Ceros como faltantes sin imputar en Glucose, BloodPressure, SkinThickness, Insulin y BMI | `mv_fisherz`, niveles de la fase 6 (edad, embarazos y antecedentes → medidas → laboratorio → diagnóstico) y dos orientaciones manuales: Age → Pregnancies y BMI → SkinThickness | Padres del objetivo: Glucose, BMI y Pregnancies. Intervenir Age cambia la probabilidad solo a través de sus hijos (Glucose y Pregnancies), nunca directamente. Intervenir BloodPressure no cambia nada y advierte. Sin las orientaciones manuales, queda bloqueado con «Oriente la arista … en Resultados». |
| `vino_tinto.json` | `winequality-red.csv`, `quality` agrupada (6–8 → 1, 3–5 → 0) | Eliminar duplicados | `fisherz`; niveles: composición (con el SO₂ libre) → SO₂ total (incluye el libre) → density y pH → calidad; tres orientaciones manuales dentro de la composición | Padres del objetivo: volatile acidity, total sulfur dioxide, sulphates y alcohol. Reducir free sulfur dioxide baja total sulfur dioxide y sube la probabilidad de buena calidad (traza visible). |
| `salud_fetal.json` | `fetal_health.csv`, `fetal_health` agrupada (1 → 0; 2, 3 → 1) | Plantilla (excluye `histogram_max`, derivada) | `chisq`, `max_k` 3, umbral 0,7; niveles: actividad (contracciones, movimientos) → eventos de la FCF (línea base, aceleraciones, deceleraciones) → variabilidad → rasgos del histograma → objetivo; dos orientaciones manuales | No se impone monotonía en `mean_value_of_short_term_variability` (relación en U según la recomendación) y la comparación con el modelo de referencia muestra el costo de la parsimonia. |

Notas sobre por qué difieren de la configuración de la fase 6:

- **Diabetes:** PC deja sin orientar Pregnancies — Age y SkinThickness — BMI (mismo nivel), lo
  que bloquea el modelo. Con Age → Pregnancies, la edad también influye a través de los
  embarazos, así que el criterio es «solo a través de sus hijos», no «solo por Glucose».
- **Vino tinto:** con toda la composición en un nivel, PC orienta total → free (frecuencia
  1,0) y el SO₂ libre no es ancestro de la calidad; una orientación manual no puede invertir
  una arista ya orientada. Con el SO₂ libre en un nivel anterior sale free → total.
- **Salud fetal:** con todas las variables en un nivel, el subgrafo del objetivo tiene más de
  20 ciclos. Con niveles por dominio queda un ciclo entre histogram_mean, histogram_variance y
  histogram_median; el umbral 0,7 quita su arista más débil (histogram_mean →
  histogram_variance, 65 % de las corridas).

## Configuraciones de aceptación de la prescripción

La sección `prescripcion` de cada `configuraciones/<nombre>.json` indica las modificables, la
dirección del objetivo (la probabilidad deseada es el umbral de decisión ± 0,1) y los cambios a
las restricciones por defecto. La usa `nucleo/tests/test_aceptacion_prescripcion.py` (lenta),
que calibra μ con train y prescribe los casos de test que no cumplen el objetivo.

| Archivo | Modificables | Objetivo | Criterios |
|---|---|---|---|
| `diabetes.json` | BMI, Glucose | Bajar la probabilidad de diabetes | Solo se cambian BMI y Glucose (nunca Age, Pregnancies ni BloodPressure) y dentro del cambio máximo; la mayoría de los casos en riesgo alcanza el objetivo; gradiente proximal y genético tienen un éxito similar (McNemar). Sin modificables, queda bloqueado con «Con estos datos no hay variables prescriptivas». |
| `vino_tinto.json` | alcohol, sulphates, volatile acidity, free sulfur dioxide, citric acid, fixed acidity, residual sugar | Subir la probabilidad de buena calidad | fixed acidity (y citric acid) no tienen camino al objetivo: se detectan, se ignoran y se advierte. Reducir el SO₂ libre aparece con su efecto a través del SO₂ total en la traza. |
| `salud_fetal.json` | uterine_contractions, solo bajar | Bajar la probabilidad de un estado sospechoso o patológico | El objetivo no es alcanzable (haría falta aumentar las contracciones): se informa la restricción de dirección activa y nunca se prescribe aumentarlas. |

