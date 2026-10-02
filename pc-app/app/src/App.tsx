import { AppShell, Group, Title, UnstyledButton, ActionIcon, useMantineColorScheme, useComputedColorScheme } from "@mantine/core";
import { IconDog, IconMoon, IconSun } from "@tabler/icons-react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router";

import { Analisis } from "./pantallas/Analisis";
import { PantallaConfiguracionPc } from "./pantallas/ConfiguracionPc";
import { PantallaDecisiones } from "./pantallas/Decisiones";
import { DatosProyecto } from "./pantallas/DatosProyecto";
import { Inicio } from "./pantallas/Inicio";
import { NuevoProyecto } from "./pantallas/NuevoProyecto";
import { Preparacion } from "./pantallas/Preparacion";
import { Recomendacion } from "./pantallas/Recomendacion";
import { Resultados } from "./pantallas/Resultados";
import { ModeloCausal } from "./pantallas/ModeloCausal";
import { Prescripcion } from "./pantallas/Prescripcion";
import { Revision } from "./pantallas/Revision";
import { NavegacionLateral } from "./componentes/NavegacionLateral";

export function Rutas() {
  return (
    <Routes>
      <Route path="/" element={<Inicio />} />
      <Route path="/nuevo" element={<NuevoProyecto />} />
      <Route path="/proyectos/:id/datos" element={<DatosProyecto />} />
      <Route path="/proyectos/:id/revision" element={<Revision />} />
      <Route path="/proyectos/:id/decisiones" element={<PantallaDecisiones />} />
      <Route path="/proyectos/:id/preparacion" element={<Preparacion />} />
      <Route path="/proyectos/:id/recomendacion" element={<Recomendacion />} />
      <Route path="/proyectos/:id/configuracion" element={<PantallaConfiguracionPc />} />
      <Route path="/proyectos/:id/analisis" element={<Analisis />} />
      <Route path="/proyectos/:id/resultados" element={<Resultados />} />
      <Route path="/proyectos/:id/modelo-causal" element={<ModeloCausal />} />
      <Route path="/proyectos/:id/prescripcion" element={<Prescripcion />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  const navegar = useNavigate();
  const location = useLocation();
  const isProjectRoute = location.pathname.startsWith('/proyectos/');
  
  const { setColorScheme } = useMantineColorScheme();
  const computedColorScheme = useComputedColorScheme("light", { getInitialValueInEffect: true });

  const toggleColorScheme = () => {
    setColorScheme(computedColorScheme === "light" ? "dark" : "light");
  };

  return (
    <AppShell 
      header={{ height: 52 }} 
      navbar={{ width: 280, breakpoint: 'sm', collapsed: { mobile: !isProjectRoute, desktop: !isProjectRoute } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <UnstyledButton onClick={() => navegar("/")}>
            <Group gap="sm">
              <IconDog color={computedColorScheme === "dark" ? "white" : "black"} fill={computedColorScheme === "dark" ? "white" : "black"} size={24} />
              <Title order={4}>scottyPC</Title>
            </Group>
          </UnstyledButton>
          
          <ActionIcon
            onClick={toggleColorScheme}
            variant="default"
            size="lg"
            radius="xl"
            aria-label="Alternar tema"
          >
            {computedColorScheme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
          </ActionIcon>
        </Group>
      </AppShell.Header>
      
      <AppShell.Navbar>
        <NavegacionLateral />
      </AppShell.Navbar>

      <AppShell.Main>
        <Rutas />
      </AppShell.Main>
    </AppShell>
  );
}
