"""Plantilla de decisiones a partir de un ``InformeRevision``.

``generar_plantilla`` traduce cada hallazgo en la acción sugerida para que
el usuario (o la futura interfaz) solo tenga que revisarla y editarla.
Criterios:

- Por defecto no se destruye información dudosa: se excluyen solo columnas
  que claramente no sirven como variables (identificadores, texto libre,
  constantes, fechas, copias y derivadas) y se eliminan filas duplicadas
  exactas.
- ``requiere_confirmacion`` es ``True`` en las decisiones importantes que el
  software no puede tomar solo: ceros sospechosos, mezclas de unidades,
  faltantes que dependen del objetivo, grupos redundantes y relaciones que
  involucran al objetivo (posible fuga de información). La acción por
  defecto de esas decisiones tampoco destruye nada.
"""

from __future__ import annotations

from typing import Any

from pcapp_nucleo.configuracion import ConfiguracionValidacion
from pcapp_nucleo.modelos import Hallazgo, InformeRevision, TipoColumna, TipoHallazgo
from pcapp_nucleo.preparacion import (
    AccionHallazgo,
    Codificacion,
    ConfiguracionSeparacion,
    DecisionesUsuario,
    TratamientoColumna,
)

_OPCIONES_FALTANTES = [
    "imputar_mediana", "imputar_multivariada", "eliminar_filas", "conservar_faltantes",
    "excluir_columna",
]
_OPCIONES_EXCLUIR = ["excluir_columna", "conservar"]


class _Plantilla:
    """Acumula las decisiones mientras se recorren los hallazgos."""

    def __init__(self, informe: InformeRevision, configuracion: ConfiguracionValidacion) -> None:
        self.configuracion = configuracion
        self.objetivo = informe.objetivo
        self.acciones: dict[str, AccionHallazgo] = {}
        self.excluidas: list[str] = []
        self.faltantes: dict[str, TratamientoColumna] = {}
        self.codificaciones: dict[str, Codificacion] = {}
        self.logaritmos: list[str] = []
        self.fechas: list[str] = []
        self.notas: list[str] = []
        self.eliminar_duplicados = False
        self.ordinales = {
            h.columnas_involucradas[0]: h.evidencia["orden_sugerido"]
            for h in informe.hallazgos
            if h.tipo == TipoHallazgo.POSIBLE_VARIABLE_ORDINAL
        }

    def accion(
        self, hallazgo: Hallazgo, accion: str, opciones: list[str], descripcion: str = "",
        requiere_confirmacion: bool = False,
    ) -> None:
        self.acciones[hallazgo.identificador] = AccionHallazgo(
            accion, opciones, descripcion, requiere_confirmacion
        )

    def excluir(self, *columnas: str) -> None:
        for columna in columnas:
            if columna != self.objetivo and columna not in self.excluidas:
                self.excluidas.append(columna)


def generar_plantilla(
    informe: InformeRevision, configuracion: ConfiguracionValidacion | None = None
) -> DecisionesUsuario:
    """Decisiones prellenadas con la acción sugerida para cada hallazgo."""
    plantilla = _Plantilla(informe, configuracion or ConfiguracionValidacion())
    for hallazgo in informe.hallazgos:
        _TRADUCTORES.get(hallazgo.tipo, _informativo)(plantilla, hallazgo)
    _excluir_no_numericas(plantilla, informe)
    excluidas = set(plantilla.excluidas)
    return DecisionesUsuario(
        eliminar_duplicados=plantilla.eliminar_duplicados,
        acciones_hallazgos=plantilla.acciones,
        columnas_excluidas=plantilla.excluidas,
        faltantes={c: t for c, t in plantilla.faltantes.items() if c not in excluidas},
        codificaciones={c: k for c, k in plantilla.codificaciones.items() if c not in excluidas},
        logaritmos=[c for c in plantilla.logaritmos if c not in excluidas],
        separacion=ConfiguracionSeparacion(),
        columnas_fecha_disponibles=plantilla.fechas,
        notas=plantilla.notas,
    )


# --- Traducción de cada tipo de hallazgo -----------------------------------------------


