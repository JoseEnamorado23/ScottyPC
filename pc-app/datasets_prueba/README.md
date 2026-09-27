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
- La CLI guarda aquí los archivos que genera (`_revision.json`, `_decisiones.json`,
  `_receta.json`, `_train.csv`, `_test.csv`, `_recomendacion.json`, `_pc.json` y la
  carpeta `_pc/`). Nunca sobrescribe un archivo existente: añade `_2`, `_3`, etc. Estos
  archivos están excluidos de git.

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
