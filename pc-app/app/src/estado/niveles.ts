// Estado del editor de niveles de PC. Solo manipula la estructura (qué ficha está en
// qué nivel, nombres y orden); qué configuraciones son válidas lo decide el núcleo
// (POST .../configuracion-pc/validar). Por construcción cada variable queda siempre en
// exactamente un nivel: mover una ficha la quita de su nivel anterior y eliminar un
// nivel pasa sus fichas a un nivel vecino.

export interface Nivel {
  /** Identificador estable (para arrastrar y soltar), independiente de la posición. */
  id: string;
  nombre: string;
  variables: string[];
}

export interface EstadoNiveles {
  niveles: Nivel[];
  siguienteId: number;
}

export type AccionNiveles =
  | { tipo: "mover"; variable: string; nivel: string; indice?: number }
  | { tipo: "agregar"; posicion?: number }
  | { tipo: "eliminar"; nivel: string }
  | { tipo: "renombrar"; nivel: string; nombre: string }
  | { tipo: "reordenar"; desde: number; hasta: number }
  | { tipo: "restablecer"; niveles: string[][]; nombres?: string[] | null };

export const nombrePorDefecto = (posicion: number) => `Nivel ${posicion + 1}`;
const ES_POR_DEFECTO = /^Nivel \d+$/;

/** Los nombres por defecto («Nivel N») siguen la posición; los elegidos por el usuario se conservan. */
function renumerar(niveles: Nivel[]): Nivel[] {
  return niveles.map((n, i) => (ES_POR_DEFECTO.test(n.nombre) ? { ...n, nombre: nombrePorDefecto(i) } : n));
}

export function crearEstado(niveles: string[][], nombres?: string[] | null): EstadoNiveles {
  const usarNombres = nombres && nombres.length === niveles.length;
  return {
    niveles: niveles.map((variables, i) => ({
      id: `n${i}`,
      nombre: usarNombres ? nombres[i] : nombrePorDefecto(i),
      variables: [...variables],
    })),
    siguienteId: niveles.length,
  };
}

/** Niveles y nombres tal como los espera ConfiguracionPC (sin nombres si todos son los de por defecto). */
export function aConfiguracion(estado: EstadoNiveles): { niveles: string[][]; nombres_niveles: string[] | null } {
  const nombres = estado.niveles.map((n) => n.nombre);
  return {
    niveles: estado.niveles.map((n) => [...n.variables]),
    nombres_niveles: nombres.every((nombre, i) => nombre === nombrePorDefecto(i)) ? null : nombres,
  };
}

export function nivelDe(estado: EstadoNiveles, variable: string): Nivel | undefined {
  return estado.niveles.find((n) => n.variables.includes(variable));
}

export function reducirNiveles(estado: EstadoNiveles, accion: AccionNiveles): EstadoNiveles {
  switch (accion.tipo) {
    case "mover": {
      const destino = estado.niveles.find((n) => n.id === accion.nivel);
      const origen = nivelDe(estado, accion.variable);
      if (!destino || !origen) return estado;
      const sinFicha = estado.niveles.map((n) =>
        n.id === origen.id ? { ...n, variables: n.variables.filter((v) => v !== accion.variable) } : n,
      );
      return {
        ...estado,
        niveles: sinFicha.map((n) => {
          if (n.id !== destino.id) return n;
          const variables = [...n.variables];
          const indice = Math.min(Math.max(accion.indice ?? variables.length, 0), variables.length);
          variables.splice(indice, 0, accion.variable);
          return { ...n, variables };
        }),
      };
    }
    case "agregar": {
      const posicion = Math.min(Math.max(accion.posicion ?? estado.niveles.length, 0), estado.niveles.length);
      const nuevo: Nivel = { id: `n${estado.siguienteId}`, nombre: nombrePorDefecto(posicion), variables: [] };
      const niveles = [...estado.niveles];
      niveles.splice(posicion, 0, nuevo);
      return { niveles: renumerar(niveles), siguienteId: estado.siguienteId + 1 };
    }
    case "eliminar": {
      const indice = estado.niveles.findIndex((n) => n.id === accion.nivel);
      if (indice < 0 || estado.niveles.length === 1) return estado;
      const eliminado = estado.niveles[indice];
      // Las fichas pasan al nivel anterior (o al siguiente si era el primero).
      const receptor = estado.niveles[indice === 0 ? 1 : indice - 1];
      return {
        ...estado,
        niveles: renumerar(
          estado.niveles
            .filter((n) => n.id !== eliminado.id)
            .map((n) => (n.id === receptor.id ? { ...n, variables: [...n.variables, ...eliminado.variables] } : n)),
        ),
      };
    }
    case "renombrar":
      return {
        ...estado,
        niveles: estado.niveles.map((n) => (n.id === accion.nivel ? { ...n, nombre: accion.nombre } : n)),
      };
    case "reordenar": {
      const { desde, hasta } = accion;
      if (desde === hasta || desde < 0 || hasta < 0 || desde >= estado.niveles.length || hasta >= estado.niveles.length) {
        return estado;
      }
      const niveles = [...estado.niveles];
      const [movido] = niveles.splice(desde, 1);
      niveles.splice(hasta, 0, movido);
      return { ...estado, niveles: renumerar(niveles) };
    }
    case "restablecer":
      return crearEstado(accion.niveles, accion.nombres);
  }
}
