// Vigilancia de los trabajos en curso: aunque el usuario cambie de pantalla, al
// terminar un trabajo se actualizan las consultas del proyecto y se avisa (dentro de
// la app siempre; con una notificación del sistema si la ventana no está en primer plano).
import { notifications } from "@mantine/notifications";
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type { Esquemas } from "../api/cliente";
import { esFinal, useTrabajo } from "../api/consultas";
import { notificarSistema } from "../api/motor";

type Trabajo = Esquemas["Trabajo"];

interface ValorVigilancia {
  vigilar: (trabajo: Pick<Trabajo, "id">) => void;
}

const Contexto = createContext<ValorVigilancia | null>(null);

const NOMBRES = { pc: "El análisis", recomendacion: "La recomendación de prueba" } as const;

export function avisoDeFin(trabajo: Trabajo): { titulo: string; mensaje: string; color: string } {
  const nombre = NOMBRES[trabajo.tipo];
  switch (trabajo.estado) {
    case "completado":
      return { titulo: `${nombre} terminó`, mensaje: trabajo.mensaje ?? "Completado.", color: "green" };
    case "cancelado":
      return { titulo: `${nombre} se canceló`, mensaje: "El avance se guardó; puede reanudarlo.", color: "gray" };
    case "interrumpido":
      return { titulo: `${nombre} se interrumpió`, mensaje: "Puede reanudarlo desde el proyecto.", color: "orange" };
    default:
      return { titulo: `${nombre} falló`, mensaje: trabajo.error ?? "Error desconocido.", color: "red" };
  }
}

function Vigilado({ id, alTerminar }: { id: string; alTerminar: (trabajo: Trabajo) => void }) {
  const { data } = useTrabajo(id);
  const avisado = useRef(false);
  useEffect(() => {
    if (data && esFinal(data.estado) && !avisado.current) {
      avisado.current = true;
      alTerminar(data);
    }
  }, [data, alTerminar]);
  return null;
}

export function VigilanteTrabajos({ children }: { children: ReactNode }) {
  const [vigilados, setVigilados] = useState<string[]>([]);
  const consultas = useQueryClient();

  const vigilar = useCallback((trabajo: Pick<Trabajo, "id">) => {
    setVigilados((actuales) => (actuales.includes(trabajo.id) ? actuales : [...actuales, trabajo.id]));
  }, []);

  const alTerminar = useCallback(
    (trabajo: Trabajo) => {
      setVigilados((actuales) => actuales.filter((id) => id !== trabajo.id));
      void consultas.invalidateQueries({ queryKey: ["proyectos"] });
      const { titulo, mensaje, color } = avisoDeFin(trabajo);
      notifications.show({ title: titulo, message: mensaje, color, autoClose: 8000 });
      void notificarSistema(titulo, mensaje);
    },
    [consultas],
  );

  const valor = useMemo(() => ({ vigilar }), [vigilar]);
  return (
    <Contexto.Provider value={valor}>
      {vigilados.map((id) => (
        <Vigilado key={id} id={id} alTerminar={alTerminar} />
      ))}
      {children}
    </Contexto.Provider>
  );
}

export function useVigilancia(): ValorVigilancia {
  const valor = useContext(Contexto);
  if (!valor) throw new Error("useVigilancia debe usarse dentro de VigilanteTrabajos");
  return valor;
}
