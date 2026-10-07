# Explorador de variables — plan de diseño (alcance reducido)

Estado: **plan actualizado, pendiente de aprobación**. No se ha escrito código de la app.
Última revisión: 2026-10-04. Rama `main`, árbol limpio (los cambios previos del usuario ya están
en el commit `c92f89e`).

Herramienta **interna de investigación** (dos usuarios) para navegar las variables, depurar
resultados raros y entender por qué PC conserva o quita una arista. Se inspira en el Data Viewer
y el panel Environment de RStudio, pero no es una copia y no pretende ser un explorador completo.

---

## 1. Reglas fijas

> Copiadas tal cual del encargo original. Siguen vigentes en el alcance reducido.

- Solo lectura. El explorador sirve para INSPECCIONAR, COMPRENDER, COMPARAR y NAVEGAR.
  No edita valores, no imputa, no elimina columnas, no modifica la receta ni el grafo,
  no crea relaciones causales ni prescripciones, y no hace cálculos causales
  alternativos. Las decisiones siguen en los módulos existentes; el explorador solo
  enlaza a ellos ("Ver en Revisión →").
- Cero lógica duplicada: toda estadística o regla importante vive en el núcleo o en
  el sidecar, nunca en TypeScript. Reutiliza antes de crear.
- Estados por etapa. A: dataset cargado. B: revisión hecha. C: preparación hecha.
  D: PC hecho. E: modelo causal construido. F: prescripción disponible. Nunca se
  muestra información de una etapa que no existe; en su lugar va un estado vacío que
  explica qué paso la genera.
- Asociación ≠ causalidad. Una correlación se muestra como "ρ = 0,42", nunca como
  "X causa Y". Para relaciones causales se usa solo la terminología del núcleo.
  Las aristas no orientadas se advierten como tales.
- Rendimiento: debe ser usable con 20.000 × 50. Usa paginación en el servidor,
  muestras o datos agregados para los gráficos (nunca todos los puntos), carga bajo
  demanda por pestaña, caché por variable y versión del dataset, y no recalcules al
  cambiar de pestaña.
- Accesibilidad: los estados se indican con ícono + texto, no solo con color.
- Interfaz científica: limpia, densa pero legible, con panel lateral, pestañas,
  tooltips, badges y gráficos grandes. Nada de tarjetas gigantes ni estética de
  dashboard empresarial.
- No romper nada: no cambies APIs existentes ni el comportamiento del núcleo, salvo
  para exponer algo que ya calcula. En el menú solo se agrega la entrada
  "Explorador de variables", sin reordenar ni renombrar las demás.

### Garantías de no regresión (aplican a todas las fases)

- **Paso 0, antes de la fase 1:** ejecutar toda la suite (núcleo, sidecar y frontend: `pytest`
  en `nucleo/` y `sidecar/`, `npm test` y `npm run comprobar-tipos` en `app/`) y guardar el
  resultado como línea base (`docs/linea_base_pruebas.txt`, versionado). Las pruebas marcadas
  `lento` se ejecutan una vez en la línea base y de nuevo antes de cerrar la fase 3.
- Al final de cada fase, ningún test que pasaba en la línea base puede fallar.
- **Si algo obliga a cambiar un comportamiento existente, se detiene el trabajo y se pregunta.**
- Las pantallas existentes siguen obteniendo los datos exactamente como hoy; la caché nueva la
  usan solo los endpoints del explorador.

---

## 2. Alcance

**Dentro**

| Fase | Contenido | Capa |
|---|---|---|
| 1 | Navegación: lista de variables, encabezado y Resumen básico | backend + frontend |
| 2 | Diagnóstico: faltantes (y si dependen del objetivo), redundancia, train vs. test | backend + frontend |
| 3 | Captura de separadores en PC | **solo backend** |
| 4 | Pestaña Causal completa y grafo local | backend + frontend |

**Fuera** (ver §9, "Posibles extensiones"): Distribución, Valores (Data Viewer), Relaciones,
Preparación, Prescripción, contrafactuales, comparación de variables, heatmap, enlaces
`?variable=` a otras pantallas.

---

## 3. Hallazgos de la inspección (vigentes para el alcance reducido)

### 3.1 Arquitectura real

