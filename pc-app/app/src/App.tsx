import { AppShell, Group, Title, UnstyledButton } from "@mantine/core";
import { Navigate, Route, Routes, useNavigate } from "react-router";

import { PantallaDecisiones } from "./pantallas/Decisiones";
import { DatosProyecto } from "./pantallas/DatosProyecto";
import { Inicio } from "./pantallas/Inicio";
import { NuevoProyecto } from "./pantallas/NuevoProyecto";
import { Revision } from "./pantallas/Revision";

export function Rutas() {
  return (
    <Routes>
      <Route path="/" element={<Inicio />} />
      <Route path="/nuevo" element={<NuevoProyecto />} />
      <Route path="/proyectos/:id/datos" element={<DatosProyecto />} />
      <Route path="/proyectos/:id/revision" element={<Revision />} />
      <Route path="/proyectos/:id/decisiones" element={<PantallaDecisiones />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  const navegar = useNavigate();
  return (
    <AppShell header={{ height: 52 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md">
          <UnstyledButton onClick={() => navegar("/")}>
            <Title order={4}>pc-app</Title>
          </UnstyledButton>
        </Group>
      </AppShell.Header>
      <AppShell.Main>
        <Rutas />
      </AppShell.Main>
    </AppShell>
  );
}
