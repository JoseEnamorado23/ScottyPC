# Artefacto `.scotty`

Un artefacto es un único archivo con todo lo necesario para **predecir, prescribir y calcular
contrafactuales de estudiantes nuevos sin entrenar nada**: el modelo causal, la configuración de la
prescripción, el modelo de referencia, los datos de train (para la evidencia de vecinos) y los
esquemas de entrada. No usa `pickle`: solo JSON y Parquet.

Lo escribe Scotty PC (`pcapp_nucleo.artefacto.exportar`) y lo lee cualquier aplicación que instale el
núcleo (`pcapp_nucleo.artefacto.cargar`), sin la carpeta del proyecto, sin SQLite y sin el dataset
original.

## Exportar

| Desde | Cómo |
|---|---|
| La app | Pestaña **Lote** de Prescripción → **Exportar para producción (.scotty)** (elige la carpeta; es un trabajo con progreso). |
| El sidecar | `POST /proyectos/{id}/prescripcion/exportar-artefacto` con `{"carpeta_destino": "..."}` → trabajo (`tipo: exportacion_artefacto`); el mensaje del trabajo completado trae la ruta. |
| La terminal | `python -m pcapp_nucleo exportar-artefacto <carpeta_proyecto> <destino>` |
| Python | `exportar_artefacto(carpeta_o_objetos, destino) -> Path` (o `exportar_artefacto_completo`, que además devuelve advertencias y la comparación con Scotty PC). |

El archivo se llama `<proyecto>_v<version_resultado>_<AAAAMMDD-HHMMSS>.scotty`. **Nunca se
sobrescribe** un archivo existente (se añade `_2`, `_3`…).

### Condiciones que bloquean la exportación (`ErrorExportacion`)

- La prescripción no está vigente (su huella no es la del modelo causal) o no hay prescripción guardada.
- μ efectivo es `None` (automático sin calibrar).
- Los supuestos de las variables prescriptivas no están confirmados.
- `evaluar_prescribibilidad` devuelve algún bloqueante (por ejemplo, no hay variables prescriptivas).
- Las librerías instaladas no son las del modelo (no se podría reproducir), o el train reconstruido
  con receta y dataset no es el del modelo.
- El artefacto recién escrito no supera su propia verificación (`verificar_golden`).

### Advertencias que no bloquean (van en `manifest.advertencias`)

`SIN_EVALUACION_PRESCRIPTOR` (o `EVALUACION_PRESCRIPTOR_OBSOLETA`, si la evaluación no corresponde al
modelo y a μ actuales), `INTERMEDIAS_BINARIAS` (el modelo usa Monte Carlo), `COSTO_PARSIMONIA` y las demás
advertencias no bloqueantes de aplicabilidad (por ejemplo `MODIFICABLES_SIN_CAMINO`).

## Contenido

Un zip con fechas fijas (1980-01-01), de modo que el mismo contenido da el mismo archivo.

| Archivo | Contenido |
|---|---|
| `manifest.json` | Identidad y resumen (abajo). |
| `receta.json` | La receta de preparación (se reutiliza `preparar_nuevos`). |
| `modelo_causal.json` | El modelo estructural (mecanismos por parámetros, huella, `train_sha256`). |
| `prescripcion.json` | Configuración, modelo de referencia y calibración de μ. |
| `train.parquet` | El train preparado, con índice y tipos (zstd). |
| `esquema_entrada.json` | Columnas **originales** (nombres exactos, también con tabuladores). |
| `controles.json` | Qué se puede modificar y dentro de qué límites. |
| `evaluacion.json` | Evaluación del modelo y, si es vigente, del prescriptor. |
| `golden.json` | Casos de verificación con sus resultados. |

### `manifest.json`

`formato = "scotty-artefacto"`, `version_formato = 1`, `creado_en`, `version_nucleo`,
`versiones_librerias`, `proyecto` (id, nombre, archivo, sha256 del dataset), `objetivo` (columna, tipo,
`clase_positiva`, `clase_objetivo`, medida, dirección, deseado, `umbral_decision`), `prescripcion` (`mu`,
`mu_origen` = `manual` | `automatico`, optimizador), `modelo` (`huella`, `train_sha256`,
`version_resultado_pc`), `variables_prescriptivas`, `supuestos_confirmados`, `resumen_evaluacion`,
`aviso` (el aviso permanente), `advertencias`, `archivos` (sha256 de cada archivo) y `golden_sha256`.

