// Pantalla de arranque del motor y aviso si deja de responder.
import { Alert, Button, Center, Code, Group, Loader, Stack, Text, Title } from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { IconPlugConnectedX } from "@tabler/icons-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { crearCliente } from "../api/cliente";
import { ProveedorApi } from "../api/contexto";
import {
  escucharEstadoMotor,
  obtenerConexion,
  reiniciarMotor,
  type Conexion,
  type FalloMotor,
} from "../api/motor";

type Estado =
  | { tipo: "iniciando" }
  | { tipo: "fallo"; fallo: FalloMotor }
  | { tipo: "listo"; conexion: Conexion; caido: FalloMotor | null };

export function Arranque({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>({ tipo: "iniciando" });
  const consultas = useQueryClient();

  const conectar = useCallback(async (reiniciar: boolean) => {
    setEstado({ tipo: "iniciando" });
    try {
      const conexion = await (reiniciar ? reiniciarMotor() : obtenerConexion());
      setEstado({ tipo: "listo", conexion, caido: null });
      if (reiniciar) await consultas.invalidateQueries();
    } catch (fallo) {
      setEstado({ tipo: "fallo", fallo: fallo as FalloMotor });
    }
  }, [consultas]);

  useEffect(() => {
    void conectar(false);
  }, [conectar]);

  // Si el motor termina después de haber arrancado, Tauri avisa con «motor-estado».
  useEffect(() => {
    let dejar = () => {};
    let activo = true;
    void escucharEstadoMotor((nuevo) => {
      if (nuevo.estado === "fallo") {
        setEstado((e) => (e.tipo === "listo" ? { ...e, caido: nuevo } : e));
      }
    }).then((f) => (activo ? (dejar = f) : f()));
    return () => {
      activo = false;
      dejar();
    };
  }, []);

  const avisarSinRespuesta = useCallback(() => {
    setEstado((e) =>
      e.tipo === "listo" && !e.caido
        ? { ...e, caido: { mensaje: "El motor de análisis no responde.", carpeta_registros: "" } }
        : e,
    );
  }, []);

  const conexion = estado.tipo === "listo" ? estado.conexion : null;
  const valor = useMemo(
    () =>
      conexion
        ? { cliente: crearCliente({ ...conexion, alPerderConexion: avisarSinRespuesta }), avisarSinRespuesta }
        : null,
    [conexion, avisarSinRespuesta],
  );

  if (estado.tipo === "iniciando") {
    return (
      <Center h="100vh">
        <Stack align="center">
          <Loader />
          <Text>Iniciando el motor de análisis…</Text>
        </Stack>
      </Center>
    );
  }
  if (estado.tipo === "fallo") {
    return (
      <Center h="100vh" p="xl">
        <Stack maw={640}>
          <Title order={3}>No se pudo iniciar el motor de análisis</Title>
          <Alert color="red" variant="light">
            {estado.fallo.mensaje}
          </Alert>
          {estado.fallo.carpeta_registros && (
            <Text size="sm">
              Los registros están en <Code>{estado.fallo.carpeta_registros}</Code>
            </Text>
          )}
          <Group>
            <Button onClick={() => void conectar(true)}>Reintentar</Button>
          </Group>
        </Stack>
      </Center>
    );
  }
  return (
    <ProveedorApi valor={valor!}>
      {estado.caido && (
        <Alert color="orange" icon={<IconPlugConnectedX />} title="El motor de análisis dejó de responder" radius={0}>
          <Group justify="space-between">
            <Stack gap={2}>
              <Text size="sm">{estado.caido.mensaje}</Text>
              {estado.caido.carpeta_registros && (
                <Text size="sm">
                  Registros: <Code>{estado.caido.carpeta_registros}</Code>
                </Text>
              )}
            </Stack>
            <Button color="orange" onClick={() => void conectar(true)}>
              Reiniciar el motor
            </Button>
          </Group>
        </Alert>
      )}
      {children}
    </ProveedorApi>
  );
}
