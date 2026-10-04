# Explorador de variables — plan de diseño

Estado: **plan, pendiente de aprobación**. No se ha escrito código de la app.
Fecha de la inspección: 2026-10-04. Rama `main`, con cambios locales del usuario en prescripción
(`Caso.tsx`, `Configuracion.tsx`, `prescriptor.py`, `problema.py`, etc.) que este plan no toca.

Ficha técnica interactiva de cada variable, conectada al flujo causal y prescriptivo de
`pc-app`. Se inspira en el Data Viewer y el panel Environment de RStudio, pero no es una copia.

---

## 1. Reglas fijas

> Copiadas tal cual del encargo. No se negocian en la implementación.

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

---

## 2. Hallazgos de la inspección

### 2.1 Arquitectura real (lo que condiciona el plan)

| Capa | Hecho verificado | Consecuencia |
|---|---|---|
| Frontend | Mantine 9 (`Table`, `Tabs`, `Badge`, `Tooltip`, `AppShell`), TanStack Query 5, React Router 8 (`HashRouter`), `@tabler/icons-react`, `cytoscape` (solo el grafo), `openapi-fetch` con tipos generados (`src/api/esquema.d.ts`). Fuente Fira Code. **No hay librería de gráficos ni de tablas.** | Los gráficos serán SVG propios, como ya hace `componentes/modelo_causal/Graficos.tsx` (tokens `--serie-1`, `--viz-*`, claro/oscuro) y `VistaDistribucion.tsx` (barras con `Box`). Sin dependencias nuevas. |
| Frontend | Estado: TanStack Query + proveedores de borrador (`estado/borrador*.tsx`). Claves en `api/consultas.ts` (`claves.*`, prefijos por etapa). `opcional()` convierte el 409 de "etapa no vigente" en `null`. | El explorador no necesita estado global: variable y pestaña en la URL (`useSearchParams`); consultas con `claves.*` nuevas. |
| Navegación | `NavegacionLateral.tsx` recorre `ETAPAS` (`estado/etapas.ts`, espejo de `etapas.py`) y dibuja un `NavLink` por etapa. Rutas en `App.tsx` (`/proyectos/:id/<ruta>`). | El explorador **no es una etapa**: se agrega una entrada aparte después de la lista, sin tocar `ETAPAS`. |
| Sidecar | FastAPI. `Servicios(ServiciosModeloCausal, ServiciosPrescripcion)` en `flujo.py`; routers en `rutas/proyectos.py` y `rutas/prescripcion.py`. Modelos Pydantic en `esquemas.py`, con una prueba (`tests/test_seguridad_y_esquemas.py`) que exige que cada modelo coincida campo a campo con su dataclass del núcleo. | Patrón a seguir: `flujo_exploracion.py` (mixin) + `rutas/exploracion.py` + modelos en `esquemas.py` emparejados con dataclasses del núcleo. |
| Sidecar | Resultados de cada etapa = archivos JSON/CSV en la carpeta del proyecto (`revision.json`, `decisiones.json`, `receta.json`, `preparacion.json`, `train.csv`, `test.csv`, `recomendacion.json`, `pc.json`, `pc/…`, `modelo_causal/…`, `prescripcion/…`). Estado por etapa en SQLite (`etapas`). Al rehacer una etapa, sus archivos y los de las posteriores **se archivan** en `anteriores/` y quedan "desactualizada" (`etapas.py`). | Una etapa desactualizada no tiene archivos vigentes: se trata como inexistente (estado vacío "desactualizada: rehaga X"). Coincide con la regla de no mostrar nada de una etapa que no existe. |
| Sidecar | **No hay caché de DataFrames.** `/datos` y `/distribucion` releen el archivo original en cada petición (`_cargar` → `cargar_dataset`); `_datos_preparados` reaplica toda la receta (`aplicar_receta`) cada vez. Solo existe `_cache_modelo` (por `mtime`) en `flujo_causal.py`. | Para 20.000 × 50 hay que añadir una caché de DataFrames (crudo y train/test) por `(proyecto, sha256, hoja/mtime)`, con el mismo patrón que `_cache_modelo`. Es el cambio de infraestructura más importante. |
| Sidecar | `train.csv`/`test.csv` se guardan **sin índice** (`to_csv(index=False)`); la correspondencia con las filas originales está en `receta.indices_train/indices_test`. | Para unir valor original ↔ preparado se usa la receta, no el CSV. Se puede leer `train.csv` directamente (más barato que `aplicar_receta`). |

### 2.2 Las etapas A–F frente a las etapas reales del sidecar

El sidecar tiene 8 etapas (`revision → decisiones → preparacion → recomendacion / configuracion_pc → analisis → modelo_causal → prescripcion`). El estado del explorador se **calcula en el sidecar** (una sola fuente; el TS solo lo pinta):

| Estado | Condición en el sidecar | Qué habilita |
|---|---|---|
| A | El proyecto existe (archivo copiado, sin etapa necesaria). | Perfil y distribución sobre el dataset original. |
| B | `revision` vigente. | Hallazgos de revisión, grupos redundantes, calidad. |
| C | `preparacion` vigente (implica `decisiones` vigente). | Receta, valores preparados, train vs test, relación con el objetivo, relaciones. |
| D | `analisis` vigente. | Grafo de PC, frecuencias, caracterización. |
| E | `modelo_causal` vigente (y `vigente: true` en `GET /modelo-causal`, que además exige que la versión de PC coincida). | Mecanismo, efectos parciales, rol en el modelo. |
| F | `prescripcion` vigente (configuración guardada). | Modificabilidad, restricciones, supuestos, participación en la prescripción. |

`recomendacion` y `configuracion_pc` no son estados del explorador, pero `recomendacion.json` aporta datos reutilizables (diagnósticos de forma de la relación, §3).

