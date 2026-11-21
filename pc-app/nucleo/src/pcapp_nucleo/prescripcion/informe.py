"""Exportación de la prescripción: CSV de prescripciones e informe HTML autocontenido."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from pcapp_nucleo.causal.configuracion import decimal
from pcapp_nucleo.informe import _ESTILOS, _e, _tabla

AVISO_PERMANENTE = (
    "Recomendaciones basadas en datos observacionales. No reemplazan el criterio de un experto ni una "
    "validación experimental."
)
NOMBRES_SUPUESTOS = {
    "modificable_por_decision": "Se puede modificar mediante una decisión real",
    "medida_antes_del_resultado": "Se mide antes del resultado",
    "no_define_el_objetivo": "No es parte de la definición del objetivo",
}


def _texto_acciones(r: dict[str, Any]) -> str:
    partes = []
    for a in r["acciones"]:
        if a["cambio"] is not None:
            partes.append(f"{a['variable']}: {a['antes']} → {a['despues']} ({decimal(a['cambio'], '+.4g')})")
        else:
            partes.append(f"{a['variable']}: {a['antes']} → {a['despues']}")
    return "; ".join(partes)


def prescripciones_csv(resultados: list[dict[str, Any]]) -> str:
    """Una fila por caso; las acciones también en columnas «<variable> antes/después»."""
    filas = []
    for r in resultados:
        fila = {
            "caso": r["caso"].get("indice"),
            "antes": r["antes"],
            "despues": r["despues"],
            "deseado": r["deseado"],
            "alcanzado": r["alcanzado"],
            "ya_cumple": r["ya_cumple"],
            "falta": r["falta"],
            "requiere_revision": r["requiere_revision"],
            "extrapolacion": r["extrapolacion"],
            "aproximado": r["aproximado"],
            "costo_total": r["costo_total"],
            "acciones": _texto_acciones(r),
            "restricciones_activas": "; ".join(f"{x['variable']}: {x['restriccion']}" for x in r["restricciones_activas"]),
            "explicacion": r["explicacion"],
        }
        if r.get("solo_con_cambios_intermedios"):  # la columna solo aparece cuando ocurre
            fila["solo_con_cambios_intermedios"] = True
        evidencia = r.get("evidencia")
        if evidencia:
            fila["vecinos_con_prescripcion"] = evidencia["prescrita"]["valor"]
            fila["vecinos_con_valores_actuales"] = evidencia["actual"]["valor"]
            fila["vecinos_mejora"] = evidencia["mejora"]
            fila["vecinos_con_respaldo"] = evidencia["prescrita"]["con_respaldo"]
        for a in r["acciones"]:
            fila[f"{a['variable']} antes"] = a["antes"]
            fila[f"{a['variable']} despues"] = a["despues"]
        filas.append(fila)
    salida = io.StringIO()
    pd.DataFrame(filas).to_csv(salida, index=False)
    return salida.getvalue()


def _pct(valor: float | None) -> str:
    return "—" if valor is None else decimal(100 * valor, ".1f") + " %"


def _num(valor: float | None, formato: str = ".3f") -> str:
    return "—" if valor is None else decimal(valor, formato)


def _evidencia_y_comparador(evaluacion: dict[str, Any]) -> list[str]:
    """Evidencia de vecinos y comparador de métodos (las evaluaciones antiguas no los traen)."""
    partes: list[str] = []
    e = evaluacion.get("evidencia_vecinos")
    valor = _pct if (e or {}).get("medida", "proporcion") == "proporcion" else _num
    if e:
        intervalo = e["intervalo_mejora"]
        partes += [
            "<h3>Evidencia de vecinos (datos observados)</h3>",
            f'<div class="aviso">{_e(e["texto"])}</div>',
            _tabla(
                ["Métrica", "Valor"],
                [
                    ["Vecinos por caso (k)", e["k"]],
                    ["Prescripciones con respaldo en los datos", f"{e['con_respaldo']} de {e['casos']} ({decimal(e['porcentaje_con_respaldo'], '.1f')} %)"],
                    ["Resultado observado en los vecinos con la prescripción", valor(e["valor_prescrita_medio"])],
                    ["Resultado observado en los vecinos con los valores actuales", valor(e["valor_actual_medio"])],
                    ["Mejora observada media (IC 95 %)",
                     f"{valor(e['mejora_media'])}" + (f" ({valor(intervalo[0])} a {valor(intervalo[1])})" if intervalo else "")],
                    ["Casos en que los vecinos mejoran", "—" if e["porcentaje_mejora_positiva"] is None else decimal(e["porcentaje_mejora_positiva"], ".1f") + " %"],
                    ["Casos en que los vecinos cumplen el objetivo", "—" if e["porcentaje_cumple"] is None else decimal(e["porcentaje_cumple"], ".1f") + " %"],
                    ["Coincidencia modelo causal / vecinos", "—" if e["coincidencia_modelo"] is None else decimal(e["coincidencia_modelo"], ".1f") + " %"],
                    ["p (Wilcoxon, prescripción frente a valores actuales)", _num(e["p_valor"], ".4g")],
                ],
                {1},
            ),
            '<p class="nota">Calculado sobre los casos cuya prescripción tiene respaldo (vecinos tan cercanos como los de un caso típico de train).</p>',
        ]
    comparador = evaluacion.get("comparador") or []
    if comparador:
        partes += [
            "<h3>Comparador de métodos (mismos casos, mismas restricciones)</h3>",
            f'<p class="nota">{_e(evaluacion.get("texto_comparador") or "")}</p>',
            _tabla(
                ["Método", "Éxito (modelo causal)", "Éxito (referencia)", "Con respaldo", "Cumple en vecinos",
                 "Resultado en vecinos", "Mejora en vecinos", "p frente al prescriptor", "Costo medio", "Acciones medias"],
                [
                    [m["nombre"], _pct(m["tasa_exito_causal"]), _pct(m["tasa_exito_referencia"]),
                     "—" if m["porcentaje_con_respaldo"] is None else decimal(m["porcentaje_con_respaldo"], ".1f") + " %",
                     _pct(m["tasa_cumple_vecinos"]), valor(m["valor_vecinos_medio"]), valor(m["mejora_vecinos_media"]),
                     _num(m["p_valor_frente_prescriptor"], ".4g"), _num(m["costo_medio"]), _num(m["acciones_medias"], ".2f")]
                    for m in comparador
                ],
                {1, 2, 3, 4, 5, 6, 7, 8, 9},
            ),
        ]
    return partes


def informe_prescripcion_html(
    nombre_proyecto: str,
    fecha: str,
    configuracion: dict[str, Any],
    calibracion: dict[str, Any] | None,
    condiciones: list[dict[str, Any]],
    evaluacion: dict[str, Any] | None,
    resultados: list[dict[str, Any]] | None,
    medida: str,
) -> str:
    """Informe autocontenido (se abre sin conexión) con la configuración, la declaración de
    supuestos, la calibración de μ, las métricas de la evaluación y las advertencias."""
    formato_objetivo = (lambda v: decimal(v, ".2f")) if medida == "probabilidad" else (lambda v: decimal(v, ".4g"))
    objetivo = configuracion["objetivo"]
    partes = [
        f"<h1>Prescripción: {_e(nombre_proyecto)}</h1>",
        f'<p class="nota">Generado el {_e(fecha)}.</p>',
        f'<div class="aviso"><strong>{_e(AVISO_PERMANENTE)}</strong></div>',
        "<h2>Objetivo deseado</h2>",
        f"<p>{'Subir' if objetivo['direccion'] == 'subir' else 'Bajar'} "
        f"{'la probabilidad de la clase 1' if medida == 'probabilidad' else 'el valor del objetivo'} "
        f"hasta {_e(formato_objetivo(objetivo['valor']))}.</p>",
        "<h2>Variables prescriptivas y restricciones</h2>",
        _tabla(
            ["Variable", "Permitida", "Dirección", "Mínimo", "Máximo", "Cambio máximo", "Costo", "Estados permitidos"],
            [
                [
                    v, "sí" if a["permitida"] else "no", a["direccion"], _num(a["minimo"], ".4g"), _num(a["maximo"], ".4g"),
                    _num(a["cambio_maximo"], ".4g"), _num(a["costo"], ".4g"),
                    ", ".join(map(str, a["estados_permitidos"])) if a.get("estados_permitidos") else "todos",
                ]
                for v, a in configuracion["acciones"].items()
            ],
            {3, 4, 5, 6},
        ),
        f"<p>Modificables declaradas: {_e(', '.join(configuracion['modificables']) or '—')}. Optimizador: "
        f"{_e(configuracion['optimizador'])}. μ: {_e(configuracion['mu'])}.</p>",
        "<h2>Declaración de supuestos</h2>",
        '<p class="nota">El sistema no puede verificar estas condiciones con los datos; las confirma el usuario.</p>',
        _tabla(
            ["Variable", *NOMBRES_SUPUESTOS.values(), "Confirmado el"],
            [
                [v, *("sí" if s.get(k) else "no" for k in NOMBRES_SUPUESTOS), s.get("confirmado_en") or "—"]
                for v, s in configuracion.get("supuestos", {}).items()
            ],
        ),
    ]
    if calibracion:
        partes += [
            "<h2>Calibración de μ</h2>",
            f"<p>μ elegido: <strong>{_e(decimal(calibracion['mu'], 'g'))}</strong>. Casos de entrenamiento que no "
            f"cumplen el objetivo: {calibracion['casos']} ({calibracion['alcanzables']} alcanzables, "
            f"{calibracion['no_alcanzables']} no alcanzables).</p>",
            _tabla(
                ["μ", "Tasa de éxito", "Éxitos", "Evaluados"],
                [[decimal(p["mu"], "g"), _pct(p["tasa_exito"]), p["exitos"], p["evaluados"]] for p in calibracion["rejilla"]],
                {0, 1, 2, 3},
            ),
            f'<p class="nota">{_e(calibracion["nota"])}</p>',
        ]
        if calibracion.get("advertencia"):
            partes.append(f'<div class="aviso">{_e(calibracion["advertencia"])}</div>')
    if condiciones:
        partes += [
            "<h2>Advertencias</h2>",
            "<ul>" + "".join(f"<li>{_e(c['mensaje'])}</li>" for c in condiciones) + "</ul>",
        ]
    if evaluacion:
        partes += [
            "<h2>Evaluación del prescriptor sobre test</h2>",
            f'<div class="aviso">{_e(evaluacion["texto"])}</div>',
            _tabla(
                ["Métrica", "Valor"],
                [
                    ["Casos de test que no cumplen el objetivo", evaluacion["casos"]],
                    ["Tasa de éxito", _pct(evaluacion["tasa_exito"])],
                    ["Casos no alcanzables", evaluacion["no_alcanzables"]],
                    ["Acciones que quedan en cero", decimal(evaluacion["porcentaje_acciones_en_cero"], ".1f") + " %"],
                    ["Casos que requieren revisión", decimal(evaluacion["porcentaje_requiere_revision"], ".1f") + " %"],
                    ["Casos con extrapolación", decimal(evaluacion["porcentaje_extrapolacion"], ".1f") + " %"],
                ],
                {1},
            ),
            "<h3>Cambio medio por acción (unidades originales)</h3>",
            _tabla(
                ["Variable", "Cambio medio", "Cambio absoluto medio", "Casos que la usan"],
                [[v, _num(x["cambio_medio"], ".4g"), _num(x["cambio_absoluto_medio"], ".4g"), x["usos"]]
                 for v, x in evaluacion["cambio_medio"].items()],
                {1, 2, 3},
            ),
            "<h3>Sensibilidad</h3>",
            _tabla(
                ["Cambio máximo (% del rango)", "Tasa de éxito", "Costo medio"],
                [[decimal(100 * s["fraccion_rango"], ".0f") + " %", _pct(s["tasa_exito"]), _num(s["costo_medio"])]
                 for s in evaluacion["sensibilidad_cambio_maximo"]],
                {0, 1, 2},
            ),
            _tabla(
                ["μ", "Tasa de éxito", "Costo medio"],
                [[decimal(s["mu"], "g"), _pct(s["tasa_exito"]), _num(s["costo_medio"])] for s in evaluacion["sensibilidad_mu"]],
                {0, 1, 2},
            ),
            "<h3>Comparación de optimizadores</h3>",
            _tabla(
                ["Optimizador", "Tasa de éxito", "Costo medio", "Segundos por caso"],
                [[c["optimizador"], _pct(c["tasa_exito"]), _num(c["costo_medio"]), _num(c["segundos_medios"])]
                 for c in evaluacion["comparacion_optimizadores"]],
                {1, 2, 3},
            ),
            f"<p>{_e(evaluacion['mcnemar']['prueba'])}: {evaluacion['mcnemar']['solo_gradiente']} casos solo con "
            f"gradiente proximal, {evaluacion['mcnemar']['solo_genetico']} solo con el genético; p = "
            f"{_e(decimal(evaluacion['mcnemar']['p_valor'], '.4g'))}.</p>",
            *_evidencia_y_comparador(evaluacion),
        ]
    if resultados:
        partes += [
            f"<h2>Prescripciones ({len(resultados)})</h2>",
            _tabla(
                ["Caso", "Antes", "Después", "Alcanzado", "Revisión", "Explicación", "Evidencia de vecinos"],
                [
                    [r["caso"].get("indice"), formato_objetivo(r["antes"]), formato_objetivo(r["despues"]),
                     "sí" if r["alcanzado"] else "no", "sí" if r["requiere_revision"] else "no", r["explicacion"],
                     (r.get("evidencia") or {}).get("texto", "—")]
                    for r in resultados[:500]
                ],
                {1, 2},
            ),
        ]
    estilos = _ESTILOS + ".aviso{border-left:4px solid #e8590c;padding:.5em .8em;margin:1em 0;background:#fff4e6}"
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Prescripción: {_e(nombre_proyecto)}</title><style>{estilos}</style></head>"
        f"<body><main>{''.join(partes)}</main></body></html>\n"
    )
