# Aplicación de escritorio

Tauri v2 + React + Vite + TypeScript, con Mantine, TanStack Query y React Router. La
interfaz está en español. Toda la lógica de datos vive en Python: la aplicación lanza el
sidecar (`pcapp_servidor`) como proceso hijo y le habla por HTTP en `127.0.0.1`.

Pantallas: arranque del motor, Inicio, Nuevo proyecto, Revisión, Decisiones, Preparación,
Recomendación de prueba, Configuración de PC, Análisis (progreso) y Resultados (grafo
interactivo, ajuste del umbral y de las orientaciones, versiones y exportación). El motor
empaquetado (`externalBin`) llega en la fase 8.

## Requisitos

- Node 20+ y npm.
- Rust (stable) y, en Windows, Visual Studio Build Tools con C++ y WebView2.
- El sidecar instalado en su entorno virtual (`pc-app/sidecar/.venv`, ver su README).

```bash
cd pc-app/app
npm install
npm run tauri dev        # compila Rust, arranca Vite (puerto 5173) y abre la ventana
```

Si `cargo` no está en el PATH (instalación de rustup sin reiniciar la terminal), añádalo:
`export PATH="$PATH:$HOME/.cargo/bin"`.

| Script | Qué hace |
|---|---|
| `npm run tauri dev` | Aplicación en modo desarrollo. |
| `npm run dev` | Solo el frontend en el navegador (usa el sidecar en `--modo-desarrollo --sin-token`, puerto 8765). |
| `npm test` | Pruebas de Vitest + React Testing Library. |
| `npm run comprobar-tipos` | `tsc --noEmit`. |
| `npm run generar-tipos` | Regenera `src/api/esquema.d.ts` desde `/openapi.json`. |

## Motor de análisis (sidecar)

`src-tauri/src/motor.rs` gestiona su ciclo de vida. Solo cambia *cómo se lanza*
(`OrigenMotor`); leer el arranque, el estado, el apagado y el reinicio es común:

- **Desarrollo:** `python -m pcapp_servidor --datos <datos de la app> --pid-padre <pid>`.
  El intérprete es `PCAPP_PYTHON` si está definida; si no, `pc-app/sidecar/.venv`.
- **Empaquetado:** reservado para la fase 8 (hoy informa de que no está disponible).
- **Arranque:** lee la línea `{"evento":"listo","puerto":N,"token":"..."}` o
  `{"evento":"error","mensaje":"..."}`. El tiempo límite es de 60 s por defecto y se
  cambia con `PCAPP_TIEMPO_ARRANQUE` (en segundos). Si el proceso termina antes, se
  muestra su último mensaje de error.
- **Datos:** la carpeta de datos es la de la aplicación (en Windows,
  `%APPDATA%\com.pcapp.escritorio`); los registros están en su subcarpeta `logs/`.
- **Rutas:** los argumentos se pasan como `OsStr` (sin pasar por un shell), así que
  funcionan rutas con espacios y acentos. Python se lanza con `PYTHONUTF8=1`.
- **Comandos de Tauri:**
  - `obtener_conexion()` espera el arranque y devuelve `{url, token}` o `{mensaje, carpeta_registros}`;
  - `reiniciar_motor()` apaga el motor y lo vuelve a lanzar.
- **Evento `motor-estado`:** avisa si el motor termina inesperadamente.
- **Al cerrar la ventana:** `POST /apagar` y, si el proceso no termina en 5 s, se mata.
  Si la aplicación muere de golpe, el sidecar se cierra solo gracias a `--pid-padre`.

**Permisos mínimos** (`capabilities/default.json`): `core:default`, `dialog:allow-open`,
`core:window:allow-is-focused` y `notification:default`. El proceso se lanza desde Rust, así
que el frontend no tiene permisos de shell.

