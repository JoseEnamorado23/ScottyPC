// Resultados: grafo interactivo, ajuste del umbral y de las orientaciones sin volver a
// ejecutar PC (vista previa calculada por el núcleo), versiones, pestañas y exportación.
import {
  Accordion, ActionIcon, Alert, Badge, Button, Center, Grid, Group, Loader, Modal, Stack, Switch, Tabs, Text, Title, Tooltip,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useQueryClient } from "@tanstack/react-query";
import { notifications } from "@mantine/notifications";
import { IconDownload, IconFileExport, IconFocus2, IconZoomIn, IconZoomOut } from "@tabler/icons-react";
import { useRef, useState } from "react";
import { useParams } from "react-router";

import { ErrorApi } from "../api/cliente";
import { claves, useProcedencia, useProyecto, useResultado, useVersiones, useVistaPrevia } from "../api/consultas";
import { elegirCarpeta, guardarImagen } from "../api/motor";
import { useAccionesResultado } from "../api/resultados";

import { MensajeError } from "../componentes/MensajeError";
import { DialogoOrientacion, erroresDeOrientacion, type ErroresOrientacion } from "../componentes/resultados/DialogoOrientacion";
import { GrafoCausal, type ControlGrafo } from "../componentes/resultados/GrafoCausal";
import {
  HistorialVersiones, LeyendaGrafo, ListaAvisos, PanelAjuste, PanelVariable, ResumenConfiguracion,
} from "../componentes/resultados/Paneles";
import { TablaAristas, TablaCaracterizacion } from "../componentes/resultados/Tablas";
import {
  aSolicitud, ajusteDe, conOrientacion, conUmbral, mismoAjuste, orientacionDe, sinOrientacion, type Ajuste, type Orientacion,
} from "../estado/ajustes";
import type { Arista } from "../estado/grafo";

/** Retardo de la vista previa mientras se mueve el deslizante. */
export const RETARDO_VISTA_PREVIA_MS = 300;

export function Resultados() {
  const { id = "" } = useParams();
  // Una instancia por proyecto: el grafo, el borrador y la selección no pasan de un proyecto a otro.
  return <PantallaResultados key={id} id={id} />;
}

