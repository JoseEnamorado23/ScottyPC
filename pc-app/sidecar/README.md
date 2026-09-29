# Sidecar (servidor local)

Servidor FastAPI local que expone el núcleo (`pcapp_nucleo`) por HTTP. Tauri lo arranca como
proceso aparte y el frontend en React le hace peticiones.

## Instalación

```bash
cd pc-app/sidecar
python -m venv .venv
.venv\Scripts\activate            # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ../nucleo           # primero el núcleo, en modo editable
pip install -e ".[dev]"
```

> Los paquetes se llaman `pcapp_nucleo` y `pcapp_servidor` para no chocar con paquetes de
> PyPI (existe uno ajeno llamado `nucleo`). `pcapp_nucleo` no está publicado en PyPI, así que
> debe instalarse antes y en modo editable; si falta, pip se detiene con un error en vez de
> instalar algo ajeno. Al arrancar, el servidor comprueba además que el núcleo cargado sea
> el de pc-app.

## Arranque

```bash
python -m pcapp_servidor --datos <carpeta> [--puerto N] [--pid-padre N] [--procesos N]
                   [--modo-desarrollo [--sin-token]]
```

- Escucha **solo en 127.0.0.1**. Sin `--puerto`, el sistema elige un puerto libre.
- Al estar listo imprime en stdout **una única línea JSON**; nada más se escribe en stdout:

  ```json
  {"evento": "listo", "puerto": 57469, "token": "…"}
  ```

  Si no puede arrancar (puerto ocupado, núcleo ausente, opciones incompatibles):
  `{"evento": "error", "mensaje": "…"}` y código de salida 1.
- `--pid-padre N`: el servidor se cierra solo cuando termina ese proceso (se comprueba
  cada 2 s con psutil, incluida la hora de creación para no confundirlo con otro proceso
  que reutilice el PID). Así no quedan procesos huérfanos si la aplicación se cierra mal.
- `--modo-desarrollo`: puerto fijo 8765; con `--sin-token` no se exige el token.
- Cierre ordenado: `POST /apagar` (o Ctrl+C). Los trabajos en curso se cancelan, guardan
  su punto de control y quedan como `interrumpido`.
- Empaquetado con PyInstaller: el punto de entrada llama primero a
  `multiprocessing.freeze_support()` y los recursos (el esquema SQL) se leen con
  `importlib.resources`, sin rutas basadas en `__file__`.

## Seguridad

- **Token:** todas las peticiones deben incluir `X-Token: <token>` (401 si falta o no
  coincide). El token es aleatorio en cada arranque y **nunca** se acepta en la URL,
  porque quedaría en registros e historiales.
- **CORS:** solo `tauri://localhost`, `http://tauri.localhost`, `https://tauri.localhost`
  y el servidor de desarrollo de Vite (`http://localhost:5173`, `http://127.0.0.1:5173`).
- **Archivos:** `GET /proyectos/{id}/archivos/{nombre}?version=` solo sirve `grafo.png`,
  `aristas.csv`, `mascara.csv`, `matriz_frecuencias.csv` y `resultado.json`, y comprueba con
  `resolve()` que la ruta quede dentro de la carpeta de resultados.
- **Errores técnicos:** van al registro (`<datos>/logs/servidor.log`, rotativo); el
  cliente solo recibe un código y una referencia para buscarlos.

### Mostrar imágenes y descargar archivos desde el frontend

Una etiqueta `<img src="…">` no puede enviar el encabezado `X-Token`, así que el frontend
debe descargar el archivo con `fetch` y mostrarlo con `URL.createObjectURL`:

```ts
const respuesta = await fetch(`http://127.0.0.1:${puerto}/proyectos/${id}/archivos/grafo.png`, {
  headers: { "X-Token": token },
});
const url = URL.createObjectURL(await respuesta.blob());
imagen.src = url;               // o <img src={url} /> en React
// …y al desmontar el componente: URL.revokeObjectURL(url);
```

El servidor devuelve el `Content-Type` correcto (`image/png`, `text/csv`,
`application/json`), de modo que el `Blob` conserva su tipo.

## Almacenamiento

```
<datos>/
├── app.db                      SQLite (tablas proyectos, etapas, trabajos)
├── logs/servidor.log           registro rotativo (5 MB × 5)
└── proyectos/<id>/
    ├── original.csv|xlsx       copia del archivo (el original del usuario no se toca)
    ├── revision.json  decisiones.json  receta.json  train.csv  test.csv
    ├── recomendacion.json  pc.json
    ├── pc/                     resultados de PC = versión 1 (y punto_control.json mientras corre)
    │   ├── versiones.json      índice: parámetros de cada versión y la versión actual
    │   └── versiones/<n>/      versiones ajustadas (resultado.json, grafo.png, CSV)
    ├── modelo_causal/          modelo_causal.json (mecanismos, huella) y evaluacion.json
    └── anteriores/<fecha-hora>/   archivos de etapas invalidadas