**Guardar la imagen del grafo sin permisos de escritura.** Se descartó `tauri-plugin-fs` con
`fs:allow-write-file`: el plugin de diálogo añade al alcance de `fs` *cualquier* ruta que
devuelva un diálogo durante la sesión (también el dataset elegido al abrirlo y la carpeta de
exportación), así que el permiso no quedaba limitado al archivo elegido al guardar. En su
lugar, el comando de Rust `guardar_imagen` (`src-tauri/src/imagen.rs`) recibe los bytes del
PNG, comprueba que lo sean, abre él mismo el diálogo «Guardar» y escribe solo en la ruta
elegida allí. El frontend no tiene permisos de `fs` ni `dialog:allow-save`. La CSP solo
permite conexiones a `http://127.0.0.1:*`. El token viaja siempre en el encabezado
`X-Token`, nunca en la URL.

## Estructura del frontend

- **`src/api/`**
  - `esquema.d.ts`: tipos generados, no se edita a mano.
  - `cliente.ts`: `openapi-fetch` con el token, más `ErrorApi` (mensaje, `porCampo`, `referencia` de los 500) y `ErrorSinRespuesta`.
  - `consultas.ts`: consultas de TanStack Query.
  - `motor.ts`: comandos de Tauri, diálogo de archivos y notificación del sistema.
  - `trabajos.ts`: lanzar la recomendación o el análisis, cancelar y reanudar.
  - `resultados.ts`: guardar un ajuste como versión, cambiar de versión, validar una orientación y exportar.
  - `modeloCausal.ts`: aplicabilidad, modelo guardado, casos de test, escenarios y construcción (trabajo).
  - `prescripcion.ts`: configuración, condiciones, validación, caso, lotes, evaluaciones, trabajos y exportación.
- **`src/estado/`**
  - `etapas.ts`: las ocho etapas y cuáles se desactualizan.
  - `borrador.tsx`: elecciones y ediciones por proyecto.
  - `useElecciones.ts`: pide la previsualización con un retardo de 300 ms.
  - `niveles.ts`: reductor del editor de niveles (mover fichas, agregar, eliminar, renombrar, reordenar, restablecer).
  - `borradorAnalisis.tsx`: prueba elegida y configuración de PC en edición, por proyecto.
  - `trabajos.tsx`: vigilancia de los trabajos en curso y aviso al terminar.
  - `ajustes.ts`: borrador del ajuste (umbral y orientaciones manuales) y su comparación con la versión vista.
  - `grafo.ts`: datos de Cytoscape (colores por categoría y signo, id estable por par), disposición por niveles y camino al objetivo.
  - `modeloCausal.ts`: overrides de la construcción (mecanismo y monotonía), intervenciones de los escenarios, formatos y disposición del grafo pequeño.
  - `prescripcion.ts`: borrador de la configuración, declaración de supuestos (fecha al confirmar las tres casillas) y paso de una prescripción al explorador de escenarios.
- **`src/componentes/`**
  - `Arranque`: pantalla de arranque, «Reintentar» y aviso «Reiniciar el motor».
  - `Etapas`: el stepper.
  - `ConfirmarInvalidacion`, `MensajeError` y los editores de decisiones.
  - `EditorNiveles`: arrastrar y soltar con dnd-kit (también con el teclado o con el menú «Mover a» de cada ficha).
  - `ProgresoTrabajo`: progreso, modo, cancelación con confirmación y reanudación.
  - `resultados/GrafoCausal`: grafo con Cytoscape.js.
  - `resultados/DialogoOrientacion`: orientación manual con dirección y justificación obligatoria.
  - `resultados/Tablas` y `resultados/Paneles`: caracterización, aristas, ajuste, historial de versiones, detalle de la variable, advertencias, configuración y leyenda.
  - `modelo_causal/Aplicabilidad`: lista de bloqueantes y advertencias con el botón que lleva a donde se resuelven.
  - `modelo_causal/Mecanismos`: tabla de mecanismos (con el selector para cambiar el elegido) y curvas de efecto parcial del objetivo con su monotonía editable.
  - `modelo_causal/Evaluacion`: métricas en validación cruzada y test (umbral y Brier), calibración y modelo de referencia.
  - `modelo_causal/Escenarios` y `modelo_causal/GrafoPropagacion`: explorador de escenarios y grafo pequeño de la propagación.
  - `modelo_causal/Graficos`: gráficos SVG (curva de efecto con histograma y calibración).
  - `prescripcion/Configuracion`, `prescripcion/Caso`, `prescripcion/Lote` y `prescripcion/Evaluacion`: configuración con la declaración de supuestos, caso individual (con «Probar una variante», que abre el explorador de escenarios con la prescripción precargada), lotes filtrables y evaluación con sensibilidad y comparación de optimizadores.
