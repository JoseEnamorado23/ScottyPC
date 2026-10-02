"""Condiciones para prescribir: mismo formato de problemas que la aplicabilidad del modelo causal."""

from __future__ import annotations

from pcapp_nucleo.causal.aplicabilidad import ADVERTENCIA, BLOQUEANTE, ProblemaAplicabilidad
from pcapp_nucleo.causal.modelo import BINARIA, INTERMEDIA, ModeloCausal
from pcapp_nucleo.prescripcion.configuracion import ConfiguracionPrescripcion, variables_prescriptivas

MODELO_CAUSAL, PRESCRIPCION, RESULTADOS = "modelo_causal", "prescripcion", "resultados"
MENSAJE_SIN_PRESCRIPTIVAS = "Con estos datos no hay variables prescriptivas"


def evaluar_prescribibilidad(
    modelo: ModeloCausal | None,
    configuracion: ConfiguracionPrescripcion | None,
    vigente: bool = True,
) -> list[ProblemaAplicabilidad]:
    """Bloqueantes y advertencias para prescribir con ``modelo`` y ``configuracion``.

    ``vigente`` = el modelo causal está vigente (el sidecar lo sabe por las etapas y la versión
    del resultado de PC). Sin modelo, solo se informa ese bloqueante.
    """
    problemas: list[ProblemaAplicabilidad] = []
    if modelo is None or not vigente:
        problemas.append(ProblemaAplicabilidad(
            "MODELO_NO_VIGENTE", BLOQUEANTE,
            "El modelo causal no está vigente: la prescripción se apoya en él.",
            "Construya (o reconstruya) el modelo causal.", MODELO_CAUSAL,
        ))
        if modelo is None:
            return problemas

    modificables = configuracion.modificables if configuracion else []
    variables = variables_prescriptivas(modelo, modificables)
    if not variables.prescriptivas:
        if not modificables:
            motivo = "no hay ninguna variable marcada como modificable."
        else:
            motivo = (
                f"las modificables marcadas ({', '.join(modificables)}) no tienen camino hacia "
                f"'{modelo.objetivo}' en el grafo causal."
            )
        problemas.append(ProblemaAplicabilidad(
            "SIN_PRESCRIPTIVAS", BLOQUEANTE,
            f"{MENSAJE_SIN_PRESCRIPTIVAS}: una variable prescriptiva debe ser a la vez ancestro del "
            f"objetivo y modificable, y {motivo}",
            "Marque como modificables variables que sean causas (directas o indirectas) del objetivo.",
            PRESCRIPCION, list(modificables),
        ))
    elif configuracion is not None:
        permitidas = [v for v in variables.prescriptivas if configuracion.acciones.get(v) is None or configuracion.acciones[v].permitida]
        if not permitidas:
            problemas.append(ProblemaAplicabilidad(
                "NINGUNA_PERMITIDA", BLOQUEANTE, "Todas las variables prescriptivas están marcadas como no permitidas.",
                "Permita al menos una variable en la configuración.", PRESCRIPCION, list(variables.prescriptivas),
            ))
        sin_confirmar = [
            v for v in permitidas if not (configuracion.supuestos.get(v) and configuracion.supuestos[v].confirmados)
        ]
        if sin_confirmar:
            problemas.append(ProblemaAplicabilidad(
                "SUPUESTOS_SIN_CONFIRMAR", BLOQUEANTE,
                "Falta confirmar la declaración de supuestos de: " + ", ".join(sin_confirmar)
                + ". El sistema no puede verificar con los datos que se puedan modificar mediante una decisión "
                "real, que se midan antes del resultado ni que no formen parte de la definición del objetivo.",
                "Confirme la declaración de supuestos de cada variable en la configuración.", PRESCRIPCION, sin_confirmar,
            ))

    if variables.sin_camino:
        problemas.append(ProblemaAplicabilidad(
            "MODIFICABLES_SIN_CAMINO", ADVERTENCIA,
            f"Estas modificables no tienen camino hacia '{modelo.objetivo}' y se ignoran: "
            f"{', '.join(variables.sin_camino)}.",
            "No requiere acción; puede quitarlas de la lista de modificables.", PRESCRIPCION, list(variables.sin_camino),
        ))
    if variables.desconocidas:
        problemas.append(ProblemaAplicabilidad(
            "MODIFICABLES_DESCONOCIDAS", ADVERTENCIA,
            f"Estas modificables no son variables del grafo y se ignoran: {', '.join(variables.desconocidas)}.",
            "Quítelas de la lista de modificables.", PRESCRIPCION, list(variables.desconocidas),
        ))
    if any(a.get("codigo") == "COSTO_PARSIMONIA" for a in modelo.datos.get("advertencias", [])):
        problemas.append(ProblemaAplicabilidad(
            "COSTO_PARSIMONIA", ADVERTENCIA,
            "El modelo causal predice peor que un modelo con todas las variables (costo de la parsimonia): las "
            "probabilidades en las que se basan las prescripciones deben interpretarse con cuidado.",
            "Revise la evaluación del modelo causal.", MODELO_CAUSAL,
        ))
    binarias = [v for v in modelo.variables if modelo.info_variables[v]["rol"] == INTERMEDIA and modelo.tipo(v) == BINARIA]
    if binarias:
        problemas.append(ProblemaAplicabilidad(
            "INTERMEDIAS_BINARIAS", ADVERTENCIA,
            f"Hay intermedias binarias ({', '.join(binarias)}): cada resultado es una aproximación de Monte Carlo.",
            "No requiere acción.", None, binarias,
        ))
    return problemas