| Capa | Hecho verificado | Consecuencia |
|---|---|---|
| Frontend | Mantine 9 (`Table`, `Tabs`, `Badge`, `Tooltip`, `AppShell`), TanStack Query 5, React Router 8 (`HashRouter`), `@tabler/icons-react`, `cytoscape` (solo el grafo), `openapi-fetch` con tipos generados (`src/api/esquema.d.ts`). **No hay librería de gráficos ni de tablas.** | Gráficos en SVG propio (como `componentes/modelo_causal/Graficos.tsx`) y `Table` de Mantine. Sin dependencias nuevas. |
| Frontend | Claves de consulta en `api/consultas.ts`; `opcional()` convierte el 409 de "etapa no vigente" en `null`. | Consultas nuevas con claves `claves.*` propias; los estados vacíos salen de ahí. |
| Navegación | `NavegacionLateral.tsx` recorre `ETAPAS` (`estado/etapas.ts`) y dibuja un `NavLink` por etapa. | El explorador **no es una etapa**: una entrada aparte después de la lista; `ETAPAS` no cambia. |
| Sidecar | `Servicios(ServiciosModeloCausal, ServiciosPrescripcion)` en `flujo.py`; routers en `rutas/`; modelos en `esquemas.py` con una prueba (`tests/test_seguridad_y_esquemas.py`) que exige que cada modelo coincida con su dataclass del núcleo. | Patrón: `flujo_exploracion.py` (mixin) + `rutas/exploracion.py` + modelos emparejados con dataclasses. |
| Sidecar | Cada etapa guarda JSON/CSV en la carpeta del proyecto; rehacer una etapa archiva sus archivos y los de las posteriores en `anteriores/` y las marca "desactualizada". | Una etapa desactualizada no tiene archivos vigentes: se trata como inexistente (estado vacío). |
| Sidecar | **No hay caché de DataFrames**: `/datos` y `/distribucion` releen el archivo en cada petición y `_datos_preparados` reaplica toda la receta. Solo existe `_cache_modelo` (por `mtime`) en `flujo_causal.py`. | Caché nueva, exclusiva del explorador (§5). |
| Sidecar | `train.csv`/`test.csv` se guardan sin índice; la correspondencia con las filas originales está en `receta.indices_train/indices_test`. | Para train vs. test se leen esos CSV directamente (más barato que `aplicar_receta`). |

### 3.2 Estados A–F frente a las etapas del sidecar

El estado se calcula en el sidecar (una sola fuente; el TS solo lo pinta). Con este alcance se
usan A, B, C y D:

| Estado | Condición | Qué habilita |
|---|---|---|
| A | El proyecto existe. | Perfil (`perfilar_columnas` sobre el DataFrame en caché) y Resumen. |
| B | `revision` vigente (hay `objetivo`). | Faltantes vs. objetivo, hallazgos de la columna, redundancia. |
| C | `preparacion` vigente. | Train vs. test. |
| D | `analisis` vigente. | Pestaña Causal. |
| E, F | `modelo_causal` / `prescripcion` vigentes. | No se usan en este alcance (se muestra solo el rol de caracterización que ya trae el resultado de PC). |

### 3.3 Datos que se reutilizan

| Dato | Origen | Notas |
|---|---|---|
| Perfil de columna | `perfilado.perfilar_columnas` → `PerfilColumna` | `faltantes` cuenta solo NaN. **Decisión 6:** el explorador cuenta faltantes con la definición de los detectores (NaN + centinelas, `detectores_objetivo.mascara_faltantes`), y muestra ambos números cuando difieran. |
| Hallazgos y grupos redundantes | `revision.json` (`Hallazgo`, `grupo_redundante` con `evidencia.correlaciones`) | Se filtran por `columnas_involucradas`. |
| Faltantes vs. objetivo | `detectores_objetivo.detectar_faltantes_dependientes_objetivo` | Categórico: χ²/Fisher y % de faltantes por clase. Continuo: Mann-Whitney sobre el valor del objetivo (no compara por rangos). Solo emite hallazgo si supera umbrales (ver §6, F2). |
| Receta, train/test | `receta.json`, `train.csv`, `test.csv`, `preparacion.json` | Base de la comparación train vs. test. |
| Resultado de PC | `pc/resultado.json` → `ResultadoPC` (`aristas`, `caracterizacion`, `matrices`, `avisos`, `ciclos`), versiones en `pc/versiones/<n>/` | Frecuencias de aparición de **todos** los pares en `matrices`/`cuentas`. |
| Caracterización | `caracterizacion.caracterizar` | `causa_directa`, `causa_indirecta`, `consecuencia`, `ambigua`, `sin_camino`, con `a_traves_de` y `frecuencia_con_objetivo`. |
| Subgrafo | `causal.subgrafo.subgrafo_objetivo` | Referencia para la vecindad local; la vecindad nueva es de lectura sobre `aristas`. |

### 3.4 PC y los separadores: estado real y limitación importante

