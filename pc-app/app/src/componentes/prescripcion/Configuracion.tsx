// Configuración de la prescripción: objetivo deseado, modificables, restricciones por variable,
// μ, optimizador y declaración de supuestos (obligatoria). La validación y las condiciones las
// calcula el núcleo; aquí solo se edita el borrador.
import {
  Alert, Badge, Button, Card, Checkbox, Group, MultiSelect, NumberInput, SegmentedControl, Select, Stack, Switch, Table,
  Text, Title,
} from "@mantine/core";
import { IconAdjustments, IconDeviceFloppy } from "@tabler/icons-react";

import type { Esquemas } from "../../api/cliente";
import { numero, porcentaje } from "../../estado/modeloCausal";
import {
  SUPUESTOS, conAccion, conSupuesto, confirmados, supuestosDe,
} from "../../estado/prescripcion";

type Configuracion = Esquemas["ConfiguracionPrescripcion"];
type Vista = Esquemas["VistaConfiguracionPrescripcion"];
type Control = Esquemas["ControlVariable"];

interface Props {
  vista: Vista;
  borrador: Configuracion;
  errores: Record<string, string>;
  sinGuardar: boolean;
  guardando: boolean;
  calibrando: boolean;
  alCambiar: (c: Configuracion) => void;
  alGuardar: () => void;
  alDescartar: () => void;
  alCalibrar: () => void;
}

const numeroONulo = (v: string | number) => (typeof v === "number" ? v : null);

function FilaAccion({
  control, borrador, errores, alCambiar,
}: { control: Control; borrador: Configuracion; errores: Record<string, string>; alCambiar: (c: Configuracion) => void }) {
  const variable = control.nombre;
  const accion = borrador.acciones[variable];
  if (!accion) return null;
  const numerica = control.control === "numerica" || control.control === "ordinal";
  const campo = (c: string) => errores[`acciones.${variable}.${c}`];
  const cambiar = (cambios: Partial<Esquemas["ConfiguracionAccion"]>) => alCambiar(conAccion(borrador, variable, cambios));
  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm" fw={500}>{variable}</Text>
        <Text size="xs" c="dimmed">
          {control.rol === "raiz" ? "raíz" : "intermedia"}
          {numerica && control.minimo !== null && ` · train: ${numero(control.minimo, 2)} – ${numero(control.maximo, 2)}`}
        </Text>
      </Table.Td>
      <Table.Td>
        <Switch aria-label={`Permitir ${variable}`} checked={accion.permitida ?? true} onChange={(e) => cambiar({ permitida: e.currentTarget.checked })} />
      </Table.Td>
      <Table.Td>
        {control.control === "grupo_one_hot" ? (
          <Text size="xs" c="dimmed">—</Text>
        ) : (
          <Select
            size="xs" w={120} aria-label={`Dirección de ${variable}`} allowDeselect={false}
            value={accion.direccion ?? "ambas"}
            onChange={(v) => cambiar({ direccion: (v ?? "ambas") as "subir" | "bajar" | "ambas" })}
            data={[{ value: "ambas", label: "Ambas" }, { value: "subir", label: "Solo subir" }, { value: "bajar", label: "Solo bajar" }]}
          />
        )}
      </Table.Td>
      {numerica ? (
        <>
          <Table.Td>
            <NumberInput size="xs" w={100} aria-label={`Mínimo de ${variable}`} decimalSeparator="," value={accion.minimo ?? ""}
              error={campo("minimo")} onChange={(v) => cambiar({ minimo: numeroONulo(v) })} />
          </Table.Td>
          <Table.Td>
            <NumberInput size="xs" w={100} aria-label={`Máximo de ${variable}`} decimalSeparator="," value={accion.maximo ?? ""}
              error={campo("maximo")} onChange={(v) => cambiar({ maximo: numeroONulo(v) })} />
          </Table.Td>
          <Table.Td>
            <NumberInput size="xs" w={100} aria-label={`Cambio máximo de ${variable}`} decimalSeparator="," min={0}
              value={accion.cambio_maximo ?? ""} error={campo("cambio_maximo")} onChange={(v) => cambiar({ cambio_maximo: numeroONulo(v) })} />
          </Table.Td>
        </>
      ) : (
        <Table.Td colSpan={3}>
          <MultiSelect
            size="xs" aria-label={`Estados permitidos de ${variable}`} placeholder="Todos"
            data={control.categorias.map((c) => ({ value: String(c), label: String(c) }))}
            value={(accion.estados_permitidos ?? []).map(String)}
            error={campo("estados_permitidos")}
            onChange={(v) => cambiar({
              estados_permitidos: v.length ? v.map((x) => control.categorias.find((c) => String(c) === x) ?? x) : null,
            })}
          />
        </Table.Td>
      )}
      <Table.Td>
        <NumberInput size="xs" w={80} aria-label={`Costo de ${variable}`} decimalSeparator="," min={0}
          value={accion.costo ?? 1} error={campo("costo")} onChange={(v) => cambiar({ costo: typeof v === "number" ? v : 1 })} />
      </Table.Td>
    </Table.Tr>
  );
}

