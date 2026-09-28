import { describe, expect, it } from "vitest";

import { aConfiguracion, crearEstado, nivelDe, reducirNiveles, type AccionNiveles, type EstadoNiveles } from "../estado/niveles";

const inicial = () => crearEstado([["Age", "Pregnancies", "BMI", "Glucose"], ["Outcome"]]);

function aplicar(estado: EstadoNiveles, ...acciones: AccionNiveles[]) {
  return acciones.reduce(reducirNiveles, estado);
}

const variables = (estado: EstadoNiveles) => estado.niveles.map((n) => n.variables);
const todas = (estado: EstadoNiveles) => estado.niveles.flatMap((n) => n.variables).sort();

describe("editor de niveles", () => {
  it("parte de la plantilla con nombres por defecto", () => {
    const estado = inicial();

    expect(estado.niveles.map((n) => n.nombre)).toEqual(["Nivel 1", "Nivel 2"]);
    expect(aConfiguracion(estado)).toEqual({
      niveles: [["Age", "Pregnancies", "BMI", "Glucose"], ["Outcome"]],
      nombres_niveles: null,
    });
  });

  it("mueve fichas entre niveles y dentro de un nivel sin duplicarlas", () => {
    let estado = aplicar(inicial(), { tipo: "agregar", posicion: 1 });
    const [primero, medio, ultimo] = estado.niveles.map((n) => n.id);

    estado = aplicar(
      estado,
      { tipo: "mover", variable: "BMI", nivel: medio },
      { tipo: "mover", variable: "Glucose", nivel: medio, indice: 0 },
      { tipo: "mover", variable: "Age", nivel: primero, indice: 2 },
    );

    expect(variables(estado)).toEqual([["Pregnancies", "Age"], ["Glucose", "BMI"], ["Outcome"]]);
    expect(todas(estado)).toEqual(["Age", "BMI", "Glucose", "Outcome", "Pregnancies"]);
    expect(nivelDe(estado, "BMI")?.id).toBe(medio);
    expect(nivelDe(estado, "Outcome")?.id).toBe(ultimo);
  });

  it("mover a un nivel inexistente o una variable desconocida no cambia nada", () => {
    const estado = inicial();

    expect(aplicar(estado, { tipo: "mover", variable: "BMI", nivel: "nada" })).toBe(estado);
    expect(aplicar(estado, { tipo: "mover", variable: "Nada", nivel: estado.niveles[1].id })).toBe(estado);
  });

  it("agrega niveles en cualquier posición con identificadores nuevos", () => {
    const estado = aplicar(inicial(), { tipo: "agregar", posicion: 0 }, { tipo: "agregar" });

    expect(variables(estado)).toEqual([[], ["Age", "Pregnancies", "BMI", "Glucose"], ["Outcome"], []]);
    expect(new Set(estado.niveles.map((n) => n.id)).size).toBe(4);
  });

  it("al eliminar un nivel sus fichas pasan al anterior (o al siguiente si era el primero)", () => {
    let estado = aplicar(inicial(), { tipo: "agregar", posicion: 1 });
    estado = aplicar(estado, { tipo: "mover", variable: "BMI", nivel: estado.niveles[1].id });

    const sinMedio = aplicar(estado, { tipo: "eliminar", nivel: estado.niveles[1].id });
    const sinPrimero = aplicar(estado, { tipo: "eliminar", nivel: estado.niveles[0].id });

    expect(variables(sinMedio)).toEqual([["Age", "Pregnancies", "Glucose", "BMI"], ["Outcome"]]);
    expect(variables(sinPrimero)).toEqual([["BMI", "Age", "Pregnancies", "Glucose"], ["Outcome"]]);
    expect(todas(sinPrimero)).toEqual(todas(estado));
  });

  it("no elimina el único nivel", () => {
    const estado = crearEstado([["a", "y"]]);

    expect(aplicar(estado, { tipo: "eliminar", nivel: estado.niveles[0].id })).toBe(estado);
  });

  it("renombra y reordena niveles; los nombres se envían si no son los de por defecto", () => {
    let estado = aplicar(inicial(), { tipo: "agregar", posicion: 0 });
    estado = aplicar(
      estado,
      { tipo: "renombrar", nivel: estado.niveles[0].id, nombre: "Demografía" },
      { tipo: "reordenar", desde: 2, hasta: 0 },
    );

    // Los nombres por defecto siguen la posición; el elegido por el usuario se conserva.
    expect(estado.niveles.map((n) => n.nombre)).toEqual(["Nivel 1", "Demografía", "Nivel 3"]);
    expect(variables(estado)).toEqual([["Outcome"], [], ["Age", "Pregnancies", "BMI", "Glucose"]]);
    expect(aConfiguracion(estado).nombres_niveles).toEqual(["Nivel 1", "Demografía", "Nivel 3"]);
    const soloPorDefecto = aplicar(inicial(), { tipo: "agregar", posicion: 0 }, { tipo: "reordenar", desde: 0, hasta: 2 });
    expect(soloPorDefecto.niveles.map((n) => n.nombre)).toEqual(["Nivel 1", "Nivel 2", "Nivel 3"]);
    expect(aConfiguracion(soloPorDefecto).nombres_niveles).toBeNull();
    expect(aplicar(estado, { tipo: "reordenar", desde: 0, hasta: 7 })).toBe(estado);
  });

  it("restablece a la plantilla", () => {
    let estado = aplicar(inicial(), { tipo: "agregar" }, { tipo: "renombrar", nivel: "n0", nombre: "X" });
    estado = aplicar(estado, { tipo: "restablecer", niveles: [["Age", "Pregnancies", "BMI", "Glucose"], ["Outcome"]] });

    expect(estado).toEqual(inicial());
  });

  it("usa los nombres guardados si coinciden con los niveles", () => {
    expect(crearEstado([["a"], ["y"]], ["Causas", "Efecto"]).niveles.map((n) => n.nombre)).toEqual(["Causas", "Efecto"]);
    expect(crearEstado([["a"], ["y"]], ["Solo uno"]).niveles.map((n) => n.nombre)).toEqual(["Nivel 1", "Nivel 2"]);
  });
});