def _informativo(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    plantilla.accion(hallazgo, "conservar", ["conservar"])


def _duplicados(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    plantilla.eliminar_duplicados = True
    plantilla.accion(
        hallazgo, "eliminar_duplicados", ["eliminar_duplicados", "conservar"],
        "Las filas repetidas pueden quedar a la vez en entrenamiento y test e inflar la exactitud.",
    )


def _faltantes(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    columna = hallazgo.columnas_involucradas[0]
    if columna == plantilla.objetivo:
        _informativo(plantilla, hallazgo)
        return
    plantilla.faltantes.setdefault(columna, TratamientoColumna(imputacion="mediana"))
    plantilla.accion(hallazgo, "imputar_mediana", _OPCIONES_FALTANTES)


def _alta_proporcion(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    plantilla.excluir(hallazgo.columnas_involucradas[0])
    plantilla.accion(hallazgo, "excluir_columna", _OPCIONES_FALTANTES)


def _faltantes_objetivo(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    columna = hallazgo.columnas_involucradas[0]
    plantilla.faltantes[columna] = TratamientoColumna(imputacion="mediana", indicador_medido=True)
    plantilla.accion(
        hallazgo, "imputar_con_indicador",
        ["excluir_columna", "imputar_con_indicador", "solo_casos_completos", "conservar"],
        "Los faltantes dependen del objetivo: el indicador de 'dato medido' conserva esa "
        "información en lugar de ocultarla con la imputación.",
        requiere_confirmacion=True,
    )


def _ceros(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    plantilla.accion(
        hallazgo, "conservar", ["conservar", "ceros_como_faltantes"],
        "Si el cero no es un valor posible, marque 'ceros_como_faltantes' en 'faltantes' "
        "para esta columna.",
        requiere_confirmacion=True,
    )


def _excluir_columna(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    plantilla.excluir(hallazgo.columnas_involucradas[0])
    plantilla.accion(hallazgo, "excluir_columna", _OPCIONES_EXCLUIR)


def _fecha(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    columna = hallazgo.columnas_involucradas[0]
    plantilla.excluir(columna)
    plantilla.fechas.append(columna)
    plantilla.accion(
        hallazgo, "excluir_columna", ["excluir_columna", "separacion_temporal"],
        f"Para separar por tiempo, use 'separacion': {{'tipo': 'temporal', "
        f"'columna_fecha': '{columna}'}}.",
    )


def _categorica(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    columna = hallazgo.columnas_involucradas[0]
    if columna == plantilla.objetivo:
        _informativo(plantilla, hallazgo)
        return
    if hallazgo.evidencia["origen"] == "enteros":
        plantilla.accion(
            hallazgo, "conservar_numerica", ["conservar_numerica", "one_hot"],
            "Ya es numérica; se usa tal cual.",
        )
        return
    if columna in plantilla.ordinales:
        plantilla.codificaciones[columna] = Codificacion("ordinal", orden=plantilla.ordinales[columna])
        accion = "ordinal"
    elif _categorias_reales(plantilla, hallazgo) == 2:
        plantilla.codificaciones[columna] = Codificacion("binaria")
        accion = "binaria"
    else:
        plantilla.codificaciones[columna] = Codificacion("one_hot")
        accion = "one_hot"
    descripcion = "La codificación one-hot añade variables a PC." if accion == "one_hot" else ""
    plantilla.accion(hallazgo, accion, ["binaria", "ordinal", "one_hot", "excluir_columna"], descripcion)


def _categorias_reales(plantilla: _Plantilla, hallazgo: Hallazgo) -> int:
    """Categorías sin contar los textos centinela (se tratarán como faltantes)."""
    centinelas = plantilla.configuracion.valores_centinela_faltantes
    return sum(
        1 for categoria in hallazgo.evidencia["categorias"]
        if str(categoria["valor"]).strip() not in centinelas
    )


def _ordinal(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    plantilla.accion(
        hallazgo, "usar_orden_sugerido", ["usar_orden_sugerido", "sin_orden"],
        f"Orden sugerido: {hallazgo.evidencia['orden_sugerido']}.",
    )


def _distribucion(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    clases = [d["valor"] for d in hallazgo.evidencia["distribucion"]]
    if len(clases) <= 2:
        _informativo(plantilla, hallazgo)
        return
    ejemplo = {str(valor): 0 if i == 0 else 1 for i, valor in enumerate(sorted(clases, key=str))}
    plantilla.accion(
        hallazgo, "conservar_clases", ["conservar_clases", "agrupar_clases"],
        f"El objetivo tiene {len(clases)} clases. Para agruparlas, agregue en 'codificaciones' "
        f"una entrada para '{plantilla.objetivo}' con tipo 'agrupacion' y 'grupos' "
        f"{{valor_original: nuevo_valor}}; por ejemplo {ejemplo}.",
    )


def _derivada(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    derivadas = hallazgo.evidencia.get("derivada_sugerida", [])
    if plantilla.objetivo in hallazgo.columnas_involucradas:
        plantilla.accion(
            hallazgo, "conservar", ["conservar", "excluir_derivada"],
            "La relación involucra al objetivo: posible fuga de información. Revise si alguna "
            "variable se calculó a partir del objetivo (o al revés).",
            requiere_confirmacion=True,
        )
        return
    plantilla.excluir(*derivadas)
    plantilla.accion(
        hallazgo, "excluir_derivada", ["excluir_derivada", "conservar"],
        f"Se sugiere conservar {hallazgo.evidencia.get('original_sugerida')} y excluir {derivadas}.",
    )


def _recodificacion(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    columna_a, columna_b = hallazgo.columnas_involucradas
    if plantilla.objetivo in (columna_a, columna_b):
        _derivada(plantilla, hallazgo)
        return
    plantilla.excluir(columna_b)
    plantilla.accion(
        hallazgo, "excluir_una", ["excluir_una", "conservar"],
        f"Ambas columnas contienen la misma información; se sugiere conservar '{columna_a}'.",
    )


def _correlacion(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    columna_a, columna_b = hallazgo.columnas_involucradas
    lineal = hallazgo.evidencia.get("tipo_relacion") == "transformacion_lineal"
    if lineal and plantilla.objetivo not in (columna_a, columna_b):
        plantilla.excluir(columna_b)
        plantilla.accion(
            hallazgo, "excluir_una", ["excluir_una", "conservar"],
            f"'{columna_b}' es una transformación lineal exacta de '{columna_a}'.",
        )
    else:
        plantilla.accion(hallazgo, "conservar", ["conservar", "excluir_una"])


def _mezcla_unidades(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    columna = hallazgo.columnas_involucradas[0]
    bajo, alto = hallazgo.evidencia["grupo_bajo"], hallazgo.evidencia["grupo_alto"]
    umbral = round((bajo["maximo"] + alto["minimo"]) / 2, 4)
    ejemplo: dict[str, Any] = {
        "columna": columna, "condicion": ">", "umbral": umbral, "restar": 32,
        "multiplicar": round(5 / 9, 6), "descripcion": "°F → °C",
    }
    plantilla.accion(
        hallazgo, "conservar", ["conservar", "convertir_unidades"],
        "Si los grupos corresponden a unidades distintas, agregue una entrada en "
        f"'conversiones'; por ejemplo {ejemplo}.",
        requiere_confirmacion=True,
    )


def _grupo_redundante(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    plantilla.accion(
        hallazgo, "conservar", ["conservar", "excluir_variables"],
        "PC tiende a conservar solo una variable del grupo como causa.",
        requiere_confirmacion=True,
    )


def _asimetria(plantilla: _Plantilla, hallazgo: Hallazgo) -> None:
    columna = hallazgo.columnas_involucradas[0]
    if columna == plantilla.objetivo:
        _informativo(plantilla, hallazgo)
        return
    plantilla.logaritmos.append(columna)
    plantilla.accion(hallazgo, "aplicar_logaritmo", ["aplicar_logaritmo", "conservar"])


_TRADUCTORES = {
    TipoHallazgo.FILAS_DUPLICADAS: _duplicados,
    TipoHallazgo.VALORES_FALTANTES: _faltantes,
    TipoHallazgo.ALTA_PROPORCION_FALTANTES: _alta_proporcion,
    TipoHallazgo.FALTANTES_DEPENDIENTES_OBJETIVO: _faltantes_objetivo,
    TipoHallazgo.CEROS_SOSPECHOSOS: _ceros,
    TipoHallazgo.CONSTANTE: _excluir_columna,
    TipoHallazgo.POSIBLE_IDENTIFICADOR: _excluir_columna,
    TipoHallazgo.TEXTO_LIBRE: _excluir_columna,
    TipoHallazgo.POSIBLE_FECHA: _fecha,
    TipoHallazgo.VARIABLE_CATEGORICA: _categorica,
    TipoHallazgo.POSIBLE_VARIABLE_ORDINAL: _ordinal,
    TipoHallazgo.DISTRIBUCION_OBJETIVO: _distribucion,
    TipoHallazgo.COLUMNAS_REDUNDANTES: _derivada,
    TipoHallazgo.COLUMNA_DERIVADA: _derivada,
    TipoHallazgo.BINARIA_DERIVADA: _derivada,
    TipoHallazgo.RECODIFICACION_UNO_A_UNO: _recodificacion,
    TipoHallazgo.CORRELACION_CASI_PERFECTA: _correlacion,
    TipoHallazgo.POSIBLE_MEZCLA_UNIDADES: _mezcla_unidades,
    TipoHallazgo.GRUPO_REDUNDANTE: _grupo_redundante,
    TipoHallazgo.ASIMETRIA_FUERTE: _asimetria,
}


def _excluir_no_numericas(plantilla: _Plantilla, informe: InformeRevision) -> None:
    """Excluye columnas que no serían numéricas tras la preparación, con una nota."""
    no_numericas = (TipoColumna.CATEGORICA, TipoColumna.TEXTO, TipoColumna.FECHA, TipoColumna.VACIA)
    for perfil in informe.perfiles_columnas:
        columna = perfil.nombre
        if columna == plantilla.objetivo or columna in plantilla.excluidas:
            continue
        if perfil.tipo_detectado in no_numericas and columna not in plantilla.codificaciones:
            plantilla.excluir(columna)
            plantilla.notas.append(
                f"La columna '{columna}' ({perfil.tipo_detectado}) no tiene una codificación "
                "sugerida y se excluye; puede codificarla editando 'codificaciones'."
            )