function PantallaResultados({ id }: { id: string }) {
  const proyecto = useProyecto(id);
  const versiones = useVersiones(id);
  const version = versiones.data?.version_actual ?? null;
  const resultado = useResultado(id, version, !!versiones.data);
  const acciones = useAccionesResultado(id);
  const consultas = useQueryClient();

  // Borrador del ajuste: null = sin cambios respecto a la versión vista.
  const [borrador, setBorrador] = useState<Ajuste | null>(null);
  const base = resultado.data ? ajusteDe(resultado.data.agregacion) : null;
  const ajuste = borrador ?? base;
  const sinGuardar = borrador !== null && base !== null && !mismoAjuste(borrador, base);
  const [diferido] = useDebouncedValue(sinGuardar ? borrador : null, RETARDO_VISTA_PREVIA_MS);
  const vistaPrevia = useVistaPrevia(id, sinGuardar && diferido ? aSolicitud(diferido) : null);
  const mostrado = sinGuardar ? (vistaPrevia.data ?? resultado.data) : resultado.data;
  const calculando = sinGuardar && (vistaPrevia.isFetching || diferido !== borrador);

  const [pestana, setPestana] = useState<string | null>("grafo");
  const [soloRelacionadas, setSoloRelacionadas] = useState(false);
  const [seleccionado, setSeleccionado] = useState<string | null>(null);
  const [aristaElegida, setAristaElegida] = useState<Arista | null>(null);
  const [versionPendiente, setVersionPendiente] = useState<number | null>(null);
  const control = useRef<ControlGrafo>(null);

  if (proyecto.isPending || versiones.isPending || (!!versiones.data && resultado.isPending && !resultado.data)) {
    return <Center><Loader /></Center>;
  }
  const error = proyecto.error ?? versiones.error ?? resultado.error;
  if (error) return <MensajeError error={error} />;
  if (!proyecto.data || !versiones.data || !mostrado || !ajuste || version === null) {
    return <Alert color="orange">No hay un análisis vigente: ejecute el análisis para ver los resultados.</Alert>;
  }

  const umbralOriginal = versiones.data.umbral_original;
  const verVersion = (numero: number) => {
    setBorrador(null);
    setVersionPendiente(null);
    acciones.cambiarVersion.mutate(numero);
  };

  const elegirArista = (arista: Arista) => {
    if (arista.tipo !== "dirigida") setAristaElegida(arista);
  };

  const aplicarOrientacion = async (orientacion: Orientacion): Promise<ErroresOrientacion | null> => {
    const propuesta = conOrientacion(ajuste, orientacion);
    try {
      await acciones.previsualizar(propuesta);
      setBorrador(propuesta);
      return null;
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 422) {
        return erroresDeOrientacion(e.porCampo, propuesta.orientaciones.length - 1);
      }
      return { general: e instanceof Error ? e.message : String(e) };
    }
  };

  const guardar = () =>
    acciones.guardarVersion.mutate(
      { ajuste, base: version },
      {
        onSuccess: (nuevas) => {
          // La vista previa ya es el contenido de la versión nueva: se muestra sin esperar.
          if (vistaPrevia.data) {
            consultas.setQueryData(claves.resultado(id, nuevas.version_actual), { ...vistaPrevia.data, version: nuevas.version_actual });
          }
          setBorrador(null);
          notifications.show({ color: "green", message: `Versión ${nuevas.version_actual} guardada.` });
        },
      },
    );

  const exportar = async () => {
    const carpeta = await elegirCarpeta();
    if (!carpeta) return;
    acciones.exportar.mutate(
      { carpeta, version },
      {
        onSuccess: (r) =>
          notifications.show({
            color: "green",
            title: `Versión ${r.version} exportada`,
            message: `${r.archivos.length} archivos (con informe.html) en ${r.carpeta}`,
            autoClose: 10000,
          }),
      },
    );
  };

  const guardarPng = async () => {
    const imagen = control.current?.png();
    if (!imagen) return;
    try {
      const ruta = await guardarImagen(imagen, `${proyecto.data.nombre}_grafo_v${version}${sinGuardar ? "_vista_previa" : ""}.png`);
      if (ruta) notifications.show({ color: "green", message: `Imagen guardada en ${ruta}` });
    } catch (e) {
      notifications.show({ color: "red", title: "No se pudo guardar la imagen", message: String(e) });
    }
  };

  return (
    <Stack>

      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={2}>Resultados</Title>
          <Text size="sm" c="dimmed">
            Objetivo: {mostrado.caracterizacion.objetivo} · {mostrado.corridas.validas} corridas válidas de {mostrado.corridas.totales}
          </Text>
        </div>
        <Tooltip label={sinGuardar ? `Exporta la versión ${version} guardada; los cambios sin guardar no se incluyen.` : `Exporta la versión ${version} con su informe HTML.`}>
          <Button leftSection={<IconFileExport size={18} />} onClick={exportar} loading={acciones.exportar.isPending}>
            Exportar
          </Button>
        </Tooltip>
      </Group>
      <MensajeError error={acciones.exportar.error} titulo="No se pudo exportar" />

      <Accordion variant="contained" defaultValue={null}>
        <Accordion.Item value="versiones">
          <Accordion.Control>
            <Group gap="xs">
              <Text fw={600}>Historial de versiones</Text>
              <Text size="sm" c="dimmed">
                ({versiones.data.versiones.length}) · viendo la versión {version}
              </Text>
              <EtiquetaVersion etiqueta={versiones.data.versiones.find((v) => v.version === version)?.etiqueta ?? ""} />
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <HistorialVersiones
              versiones={versiones.data.versiones}
              vista={version}
              cambiando={acciones.cambiarVersion.isPending}
              alVer={(numero) => (sinGuardar ? setVersionPendiente(numero) : verVersion(numero))}
            />
            <MensajeError error={acciones.cambiarVersion.error} titulo="No se pudo cambiar de versión" />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      <PanelAjuste
        ajuste={ajuste}
        umbralOriginal={umbralOriginal}
        sinGuardar={sinGuardar}
        calculando={calculando}
        guardando={acciones.guardarVersion.isPending}
        alCambiarUmbral={(umbral) => setBorrador(conUmbral(ajuste, umbral))}
        alQuitarOrientacion={(a, b) => setBorrador(sinOrientacion(ajuste, a, b))}
        alGuardar={guardar}
        alDescartar={() => setBorrador(null)}
      />
      <MensajeError error={acciones.guardarVersion.error} titulo="No se pudo guardar la versión" />
      <MensajeError error={sinGuardar ? vistaPrevia.error : null} titulo="No se pudo calcular la vista previa" />

      <Tabs value={pestana} onChange={setPestana} keepMounted>
        <Tabs.List>
          <Tabs.Tab value="grafo">Grafo</Tabs.Tab>
          <Tabs.Tab value="caracterizacion">Caracterización</Tabs.Tab>
          <Tabs.Tab value="aristas">Aristas ({mostrado.aristas.length})</Tabs.Tab>
          <Tabs.Tab
            value="advertencias"
            rightSection={mostrado.avisos.length > 0 && <Badge size="sm" color="orange" circle>{mostrado.avisos.length}</Badge>}
          >
            Advertencias
          </Tabs.Tab>
          <Tabs.Tab value="configuracion">Configuración</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="grafo" pt="md">
          <Stack gap="sm">
            <Group justify="space-between">
              <Group gap="xs">
                <Text fw={600}>{sinGuardar ? "Vista previa sin guardar" : `Versión ${version}`}</Text>
                <EtiquetaVersion etiqueta={mostrado.etiqueta} />
                {calculando && <Loader size="xs" aria-label="Calculando la vista previa" />}
              </Group>
              <Group gap="xs">
                <Switch
                  label="Mostrar solo lo relacionado con el objetivo"
                  checked={soloRelacionadas}
                  onChange={(e) => setSoloRelacionadas(e.currentTarget.checked)}
                />
                <ActionIcon variant="default" aria-label="Acercar" onClick={() => control.current?.acercar(1.25)}>
                  <IconZoomIn size={18} />
                </ActionIcon>
                <ActionIcon variant="default" aria-label="Alejar" onClick={() => control.current?.acercar(0.8)}>
                  <IconZoomOut size={18} />
                </ActionIcon>
                <ActionIcon variant="default" aria-label="Encuadrar todo" onClick={() => control.current?.ajustar()}>
                  <IconFocus2 size={18} />
                </ActionIcon>
                <Button variant="default" size="xs" leftSection={<IconDownload size={16} />} onClick={guardarPng}>
                  Guardar la vista en PNG
                </Button>
              </Group>
            </Group>
            <Grid>
              <Grid.Col span={{ base: 12, md: seleccionado ? 9 : 12 }}>
                <GrafoCausal
                  ref={control}
                  resultado={mostrado}
                  soloRelacionadas={soloRelacionadas}
                  seleccionado={seleccionado}
                  visible={pestana === "grafo"}
                  alSeleccionarNodo={setSeleccionado}
                  alElegirArista={elegirArista}
                />
              </Grid.Col>
              {seleccionado && (
                <Grid.Col span={{ base: 12, md: 3 }}>
                  <PanelVariable resultado={mostrado} variable={seleccionado} alCerrar={() => setSeleccionado(null)} />
                </Grid.Col>
              )}
            </Grid>
            <LeyendaGrafo />
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="caracterizacion" pt="md">
          <TablaCaracterizacion
            resultado={mostrado}
            alElegir={(variable) => {
              setSeleccionado(variable);
              setPestana("grafo");
            }}
          />
        </Tabs.Panel>

        <Tabs.Panel value="aristas" pt="md">
          <TablaAristas aristas={mostrado.aristas} alOrientar={elegirArista} />
        </Tabs.Panel>

        <Tabs.Panel value="advertencias" pt="md">
          <ListaAvisos avisos={mostrado.avisos} />
        </Tabs.Panel>

        <Tabs.Panel value="configuracion" pt="md">
          {pestana === "configuracion" && <PestanaConfiguracion id={id} resultado={mostrado} />}
        </Tabs.Panel>
      </Tabs>

      <DialogoOrientacion
        arista={aristaElegida}
        actual={aristaElegida ? orientacionDe(ajuste, aristaElegida.origen, aristaElegida.destino) : undefined}
        alCerrar={() => setAristaElegida(null)}
        alAplicar={aplicarOrientacion}
        alQuitar={() => aristaElegida && setBorrador(sinOrientacion(ajuste, aristaElegida.origen, aristaElegida.destino))}
      />

      <Modal opened={versionPendiente !== null} onClose={() => setVersionPendiente(null)} title="Cambios sin guardar">
        <Text size="sm">Si cambia a la versión {versionPendiente}, se descartan los cambios sin guardar del ajuste.</Text>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setVersionPendiente(null)}>
            Seguir ajustando
          </Button>
          <Button color="red" onClick={() => versionPendiente !== null && verVersion(versionPendiente)}>
            Descartar y cambiar
          </Button>
        </Group>
      </Modal>
    </Stack>
  );
}

function EtiquetaVersion({ etiqueta }: { etiqueta: string }) {
  if (!etiqueta) return null;
  return (
    <Badge color={etiqueta === "Original" ? "blue" : "orange"} variant="light" data-testid="etiqueta-version">
      {etiqueta}
    </Badge>
  );
}

function PestanaConfiguracion({ id, resultado }: { id: string; resultado: Parameters<typeof ResumenConfiguracion>[0]["resultado"] }) {
  const procedencia = useProcedencia(id);
  if (procedencia.isPending) return <Loader size="sm" />;
  if (procedencia.error) return <MensajeError error={procedencia.error} />;
  return <ResumenConfiguracion procedencia={procedencia.data} resultado={resultado} />;
}