### 2.3 Respuestas concretas

#### a) ¿Qué datos existen y se pueden reutilizar?

| Dato | Dónde se calcula (núcleo) | Dónde se guarda / sirve (sidecar) | ¿Listo para el explorador? |
|---|---|---|---|
| **Perfil de columna** (tipo, faltantes NaN, % faltantes, únicos, mín., máx.) | `perfilado.perfilar_columna` → `modelos.PerfilColumna` | `revision.json` → `GET /proyectos/{id}/revision` (`perfiles_columnas`) | Sí. **Ojo:** `faltantes` cuenta solo NaN; los *centinelas* ("?", "NA") los cuentan los detectores (`detectores_objetivo.mascara_faltantes`, `detectores.contar_centinelas`). Se debe usar esa definición para "faltantes efectivos". |
| **Hallazgos de revisión** (por columna: faltantes, ceros, constante, casi constante, identificador, texto libre, fecha, categórica, ordinal, asimetría, copias, recodificación, derivadas, correlación casi perfecta, mezcla de unidades, faltantes dependientes del objetivo, tamaño efectivo…) | `revision.revisar_dataset` → `Hallazgo` (con `evidencia`, `acciones_posibles`, `identificador`) | `revision.json` (`hallazgos`) | Sí: se filtran por `columnas_involucradas`. |
| **Grupos redundantes** | `detectores_relaciones.detectar_grupos_redundantes` (componentes conexas con `|ρ Spearman| ≥ umbral_spearman_grupo_redundante`; `evidencia.correlaciones` lista cada par con su ρ) | Hallazgos `grupo_redundante` en `revision.json`; `flujo._grupos_redundantes` los extrae; `CaracterizacionVariable.grupo_redundante` | Sí. |
| **Matriz de Spearman** | `pc_bootstrap.matriz_spearman(train, variables)` (pares con filas completas, `None` si no se puede) | `pc/resultado.json` → clave `spearman` (**no** va en `GET /resultado`, que la omite; sí en la descarga `resultado.json` de `/archivos`). Cada `AristaAgregada` lleva su `spearman` y `signo`. | Solo para pares de variables de PC y a partir de D. Para C (sin PC) falta calcular ρ de una variable contra las demás: reutilizando `pc_bootstrap._spearman` (hoy privada; se promueve a pública sin cambiar su lógica). |
| **Receta de preparación** | `preparacion.Receta` (`columnas: list[MetadatosColumna]` con `tipo_final`, `transformaciones`, `parametros`; `decisiones`; `separacion_aplicada`; `indices_train/test`) | `receta.json`, `GET /preparacion` (`EstadoPreparacion.resumen`), `ResumenPreparacion.columnas` | Sí. |
| **Unidades originales** | `causal.unidades.Unidades(receta.columnas)`: `a_original`, `describir`, agrupa one-hot por `columna_original` | Se construye con los metadatos de la receta; hoy solo se usa dentro del modelo causal | Sí, y **no depende del modelo**: se instancia con `receta.columnas`. |
| **Train/test** | `preparacion.preparar` / `_separar`; `distribucion_objetivo` | `train.csv`, `test.csv`, `preparacion.json` (`distribucion_objetivo` train y test, `faltantes_restantes`) | Datos sí; **la comparación variable a variable train vs test no existe** (hay que crearla, §4). |
| **Diagnóstico de forma vs objetivo** (ρ Spearman con el objetivo, p por intervalos, curva por cuantiles, monotonía) | `seleccion_prueba.diagnosticar_variable` → `DiagnosticoVariable` | `recomendacion.json` (`diagnosticos`) → `GET /recomendacion`. Solo existe si se ejecutó la recomendación (opcional en el flujo) y solo para columnas continuas. | Reutilizable; si no hay recomendación vigente, el endpoint nuevo llama a la misma función `diagnosticar_variable` sobre train. |
| **Grafo de PC** | `pc_bootstrap.agregar_cuentas` → `GrafoAgregado` / `AristaAgregada` (tipo `dirigida`/`sin_orientar`/`manual`, frecuencias, ρ, signo); `ciclos_dirigidos` | `pc/resultado.json`; `GET /resultado?version=` (`ResultadoPC`); versiones en `pc/versiones/<n>/` | Sí. |
| **Frecuencias de bootstrap** | `ResultadoBootstrap.dirigidas / sin_orientar` (cuentas enteras de todos los pares) | `resultado.json` (`cuentas`, y `matrices.frecuencia_dirigida/frecuencia_sin_orientar` ya expuestas en `ResultadoPC`) | Sí, para **todos** los pares, no solo los aceptados. |
| **Caracterización** (causa directa / indirecta / consecuencia / ambigua / sin camino, `a_traves_de`, `frecuencia_con_objetivo`, `grupo_redundante`, `modificable`) | `caracterizacion.caracterizar` | En `ResultadoPC.caracterizacion` | Sí. Con la nota `origen_candidatas`: las candidatas pueden venir de la lista de modificables de PC o de la de prescripción (`flujo._con_candidatas`). |
| **Candidatas prescriptivas y modificabilidad** | `Caracterizacion.candidatas_prescriptivas`; `prescripcion.configuracion.variables_prescriptivas` (prescriptivas / sin_camino / desconocidas); `pc.json.modificables` | `ResultadoPC`, `GET /prescripcion/configuracion` (`VistaConfiguracionPrescripcion`) | Sí. |
| **Modelo causal** (subgrafo, padres, rol raíz/intermedia/objetivo, mediana/mín./máx. de train, mecanismo y su selección, efectos parciales, calibración) | `causal.modelo.construir_modelo`, `causal.subgrafo.subgrafo_objetivo`, `causal.mecanismos` | `modelo_causal/modelo_causal.json` + `evaluacion.json` → `GET /modelo-causal` (resumen, `evaluacion`, `controles`, `vigente`); caché en memoria `_cache_modelo` | Sí. `EfectoParcial` (curva + histograma de train por padre) ya viene listo para dibujar. |
| **Motor de contrafactuales** | `causal.contrafactuales.contrafactual` | `POST /modelo-causal/contrafactual`, `GET /modelo-causal/casos` | **No se reutiliza para calcular** (regla "sin cálculos causales alternativos"): el explorador solo enlaza a la pantalla de Escenarios. |
| **Configuración de prescripción** (`ConfiguracionAccion`: permitida, dirección, mín., máx., cambio máximo, costo, estados permitidos; `Supuestos`; objetivo deseado; μ) | `prescripcion.configuracion` | `prescripcion/prescripcion.json` → `GET /prescripcion/configuracion` | Sí. |
| **Estadísticos descriptivos** (media, mediana, desviación, cuartiles, asimetría, curtosis, moda, IQR, atípicos) | **No existen.** Solo hay mín./máx. en `PerfilColumna`, el histograma de 20 intervalos y el top‑20 de categorías (`flujo.describir_distribucion`, que vive en el sidecar). | — | Hay que crearlos en el núcleo. |
| **Valores de la columna con paginación** | No existe (`/datos` devuelve solo las 20 primeras filas). | — | Crear. |

