# pc-app

Aplicación de escritorio para investigación sobre modelos prescriptivos.

## Objetivo del proyecto

El paquete `nucleo` valida, revisa y prepara datasets antes del descubrimiento causal.
Comprueba que el dataset cumple las condiciones mínimas, perfila cada columna, detecta
problemas de calidad y relaciones sospechosas, aplica las decisiones de preparación del
usuario de forma reproducible y recomienda la prueba de independencia para PC.

**El revisor solo informa y sugiere acciones: nunca modifica, corrige ni elimina datos.**
Las transformaciones ocurren únicamente en la preparación, según las decisiones que el
usuario revisa y confirma.

La ejecución del algoritmo PC y las demás capas de la aplicación **todavía están
pendientes** (causal-learn solo se usa, por ahora, para estimar el tiempo de PC).

## Arquitectura actual

```
pc-app/
├── nucleo/            Paquete Python del núcleo (funcional)
│   ├── pyproject.toml
│   ├── src/nucleo/
│   └── tests/
├── sidecar/           Vacío: futuro servidor local FastAPI (sin implementar)
├── app/               Vacío: futuro frontend Tauri v2 + React (sin implementar)
└── datasets_prueba/   Datasets reales y sintéticos para pruebas
```

| Componente     | Tecnología prevista                     | Estado                    |
|----------------|-----------------------------------------|---------------------------|
| Núcleo         | Paquete Python independiente (`nucleo`) | Revisión, preparación y selección de prueba |
| Sidecar        | FastAPI local en Python                 | Pendiente                 |
| Frontend       | Tauri v2 + React + Vite + TypeScript    | Pendiente                 |
| Almacenamiento | SQLite + archivos locales               | Pendiente                 |

El núcleo no depende de ningún componente de presentación.

### Módulos de `nucleo`

| Módulo | Responsabilidad |
|---|---|
| `carga.py` | Lectura de CSV (detecta separador y codificación) y XLSX (selección de hoja). |
| `validacion.py` | Validación estructural: encabezados, dimensiones y variable objetivo. |
| `fechas.py` | Interpretación de fechas escritas como texto (formatos con `/`, `-` y `.`). |
| `perfilado.py` | Perfil de cada columna: tipo preliminar, faltantes, valores únicos, mínimo y máximo. |
| `detectores.py` | Detectores básicos por columna y del objetivo. |
| `detectores_objetivo.py` | Detectores que usan los datos y el objetivo: faltantes dependientes y tamaño efectivo. |
| `detectores_relaciones.py` | Relaciones entre columnas, grupos redundantes y mezclas de unidades. |
| `revision.py` | Orquesta perfilado y detectores y produce el `InformeRevision`. |
| `analisis.py` | Flujo validación + revisión. |
| `plantilla.py` | Decisiones sugeridas a partir del informe de revisión. |
| `preparacion.py` | Decisiones del usuario, preparación, receta reproducible y `aplicar_receta`. |
| `seleccion_prueba.py` | Diagnósticos (faltantes, categóricas, no linealidad) y prueba sugerida para PC. |
| `cli.py`, `cli_preparacion.py`, `cli_comun.py` | Interfaz de línea de comandos (`python -m nucleo`). |
| `modelos.py`, `configuracion.py`, `utilidades.py` | Dataclasses de resultados, umbrales centralizados y serialización a JSON. |

## Flujo

```
archivo → carga → validación ─┬─ errores bloqueantes → se informan y se detiene
                              └─ válido → revisión (perfil + detectores) → InformeRevision
                                  → plantilla de decisiones → el usuario revisa y edita
                                  → preparación → train / test + receta
                                  → selección de la prueba de independencia
```

## Contrato del núcleo

> Las funciones de análisis y preparación no modifican el DataFrame recibido.