- **`src/pantallas/`**
  - `Inicio`, `NuevoProyecto`, `DatosProyecto` (hoja, vista previa, objetivo y distribución), `Revision` y `Decisiones`.
  - `Preparacion`, `Recomendacion`, `ConfiguracionPc`, `Analisis`, `Resultados`, `ModeloCausal` y `Prescripcion` (con el aviso permanente sobre datos observacionales).

**No hay lógica de mapeo en TypeScript.** Las decisiones que resultan de las acciones
elegidas las calcula el núcleo (`POST /proyectos/{id}/decisiones/previsualizar`, que usa
`aplicar_elecciones`). El frontend solo superpone los valores que el usuario edita:
- el orden ordinal;
- los grupos de clases;
- el umbral, `restar` y `multiplicar` de las conversiones.

Los campos numéricos admiten fracciones (`5/9`) y coma decimal. Lo que no es un número se
envía tal cual, para que el servidor devuelva el 422 en ese campo.

Lo mismo en las etapas de análisis:
- **Preparación:** la separación la aplica y guarda el núcleo (en la receta); el límite de
  columnas (30/50) y la distribución del objetivo en train y test vienen en el resumen.
- **Recomendación:** las advertencias sobre la prueba y el max_k elegidos las calcula el
  núcleo (`POST .../recomendacion/evaluar`, con un retardo de 300 ms).
- **Configuración de PC:** el editor solo cambia la estructura de los niveles; errores y
  advertencias (p. ej. el objetivo fuera del último nivel) vienen de
  `POST .../configuracion-pc/validar`, con un retardo de 300 ms.

- **Resultados:** qué aristas quedan con otro umbral u otras orientaciones, su categoría,
  las advertencias y la validación de una orientación contra los niveles los calcula el núcleo
  (`POST .../resultado/reagregar`, con un retardo de 300 ms). El frontend solo guarda el
  borrador del ajuste.

- **Modelo causal:** la aplicabilidad, la elección de mecanismos, la monotonía, las métricas,
  las curvas y los escenarios (incluida la conversión a unidades originales y la agrupación
  de las dummies one-hot en un control de categoría) los calcula el núcleo. El frontend solo
  guarda los overrides que el usuario cambia («Cambios sin aplicar» hasta reconstruir) y las
  intervenciones del escenario, que envía con un retardo de 300 ms.

**Grafo (Cytoscape.js).** Una sola instancia por proyecto, que nunca se vuelve a crear:
- **Disposición:** posiciones por nivel (una columna por nivel con su nombre; un nivel de más
  de 8 variables se reparte en subcolumnas) calculadas y encuadradas solo la primera vez.
- **Al cambiar de versión o llegar una vista previa:** un diff dentro de `cy.batch()` quita y
  agrega las aristas que cambian (id = par de variables), actualiza sus datos, cambia la
  dirección con `edge.move()` y actualiza la categoría de cada nodo. No se quitan nodos, ni se
  recalcula la disposición, ni se encuadra: se conservan las posiciones arrastradas, el zoom
  y el desplazamiento.
- **«Mostrar solo lo relacionado con el objetivo»** oculta con una clase (`display: none`).
- **Aristas dentro de un nivel** que saltan un nodo se curvan hacia un lado.
- **«Guardar la vista en PNG»** exporta la vista actual (`cy.png({ full: false })`).

