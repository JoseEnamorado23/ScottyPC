# pc-app

Aplicación de escritorio para investigación sobre modelos prescriptivos.

## Objetivo del proyecto

El paquete `nucleo` valida y revisa datasets antes de las etapas posteriores de
modelado. Comprueba que el dataset cumple las condiciones mínimas para continuar,
perfila cada columna y detecta problemas de calidad y relaciones sospechosas entre
columnas. **Solo informa y sugiere acciones: nunca modifica, corrige ni elimina datos.**
La decisión final siempre es del usuario.

El descubrimiento causal (algoritmo PC) y las demás capas de la aplicación **todavía
están pendientes**.

## Arquitectura actual

```
pc-app/
├── nucleo/            Paquete Python del núcleo (funcional)
│   ├── pyproject.toml
│   ├── src/nucleo/
│   └── tests/
├── sidecar/           Vacío: futuro servidor local FastAPI (sin implementar)
├── app/               Vacío: futuro frontend Tauri v2 + React (sin implementar)
└── datasets_prueba/   Datasets reales y sintéticos para pruebas manuales
```

| Componente     | Tecnología prevista                     | Estado                    |
|----------------|-----------------------------------------|---------------------------|
| Núcleo         | Paquete Python independiente (`nucleo`) | Primera versión funcional |
| Sidecar        | FastAPI local en Python                 | Pendiente                 |
| Frontend       | Tauri v2 + React + Vite + TypeScript    | Pendiente                 |
| Almacenamiento | SQLite + archivos locales               | Pendiente                 |

El núcleo no depende de ningún componente de presentación.

### Módulos de `nucleo`

| Módulo | Responsabilidad |
|---|---|
| `carga.py` | Lectura de CSV (detecta separador y codificación) y XLSX (selección de hoja). |
| `validacion.py` | Validación estructural: encabezados, dimensiones y variable objetivo. |
| `perfilado.py` | Perfil de cada columna: tipo preliminar, faltantes, valores únicos, mínimo y máximo. |
| `detectores.py` | Detectores básicos por columna y del objetivo. |
| `detectores_relaciones.py` | Detectores de relaciones entre columnas y mezclas de unidades. |
| `revision.py` | Orquesta perfilado y detectores y produce el `InformeRevision`. |
| `analisis.py` | Flujo completo: validación y, si es válido, revisión. |
| `cli.py` | Interfaz de línea de comandos (`python -m nucleo`). |
| `modelos.py`, `configuracion.py`, `utilidades.py` | Dataclasses de resultados, umbrales centralizados y serialización a JSON. |

## Flujo

```
archivo → carga → validación ─┬─ errores bloqueantes → se informan y se detiene
                              └─ válido → perfil → detectores básicos
                                          → detectores de relaciones
                                          → InformeRevision → JSON
```

## Contrato del núcleo

> Las funciones de análisis no modifican el dataset recibido.

| Función | Entrada | Salida | Responsabilidad |
|---|---|---|---|
| `nucleo.carga.cargar_dataset(ruta, hoja=None)` | Ruta CSV/XLSX | `pd.DataFrame` | Leer el archivo. Lanza `ErrorCarga` (con un `ProblemaValidacion`) si no puede. |
| `nucleo.validacion.validar_dataset(df, objetivo, configuracion=None)` | DataFrame y objetivo | `ResultadoValidacion` | Condiciones mínimas: `valido` es `True` solo si no hay errores. |
| `nucleo.revision.revisar_dataset(df, objetivo, configuracion=None)` | DataFrame y objetivo | `InformeRevision` | Resumen, perfiles de columnas y hallazgos de todos los detectores. |
| `nucleo.analisis.analizar_dataset(df, objetivo, configuracion=None)` | DataFrame y objetivo | `ResultadoAnalisis` | Valida y solo revisa si no hay errores bloqueantes (si no, `informe` es `None`). |
| `nucleo.analisis.resultado_a_diccionario(resultado)` | `ResultadoAnalisis` | `dict` | Estructura compatible con `json.dumps`. |

Ninguna de estas funciones modifica el DataFrame. Todos los umbrales están en
`ConfiguracionValidacion` (`configuracion.py`).

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
| Fechas | `posible_fecha` | Variables temporales (tipo fecha o texto con formato de fecha con separadores). |
| Categóricas | `variable_categorica`, `posible_variable_ordinal` | Variables categóricas y posible orden natural. |
| Distribución del objetivo | `distribucion_objetivo` | Conteo y porcentaje por clase. |
| Desbalance | `desbalance_clases` | Clase minoritaria por debajo del 20 % (objetivo binario). |
| Copias | `columnas_redundantes` | Columnas idénticas. |
| Recodificaciones | `recodificacion_uno_a_uno` | Correspondencias uno a uno entre columnas. |
| Derivadas | `columna_derivada` | Relaciones de suma o resta (p. ej. `ancho = maximo - minimo`). |
| Binarias derivadas | `binaria_derivada` | Binarias que parecen resultar de un umbral sobre una variable numérica. |
| Correlación | `correlacion_casi_perfecta` | \|r\| > 0.99, incluidas transformaciones lineales exactas. |
| Unidades | `posible_mezcla_unidades` | Dos grupos de valores claramente separados (posibles escalas distintas). |

## Uso desde la terminal

```bash
python -m nucleo revisar <archivo> --objetivo <columna> [--hoja <nombre>]
```

Ejemplos:

```bash
python -m nucleo revisar datasets_prueba/dataset_prueba.csv --objetivo objetivo
python -m nucleo revisar datos.xlsx --objetivo aprobado --hoja estudiantes
```

La CLI muestra un resumen y guarda el informe completo en `<nombre>_revision.json`,
junto al archivo analizado. **Nunca sobrescribe un informe existente**: si ya existe,
usa `<nombre>_revision_2.json`, `<nombre>_revision_3.json`, etc. Si el dataset no es
válido, muestra los errores bloqueantes y no genera informe.

Códigos de salida:

| Código | Significado |
|---|---|
| `0` | Análisis completado; informe generado. |
| `1` | Error de argumentos o de ejecución (archivo inexistente, formato no soportado, hoja inexistente...). |
| `2` | Dataset no válido (errores bloqueantes de validación). |

Estructura del JSON: `origen`, `valido`, `validacion` (errores y advertencias),
`resumen`, `hallazgos`, `perfiles_columnas`, `objetivo` e `informacion_objetivo`.

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

Dependencias: `pandas`, `numpy` y `openpyxl`; `pytest` para desarrollo.

## Pruebas

```bash
cd nucleo
pytest
```