Lo que hoy guarda PC: `ejecutar_corrida` (`pc_bootstrap.py`) llama a `causallearn.pc(...)` y
**solo conserva** tres matrices de adyacencia extraídas de `grafo.G.graph`; el resto del objeto
`CausalGraph` se descarta. `resultado.json` y el punto de control solo tienen **cuentas por par**.

Lo que `causal-learn` calcula y se pierde (verificado en el código instalado):

- `cg.sepset[i][j]`: con `stable=True` es la **unión** de las variables de todos los conjuntos
  condicionantes que dieron independencia en la profundidad en que se quitó la arista, no «el»
  conjunto que la quitó. **No se presentará como tal** (ajuste del usuario).
- `cg.test.pvalue_cache`: p de cada prueba hecha, con clave `"i;j|s1.s2"` (índices ordenados
  `i < j`). Filtrando las claves del par con `p > alpha` se obtienen **exactamente los conjuntos
  condicionantes con los que PC encontró independencia**, cada uno con su p. Es la fuente que se
  usará.
- El estadístico no se guarda. Con `fisherz`/`mv_fisherz` se deriva del p
  (`X = Φ⁻¹(1 − p/2)`, con `X = √(n − |S| − 3)·|Z|`); con `chisq`/`gsq` no (**decisión 1**: solo el p).
  La prueba usada se conoce globalmente (`ConfiguracionPC.prueba`).

**Frecuencia de eliminación en el bootstrap: ya se puede calcular hoy**, sin cambios: PC solo
quita aristas en el esqueleto y las prohibiciones por niveles son unidireccionales, por lo que
`1 − (dirigidas[i][j] + dirigidas[j][i] + sin_orientar[i][j]) / corridas_validas` es la fracción
de corridas en que se quitó el par. Un par ausente del grafo agregado puede haberse conservado en
algunas corridas por debajo del umbral.

> ### Resuelto: no existe una «corrida principal»; los separadores salen del bootstrap
>
> No hay ninguna corrida de PC sobre todo el conjunto de entrenamiento: `ejecutar_bootstrap`
> ejecuta solo las `corridas_bootstrap` (por defecto 100) sobre **submuestras** del 80 % de train
> (`fraccion_submuestra = 0.8`, `submuestra(...)`). **Decisión del usuario (opción A):** los
> separadores y la frecuencia de eliminación salen de **las mismas corridas del bootstrap**, así
> que ambos datos comparten origen y denominador (N, las corridas válidas). No se añade ninguna
> ejecución de PC y no cambia ningún comportamiento existente. La opción de una corrida adicional
> sobre todo train queda descartada y solo se menciona en §10.

---

## 4. Endpoints mínimos

Convenciones de la API existente: router bajo `/proyectos/{proyecto_id}`; la columna va como
**parámetro de consulta `columna`** (como `/distribucion`); errores `404/409/422` con el cuerpo
uniforme; 409 `ETAPA_REQUERIDA` cuando la etapa no está vigente. Todos son `GET`, sin escritura y
sin trabajos en segundo plano. **No se modifica ningún endpoint existente.**

| # | Endpoint | Fase | Contenido |
|---|---|---|---|
| 1 | `GET /proyectos/{id}/variables` | 1 | Lista ligera para el panel: nombre, tipo detectado, % faltantes efectivo, únicos, rol (objetivo / categoría causal si hay PC), nº de hallazgos por severidad (si hay revisión), `estados` A–D y `huella`. |
| 2 | `GET /proyectos/{id}/variables/resumen?columna=` | 1 | Perfil de la columna y estadísticos básicos (n, faltantes, únicos, mín., máx., media, mediana, desviación, cuartiles; para categóricas, moda y categorías más frecuentes en tabla). Sin gráfico de distribución. |
| 3 | `GET /proyectos/{id}/variables/diagnostico?columna=` | 2 | Tres secciones, cada una `null` + `motivo_vacio` si su etapa no existe: **faltantes** (B), **redundancia** (B), **train vs. test** (C). |
| 4 | `GET /proyectos/{id}/variables/causal?columna=&version=` | 4 | Caracterización, aristas incidentes, pares eliminados con frecuencia de eliminación y (si se registraron) conjuntos condicionantes con su p, vecindad de 1–2 saltos, ciclos y avisos que nombran la variable. |

Cuatro endpoints en total. Quedan fuera los de valores, objetivo, relaciones, preparación, modelo y
prescripción (§9). La **fase 3 no añade ningún endpoint**: solo escribe `pc/separadores.json`, que
lee el endpoint 4.

---

## 5. Caché, rendimiento y versión

