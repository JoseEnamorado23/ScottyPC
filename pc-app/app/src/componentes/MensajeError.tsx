import { ActionIcon, Alert, Code, CopyButton, Group, Text, Tooltip } from "@mantine/core";
import { IconAlertTriangle, IconCheck, IconCopy } from "@tabler/icons-react";

import { ErrorApi, ErrorSinRespuesta } from "../api/cliente";

/** Mensaje de un error de la API en español; los 500 muestran la referencia del registro para copiarla. */
export function MensajeError({ error, titulo = "No se pudo completar la operación" }: { error: unknown; titulo?: string }) {
  if (!error) return null;
  const mensaje = error instanceof Error ? error.message : String(error);
  const referencia = error instanceof ErrorApi ? error.referencia : null;
  return (
    <Alert color="red" variant="light" title={titulo} icon={<IconAlertTriangle />} role="alert">
      <Text size="sm">{mensaje}</Text>
      {error instanceof ErrorSinRespuesta && (
        <Text size="sm" mt="xs">
          Use «Reiniciar el motor» en el aviso superior.
        </Text>
      )}
      {referencia && (
        <Group gap="xs" mt="xs">
          <Text size="sm">Referencia del registro:</Text>
          <Code>{referencia}</Code>
          <CopyButton value={referencia}>
            {({ copied, copy }) => (
              <Tooltip label={copied ? "Copiada" : "Copiar referencia"}>
                <ActionIcon variant="subtle" onClick={copy} aria-label="Copiar referencia">
                  {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                </ActionIcon>
              </Tooltip>
            )}
          </CopyButton>
        </Group>
      )}
    </Alert>
  );
}
