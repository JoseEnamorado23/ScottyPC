// Borradores por proyecto de las etapas de análisis: la prueba y el max_k elegidos en la
// recomendación y la configuración de PC que se está editando. Viven en memoria para no
// perderse al cambiar de pantalla; se guardan en el servidor con PUT configuracion-pc.
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import type { Esquemas } from "../api/cliente";

export type Prueba = Esquemas["ConfiguracionPC"]["prueba"];

export interface EleccionPrueba {
  prueba: Prueba;
  max_k: number | null;
}

interface BorradorAnalisis {
  eleccion?: EleccionPrueba;
  configuracion?: Esquemas["ConfiguracionPC"];
}

type Actualizar = (proyecto: string, cambiar: (anterior: BorradorAnalisis) => BorradorAnalisis) => void;

interface ValorContexto {
  borradores: Record<string, BorradorAnalisis>;
  actualizar: Actualizar;
}

const Contexto = createContext<ValorContexto | null>(null);

export function ProveedorBorradoresAnalisis({ children }: { children: ReactNode }) {
  const [borradores, setBorradores] = useState<Record<string, BorradorAnalisis>>({});
  const actualizar = useCallback<Actualizar>((proyecto, cambiar) => {
    setBorradores((todos) => ({ ...todos, [proyecto]: cambiar(todos[proyecto] ?? {}) }));
  }, []);
  const valor = useMemo(() => ({ borradores, actualizar }), [borradores, actualizar]);
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useBorradorAnalisis(proyecto: string) {
  const contexto = useContext(Contexto);
  if (!contexto) throw new Error("useBorradorAnalisis debe usarse dentro de ProveedorBorradoresAnalisis");
  const { borradores, actualizar } = contexto;
  const borrador = borradores[proyecto];

  // Funciones estables (no dependen del borrador): se pueden usar en efectos sin bucles.
  const elegirPrueba = useCallback(
    (eleccion: EleccionPrueba) =>
      actualizar(proyecto, (b) => ({
        ...b,
        eleccion,
        // La elección se aplica también a la configuración que se esté editando.
        configuracion: b.configuracion ? { ...b.configuracion, ...eleccion } : undefined,
      })),
    [actualizar, proyecto],
  );
  const editarConfiguracion = useCallback(
    (configuracion: Esquemas["ConfiguracionPC"] | undefined) => actualizar(proyecto, (b) => ({ ...b, configuracion })),
    [actualizar, proyecto],
  );

  return { eleccion: borrador?.eleccion, configuracion: borrador?.configuracion, elegirPrueba, editarConfiguracion };
}
