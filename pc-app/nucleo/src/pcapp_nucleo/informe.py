"""Informe HTML autocontenido de un resultado de PC (se abre sin conexión).

Todo va en un único archivo: estilos en línea y ``grafo.png`` en base64, sin
scripts ni recursos externos. ``resumen_decisiones`` y ``resumen_separacion``
también los usa la aplicación (pestaña «Configuración»), para que el informe y
la interfaz describan las decisiones con las mismas palabras.
"""

from __future__ import annotations

import base64
import html
from dataclasses import dataclass
from typing import Any

from pcapp_nucleo.reagregacion import AvisoResultado

CATEGORIAS = {
    "causa_directa": "Causa directa",
    "causa_indirecta": "Causa indirecta",
    "consecuencia": "Consecuencia",
    "ambigua": "Ambigua",
    "sin_camino": "Sin camino",
}
TIPOS_ARISTA = {"dirigida": "Dirigida", "sin_orientar": "Sin orientar", "manual": "Manual"}
_IMPUTACIONES = {
    None: "conservar los faltantes",
    "eliminar_filas": "eliminar las filas",
    "mediana": "imputar con la mediana",
    "multivariada": "imputación multivariada",
}


@dataclass(frozen=True)
class LineaResumen:
    concepto: str
    detalle: str


# --- Resúmenes compartidos con la aplicación --------------------------------------------------


def _lista(valores: list[Any]) -> str:
    return ", ".join(str(v) for v in valores)


def resumen_decisiones(decisiones: dict[str, Any]) -> list[LineaResumen]:
    """Decisiones de preparación en frases cortas (solo las que cambian algo)."""
    lineas: list[LineaResumen] = []

    def agregar(concepto: str, detalle: str) -> None:
        lineas.append(LineaResumen(concepto, detalle))

    agregar("Filas duplicadas", "se eliminan" if decisiones.get("eliminar_duplicados") else "se conservan")
    if decisiones.get("columnas_excluidas"):
        agregar("Columnas excluidas", _lista(decisiones["columnas_excluidas"]))
    for columna, tratamiento in (decisiones.get("faltantes") or {}).items():
        partes = []
        if tratamiento.get("ceros_como_faltantes"):
            partes.append("ceros como faltantes")
        partes.append(_IMPUTACIONES.get(tratamiento.get("imputacion"), str(tratamiento.get("imputacion"))))
        if tratamiento.get("indicador_medido"):
            partes.append("con indicador de medido")
        agregar(f"Faltantes de {columna}", "; ".join(partes))
    for columna, codificacion in (decisiones.get("codificaciones") or {}).items():
        detalle = codificacion["tipo"]
        if codificacion.get("orden"):
            detalle += f" ({_lista(codificacion['orden'])})"
        if codificacion.get("valor_positivo") is not None:
            detalle += f" (positivo: {codificacion['valor_positivo']})"
        if codificacion.get("grupos"):
            detalle += " (" + _lista(f"{k} → {v}" for k, v in codificacion["grupos"].items()) + ")"
        agregar(f"Codificación de {columna}", detalle)
    for conversion in decisiones.get("conversiones") or []:
        detalle = (
            f"si {conversion['columna']} {conversion['condicion']} {decimal(conversion['umbral'])}: "
            f"(x − {decimal(conversion.get('restar', 0))}) × {decimal(conversion.get('multiplicar', 1))}"
        )
        if conversion.get("descripcion"):
            detalle += f" — {conversion['descripcion']}"
        agregar(f"Conversión de unidades de {conversion['columna']}", detalle)
    if decisiones.get("logaritmos"):
        agregar("Logaritmo", _lista(decisiones["logaritmos"]))
    agregar("Normalización min–max", "sí" if decisiones.get("normalizar", True) else "no")
    if decisiones.get("columnas_fecha_disponibles"):
        agregar("Fechas reservadas (no son variables)", _lista(decisiones["columnas_fecha_disponibles"]))
    acciones = decisiones.get("acciones_hallazgos") or {}
    confirmadas = [f"{clave}: {valor['accion']}" for clave, valor in acciones.items() if valor.get("requiere_confirmacion")]
    if confirmadas:
        agregar("Decisiones confirmadas por el usuario", "; ".join(confirmadas))
    for nota in decisiones.get("notas") or []:
        agregar("Nota", nota)
    return lineas