**Versiones.** Un ajuste sin guardar se marca con «Cambios sin guardar» (Guardar como
versión nueva / Descartar). Cada versión ajustada lleva la etiqueta «Ajustada: umbral X,
original Y» en el historial y en el encabezado del grafo; con un umbral menor que 0,5 aparece
«Umbrales bajos incluyen más aristas espurias». Cambiar de versión con cambios sin guardar
pide confirmación. «Exportar» exporta la versión vista (sin los cambios sin guardar).

**Sondeo del progreso:** `GET /trabajos/{id}` cada segundo mientras el trabajo está pendiente
o en curso. Se detiene en un estado final, si la consulta falla (aparece el aviso del motor)
y mientras la ventana no está visible. Un vigilante global sigue los trabajos en curso aunque
se cambie de pantalla. Al terminar actualiza el proyecto y avisa: dentro de la app siempre, y
con una notificación del sistema si la ventana no está en primer plano.

## Pruebas automáticas

`npm test` usa un sidecar simulado: un `fetch` falso que enruta por método y ruta. Cubre:
- el bloqueo por hallazgos pendientes de confirmar, en Revisión y en Decisiones;
- que todas las peticiones llevan `X-Token`;
- los errores 422 junto a su campo, por ejemplo `conversiones.0.multiplicar`, y la lista de los campos sin editor;
- la vista previa de la conversión °F → °C y el valor enviado;
- la advertencia de invalidación: qué etapas anuncia, que al cancelar no se guarda y que no pregunta si no hay etapas posteriores vigentes;
- `comoNumero`;
- el reductor del editor de niveles: mover fichas, agregar y eliminar niveles (las fichas pasan al vecino), renombrar, reordenar y restablecer;
- la validación en vivo de la configuración: errores por nivel, advertencia del objetivo, guardado bloqueado y «Restablecer»;
- las advertencias de la prueba elegida, junto a su campo, y la forma en U por sextiles;
- los estados de la pantalla de progreso (en curso, cancelado, interrumpido y completado), la confirmación al cancelar y el paso a Resultados;
- Resultados: la vista previa con retardo (una sola petición al mover el deslizante varios pasos), «Cambios sin guardar» con Descartar y Guardar, el aviso de umbral bajo, el historial de versiones y la confirmación al cambiar de versión con cambios sin guardar;
- el diálogo de orientación manual: dirección y justificación obligatorias, el rechazo del núcleo (contra los niveles) junto a la dirección, la orientación aplicada y quitarla desde la tabla de aristas;
- Modelo causal: la lista de aplicabilidad (bloqueante con su acción y el botón que lleva a Resultados), la construcción con los overrides de mecanismo y monotonía, el aviso de modelo desactualizado, la evaluación (umbral, Brier, calibración y costo de la parsimonia) y el explorador de escenarios (petición con la fila de test y las intervenciones, la categoría como un solo control que solo se fija, la extrapolación, la traza y el grafo de propagación);
- Prescripción: el aviso permanente, los bloqueantes con su botón, la declaración de supuestos (fecha al confirmar y envío al guardar), el caso individual (acciones ordenadas, marcas, explicación y «Probar una variante» con las intervenciones precargadas), el filtro del lote y la evaluación (evaluación interna y McNemar);
- los filtros por categoría de la caracterización, el recuadro de candidatas prescriptivas y el mensaje cuando no las hay; advertencias, configuración (original y ajustes de la versión) y el panel de una variable.

En jsdom no hay canvas: `src/pruebas/GrafoFalso.tsx` sustituye al grafo de Cytoscape por
botones con los mismos avisos (clic en un nodo o en una arista).

## Prueba manual

Con `npm run tauri dev`:

