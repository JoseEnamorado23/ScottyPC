import { Alert, List, Text } from "@mantine/core";
import { IconAlertTriangle, IconBan } from "@tabler/icons-react";

import type { Esquemas } from "../api/cliente";

type Problema = Esquemas["ProblemaValidacion"];

export function ProblemasValidacion({ problemas, bloqueantes }: { problemas: Problema[]; bloqueantes: boolean }) {
  if (problemas.length === 0) return null;
  return (
    <Alert
      color={bloqueantes ? "red" : "yellow"}
      variant="light"
      icon={bloqueantes ? <IconBan /> : <IconAlertTriangle />}
      title={bloqueantes ? "El dataset no se puede analizar" : "Advertencias de validación"}
      role={bloqueantes ? "alert" : undefined}
    >
      {bloqueantes && (
        <Text size="sm" mb="xs">
          Corrija estos problemas en el archivo (o elija otra hoja u objetivo) para poder continuar.
        </Text>
      )}
      <List size="sm">
        {problemas.map((p, i) => (
          <List.Item key={`${p.codigo}-${i}`}>
            {p.mensaje}
            {p.columnas.length > 0 && <Text span c="dimmed"> ({p.columnas.join(", ")})</Text>}
          </List.Item>
        ))}
      </List>
    </Alert>
  );
}

/** Los errores de validación que llegan en `detalles` de un 422 DATASET_NO_VALIDO. */
export function esListaDeProblemas(detalles: unknown): detalles is Problema[] {
  return Array.isArray(detalles) && detalles.every((d) => d && typeof d === "object" && "nivel" in d && "mensaje" in d);
}
