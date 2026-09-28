# Aplicación de escritorio

Tauri v2 + React + Vite + TypeScript, con Mantine, TanStack Query y React Router. La
interfaz está en español. Toda la lógica de datos vive en Python: la aplicación lanza el
sidecar (`pcapp_servidor`) como proceso hijo y le habla por HTTP en `127.0.0.1`.

Esta fase incluye: arranque del motor, Inicio, Nuevo proyecto, Revisión y Decisiones.
Preparación, configuración de PC, ejecución y resultados llegan en las fases 6–7; el
motor empaquetado (`externalBin`), en la fase 8.

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

**Permisos mínimos** (`capabilities/default.json`): `core:default` y `dialog:allow-open`. El
proceso se lanza desde Rust, así que el frontend no tiene permisos de shell. La CSP solo
permite conexiones a `http://127.0.0.1:*`. El token viaja siempre en el encabezado
`X-Token`, nunca en la URL.

## Estructura del frontend

- **`src/api/`**
  - `esquema.d.ts`: tipos generados, no se edita a mano.
  - `cliente.ts`: `openapi-fetch` con el token, más `ErrorApi` (mensaje, `porCampo`, `referencia` de los 500) y `ErrorSinRespuesta`.
  - `consultas.ts`: consultas de TanStack Query.
  - `motor.ts`: comandos de Tauri y diálogo de archivos.
- **`src/estado/`**
  - `etapas.ts`: las seis etapas y cuáles se desactualizan.
  - `borrador.tsx`: elecciones y ediciones por proyecto.
  - `useElecciones.ts`: pide la previsualización con un retardo de 300 ms.
- **`src/componentes/`**
  - `Arranque`: pantalla de arranque, «Reintentar» y aviso «Reiniciar el motor».
  - `Etapas`: el stepper.
  - `ConfirmarInvalidacion`, `MensajeError` y los editores de decisiones.
- **`src/pantallas/`**
  - `Inicio`, `NuevoProyecto`, `DatosProyecto` (hoja, vista previa, objetivo y distribución), `Revision` y `Decisiones`.

**No hay lógica de mapeo en TypeScript.** Las decisiones que resultan de las acciones
elegidas las calcula el núcleo (`POST /proyectos/{id}/decisiones/previsualizar`, que usa
`aplicar_elecciones`). El frontend solo superpone los valores que el usuario edita:
- el orden ordinal;
- los grupos de clases;
- el umbral, `restar` y `multiplicar` de las conversiones.

Los campos numéricos admiten fracciones (`5/9`) y coma decimal. Lo que no es un número se
envía tal cual, para que el servidor devuelva el 422 en ese campo.

## Pruebas automáticas

`npm test` usa un sidecar simulado: un `fetch` falso que enruta por método y ruta. Cubre:
- el bloqueo por hallazgos pendientes de confirmar, en Revisión y en Decisiones;
- que todas las peticiones llevan `X-Token`;
- los errores 422 junto a su campo, por ejemplo `conversiones.0.multiplicar`, y la lista de los campos sin editor;
- la vista previa de la conversión °F → °C y el valor enviado;
- la advertencia de invalidación: qué etapas anuncia, que al cancelar no se guarda y que no pregunta si no hay etapas posteriores vigentes;
- `comoNumero`.

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
   - En el terminal, prepare los datos del proyecto con `POST /proyectos/{id}/preparar`, o espere a la fase 6.
   - Vuelva a guardar las decisiones: debe advertirse que «Preparación» quedará desactualizada.
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
