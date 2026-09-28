"""Decisiones a partir de un ``InformeRevision`` y de las acciones elegidas.

Cada tipo de hallazgo define sus opciones (con la sugerida y su efecto sobre
las decisiones). ``aplicar_elecciones`` construye las decisiones desde cero
aplicando, para cada hallazgo, la acción elegida por el usuario o, si no eligió
ninguna, la sugerida. ``generar_plantilla`` es el caso sin elecciones.

Criterios de las acciones sugeridas:

- Por defecto no se destruye información dudosa: se excluyen solo columnas
  que claramente no sirven como variables (identificadores, texto libre,
  constantes, fechas, copias y derivadas) y se eliminan filas duplicadas
  exactas.
- ``requiere_confirmacion`` es ``True`` en las decisiones importantes que el
  software no puede tomar solo: ceros sospechosos, mezclas de unidades,
  faltantes que dependen del objetivo, grupos redundantes y relaciones que
  involucran al objetivo (posible fuga de información). La acción sugerida de
  esas decisiones tampoco destruye nada.
- Las acciones que necesitan datos que la revisión no decide (orden ordinal,
  agrupación de clases, fórmula de una conversión) crean un valor inicial que
  el usuario edita después.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pcapp_nucleo.configuracion import ConfiguracionValidacion
from pcapp_nucleo.modelos import Hallazgo, InformeRevision, TipoColumna, TipoHallazgo
from pcapp_nucleo.preparacion import (
    AccionHallazgo,
    Codificacion,
    ConfiguracionSeparacion,
    ConversionUnidades,
    DecisionesUsuario,
    ErrorPreparacion,
    TratamientoColumna,
)


class ErrorEleccion(ErrorPreparacion):
    """Elección no válida para un hallazgo (identificador desconocido o acción no ofrecida)."""

    def __init__(self, identificador: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.identificador = identificador


@dataclass
class _Especificacion:
    """Opciones de un hallazgo: la sugerida y el efecto de cada una."""

    sugerida: str
    efectos: dict[str, Callable[[], None]]
    descripcion: str = ""
    requiere_confirmacion: bool = False


@dataclass
class _Faltantes:
    ceros_como_faltantes: bool = False
    indicador_medido: bool = False
    imputacion: str | None = None


@dataclass
class _Decisiones:
    """Acumula las decisiones mientras se recorren los hallazgos."""

    informe: InformeRevision
    configuracion: ConfiguracionValidacion
    acciones: dict[str, AccionHallazgo] = field(default_factory=dict)
    excluidas: list[str] = field(default_factory=list)
    faltantes: dict[str, _Faltantes] = field(default_factory=dict)
    codificaciones: dict[str, Codificacion] = field(default_factory=dict)
    conversiones: list[ConversionUnidades] = field(default_factory=list)
    logaritmos: list[str] = field(default_factory=list)
    fechas: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    eliminar_duplicados: bool = False
    separacion: ConfiguracionSeparacion = field(default_factory=ConfiguracionSeparacion)

    @property
    def objetivo(self) -> str | None:
        return self.informe.objetivo

    def excluir(self, *columnas: str) -> None:
        for columna in columnas:
            if columna != self.objetivo and columna not in self.excluidas:
                self.excluidas.append(columna)

    def faltante(self, columna: str) -> _Faltantes:
        return self.faltantes.setdefault(columna, _Faltantes())

    def ordinal_sugerido(self, columna: str) -> list | None:
        for hallazgo in self.informe.hallazgos:
            if hallazgo.tipo == TipoHallazgo.POSIBLE_VARIABLE_ORDINAL and hallazgo.columnas_involucradas[0] == columna:
                return list(hallazgo.evidencia["orden_sugerido"])
        return None


def _nada() -> None:
    return None


def generar_plantilla(
    informe: InformeRevision, configuracion: ConfiguracionValidacion | None = None
) -> DecisionesUsuario:
    """Decisiones con la acción sugerida para cada hallazgo."""
    return aplicar_elecciones(informe, {}, configuracion)


def aplicar_elecciones(
    informe: InformeRevision,
    elecciones: dict[str, str],
    configuracion: ConfiguracionValidacion | None = None,
) -> DecisionesUsuario:
    """Decisiones resultantes de aplicar ``elecciones`` ({identificador: acción}).

    Los hallazgos sin elección usan su acción sugerida.

    Raises:
        ErrorEleccion: si un identificador no corresponde a ningún hallazgo o la
            acción no está entre las opciones de ese hallazgo.
    """
    decisiones = _Decisiones(informe, configuracion or ConfiguracionValidacion())
    identificadores = {h.identificador for h in informe.hallazgos}
    for identificador in elecciones:
        if identificador not in identificadores:
            raise ErrorEleccion(identificador, f"No existe el hallazgo '{identificador}'.")
    for hallazgo in informe.hallazgos:
        especificacion = _ESPECIFICADORES.get(hallazgo.tipo, _informativo)(decisiones, hallazgo)
        accion = elecciones.get(hallazgo.identificador, especificacion.sugerida)
        if accion not in especificacion.efectos:
            raise ErrorEleccion(
                hallazgo.identificador,
                f"La acción '{accion}' no es válida para este hallazgo; opciones: "
                f"{', '.join(especificacion.efectos)}.",
            )
        especificacion.efectos[accion]()
        decisiones.acciones[hallazgo.identificador] = AccionHallazgo(
            accion, list(especificacion.efectos), especificacion.descripcion,
            especificacion.requiere_confirmacion,
        )
    _excluir_no_numericas(decisiones)
    return _construir(decisiones)


def _construir(decisiones: _Decisiones) -> DecisionesUsuario:
    excluidas = set(decisiones.excluidas)
    faltantes = {
        columna: TratamientoColumna(f.ceros_como_faltantes, f.indicador_medido, f.imputacion)
        for columna, f in decisiones.faltantes.items()
        if columna not in excluidas and (f.ceros_como_faltantes or f.indicador_medido or f.imputacion)
    }
    return DecisionesUsuario(
        eliminar_duplicados=decisiones.eliminar_duplicados,
        acciones_hallazgos=decisiones.acciones,
        columnas_excluidas=decisiones.excluidas,
        faltantes=faltantes,
        codificaciones={c: k for c, k in decisiones.codificaciones.items() if c not in excluidas},
        conversiones=[c for c in decisiones.conversiones if c.columna not in excluidas],
        logaritmos=[c for c in decisiones.logaritmos if c not in excluidas],
        separacion=decisiones.separacion,
        columnas_fecha_disponibles=decisiones.fechas,
        notas=decisiones.notas,
    )


# --- Especificación de cada tipo de hallazgo ---------------------------------------------


def _informativo(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    return _Especificacion("conservar", {"conservar": _nada})


def _duplicados(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    def eliminar() -> None:
        d.eliminar_duplicados = True

    return _Especificacion(
        "eliminar_duplicados", {"eliminar_duplicados": eliminar, "conservar": _nada},
        "Las filas repetidas pueden quedar a la vez en entrenamiento y test e inflar la exactitud.",
    )


def _efectos_faltantes(d: _Decisiones, columna: str) -> dict[str, Callable[[], None]]:
    def imputar(metodo: str | None) -> Callable[[], None]:
        def efecto() -> None:
            d.faltante(columna).imputacion = metodo
        return efecto

    return {
        "imputar_mediana": imputar("mediana"),
        "imputar_multivariada": imputar("multivariada"),
        "eliminar_filas": imputar("eliminar_filas"),
        "conservar_faltantes": imputar(None),
        "excluir_columna": lambda: d.excluir(columna),
    }


def _faltantes(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna = h.columnas_involucradas[0]
    if columna == d.objetivo:
        return _informativo(d, h)
    return _Especificacion("imputar_mediana", _efectos_faltantes(d, columna))


def _alta_proporcion(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    return _Especificacion("excluir_columna", _efectos_faltantes(d, h.columnas_involucradas[0]))


def _faltantes_objetivo(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna = h.columnas_involucradas[0]

    def tratamiento(imputacion: str | None, indicador: bool) -> Callable[[], None]:
        def efecto() -> None:
            f = d.faltante(columna)
            f.imputacion, f.indicador_medido = imputacion, indicador
        return efecto

    return _Especificacion(
        "imputar_con_indicador",
        {
            "excluir_columna": lambda: d.excluir(columna),
            "imputar_con_indicador": tratamiento("mediana", True),
            "solo_casos_completos": tratamiento("eliminar_filas", False),
            "conservar": tratamiento(None, False),
        },
        "Los faltantes dependen del objetivo: el indicador de 'dato medido' conserva esa "
        "información en lugar de ocultarla con la imputación.",
        requiere_confirmacion=True,
    )


def _ceros(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna = h.columnas_involucradas[0]

    def como_faltantes(imputar: bool) -> Callable[[], None]:
        def efecto() -> None:
            f = d.faltante(columna)
            f.ceros_como_faltantes = True
            if imputar:
                f.imputacion = "mediana"
        return efecto

    return _Especificacion(
        "conservar",
        {
            "conservar": _nada,
            "ceros_como_faltantes": como_faltantes(False),
            "ceros_como_faltantes_imputar_mediana": como_faltantes(True),
        },
        "Si el cero no es un valor posible para esta variable, trátelo como faltante.",
        requiere_confirmacion=True,
    )


def _excluir_columna(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna = h.columnas_involucradas[0]
    return _Especificacion("excluir_columna", {"excluir_columna": lambda: d.excluir(columna), "conservar": _nada})


def _fecha(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna = h.columnas_involucradas[0]
    d.fechas.append(columna)

    def temporal() -> None:
        d.separacion = ConfiguracionSeparacion(tipo="temporal", columna_fecha=columna)

    return _Especificacion(
        "excluir_columna",
        {"excluir_columna": lambda: d.excluir(columna), "separacion_temporal": temporal},
        "La fecha no se usa como variable. Puede usarse para separar entrenamiento y test por "
        "tiempo (lo anterior al corte para entrenar).",
    )


def _categorias_reales(d: _Decisiones, h: Hallazgo) -> list:
    """Categorías sin los textos centinela (se tratarán como faltantes)."""
    centinelas = d.configuracion.valores_centinela_faltantes
    return [c["valor"] for c in h.evidencia["categorias"] if str(c["valor"]).strip() not in centinelas]


def _categorica(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna = h.columnas_involucradas[0]
    if columna == d.objetivo:
        return _informativo(d, h)

    def codificar(codificacion: Codificacion) -> Callable[[], None]:
        def efecto() -> None:
            d.codificaciones[columna] = codificacion
        return efecto

    if h.evidencia["origen"] == "enteros":
        return _Especificacion(
            "conservar_numerica",
            {"conservar_numerica": _nada, "one_hot": codificar(Codificacion("one_hot"))},
            "Ya es numérica; se usa tal cual.",
        )
    categorias = _categorias_reales(d, h)
    orden = d.ordinal_sugerido(columna)
    efectos: dict[str, Callable[[], None]] = {}
    if len(categorias) == 2:
        efectos["binaria"] = codificar(Codificacion("binaria"))
    efectos["ordinal"] = codificar(Codificacion("ordinal", orden=orden or sorted(categorias, key=str)))
    efectos["one_hot"] = codificar(Codificacion("one_hot"))
    efectos["excluir_columna"] = lambda: d.excluir(columna)
    sugerida = "ordinal" if orden else ("binaria" if len(categorias) == 2 else "one_hot")
    descripcion = "La codificación one-hot añade variables a PC." if sugerida == "one_hot" else ""
    return _Especificacion(sugerida, efectos, descripcion)


def _ordinal(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna = h.columnas_involucradas[0]

    def sin_orden() -> None:
        codificacion = d.codificaciones.get(columna)
        if codificacion is not None and codificacion.tipo == "ordinal":
            d.codificaciones[columna] = Codificacion("one_hot")

    return _Especificacion(
        "usar_orden_sugerido", {"usar_orden_sugerido": _nada, "sin_orden": sin_orden},
        f"Orden sugerido: {h.evidencia['orden_sugerido']}.",
    )


def _distribucion(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    clases = [c["valor"] for c in h.evidencia["distribucion"]]
    if len(clases) <= 2:
        return _informativo(d, h)
    grupos = {str(valor): 0 if i == 0 else 1 for i, valor in enumerate(sorted(clases, key=str))}

    def agrupar() -> None:
        d.codificaciones[d.objetivo] = Codificacion("agrupacion", grupos=grupos)

    return _Especificacion(
        "conservar_clases", {"conservar_clases": _nada, "agrupar_clases": agrupar},
        f"El objetivo tiene {len(clases)} clases. Al agruparlas se parte de {grupos}; edite los "
        "grupos en las decisiones.",
    )


def _derivada(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    if d.objetivo in h.columnas_involucradas:
        otras = [c for c in h.columnas_involucradas if c != d.objetivo]
        return _Especificacion(
            "conservar", {"conservar": _nada, "excluir_derivada": lambda: d.excluir(*otras)},
            "La relación involucra al objetivo: posible fuga de información. Revise si alguna "
            "variable se calculó a partir del objetivo (o al revés); excluirla elimina "
            f"{otras} del análisis.",
            requiere_confirmacion=True,
        )
    derivadas = h.evidencia.get("derivada_sugerida", [])
    return _Especificacion(
        "excluir_derivada", {"excluir_derivada": lambda: d.excluir(*derivadas), "conservar": _nada},
        f"Se sugiere conservar {h.evidencia.get('original_sugerida')} y excluir {derivadas}.",
    )


def _recodificacion(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna_a, columna_b = h.columnas_involucradas
    if d.objetivo in (columna_a, columna_b):
        return _derivada(d, h)
    return _Especificacion(
        "excluir_una", {"excluir_una": lambda: d.excluir(columna_b), "conservar": _nada},
        f"Ambas columnas contienen la misma información; se sugiere conservar '{columna_a}'.",
    )


def _correlacion(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna_a, columna_b = h.columnas_involucradas
    excluida = columna_a if columna_b == d.objetivo else columna_b
    lineal = h.evidencia.get("tipo_relacion") == "transformacion_lineal"
    sugerida = "excluir_una" if lineal and d.objetivo not in (columna_a, columna_b) else "conservar"
    descripcion = f"'{columna_b}' es una transformación lineal exacta de '{columna_a}'." if lineal else ""
    return _Especificacion(
        sugerida, {"excluir_una": lambda: d.excluir(excluida), "conservar": _nada}, descripcion
    )


def _mezcla_unidades(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna = h.columnas_involucradas[0]
    bajo, alto = h.evidencia["grupo_bajo"], h.evidencia["grupo_alto"]
    umbral = round((bajo["maximo"] + alto["minimo"]) / 2, 4)

    def convertir() -> None:
        d.conversiones.append(
            ConversionUnidades(
                columna, ">", umbral, 0.0, 1.0,
                "Complete 'restar' y 'multiplicar' (p. ej. °F → °C: restar 32, multiplicar 5/9).",
            )
        )

    return _Especificacion(
        "conservar", {"conservar": _nada, "convertir_unidades": convertir},
        f"Los valores forman dos grupos ({bajo['minimo']:g}–{bajo['maximo']:g} y "
        f"{alto['minimo']:g}–{alto['maximo']:g}). Si corresponden a unidades distintas, conviértalos "
        f"a una sola escala (se propone el umbral {umbral:g}).",
        requiere_confirmacion=True,
    )


def _grupo_redundante(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    representante, *resto = h.columnas_involucradas
    return _Especificacion(
        "conservar", {"conservar": _nada, "excluir_variables": lambda: d.excluir(*resto)},
        f"PC tiende a conservar solo una variable del grupo como causa. Excluir las demás deja "
        f"solo '{representante}'.",
        requiere_confirmacion=True,
    )


def _asimetria(d: _Decisiones, h: Hallazgo) -> _Especificacion:
    columna = h.columnas_involucradas[0]
    if columna == d.objetivo:
        return _informativo(d, h)
    return _Especificacion(
        "aplicar_logaritmo", {"aplicar_logaritmo": lambda: d.logaritmos.append(columna), "conservar": _nada}
    )


_ESPECIFICADORES = {
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


def _excluir_no_numericas(d: _Decisiones) -> None:
    """Excluye columnas que no serían numéricas tras la preparación, con una nota."""
    no_numericas = (TipoColumna.CATEGORICA, TipoColumna.TEXTO, TipoColumna.FECHA, TipoColumna.VACIA)
    temporal = d.separacion.columna_fecha if d.separacion.tipo == "temporal" else None
    for perfil in d.informe.perfiles_columnas:
        columna = perfil.nombre
        if columna in (d.objetivo, temporal) or columna in d.excluidas:
            continue
        if perfil.tipo_detectado in no_numericas and columna not in d.codificaciones:
            d.excluir(columna)
            d.notas.append(
                f"La columna '{columna}' ({perfil.tipo_detectado}) no tiene una codificación "
                "elegida y se excluye; puede codificarla editando 'codificaciones'."
            )
