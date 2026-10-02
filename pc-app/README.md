# pc-app

Aplicación de escritorio para investigación sobre modelos prescriptivos.

## Objetivo del proyecto

El paquete `pcapp_nucleo` valida, revisa y prepara datasets y ejecuta el descubrimiento causal.
Comprueba que el dataset cumple las condiciones mínimas, perfila cada columna, detecta
problemas de calidad y relaciones sospechosas, aplica las decisiones de preparación del
usuario de forma reproducible, recomienda la prueba de independencia, ejecuta PC con
bootstrap y caracteriza cada variable respecto al objetivo (causa directa, indirecta,
consecuencia...) para identificar candidatas prescriptivas.

**El revisor solo informa y sugiere acciones: nunca modifica, corrige ni elimina datos.**
Las transformaciones ocurren únicamente en la preparación, según las decisiones que el
usuario revisa y confirma.

El sidecar (servidor FastAPI local con almacenamiento SQLite) expone todo el flujo por HTTP;
ver [`sidecar/README.md`](sidecar/README.md). El frontend **todavía está pendiente**.

## Arquitectura actual

```
pc-app/
├── nucleo/            Paquete Python del núcleo (funcional)
│   ├── pyproject.toml
│   ├── src/nucleo/
│   └── tests/
├── sidecar/           Servidor local FastAPI que expone el núcleo (funcional)
├── app/               Aplicación de escritorio Tauri v2 + React (ver app/README.md)
└── datasets_prueba/   Datasets reales y sintéticos para pruebas
```

| Componente     | Tecnología prevista                     | Estado                    |
|----------------|-----------------------------------------|---------------------------|
| Núcleo         | Paquete Python independiente (`pcapp_nucleo`) | Revisión, preparación, PC con bootstrap, caracterización, modelo causal y prescripción |
| Sidecar        | FastAPI local en Python                 | Funcional                 |
| Frontend       | Tauri v2 + React + Vite + TypeScript    | Funcional (ver app/README.md) |
| Almacenamiento | SQLite + archivos locales               | Funcional (en el sidecar) |

El núcleo no depende de ningún componente de presentación.

### Módulos de `pcapp_nucleo`

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
| `pc_config.py` | Configuración de PC: prueba, bootstrap, niveles, modificables y orientaciones manuales. |
| `pc_bootstrap.py` | PC con bootstrap (paralelo, progreso, cancelación, puntos de control) y agregación del grafo. |
| `caracterizacion.py` | Categoría de cada variable respecto al objetivo y candidatas prescriptivas. |
| `exportacion.py` | `resultado.json`, `aristas.csv`, `mascara.csv`, `matriz_frecuencias.csv` y `grafo.png`. |
| `reagregacion.py` | Reagregar el resultado con otro umbral u otras orientaciones manuales sin volver a ejecutar PC; migración de resultados antiguos; advertencias de interpretación. |
| `informe.py` | Informe HTML autocontenido (se abre sin conexión) y resúmenes de decisiones y separación. |
| `prescripcion/` | Optimizador de prescripciones: `configuracion.py` (configuración y variables prescriptivas), `condiciones.py`, `problema.py` (restricciones, función objetivo y evaluador vectorizado), `optimizadores.py` (gradiente proximal y genético, pulido, cierre y recorte), `prescriptor.py` (resultado por caso y explicación), `calibracion.py` (μ con train), `lotes.py` (lotes y evaluación), `referencia.py` e `informe.py` (CSV y HTML). |
| `causal/` | Modelo causal estructural sobre el resultado de PC: `aplicabilidad.py` (bloqueantes y advertencias), `subgrafo.py` (objetivo y ancestros), `mecanismos.py` (candidatos, validación cruzada, parsimonia, GAM de pyGAM y su serialización), `modelo.py` (construcción, evaluación, modelo de referencia, curvas, guardar y cargar), `contrafactuales.py` (abducción–acción–predicción) y `unidades.py` (unidades originales ↔ preparadas con la receta). |
| `cli.py`, `cli_preparacion.py`, `cli_pc.py`, `cli_comun.py` | Interfaz de línea de comandos (`python -m pcapp_nucleo`). |
| `modelos.py`, `configuracion.py`, `utilidades.py` | Dataclasses de resultados, umbrales centralizados y serialización a JSON. |

