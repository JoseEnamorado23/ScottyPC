# Pendientes

Puntos para después. No están implementados.

1. **Ordinales y variables de pocos valores prescritas como continuas.** Variables como Preparacion (0–2) o
   Asistencia (0–3) se tratan hoy como continuas: el optimizador desciende por el gradiente y devuelve valores
   intermedios (p. ej. Asistencia 2 → 2,4976). Deberían tratarse como estados discretos para que el optimizador
   enumere los estados permitidos en lugar de descender.
2. **El resultado depende del tope de iteraciones cuando un arranque no converge.** En el gradiente proximal, un
   arranque que llega al tope de 300 iteraciones en un valle plano amplifica diferencias de 1 ULP (entre
   plataformas) hasta ~1e-6, y el mínimo entre arranques puede elegir otro ganador. Definir un criterio de
   convergencia relativo y una regla estable para elegir entre arranques casi empatados. Mientras tanto,
   `verificar_golden` acepta resultados equivalentes (ver `docs/artefacto.md`).
3. **DropOut: Course es un código de programa y se modela como continuo** (mecanismo lineal). Revisarlo: debería
   ser categórico (one-hot) o quedar fuera del modelo.
