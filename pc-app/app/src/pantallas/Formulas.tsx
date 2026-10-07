import { Stack, Tabs, Text, Title } from "@mantine/core";
import { useParams, useSearchParams } from "react-router";

import { AnalisisPc } from "../componentes/formulas/AnalisisPc";
import { ModeloCausal } from "../componentes/formulas/ModeloCausal";
import { Prescripcion } from "../componentes/formulas/Prescripcion";
import { SeleccionPrueba } from "../componentes/formulas/SeleccionPrueba";

/** Etapas con explorador, en el orden del flujo. Para agregar otra: su componente y una entrada aquí. */
const SECCIONES = [
  { clave: "seleccion-prueba", nombre: "Selección de prueba", descripcion: "Cómo se elige la prueba de independencia para PC" },
  { clave: "analisis-pc", nombre: "Análisis de PC", descripcion: "Cómo las corridas de bootstrap forman el grafo y la caracterización" },
  { clave: "modelo-causal", nombre: "Modelo causal", descripcion: "Qué variables entran, cómo se elige cada mecanismo y qué calcula" },
  { clave: "prescripcion", nombre: "Prescripción", descripcion: "Cómo se calibra μ y qué función se minimiza en cada caso" },
] as const;

export function Formulas() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const actual = SECCIONES.find((s) => s.clave === params.get("etapa")) ?? SECCIONES[0];

  return (
    <Stack gap="md">
      <div>
        <Title order={3}>Explorador de fórmulas</Title>
        <Text c="dimmed" size="sm">{actual.descripcion}</Text>
      </div>
      <Tabs value={actual.clave} onChange={(v) => v && setParams({ etapa: v }, { replace: true })} keepMounted={false}>
        <Tabs.List>
          {SECCIONES.map((s) => <Tabs.Tab key={s.clave} value={s.clave}>{s.nombre}</Tabs.Tab>)}
        </Tabs.List>
        <Tabs.Panel value="seleccion-prueba" pt="md"><SeleccionPrueba id={id} /></Tabs.Panel>
        <Tabs.Panel value="analisis-pc" pt="md"><AnalisisPc id={id} /></Tabs.Panel>
        <Tabs.Panel value="modelo-causal" pt="md"><ModeloCausal id={id} /></Tabs.Panel>
        <Tabs.Panel value="prescripcion" pt="md"><Prescripcion id={id} /></Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