- **`huella`** = `{sha256 del dataset, hoja, versión del resultado de PC, actualizada_en de cada etapa}`,
  devuelta por el endpoint 1; el cliente la usa en las claves de consulta, así que un cambio de
  etapa invalida solo lo que depende de ella.
- **Caché de DataFrames** (patrón `_cache_modelo`: clave + marca de archivo + cerrojo) con **LRU
  pequeño** (p. ej. 3 entradas en total, medido en memoria con 20.000 × 50): DataFrame crudo por
  `(proyecto, sha256, hoja)` y train/test por `mtime` de `train.csv`/`test.csv`.
  **Solo la usan los endpoints del explorador.** `_cargar`, `_datos_preparados`, `/datos`,
  `/distribucion` y el resto de pantallas siguen exactamente como están (hay una prueba que lo
  verifica: sus respuestas y llamadas no cambian).
- Caché de resultados por `(columna, endpoint, huella)`, también LRU acotado.
- Cliente: una consulta por pestaña, solo cuando está abierta (`enabled`), `staleTime: Infinity`
  con la huella en la clave; cambiar de pestaña no recalcula.
- Sin gráficos con puntos individuales; el grafo local tiene como máximo 1–2 saltos (acotado a un
  número fijo de nodos, con aviso "mostrando N de M vecinos").
- Medición obligatoria con un dataset sintético de 20.000 × 50 al cerrar las fases 1, 2 y 3.
  Objetivo: respuesta en caché < 100 ms y primera respuesta en CSV < 2 s; XLSX depende de la lectura
  y se cachea.

---

## 6. Fases

Cada fase termina con la suite completa comparada contra la línea base (§1). Los commits los hace
el usuario.

### Paso 0 — Línea base

Ejecutar toda la suite, guardar el resultado en `docs/linea_base_pruebas.txt` (versionado) y
registrar versiones (Python, Node, causal-learn). Regenerar `esquema.d.ts` con
`npm run generar-tipos` desde el commit actual y comprobar que **no produce diferencias** respecto
al archivo versionado (así los cambios de tipos posteriores son solo los nuevos).

### Fase 1 — Navegación: lista, encabezado y Resumen básico

- **Núcleo:** `pcapp_nucleo/exploracion/` (convención de `causal/` y `prescripcion/`):
  `estadisticos.py` (descriptivos básicos y cuantiles de una serie) y `modelos.py` (dataclasses de
  los contratos). Faltantes efectivos con la función de los detectores (`mascara_faltantes`), sin
  copiar su regla.
- **Sidecar:** `flujo_exploracion.py` (mixin añadido a `Servicios`), `rutas/exploracion.py`
  (registrado en `aplicacion.py`), modelos al final de `esquemas.py`, caché de DataFrames,
  `huella`, estados A–D. Endpoints 1 y 2.
- **Frontend:** ruta `/proyectos/:id/variables`, entrada de menú, `ListaVariables` (búsqueda,
  filtros por tipo y por estado), `EncabezadoVariable`, pestaña Resumen, `EstadoVacio`. En estado A
  la lista usa `perfilar_columnas` sobre el DataFrame en caché (**decisión 6**).
- **Criterio de salida:** proyecto recién cargado → lista y resumen correctos; 20.000 × 50 dentro
  de los tiempos de §5; la carpeta del proyecto no cambia tras llamar a los endpoints (solo
  lectura); suite sin regresiones.

### Fase 2 — Diagnóstico: faltantes, redundancia, train vs. test

- **Núcleo, refactor sin cambio de comportamiento:** en `detectores_objetivo.py`, separar el
  **cálculo** de la evidencia (prueba, p, % por clase, medianas) de la **decisión** de emitir el
  hallazgo. `detectar_faltantes_dependientes_objetivo` llama a la nueva función y aplica los mismos
  umbrales (`alfa_faltantes_objetivo`, `diferencia_minima_faltantes_objetivo`). Prueba de
  regresión: hallazgos idénticos (campo a campo, incluida la `evidencia`) con todos los datasets de
  `datasets_prueba/` y con los sintéticos de `test_detectores.py`. **Si esto exigiera cambiar un
  hallazgo existente, se detiene el trabajo y se pregunta.**