## Flujo

```
archivo → carga → validación ─┬─ errores bloqueantes → se informan y se detiene
                              └─ válido → revisión (perfil + detectores) → InformeRevision
                                  → plantilla de decisiones → el usuario revisa y edita
                                  → preparación → train / test + receta
                                  → selección de la prueba de independencia
                                  → configuración de PC (niveles, modificables)
                                  → PC con bootstrap → grafo agregado → caracterización
                                  → modelo causal (objetivo y ancestros) → escenarios «¿qué pasa si…?»
                                  → prescripción (intervención mínima que alcanza el objetivo)
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
| `plantilla.aplicar_elecciones(informe, elecciones)` | `InformeRevision`, `{identificador: accion}` | `DecisionesUsuario` | Única implementación del paso acciones → decisiones; los hallazgos sin elección usan la sugerida. `ErrorEleccion` si el hallazgo o la acción no existen. |
| `preparacion.preparar(df, objetivo, decisiones, separacion=None)` | DataFrame, objetivo, decisiones y `ConfiguracionSeparacion` | `DatosPreparados` | Aplica las decisiones, separa y registra la `Receta` (única fuente de la separación). Lanza `ErrorPreparacion`. |
| `preparacion.separacion_sugerida(decisiones, heredada=None)` | Decisiones | `ConfiguracionSeparacion` | Valor inicial cuando aún no hay receta: la de un archivo de decisiones antiguo (`separacion_heredada`), temporal si hay una fecha reservada o estratificada. |
| `preparacion.evaluar_columnas(columnas)` | Metadatos de las columnas finales | `LimiteColumnas` | `ok`, `lento` (más de 30) o `bloqueado` (más de 50), con el mensaje y lo que aporta cada one-hot. |
| `preparacion.aplicar_receta(df, receta)` | DataFrame original y receta | `DatosPreparados` | Reproduce exactamente train y test sin volver a aprender nada. |
| `seleccion_prueba.recomendar_prueba(datos)` | `DatosPreparados` | `RecomendacionPrueba` | Prueba sugerida, motivo, evidencia, alternativas y tiempo estimado. Usa solo train. |
| `seleccion_prueba.evaluar_eleccion(recomendacion, prueba, max_k)` | Recomendación y elección del usuario | `EvaluacionEleccion` | Advertencias (con su campo) si la elección contradice los datos y el tiempo estimado con ella. |
| `pc_config.problemas_configuracion(config, variables, objetivo)` | `ConfiguracionPC` | `list[ProblemaConfiguracion]` | Todos los errores con la ruta de su campo; `advertencias_configuracion` avisa si el objetivo no está en el último nivel. |
| `pc_bootstrap.ejecutar_bootstrap(datos, config, progreso, cancelacion, punto_control, reanudar, al_decidir_modo)` | `DatosPreparados`, `ConfiguracionPC` | `ResultadoBootstrap` | Cuentas de aristas por corrida. Usa solo train. |
| `pc_bootstrap.agregar(resultado, datos, config, spearman=None)` | `ResultadoBootstrap` | `GrafoAgregado` | Aristas aceptadas, orientación, orientaciones manuales, signo y ciclos. `spearman`: matriz de `matriz_spearman(train, variables)` (ρ de todos los pares). |
| `reagregacion.reagregar(contenido, umbral, orientaciones)` | `resultado.json` (con cuentas) | `Reagregacion` | Mismas reglas que `agregar` y `caracterizar`, sin datos ni PC. Con el umbral y las orientaciones originales reproduce el resultado exacto. Lanza `ErrorReagregacion` (subclase de `ErrorConfiguracionPC`) con cada problema y su campo, p. ej. una orientación contraria a los niveles o sin justificación. |
| `reagregacion.migrar_resultado(contenido, spearman)` | `resultado.json` antiguo | `resultado.json` con cuentas | Reconstruye las cuentas desde las frecuencias guardadas (exacto con menos de 10 000 corridas válidas). |
| `reagregacion.avisos_resultado(contenido, hallazgos, prueba_recomendada)` | `resultado.json` | `list[AvisoResultado]` | Corridas fallidas, ciclos, aristas débiles (del 40 % al umbral, destacando las del objetivo), aristas que solo aparecen por bajar el umbral, grupos redundantes, tamaño efectivo y prueba distinta de la recomendada. |
| `informe.informe_html(contenido, receta, avisos, png, versiones, version, nombre, fecha)` | Una versión del resultado | HTML | Datos y hash, decisiones, separación, configuración original y ajustes de la versión, grafo, caracterización, aristas, advertencias e historial de versiones. |
| `caracterizacion.caracterizar(grafo, resultado, modificables, grupos)` | `GrafoAgregado` | `Caracterizacion` | Categoría de cada variable y candidatas prescriptivas. |
| `exportacion.exportar(carpeta, ...)` | Resultados | Archivos | Escribe los resultados en una carpeta. |

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
unidades (`si columna > umbral: (x − restar) × multiplicar`) y logaritmos.

**La separación no forma parte de las decisiones**: se elige al preparar y se guarda solo
en la receta (`Receta.separacion`, versión 2 de la receta). Las decisiones antiguas que aún
tengan `separacion` se leen igual y ese valor solo se usa como valor inicial mientras no hay
receta; las recetas versión 1 se leen tomando la separación de sus decisiones. Las fechas
detectadas (`columnas_fecha_disponibles`) nunca son variables: la acción
`separacion_temporal` solo la reserva para poder separar por ella.

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

Con más de 30 columnas finales (el one-hot suma una por categoría) PC será lento; con más
de 50, la aplicación no continúa (la terminal solo lo advierte).

La receta JSON guarda todas las decisiones, la separación, los índices de train y test, los
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

## PC con bootstrap

La configuración (`ConfiguracionPC`, editable como `<nombre>_pc.json`) define la prueba
(`fisherz`, `mv_fisherz`, `chisq` o `kci`), alpha, las corridas de bootstrap, la fracción de
cada submuestra, el umbral de frecuencia, `max_k`, la semilla, los procesos, los **niveles**
(nada de un nivel posterior puede causar algo de uno anterior; cada variable en exactamente
un nivel), las variables **modificables** y las **orientaciones manuales** (con su
justificación). La plantilla pone todas las variables en un nivel y el objetivo después.
`nombres_niveles` (opcional) da un título a cada nivel; se usa en las columnas de `grafo.png`.

- **Reproducible:** la corrida `k` usa una submuestra sin reemplazo generada con
  `SeedSequence([semilla, k])` y PC es determinista, así que el resultado es idéntico con
  cualquier número de procesos, en cualquier orden y al reanudar.
- **Modo de ejecución** (`modo_ejecucion`, o `--modo` en la terminal):
  - `adaptativo` (por defecto): ejecuta la primera corrida en el propio proceso y la mide.
    Si el tiempo estimado del resto supera `umbral_paralelo_s` (30 s), mide una segunda
    corrida (la primera incluye costos de arranque que pueden multiplicar su duración) y,
    si aun así se supera, reparte el resto entre `procesos` procesos (por defecto,
    núcleos − 1). Abrir los procesos cuesta unos 15–20 s en Windows, así que con corridas
    rápidas es mejor seguir en secuencial.
  - `secuencial` o `paralelo`: fuerzan el modo.

  El modo nunca cambia el resultado. `resultado.json` registra en `ejecucion` el modo
  solicitado y el usado, los procesos, los tiempos medidos y el motivo de la elección.
  Tiempos de referencia (100 corridas): vino tinto 11 s en secuencial frente a 28 s en
  paralelo; salud fetal con `chisq` 19,6 min en secuencial frente a 3,6 min en paralelo.
- **Progreso y cancelación:** un callback `(completadas, total, segundos)` por corrida y un
  evento de cancelación (`is_set()`). En paralelo, cancelar termina las corridas en curso;
  el resultado parcial se marca `completo = False`. En la terminal, Ctrl+C cancela.
- **Puntos de control:** cada `punto_control_cada` corridas (y al cancelar) se guarda
  `punto_control.json` con las matrices acumuladas, la lista de corridas completadas y
  fallidas y una firma de la configuración y los datos; `--reanudar` continúa desde ahí.
- **Corridas fallidas** (matriz singular, columna constante en la submuestra): se
  descartan y se informan; las frecuencias se calculan sobre las corridas válidas.
- **Agregación:** una arista se acepta si aparece (en cualquier orientación) en al menos
  `umbral_frecuencia` de las corridas válidas; su orientación es la más frecuente entre
  i→j, j→i y sin orientar (empate: sin orientar). Después se aplican las orientaciones
  manuales a las aristas sin orientar. El signo es el de la correlación de Spearman en train.
  Los ciclos se informan, no se corrigen.
- **Caracterización** respecto al objetivo: `causa_directa`, `causa_indirecta` (indica por
  qué variables pasa), `consecuencia`, `ambigua` (solo conectada mediante aristas sin
  orientar) o `sin_camino`, con la frecuencia de la arista con el objetivo (aunque esté bajo
  el umbral) y el grupo redundante del revisor. **Candidatas prescriptivas:** causas directas
  o indirectas marcadas como modificables.

Archivos en `<nombre>_pc/`:

| Archivo | Contenido |
|---|---|
| `resultado.json` | Configuración, receta de origen (hash), corridas válidas y fallidas, tiempo, aristas, matrices de frecuencia, ciclos, caracterización y advertencias (base para el frontend). Además, `cuentas` (cuentas exactas del bootstrap), `spearman` (ρ de todos los pares con train) y `agregacion` (umbral y orientaciones manuales usados): con ellos se reagrega sin volver a ejecutar PC. |
| `aristas.csv` | Origen, destino, tipo (dirigida / sin_orientar / manual), frecuencia total y por dirección, signo. |
| `mascara.csv` | 1 si se acepta la arista origen→destino (una sin orientar pone 1 en ambas direcciones). |
| `matriz_frecuencias.csv` | Frecuencia de origen→destino más la frecuencia sin orientar. |
| `grafo.png` | Variables en columnas por nivel; objetivo en rojo, causas directas en verde; aristas azules (positivas) o rojas (negativas), discontinuas si no están orientadas. |

Las matrices usan el formato de pandas: primera columna con los nombres, fila = origen,
columna = destino.

**Reagregación.** `reagregacion.reagregar` rehace el grafo con otro umbral u otras
orientaciones manuales a partir de `cuentas` y `spearman`, con las mismas funciones que el
análisis (`agregar_cuentas` y `caracterizar`): con los parámetros originales el resultado es
idéntico y subir el umbral nunca agrega aristas. Una orientación manual debe respetar los
niveles y llevar justificación. La configuración de la ejecución no cambia: el umbral y las
orientaciones de cada versión quedan en `agregacion`. Los resultados anteriores (sin
`cuentas`) se completan con `migrar_resultado`.

## Modelo causal estructural

Se construye sobre una versión del resultado de PC y sirve para cualquier dataset que cumpla
las condiciones de aplicabilidad; no hay código específico de ningún dataset. Solo entra al
modelo el **subgrafo del objetivo y sus ancestros** (por aristas dirigidas o manuales).

**Aplicabilidad** (`evaluar_aplicabilidad`): lista de problemas con código, severidad,
mensaje, acción que lo resuelve y pantalla donde se hace.

| Bloqueantes | Advertencias |
|---|---|
| Resultado de PC incompleto o desactualizado | Faltantes sin imputar en el subgrafo (se imputan con la mediana de train) |
| El objetivo no tiene causas directas | Intermedias binarias (el contrafactual es aproximado) |
| Aristas sin orientar que tocan el subgrafo, o ciclos en él (se agrupan en un solo problema) | Intermedia mal explicada (R² < 0,10 o exactitud balanceada < 0,60 en validación cruzada; tras ajustar) |
| Objetivo multiclase (agrupar clases en Decisiones) | Variables fuera del subgrafo (se ignoran) |
| Menos de 10 filas de train por padre en algún mecanismo; con objetivo binario, menos de 10 casos de la clase minoritaria por padre del objetivo | Costo de la parsimonia, pesos de clase y rescate del GAM (tras ajustar) |

**Mecanismos** (uno por variable con padres, solo con train). Se comparan dos candidatos con
validación cruzada de 5 pliegues (estratificada si la variable es binaria):

| Variable | Simple | Complejo |
|---|---|---|
| Intermedia continua | Regresión lineal | Splines cúbicos restringidos (nodos en percentiles) + Ridge |
| Intermedia binaria | Regresión logística | GAM logístico (pyGAM) |
| Objetivo binario | Regresión logística | GAM logístico (pyGAM) |
| Objetivo continuo | Regresión lineal | GAM lineal (pyGAM) |

- **Parsimonia:** se elige el complejo solo si mejora la métrica (R² o exactitud balanceada)
  en al menos `umbral_parsimonia` (0,02). Si todos los padres son discretos, el complejo
  coincidiría con el simple y no se considera. El usuario puede forzar uno u otro (queda
  registrado como `manual`).
- **Términos del GAM:** spline para los padres con 10 o más valores distintos y término
  lineal para los demás; `lam` por UBRE/GCV (búsqueda de pyGAM sobre una rejilla fija).
- **Monotonía del GAM del objetivo:** por defecto, restricción monótona en los padres cuya
  relación con el objetivo es monótona según los diagnósticos de la recomendación de prueba,
  en la dirección del signo de Spearman; sin restricción en los no monótonos (relaciones en
  U). Editable por padre; se registra si fue automática o manual.
- **Calibración:** el objetivo binario se ajusta **sin pesos de clase** para que las
  probabilidades estén calibradas; el desbalance se compensa con el **umbral de decisión**,
  elegido en validación cruzada para maximizar la exactitud balanceada y guardado en el
  modelo. Los pesos de clase son un override que advierte que las probabilidades dejan de
  estar calibradas.
- **Rescate si pyGAM no converge** (pyGAM solo lo imprime; se captura): `lam` × 10 y × 100;
  si se usaban pesos de clase, después sin pesos; si nada converge, se usa el modelo simple.
  Todo queda registrado.
- **Raíces:** conservan su valor observado; no tienen mecanismo.

**Evaluación:** para cada mecanismo, la métrica en validación cruzada y en test y los
coeficientes (lineales) o curvas con su signo. Para el objetivo: exactitud balanceada, AUC y
Brier en validación cruzada (predicciones fuera de pliegue) y **una sola vez** en test,
curva de calibración y la comparación con un **modelo de referencia** (regresión logística o
lineal con todas las variables preparadas). Si el mecanismo del objetivo es claramente peor
(diferencia > `umbral_referencia`, 0,02), se advierte el costo de la parsimonia. Curvas de
efecto parcial (dependencia parcial sobre las filas de train) de cada padre, en unidades
originales, con el histograma de train.

**Contrafactuales** (`contrafactual(modelo, caso, intervenciones)`):

- *Abducción:* las intermedias continuas guardan el residuo aditivo del caso. Una intermedia
  binaria se modela como X = 1[η(padres) + U > 0] con U logística (así P(X = 1) = σ(η)); se
  toman 200 muestras de U de la logística truncada al intervalo compatible con el valor
  observado (U > −η si X = 1; U ≤ −η si X = 0), con semilla fija, y el resultado promedia
  las muestras. Es una aproximación de Monte Carlo; sin intermedias binarias es exacto.
- *Acción:* «desplazar» suma una cantidad y «fijar» asigna un valor, en unidades originales.
  Solo tiene efecto sobre ancestros del objetivo; sobre otras variables el cambio es cero y
  se advierte. No se puede intervenir el objetivo ni sus consecuencias. Una categoría
  one-hot se interviene siempre como grupo (fijar la categoría pone su dummy en 1 y las demás
  en 0; la de referencia deja todas en 0), nunca una dummy suelta. Los valores fuera del
  rango de train se calculan y se marcan como extrapolación.
- *Predicción:* orden topológico; el objetivo es su probabilidad (o valor esperado), sin
  residuo. La traza indica qué variable cambió, cuánto y la contribución de cada padre.
- *Caso:* una fila de test (por su índice) o valores propios en unidades originales. Una raíz
  sin valor toma la mediana de train y una intermedia sin valor, la predicción de su
  mecanismo (con aviso).

**Unidades:** `causal/unidades.py` usa la receta para pasar de unidades originales a
preparadas y al revés (logaritmo, códigos de binarias, ordinales y agrupaciones, min–max).
Las conversiones de unidades condicionales no se deshacen: las «unidades originales» son las
del dataset ya convertido.

**Reproducibilidad.** `modelo_causal.json` guarda el grafo usado (versión y sha256 del
`resultado.json`), los mecanismos elegidos con sus parámetros ajustados, las puntuaciones de
los candidatos, las decisiones de monotonía, el umbral de decisión, la semilla, el hash del
train, las versiones de las librerías y una **huella** (sha256 de las predicciones de todos
los mecanismos sobre train). El GAM se guarda por sus **parámetros ajustados** (información de
cada término, nudos extremos y coeficientes), no con pickle ni reajustando al cargar:
reajustar depende del solver y de BLAS y no garantiza los mismos bits, y un pickle es
inseguro al abrirlo y frágil entre versiones. Al cargar se reconstruye el objeto de pyGAM con
esos parámetros (pyGAM está fijado en 0.12.0) y las predicciones son idénticas bit a bit; la
huella lo comprueba. El modelo queda ligado a la versión del resultado de PC: si cambia esa
versión o una etapa anterior, queda desactualizado.

## Prescripción

Se construye sobre el motor de contrafactuales del modelo causal y funciona con cualquier
dataset que tenga un modelo causal vigente y al menos una **variable prescriptiva**: ancestro
del objetivo y modificable. La lista de modificables es propia de la prescripción (empieza con
la de la configuración de PC) y cambiarla solo desactualiza la prescripción; Resultados indica
con qué lista calcula sus candidatas prescriptivas.

**Condiciones** (`evaluar_prescribibilidad`, mismo formato que la aplicabilidad). Bloqueantes:
modelo causal no vigente; ninguna variable prescriptiva («Con estos datos no hay variables
prescriptivas», con el motivo); declaración de supuestos sin confirmar. Advertencias:
modificables sin camino al objetivo (se ignoran), costo de la parsimonia del modelo causal e
intermedias binarias (Monte Carlo).

**Configuración** (`prescripcion.json`, serializable): objetivo deseado (dirección y
probabilidad o valor; por defecto el umbral de decisión ± 0,1), y por variable: permitida,
dirección (subir, bajar o ambas), límites absolutos y cambio máximo en unidades originales (por
defecto el rango de train y el 25 % de ese rango), costo por unidad de la escala normalizada y,
para binarias, ordinales y categorías one-hot (como grupo), los estados permitidos. μ automático
o manual, optimizador y la **declaración de supuestos** por variable (se puede modificar con
una decisión real, se mide antes del resultado, no forma parte de la definición del objetivo),
que el usuario confirma y queda guardada con fecha.

**Función objetivo** (escala normalizada: d = cambio / rango de train):
`max(0, brecha)² + μ · (Σ costo_i · |d_i| + Σ costo_j · [cambia el estado j])`, con brecha =
deseado − p (subir) o p − deseado (bajar), y p de la propagación completa por el grafo con los
residuos del caso. Un evaluador vectorizado propaga muchas combinaciones de acciones en una
sola llamada; solo recalcula las variables que descienden de alguna acción.

**Optimizadores** (misma interfaz y mismo resultado; deterministas con la semilla derivada de la
del modelo y del caso):
- *Gradiente proximal* (por defecto): diferencias finitas, paso proximal (soft-threshold
  lr·μ·costo, que deja exactamente en cero los cambios innecesarios), proyección a la caja de
  límites, cambio máximo y dirección, y búsqueda lineal. Las acciones discretas se enumeran si
  hay 16 combinaciones o menos (optimizando las continuas en cada una) o se recorren por
  coordenadas. Multiarranque: el valor actual y 4 puntos al azar.
- *Genético*: torneo, cruce BLX-α (continuas) y uniforme (discretas), mutación, elitismo y
  reparación recortando a la caja.
- *Intermedias binarias*: para que el gradiente no sea cero, el optimizador usa σ((η + U)/τ) en
  vez de 1[η + U > 0]; el resultado y el éxito se deciden **siempre con el motor exacto**.
- *Post-proceso común*: pulido (quita las acciones cuya retirada no empeora la pérdida), cierre
  (con la penalización el óptimo queda un poco antes del objetivo; si con las mismas acciones se
  puede alcanzar dentro de las restricciones, se escala hasta el mínimo que lo alcanza) y recorte
  (quita las acciones sin las que, volviendo a cerrar, se sigue alcanzando con un costo
  prácticamente igual). Fijar una intermedia con un cambio despreciable equivale a **mantenerla
  constante** (corta el efecto que le llega de otras acciones) y se presenta así.

**Calibración de μ** (solo train, trabajo): sobre los casos de train que no cumplen el objetivo,
el μ más grande de la rejilla (0,001 a 0,1) con el que al menos el 95 % de los casos
**alcanzables** (los que llegan al objetivo con μ = 0, dentro de las restricciones) lo alcanza;
si ninguno, el más pequeño y una advertencia. Cada caso resuelve μ = 0 y después la rejilla de
menor a mayor, arrancando desde la solución anterior (un solo arranque); la prescripción final
usa multiarranque, y el informe lo dice. Los casos se reparten entre procesos; el resultado es
idéntico en paralelo y en secuencial. Se guarda la rejilla con sus tasas.

**Resultado por caso**: acciones (antes, después y cambio en unidades originales) ordenadas por
contribución (cuánto baja el logro si se quita solo esa acción), acciones sin cambio,
probabilidad o valor antes y después, si se alcanza, traza de propagación y marcas
(extrapolación, Monte Carlo y `requiere_revision` si el modelo de referencia, evaluado sobre el
perfil propagado, discrepa). Si no se puede alcanzar: la mejor solución posible (sin penalizar
el costo), cuánto falta y las restricciones activas (las que, relajadas, acercarían al objetivo).
Un caso que ya cumple no recibe acciones. La explicación se genera con plantillas.

**Modos**: caso individual (fila de test o valores propios); lote (casos de test que no cumplen
el objetivo, o un CSV con las columnas ORIGINALES, al que `preparacion.preparar_nuevos` aplica la
receta sin aprender nada e informando las filas que no se pueden preparar); evaluación sobre test
(éxito, no alcanzables, cambio medio por acción, % de acciones en cero, % con revisión,
sensibilidad al cambio máximo y a μ, comparación de optimizadores con McNemar exacta y un texto
que aclara que es una evaluación interna). Lotes y evaluaciones se guardan numerados.
Exportación: CSV de prescripciones e informe HTML autocontenido.

## Uso desde la terminal

```bash
python -m pcapp_nucleo revisar <archivo> --objetivo <columna> [--hoja <nombre>]
python -m pcapp_nucleo plantilla <archivo> --objetivo <columna> [--hoja <nombre>]
python -m pcapp_nucleo preparar <archivo> --objetivo <columna> --decisiones <json>
    [--hoja <nombre>] [--test 0.3] [--semilla 42] [--fecha <columna> [--corte AAAA-MM-DD]]
