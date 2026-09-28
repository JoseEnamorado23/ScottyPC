import { Badge, Stepper } from "@mantine/core";
import { useNavigate } from "react-router";

import type { Esquemas } from "../api/cliente";
import { ETAPAS, estadoEtapa, type ClaveEtapa, type EstadoEtapa } from "../estado/etapas";

const COLOR: Record<EstadoEtapa, string> = { vigente: "green", desactualizada: "orange", pendiente: "gray" };
const TEXTO: Record<EstadoEtapa, string> = { vigente: "Vigente", desactualizada: "Desactualizada", pendiente: "Pendiente" };

/** Las seis etapas del análisis con su estado; las que tienen pantalla son navegables. */
export function Etapas({ proyecto, actual }: { proyecto: Esquemas["Proyecto"]; actual: ClaveEtapa }) {
  const navegar = useNavigate();
  const activa = ETAPAS.findIndex((e) => e.clave === actual);
  return (
    <Stepper
      active={activa}
      size="sm"
      allowNextStepsSelect={false}
      onStepClick={(indice) => {
        const ruta = ETAPAS[indice].ruta;
        if (ruta) navegar(`/proyectos/${proyecto.id}/${ruta}`);
      }}
    >
      {ETAPAS.map((etapa) => {
        const estado = estadoEtapa(proyecto, etapa.clave);
        return (
          <Stepper.Step
            key={etapa.clave}
            label={etapa.nombre}
            color={COLOR[estado]}
            allowStepSelect={etapa.ruta !== null && (estado !== "pendiente" || etapa.clave === "revision")}
            description={
              <Badge size="xs" variant="light" color={COLOR[estado]}>
                {TEXTO[estado]}
              </Badge>
            }
          />
        );
      })}
    </Stepper>
  );
}
