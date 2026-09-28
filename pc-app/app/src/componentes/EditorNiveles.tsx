// Editor de niveles con arrastrar y soltar (dnd-kit): columnas = niveles (se pueden
// agregar, eliminar, renombrar y reordenar) y fichas = variables (se arrastran entre
// niveles; también se pueden mover con el menú de cada ficha o con el teclado).
import {
  closestCorners,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  horizontalListSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ActionIcon, Badge, Button, Group, Menu, Paper, ScrollArea, Stack, Text, TextInput, Tooltip } from "@mantine/core";
import { IconDotsVertical, IconGripVertical, IconPlus, IconTrash } from "@tabler/icons-react";
import { useState, type Dispatch } from "react";

import { nivelDe, type AccionNiveles, type EstadoNiveles, type Nivel } from "../estado/niveles";

interface Props {
  estado: EstadoNiveles;
  despachar: Dispatch<AccionNiveles>;
  objetivo: string;
  /** Errores del servidor por ruta (`niveles.2`, `nombres_niveles.0`...). */
  errores: Record<string, string>;
}

type Arrastre = { tipo: "ficha"; variable: string } | { tipo: "nivel"; nivel: Nivel } | null;

export function EditorNiveles({ estado, despachar, objetivo, errores }: Props) {
  const [arrastre, setArrastre] = useState<Arrastre>(null);
  const sensores = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const indiceNivel = (id: string) => estado.niveles.findIndex((n) => n.id === id);

  const alEmpezar = ({ active }: DragStartEvent) => {
    if (active.data.current?.tipo === "nivel") {
      setArrastre({ tipo: "nivel", nivel: estado.niveles[indiceNivel(String(active.id))] });
    } else {
      setArrastre({ tipo: "ficha", variable: String(active.id) });
    }
  };

  const alSoltar = ({ active, over }: DragEndEvent) => {
    setArrastre(null);
    if (!over) return;
    const destino = over.data.current as { tipo?: string; nivel?: string } | undefined;
    // Nivel sobre el que se soltó: el propio, el de su zona o el que contiene la ficha.
    const nivelDestino =
      destino?.tipo === "nivel" ? String(over.id)
      : destino?.tipo === "zona" ? destino.nivel!
      : nivelDe(estado, String(over.id))?.id;
    if (!nivelDestino) return;

    if (active.data.current?.tipo === "nivel") {
      despachar({ tipo: "reordenar", desde: indiceNivel(String(active.id)), hasta: indiceNivel(nivelDestino) });
      return;
    }
    const nivel = estado.niveles[indiceNivel(nivelDestino)];
    const indice = destino?.tipo === "ficha" ? nivel.variables.indexOf(String(over.id)) : undefined;
    despachar({ tipo: "mover", variable: String(active.id), nivel: nivelDestino, indice });
  };

  return (
    <DndContext
      sensors={sensores}
      collisionDetection={closestCorners}
      onDragStart={alEmpezar}
      onDragEnd={alSoltar}
      onDragCancel={() => setArrastre(null)}
    >
      <ScrollArea type="auto" offsetScrollbars>
        <SortableContext items={estado.niveles.map((n) => n.id)} strategy={horizontalListSortingStrategy}>
          <Group align="stretch" wrap="nowrap" gap="sm" pb="xs">
            {estado.niveles.map((nivel, i) => (
              <ColumnaNivel
                key={nivel.id}
                nivel={nivel}
                posicion={i}
                estado={estado}
                objetivo={objetivo}
                despachar={despachar}
                error={errores[`niveles.${i}`]}
                errorNombre={errores[`nombres_niveles.${i}`]}
              />
            ))}
            <Button
              variant="light"
              leftSection={<IconPlus size={16} />}
              onClick={() => despachar({ tipo: "agregar" })}
              style={{ alignSelf: "flex-start", flexShrink: 0 }}
            >
              Agregar nivel
            </Button>
          </Group>
        </SortableContext>
      </ScrollArea>
      <DragOverlay>
        {arrastre?.tipo === "ficha" && <Ficha variable={arrastre.variable} esObjetivo={arrastre.variable === objetivo} />}
        {arrastre?.tipo === "nivel" && (
          <Paper withBorder p="sm" w={220} shadow="md">
            <Text fw={600}>{arrastre.nivel.nombre}</Text>
          </Paper>
        )}
      </DragOverlay>
    </DndContext>
  );
}