def separacion_de_receta(receta: dict[str, Any]) -> dict[str, Any]:
    """Separación configurada (receta versión 2, o la de las decisiones en la versión 1)."""
    return receta.get("separacion") or (receta.get("decisiones") or {}).get("separacion") or {}


def resumen_separacion(receta: dict[str, Any]) -> list[LineaResumen]:
    separacion = separacion_de_receta(receta)
    aplicada = receta.get("separacion_aplicada") or {}
    tipo = separacion.get("tipo", aplicada.get("tipo", "estratificada"))
    lineas = [LineaResumen("Tipo", tipo)]
    if tipo == "temporal":
        lineas.append(LineaResumen("Columna de fecha", str(separacion.get("columna_fecha"))))
        lineas.append(LineaResumen("Corte", separacion.get("corte") or "sin corte (proporción de test)"))
    else:
        lineas.append(LineaResumen("Proporción de test", f"{decimal(100 * separacion.get('proporcion_test', 0.3))} %"))
        lineas.append(LineaResumen("Semilla", str(separacion.get("semilla", 42))))
    if aplicada:
        lineas.append(LineaResumen(
            "Filas", f"{aplicada.get('filas_train')} de entrenamiento y {aplicada.get('filas_test')} de test",
        ))
    return lineas


def decimal(valor: float) -> str:
    """Número con coma decimal (``0,45``)."""
    return f"{valor:g}".replace(".", ",")


def etiqueta_version(umbral: float, umbral_original: float, orientaciones: int) -> str:
    """«Original», «Ajustada: umbral X, original Y» (más las orientaciones manuales añadidas) o,
    si el umbral no cambió, «Ajustada: N orientaciones manuales; umbral original Y»."""
    mismo_umbral = abs(umbral - umbral_original) < 1e-9
    if mismo_umbral and not orientaciones:
        return "Original"
    manuales = "1 orientación manual" if orientaciones == 1 else f"{orientaciones} orientaciones manuales"
    if mismo_umbral:
        return f"Ajustada: {manuales}; umbral original {decimal(umbral_original)}"
    texto = f"Ajustada: umbral {decimal(umbral)}, original {decimal(umbral_original)}"
    return texto + (f"; {manuales}" if orientaciones else "")


# --- HTML -------------------------------------------------------------------------------------------

_ESTILOS = """
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;margin:0;background:#f5f6f8;color:#1f2933;line-height:1.45}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.2rem;margin:32px 0 8px;border-bottom:2px solid #d9dee4;padding-bottom:4px}
h3{font-size:1rem;margin:16px 0 6px}
.sub{color:#52606d;margin:0 0 16px}
.caja{background:#fff;border:1px solid #d9dee4;border-radius:8px;padding:12px 16px;margin:8px 0}
.destacada{border-left:4px solid #2e7d32}.aviso{border-left:4px solid #e67700}.info{border-left:4px solid #1971c2}
table{border-collapse:collapse;width:100%;background:#fff;font-size:.9rem;margin:6px 0}
th,td{border:1px solid #d9dee4;padding:4px 8px;text-align:left;vertical-align:top}
th{background:#eef1f4}td.num{text-align:right;font-variant-numeric:tabular-nums}
.etiqueta{display:inline-block;border-radius:4px;padding:1px 8px;font-size:.85rem;font-weight:600;background:#e7f5ff;color:#1864ab}
.etiqueta.ajustada{background:#fff4e6;color:#d9480f}.etiqueta.exportada{background:#ebfbee;color:#2b8a3e}
img{max-width:100%;height:auto;background:#fff;border:1px solid #d9dee4;border-radius:8px}
code{font-family:ui-monospace,Consolas,monospace;font-size:.85rem;word-break:break-all}
@media print{body{background:#fff}.caja,table{break-inside:avoid}}
"""


