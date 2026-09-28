// Genera src/api/esquema.d.ts a partir del /openapi.json del sidecar.
// Lanza el sidecar en modo desarrollo (puerto fijo, sin token) con una carpeta
// de datos temporal, descarga el esquema, escribe los tipos y lo apaga.
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const app = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const venv = resolve(app, "..", "sidecar", ".venv");
const python =
  process.env.PCAPP_PYTHON ||
  (process.platform === "win32" ? join(venv, "Scripts", "python.exe") : join(venv, "bin", "python"));
const datos = mkdtempSync(join(tmpdir(), "pcapp-tipos-"));
const destino = join(app, "src", "api", "esquema.d.ts");

const motor = spawn(python, ["-m", "pcapp_servidor", "--datos", datos, "--modo-desarrollo", "--sin-token"], {
  env: { ...process.env, PYTHONUTF8: "1", PYTHONUNBUFFERED: "1" },
  stdio: ["ignore", "pipe", "inherit"],
});

function esperarArranque(limiteMs = 60_000) {
  return new Promise((resolver, rechazar) => {
    const temporizador = setTimeout(() => rechazar(new Error("El sidecar no arrancó a tiempo.")), limiteMs);
    motor.once("error", rechazar);
    motor.once("exit", (codigo) => rechazar(new Error(`El sidecar terminó (código ${codigo}).`)));
    createInterface({ input: motor.stdout }).on("line", (linea) => {
      try {
        const evento = JSON.parse(linea);
        clearTimeout(temporizador);
        if (evento.evento === "listo") resolver(evento.puerto);
        else rechazar(new Error(evento.mensaje));
      } catch {
        /* línea que no es de arranque */
      }
    });
  });
}

let codigo = 0;
try {
  const puerto = await esperarArranque();
  const ast = await openapiTS(new URL(`http://127.0.0.1:${puerto}/openapi.json`));
  const aviso = "// Generado por `npm run generar-tipos` a partir de /openapi.json. No editar.\n\n";
  writeFileSync(destino, aviso + astToString(ast));
  console.log(`Tipos escritos en ${destino}`);
  await fetch(`http://127.0.0.1:${puerto}/apagar`, { method: "POST" }).catch(() => {});
} catch (error) {
  console.error(`No se pudieron generar los tipos: ${error.message}`);
  codigo = 1;
} finally {
  const limite = setTimeout(() => motor.kill(), 5000);
  if (motor.exitCode === null) await new Promise((r) => motor.once("exit", r));
  clearTimeout(limite);
  rmSync(datos, { recursive: true, force: true });
}
process.exit(codigo);
