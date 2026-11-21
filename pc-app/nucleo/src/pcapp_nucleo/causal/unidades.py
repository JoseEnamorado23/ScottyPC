"""Conversión entre unidades originales y preparadas, a partir de la receta.

La preparación de una columna, en el orden de ``preparacion._preprocesar``, es:
conversión de unidades → logaritmo (``log`` o ``log1p``) → codificación → imputación →
normalización min–max. Aquí «unidades originales» son las del dataset tras la conversión
de unidades (que es condicional y no se deshace): números para las columnas numéricas y
etiquetas para las codificadas.

Las columnas one-hot se agrupan por su columna original: el valor de un grupo es una
categoría; la categoría de referencia es la que deja todas las dummies en 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from pcapp_nucleo.preparacion import MetadatosColumna, _mismo_valor

# Tipos de control de una variable en los escenarios.
NUMERICA, ORDINAL, CATEGORICA, GRUPO = "numerica", "ordinal", "categorica", "grupo_one_hot"


class ErrorUnidades(ValueError):
    """Un valor no es válido para la variable (tipo, categoría o dominio)."""


@dataclass(frozen=True)
class GrupoCategorico:
    """Dummies one-hot de una columna original. ``columnas[i]`` corresponde a ``categorias[i + 1]``."""

    nombre: str
    referencia: Any
    categorias: list[Any]
    columnas: list[str]


@dataclass(frozen=True)
class DescripcionVariable:
    """Cómo se controla una variable (o grupo) en unidades originales."""

    nombre: str
    control: str
    columnas: list[str]
    categorias: list[Any] = field(default_factory=list)
    minimo: float | None = None
    maximo: float | None = None


class Unidades:
    """Conversión por columna preparada; se construye con los metadatos de la receta."""

    def __init__(self, columnas: list[MetadatosColumna]) -> None:
        self.metadatos = {c.nombre: c for c in columnas}
        grupos: dict[str, dict[str, Any]] = {}
        for c in columnas:
            if c.tipo_final == "one_hot" and "columna_original" in c.parametros:
                p = c.parametros
                grupo = grupos.setdefault(p["columna_original"], {"referencia": p.get("referencia"), "pares": []})
                grupo["pares"].append((p.get("categoria"), c.nombre))
        self.grupos = {
            nombre: GrupoCategorico(
                nombre, g["referencia"], [g["referencia"], *(cat for cat, _ in g["pares"])],
                [col for _, col in g["pares"]],
            )
            for nombre, g in grupos.items()
        }
        self.grupo_de = {col: g.nombre for g in self.grupos.values() for col in g.columnas}

    # --- Descripción ---------------------------------------------------------------------------

    def _parametros(self, columna: str) -> dict[str, Any]:
        metadatos = self.metadatos.get(columna)
        return dict(metadatos.parametros) if metadatos else {}

    def _logaritmo(self, columna: str) -> str | None:
        metadatos = self.metadatos.get(columna)
        if metadatos is None:
            return None
        for transformacion in metadatos.transformaciones:
            if transformacion in ("log", "log1p"):
                return transformacion
        return None

    def mapeo(self, columna: str) -> list[list[Any]] | None:
        """Pares [valor original, código] de una columna codificada (binaria, ordinal o agrupación)."""
        mapeo = self._parametros(columna).get("mapeo")
        return [list(par) for par in mapeo] if mapeo else None

    def control(self, columna: str) -> str:
        if columna in self.grupo_de:
            return GRUPO
        metadatos = self.metadatos.get(columna)
        tipo = metadatos.tipo_final if metadatos else None
        if self.mapeo(columna) is not None:
            return ORDINAL if tipo == "ordinal" else CATEGORICA
        if tipo in ("binaria", "indicador", "one_hot"):
            return CATEGORICA
        return NUMERICA

    def describir(self, nombre: str, minimo: float | None = None, maximo: float | None = None) -> DescripcionVariable:
        """``minimo`` y ``maximo`` (unidades preparadas, de train) se pasan a unidades originales."""
        if nombre in self.grupos:
            grupo = self.grupos[nombre]
            return DescripcionVariable(nombre, GRUPO, list(grupo.columnas), list(grupo.categorias))
        control = self.control(nombre)
        categorias: list[Any] = []
        mapeo = self.mapeo(nombre)
        if mapeo is not None:
            categorias = [original for original, _ in sorted(mapeo, key=lambda par: par[1])]
        elif control == CATEGORICA:
            categorias = [0, 1]
        bajo = self.a_original(nombre, minimo) if minimo is not None and control == NUMERICA else None
        alto = self.a_original(nombre, maximo) if maximo is not None and control == NUMERICA else None
        return DescripcionVariable(nombre, control, [nombre], categorias, bajo, alto)

    # --- Conversión ----------------------------------------------------------------------------

    def _normalizar(self, columna: str, valor: float) -> float:
        p = self._parametros(columna)
        if "minimo" in p and "maximo" in p:
            rango = p["maximo"] - p["minimo"]
            return (valor - p["minimo"]) / rango if rango > 0 else 0.0
        return valor

    def _desnormalizar(self, columna: str, valor: float) -> float:
        p = self._parametros(columna)
        if "minimo" in p and "maximo" in p:
            return valor * (p["maximo"] - p["minimo"]) + p["minimo"]
        return valor

    def codigo(self, columna: str, valor: Any) -> float:
        """Código numérico (antes de normalizar) de un valor original."""
        mapeo = self.mapeo(columna)
        if mapeo is not None:
            for original, codigo in mapeo:
                if _mismo_valor(valor, original):
                    return float(codigo)
            for _, codigo in mapeo:
                if _es_numero(valor) and float(valor) == float(codigo):
                    return float(codigo)
            opciones = ", ".join(repr(o) for o, _ in mapeo)
            raise ErrorUnidades(f"'{valor}' no es un valor de '{columna}' (valores posibles: {opciones}).")
        if not _es_numero(valor):
            raise ErrorUnidades(f"'{columna}' necesita un número; se recibió {valor!r}.")
        numero = float(valor)
        if self.control(columna) == CATEGORICA and numero not in (0.0, 1.0):
            raise ErrorUnidades(f"'{columna}' solo admite 0 o 1; se recibió {valor!r}.")
        logaritmo = self._logaritmo(columna)
        if logaritmo == "log":
            if numero <= 0:
                raise ErrorUnidades(f"'{columna}' debe ser mayor que 0 (se usa su logaritmo).")
            return math.log(numero)
        if logaritmo == "log1p":
            if numero <= -1:
                raise ErrorUnidades(f"'{columna}' debe ser mayor que -1 (se usa log(1 + x)).")
            return math.log1p(numero)
        return numero

    def a_preparada(self, columna: str, valor: Any) -> float:
        return self._normalizar(columna, self.codigo(columna, valor))

    def a_original_numerico(self, columna: str, valor: float) -> float:
        """Valor original como número (para las codificadas, el código)."""
        numero = self._desnormalizar(columna, float(valor))
        logaritmo = self._logaritmo(columna)
        if logaritmo == "log":
            return math.exp(numero)
        if logaritmo == "log1p":
            return math.expm1(numero)
        return numero

    def a_preparada_numerica(self, columna: str, valor: float) -> float:
        """Inversa de ``a_original_numerico``: de un número original (para las codificadas, su
        código) a la escala preparada. No ambigua con etiquetas numéricas, a diferencia de
        ``a_preparada``, que interpreta primero el valor como etiqueta.

        Raises:
            ErrorUnidades: si el valor no está en el dominio (p. ej. ≤ 0 con logaritmo).
        """
        if self.mapeo(columna) is not None:
            return self._normalizar(columna, float(valor))
        return self.a_preparada(columna, valor)

    # --- Ordinales: valores originales frente a códigos ----------------------------------------
    #
    # El «valor original» de un nivel es su etiqueta cuando todas las etiquetas son números (créditos
    # 14, 15, …) y su posición (el código 0, 1, …) cuando no lo son («bajo», «medio», «alto»). Los
    # límites, el cambio máximo y la dirección de una ordinal se escriben SIEMPRE en ese valor; el
    # código es interno y la conversión es esta, única.

    def niveles_ordinal(self, columna: str) -> list[tuple[float, float]]:
        """Pares (valor original, código) de cada nivel, por código creciente."""
        mapeo = sorted(self.mapeo(columna) or [], key=lambda par: par[1])
        numericas = all(_es_numero(original) for original, _ in mapeo)
        return [(float(original) if numericas else float(codigo), float(codigo)) for original, codigo in mapeo]

    def etiquetas_numericas(self, columna: str) -> bool:
        """True si los límites de la ordinal se escriben en sus etiquetas; False si se cuentan niveles."""
        mapeo = self.mapeo(columna) or []
        return bool(mapeo) and all(_es_numero(original) for original, _ in mapeo)

    def valor_de_codigo(self, columna: str, codigo: float) -> float:
        """Valor original (numérico) de un código; entre dos niveles, interpolación lineal."""
        niveles = self.niveles_ordinal(columna)
        codigos = [c for _, c in niveles]
        valores = [v for v, _ in niveles]
        if len(niveles) < 2:
            return valores[0] if valores else float(codigo)
        return float(np.interp(float(codigo), codigos, valores))

    def niveles_permitidos(
        self, columna: str, minimo: float | None = None, maximo: float | None = None,
        centro: float | None = None, radio: float | None = None, sentido: str | None = None,
    ) -> list[float]:
        """Códigos de los niveles cuyo valor original está entre ``minimo`` y ``maximo``, a no más de
        ``radio`` del valor del código ``centro`` y, si ``sentido`` es ``subir`` o ``bajar``, no por
        debajo/encima de él."""
        valor_centro = self.valor_de_codigo(columna, centro) if centro is not None else None
        permitidos = []
        for valor, codigo in self.niveles_ordinal(columna):
            holgura = 1e-9 * max(1.0, abs(valor))
            if minimo is not None and valor < minimo - holgura:
                continue
            if maximo is not None and valor > maximo + holgura:
                continue
            if valor_centro is not None:
                if radio is not None and abs(valor - valor_centro) > radio + holgura:
                    continue
                if sentido == "subir" and valor < valor_centro - holgura:
                    continue
                if sentido == "bajar" and valor > valor_centro + holgura:
                    continue
            permitidos.append(codigo)
        return permitidos

    def a_original(self, columna: str, valor: float | None) -> Any:
        """Valor en unidades originales: número o, si es un código exacto, su etiqueta."""
        if valor is None or (isinstance(valor, float) and math.isnan(valor)):
            return None
        numero = self.a_original_numerico(columna, valor)
        mapeo = self.mapeo(columna)
        if mapeo is not None:
            etiquetas = [o for o, c in mapeo if abs(float(c) - numero) < 1e-9]
            if len(etiquetas) == 1:
                return etiquetas[0]
        return numero

    def categoria_de_grupo(self, grupo: str, valores: dict[str, float]) -> Any:
        """Categoría de un grupo one-hot según sus dummies (en unidades preparadas)."""
        g = self.grupos[grupo]
        activas = [g.categorias[i + 1] for i, col in enumerate(g.columnas) if valores.get(col, 0.0) >= 0.5]
        return activas[0] if len(activas) == 1 else (g.referencia if not activas else None)

    def dummies_de_categoria(self, grupo: str, categoria: Any) -> dict[str, float]:
        """Valores preparados de las dummies de un grupo al fijar ``categoria``."""
        g = self.grupos[grupo]
        if not any(_mismo_valor(categoria, c) for c in g.categorias):
            opciones = ", ".join(repr(c) for c in g.categorias)
            raise ErrorUnidades(f"'{categoria}' no es una categoría de '{grupo}' (categorías: {opciones}).")
        return {
            col: self._normalizar(col, 1.0 if _mismo_valor(categoria, g.categorias[i + 1]) else 0.0)
            for i, col in enumerate(g.columnas)
        }


def _es_numero(valor: Any) -> bool:
    if isinstance(valor, bool):
        return False
    try:
        return math.isfinite(float(valor))
    except (TypeError, ValueError):
        return False