### `esquema_entrada.json`

Por columna: `nombre` (exacto), `nombre_visible` (sin caracteres de control ni espacios extra),
`tipo` (`continua` | `binaria` | `ordinal` | `categorica`), `categorias`, `minimo`/`maximo` observados en
train **en unidades originales**, `rol` (`ancestro_objetivo` | `prescriptiva` | `fuera_del_subgrafo` | `id`),
`admite_faltantes`, `imputacion` y `detalle_imputacion`. El rol `id` está reservado: hoy las columnas
identificadoras se descartan en la receta y no llegan al esquema.

### `controles.json`

Por variable prescriptiva: `variable`, `nombre_visible`, `tipo`, `direccion`, `minimo`, `maximo`,
`cambio_maximo`, `costo`, `estados_permitidos`, `permitida` y `paso` (1 si en train solo hay enteros; `null`
si no). Solo hay controles de las variables con supuestos confirmados.

## Cargar y usar

```python
from pcapp_nucleo.artefacto import cargar_artefacto, verificar_golden

art = cargar_artefacto("ruta.scotty")      # también acepta bytes
informe = verificar_golden(art)            # al arrancar el servicio
if not informe.correcto:
    raise SystemExit(informe.diferencias)
```

`cargar_artefacto` comprueba, en este orden: que sea un zip con los archivos esperados (ni más ni
menos, sin duplicados), el `formato` y la `version_formato`, el sha256 de cada archivo, las versiones de
las librerías (**una diferencia es un error**; pyGAM está fijado en 0.12.0), la versión del núcleo (una
diferencia solo agrega un aviso a `art.avisos_carga`), que `sha256_train(train)` sea el del modelo,
que el modelo reconstruido reproduzca su huella, y que μ y las variables prescriptivas coincidan con el
manifest. Después construye una sola vez el modelo, la configuración, la referencia y el índice de vecinos.
Los errores son `ErrorArtefacto(mensaje, codigo)`, con `codigo` en `FORMATO`, `INTEGRIDAD`, `VERSIONES`
o `MODELO`.

Todo se expresa en **unidades originales** (las del dataset tras la conversión de unidades de la
receta). Las filas son diccionarios `{nombre_exacto_de_columna: valor}`; los marcadores `NA`, `?`, `-`, `""`
y `None` cuentan como faltantes. El objetivo no se envía.

| Método | Devuelve |
|---|---|
| `art.manifest`, `art.esquema_entrada`, `art.controles` | Los datos del artefacto. |
| `validar_filas(df)` | `InformeValidacion`: columnas faltantes (con pista del nombre exacto), categorías no vistas, valores no numéricos, filas no preparables, valores fuera del rango de train (solo avisan). `fila` = posición en el archivo, desde 0. |
| `predecir(fila)` | `objetivo`, `medida`, `probabilidad`, `umbral_decision`, `clase`, `clase_etiqueta`, `probabilidad_clase_objetivo` (binario) o `valor` (continuo), `cumple_objetivo`, `causas` (`variable`, `categoria` directa/indirecta, `valor`, `valor_tipico`, `contribucion`, `prescriptiva`; de mayor a menor |contribución|), `extrapolacion`, `avisos`. |
| `prescribir(fila)` | Lo mismo que `ResultadoPrescripcion` de Scotty PC serializado (acciones, antes/después, `alcanzado`, `ya_cumple`, referencia, `requiere_revision`, `evidencia` de vecinos), con `caso = {"origen": "usuario", ...}`. |
| `contrafactual(fila, intervenciones)` | Con `intervenciones = [{"variable", "tipo": "fijar"\|"desplazar", "valor"}]`. Se puede intervenir cualquier variable del modelo, no solo las prescriptivas. |
| `prescribir_lote(df, progreso=None, cancelacion=None, procesos=1, tamano_bloque=...)` | `ResultadoLote`: un resultado por fila preparada (`fila`, `prescripcion`) y las filas que no se pudieron preparar. |