export function ConfiguracionPrescripcion(p: Props) {
  const { vista, borrador, errores } = p;
  const probabilidad = vista.medida === "probabilidad";
  const controles = vista.controles.filter((c) => borrador.acciones[c.nombre]);
  const mu = borrador.mu;
  const manual = mu !== "automatico";
  const sinConfirmar = controles.filter((c) => (borrador.acciones[c.nombre]?.permitida ?? true) && !confirmados(supuestosDe(borrador, c.nombre)));
  return (
    <Stack>
      <Card withBorder id="seccion-objetivo">
        <Stack gap="sm">
          <Title order={4}>Objetivo deseado</Title>
          {probabilidad && (
            <SegmentedControl
              aria-label="Clase de interés"
              value={String(borrador.objetivo.clase_positiva ?? 1)}
              onChange={(v) => p.alCambiar({ ...borrador, objetivo: { ...borrador.objetivo, clase_positiva: Number(v) as 0 | 1 } })}
              data={[
                { value: "1", label: `${vista.objetivo}=1` },
                { value: "0", label: `${vista.objetivo}=0` },
              ]}
            />
          )}
          <Group align="flex-end">
            <SegmentedControl
              aria-label="Dirección del objetivo"
              value={borrador.objetivo.direccion}
              onChange={(v) => p.alCambiar({ ...borrador, objetivo: { ...borrador.objetivo, direccion: v as "subir" | "bajar" } })}
              data={[
                { value: "bajar", label: probabilidad ? "Bajar la probabilidad" : "Bajar el valor" },
                { value: "subir", label: probabilidad ? "Subir la probabilidad" : "Subir el valor" },
              ]}
            />
            <NumberInput
              label={probabilidad ? `Probabilidad deseada de ${vista.objetivo}=${borrador.objetivo.clase_positiva ?? 1}` : "Valor deseado"}
              w={220} decimalSeparator="," step={probabilidad ? 0.01 : 1} min={probabilidad ? 0 : undefined} max={probabilidad ? 1 : undefined}
              value={borrador.objetivo.valor} error={errores["objetivo.valor"]}
              onChange={(v) => p.alCambiar({ ...borrador, objetivo: { ...borrador.objetivo, valor: typeof v === "number" ? v : 0 } })}
            />
          </Group>
          {probabilidad && vista.umbral_decision !== null && (
            <Text size="xs" c="dimmed">
              Umbral de decisión del modelo: {porcentaje(vista.umbral_decision)}. La clase y la dirección son una decisión tuya: el valor
              inicial es solo una sugerencia (bajar la clase 1 si es minoritaria; umbral ± 0,1) y puedes cambiarlo.
            </Text>
          )}
        </Stack>
      </Card>

      <Card withBorder id="seccion-modificables">
        <Stack gap="sm">
          <Title order={4}>Variables modificables</Title>
          <MultiSelect
            aria-label="Variables modificables" searchable
            data={vista.variables_grafo} value={borrador.modificables}
            onChange={(v) => p.alCambiar({ ...borrador, modificables: v })}
          />
          <Text size="xs" c="dimmed">
            La lista parte de las modificables de la configuración de PC ({vista.modificables_pc.join(", ") || "ninguna"}). Cambiarla
            solo desactualiza la prescripción, no el análisis. Solo son prescriptivas las que además son ancestros del objetivo.
          </Text>
          {vista.sin_camino.length > 0 && (
            <Text size="xs">Sin camino al objetivo (se ignoran): {vista.sin_camino.join(", ")}.</Text>
          )}
          {controles.length > 0 && (
            <Table.ScrollContainer minWidth={820}>
              <Table verticalSpacing={6} data-testid="tabla-acciones">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Variable prescriptiva</Table.Th>
                    <Table.Th>Permitida</Table.Th>
                    <Table.Th>Dirección</Table.Th>
                    <Table.Th>Mínimo</Table.Th>
                    <Table.Th>Máximo</Table.Th>
                    <Table.Th>Cambio máximo</Table.Th>
                    <Table.Th>Costo</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {controles.map((c) => (
                    <FilaAccion key={c.nombre} control={c} borrador={borrador} errores={errores} alCambiar={p.alCambiar} />
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
          <Text size="xs" c="dimmed">
            Límites y cambio máximo en unidades originales (por defecto, el rango de entrenamiento y el 25 % de ese rango). El costo
            es por unidad de la escala normalizada, para que sea comparable entre variables.
          </Text>
        </Stack>
      </Card>

      <Card withBorder id="seccion-supuestos">
        <Stack gap="sm">
          <Title order={4}>Declaración de supuestos</Title>
          <Text size="sm" c="dimmed">
            El sistema no puede verificar estas condiciones con los datos. Confírmelas para cada variable prescriptiva.
          </Text>
          {controles.map((c) => {
            const s = supuestosDe(borrador, c.nombre);
            return (
              <Group key={c.nombre} align="flex-start" gap="lg" data-testid={`supuestos-${c.nombre}`}>
                <Text size="sm" fw={500} w={200}>{c.nombre}</Text>
                <Stack gap={4}>
                  {SUPUESTOS.map(({ campo, texto }) => (
                    <Checkbox
                      key={campo} label={texto} aria-label={`${texto} (${c.nombre})`} checked={s[campo]}
                      onChange={(e) => p.alCambiar(conSupuesto(borrador, c.nombre, campo, e.currentTarget.checked))}
                    />
                  ))}
                  {s.confirmado_en && <Text size="xs" c="dimmed">Confirmado el {s.confirmado_en.replace("T", " ")}</Text>}
                </Stack>
              </Group>
            );
          })}
          {sinConfirmar.length > 0 && (
            <Alert color="orange" variant="light" py="xs">
              Falta confirmar: {sinConfirmar.map((c) => c.nombre).join(", ")}. Sin la declaración no se puede prescribir.
            </Alert>
          )}
        </Stack>
      </Card>

      <Card withBorder id="seccion-optimizacion">
        <Stack gap="sm">
          <Title order={4}>Optimización</Title>
          <Group align="flex-end">
            <Select
              label="Optimizador" w={220} allowDeselect={false} value={borrador.optimizador}
              onChange={(v) => p.alCambiar({ ...borrador, optimizador: (v ?? "gradiente_proximal") as Configuracion["optimizador"] })}
              data={[{ value: "gradiente_proximal", label: "Gradiente proximal" }, { value: "genetico", label: "Genético" }]}
            />
            <SegmentedControl
              aria-label="Modo de μ" value={manual ? "manual" : "automatico"}
              onChange={(v) => p.alCambiar({ ...borrador, mu: v === "manual" ? (vista.mu_efectivo ?? 0.01) : "automatico" })}
              data={[{ value: "automatico", label: "μ automático" }, { value: "manual", label: "μ manual" }]}
            />
            {manual && (
              <NumberInput label="μ" w={120} decimalSeparator="," min={0} step={0.001} value={mu as number}
                error={errores.mu} onChange={(v) => p.alCambiar({ ...borrador, mu: typeof v === "number" ? v : 0 })} />
            )}
          </Group>
          <Text size="xs" c="dimmed">
            μ es el peso de la intervención mínima: más grande, cambios más pequeños y menos variables. El automático se calibra solo con
            entrenamiento (el mayor μ con el que al menos el 95 % de los casos alcanzables llega al objetivo).
          </Text>
          {!manual && (
            <Group>
              <Badge variant="light" color={vista.calibracion ? "green" : "orange"}>
                {vista.calibracion ? `μ calibrado: ${numero(vista.calibracion.mu, 6)}` : "μ sin calibrar"}
              </Badge>
              <Button size="xs" variant="light" leftSection={<IconAdjustments size={14} />} onClick={p.alCalibrar}
                loading={p.calibrando} disabled={!vista.guardada || p.sinGuardar}>
                Calibrar μ
              </Button>
              {(!vista.guardada || p.sinGuardar) && <Text size="xs" c="dimmed">Guarde la configuración antes de calibrar.</Text>}
            </Group>
          )}
          {vista.calibracion && !manual && (
            <Stack gap={4}>
              <Table withTableBorder verticalSpacing={2} data-testid="rejilla-mu">
                <Table.Thead>
                  <Table.Tr><Table.Th>μ</Table.Th><Table.Th ta="right">Tasa de éxito</Table.Th><Table.Th ta="right">Casos</Table.Th></Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {vista.calibracion.rejilla.map((r) => (
                    <Table.Tr key={r.mu} fw={r.mu === vista.calibracion!.mu ? 700 : undefined}>
                      <Table.Td>{numero(r.mu, 6)}</Table.Td>
                      <Table.Td ta="right">{porcentaje(r.tasa_exito)}</Table.Td>
                      <Table.Td ta="right">{r.exitos} / {r.evaluados}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
              <Text size="xs" c="dimmed">
                {vista.calibracion.casos} casos de entrenamiento no cumplen el objetivo ({vista.calibracion.alcanzables} alcanzables,{" "}
                {vista.calibracion.no_alcanzables} no alcanzables). {vista.calibracion.nota}
              </Text>
              {vista.calibracion.advertencia && <Alert color="orange" variant="light" py="xs">{vista.calibracion.advertencia}</Alert>}
            </Stack>
          )}
        </Stack>
      </Card>

      <Group justify="flex-end">
        {p.sinGuardar && (
          <>
            <Badge color="orange" variant="light" size="lg" data-testid="prescripcion-sin-guardar">Cambios sin guardar</Badge>
            <Button variant="default" onClick={p.alDescartar} disabled={p.guardando}>Descartar</Button>
          </>
        )}
        <Button leftSection={<IconDeviceFloppy size={16} />} onClick={p.alGuardar} loading={p.guardando}
          disabled={Object.keys(errores).length > 0 || (!p.sinGuardar && vista.guardada)}>
          Guardar configuración
        </Button>
      </Group>
      <Text size="xs" c="dimmed" ta="right">Guardar archiva los lotes, las evaluaciones y la calibración anteriores.</Text>
    </Stack>
  );
}
