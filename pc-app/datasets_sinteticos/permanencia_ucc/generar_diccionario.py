"""Paso 6: escribe salidas/diccionario_portal.json (textos en español sencillo para estudiantes).

Uso: python generar_diccionario.py
Comprueba que cubre exactamente las columnas del generador y que `como_mejorar` existe solo en las
variables modificables.
"""
from __future__ import annotations

import json
import sys

import generador as g

OBJETIVO = {
    "variable": "permanece",
    "pregunta": "¿Seguirás estudiando el próximo semestre?",
    "texto": "seguir estudiando el próximo semestre",
    "explicacion": ("Es la probabilidad de que sigas matriculado(a) en la universidad el próximo semestre. "
                    "Es una estimación basada en la experiencia de estudiantes con una situación parecida a la tuya, "
                    "no una promesa ni una decisión sobre ti."),
    "valores": {"0": "No continúa el próximo semestre", "1": "Continúa el próximo semestre"},
}

V = {
    "estrato": {
        "etiqueta": "Estrato socioeconómico",
        "descripcion": "Estrato de la vivienda donde vives, según tu factura de servicios públicos.",
        "unidad": "nivel de 1 a 6", "valores": "1 (más bajo) a 6 (más alto)",
    },
    "genero": {
        "etiqueta": "Género",
        "descripcion": "Género con el que te identificas en el registro de la universidad.",
        "unidad": "categoría", "valores": {"0": "Hombre", "1": "Mujer"},
    },
    "edad_ingreso": {
        "etiqueta": "Edad al ingresar",
        "descripcion": "Los años que tenías cuando empezaste la carrera.",
        "unidad": "años", "valores": "entre 16 y 30",
    },
    "primera_generacion": {
        "etiqueta": "Primera persona de la familia en la universidad",
        "descripcion": "Si eres la primera persona de tu familia (padres o madres) que llega a la educación superior.",
        "unidad": "sí / no",
        "valores": {"0": "No, alguien de mi familia ya fue a la universidad", "1": "Sí, soy la primera persona"},
    },
    "vive_con_familia": {
        "etiqueta": "Vives con tu familia",
        "descripcion": "Si vives en la misma casa que tu familia.",
        "unidad": "sí / no", "valores": {"0": "No", "1": "Sí"},
    },
    "puntaje_saber11": {
        "etiqueta": "Puntaje en las pruebas Saber 11",
        "descripcion": "El puntaje global que sacaste en el examen de Estado al terminar el colegio.",
        "unidad": "puntos", "valores": "entre 0 y 500",
    },
    "horas_trabajo_semana": {
        "etiqueta": "Horas de trabajo a la semana",
        "descripcion": "Las horas que trabajas en una semana normal, además de estudiar. Cero significa que no trabajas.",
        "unidad": "horas por semana", "valores": "entre 0 y 48",
        "como_mejorar": ("Si trabajas muchas horas, reducirlas, aunque sea un poco, deja más tiempo para estudiar y asistir a clase. "
                         "Si no puedes dejar de trabajar, busca horarios que no choquen con tus clases o pregunta en Bienestar "
                         "por monitorías y apoyos económicos para trabajar menos."),
    },
    "asistencia_pct": {
        "etiqueta": "Asistencia a clase",
        "descripcion": "De cada 100 clases, a cuántas asististe en el semestre.",
        "unidad": "porcentaje (%)", "valores": "entre 30 y 100",
        "como_mejorar": ("Ir a clase con regularidad es una de las cosas que más ayuda. Marca en tu calendario las clases del semestre, "
                         "evita faltar por días seguidos y, si tienes que faltar, avisa al docente y pide lo que viste."),
    },
    "horas_estudio_semana": {
        "etiqueta": "Horas de estudio fuera de clase",
        "descripcion": "Las horas que dedicas por tu cuenta a estudiar, hacer tareas o preparar exámenes en una semana normal.",
        "unidad": "horas por semana", "valores": "entre 0 y 30, de media en media hora",
        "como_mejorar": ("Reserva bloques fijos de estudio en tu semana, por ejemplo una hora después de cada clase difícil. "
                         "Estudiar poco a poco rinde más que hacerlo todo la noche anterior, y las primeras horas extra son las que más se notan."),
    },
    "tutorias_asistidas": {
        "etiqueta": "Tutorías a las que asististe",
        "descripcion": "Cuántas tutorías académicas (clases de apoyo con un docente o monitor) tomaste en el semestre.",
        "unidad": "tutorías", "valores": "números enteros, de 0 a 8",
        "como_mejorar": ("Apúntate a las tutorías de las materias que más te cuestan y pregunta sin pena. "
                         "No hace falta ir a todas: unas pocas, bien aprovechadas, ayudan."),
    },
    "creditos_matriculados": {
        "etiqueta": "Créditos matriculados",
        "descripcion": "La carga académica del semestre: la suma de los créditos de las materias que inscribiste.",
        "unidad": "créditos", "valores": "números enteros, de 8 a 22",
        "como_mejorar": ("Una carga muy alta te quita tiempo para estudiar cada materia, y una muy baja alarga la carrera. "
                         "Entre 14 y 16 créditos suele ser manejable; si tienes más y además trabajas, "
                         "habla con tu coordinación académica antes de inscribir las materias."),
    },
    "apoyo_bienestar": {
        "etiqueta": "Apoyo de Bienestar Universitario",
        "descripcion": "Si recibes acompañamiento de Bienestar: orientación psicológica, apoyo académico o actividades de acompañamiento.",
        "unidad": "sí / no", "valores": {"0": "No lo recibo", "1": "Sí lo recibo"},
        "como_mejorar": ("Acércate a Bienestar Universitario y pregunta qué acompañamiento hay para ti. "
                         "Pedir ayuda a tiempo funciona mejor que esperar a que el problema crezca."),
    },
    "apoyo_financiero": {
        "etiqueta": "Apoyo financiero",
        "descripcion": "Si tienes beca, crédito condonable, subsidio o descuento que te ayuda a pagar la matrícula o el sostenimiento.",
        "unidad": "sí / no", "valores": {"0": "No lo tengo", "1": "Sí lo tengo"},
        "como_mejorar": ("Pregunta en la oficina de financiación o de becas por las convocatorias abiertas, "
                         "los requisitos y los plazos. Revisa cada semestre, porque se abren nuevas opciones."),
    },
    "promedio_semestre": {
        "etiqueta": "Promedio del semestre",
        "descripcion": "Tu nota promedio de las materias del semestre, en la escala colombiana.",
        "unidad": "nota de 0 a 5", "valores": "entre 0,0 y 5,0",
    },
    "materias_reprobadas": {
        "etiqueta": "Materias reprobadas",
        "descripcion": "Cuántas materias perdiste en el semestre.",
        "unidad": "materias", "valores": "números enteros, de 0 a 6",
    },
    "permanece": {
        "etiqueta": "Continúa el próximo semestre",
        "descripcion": "Si volviste a matricularte al semestre siguiente. Es lo que queremos entender y apoyar.",
        "unidad": "sí / no", "valores": {"0": "No continúa", "1": "Continúa"},
    },
}