```

Un índice único parcial en `trabajos` garantiza **un solo trabajo activo por proyecto**.

## Etapas e invalidación

| Etapa | Requiere (vigente) | Archivos |
|---|---|---|
| revision | proyecto | `revision.json` |
| decisiones | revision | `decisiones.json` |
| preparacion | decisiones | `receta.json`, `preparacion.json`, `train.csv`, `test.csv` |
| recomendacion | preparacion | `recomendacion.json` |
| configuracion_pc | preparacion | `pc.json` |
| analisis | configuracion_pc | `pc/` |
| modelo_causal | analisis | `modelo_causal/` |

Al rehacer una etapa, sus archivos anteriores y los de **todas las posteriores** se mueven
a `anteriores/<fecha-hora>/` y esas etapas quedan `desactualizada`. Ejecutar una etapa sin
su requisito vigente, o modificar un proyecto con un trabajo en curso, devuelve **409** con
un mensaje que indica qué falta.

Rehacer la preparación (p. ej. con otra separación) deja desactualizadas la recomendación,
la configuración de PC, el análisis y el modelo causal, pero no las decisiones.

El modelo causal queda ligado a la versión del resultado de PC con la que se construyó
(número y sha256 de su `resultado.json`): guardar una versión nueva o cambiar la versión
actual lo archiva y lo deja `desactualizada`.

## Endpoints

| Método y ruta | Descripción |
|---|---|
| `GET /salud` | Estado, versiones y si el grupo de procesos está creado. |
| `POST /apagar` | Cierre ordenado. |
| `POST /proyectos` `{ruta_archivo, nombre?}` | Copia el archivo; devuelve hojas, columnas y las 20 primeras filas. |
| `GET /proyectos` · `GET/DELETE /proyectos/{id}` | Lista, detalle (con el estado de cada etapa) y borrado (409 si hay un trabajo activo). |
| `GET /proyectos/{id}/datos?hoja=` | Hojas, filas, columnas y 20 primeras filas de una hoja. |
| `GET /proyectos/{id}/distribucion?columna=&hoja=` | Conteos por valor (20 más frecuentes + `otros`) o histograma de 20 intervalos si es numérica con más de 20 valores. |
| `POST /proyectos/{id}/revision` `{objetivo, hoja?}` | Validación + `InformeRevision` (422 si el dataset no es válido). |
| `GET /proyectos/{id}/revision` | Revisión guardada (409 si no está vigente). |
| `GET /proyectos/{id}/decisiones/plantilla` | Decisiones sugeridas. |
| `POST /proyectos/{id}/decisiones/previsualizar` `{elecciones: {identificador: accion}}` | Decisiones que resultan de las acciones elegidas, calculadas por el núcleo (`aplicar_elecciones`); no guarda nada. Una elección no válida da 422 con `campo = elecciones.<identificador>`. |
| `GET/PUT /proyectos/{id}/decisiones` | Decisiones guardadas; el PUT valida (422 por campo) e invalida lo posterior. |
| `POST /proyectos/{id}/preparar` `{separacion?}` | Prepara con la separación indicada (o la inicial) y la guarda en la receta. Resumen: filas y distribución del objetivo en train y test, columnas finales, faltantes restantes y `limite_columnas`. |
| `GET /proyectos/{id}/preparacion` | Resumen vigente (o `null`), separación inicial del formulario (la de la receta más reciente o la sugerida) y fechas disponibles. |
| `POST /proyectos/{id}/recomendacion?estimar_tiempo=` | Recomendación de prueba como **trabajo** (202). 409 `DEMASIADAS_COLUMNAS` si hay más de 50 columnas finales. |
| `GET /proyectos/{id}/recomendacion` | Recomendación guardada. |
| `POST /proyectos/{id}/recomendacion/evaluar` `{prueba, max_k}` | Advertencias del núcleo si la elección contradice los datos y tiempo estimado con ella; no guarda nada. |
| `GET/PUT /proyectos/{id}/configuracion-pc` | Configuración de PC (el GET devuelve la plantilla con `guardada: false` si no existe). El PUT devuelve 422 con todos los errores, cada uno con su campo (`niveles.2`, `nombres_niveles.0`, `modificables`...). |
| `GET /proyectos/{id}/configuracion-pc/plantilla` | Plantilla (todas las variables en un nivel y el objetivo al final), para restablecer. |
| `POST /proyectos/{id}/configuracion-pc/validar` | `{valida, errores, advertencias}` sin guardar (p. ej. el objetivo fuera del último nivel). |
| `POST /proyectos/{id}/pc` | Lanza el análisis como **trabajo** (202). 409 `DEMASIADAS_COLUMNAS` como la recomendación. |
| `GET /trabajos/{id}` | Estado, completadas, total, fallidas, tiempo transcurrido y restante estimado; `detalles` = modo del análisis en curso (`midiendo`, `secuencial` o `paralelo` con N procesos). |
| `POST /trabajos/{id}/cancelar` · `POST /trabajos/{id}/reanudar` | Cancelar; reanudar (PC continúa desde su punto de control; la recomendación se repite). |
| `GET /proyectos/{id}/resultado?version=` | Resultado de una versión (por defecto la actual), con `agregacion`, `etiqueta` («Original» o «Ajustada: umbral X, original Y»), `avisos` (advertencias de interpretación) y `disposicion` (columnas del grafo por nivel). |
| `GET /proyectos/{id}/resultado/versiones` | Versiones (número, base, umbral, orientaciones manuales, fecha, `migrada`, etiqueta), versión actual y umbral original. La primera consulta de un resultado anterior a las versiones lo migra. |
| `POST /proyectos/{id}/resultado/reagregar` `{umbral_frecuencia, orientaciones_manuales}` | Vista previa con otro umbral u otras orientaciones, **sin escribir nada**. 422 `AJUSTE_NO_VALIDO` con el campo de cada problema (`orientaciones_manuales.0` si contradice los niveles, `.justificacion` si falta). |
| `POST /proyectos/{id}/resultado/versiones` `{umbral_frecuencia, orientaciones_manuales, version_base}` | Guarda el ajuste como versión nueva (201) y la hace actual. Las anteriores y `pc.json` no cambian. |
| `PUT /proyectos/{id}/resultado/version-actual` `{version}` | Vuelve a cualquier versión. |
| `GET /proyectos/{id}/resultado/procedencia` | Archivo, hash, filas, decisiones y separación resumidas por el núcleo, configuración original de PC y prueba recomendada. |
| `GET /proyectos/{id}/archivos/{nombre}?version=` | Archivos de resultados de una versión (ver *Seguridad*). |
| `POST /proyectos/{id}/modelo-causal/aplicabilidad` `{monotonia?, mecanismos?, pesos_clase?, umbral_parsimonia?}` | Bloqueantes y advertencias del modelo causal (cada uno con `accion` y `destino`: la pantalla donde se resuelve) y el subgrafo del objetivo, **sin construir nada**. Si el análisis no está vigente, un único bloqueante (`RESULTADO_DESACTUALIZADO` o `RESULTADO_INCOMPLETO`). |
| `POST /proyectos/{id}/modelo-causal` `{monotonia?, mecanismos?, pesos_clase?, umbral_parsimonia?}` | Construye el modelo causal sobre la versión actual del resultado como **trabajo** (202). 409 `MODELO_NO_APLICABLE` con `detalles.problemas` si hay bloqueantes; el trabajo falla con `RESULTADO_CAMBIADO` si la versión cambia mientras se construye. «Reanudar» lo repite con la misma configuración. |
| `GET /proyectos/{id}/modelo-causal` | Modelo (subgrafo, mecanismos elegidos con sus candidatos, monotonía, umbral de decisión, advertencias, huella), evaluación (métricas, calibración, referencia, curvas de efecto parcial con histograma), `controles` de los escenarios (dummies one-hot agrupadas por categoría) y `vigente`. |
| `GET /proyectos/{id}/modelo-causal/casos?pagina=` | Filas de test en unidades originales (50 por página) para elegir un caso. |
| `POST /proyectos/{id}/modelo-causal/contrafactual` `{caso: {indice_test} \| {valores}, intervenciones: [{variable, tipo, valor}]}` | Escenario: valores antes y después de todas las variables del subgrafo, probabilidad (o valor) del objetivo, clase según el umbral, traza de propagación, extrapolaciones y avisos (`SIN_EFECTO`, `EXTRAPOLACION`...). 422 `CONTRAFACTUAL_NO_VALIDO` con el campo (p. ej. `intervenciones.0.variable` al intervenir el objetivo o una consecuencia suya, `caso.valores.Age` si el valor no es válido). |
| `POST /proyectos/{id}/exportar` `{carpeta_destino, version?}` | Copia los archivos de **una** versión (por defecto la actual) y la receta a `<destino>/<nombre>_v<n>_<fecha-hora>/`, con `informe.html`: informe autocontenido que se abre sin conexión, con el umbral original junto al usado y el historial de versiones (marcando la exportada). |

El esquema completo está en `/openapi.json` (con token) y `/docs`. Formato de error
uniforme:

```json
{"error": {"codigo": "DECISIONES_NO_VALIDAS", "mensaje": "Hay decisiones no válidas.",
           "detalles": [{"campo": "faltantes.Glucose.imputacion", "mensaje": "Valor no permitido; …"}]}}
```

## Trabajos y grupo de procesos

- Cada trabajo corre en un hilo del servidor con un evento de cancelación. El progreso se
  guarda en memoria en cada corrida y en SQLite como mucho una vez por segundo. El tiempo
  restante se estima con el ritmo de la sesión actual.
- Tipos de trabajo: `recomendacion`, `pc` y `modelo_causal`. La tabla `trabajos` pasó a la
  versión 2 del esquema para admitir el tercero (la migración conserva las filas).
- Si el servidor se reinicia, los trabajos que estaban activos quedan `interrumpido` y se
  pueden reanudar. Cada proyecto expone `ultimo_trabajo` (con `reanudable`) para marcarlos.
- El grupo de procesos de PC se crea una sola vez, de forma perezosa (solo cuando un
  análisis decide ir en paralelo), y se reutiliza entre análisis: arrancarlo cuesta unos
  20 s en Windows. Tras una cancelación se recicla cuando ningún otro análisis lo usa. El
  resultado es idéntico con o sin él.

## Pruebas y demostración

```bash
pytest                          # incluye el arranque del proceso real y la vigilancia del padre
python scripts/demo_api.py      # arranca el servidor y recorre el flujo con diabetes por HTTP
```