#### b) ¿PC guarda el separador, la prueba, el estadístico y el p‑valor de cada arista eliminada?

**No.** Lo que hoy se guarda de PC:

- `ejecutar_corrida` (`pc_bootstrap.py`) llama a `causallearn.pc(...)` y **solo conserva** tres matrices de adyacencia (`dirigidas`, `sin_orientar`, bidireccionales) extraídas de `grafo.G.graph`. El resto del objeto `CausalGraph` se descarta al terminar cada corrida.
- `ejecutar_bootstrap` suma esas matrices (`_Estado.sumar`); el punto de control (`punto_control.json`) y `resultado.json` solo contienen **cuentas por par**.
- La **prueba** sí queda registrada, pero globalmente (`ConfiguracionPC.prueba`, `alpha`, `max_k`), no por arista.

Qué existe en `causal-learn` y se pierde (verificado en el código instalado, `.venv/.../causallearn`):

| Dato | ¿Está en el objeto que devuelve `pc()`? |
|---|---|
| Conjunto separador | **Sí, parcialmente**: `cg.sepset[i][j]`. Con `stable=True` (el que usa la app) es la **unión** de las variables de *todos* los conjuntos condicionantes que dieron independencia en la profundidad en que se quitó la arista, no «el» conjunto que la quitó. Además `append_value` puede duplicarlo (se visita (x,y) y (y,x)). |
| p‑valor | **Sí**: `cg.test.pvalue_cache` guarda el p de cada prueba hecha, con clave `"i;j|s1.s2"`. Filtrando las claves del par con `p > alpha` se recuperan exactamente los conjuntos que declararon independencia y su p. |
| Estadístico | **No se guarda.** Para `fisherz`/`mv_fisherz` se puede recuperar a partir del p (`X = Φ⁻¹(1 − p/2)`, con `X = √(n−|S|−3)·|Z|`); para `chisq`/`gsq` no (depende de los grados de libertad). |
| Profundidad / `max_k` | Se deduce de `len(S)`. Una arista que **sobrevive** porque `max_k` cortó la búsqueda no está "probada hasta ese tamaño": hay que poder distinguirlo. |

**Frecuencia de eliminación en el bootstrap: ya se puede obtener hoy, sin cambiar nada.** PC parte del grafo completo y, tras el esqueleto, solo orienta (no quita aristas); las prohibiciones por niveles son unidireccionales (`prohibiciones_por_niveles`), así que ninguna arista se quita por conocimiento previo. Por tanto, para un par (i, j):

```
frecuencia de eliminación = 1 − (dirigidas[i][j] + dirigidas[j][i] + sin_orientar[i][j]) / corridas_validas
```

es la fracción de corridas en que PC lo eliminó en el esqueleto. Los datos están en `resultado.json` (`cuentas`) y las matrices de frecuencia ya llegan al frontend (`ResultadoPC.matrices`). Matiz que la interfaz debe mostrar: un par **ausente del grafo agregado** puede haberse conservado en algunas corridas pero por debajo del umbral (`umbral_frecuencia`); no equivale a "PC nunca lo vio".

**Propuesta para exponer separador y p‑valor sin cambiar el comportamiento ni los resultados (captura solo lectura):**

1. En `ejecutar_corrida`, *después* de `pc(...)` y sin tocar sus argumentos ni la construcción de `dirigidas/sin_orientar`, leer `grafo.sepset` y `grafo.test.pvalue_cache` y reducirlos a un registro compacto por par eliminado: separador (unión, ordenado), conjunto con mayor p y su p, profundidad. Nada de lo que ya se devuelve cambia.
2. Agregarlos dentro del proceso (el registro por corrida es ≤ n·(n−1)/2 pares; para 50 variables, ≤ 1.225): por par, número de corridas por separador (se guardan los 3 más frecuentes) y mediana/rango intercuartílico del p. Como cada corrida usa una submuestra distinta, **no existe un único separador/p por par**: se informa el más frecuente y la dispersión, nunca un valor "verdadero".
3. Guardarlo en un archivo nuevo y opcional `pc/separadores.json` (no en `resultado.json`, para no acoplarlo a la reagregación ni a las versiones) y en una clave nueva, opcional, del punto de control (los puntos de control antiguos se siguen leyendo; si faltan, el registro queda marcado como parcial: `corridas_con_registro < corridas_validas`). Ninguno de estos datos entra en `firma_analisis`.
4. Estadístico: devolver `null` salvo con `fisherz`/`mv_fisherz`, donde se deriva del p; documentarlo en el contrato. Es una decisión a confirmar (ver §9).
5. **Prueba de no regresión obligatoria:** con la misma semilla, `dirigidas`, `sin_orientar`, `bidireccionales`, `corridas_validas` y `resultado.json` deben ser idénticos con la captura activada y desactivada (en secuencial y en paralelo, y tras reanudar desde un punto de control).
6. Los análisis ya hechos **no tienen** esos datos: el explorador muestra "No registrado en este análisis; vuelva a ejecutar el análisis" (esto invalida modelo causal y prescripción, y el texto debe avisarlo).

