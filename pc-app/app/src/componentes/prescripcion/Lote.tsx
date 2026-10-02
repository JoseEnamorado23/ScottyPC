// Lotes de prescripciones: casos de test que no cumplen el objetivo o un CSV nuevo con las
// columnas originales. Tabla filtrable (alcanzado, no alcanzable, requiere revisión) y exportación.
import {
  Alert, Badge, Button, Card, Group, Modal, SegmentedControl, Select, Stack, Table, Text,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconFileExport, IconFileUpload, IconPlayerPlay } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import type { Esquemas } from "../../api/cliente";
import { elegirArchivo, elegirCarpeta } from "../../api/motor";
import { useAccionesPrescripcion, useEvaluaciones, useLotes, usePaginaLote } from "../../api/prescripcion";
import { numero, porcentaje } from "../../estado/modeloCausal";
import { FILTROS_LOTE } from "../../estado/prescripcion";
import { MensajeError } from "../MensajeError";
import { TarjetaPrescripcion } from "./Caso";

type Resultado = Esquemas["ResultadoPrescripcion"];

export function Lotes({ proyectoId, bloqueado, enCurso }: { proyectoId: string; bloqueado: boolean; enCurso: boolean }) {
  const lotes = useLotes(proyectoId, true);
  const evaluaciones = useEvaluaciones(proyectoId, true);
  const acciones = useAccionesPrescripcion(proyectoId);
  const [numero_, setNumero] = useState<number | null>(null);
  const [filtro, setFiltro] = useState("todos");
  const [pagina, setPagina] = useState(1);
  const [detalle, setDetalle] = useState<Resultado | null>(null);
  const lista = lotes.data ?? [];
  useEffect(() => {
    if (lista.length && (numero_ === null || !lista.some((l) => l.numero === numero_))) setNumero(lista[lista.length - 1].numero);
  }, [lista, numero_]);
  const datos = usePaginaLote(proyectoId, numero_, pagina, filtro === "todos" ? null : filtro);
  const meta = lista.find((l) => l.numero === numero_);
  const formato = (v: number, r: Resultado) => (r.medida === "probabilidad" ? porcentaje(v) : numero(v));

  const csv = async () => {
    const ruta = await elegirArchivo();
    if (ruta) acciones.lote.mutate({ origen: "csv", ruta_csv: ruta });
  };
  const exportar = async () => {
    const carpeta = await elegirCarpeta();
    if (!carpeta) return;
    const ultima = evaluaciones.data?.length ? evaluaciones.data[evaluaciones.data.length - 1].numero : null;
    acciones.exportar.mutate(
      { carpeta_destino: carpeta, lote: numero_, evaluacion: ultima },
      { onSuccess: (r) => notifications.show({ color: "green", message: `Exportado en ${r.carpeta}.` }) },
    );
  };
  const totalPaginas = datos.data ? Math.max(1, Math.ceil(datos.data.total / datos.data.por_pagina)) : 1;

  return (
    <Stack>
      <Card withBorder>
        <Group>
          <Button leftSection={<IconPlayerPlay size={16} />} onClick={() => acciones.lote.mutate({ origen: "test" })}
            loading={acciones.lote.isPending} disabled={bloqueado || enCurso}>
            Prescribir los casos de test que no cumplen el objetivo
          </Button>
          <Button variant="light" leftSection={<IconFileUpload size={16} />} onClick={csv} disabled={bloqueado || enCurso}>
            Prescribir un CSV nuevo…
          </Button>
          <Text size="xs" c="dimmed">El CSV debe tener las columnas ORIGINALES del dataset; se le aplica la receta completa.</Text>
        </Group>
        <MensajeError error={acciones.lote.error} titulo="No se pudo iniciar el lote" />
      </Card>

      {lista.length === 0 ? (
        <Text size="sm" c="dimmed">Todavía no hay lotes.</Text>
      ) : (
        <>
          <Group justify="space-between" align="flex-end">
            <Group align="flex-end">
              <Select label="Lote" w={320} allowDeselect={false} value={numero_ === null ? null : String(numero_)}
                onChange={(v) => { setNumero(Number(v)); setPagina(1); }}
                data={lista.map((l) => ({
                  value: String(l.numero),
                  label: `Lote ${l.numero} · ${l.origen === "test" ? "test" : "CSV"} · ${l.casos} casos`,
                }))} />
              <SegmentedControl
                value={filtro} onChange={(v) => { setFiltro(v); setPagina(1); }} aria-label="Filtrar el lote"
                data={FILTROS_LOTE.map((f) => ({
                  value: f.valor,
                  label: `${f.etiqueta}${f.valor !== "todos" && meta ? ` (${meta.resumen[f.valor] ?? 0})` : ""}`,
                }))}
              />
            </Group>
            <Button variant="default" leftSection={<IconFileExport size={16} />} onClick={exportar} loading={acciones.exportar.isPending}>
              Exportar CSV e informe
            </Button>
          </Group>
          <MensajeError error={acciones.exportar.error} titulo="No se pudo exportar" />
          {meta && meta.filas_con_problemas.length > 0 && (
            <Alert color="orange" variant="light" title={`${meta.filas_con_problemas.length} filas no se pudieron preparar`}>
              {meta.filas_con_problemas.slice(0, 5).map((p) => `Fila ${p.fila + 1}: ${p.mensaje}`).join(" · ")}
            </Alert>
          )}
          {meta && meta.columnas_ignoradas.length > 0 && (
            <Text size="xs" c="dimmed">Columnas ignoradas: {meta.columnas_ignoradas.join(", ")}.</Text>
          )}
          <Table.ScrollContainer minWidth={760}>
            <Table striped verticalSpacing={4} data-testid="tabla-lote">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Caso</Table.Th>
                  <Table.Th>Antes → después</Table.Th>
                  <Table.Th>Estado</Table.Th>
                  <Table.Th>Acciones</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {(datos.data?.filas ?? []).map((r) => (
                  <Table.Tr key={String(r.caso.indice)}>
                    <Table.Td>{String(r.caso.indice)}</Table.Td>
                    <Table.Td>{formato(r.antes, r)} → {formato(r.despues, r)}</Table.Td>
                    <Table.Td>
                      <Group gap={4}>
                        {r.ya_cumple ? <Badge size="xs" color="gray" variant="light">ya cumple</Badge>
                          : r.alcanzado ? <Badge size="xs" color="green" variant="light">alcanzado</Badge>
                            : <Badge size="xs" color="red" variant="light">no alcanzable</Badge>}
                        {r.requiere_revision && <Badge size="xs" color="orange" variant="light">revisión</Badge>}
                      </Group>
                    </Table.Td>
                    <Table.Td><Text size="xs">{r.acciones.map((a) => a.variable).join(", ") || "—"}</Text></Table.Td>
                    <Table.Td><Button size="compact-xs" variant="subtle" onClick={() => setDetalle(r)}>Ver</Button></Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Group gap={4}>
            <Button size="xs" variant="default" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anteriores</Button>
            <Text size="xs" c="dimmed">{pagina} / {totalPaginas} ({datos.data?.total ?? 0} casos)</Text>
            <Button size="xs" variant="default" disabled={pagina >= totalPaginas} onClick={() => setPagina(pagina + 1)}>Siguientes</Button>
          </Group>
        </>
      )}
      <Modal opened={detalle !== null} onClose={() => setDetalle(null)} size="xl" title={`Caso ${String(detalle?.caso.indice ?? "")}`}>
        {detalle && (
          <TarjetaPrescripcion r={detalle} proyectoId={proyectoId}
            indiceTest={meta?.origen === "test" ? Number(detalle.caso.indice) : null} />
        )}
      </Modal>
    </Stack>
  );
}