- **Núcleo, nuevo:** `exploracion/calidad.py` y `exploracion/train_test.py`.
  - Faltantes vs. objetivo: evidencia **sin umbral** + `significativo` (según los mismos umbrales);
    objetivo categórico: % de faltantes por clase; objetivo continuo: Mann-Whitney existente **más**
    % de faltantes por **cuartil** del objetivo, **solo descriptivo** (sin pruebas por cuartil;
    **decisión 4**). Distingue "no evaluada" (sin faltantes, todo faltante o sin objetivo) de
    "evaluada, no significativa".
  - Redundancia: grupo(s) `grupo_redundante` de la columna con sus ρ (de `evidencia.correlaciones`)
    y hallazgos de relaciones que la nombran. Solo lectura de `revision.json`; no se calcula ρ.
    Se muestra como "ρ = 0,87 (Spearman)", sin lenguaje causal.
  - Train vs. test: por variable, n, faltantes, media/mediana/desviación y cuartiles de cada
    conjunto, diferencia estandarizada y una prueba (KS para continuas, χ² para categóricas/binarias)
    con su p, **solo como señal para depurar**. Tabla, sin histogramas (los histogramas son una
    extensión).
- **Sidecar/frontend:** endpoint 3 y pestaña Diagnóstico con tres bloques con estado vacío propio
  ("Ejecute la revisión…", "Prepare los datos…"), badges con ícono + texto y enlaces "Ver en
  Revisión →" / "Ver en Preparación →" (solo navegación a rutas existentes, sin parámetros).
- **Criterio de salida:** suite sin regresiones, prueba de regresión de hallazgos en verde y
  comprobación manual con diabetes (Insulin/SkinThickness: faltantes vs. `Outcome`).

### Fase 3 — Captura de separadores en PC (solo backend, opción A)

Los separadores y la frecuencia de eliminación salen de las mismas corridas del bootstrap.

- **Fuente, de solo lectura.** En `ejecutar_corrida`, *después* de `pc(...)` y sin tocar sus
  argumentos ni la construcción de `dirigidas/sin_orientar`, se lee `grafo.test.pvalue_cache` y se
  reduce a un **registro mínimo transitorio de esa corrida**: para cada par cuya arista quedó
  quitada, los conjuntos condicionantes `S` con `p > α` y su p. No se usa `cg.sepset`, no se guarda
  la caché completa y **no se guardan resultados crudos por corrida**: el registro de cada corrida
  se suma al agregado y se descarta.
- **Qué se guarda por par con arista quitada** (en `pc/separadores.json`):
  - `corridas_quitado`: corridas en que PC quitó la arista.
  - Por cada conjunto condicionante con `p > α`: `corridas` (en cuántas corridas separó al par),
    `p_mediano`, `p_minimo`, `p_maximo`.
  - A nivel de archivo: `prueba`, `alpha`, `max_k`, `n_corridas_validas` (**N**) y
    `corridas_con_registro`.
- **El mediano exacto necesita los valores.** Para no guardar crudos por corrida, el agregado de
  cada (par, conjunto) mantiene en memoria la lista de sus p (como mucho N números por conjunto) y
  **solo al terminar** se escriben mediano, mínimo y máximo, descartando la lista. Esa lista sí
  viaja en el punto de control (`punto_control.json`, que ya se borra al terminar con éxito) para
  poder reanudar. Si el volumen fuese un problema se pregunta antes de pasar a un mediano aproximado.
- **Sin tope arbitrario de conjuntos por par**, para que «todos los conjuntos condicionantes con
  p > α» sea literal. Se mide el tamaño del agregado; si crece de forma descontrolada (muchos
  conjuntos por par con grados altos) **se detiene el trabajo y se pregunta**.
- **Paralelo.** Cada proceso devuelve solo el registro mínimo de *su* corrida y el proceso
  principal lo suma en el mismo punto donde ya suma las matrices (`registrar` → `_Estado.sumar`).
  No hay agregados parciales por proceso que combinar: la suma/unión es conmutativa, así que el
  resultado no depende del orden ni del número de procesos (como ya garantiza el módulo para las
  matrices).
- **Reanudar.** El agregado se guarda en el punto de control **junto con** `corridas_completadas`,
  en la misma operación que ya usa `_guardar_punto_control`; al reanudar se cargan ambos y solo se
  suman las corridas que no estaban en `corridas_completadas`, de modo que ninguna corrida se
  cuenta dos veces. Un punto de control anterior a este cambio (sin la clave nueva) se sigue
  leyendo: el registro queda marcado parcial (`corridas_con_registro < n_corridas_validas`) y la
  interfaz lo indica.
- **Cancelación.** Solo cuentan las corridas completadas y válidas: **N = `corridas_validas`**
  (las fallidas, p. ej. columna constante en la submuestra, no entran). Un resultado cancelado no
  escribe `separadores.json` (igual que hoy no se escribe `resultado.json`); al reanudar y
  completar, se escribe con el N final.
- **Estadístico.** Solo con `fisherz`/`mv_fisherz`, derivado del p (`n` de la submuestra, constante:
  `round(n·fraccion_submuestra)`); con `chisq`/`gsq`, solo el p. Antes de prometer `mv_fisherz` se
  verifica que su caché tenga las mismas claves; si no, se registra solo el p o se omite con
  motivo y **se pregunta**.
