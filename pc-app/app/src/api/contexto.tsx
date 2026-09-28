import { createContext, useContext, type ReactNode } from "react";

import type { Cliente } from "./cliente";

export interface ValorApi {
  cliente: Cliente;
  /** Muestra el aviso de que el motor no responde, con la opción de reiniciarlo. */
  avisarSinRespuesta: () => void;
}

const ContextoApi = createContext<ValorApi | null>(null);

export function ProveedorApi({ valor, children }: { valor: ValorApi; children: ReactNode }) {
  return <ContextoApi.Provider value={valor}>{children}</ContextoApi.Provider>;
}

export function useApi(): ValorApi {
  const valor = useContext(ContextoApi);
  if (!valor) throw new Error("useApi debe usarse dentro de ProveedorApi");
  return valor;
}