function ColumnaNivel({ nivel, posicion, estado, objetivo, despachar, error, errorNombre }: {
  nivel: Nivel;
  posicion: number;
  estado: EstadoNiveles;
  objetivo: string;
  despachar: Dispatch<AccionNiveles>;
  error?: string;
  errorNombre?: string;
}) {
  const ordenable = useSortable({ id: nivel.id, data: { tipo: "nivel" } });
  const zona = useDroppable({ id: `zona:${nivel.id}`, data: { tipo: "zona", nivel: nivel.id } });
  return (
    <Paper
      ref={ordenable.setNodeRef}
      withBorder
      p="sm"
      w={230}
      style={{
        flexShrink: 0,
        transform: CSS.Transform.toString(ordenable.transform),
        transition: ordenable.transition,
        opacity: ordenable.isDragging ? 0.4 : 1,
        borderColor: error ? "var(--mantine-color-red-6)" : undefined,
      }}
      data-testid={`nivel-${posicion}`}
    >
      <Stack gap="xs">
        <Group gap={4} wrap="nowrap">
          <ActionIcon
            variant="subtle"
            color="gray"
            aria-label={`Arrastrar ${nivel.nombre}`}
            {...ordenable.attributes}
            {...ordenable.listeners}
          >
            <IconGripVertical size={16} />
          </ActionIcon>
          <TextInput
            size="xs"
            style={{ flex: 1 }}
            aria-label={`Nombre del nivel ${posicion + 1}`}
            value={nivel.nombre}
            onChange={(e) => despachar({ tipo: "renombrar", nivel: nivel.id, nombre: e.currentTarget.value })}
            error={errorNombre}
          />
          <Tooltip label={estado.niveles.length === 1 ? "Debe haber al menos un nivel" : "Eliminar el nivel (sus variables pasan al nivel vecino)"}>
            <ActionIcon
              variant="subtle"
              color="red"
              aria-label={`Eliminar ${nivel.nombre}`}
              disabled={estado.niveles.length === 1}
              onClick={() => despachar({ tipo: "eliminar", nivel: nivel.id })}
            >
              <IconTrash size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
        <SortableContext items={nivel.variables} strategy={verticalListSortingStrategy}>
          <Stack
            ref={zona.setNodeRef}
            gap={6}
            mih={80}
            p={4}
            style={{
              borderRadius: 6,
              background: zona.isOver ? "var(--mantine-color-blue-0)" : "var(--mantine-color-gray-0)",
            }}
          >
            {nivel.variables.length === 0 && (
              <Text size="xs" c="dimmed" ta="center" mt="md">
                Arrastre variables aquí
              </Text>
            )}
            {nivel.variables.map((variable) => (
              <FichaOrdenable
                key={variable}
                variable={variable}
                nivel={nivel}
                estado={estado}
                esObjetivo={variable === objetivo}
                despachar={despachar}
              />
            ))}
          </Stack>
        </SortableContext>
        {error && (
          <Text size="xs" c="red" role="alert">
            {error}
          </Text>
        )}
      </Stack>
    </Paper>
  );
}

function FichaOrdenable({ variable, nivel, estado, esObjetivo, despachar }: {
  variable: string;
  nivel: Nivel;
  estado: EstadoNiveles;
  esObjetivo: boolean;
  despachar: Dispatch<AccionNiveles>;
}) {
  const ordenable = useSortable({ id: variable, data: { tipo: "ficha", nivel: nivel.id } });
  return (
    <div
      ref={ordenable.setNodeRef}
      style={{
        transform: CSS.Transform.toString(ordenable.transform),
        transition: ordenable.transition,
        opacity: ordenable.isDragging ? 0.4 : 1,
      }}
    >
      <Ficha
        variable={variable}
        esObjetivo={esObjetivo}
        asa={{ ...ordenable.attributes, ...ordenable.listeners }}
        menu={
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <ActionIcon size="sm" variant="subtle" color="gray" aria-label={`Mover ${variable}`}>
                <IconDotsVertical size={14} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>Mover a</Menu.Label>
              {estado.niveles
                .filter((n) => n.id !== nivel.id)
                .map((n) => (
                  <Menu.Item key={n.id} onClick={() => despachar({ tipo: "mover", variable, nivel: n.id })}>
                    {n.nombre}
                  </Menu.Item>
                ))}
            </Menu.Dropdown>
          </Menu>
        }
      />
    </div>
  );
}

function Ficha({ variable, esObjetivo, asa, menu }: {
  variable: string;
  esObjetivo: boolean;
  asa?: Record<string, unknown>;
  menu?: React.ReactNode;
}) {
  return (
    <Paper
      withBorder
      px="xs"
      py={4}
      bg={esObjetivo ? "orange.0" : "white"}
      style={{ borderColor: esObjetivo ? "var(--mantine-color-orange-5)" : undefined }}
      data-testid={`ficha-${variable}`}
    >
      <Group gap={4} wrap="nowrap">
        <Group gap={4} wrap="nowrap" style={{ flex: 1, cursor: "grab", minWidth: 0 }} {...asa} aria-label={`Arrastrar ${variable}`}>
          <IconGripVertical size={14} color="var(--mantine-color-gray-5)" />
          <Text size="sm" truncate title={variable}>
            {variable}
          </Text>
          {esObjetivo && (
            <Badge size="xs" color="orange" variant="light">
              objetivo
            </Badge>
          )}
        </Group>
        {menu}
      </Group>
    </Paper>
  );
}