python -m pcapp_nucleo sugerir-prueba <receta.json> [--sin-estimacion]
python -m pcapp_nucleo plantilla-pc <receta.json>
python -m pcapp_nucleo pc <receta.json> --config <pc.json> [--procesos N] [--modo adaptativo|secuencial|paralelo] [--reanudar]
```

Ejemplo completo con un dataset real:

```bash
python -m pcapp_nucleo plantilla datasets_prueba/diabetes.csv --objetivo Outcome
# editar datasets_prueba/diabetes_decisiones.json
python -m pcapp_nucleo preparar datasets_prueba/diabetes.csv --objetivo Outcome \
    --decisiones datasets_prueba/diabetes_decisiones.json
python -m pcapp_nucleo sugerir-prueba datasets_prueba/diabetes_receta.json
python -m pcapp_nucleo plantilla-pc datasets_prueba/diabetes_receta.json
# editar datasets_prueba/diabetes_pc.json (niveles, modificables)
python -m pcapp_nucleo pc datasets_prueba/diabetes_receta.json --config datasets_prueba/diabetes_pc.json
```

Archivos generados, junto al archivo de entrada: `<nombre>_revision.json`,
`<nombre>_decisiones.json`, `<nombre>_receta.json`, `<nombre>_train.csv`,
`<nombre>_test.csv`, `<nombre>_recomendacion.json`, `<nombre>_pc.json` y la carpeta
`<nombre>_pc/`. **Nunca se sobrescribe un archivo existente**: se añade `_2`, `_3`, etc.
(con el mismo número para la receta y sus CSV). `--reanudar` es la única excepción:
continúa el análisis interrumpido en su propia carpeta.

Códigos de salida:

| Código | Significado |
|---|---|
| `0` | Comando completado. |
| `1` | Error de argumentos o de ejecución (archivo inexistente, hoja inexistente, decisiones o configuración no aplicables, receta de un archivo modificado, análisis de PC cancelado...). |
| `2` | Dataset no válido (errores bloqueantes de validación). |

En Windows, si la consola muestra mal las tildes, ejecute con `python -X utf8 -m pcapp_nucleo ...`.

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

Dependencias: `pandas`, `numpy`, `openpyxl`, `scipy`, `scikit-learn`, `causal-learn`
(que incluye `matplotlib` y `networkx`) y `pygam` 0.12.0 (fijado, porque el modelo causal
guarda sus parámetros internos); `pytest` para desarrollo. pyGAM 0.12 exige `scipy<1.17`,
por eso scipy queda acotado.

## Pruebas

```bash
cd nucleo
pytest
```

Las pruebas de aceptación con datos reales (`tests/test_aceptacion_datos_reales.py`) se
omiten automáticamente si falta alguno de los archivos de `datasets_prueba/`.

Las pruebas de aceptación de PC (`tests/test_aceptacion_pc.py`: vino tinto, diabetes y
salud fetal, 100 corridas cada una) están marcadas como `lento` y **no** se ejecutan con
`pytest`. Para correrlas (unos 4 minutos en paralelo; `-s` muestra tiempos y causas):

```bash
cd nucleo
pytest -m lento -s
```