- **Siempre activa, sin interruptor.** Nada de esto entra en `firma_analisis`.
- **Prueba de no regresión (obligatoria).** Con la misma semilla, `dirigidas`, `sin_orientar`,
  `bidireccionales`, `corridas_validas` y `resultado.json` idénticos a los de la línea base, en
  secuencial, en paralelo y tras reanudar; y `separadores.json` idéntico entre secuencial y
  paralelo y entre una ejecución continua y una reanudada.
- **Prueba de coherencia (obligatoria).** Para **cada par**:
  `corridas_quitado == N − (dirigidas[i][j] + dirigidas[j][i] + sin_orientar[i][j])` (las matrices
  del bootstrap); además, para cada conjunto `corridas ≤ corridas_quitado` y
  `α < p_minimo ≤ p_mediano ≤ p_maximo`. Las corridas con separador registrado deben ser
  exactamente aquellas en que la arista no aparece; una corrida válida sin registro para un par
  quitado es un fallo.
- **Medición:** coste en tiempo y memoria con 20.000 × 50 y 100 corridas. Si el sobrecoste supera
  el **5 % del tiempo total**, **se detiene el trabajo y se pregunta**.
- **Sin interfaz:** no se toca el frontend ni se añaden endpoints.


### Fase 4 — Pestaña Causal completa y grafo local (estado D)

- **Núcleo:** `exploracion/vecindad.py`: vecindad de 1–2 saltos y pares eliminados a partir de
  `aristas` y `cuentas` del resultado. Solo lectura; la caracterización, las frecuencias y los
  avisos se reutilizan tal cual.
- **Endpoint 4**, con `?version=` (versiones del resultado de PC; por defecto la actual). Si
  `pc/separadores.json` no existe: estado vacío literal **"No registrado en este análisis. Se
  registra en las próximas ejecuciones de PC (re-ejecutar invalida el modelo causal y la
  prescripción)."** **Sin botón para re-ejecutar** desde el explorador (**decisión 2**).
- **Frontend:** `Causal.tsx` y `GrafoLocal.tsx` (cytoscape, mismos estilos y leyenda que
  `GrafoCausal`); tablas con `Table`:
  - Categoría causal con la terminología del núcleo y `a_traves_de`.
  - Aristas incidentes: tipo (`dirigida`/`sin_orientar`/`manual`), frecuencia total y por
    orientación, "ρ = … (asociación)" y signo. Las aristas `sin_orientar` y `manual` llevan
    advertencia en texto ("arista sin orientar: la dirección no está determinada").
  - **«¿Por qué no está conectada?»** Para cada par de la vecindad que PC quitó o dejó bajo el
    umbral, un bloque con la etiqueta **«Bootstrap, N corridas»** que muestra:
    - la frecuencia de eliminación (`corridas_quitado` de N);
    - la lista de conjuntos condicionantes con p > α, **ordenada de mayor a menor k**, donde cada
      fila dice **«separó al par en k de N corridas»** y el **p mediano (rango mín–máx)**; con
      `fisherz`/`mv_fisherz` se añade el estadístico derivado;
    - si el registro es parcial (`corridas_con_registro < N`), se indica en texto.
  - Texto de la interfaz: «conjuntos condicionantes con los que PC encontró independencia»;
    nunca «el conjunto que quitó la arista» ni ninguna mención a una «corrida principal» (no
    existe). La frecuencia de eliminación y los separadores comparten origen (las mismas corridas
    del bootstrap) y denominador (N).
- **Estados vacíos:** sin PC → "Ejecute el análisis (Análisis)"; resultado desactualizado →
  "Rehaga el análisis".
- **Criterio de salida:** en el explorador no aparece nunca "X causa Y"; la nota `origen_candidatas`
  se muestra cuando aplica; suite sin regresiones.

---

## 7. Archivos que se crean o modifican

**Nuevos**

```
nucleo/src/pcapp_nucleo/exploracion/__init__.py, estadisticos.py, calidad.py, train_test.py,
                                    vecindad.py, modelos.py
nucleo/tests/test_exploracion.py, test_pc_separadores.py
sidecar/src/pcapp_servidor/flujo_exploracion.py, rutas/exploracion.py
sidecar/tests/test_exploracion.py
app/src/pantallas/ExploradorVariables.tsx
app/src/componentes/exploracion/ListaVariables.tsx, EncabezadoVariable.tsx, EstadoVacio.tsx,
    Resumen.tsx, Diagnostico.tsx, Causal.tsx, GrafoLocal.tsx
app/src/api/exploracion.ts
app/src/pruebas/datosExploracion.ts, exploracion.test.tsx
docs/linea_base_pruebas.txt
```