def construir() -> dict:
    faltan = set(g.COLUMNAS) - set(V)
    sobran = set(V) - set(g.COLUMNAS)
    if faltan or sobran:
        raise SystemExit(f"Diccionario desalineado: faltan {sorted(faltan)}, sobran {sorted(sobran)}")
    con_mejora = {k for k, v in V.items() if "como_mejorar" in v}
    if con_mejora != set(g.MODIFICABLES):
        raise SystemExit(f"como_mejorar debe estar solo en las modificables: {sorted(con_mejora ^ set(g.MODIFICABLES))}")
    return {
        "descripcion": ("Diccionario en español sencillo para estudiantes. Cada variable tiene etiqueta, descripcion, unidad "
                        "y valores; las que el estudiante puede cambiar tienen además `como_mejorar`. "
                        "Los datos son sintéticos (no son estudiantes reales)."),
        "objetivo": OBJETIVO,
        "variables": {c: {"etiqueta": V[c]["etiqueta"], "modificable": c in g.MODIFICABLES,
                          **{k: x for k, x in V[c].items() if k != "etiqueta"}} for c in g.COLUMNAS},
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    d = construir()
    ruta = g.SALIDAS / "diccionario_portal.json"
    ruta.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Escrito {ruta} — {len(d['variables'])} variables, "
          f"{sum(v['modificable'] for v in d['variables'].values())} modificables")


if __name__ == "__main__":
    main()
