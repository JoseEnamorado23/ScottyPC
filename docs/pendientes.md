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
   - **Nota para el informe: efecto de la rejilla aislado del cambio máximo** (mismos 44 casos, mismo μ = 0,003162, cambio
     máximo de 1 nivel en ambas; `docs/artefactos/factores_rejilla_aislada_A_B.json`). En A las ordinales quedan como
     continuas y sin paso; en B son ordinales con rejilla.

     | | A: sin rejilla | B: con rejilla |
     |---|---|---|
     | Tasa de éxito | 44/44 (100 %) | 44/44 (100 %) |
     | Valores fuera de rejilla | 62 de 64 | 0 de 64 |
     | Cambio medio por acción (niveles) | 0,61 | 1,00 |
     | P(Clase=1) − meta: mediana / p90 / máx. | 0,00 / +0,037 / +0,066 | +0,31 / +0,32 / +0,32 |
     | Costo medio | 0,35 | 1,18 |
     | «Requiere revisión» | 54,5 % | 29,5 % |
     | Vecinos con respaldo | 93,2 % | 97,7 % |
     | Mejora media de los vecinos (pp) | +15,0 | +42,8 |

     Lectura: **la subida de 91 % a 100 % se debe al cambio máximo, no a la rejilla**: con 1 nivel, la variante sin rejilla
     también alcanza el 100 %. La rejilla no cambia la tasa de éxito, pero sí lo que se propone: la continua se queda justo en
     la meta (P = 0,50) con cambios fraccionarios que no existen (62 de 64 valores inválidos), y la rejilla obliga a pasar a
     niveles reales, que sobrepasan la meta en ~0,3 de probabilidad y cuestan ~3,4 veces más. A cambio, esas prescripciones
     tienen más respaldo en los datos y menos casos marcados para revisión. Antes de presentarlo, tener en cuenta que el
     optimizador minimiza el costo continuo y la rejilla fuerza saltos de un nivel entero; si el sobrepaso resulta excesivo,
     una rejilla más fina (p. ej. dejar Asistencia en 0,5 de nivel no es posible en una ordinal) no es una opción: habría que
     decidir si el cambio máximo de 1 nivel es el adecuado para esas variables.
   - Queda: los `.scotty` de ejemplo vienen de proyectos con configuración antigua (sin ordinales ni pasos);
     reexportar un proyecto con ordinales marcadas desde la app para tener un ejemplo con `valores_permitidos`.
2. **El resultado depende del tope de iteraciones cuando un arranque no converge.** En el gradiente proximal, un
   arranque que llega al tope de 300 iteraciones en un valle plano amplifica diferencias de 1 ULP (entre
   plataformas) hasta ~1e-6, y el mínimo entre arranques puede elegir otro ganador. Definir un criterio de
   convergencia relativo y una regla estable para elegir entre arranques casi empatados. Mientras tanto,
   `verificar_golden` acepta resultados equivalentes (ver `docs/artefacto.md`).
3. **DropOut: Course es un código de programa y se modela como continuo** (mecanismo lineal). Revisarlo: debería
   ser categórico (one-hot) o quedar fuera del modelo.