**Modificados (mínimo y aditivo)**

| Archivo | Cambio |
|---|---|
| `nucleo/.../detectores_objetivo.py` | Extraer el cálculo de la evidencia; mismos hallazgos (prueba de regresión). |
| `nucleo/.../pc_bootstrap.py` | Captura de separadores (solo lectura tras `pc()`), clave opcional del punto de control; sin tocar el cálculo. |
| `nucleo/.../exportacion.py` / `sidecar/flujo.py` (`_funcion_pc`) | Escribir `pc/separadores.json` junto a los demás archivos de `pc/` (la carpeta ya se archiva entera al desactualizar). |
| `sidecar/.../flujo.py` | `Servicios` hereda también `ServiciosExploracion`. |
| `sidecar/.../aplicacion.py` | Registrar el router. |
| `sidecar/.../esquemas.py` | Modelos nuevos al final. |
| `sidecar/tests/test_seguridad_y_esquemas.py` | Añadir los pares esquema↔dataclass nuevos. |
| `app/src/App.tsx` | Una `<Route>`. |
| `app/src/componentes/NavegacionLateral.tsx` | Una entrada "Explorador de variables" tras las etapas (ícono + texto); `ETAPAS` no cambia. |
| `app/src/api/consultas.ts` | Claves nuevas. |
| `app/src/api/esquema.d.ts` | Regenerado (parte de lo ya versionado). |

`ARCHIVOS["analisis"] = ["pc"]` en `etapas.py` ya archiva toda la carpeta `pc/`, así que
`separadores.json` se archiva al desactualizar el análisis sin cambiar `etapas.py`.

---

## 8. Contrato de tipos

Una sola cadena: dataclass del núcleo → modelo Pydantic en `esquemas.py` → `/openapi.json` →
`esquema.d.ts` → `Esquemas["…"]`. El TS no define interfaces de datos propias.

**Se reutilizan tal cual:** `PerfilColumna`, `Hallazgo`, `AristaAgregada`,
`CaracterizacionVariable`, `AvisoResultado`.

**Nuevos** (nombres provisionales; todos emparejados con su dataclass en la prueba de esquemas):

```
Huella                { sha256, hoja, version_resultado, actualizada: dict[etapa, str] }
EstadosVariable       { a, b, c, d: bool; motivos_vacios: dict[str, str]; huella: Huella }
FilaListaVariable     { nombre, tipo_detectado, porcentaje_faltantes_efectivo, valores_unicos,
                        es_objetivo, categoria_causal?, hallazgos_por_severidad? }
ListaVariables        { estados: EstadosVariable, variables: list[FilaListaVariable] }
ResumenVariable       { perfil: PerfilColumna, faltantes_efectivos, faltantes_centinela,
                        descriptivos: Descriptivos | null, categorias_frecuentes?: list[...] }
Descriptivos          { n, media, mediana, desviacion, minimo, maximo, q1, q3 }

DiagnosticoVariable   { faltantes: FaltantesVariable | null, redundancia: RedundanciaVariable | null,
                        train_test: ComparacionTrainTest | null, motivos_vacios: dict[str, str] }
FaltantesVariable     { evaluada, motivo_no_evaluada?, prueba, p_valor, significativo,
                        porcentaje_por_clase?, diferencia_puntos?, mediana_con?, mediana_sin?,
                        porcentaje_por_cuartil?: list[{desde, hasta, filas, porcentaje_faltantes}],
                        hallazgo?: Hallazgo }
RedundanciaVariable   { grupos: list[list[str]], pares: list[{variable, spearman}], hallazgos: list[Hallazgo] }
ComparacionTrainTest  { train: Descriptivos, test: Descriptivos, diferencia_estandarizada,
                        prueba, p_valor }

CausalVariable        { caracterizacion: CaracterizacionVariable, aristas: list[AristaAgregada],
                        eliminados: list[ParEliminado], vecindad: SubgrafoLocal,
                        ciclos, avisos: list[AvisoResultado], version, etiqueta,
                        separadores_disponibles: bool }
ParEliminado          { variable_a, variable_b, corridas_quitado, n_corridas_validas,
                        frecuencia_eliminacion, frecuencia_aparicion, aceptada,
                        condicionantes?: list[ConjuntoCondicionante] }   # orden: corridas desc.
ConjuntoCondicionante { conjunto: list[str], corridas, p_mediano, p_minimo, p_maximo,
                        estadistico?: float | null, prueba, alpha }
SeparadoresPC         { prueba, alpha, max_k, n_corridas_validas, corridas_con_registro,
                        origen: "bootstrap" }
```