Riesgos a vigilar: coste de memoria/tiempo de leer `pvalue_cache` por corrida (se mide en la fase 4 con 20.000 × 50), y que `mv_fisherz` use otra estructura de caché (comprobarlo con prueba antes de prometerlo).

#### c) ¿`detectores_objetivo.py` detecta faltantes que dependen del objetivo?

**Sí, parcialmente** — `detectar_faltantes_dependientes_objetivo` (`detectores_objetivo.py`), tipo de hallazgo `faltantes_dependientes_objetivo`, severidad alta:

- **Objetivo categórico (binario/multiclase):** tabla (faltante × clase) y χ² (o Fisher en tablas 2×2 con esperados < 5). Sí compara el **% de faltantes por clase** (`evidencia.porcentaje_faltantes_por_clase`, `diferencia_puntos`, `p_valor`, `prueba`).
- **Objetivo continuo:** **no** compara % de faltantes por rangos del objetivo. Hace Mann‑Whitney del *valor del objetivo* entre filas con y sin faltante (`mediana_objetivo_con_faltante/sin_faltante`).
- Usa `mascara_faltantes` (NaN **y** centinelas), a diferencia del perfil.

Limitaciones para el explorador:

1. **Solo emite hallazgo si supera los umbrales** (`alfa_faltantes_objetivo` y, en categórico, `diferencia_minima_faltantes_objetivo`); si no, no queda rastro. El explorador no podría distinguir "no depende" de "no se evaluó" ni mostrar el % por clase de una variable no marcada.
2. Omite las columnas sin faltantes o totalmente faltantes y las filas sin objetivo.
3. No hay desglose por rangos (cuantiles) del objetivo continuo.

Cambio propuesto (exponer lo que ya calcula, sin alterar hallazgos): separar en `detectores_objetivo.py` el **cálculo** de la evidencia (prueba, p, % por clase, medianas) de la **decisión** de emitir el hallazgo; el detector sigue llamando a la misma función y aplicando los mismos umbrales (prueba de regresión: mismos hallazgos con los datasets de `datasets_prueba/`). El explorador usa la función de cálculo directamente y añade `significativo: bool` según los umbrales. El desglose por cuantiles del objetivo continuo (% de faltantes por cuartil) es **cálculo nuevo de visualización**, se marca como tal y vive en el núcleo.

#### d) ¿Qué falta y cuáles son los endpoints mínimos?

Falta (todo en núcleo/sidecar, nada en TS):

1. Caché de DataFrames (crudo y train/test) en el sidecar.
2. Estadísticos descriptivos, atípicos y valores paginados.
3. Evidencia de faltantes‑vs‑objetivo sin umbral (refactor sin cambio de comportamiento).
4. Comparación train vs test por variable.
5. ρ de Spearman de una variable contra las demás (reutilizando `_spearman`).
6. Mapa columna original → columnas preparadas (one‑hot, exclusiones, columna de fecha) a partir de la receta.
7. Vecindad local del grafo (1–2 saltos) y eliminación por par a partir de `cuentas`; captura de separadores/p (§2.3 b).
8. Estado por etapa A–F y "huella" de versión para la caché.

Endpoints mínimos: ver §3.

---

## 3. Endpoints (adaptados a la API real)

Convenciones tomadas de la API existente: router propio bajo `/proyectos/{proyecto_id}`; **la columna va como parámetro de consulta `columna`** (como en `/distribucion`; los nombres pueden llevar espacios o caracteres especiales); errores `404/409/422` con el cuerpo uniforme `{error:{codigo,mensaje,detalles}}`; 409 `ETAPA_REQUERIDA` cuando la etapa no está vigente (el cliente lo convierte en estado vacío con `opcional()`). Todos son **GET**, sin escritura, sin trabajos en segundo plano. No se modifica ningún endpoint existente.

