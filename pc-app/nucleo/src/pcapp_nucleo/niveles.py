"""Constantes sobre los niveles de las variables discretas, compartidas por PC y la prescripción."""

# Una ordinal con más niveles que esto se trata como numérica por su código: la prescripción la
# optimiza como continua, y la selección de prueba y PC (chisq) la discretizan en cuantiles.
MAXIMO_NIVELES_DISCRETOS = 10
