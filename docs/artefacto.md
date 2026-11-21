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
| `predicciones_train.parquet` | (formato 2) `eta` de cada mecanismo sobre train, sin pérdida: el mismo vector que resume la huella. Sirve de referencia para cargar en otra plataforma (ver «Carga exacta y equivalente»). |
| `esquema_entrada.json` | Columnas **originales** (nombres exactos, también con tabuladores). |
| `controles.json` | Qué se puede modificar y dentro de qué límites. |
| `evaluacion.json` | Evaluación del modelo y, si es vigente, del prescriptor. |
| `golden.json` | Casos de verificación con sus resultados. |

### `manifest.json`

`formato = "scotty-artefacto"`, `version_formato = 3` (el 1 y el 2 se siguen leyendo; ver «Comportamiento por formato»), `creado_en`, `version_nucleo`,
`versiones_librerias` (pygam, scikit-learn, numpy, scipy, y desde el formato 2 también python, pandas, pyarrow y networkx), `proyecto` (id, nombre, archivo, sha256 del dataset), `objetivo` (columna, tipo,
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
`cambio_maximo`, `costo`, `estados_permitidos`, `permitida`, `paso` y `valores_permitidos`. Solo hay controles de
las variables con supuestos confirmados. Todo está en **unidades originales** (ver «Formato 3»).

| Campo | Continuas | Ordinales | Binarias y categóricas |
|---|---|---|---|
| `minimo`, `maximo` | Límites absolutos | Límites absolutos, **en valores originales** | `null` |
| `cambio_maximo` | Máximo cambio respecto al valor actual | Ídem, en valores originales (créditos, no niveles) | `null` |
| `paso` | Resolución con la que prescribe el núcleo (1 para enteras, 0,5 para horas a media hora, `null` = libre) | `null` (se usa `valores_permitidos`) | `null` |
| `valores_permitidos` | `null` | Niveles a los que se puede pasar | `null` |
| `estados_permitidos` | `null` | Etiquetas de esos niveles | Valores a los que se puede pasar |

`valores_permitidos` es una lista, por orden de nivel, de `{"valor": número, "etiqueta": texto | null}`: `valor` es
el valor original del nivel (la etiqueta si todas son números —créditos 14, 15, …— y entonces `etiqueta` es `null`;
si no, su posición 0, 1, … y `etiqueta` es el texto, p. ej. `{"valor": 2, "etiqueta": "alto"}`). Solo incluye los niveles que están entre
`minimo` y `maximo` y en `estados_permitidos`.

### Formato 3: qué cambia para quien consume el artefacto (el portal)

Solo cambia `controles.json` (y el número `version_formato` de todos los archivos); `prescripcion.json`, el modelo y
el train son los mismos. Un lector del formato 2 que encuentre un `3` lo rechaza por `version_formato`; el núcleo
nuevo lee los formatos 1, 2 y 3.

1. **`paso` es el paso real, no «1 si hay enteros».** Antes era informativo (1 o `null`, solo continuas) y la
   prescripción podía proponer 2,4 tutorías. Ahora el núcleo solo propone múltiplos de `paso` (y el golden lo
   comprueba). Un portal debe usarlo como `step` del campo numérico y no esperar valores intermedios. Puede ser
   decimal (0,5). Ya no es un entero.
2. **Las ordinales traen `valores_permitidos`** (nuevo, obligatorio en el formato 3 para `tipo = "ordinal"`). Un portal
   debe ofrecer exactamente esos valores (lista desplegable o control deslizante discreto) y mostrar `etiqueta` cuando
   no es `null`. Antes había que deducir los niveles de `estados_permitidos`.
3. **Los límites de las ordinales están en valores originales.** En los formatos 1 y 2, `minimo`, `maximo` y
   `cambio_maximo` de una ordinal iban en **códigos** (posición del nivel): con créditos 8…22, «mínimo 2» significaba 10
   créditos. Ahora «mínimo 10» es 10 créditos, y `cambio_maximo = 6` son 6 créditos. Si las etiquetas son texto,
   el «valor original» es la posición (0 = el primer nivel). Al cargar un artefacto de formato 1 o 2, el núcleo
   convierte esos controles (`art.controles` ya los trae en valores originales; el archivo no se modifica).
4. **`prescribir` informa `solo_con_cambios_intermedios`** (booleano, siempre presente): `true` cuando el objetivo
   se alcanzaría con valores intermedios pero no con los permitidos por `paso` y `valores_permitidos`. Va junto con
   `alcanzado = false`, y su `explicacion` termina con «Alcanzable solo con cambios intermedios…». Un portal puede
   mostrarlo como «el objetivo exige un cambio más fino que la resolución configurada». Los resultados de `prescribir`
   y `acciones[].cambio`, `antes_numerico`, `despues_numerico` de una ordinal con muchos niveles (más de 10, que se
   resuelve como continua sobre su rejilla) también están en valores originales. El golden de un artefacto anterior no trae el campo: ausente equivale a `false`.

Los límites, el paso y los valores permitidos que cumple cada acción se verifican en `verificar_golden` (valor fuera de
la rejilla o de `valores_permitidos` = caso fallido), **solo en los artefactos de formato 3** (ver la tabla siguiente).

### Comportamiento por formato

El núcleo lee los formatos 1, 2 y 3. Los artefactos antiguos se comportan como cuando se exportaron:

| | Formato 1 | Formato 2 | Formato 3 |
|---|---|---|---|
| Carga | Comprobación estricta (huella bit a bit), cualquier librería del manifest es estricta | Equivalente a 1 ULP; solo avisan python, pandas, pyarrow y networkx | Ídem formato 2 |
| `paso` de `controles.json` | **Informativo** (1 si en train solo hay enteros, `null` si no; solo continuas) | **Informativo**, igual que en el 1 | **Real**: el núcleo solo prescribe múltiplos del paso |
| Rejilla al prescribir | No hay: se prescribe con lo que diga la configuración de `prescripcion.json` (normalmente sin paso, así que puede proponer 2,4975 o 0,5) | Ídem | Sí: `paso` y `valores_permitidos` |
| `verificar_golden` comprueba `paso` y `valores_permitidos` | **No** | **No** | **Sí** (un valor fuera de la rejilla es un caso fallido) |
| `valores_permitidos` de las ordinales | No existe | No existe | Obligatorio para `tipo = "ordinal"` |
| Límites de las ordinales en `controles.json` | Códigos; al cargar se convierten a valores originales en memoria | Ídem | Valores originales |
| `solo_con_cambios_intermedios` en el golden | Ausente = `false` | Ausente = `false` | Siempre presente |

`verificar_golden` mantiene en todos los formatos lo demás: límites (`minimo`, `maximo`), `cambio_maximo`, dirección y estados
permitidos de cada acción recalculada, y que alcance el objetivo con el motor exacto. El resultado de un artefacto de
formato 1 o 2 es idéntico al de la versión con la que se exportó (golden idéntico en los 20 casos); está cubierto en
`pc-app/nucleo/tests/test_artefacto_formato2.py` con artefactos reales de formato 2 exportados con v0.5.

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
las librerías (**una diferencia en pygam, scikit-learn, numpy o scipy es un error**; pyGAM está fijado en
0.12.0; en python, pandas, pyarrow y networkx solo agrega un aviso a `art.avisos_carga`), la versión del
núcleo (también solo un aviso), que `sha256_train(train)` sea el del modelo, que el modelo reconstruido
reproduzca su huella (exacta o equivalente, ver abajo), y que μ y las variables prescriptivas coincidan con el
manifest. Después construye una sola vez el modelo, la configuración, la referencia y el índice de vecinos.
Los errores son `ErrorArtefacto(mensaje, codigo)`, con `codigo` en `FORMATO`, `INTEGRIDAD`, `VERSIONES`
o `MODELO`.

### Carga exacta y equivalente

La huella del modelo es el sha256 de las predicciones (`eta`) de cada mecanismo sobre train. BLAS/LAPACK
distintos (por ejemplo Windows y Linux/Docker) pueden dar 1 ULP (~1e-16) de diferencia con las mismas versiones
de librerías, y entonces la huella no coincide aunque el modelo sea el mismo. Por eso un artefacto de formato 2
guarda en `predicciones_train.parquet` las predicciones del equipo que lo exportó y `cargar_artefacto` hace lo
siguiente:

1. Si la huella sha256 coincide: carga **exacta**.
2. Si no, compara las predicciones recalculadas con las guardadas con `rtol=1e-10` y `atol=1e-12`
   (`|a − b| ≤ atol + rtol·|b|`): si todas están dentro, carga **equivalente**; si alguna no, `ErrorArtefacto`
   (`MODELO`) con el mecanismo y la diferencia.

```python
art = cargar_artefacto("ruta.scotty", rtol=1e-10, atol=1e-12)   # la tolerancia es un parámetro
art.informe_carga.tipo          # "exacta" | "equivalente"
art.informe_carga.mecanismos    # por mecanismo: filas, filas_distintas, filas_fuera_de_tolerancia,
                                # diferencia_maxima_absoluta, diferencia_maxima_relativa
```

Una carga equivalente agrega un aviso a `art.avisos_carga`. Las predicciones guardadas solo valen de referencia si
su sha256 está en el manifest y reproducen la huella guardada del modelo. Scotty PC de escritorio sigue exigiendo igualdad bit a bit
(`modelo_desde_diccionario`). Los artefactos del formato 1 se siguen leyendo, con la comprobación estricta de siempre
(huella bit a bit y todas las librerías del manifest idénticas).

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

`verificar_golden(art) -> InformeGolden` recalcula cada caso y compara. `predecir` y `contrafactual`: **igualdad
exacta** en lo discreto (textos, booleanos, enteros, claves y longitudes) y **≤ 1e-9** en los números. También
comprueba el sha256. Un microservicio debe llamarlo al arrancar y negarse a servir si `correcto` es falso.

`prescribir` se verifica por **resultado equivalente**. El optimizador usa arranques aleatorios y, si alguno no
converge (llega al tope de 300 iteraciones en un valle plano), 1 ULP de diferencia entre plataformas se amplifica
hasta ~1e-6 y el mínimo entre arranques puede elegir otro ganador, igual de válido. Por eso:

- Si el resultado coincide como antes (exacto en lo discreto, 1e-9 en los números), la trayectoria es **idéntica**.
- Si no, se acepta como **equivalente** cuando:
  - **Exacto:** `alcanzado`, `ya_cumple`, `requiere_revision`, `extrapolacion`, `aproximado`, los campos que solo
    dependen del caso (`antes`, `deseado`, `mu`…) y el **conjunto** de variables con cambio distinto de cero.
  - **Con tolerancia** (parámetros de `verificar_golden`, con estos valores por defecto): `costo_total` relativo
    ≤ 2 % (`costo_relativo`); `despues` (y `falta`) absoluto ≤ 0,01 (`despues_absoluto`); el `cambio` de cada acción
    ≤ 1,5 % del rango de train de su variable (`cambio_relativo_rango`).
  - **Válida:** la solución recalculada tiene cada valor final dentro de `[minimo, maximo]`, `|cambio| ≤
    cambio_maximo`, la dirección respetada, estados permitidos, y `alcanzado` con el motor exacto.
  - **No se comparan:** `traza`, `evidencia`, `referencia.despues`, `explicacion` ni `restricciones_activas`.

`InformeGolden` dice cuántos casos fueron `casos_identicos`, `casos_equivalentes` y `casos_fallidos`, en qué campo
falló cada uno (`campos_fallidos`: campo → índices de test) y, por caso, `trayectorias` (`resultado` y las
diferencias máximas `costo_relativo`, `despues_absoluto`, `cambio_relativo_rango`). El formato de `golden.json` no
cambia.

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
- **Unidades.** Los límites del esquema y de los controles están en unidades originales (desde el formato 3 también
  los de las ordinales); las conversiones de la receta se aplican al preparar.
- **Versiones.** Un cambio en pygam, scikit-learn, numpy o scipy es un error (los parámetros del modelo dependen
  de ellas); un cambio en python, pandas, pyarrow, networkx o en la versión del núcleo es un aviso. En el formato 1
  toda librería del manifest es estricta.
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