| # | Endpoint | Etapa | Contenido | Se apoya en |
|---|---|---|---|---|
| 1 | `GET /proyectos/{id}/variables` | A | Lista ligera para el panel lateral: nombre, tipo detectado, % faltantes, únicos, indicadores (hallazgos por severidad, grupo redundante, rol: objetivo/modificable/categoría causal…), estados A–F disponibles y `huella` de versión. Con `?q=` y filtros; paginada solo si hay > 200 variables. | `PerfilColumna`, `Hallazgo`, `Caracterizacion`, `GestorEtapas.vigentes` |
| 2 | `GET …/variables/resumen?columna=` | A | Perfil + estadísticos descriptivos + cuantiles + atípicos + distribución (reusa `describir_distribucion` / `Distribucion`). | `perfilado`, nuevo `exploracion.estadisticos` |
| 3 | `GET …/variables/valores?columna=&pagina=&orden=&filtro=` | A→C | Página de valores (50 filas, como `casos`), orden y filtro en servidor; en C, el valor preparado al lado, unido por la receta. | caché DataFrame, `receta.indices_*` |
| 4 | `GET …/variables/calidad?columna=` | B | Faltantes efectivos (NaN + centinelas), ceros sospechosos, atípicos, hallazgos de la columna (con "Ver en Revisión →"), grupo redundante con sus ρ, **faltantes vs objetivo** (evidencia sin umbral + `significativo`). | `revision.json`, `detectores_objetivo` (refactor), `detectores_relaciones` |
| 5 | `GET …/variables/preparacion?columna=` | C | Decisión aplicada (excluida, faltantes, codificación, conversión, logaritmo), `MetadatosColumna`, columnas resultantes, unidades originales, **train vs test** (distribución, diferencia estandarizada, prueba KS/χ²), faltantes restantes. | `Receta`, `Unidades`, nuevo `exploracion.train_test` |
| 6 | `GET …/variables/objetivo?columna=` | C | Relación con el objetivo: distribución por clase o curva por cuantiles, ρ, `DiagnosticoVariable` (de `recomendacion.json` o calculado con `diagnosticar_variable`). | `seleccion_prueba` |
| 7 | `GET …/variables/relaciones?columna=&limite=` | C | Las N variables con mayor \|ρ\| frente a esta (sobre train) + pares de los grupos redundantes. Muestra "ρ = 0,42", sin lenguaje causal. | `pc_bootstrap._spearman` (promovida a pública) |
| 8 | `GET …/variables/causal?columna=&version=` | D | Categoría de caracterización (`a_traves_de`, `frecuencia_con_objetivo`), aristas incidentes (tipo, frecuencias, ρ, signo, `justificacion`), **vecindad de 1–2 saltos** para el grafo local, ciclos que la incluyen, avisos del resultado que la nombran, **eliminación por par** (`1 − frecuencia`), y separadores/p si existen (`separadores.json`). | `ResultadoPC`, `cuentas`, `avisos_resultado` |
| 9 | `GET …/variables/modelo?columna=` | E | Rol (raíz/intermedia/objetivo), padres e hijos, mecanismo y su selección, efecto parcial por padre (`EfectoParcial`), tipo de control y rango en unidades originales (`ControlVariable`); aviso si el modelo no está `vigente`. | `GET /modelo-causal`, `descripcion_variables` |
| 10 | `GET …/variables/prescripcion?columna=` | F | Modificable (PC vs prescripción), ¿prescriptiva?, `ConfiguracionAccion`, `Supuestos` y su confirmación, μ efectivo, enlaces a Configuración/Caso. | `GET /prescripcion/configuracion` |

Comparación de variables (fase 5): **sin endpoint propio**; el cliente pide en paralelo los mismos endpoints por variable y los alinea en columnas. Así no hay lógica nueva ni caché duplicada.

Enlaces de salida (solo navegación, nunca escritura): `/proyectos/:id/revision`, `/decisiones`, `/preparacion`, `/configuracion`, `/resultados`, `/modelo-causal`, `/prescripcion`. Opcional y aditivo (a confirmar, §9): un parámetro `?variable=` que las pantallas actuales ignoren si no lo entienden.

**Caché y rendimiento (transversal a todos los endpoints):**

- `huella` = `{sha256 del dataset, hoja, versión del resultado de PC, `actualizada_en` de cada etapa}`. Se devuelve en el endpoint 1.
- Servidor: caché en memoria de DataFrames por `(proyecto, sha256, hoja)` (crudo) y por `mtime` de `train.csv`/`test.csv` (preparado), con el patrón de `_cache_modelo` y un cerrojo; resultados por `(variable, endpoint, huella)` con límite de tamaño (LRU). Se invalida solo al cambiar la huella.
- Gráficos: histograma de 20 intervalos, top‑20 de categorías y "otros", cuantiles para curvas, **máximo ~500 puntos** en cualquier dispersión (muestra con semilla fija, indicando "muestra de N de M"). Nunca todos los puntos.
- Cliente: una consulta por pestaña activa (`enabled` solo si la pestaña está abierta), `staleTime: Infinity` con la `huella` en la clave; cambiar de pestaña no recalcula.
- Medir con un dataset sintético de 20.000 × 50 antes de dar por buena cada fase (objetivo: respuesta en caché < 100 ms; primera respuesta < 2 s en CSV; XLSX depende de la lectura y se cachea).

---

## 4. Qué se reutiliza y qué se crea

### Reutiliza (sin tocar su lógica)

`perfilado`, `revision` / `Hallazgo`, `detectores_relaciones` (grupos redundantes), `Receta` + `Unidades`, `diagnosticar_variable`, `pc_bootstrap.matriz_spearman` / cuentas, `caracterizacion`, `reagregacion.avisos_resultado`, `causal.subgrafo`, `descripcion_variables`, `EfectoParcial`, `prescripcion.configuracion`, `flujo.describir_distribucion`, el patrón `_cache_modelo`, `GestorEtapas`, `opcional()`, `VistaDistribucion`/`Graficos.tsx` como base visual.

### Crea

**Núcleo** — paquete `pcapp_nucleo/exploracion/` (misma convención que `causal/` y `prescripcion/`):

| Módulo | Contenido |
|---|---|
| `estadisticos.py` | Descriptivos, cuantiles, atípicos (regla IQR) de una serie → dataclass. |
| `calidad.py` | Faltantes efectivos, hallazgos por columna, faltantes vs objetivo (usa la función extraída de `detectores_objetivo`). |
| `train_test.py` | Comparación de una variable entre train y test. |
| `relaciones.py` | ρ de Spearman de una variable frente a las demás. |
| `vecindad.py` | Vecindad de k saltos y eliminación por par a partir de `cuentas` y `aristas` del resultado. |
| `modelos.py` | Dataclasses de los contratos nuevos (espejadas en `esquemas.py`). |

Refactors mínimos en módulos existentes, **sin cambio de comportamiento** y con prueba de regresión: `detectores_objetivo.py` (extraer la evidencia), `pc_bootstrap.py` (hacer pública `_spearman`; captura de separadores, fase 4).

