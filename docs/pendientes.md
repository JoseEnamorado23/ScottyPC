# Pendientes

Puntos para después. No están implementados.

1. ~~**Ordinales y variables de pocos valores prescritas como continuas.**~~ **Resuelto en v0.6.0.**
   - Una variable se marca ordinal desde la pantalla Decisiones («Variables ordinales») o con la acción sugerida
     `usar_orden_sugerido`, que ahora crea la codificación.
   - Cada variable prescriptiva tiene un `paso` (1 por defecto en enteras y ordinales): solo se proponen valores de
     su rejilla. Las ordinales con más de 10 niveles se resuelven por relajación continua y ajuste a la rejilla;
     un valor fuera de rejilla es un error interno. Si el objetivo solo se alcanza con valores intermedios, el
     caso sale «Alcanzable solo con cambios intermedios».
   - Los límites y el cambio máximo de las ordinales se escriben en valores originales; las configuraciones
     antiguas se migran al abrirlas y se avisa de lo que cambie.
   - Artefacto formato 3 (`docs/artefacto.md`): `paso` real y `valores_permitidos` de las ordinales.
   - Verificación en Factores (`docs/artefactos/factores_rejilla_antes_despues.json`, 44 casos de test que no
     cumplen): antes, 69 de 69 valores fuera de rejilla (Asistencia 2,4976, Preparacion 0,5…) y 91 % de éxito;
     después, 0 de 64 fuera de rejilla y 100 % de éxito, tanto con el μ del proyecto como con el recalibrado.
     Ojo: el «después» también cambia el cambio máximo de 0,5 a 1 nivel, así que la mejora de la tasa no es
     solo de la rejilla.
   - Queda: los `.scotty` de ejemplo vienen de proyectos con configuración antigua (sin ordinales ni pasos);
     reexportar un proyecto con ordinales marcadas desde la app para tener un ejemplo con `valores_permitidos`.
2. **El resultado depende del tope de iteraciones cuando un arranque no converge.** En el gradiente proximal, un
   arranque que llega al tope de 300 iteraciones en un valle plano amplifica diferencias de 1 ULP (entre
   plataformas) hasta ~1e-6, y el mínimo entre arranques puede elegir otro ganador. Definir un criterio de
   convergencia relativo y una regla estable para elegir entre arranques casi empatados. Mientras tanto,
   `verificar_golden` acepta resultados equivalentes (ver `docs/artefacto.md`).
3. **DropOut: Course es un código de programa y se modela como continuo** (mecanismo lineal). Revisarlo: debería
   ser categórico (one-hot) o quedar fuera del modelo.