Los errores de la solicitud son `ErrorSolicitud(mensaje, campo, problemas)`; `campo` apunta a la columna
o a `intervenciones.<i>.<campo>`.

### Lotes y memoria

`prescribir_lote` procesa **por bloques, en secuencia**, liberando memoria entre bloques; `procesos=1`
es el valor por defecto. Con `procesos>1` usa un número acotado de procesos y envía cada bloque solo cuando
hay un trabajador libre. (El lote del sidecar, que envía todos los bloques de golpe y serializa el modelo y el
índice en cada uno, agotó la RAM con DropOut; el artefacto no repite ese diseño.)
`iterar_lote` entrega los bloques a medida que se calculan. `cancelacion.is_set()` se consulta entre
bloques y lanza `LoteCancelado`.

## Determinismo

El mismo artefacto con la misma fila da exactamente el mismo resultado. El optimizador usa una semilla
`SeedSequence([modelo.semilla, crc32(valores del caso redondeados)])`: **depende solo de los valores**, no
de la posición de la fila en el archivo (`semilla_por_valores=True`; Scotty PC conserva su comportamiento
anterior: para filas de test la semilla incluye el índice). El único campo no determinista de un resultado
es `segundos`, que el golden excluye.

## Golden y verificación

`golden.json` guarda hasta 20 casos de test (hasta 15 que no cumplen el objetivo y 5 que sí; si falta
un grupo, se completa con el otro). Cada caso trae `fila_original` (convertida a unidades originales),
`predecir`, `prescribir` y un `contrafactual` (fijar la primera variable prescriptiva en su máximo
permitido). Se calculan con la API de carga sobre el archivo recién escrito. `manifest.golden_sha256` es el
sha256 del JSON canónico (claves ordenadas, sin espacios) de los resultados.

`verificar_golden(art) -> InformeGolden` recalcula cada caso y compara: **igualdad exacta** en lo
discreto (textos, booleanos, enteros, claves y longitudes) y **≤ 1e-9** en los números. También comprueba
el sha256. Un microservicio debe llamarlo al arrancar y negarse a servir si `correcto` es falso.

Además, al exportar se compara, de forma informativa y sin bloquear, con el flujo de Scotty PC
(`comparar_con_scotty_pc`): tasa de acuerdo en `alcanzado`, en las acciones y en `requiere_revision`, y
diferencia media y máxima de `despues`. Una tasa de acuerdo baja indica que la preparación o la semilla
difieren y conviene revisar antes de publicar.

## Decisiones de diseño

- **Parquet y la huella.** `sha256_train` incluye el índice y los nombres de columna; el viaje de ida y
  vuelta por Parquet los conserva (se probó con los dos proyectos reales) y el exportador lo verifica. Si
  no se conservara, la exportación falla: no se puede reconstruir el train desde receta y dataset, porque
  el artefacto no lleva el dataset.
- **`clase_objetivo`.** En objetivos binarios, la clase cuya probabilidad se predice (la positiva);
  `clase_positiva` conserva las etiquetas originales.
- **`permitida`.** Un control puede estar declarado pero desactivado; las prescripciones lo respetan.
- **Unidades.** Los límites del esquema y de los controles están en unidades originales; las conversiones
  de la receta se aplican al preparar.
- **Versiones.** Cualquier cambio de librería es un error (los parámetros del modelo dependen de ellas); un
  cambio de versión del núcleo es un aviso.
- **Archivos desconocidos.** Un zip con archivos de más se rechaza, y también uno con campos
  desconocidos en el manifest, el esquema o los controles.

## Cómo verificar un artefacto

```bash
python -c "
from pcapp_nucleo.artefacto import cargar_artefacto, verificar_golden
a = cargar_artefacto('ruta.scotty'); print(a.avisos_carga); print(verificar_golden(a))"
```

Los artefactos de los proyectos reales de ejemplo y sus informes están en
[`docs/artefactos/`](artefactos/).
