import { Badge, Center, Loader, NavLink, ScrollArea, Stack, Text } from "@mantine/core";
import {
  IconChartBar,
  IconChecklist,
  IconHierarchy,
  IconRoute,
  IconScale,
  IconSettings,
  IconThumbUp,
  IconWand,
} from "@tabler/icons-react";
import { matchPath, useLocation, useNavigate } from "react-router";

import { useProyecto } from "../api/consultas";
import { ETAPAS, estadoEtapa, etapaDisponible, type ClaveEtapa } from "../estado/etapas";

const ICONOS: Record<ClaveEtapa, any> = {
  revision: IconChecklist,
  decisiones: IconScale,
  preparacion: IconWand,
  recomendacion: IconThumbUp,
  configuracion_pc: IconSettings,
  analisis: IconChartBar,
  modelo_causal: IconHierarchy,
  prescripcion: IconRoute,
};

const COLOR: Record<string, string> = {
  vigente: "green",
  desactualizada: "orange",
  pendiente: "gray",
};
const TEXTO: Record<string, string> = {
  vigente: "Vigente",
  desactualizada: "Desactualizada",
  pendiente: "Pendiente",
};

export function NavegacionLateral() {
  const { pathname } = useLocation();
  const navegar = useNavigate();
  const match = matchPath("/proyectos/:id/*", pathname);
  const id = match?.params.id;

  const proyectoQuery = useProyecto(id ?? "");

  if (!id) return null;

  if (proyectoQuery.isPending) return (
    <Center p="md">
      <Loader size="sm" />
    </Center>
  );
  if (proyectoQuery.error || !proyectoQuery.data) return null;

  const proyecto = proyectoQuery.data;
  const currentEtapa = ETAPAS.find((e) => pathname.includes(e.ruta));

  return (
    <ScrollArea style={{ flex: 1 }}>
      <Stack gap="xs" p="md">
        <Text fw={600} size="lg" mb="xl" truncate="end" title={proyecto.nombre}>
          {proyecto.nombre}
        </Text>
        
        {ETAPAS.map((etapa) => {
          const Icono = ICONOS[etapa.clave];
          const estado = estadoEtapa(proyecto, etapa.clave);
          const disponible = etapaDisponible(proyecto, etapa.clave);
          const active = currentEtapa?.clave === etapa.clave;

          return (
            <NavLink
              key={etapa.clave}
              active={active}
              label={etapa.nombre}
              leftSection={<Icono size={20} stroke={1.5} />}
              rightSection={
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    backgroundColor: `var(--mantine-color-${COLOR[estado]}-filled, ${COLOR[estado]})`,
                  }}
                  title={TEXTO[estado]}
                />
              }
              disabled={!disponible}
              onClick={() => {
                if (disponible) navegar(`/proyectos/${id}/${etapa.ruta}`);
              }}
              style={{ borderRadius: 8 }}
            />
          );
        })}
      </Stack>
    </ScrollArea>
  );
}