1. **Arranque.** Aparece «Iniciando el motor de análisis…» y después la lista de proyectos.
   - Para probar el fallo, cierre la app y ejecute `PCAPP_PYTHON=C:\no\existe npm run tauri dev`.
   - Debe verse un mensaje claro, la carpeta de registros y «Reintentar».
2. **Nuevo proyecto con `datasets_prueba/diabetes.csv`.**
   - Elegir el archivo en el diálogo nativo (filtro CSV/Excel).
   - Debe mostrarse la vista previa de 20 filas.
   - Al elegir el objetivo `Outcome` aparece su distribución (500 / 268).
   - Pulse «Revisar dataset».
3. **Revisión.**
   - Debe haber **7 hallazgos, 6 pendientes de confirmar** (los ceros sospechosos de las seis columnas).
   - El botón dice «Continuar (faltan 6 por confirmar)» y está desactivado.
   - En Glucose, BloodPressure, SkinThickness, Insulin y BMI, elija «Tratar los ceros como faltantes».
   - En Pregnancies, pulse «Confirmar: Conservar».
   - El botón se activa: pase a Decisiones.
4. **Decisiones.**
   - El resumen muestra los ceros como faltantes en esas cinco columnas.
   - Pulse «Guardar decisiones».
   - Compare `%APPDATA%\com.pcapp.escritorio\proyectos\<id>\decisiones.json` con `datasets_prueba/diabetes_decisiones.json`, que es la plantilla editada en la terminal. Deben coincidir en todo salvo `acciones_hallazgos`, porque en la terminal se editó `faltantes` a mano.
   - Esta comparación también es una prueba automática del sidecar (`test_decisiones_de_la_app_coinciden_con_las_de_la_terminal`).
5. **Invalidación.**
   - Prepare los datos (paso 10) y vuelva a guardar las decisiones: debe advertirse que «Preparación» quedará desactualizada.
6. **Dengue (`Dengue Dataset 2023-2025.xlsx`).**
   - Hoja `Sheet1`, objetivo `Outcome`.
   - En el hallazgo de mezcla de unidades de `Temp`, elija «Convertir unidades».
   - En Decisiones, ponga condición `>`, umbral `50`, restar `32` y multiplicar `5/9`.
   - La vista previa debe convertir los valores en °F (p. ej. 86 → 30; el hallazgo propone un umbral de 47,1) y dejar los demás «sin cambio».
7. **Motor caído.**
   - Con la app abierta, termine el proceso `python.exe` del motor desde el Administrador de tareas.
   - Aparece «El motor de análisis dejó de responder» con «Reiniciar el motor».
   - Al pulsarlo, todo vuelve a funcionar.
8. **Cierre.** Cierre la ventana. No debe quedar ningún `python.exe` con `pcapp_servidor` en la línea de órdenes, y el registro termina con «Servidor detenido».
9. **Error 500.** Si ocurre alguno, el mensaje muestra la referencia del registro con un botón para copiarla.
10. **Diabetes, flujo completo** (sigue al paso 4).
    - **Preparación:** estratificada, 30 % de test y semilla 42. Tras «Preparar datos» se ven 537 / 231 filas con la distribución del objetivo, 9 columnas y los faltantes sin imputar, que obligan a usar mv_fisherz.
    - **Recomendación:** con «Estimar el tiempo» sugiere **mv_fisherz**.
    - **Configuración:**
      - Agregue dos niveles y arrastre las fichas hasta [Age, Pregnancies, DiabetesPedigreeFunction] → [BMI, SkinThickness, BloodPressure] → [Glucose, Insulin] → [Outcome].
      - Póngales nombres, marque BMI, Glucose y BloodPressure como modificables y guarde.
      - Si mueve Outcome antes de otro nivel con variables, aparece la advertencia.
    - **Análisis:** «Ejecutar análisis»; la barra avanza con el modo y los tiempos. Al terminar aparece la notificación y la pantalla Resultados.
    - **Resultado esperado:**
      - causas directas: Glucose, BMI y Pregnancies;
      - candidatas prescriptivas: Glucose y BMI;
      - el grafo con los nombres de los niveles;
      - las mismas aristas que `datasets_prueba/diabetes_pc/resultado.json`, el resultado de la terminal.
