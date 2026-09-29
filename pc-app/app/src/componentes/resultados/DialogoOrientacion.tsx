// Diálogo para orientar a mano una arista que PC dejó sin orientar (o cambiar/quitar una
// orientación manual). La dirección se valida en el núcleo contra los niveles: los errores
// llegan como 422 por campo y se muestran junto al control correspondiente.
import { Alert, Button, Group, Modal, Radio, Stack, Text, Textarea } from "@mantine/core";
import { useEffect, useState } from "react";

import type { Orientacion } from "../../estado/ajustes";
import type { Arista } from "../../estado/grafo";

export interface ErroresOrientacion {
  direccion?: string;
  justificacion?: string;
  general?: string;
}

interface Props {
  /** Arista a orientar; `null` = diálogo cerrado. */
  arista: Arista | null;
  /** Orientación manual que ya tiene la arista en el ajuste en curso. */
  actual: Orientacion | undefined;
  alCerrar: () => void;
  /** Valida y aplica la orientación; devuelve los errores o `null` si se aplicó. */
  alAplicar: (orientacion: Orientacion) => Promise<ErroresOrientacion | null>;
  alQuitar: () => void;
}

/** Errores de la reagregación que corresponden a la orientación en la posición `indice`. */
export function erroresDeOrientacion(porCampo: Record<string, string>, indice: number): ErroresOrientacion {
  const errores: ErroresOrientacion = {};
  const otros: string[] = [];
  for (const [campo, mensaje] of Object.entries(porCampo)) {
    if (campo === `orientaciones_manuales.${indice}`) errores.direccion = mensaje;
    else if (campo === `orientaciones_manuales.${indice}.justificacion`) errores.justificacion = mensaje;
    else otros.push(mensaje);
  }
  if (otros.length) errores.general = otros.join(" ");
  return errores;
}

export function DialogoOrientacion({ arista, actual, alCerrar, alAplicar, alQuitar }: Props) {
  const [direccion, setDireccion] = useState<string | null>(null);
  const [justificacion, setJustificacion] = useState("");
  const [errores, setErrores] = useState<ErroresOrientacion>({});
  const [validando, setValidando] = useState(false);

  useEffect(() => {
    setDireccion(actual ? `${actual.origen}→${actual.destino}` : null);
    setJustificacion(actual?.justificacion ?? "");
    setErrores({});
  }, [arista, actual]);

  if (!arista) return null;
  const [a, b] = [arista.origen, arista.destino];
  const opciones = [
    { valor: `${a}→${b}`, origen: a, destino: b },
    { valor: `${b}→${a}`, origen: b, destino: a },
  ];
  const elegida = opciones.find((o) => o.valor === direccion);
  const puedeAplicar = !!elegida && justificacion.trim().length > 0 && !validando;

  const aplicar = async () => {
    if (!elegida) return;
    setValidando(true);
    try {
      const resultado = await alAplicar({ origen: elegida.origen, destino: elegida.destino, justificacion: justificacion.trim() });
      if (resultado) setErrores(resultado);
      else alCerrar();
    } finally {
      setValidando(false);
    }
  };

  return (
    <Modal opened onClose={alCerrar} title={`Orientar la arista ${a} — ${b}`} size="lg">
      <Stack>
        <Text size="sm">
          {arista.tipo === "sin_orientar"
            ? "PC no pudo decidir la dirección de esta arista con los datos. "
            : "Esta arista tiene una orientación manual. "}
          Elija la dirección que respalda su conocimiento del tema y explique por qué: la justificación queda en la
          versión guardada y en el informe. Una dirección que contradiga los niveles se rechaza.
        </Text>
        <Radio.Group
          label="Dirección"
          value={direccion}
          onChange={(valor) => {
            setDireccion(valor);
            setErrores((e) => ({ ...e, direccion: undefined, general: undefined }));
          }}
          error={errores.direccion}
          withAsterisk
        >
          <Stack gap="xs" mt="xs">
            {opciones.map((o) => (
              <Radio key={o.valor} value={o.valor} label={`${o.origen} → ${o.destino}`} />
            ))}
          </Stack>
        </Radio.Group>
        <Textarea
          label="Justificación"
          description="Obligatoria. Por ejemplo: «la edad se registra antes que la glucosa»."
          value={justificacion}
          onChange={(e) => {
            setJustificacion(e.currentTarget.value);
            setErrores((errores) => ({ ...errores, justificacion: undefined }));
          }}
          error={errores.justificacion}
          autosize
          minRows={2}
          withAsterisk
        />
        {errores.general && (
          <Alert color="red" variant="light" role="alert">
            {errores.general}
          </Alert>
        )}
        <Group justify="space-between">
          <div>
            {actual && (
              <Button
                variant="subtle"
                color="red"
                onClick={() => {
                  alQuitar();
                  alCerrar();
                }}
              >
                Quitar la orientación manual
              </Button>
            )}
          </div>
          <Group>
            <Button variant="default" onClick={alCerrar}>
              Cancelar
            </Button>
            <Button onClick={aplicar} disabled={!puedeAplicar} loading={validando}>
              Aplicar
            </Button>
          </Group>
        </Group>
      </Stack>
    </Modal>
  );
}
