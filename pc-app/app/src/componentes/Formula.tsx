import katex from "katex";
import "katex/dist/katex.min.css";
import { useMemo } from "react";

/** Fórmula LaTeX renderizada con KaTeX. Un LaTeX inválido se muestra como texto, sin romper la pantalla. */
export function Formula({ latex, bloque = false }: { latex: string; bloque?: boolean }) {
  const html = useMemo(
    () => katex.renderToString(latex, { displayMode: bloque, throwOnError: false, trust: false, strict: "ignore" }),
    [latex, bloque],
  );
  return (
    <span
      role="math"
      aria-label={latex}
      style={bloque ? { display: "block", overflowX: "auto", overflowY: "hidden" } : undefined}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