| Función | Entrada | Salida | Responsabilidad |
|---|---|---|---|
| `carga.cargar_dataset(ruta, hoja=None)` | Ruta CSV/XLSX | `pd.DataFrame` | Leer el archivo. Lanza `ErrorCarga` si no puede. |
| `validacion.validar_dataset(df, objetivo)` | DataFrame y objetivo | `ResultadoValidacion` | Condiciones mínimas: `valido` solo si no hay errores. |
| `revision.revisar_dataset(df, objetivo)` | DataFrame y objetivo | `InformeRevision` | Resumen, perfiles y hallazgos (cada uno con un `identificador` único). |
| `analisis.analizar_dataset(df, objetivo)` | DataFrame y objetivo | `ResultadoAnalisis` | Valida y solo revisa si no hay errores bloqueantes. |
| `plantilla.generar_plantilla(informe)` | `InformeRevision` | `DecisionesUsuario` | Acción sugerida por hallazgo, con `requiere_confirmacion`. |
| `preparacion.preparar(df, objetivo, decisiones)` | DataFrame, objetivo, decisiones | `DatosPreparados` | Aplica las decisiones y registra la `Receta`. Lanza `ErrorPreparacion`. |
| `preparacion.aplicar_receta(df, receta)` | DataFrame original y receta | `DatosPreparados` | Reproduce exactamente train y test sin volver a aprender nada. |
| `seleccion_prueba.recomendar_prueba(datos)` | `DatosPreparados` | `RecomendacionPrueba` | Prueba sugerida, motivo, evidencia, alternativas y tiempo estimado. Usa solo train. |

Todos los umbrales están en `ConfiguracionValidacion` (`configuracion.py`).

## Detectores

| Detector | Tipo de hallazgo | Descripción |
|---|---|---|
| Duplicados | `filas_duplicadas` | Filas exactamente repetidas. |
| Faltantes | `valores_faltantes`, `alta_proporcion_faltantes` | Faltantes reales y textos centinela (`NA`, `?`, `-`); alta proporción si supera el 40 %. |
| Ceros sospechosos | `ceros_sospechosos` | Posibles faltantes codificados como cero en variables continuas. |
| Constantes | `constante` | Columnas sin variación. |
| Casi constantes | `casi_constante` | Columnas donde un valor supera el 99 %. |
| IDs | `posible_identificador` | Posibles identificadores (enteros consecutivos, nombres sugerentes, texto único por fila). |
| Texto libre | `texto_libre` | Texto no estructurado (largo, varias palabras, muchos valores distintos). |
| Fechas | `posible_fecha` | Tipo fecha o texto con `/`, `-` o `.`, año de 2 o 4 dígitos, día o mes primero; al menos el 90 % con un mismo formato. |
| Categóricas | `variable_categorica`, `posible_variable_ordinal` | Variables categóricas y posible orden natural. |
| Asimetría | `asimetria_fuerte` | Variables positivas muy asimétricas (se sugiere logaritmo). |
| Distribución del objetivo | `distribucion_objetivo` | Conteo y porcentaje por clase. |
| Desbalance | `desbalance_clases` | Clase minoritaria por debajo del 20 % (objetivo binario). |
| Faltantes dependientes del objetivo | `faltantes_dependientes_objetivo` | El % de faltantes cambia con el objetivo (chi-cuadrado/Fisher o Mann-Whitney). Severidad alta. |
| Tamaño efectivo | `tamano_efectivo_insuficiente` | Clase minoritaria con menos de 50 casos o de 10 por variable candidata. |
| Grupos redundantes | `grupo_redundante` | Variables con \|ρ de Spearman\| >= 0.8 entre sí; PC tiende a conservar solo una. |
| Copias | `columnas_redundantes` | Columnas idénticas. |
| Recodificaciones | `recodificacion_uno_a_uno` | Correspondencias uno a uno entre columnas. |
| Derivadas | `columna_derivada` | Relaciones de suma o resta (p. ej. `ancho = maximo - minimo`). |
| Binarias derivadas | `binaria_derivada` | Binarias que parecen resultar de un umbral sobre una variable numérica. |
| Correlación | `correlacion_casi_perfecta` | \|r\| > 0.99, incluidas transformaciones lineales exactas. |
| Unidades | `posible_mezcla_unidades` | Dos grupos de valores claramente separados (posibles escalas distintas). |

## Preparación

Las decisiones (`DecisionesUsuario`, editables como JSON) cubren: eliminar duplicados,
excluir columnas, tratamiento de faltantes por columna (eliminar filas, mediana,
imputación multivariada, indicador de "dato medido", ceros como faltantes), codificación
de categóricas (binaria, ordinal, one-hot o agrupación de clases), conversiones de
unidades (`si columna > umbral: (x − restar) × multiplicar`), logaritmos y la separación.