def _e(valor: Any) -> str:
    return html.escape("" if valor is None else str(valor))


def _tabla(encabezados: list[str], filas: list[list[Any]], numericas: set[int] | None = None) -> str:
    numericas = numericas or set()
    cabeza = "".join(f"<th>{_e(h)}</th>" for h in encabezados)
    cuerpo = "".join(
        "<tr>" + "".join(
            f'<td class="num">{_e(c)}</td>' if i in numericas else f"<td>{_e(c)}</td>" for i, c in enumerate(fila)
        ) + "</tr>"
        for fila in filas
    )
    return f"<table><thead><tr>{cabeza}</tr></thead><tbody>{cuerpo}</tbody></table>"


def _lineas(lineas: list[LineaResumen]) -> str:
    return _tabla(["Concepto", "Detalle"], [[linea.concepto, linea.detalle] for linea in lineas])


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{100 * valor:.1f} %".replace(".", ",")


def _rho(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:+.3f}".replace(".", ",")


def _orientaciones(orientaciones: list[dict[str, Any]]) -> str:
    if not orientaciones:
        return "<p>Ninguna.</p>"
    return _tabla(
        ["Orientación", "Justificación"],
        [[f"{o['origen']} → {o['destino']}", o.get("justificacion") or "—"] for o in orientaciones],
    )


