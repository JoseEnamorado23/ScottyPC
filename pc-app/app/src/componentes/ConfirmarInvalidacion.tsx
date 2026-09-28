import { Button, Group, List, Modal, Text } from "@mantine/core";
import { useCallback, useRef, useState } from "react";

/**
 * Advertencia antes de guardar una etapa cuando hay etapas posteriores vigentes
 * que quedarán desactualizadas. `confirmar(nombres)` resuelve `true` sin preguntar
 * si la lista está vacía.
 */
export function useConfirmarInvalidacion() {
  const [etapas, setEtapas] = useState<string[] | null>(null);
  const resolver = useRef<(aceptado: boolean) => void>(() => {});

  const confirmar = useCallback((afectadas: string[]) => {
    if (afectadas.length === 0) return Promise.resolve(true);
    setEtapas(afectadas);
    return new Promise<boolean>((r) => (resolver.current = r));
  }, []);

  const cerrar = (aceptado: boolean) => {
    setEtapas(null);
    resolver.current(aceptado);
  };

  const modal = (
    <Modal opened={etapas !== null} onClose={() => cerrar(false)} title="Se desactualizarán etapas posteriores">
      <Text size="sm">Al guardar, estas etapas quedarán desactualizadas y habrá que repetirlas:</Text>
      <List size="sm" my="sm">
        {etapas?.map((e) => <List.Item key={e}>{e}</List.Item>)}
      </List>
      <Text size="sm" c="dimmed">
        Sus archivos anteriores se conservan en la carpeta del proyecto.
      </Text>
      <Group justify="flex-end" mt="md">
        <Button variant="default" onClick={() => cerrar(false)}>
          Cancelar
        </Button>
        <Button color="orange" onClick={() => cerrar(true)}>
          Guardar de todos modos
        </Button>
      </Group>
    </Modal>
  );

  return { confirmar, modal };
}