**Sidecar:** `flujo_exploracion.py` (mixin `ServiciosExploracion`, añadido a `Servicios` como los otros dos), `rutas/exploracion.py` (registrado en `aplicacion.py`), modelos nuevos al final de `esquemas.py`, caché de DataFrames.

**Frontend** (siguiendo la convención observada):

```
app/src/
├─ pantallas/ExploradorVariables.tsx          # ruta /proyectos/:id/variables
├─ componentes/exploracion/
│  ├─ ListaVariables.tsx                      # panel lateral: búsqueda, filtros, badges
│  ├─ EncabezadoVariable.tsx                  # nombre, tipo, rol, estados por etapa
│  ├─ EstadoVacio.tsx                         # "qué paso genera esto" + enlace
│  ├─ pestanas/Resumen.tsx, Distribucion.tsx, Valores.tsx, Calidad.tsx,
│  │            ObjetivoRelacion.tsx, Relaciones.tsx, Preparacion.tsx,
│  │            TrainTest.tsx, Causal.tsx, Modelo.tsx, Prescripcion.tsx
│  ├─ GrafoLocal.tsx                          # cytoscape, reutiliza estilos de GrafoCausal
│  ├─ Comparar.tsx
│  └─ graficos/ Histograma.tsx, Barras.tsx, CajaBigotes.tsx, Curva.tsx   # SVG propio
├─ api/exploracion.ts                         # hooks useQuery; claves en consultas.ts
├─ estado/exploracion.ts                      # solo formato/etiquetas (sin estadística)
└─ pruebas/datosExploracion.ts, exploracion.test.tsx
```

Cambios en archivos existentes (mínimos): `App.tsx` (una `<Route>`), `NavegacionLateral.tsx` (una entrada "Explorador de variables" tras la lista de etapas, con ícono + texto; `ETAPAS` no cambia), `api/consultas.ts` (claves nuevas), `esquema.d.ts` (regenerado con `npm run generar-tipos`; hoy tiene cambios locales sin commit del usuario: regenerar tras integrarlos).

---

## 5. Contrato de tipos (sin sistema paralelo)

Una sola cadena: dataclass del núcleo → modelo Pydantic en `esquemas.py` → `/openapi.json` → `esquema.d.ts` → `Esquemas["…"]` en el cliente. El TS **no define interfaces de datos propias**.

**Modelos existentes que se reutilizan tal cual** (ya generados): `PerfilColumna`, `Hallazgo`, `Distribucion` (+`Categoria`, `Histograma`), `DiagnosticoVariable`, `MetadatosColumna`, `AristaAgregada`, `CaracterizacionVariable`, `AvisoResultado`, `ControlVariable`, `InfoVariableModelo`, `ResumenMecanismo`, `EfectoParcial`, `ConfiguracionAccion`, `Supuestos`, `ProblemaAplicabilidad`.

**Modelos nuevos**, que *componen* los anteriores (nombres provisionales, ya en la terminología del núcleo):

```
EstadosVariable        { a,b,c,d,e,f: bool; motivos_vacios: dict[str,str]; huella: Huella }
Huella                 { sha256, hoja, version_resultado, actualizada: dict[etapa,str] }
FilaListaVariable      { nombre, tipo_detectado, porcentaje_faltantes, valores_unicos,
                         hallazgos_por_severidad: {alta,media,baja}, es_objetivo,
                         categoria_causal?, modificable?, grupo_redundante? }
ListaVariables         { estados: EstadosVariable, variables: list[FilaListaVariable] }

Descriptivos           { n, media, mediana, desviacion, minimo, maximo, q1, q3, iqr,
                         asimetria, curtosis, moda, atipicos, limite_inferior, limite_superior }
ResumenVariable        { perfil: PerfilColumna, descriptivos: Descriptivos | null,
                         distribucion: Distribucion }
PaginaValores          { total, pagina, por_pagina, filas: list[{indice, original, preparado?, conjunto?}] }
CalidadVariable        { faltantes_efectivos, faltantes_nulos, faltantes_centinela,
                         valores_centinela, hallazgos: list[Hallazgo],
                         grupo_redundante: GrupoRedundante | null,
                         faltantes_objetivo: FaltantesObjetivo | null }
FaltantesObjetivo      { prueba, p_valor, significativo, porcentaje_por_clase?,
                         diferencia_puntos?, mediana_con?, mediana_sin?, por_cuantil? }
PreparacionVariable    { decision: …(TratamientoColumna, Codificacion, ConversionUnidades reutilizados),
                         metadatos: list[MetadatosColumna], excluida: bool, motivo_exclusion?,
                         unidades: ControlVariable-like, train_test: ComparacionTrainTest }
ComparacionTrainTest   { histograma_comun, train: Distribucion, test: Distribucion,
                         diferencia_estandarizada?, prueba, p_valor }
RelacionObjetivo       { medida, diagnostico: DiagnosticoVariable | null, por_clase? | curva? }
RelacionesVariable     { vecinas: list[{variable, spearman, n_pares}], grupo_redundante? }
CausalVariable         { caracterizacion: CaracterizacionVariable, aristas: list[AristaAgregada],
                         eliminaciones: list[EliminacionPar], vecindad: SubgrafoLocal,
                         ciclos, avisos: list[AvisoResultado], version, etiqueta }
EliminacionPar         { variable_a, variable_b, frecuencia_eliminacion, frecuencia_aparicion,
                         aceptada, separadores?: SeparadorPar | null }       # separadores: fase 4
SeparadorPar           { separador_frecuente, corridas_con_ese_separador, corridas_registradas,
                         p_mediana, p_q1, p_q3, estadistico?: number | null, prueba }
ModeloVariable         { rol, padres, hijos, mecanismo: ResumenMecanismo, efectos: list[EfectoParcial],
                         control: ControlVariable | null, vigente: bool, motivo_desactualizado? }
PrescripcionVariable   { modificable_pc, modificable_prescripcion, prescriptiva,
                         accion: ConfiguracionAccion | null, supuestos: Supuestos | null,
                         mu_efectivo, aviso }
```