11. **Salud fetal (`fetal_health.csv`, objetivo `fetal_health`).**
    - La recomendación es **chisq**, y mean_value_of_short_term_variability aparece con forma de U en su gráfico por sextiles.
    - Con max_k = 3, cancele a mitad del análisis: el diálogo explica que el avance se guarda.
    - Pulse «Reanudar»: el resultado final es el mismo que el de una ejecución sin interrumpir.
12. **Cerrar durante un análisis.**
    - Con un análisis en curso, cierre la ventana.
    - Al volver a abrir, Inicio marca el proyecto con «Análisis interrumpido: puede reanudarse».
    - En la pantalla Análisis, «Reanudar» continúa desde la última corrida guardada.
13. **Notificación del sistema.** Con un análisis en curso, pase a otra ventana: al terminar llega una notificación de Windows. Con la app en primer plano, solo la de la app.
14. **Resultados de diabetes** (sigue al paso 10).
    - **Grafo:** una columna por nivel con sus nombres, colores por categoría con la leyenda, y las modificables con borde doble.
    - **Categorías:** Glucose, BMI y Pregnancies son causas directas, Age es indirecta y BloodPressure no tiene camino. El recuadro de candidatas prescriptivas (pestaña Caracterización) muestra Glucose y BMI.
    - **Interacción:**
      - pase el cursor por una arista: frecuencia total, por dirección y ρ de Spearman;
      - haga clic en un nodo: panel con categoría, camino, frecuencia con el objetivo y grupo redundante;
      - «Mostrar solo lo relacionado con el objetivo» oculta BloodPressure, Insulin y DiabetesPedigreeFunction.
15. **Posición del usuario al ajustar.**
    - Arrastre un nodo a otro lugar y cambie el zoom con la rueda.
    - Mueva el deslizante del umbral: el nodo conserva su posición, el zoom no cambia y la vista no se desplaza. Solo aparecen o desaparecen aristas.
    - Por debajo de 50 % aparece «Umbrales bajos incluyen más aristas espurias».
16. **Orientación manual y versiones.**
    - Haga clic en la arista discontinua SkinThickness — BMI.
    - Elija BMI → SkinThickness, escriba una justificación y pulse «Aplicar»: la arista pasa a punteada con flecha y aparece «Cambios sin guardar».
    - «Guardar como versión nueva»: el historial muestra la versión 2 con su etiqueta.
    - Pase a la versión 1 y vuelva a la 2: la orientación, la justificación y las posiciones se conservan.
    - En Configuración se ven la configuración original y los ajustes de la versión vista.
17. **Dengue pediátrico** (`MASTER_CHART_F1000Research.xlsx`, FERRITIN excluida, prueba chisq, umbral 0,6).
    - Advertencias lista STEROIDS — objetivo (58,5 %) como arista débil con el objetivo.
    - Con el deslizante en 40 %, esa arista entra en el grafo y Advertencias la muestra en «Aristas añadidas al bajar el umbral».
    - Con estos datos, PLATELET COUNT — objetivo aparece en el 28,7 % de las corridas (chisq), por debajo del 40 %: no aparece ni siquiera con 0,4.
18. **Exportar.**
    - «Exportar» abre el diálogo de carpeta y crea `<nombre>_v<n>_<fecha-hora>/` con los archivos de la versión vista, la receta e `informe.html`.
    - Abra `informe.html` sin conexión: datos y hash, decisiones, separación, configuración original, ajustes de la versión (umbral usado y original), grafo, caracterización, aristas, advertencias e historial de versiones, con la exportada marcada.
19. **Imagen del grafo.** «Guardar la vista en PNG» abre el diálogo «Guardar» de Windows y guarda lo que se ve (con el zoom actual).