def informe_html(
    contenido: dict[str, Any],
    receta: dict[str, Any],
    avisos: list[AvisoResultado],
    grafo_png: bytes,
    versiones: list[dict[str, Any]],
    version_exportada: int,
    nombre_proyecto: str,
    generado_en: str,
) -> str:
    """Informe completo de la versión ``version_exportada`` de un resultado.

    Args:
        contenido: ``resultado.json`` de esa versión.
        receta: ``receta.json`` (dataset, hash, decisiones y separación).
        avisos: ``reagregacion.avisos_resultado`` de esa versión.
        grafo_png: ``grafo.png`` de esa versión.
        versiones: historial (``version``, ``base``, ``umbral_frecuencia``,
            ``orientaciones_manuales``, ``creada_en`` y, opcional, ``migrada``).
    """
    configuracion = contenido["configuracion"]
    agregacion = contenido["agregacion"]
    caracterizacion = contenido["caracterizacion"]
    corridas = contenido["corridas"]
    umbral, umbral_original = agregacion["umbral_frecuencia"], configuracion["umbral_frecuencia"]
    etiqueta = etiqueta_version(umbral, umbral_original, orientaciones_nuevas(agregacion, configuracion))
    partes: list[str] = []
    agregar = partes.append

    agregar(f"<h1>Informe de resultados: {_e(nombre_proyecto)}</h1>")
    clase = "ajustada" if etiqueta != "Original" else ""
    agregar(
        f'<p class="sub">Generado el {_e(generado_en)} · Versión exportada: <strong>{version_exportada}</strong> '
        f'<span class="etiqueta {clase}">{_e(etiqueta)}</span></p>'
    )
    agregar(
        '<div class="caja info"><strong>Umbral de frecuencia usado:</strong> '
        f"{_pct(umbral)} · <strong>umbral original de la ejecución:</strong> {_pct(umbral_original)}</div>"
    )

    agregar("<h2>Datos</h2>")
    origen = receta.get("origen") or {}
    aplicada = receta.get("separacion_aplicada") or {}
    agregar(_lineas([
        LineaResumen("Archivo", origen.get("archivo") or "—"),
        *([LineaResumen("Hoja", origen["hoja"])] if origen.get("hoja") else []),
        LineaResumen("SHA-256", origen.get("sha256") or "—"),
        LineaResumen("Objetivo", f"{receta.get('objetivo')} ({receta.get('tipo_objetivo') or 'tipo no determinado'})"),
        LineaResumen("Filas", f"{aplicada.get('filas_train', '—')} de entrenamiento y {aplicada.get('filas_test', '—')} de test"),
        LineaResumen("Variables del análisis", _lista(contenido["variables"])),
    ]))

    agregar("<h2>Decisiones de preparación</h2>")
    agregar(_lineas(resumen_decisiones(receta.get("decisiones") or {})))
    agregar("<h3>Separación en entrenamiento y test</h3>")
    agregar(_lineas(resumen_separacion(receta)))
    columnas = receta.get("columnas") or []
    if columnas:
        agregar("<h3>Columnas finales</h3>")
        agregar(_tabla(
            ["Columna", "Tipo", "Transformaciones"],
            [[c["nombre"], c["tipo_final"], ", ".join(c.get("transformaciones") or []) or "—"] for c in columnas],
        ))

    agregar("<h2>Configuración de PC (ejecución original)</h2>")
    nombres = configuracion.get("nombres_niveles") or [f"Nivel {i + 1}" for i in range(len(configuracion["niveles"]))]
    agregar(_lineas([
        LineaResumen("Prueba de independencia", configuracion["prueba"]),
        LineaResumen("alpha", decimal(configuracion['alpha'])),
        LineaResumen("max_k", "sin límite" if configuracion.get("max_k") is None else str(configuracion["max_k"])),
        LineaResumen("Corridas de bootstrap", str(configuracion["corridas_bootstrap"])),
        LineaResumen("Fracción de la submuestra", decimal(configuracion['fraccion_submuestra'])),
        LineaResumen("Umbral de frecuencia", _pct(umbral_original)),
        LineaResumen("Semilla", str(configuracion["semilla"])),
        LineaResumen("Modificables", _lista(configuracion.get("modificables") or []) or "ninguna"),
    ]))
    agregar("<h3>Niveles</h3>")
    agregar(_tabla(["Nivel", "Variables"], [[n, _lista(nivel)] for n, nivel in zip(nombres, configuracion["niveles"])]))
    agregar("<h3>Orientaciones manuales de la configuración</h3>")
    agregar(_orientaciones(configuracion.get("orientaciones_manuales") or []))

    agregar(f"<h2>Ajustes de la versión {version_exportada}</h2>")
    agregar(_lineas([
        LineaResumen("Umbral usado", _pct(umbral)),
        LineaResumen("Umbral original", _pct(umbral_original)),
    ]))
    agregar("<h3>Orientaciones manuales aplicadas</h3>")
    agregar(_orientaciones(agregacion.get("orientaciones_manuales") or []))

    agregar("<h2>Grafo</h2>")
    imagen = base64.b64encode(grafo_png).decode("ascii")
    agregar(f'<img alt="Grafo causal" src="data:image/png;base64,{imagen}">')

    agregar("<h2>Caracterización respecto al objetivo</h2>")
    candidatas = caracterizacion["candidatas_prescriptivas"]
    agregar(
        f'<div class="caja {"destacada" if candidatas else "aviso"}"><strong>Candidatas prescriptivas:</strong> '
        f"{_e(_lista(candidatas) or 'ninguna')}<br>{_e(caracterizacion['mensaje'])}</div>"
    )
    agregar(_tabla(
        ["Variable", "Categoría", "A través de", "Frecuencia con el objetivo", "Grupo redundante", "Modificable"],
        [
            [
                v["variable"], CATEGORIAS.get(v["categoria"], v["categoria"]), " → ".join(v["a_traves_de"]) or "—",
                _pct(v["frecuencia_con_objetivo"]), _lista(v["grupo_redundante"] or []) or "—",
                "sí" if v["modificable"] else "no",
            ]
            for v in caracterizacion["variables"]
        ],
        numericas={3},
    ))

    agregar("<h2>Aristas</h2>")
    agregar(_tabla(
        ["Origen", "Destino", "Tipo", "Frecuencia total", "Origen → destino", "Destino → origen", "Sin orientar", "ρ de Spearman", "Justificación"],
        [
            [
                a["origen"], a["destino"], TIPOS_ARISTA.get(a["tipo"], a["tipo"]), _pct(a["frecuencia_total"]),
                _pct(a["frecuencia_origen_destino"]), _pct(a["frecuencia_destino_origen"]),
                _pct(a["frecuencia_sin_orientar"]), _rho(a["spearman"]), a.get("justificacion") or "—",
            ]
            for a in contenido["aristas"]
        ],
        numericas={3, 4, 5, 6, 7},
    ) if contenido["aristas"] else "<p>No se aceptó ninguna arista.</p>")

    agregar("<h2>Advertencias</h2>")
    if not avisos:
        agregar("<p>Ninguna.</p>")
    for aviso in avisos:
        agregar(f'<div class="caja {"aviso" if aviso.nivel == "advertencia" else "info"}">'
                f"<strong>{_e(aviso.titulo)}</strong><br>{_e(aviso.mensaje)}")
        if aviso.pares:
            agregar(_tabla(
                ["Par", "Frecuencia"],
                [[f"{p.variable_a} — {p.variable_b}", _pct(p.frecuencia)] for p in aviso.pares],
                numericas={1},
            ))
        agregar("</div>")

    agregar("<h2>Historial de versiones</h2>")
    filas = []
    for v in versiones:
        numero = v["version"]
        estado = "exportada" if numero == version_exportada else ""
        filas.append([
            f"{numero}{' (exportada)' if estado else ''}",
            "—" if v.get("base") is None else str(v["base"]),
            etiqueta_version(v["umbral_frecuencia"], umbral_original, orientaciones_nuevas(v, configuracion)),
            _pct(v["umbral_frecuencia"]),
            "; ".join(
                f"{o['origen']} → {o['destino']} ({o.get('justificacion') or 'sin justificación'})"
                for o in v.get("orientaciones_manuales") or []
            ) or "—",
            v.get("creada_en") or "—",
            "sí" if v.get("migrada") else "no",
        ])
    agregar(_tabla(["Versión", "Base", "Descripción", "Umbral", "Orientaciones manuales", "Fecha", "Migrada"], filas))
    agregar(f'<p>Este informe corresponde a la <span class="etiqueta exportada">versión {version_exportada}</span>.</p>')

    agregar("<h2>Ejecución</h2>")
    ejecucion = contenido.get("ejecucion") or {}
    agregar(_lineas([
        LineaResumen("Corridas", f"{corridas['validas']} válidas de {corridas['totales']} ({len(corridas['fallidas'])} fallidas)"),
        LineaResumen("Tiempo", f"{contenido.get('tiempo_s', 0):.0f} s"),
        *([LineaResumen("Modo", f"{ejecucion['modo_usado']} ({ejecucion['procesos']} proceso(s))")] if ejecucion else []),
    ]))

    return (
        '<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Informe: {_e(nombre_proyecto)}</title><style>{_ESTILOS}</style></head>"
        f"<body><main>{''.join(partes)}</main></body></html>\n"
    )


def orientaciones_nuevas(agregacion: dict[str, Any], configuracion: dict[str, Any]) -> int:
    """Orientaciones manuales de la versión que no estaban en la configuración de la ejecución."""
    originales = {
        (o["origen"], o["destino"], o.get("justificacion", "")) for o in configuracion.get("orientaciones_manuales") or []
    }
    return sum(
        (o["origen"], o["destino"], o.get("justificacion", "")) not in originales
        for o in agregacion.get("orientaciones_manuales") or []
    )