Cada dataclass nueva se añade a la lista de pares de `tests/test_seguridad_y_esquemas.py`, de modo que la API y el núcleo no se desincronicen. Los campos opcionales (`?`) existen porque cada pestaña solo se rellena si su etapa existe; el estado vacío se decide con `EstadosVariable`, no inspeccionando `null` en TS.

**Terminología:** el contrato usa exclusivamente `causa_directa`, `causa_indirecta`, `consecuencia`, `ambigua`, `sin_camino`, `dirigida`/`sin_orientar`/`manual`. Cualquier relación no causal se llama `spearman` / "asociación". Las aristas `sin_orientar` y `manual` llevan un campo/etiqueta de advertencia en la interfaz ("arista sin orientar: la dirección no está determinada").

---

## 6. Interfaz (guía común a todas las fases)

- Pantalla única en `/proyectos/:id/variables`. Izquierda: lista de variables (búsqueda, filtros por tipo/estado/hallazgo, orden), densa, una fila por variable con ícono de tipo, mini‑indicador de faltantes y badges. Derecha: encabezado de la variable + pestañas (`Tabs` de Mantine). Variable y pestaña en la URL (`?v=…&t=…`).
- Las pestañas se montan y consultan **solo al abrirse** (`keepMounted={false}` + `enabled`). Las pestañas de una etapa inexistente **se muestran deshabilitadas con su estado vacío explicativo** al abrirse (qué paso la genera + botón de navegación), nunca vacías ni con datos viejos.
- Estados siempre con **ícono + texto**: `IconCircleCheck` "Vigente", `IconClockExclamation` "Desactualizada", `IconCircleDashed` "Pendiente"; severidades `alta/media/baja` con ícono distinto además del color. Sin depender solo del color (la navegación actual usa un punto de color: no se replica).
- Gráficos grandes (ancho completo del panel), SVG propio con los tokens de `Graficos.tsx` en claro y oscuro, tooltips con valores exactos. Sin tarjetas grandes: tablas densas, `Text size="sm"`, `Divider`, definición en rejilla de 2 columnas para estadísticos.
- Textos de interpretación: ρ siempre "ρ = 0,42 (Spearman, n = …)", con el recordatorio permanente "asociación, no causalidad" en las pestañas Relaciones y Objetivo. En la pestaña Causal solo vocabulario del núcleo.
- Solo lectura: ningún botón de guardar. Los únicos botones son enlaces ("Ver en Revisión →", "Ver en Preparación →", "Ver en Modelo causal →", …).

---

## 7. Fases

Cada fase termina con: pruebas del núcleo y del sidecar en verde, `npm run comprobar-tipos`, `npm test`, y comprobación manual en la app con un dataset real de `datasets_prueba/` (diabetes) y con uno sintético de 20.000 × 50 para medir tiempos. Los commits los hace el usuario.

### F1 — Base, lista de variables, encabezado, Resumen y Distribución (estado A)

- **Infraestructura sidecar:** caché de DataFrames crudo; `flujo_exploracion.py`, `rutas/exploracion.py`; `Huella` y `EstadosVariable`.
- **Núcleo:** `exploracion/estadisticos.py` (descriptivos, cuantiles, atípicos).
- **Endpoints:** #1 (lista) y #2 (resumen + distribución).
- **Frontend:** ruta, entrada de menú, `ListaVariables`, `EncabezadoVariable`, pestañas Resumen y Distribución, gráficos SVG `Histograma`, `Barras`, `CajaBigotes`, `EstadoVacio`.
- **Ajuste respecto al encargo:** la lista usa `perfiles_columnas`, que sale de `revision.json` (estado B). En A puro (antes de revisar) no existe perfil guardado: el endpoint #1 llama a `perfilar_columnas` sobre el DataFrame en caché. Se hace así para que A funcione sin ejecutar la revisión, sin duplicar lógica (misma función del núcleo).
- **Criterio de salida:** proyecto recién cargado → lista y distribución correctas; 20.000 × 50: lista < 2 s, cambio de variable en caché < 100 ms; sin escrituras (comprobado en prueba: la carpeta del proyecto no cambia).

### F2 — Valores, Calidad, hallazgos de revisión y redundancia (estado B)

- **Núcleo:** extraer la evidencia de `detectar_faltantes_dependientes_objetivo` (con prueba de regresión: mismos hallazgos que antes en todos los datasets de `datasets_prueba/`); `exploracion/calidad.py`.
- **Endpoints:** #3 (valores paginados, orden y filtro en servidor, solo datos originales) y #4 (calidad).
- **Frontend:** pestañas Valores (tabla paginada), Calidad (faltantes efectivos con distinción nulos/centinelas, ceros, atípicos, lista de hallazgos con severidad ícono+texto, grupo redundante con sus ρ, faltantes vs objetivo con % por clase o medianas) y enlaces "Ver en Revisión →".
- **Estados vacíos:** sin revisión → "Ejecute la revisión del dataset (Revisión)".
- **Nota:** hay que decidir cómo mostrar "no evaluado" vs "no significativo" en faltantes vs objetivo (§9).

### F3 — Relación con el objetivo, Relaciones, Preparación y train vs. test (estado C)

