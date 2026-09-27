"""Demostración: arranca el sidecar y recorre el flujo completo con diabetes por HTTP.

Uso (desde pc-app/sidecar, con el entorno instalado):

    python scripts/demo_api.py [--datos <carpeta>] [--corridas 100]

Solo usa la biblioteca estándar para las peticiones, como lo haría cualquier cliente.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIABETES = RAIZ.parent / "datasets_prueba" / "diabetes.csv"
NIVELES = [
    ["Age", "Pregnancies", "DiabetesPedigreeFunction"],
    ["BMI", "SkinThickness", "BloodPressure"],
    ["Glucose", "Insulin"],
    ["Outcome"],
]
CEROS = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]


class Cliente:
    def __init__(self, puerto: int, token: str) -> None:
        self.base, self.token = f"http://127.0.0.1:{puerto}", token

    def llamar(self, metodo: str, ruta: str, cuerpo: object = None, binario: bool = False):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
        solicitud = urllib.request.Request(
            self.base + ruta, data=datos, method=metodo,
            headers={"X-Token": self.token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(solicitud, timeout=600) as respuesta:
                contenido = respuesta.read()
        except urllib.error.HTTPError as error:
            detalle = json.loads(error.read())["error"]
            raise SystemExit(f"Error {error.code} en {metodo} {ruta}: {detalle['mensaje']} {detalle['detalles'] or ''}")
        if binario:
            return contenido
        return json.loads(contenido) if contenido else None


def esperar(cliente: Cliente, trabajo_id: str, titulo: str) -> dict:
    while True:
        trabajo = cliente.llamar("GET", f"/trabajos/{trabajo_id}")
        hechas, total = trabajo["completadas"], trabajo["total"] or 1
        barra = "#" * int(30 * hechas / total)
        restante = trabajo["segundos_restantes_estimados"]
        texto = f"\r{titulo}: [{barra:<30}] {hechas}/{total} · {trabajo['segundos_transcurridos']:.0f} s"
        if restante is not None:
            texto += f" · faltan ~{restante:.0f} s"
        print(texto.ljust(90), end="", flush=True)
        if trabajo["estado"] not in ("pendiente", "en_curso"):
            print()
            if trabajo["estado"] != "completado":
                raise SystemExit(f"El trabajo terminó como '{trabajo['estado']}': {trabajo['error'] or trabajo['mensaje']}")
            return trabajo
        time.sleep(0.3)


def main() -> int:
    opciones = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    opciones.add_argument("--datos", help="Carpeta de datos del sidecar (por defecto, una temporal).")
    opciones.add_argument("--corridas", type=int, default=100)
    opciones = opciones.parse_args()
    datos = Path(opciones.datos or tempfile.mkdtemp(prefix="pc-app-demo-"))

    print(f"Arrancando el sidecar (datos en {datos})...")
    proceso = subprocess.Popen(
        [sys.executable, "-m", "servidor", "--datos", str(datos), "--pid-padre", str(os.getpid())],
        stdout=subprocess.PIPE, text=True, encoding="utf-8",
    )
    listo = json.loads(proceso.stdout.readline())
    if listo.get("evento") != "listo":
        raise SystemExit(f"El sidecar no arrancó: {listo}")
    print(f"Listo en el puerto {listo['puerto']}.")
    cliente = Cliente(listo["puerto"], listo["token"])
    try:
        salud = cliente.llamar("GET", "/salud")
        print(f"Núcleo {salud['version_nucleo']} · servidor {salud['version_servidor']}")

        proyecto = cliente.llamar("POST", "/proyectos", {"ruta_archivo": str(DIABETES), "nombre": "Diabetes (demo)"})
        pid = proyecto["id"]
        print(f"\n1. Proyecto {pid}: {proyecto['filas']} filas, columnas {', '.join(proyecto['columnas'])}")

        revision = cliente.llamar("POST", f"/proyectos/{pid}/revision", {"objetivo": "Outcome"})
        print(f"2. Revisión: {len(revision['hallazgos'])} hallazgos "
              f"(p. ej. {', '.join(sorted({h['tipo'] for h in revision['hallazgos']})[:4])}...)")

        decisiones = cliente.llamar("GET", f"/proyectos/{pid}/decisiones/plantilla")
        confirmar = [k for k, a in decisiones["acciones_hallazgos"].items() if a["requiere_confirmacion"]]
        for columna in CEROS:  # decisión del usuario: los ceros clínicos son faltantes
            decisiones["faltantes"][columna] = {"ceros_como_faltantes": True, "imputacion": None}
        cliente.llamar("PUT", f"/proyectos/{pid}/decisiones", decisiones)
        print(f"3. Decisiones guardadas ({len(confirmar)} requerían confirmación: ceros como faltantes).")

        resumen = cliente.llamar("POST", f"/proyectos/{pid}/preparar")
        print(f"4. Preparación: {resumen['filas_train']} filas de train, {resumen['filas_test']} de test; "
              f"faltantes restantes en {len(resumen['faltantes_restantes'])} columnas.")

        trabajo = cliente.llamar("POST", f"/proyectos/{pid}/recomendacion?estimar_tiempo=true")
        esperar(cliente, trabajo["id"], "5. Recomendación")
        recomendacion = cliente.llamar("GET", f"/proyectos/{pid}/recomendacion")
        print(f"   Prueba sugerida: {recomendacion['prueba']}. {recomendacion['motivo']}")

        configuracion = cliente.llamar("GET", f"/proyectos/{pid}/configuracion-pc")["configuracion"]
        configuracion.update({"niveles": NIVELES, "modificables": ["BMI", "Glucose", "BloodPressure"],
                              "corridas_bootstrap": opciones.corridas})
        cliente.llamar("PUT", f"/proyectos/{pid}/configuracion-pc", configuracion)
        print(f"6. Configuración de PC: {configuracion['prueba']}, {opciones.corridas} corridas, 4 niveles.")

        trabajo = cliente.llamar("POST", f"/proyectos/{pid}/pc")
        esperar(cliente, trabajo["id"], "7. Análisis PC")
        resultado = cliente.llamar("GET", f"/proyectos/{pid}/resultado")
        por_categoria: dict[str, list[str]] = {}
        for variable in resultado["caracterizacion"]["variables"]:
            por_categoria.setdefault(variable["categoria"], []).append(variable["variable"])
        print(f"\nResultado ({resultado['corridas']['validas']} corridas válidas, "
              f"modo {resultado['ejecucion']['modo_usado']}):")
        for categoria in ("causa_directa", "causa_indirecta", "consecuencia", "ambigua", "sin_camino"):
            print(f"  {categoria}: {', '.join(por_categoria.get(categoria, [])) or '-'}")
        print(f"  {resultado['caracterizacion']['mensaje']}")

        imagen = cliente.llamar("GET", f"/proyectos/{pid}/archivos/grafo.png", binario=True)
        salida = datos / "grafo_demo.png"
        salida.write_bytes(imagen)
        print(f"\nGrafo descargado con el token en el encabezado: {salida}")
    finally:
        cliente.llamar("POST", "/apagar")
        proceso.wait(timeout=30)
        print("Sidecar apagado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