El campo `diagnostico` se llama `DiagnosticoVariable` provisionalmente; **ya existe un modelo con
ese nombre** (`seleccion_prueba.DiagnosticoVariable`, forma de la relación con el objetivo), así
que el nuevo se llamará `DiagnosticoExploracion` para no colisionar.

Terminología: solo `causa_directa`, `causa_indirecta`, `consecuencia`, `ambigua`, `sin_camino`,
`dirigida`/`sin_orientar`/`manual`; lo demás es `spearman`/"asociación".

---

## 9. Pruebas

- **Núcleo:** estadísticos contra `pandas`/`scipy`; regresión de hallazgos de faltantes vs.
  objetivo; no regresión de PC con captura (secuencial, paralelo, reanudación); `lento` con
  datasets reales de `datasets_prueba/` y el sintético de 20.000 × 50.
- **Sidecar:** 409 por etapa; la carpeta del proyecto no cambia tras llamar a los 4 endpoints
  (solo lectura); la caché evita releer el archivo; invalidación al cambiar la huella; las
  respuestas de `/datos` y `/distribucion` no cambian; pares esquema↔dataclass.
- **Frontend:** estados vacíos por etapa (incluido el literal de separadores); ningún texto
  "causa" fuera de la pestaña Causal; badges con ícono y texto; una sola petición por pestaña al
  cambiar entre ellas; solo métodos `GET`.
- **Datasets de prueba:** los de `datasets_prueba/` ya incluidos en la prueba genérica; si el
  usuario añade uno nuevo, entra como siempre.

---

## 10. Posibles extensiones (fuera de alcance)

No se implementan ni se diseñan en detalle; quedan como referencia si el uso interno lo pide:

- Pestaña **Distribución** (histograma, barras, caja y bigotes; hoy existe `VistaDistribucion` y el
  endpoint `/distribucion`).
- Pestaña **Valores** estilo Data Viewer: tabla paginada con orden y filtro en servidor, y valor
  original junto al preparado (unión por `receta.indices_*`).
- Pestaña **Relaciones**: variables con mayor |ρ| frente a la seleccionada (promover
  `pc_bootstrap._spearman` a pública) y heatmap de correlaciones.
- Pestañas **Preparación** (transformaciones de la receta, `Unidades`, columnas one-hot) y
  **Relación con el objetivo** (`diagnosticar_variable` / `DiagnosticoVariable`).
- Pestañas **Modelo** y **Prescripción** (mecanismo, `EfectoParcial`, modificabilidad,
  `ConfiguracionAccion`, supuestos, μ efectivo) y **contrafactuales** (solo enlace a Escenarios).
- **Comparación de variables** lado a lado (sin endpoint propio: composición de los mismos
  endpoints por variable).
- **Enlaces profundos** `?variable=` a Revisión, Preparación, Modelo causal y Prescripción (tocan
  pantallas existentes; hoy se evitan).
- Una corrida adicional de PC sobre todo train como fuente alternativa de separadores (descartada: no existe hoy y cambiaría el comportamiento).

---

## 11. Decisiones registradas

| # | Decisión |
|---|---|
| 1 | Estadístico solo cuando se pueda derivar del p (`fisherz`, `mv_fisherz`); con `chisq`/`gsq`, solo el p. |
| 2 | Análisis previos: estado vacío literal "No registrado en este análisis. Se registra en las próximas ejecuciones de PC (re-ejecutar invalida el modelo causal y la prescripción)."; sin botón de re-ejecución. |
| 3 | Captura siempre activa, sin interruptor; solo pruebas de pares quitados (`p > α`), nunca toda la `pvalue_cache`. |
| 4 | Faltantes por cuartil del objetivo continuo: sí, descriptivo, junto al Mann-Whitney; el cálculo se extrae de la decisión sin cambiar hallazgos. |
| 5 | Sin `?variable=`; no se tocan pantallas existentes. |
| 6 | Estado A: `perfilar_columnas` sobre el DataFrame en caché, faltantes con la definición de los detectores. |
| 7 | Documento en `docs/explorador_variables.md`, versionado. |

| 8 | Opción A: separadores y frecuencias salen de las mismas corridas del bootstrap (no hay «corrida principal»). Agregación durante la ejecución, sin resultados crudos por corrida. |
| 9 | Aprobados: plan, 4 endpoints, fases, redundancia desde `revision.json`, `DiagnosticoExploracion`, umbral del 5 % y comprobación de `mv_fisherz`. |