Orden de aplicación, para no filtrar información del test:

1. **Antes de separar** (nada aprende de la distribución): duplicados, exclusiones,
   centinelas → faltantes, conversiones de unidades, ceros → faltantes, indicadores de
   dato medido, logaritmos, codificaciones y eliminación de filas con faltantes.
2. **Separación**: estratificada (test 0.3, semilla 42 por defecto) o temporal por una
   columna de fecha (corte explícito o el primer 70 % cronológico). La fecha no se usa
   después como variable.
3. **Después de separar**, ajustado solo con train y aplicado a ambos: imputación por
   mediana, imputación multivariada (regresión lineal iterativa propia, 10 rondas) y
   normalización min-max.

La receta JSON guarda todas las decisiones, los índices de train y test, la semilla, los
parámetros aprendidos (medianas, mínimos, máximos, coeficientes del imputador) y el hash
SHA-256 del archivo original.

## Selección de la prueba de independencia

Con el conjunto de entrenamiento: si quedan faltantes → `mv_fisherz`; si más del 50 % de
las variables son categóricas o binarias → `chisq`; si alguna variable tiene una relación
no monótona con el objetivo → `chisq` sobre quintiles; en otro caso → `fisherz`.

Una variable es "no monótona" si la dependencia por sextiles es significativa (p < 0.01)
y la curva del objetivo por sextil sube y baja con tramos de al menos 0.3 desviaciones
estándar del objetivo, o si la correlación de Spearman es débil (|ρ| < 0.1) con una
dependencia de ese tamaño. El tiempo se estima con 2 ejecuciones reales de PC
(causal-learn) sobre el 80 % de train; si `chisq` supera unos 10 minutos para 100 corridas
de bootstrap, se sugiere `max_k = 3` y se explica su costo. La recomendación es solo una
sugerencia.

## Uso desde la terminal

```bash
python -m nucleo revisar <archivo> --objetivo <columna> [--hoja <nombre>]
python -m nucleo plantilla <archivo> --objetivo <columna> [--hoja <nombre>]
python -m nucleo preparar <archivo> --objetivo <columna> --decisiones <json>
    [--hoja <nombre>] [--test 0.3] [--semilla 42] [--fecha <columna> [--corte AAAA-MM-DD]]
python -m nucleo sugerir-prueba <receta.json> [--sin-estimacion]
```

Ejemplo completo con un dataset real:

```bash
python -m nucleo plantilla datasets_prueba/diabetes.csv --objetivo Outcome
# editar datasets_prueba/diabetes_decisiones.json
python -m nucleo preparar datasets_prueba/diabetes.csv --objetivo Outcome \
    --decisiones datasets_prueba/diabetes_decisiones.json
python -m nucleo sugerir-prueba datasets_prueba/diabetes_receta.json
```

Archivos generados, junto al archivo de entrada: `<nombre>_revision.json`,
`<nombre>_decisiones.json`, `<nombre>_receta.json`, `<nombre>_train.csv`,
`<nombre>_test.csv` y `<nombre>_recomendacion.json`. **Nunca se sobrescribe un archivo
existente**: se añade `_2`, `_3`, etc. (con el mismo número para la receta y sus CSV).

Códigos de salida:

| Código | Significado |
|---|---|
| `0` | Comando completado. |
| `1` | Error de argumentos o de ejecución (archivo inexistente, hoja inexistente, decisiones no aplicables, receta de un archivo modificado...). |
| `2` | Dataset no válido (errores bloqueantes de validación). |

En Windows, si la consola muestra mal las tildes, ejecute con `python -X utf8 -m nucleo ...`.

## Entorno de desarrollo

Requiere Python 3.11 o superior.

```bash
cd nucleo
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

Dependencias: `pandas`, `numpy`, `openpyxl`, `scipy`, `scikit-learn` y `causal-learn`;
`pytest` para desarrollo.

## Pruebas

```bash
cd nucleo
pytest
```

Las pruebas de aceptación con datos reales (`tests/test_aceptacion_datos_reales.py`) se
omiten automáticamente si falta alguno de los archivos de `datasets_prueba/`.
