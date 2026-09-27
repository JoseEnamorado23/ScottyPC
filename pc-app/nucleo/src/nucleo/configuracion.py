"""Configuración central del núcleo.

Todos los umbrales que usarán la validación y la revisión se definen aquí
para evitar números mágicos dispersos por el código. Los porcentajes se
expresan en escala 0–100.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfiguracionValidacion:
    """Valores configurables para la validación y revisión de datasets."""

    # Formato y tamaño
    formatos_aceptados: tuple[str, ...] = (".csv", ".xlsx")
    minimo_filas: int = 100
    maximo_columnas: int = 50

    # Lectura de CSV
    separadores_csv: tuple[str, ...] = (",", ";", "\t", "|")
    # Se prueban en orden; cp1252 cubre los CSV exportados por Excel en Windows.
    codificaciones_csv: tuple[str, ...] = ("utf-8-sig", "cp1252")
    filas_muestra_separador: int = 200

    # Perfilado preliminar de columnas
    # Una columna de texto con hasta este número de valores distintos se
    # considera categórica; con más, texto.
    maximo_valores_categorica: int = 20
    # Un objetivo numérico con más valores distintos que este se considera continuo.
    maximo_clases_objetivo: int = 10

    # Faltantes
    porcentaje_maximo_faltantes_advertencia: float = 40.0
    # Textos que se reportan como posibles faltantes (se comparan sin espacios
    # al inicio o al final). Nunca se convierten en NaN.
    valores_centinela_faltantes: tuple[str, ...] = ("NA", "?", "-")

    # Columnas casi constantes: porcentaje del valor más frecuente
    porcentaje_casi_constante: float = 99.0

    # Relaciones entre columnas
    # Correlación de Pearson: se reporta solo si |r| supera este valor.
    umbral_correlacion_casi_perfecta: float = 0.99
    # Tolerancias para comparar valores numéricos (como en numpy.isclose):
    # absorben errores de representación de punto flotante sin aceptar
    # diferencias reales.
    tolerancia_relativa_relaciones: float = 1e-9
    tolerancia_absoluta_relaciones: float = 1e-9
    # Filas comparables mínimas (sin faltantes en las columnas implicadas).
    minimo_filas_relacion: int = 3
    # Filas usadas para descartar rápidamente relaciones de suma/resta antes
    # de verificarlas sobre todas las filas.
    filas_muestra_relaciones: int = 50

    # Variable objetivo: clase minoritaria por debajo de este porcentaje
    porcentaje_desbalance_clase: float = 20.0

    # Texto libre: deben cumplirse los tres criterios
    porcentaje_unicos_texto_libre: float = 50.0
    longitud_media_minima_texto_libre: int = 30
    promedio_minimo_palabras_texto_libre: float = 4.0

    # Ceros sospechosos: solo en variables numéricas con al menos este número
    # de valores distintos (consideradas continuas)
    minimo_valores_distintos_continua: int = 10

    # Posibles identificadores: filas mínimas para considerar el patrón
    minimo_filas_identificador: int = 5

    # Fechas escritas como texto: porcentaje mínimo de valores convertibles
    porcentaje_minimo_fechas_convertibles: float = 95.0

    # Categóricas enteras: rango de valores distintos
    minimo_valores_categorica_entera: int = 3
    maximo_valores_categorica_entera: int = 10

    # Número máximo de ejemplos incluidos en la evidencia de un hallazgo
    maximo_ejemplos_evidencia: int = 5

    # Binaria derivada de una variable numérica mediante un umbral
    # Valores distintos mínimos de la variable numérica.
    minimo_valores_distintos_umbral: int = 3
    # Observaciones mínimas de cada una de las dos clases.
    minimo_por_clase_binaria_derivada: int = 3
    # Acierto balanceado mínimo de la regla de umbral: media del porcentaje de
    # acierto de cada clase (no del total de filas, para no aceptar reglas que
    # solo aciertan la clase mayoritaria).
    porcentaje_minimo_acierto_umbral: float = 99.0

    # Posible mezcla de unidades o escalas (dos grupos de valores separados)
    minimo_observaciones_mezcla: int = 10
    # Cada grupo debe contener al menos este porcentaje de las observaciones.
    porcentaje_minimo_grupo_mezcla: float = 10.0
    # La brecha entre grupos debe ser al menos esta fracción del rango total...
    proporcion_minima_brecha_mezcla: float = 0.25
    # ...y al menos este múltiplo de la desviación estándar del grupo más disperso.
    factor_brecha_dispersion_mezcla: float = 2.0