- **Núcleo:** `exploracion/train_test.py`, `exploracion/relaciones.py`; promover `_spearman`; mapa columna original → preparadas (one‑hot, exclusión, fecha) desde la receta; uso de `Unidades(receta.columnas)` para valores en unidades originales.
- **Caché:** lectura directa de `train.csv`/`test.csv` (no `aplicar_receta`).
- **Endpoints:** #5, #6, #7; #3 se extiende con el valor preparado y el conjunto (train/test) vía `receta.indices_*`.
- **Frontend:** pestañas Preparación (transformaciones en orden: conversión → log → codificación → imputación → normalización, con parámetros), Train vs test (histogramas superpuestos con el mismo binning), Objetivo (curva por cuantiles / distribución por clase), Relaciones (tabla ordenada por |ρ| + mini‑barras).
- **Estados vacíos:** sin preparación → "Prepare los datos (Preparación)"; sin recomendación, la forma de la relación se calcula igualmente con `diagnosticar_variable`.
- **Riesgo:** ρ de una variable contra 49 con 20.000 filas ≈ 49 `spearmanr` (< 1 s esperado, a medir); si pesa, se cachea por variable.

### F4 — Pestaña Causal y grafo local (estado D)

- **Núcleo:** `exploracion/vecindad.py` (vecindad k saltos, eliminación por par desde `cuentas`); **captura de separadores/p‑valores** (§2.3 b) con su prueba de no regresión y el archivo `pc/separadores.json`.
- **Endpoint:** #8, con `?version=` (versiones del resultado de PC).
- **Frontend:** `Causal.tsx` y `GrafoLocal.tsx` (cytoscape; mismo estilo y leyenda que `GrafoCausal`; las aristas sin orientar y manuales con trazo/etiqueta distintos y advertencia en texto). Tabla de aristas incidentes (frecuencia total, orientada, sin orientar, ρ y signo, entre paréntesis "asociación"). Tabla de pares eliminados con frecuencia de eliminación y, si existe, separador más frecuente y p mediana (con rango); si no existe: "No registrado en este análisis".
- **Estados vacíos:** sin PC → "Ejecute el análisis (Análisis)"; resultado desactualizado → "Rehaga el análisis".
- **Criterio de salida:** en el explorador no aparece nunca "X causa Y"; las candidatas se explican con la nota `origen_candidatas`.

### F5 — Prescripción, contrafactuales y comparación de variables (estados E–F)

- **Endpoints:** #9 y #10.
- **Frontend:** pestañas Modelo (rol, mecanismo, efecto parcial con su histograma de train; aviso si el modelo no está vigente) y Prescripción (modificable según PC y según prescripción, ¿prescriptiva?, restricciones y supuestos tal como están configurados, μ efectivo, enlaces a Configuración y a Caso/Lote). **Contrafactuales:** solo enlace "Ver en Modelo causal → Escenarios" (no se calcula nada aquí).
- **Comparación:** vista lado a lado de 2–4 variables (mismos endpoints por variable, en paralelo; sin endpoint nuevo): perfil, calidad, ρ con el objetivo, categoría causal, rol, modificabilidad. Selección desde la lista; resultado en la URL.
- **Estados vacíos:** sin modelo → "Construya el modelo causal (Modelo causal)"; sin configuración → "Configure la prescripción (Prescripción)".
- **Criterio de salida:** comprobación manual de que no hay ningún `POST/PUT/DELETE` desde el explorador (prueba automática sobre el cliente: solo se llaman `GET`).

---

## 8. Pruebas (por capa)

- **Núcleo** (`nucleo/tests/test_exploracion.py`): estadísticos contra `pandas`/`scipy` en casos conocidos; regresión de hallazgos de faltantes‑vs‑objetivo; no regresión de PC con captura de separadores (secuencial, paralelo, reanudación); dataset sintético 20.000 × 50 en una prueba marcada `lento`.
- **Sidecar** (`sidecar/tests/test_exploracion.py`): 409 por etapa; la carpeta del proyecto no cambia tras llamar a todos los endpoints (solo lectura); caché (la segunda llamada no relee el archivo); invalidación al cambiar la huella; el par esquema↔dataclass nuevo en `test_seguridad_y_esquemas.py`.
- **Frontend** (`pruebas/exploracion.test.tsx`, fixtures en `datosExploracion.ts`, como `datosModeloCausal.ts`): estados vacíos por etapa; ningún texto "causa" fuera de la pestaña Causal; badges con ícono y texto; una sola petición por pestaña al cambiar entre ellas; solo métodos `GET`.
- **Datasets de prueba:** el explorador se ejercita con los datasets de `datasets_prueba/` ya incluidos en las pruebas; si el usuario añade uno nuevo, entra en la prueba genérica como siempre.

---

## 9. Decisiones que necesito confirmar antes de empezar

1. **Estadístico de la prueba de independencia:** guardar solo el p‑valor y derivar el estadístico únicamente con `fisherz`/`mv_fisherz` (`null` con `chisq`). Alternativa: no mostrarlo nunca.
2. **Análisis ya existentes:** no tienen separadores/p‑valores y registrarlos obliga a re‑ejecutar PC (invalida modelo causal y prescripción). ¿Aceptas el estado vacío "no registrado en este análisis", sin migración?
3. **Captura de separadores:** ¿activa siempre (coste pequeño pero no nulo, a medir en F4) o con un interruptor en la configuración de PC? Recomiendo siempre activa si la medición es aceptable.
4. **Faltantes vs objetivo continuo:** además de Mann‑Whitney (ya existe), ¿quieres el desglose "% de faltantes por cuartil del objetivo"? Es cálculo nuevo de visualización.
5. **Enlaces profundos** (`?variable=` en Revisión/Preparación/Modelo causal): tocan pantallas existentes de forma aditiva. ¿Se permiten o el explorador solo enlaza a la pantalla?
6. **Estado A sin revisión:** la lista usa `perfilar_columnas` sobre el DataFrame en caché cuando no existe `revision.json` (ver F1). ¿De acuerdo?
7. **Ubicación de este documento:** `docs/` no existía; se creó en la raíz del repositorio (`ScottyPC/docs/`), no dentro de `pc-app/`. Indícame si prefieres `pc-app/docs/`.
