# Sidecar (servidor local)

Servidor FastAPI local que expone el núcleo (`nucleo`) por HTTP. Tauri lo arranca como
proceso aparte y el frontend en React le hace peticiones.

## Instalación

```bash
cd pc-app/sidecar
python -m venv .venv
.venv\Scripts\activate            # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ../nucleo           # primero el núcleo, en modo editable
pip install -e ".[dev]"
```

> El núcleo **no** se declara como dependencia en `pyproject.toml`: en PyPI existe un
> paquete ajeno llamado `nucleo`, y declararlo podría instalarlo por error. Al arrancar,
> el servidor comprueba que el núcleo instalado sea el de pc-app.

## Arranque

```bash
python -m servidor --datos <carpeta> [--puerto N] [--pid-padre N] [--procesos N]
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
- **Archivos:** `GET /proyectos/{id}/archivos/{nombre}` solo sirve `grafo.png`,
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
    ├── pc/                     resultados de PC (y punto_control.json mientras corre)
    └── anteriores/<fecha-hora>/   archivos de etapas invalidadas
```

Un índice único parcial en `trabajos` garantiza **un solo trabajo activo por proyecto**.

## Etapas e invalidación

| Etapa | Requiere (vigente) | Archivos |
|---|---|---|
| revision | proyecto | `revision.json` |
| decisiones | revision | `decisiones.json` |
| preparacion | decisiones | `receta.json`, `train.csv`, `test.csv` |
| recomendacion | preparacion | `recomendacion.json` |
| configuracion_pc | preparacion | `pc.json` |
| analisis | configuracion_pc | `pc/` |

Al rehacer una etapa, sus archivos anteriores y los de **todas las posteriores** se mueven
a `anteriores/<fecha-hora>/` y esas etapas quedan `desactualizada`. Ejecutar una etapa sin
su requisito vigente, o modificar un proyecto con un trabajo en curso, devuelve **409** con
un mensaje que indica qué falta.

## Endpoints

| Método y ruta | Descripción |
|---|---|
| `GET /salud` | Estado, versiones y si el grupo de procesos está creado. |
| `POST /apagar` | Cierre ordenado. |
| `POST /proyectos` `{ruta_archivo, nombre?}` | Copia el archivo; devuelve hojas, columnas y las 20 primeras filas. |
| `GET /proyectos` · `GET/DELETE /proyectos/{id}` | Lista, detalle (con el estado de cada etapa) y borrado (409 si hay un trabajo activo). |
| `POST /proyectos/{id}/revision` `{objetivo, hoja?}` | Validación + `InformeRevision` (422 si el dataset no es válido). |
| `GET /proyectos/{id}/decisiones/plantilla` | Decisiones sugeridas. |
| `GET/PUT /proyectos/{id}/decisiones` | Decisiones guardadas; el PUT valida (422 por campo) e invalida lo posterior. |
| `POST /proyectos/{id}/preparar` | Receta y resumen (filas, columnas finales, faltantes restantes). |
| `POST /proyectos/{id}/recomendacion?estimar_tiempo=` | Recomendación de prueba como **trabajo** (202). |
| `GET /proyectos/{id}/recomendacion` | Recomendación guardada. |
| `GET/PUT /proyectos/{id}/configuracion-pc` | Configuración de PC (el GET devuelve la plantilla con `guardada: false` si no existe). |
| `POST /proyectos/{id}/pc` | Lanza el análisis como **trabajo** (202). |
| `GET /trabajos/{id}` | Estado, completadas, total, fallidas, tiempo transcurrido y restante estimado. |
| `POST /trabajos/{id}/cancelar` · `POST /trabajos/{id}/reanudar` | Cancelar; reanudar (PC continúa desde su punto de control; la recomendación se repite). |
| `GET /proyectos/{id}/resultado` | `resultado.json`. |
| `GET /proyectos/{id}/archivos/{nombre}` | Archivos de resultados (ver *Seguridad*). |
| `POST /proyectos/{id}/exportar` `{carpeta_destino}` | Copia resultados y receta a `<destino>/<nombre>_<fecha-hora>/`. |

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
- Si el servidor se reinicia, los trabajos que estaban activos quedan `interrumpido` y se
  pueden reanudar.
- El grupo de procesos de PC se crea una sola vez, de forma perezosa (solo cuando un
  análisis decide ir en paralelo), y se reutiliza entre análisis: arrancarlo cuesta unos
  20 s en Windows. Tras una cancelación se recicla cuando ningún otro análisis lo usa. El
  resultado es idéntico con o sin él.

## Pruebas y demostración

```bash
pytest                          # incluye el arranque del proceso real y la vigilancia del padre
python scripts/demo_api.py      # arranca el servidor y recorre el flujo con diabetes por HTTP
```
