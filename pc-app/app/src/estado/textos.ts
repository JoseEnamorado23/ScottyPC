// Nombres legibles de tipos de hallazgo y acciones (solo presentación).

const TIPOS: Record<string, string> = {
  filas_duplicadas: "Filas duplicadas",
  valores_faltantes: "Valores faltantes",
  alta_proporcion_faltantes: "Alta proporción de faltantes",
  ceros_sospechosos: "Ceros sospechosos",
  constante: "Columna constante",
  casi_constante: "Columna casi constante",
  posible_identificador: "Posible identificador",
  texto_libre: "Texto libre",
  posible_fecha: "Posible fecha",
  variable_categorica: "Variable categórica",
  posible_variable_ordinal: "Posible variable ordinal",
  distribucion_objetivo: "Distribución del objetivo",
  desbalance_clases: "Desbalance de clases",
  columnas_redundantes: "Columnas redundantes",
  recodificacion_uno_a_uno: "Recodificación uno a uno",
  columna_derivada: "Columna derivada",
  binaria_derivada: "Binaria derivada",
  correlacion_casi_perfecta: "Correlación casi perfecta",
  posible_mezcla_unidades: "Posible mezcla de unidades",
  asimetria_fuerte: "Asimetría fuerte",
  faltantes_dependientes_objetivo: "Faltantes que dependen del objetivo",
  tamano_efectivo_insuficiente: "Tamaño efectivo insuficiente",
  grupo_redundante: "Grupo redundante",
};

const ACCIONES: Record<string, string> = {
  eliminar_duplicados: "Eliminar duplicados",
  conservar: "Conservar",
  imputar_mediana: "Imputar con la mediana",
  imputar_multivariada: "Imputación multivariada",
  eliminar_filas: "Eliminar las filas con faltantes",
  conservar_faltantes: "Conservar los faltantes",
  excluir_columna: "Excluir la columna",
  imputar_con_indicador: "Imputar y añadir indicador de medición",
  solo_casos_completos: "Usar solo casos completos",
  ceros_como_faltantes: "Tratar los ceros como faltantes",
  ceros_como_faltantes_imputar_mediana: "Ceros como faltantes e imputar con la mediana",
  separacion_temporal: "Usarla para una separación temporal",
  conservar_numerica: "Conservarla numérica",
  one_hot: "Codificación one-hot",
  binaria: "Codificación binaria",
  ordinal: "Codificación ordinal",
  usar_orden_sugerido: "Usar el orden sugerido",
  sin_orden: "Sin orden (one-hot)",
  conservar_clases: "Conservar las clases",
  agrupar_clases: "Agrupar clases",
  excluir_derivada: "Excluir la derivada",
  excluir_una: "Excluir una de las dos",
  convertir_unidades: "Convertir unidades",
  excluir_variables: "Excluir las redundantes",
  aplicar_logaritmo: "Aplicar logaritmo",
};

const legible = (clave: string) => {
  const texto = clave.replace(/_/g, " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
};

export const nombreTipo = (tipo: string) => TIPOS[tipo] ?? legible(tipo);
export const nombreAccion = (accion: string) => ACCIONES[accion] ?? legible(accion);

export function formatoValor(valor: unknown): string {
  if (typeof valor === "number") return valor.toLocaleString("es", { maximumFractionDigits: 4 });
  if (valor === null || valor === undefined) return "—";
  if (typeof valor === "string") return valor;
  if (Array.isArray(valor)) {
    return valor.map(formatoValor).join(valor.every((v) => typeof v !== "object" || v === null) ? ", " : "; ");
  }
  if (typeof valor === "object" && !Array.isArray(valor)) {
    return Object.entries(valor as Record<string, unknown>)
      .map(([clave, v]) => `${clave.replace(/_/g, " ")}: ${formatoValor(v)}`)
      .join(" · ");
  }
  return JSON.stringify(valor);
}
