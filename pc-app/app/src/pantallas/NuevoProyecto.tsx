import { Button, Stack, Text, TextInput, Title } from "@mantine/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { IconFileSpreadsheet } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { datos } from "../api/cliente";
import { claves } from "../api/consultas";
import { useApi } from "../api/contexto";
import { elegirArchivo } from "../api/motor";
import { MensajeError } from "../componentes/MensajeError";

export function NuevoProyecto() {
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const navegar = useNavigate();
  const [nombre, setNombre] = useState("");

  const crear = useMutation({
    mutationFn: async () => {
      const ruta = await elegirArchivo();
      if (!ruta) return null;
      return datos(cliente.POST("/proyectos", { body: { ruta_archivo: ruta, nombre: nombre.trim() || null } }));
    },
    onSuccess: async (proyecto) => {
      if (!proyecto) return;
      await consultas.invalidateQueries({ queryKey: claves.proyectos });
      navegar(`/proyectos/${proyecto.id}/datos`);
    },
  });

  return (
    <Stack maw={560}>
      <Title order={2}>Nuevo proyecto</Title>
      <Text size="sm" c="dimmed">
        Elija un archivo CSV o Excel. La aplicación trabaja sobre una copia: su archivo original no se modifica.
      </Text>
      <TextInput
        label="Nombre del proyecto (opcional)"
        description="Si lo deja vacío se usa el nombre del archivo."
        value={nombre}
        onChange={(e) => setNombre(e.currentTarget.value)}
      />
      <Button leftSection={<IconFileSpreadsheet size={16} />} loading={crear.isPending} onClick={() => crear.mutate()}>
        Elegir archivo…
      </Button>
      <MensajeError error={crear.error} titulo="No se pudo crear el proyecto" />
    </Stack>
  );
}
