# Datasets de prueba

Datasets para comprobar manualmente el comportamiento del núcleo (`nucleo`) con datos
reales y sintéticos. No forman parte del código del paquete.

- La prueba `test_datasets_reales_se_revisan_sin_errores` carga y revisa automáticamente
  todos los CSV y XLSX de esta carpeta. Solo comprueba que no fallen, que el DataFrame no
  se modifique y que el informe se pueda serializar a JSON. No exige hallazgos concretos.
- La CLI guarda aquí los informes `<nombre>_revision.json`. Un informe existente nunca se
  sobrescribe: se crea `<nombre>_revision_2.json`, `_3`, etc.

## Ejecución

Desde la raíz del repositorio (`pc-app/`), con el paquete instalado:

```bash
python -m nucleo revisar datasets_prueba/dataset_prueba.csv --objetivo objetivo
```

Para XLSX con varias hojas, indique la hoja con `--hoja <nombre>`.

## Dataset sintético

| Archivo | Objetivo | Detectores que ejercita |
|---|---|---|
| `dataset_prueba.csv` | `objetivo` (binario, ≈11 % «si») | Filas duplicadas, faltantes reales y centinela (`?`), posible identificador (`id`), texto libre (`observacion`), fecha como texto (`fecha`), categórica y ordinal (`nivel`), variable derivada (`ancho = maximo - minimo`), correlación casi perfecta / transformación lineal (`altura`, `altura_m`), distribución del objetivo y desbalance. También produce una advertencia de ceros sospechosos en `minimo` (tiene ceros legítimos entre 40 valores distintos). |

Se genera con `construir_dataset_prueba()` de `nucleo/tests/datos_sinteticos.py` (semilla
fija). La prueba end-to-end de la CLI usa la misma función.

## Datasets reales

| Archivo | Objetivo sugerido | Qué permite comprobar |
|---|---|---|
| `Dengue Dataset 2023-2025.xlsx` | `Outcome` (multiclase) | Binaria derivada real (`Platelet_Risk = 0 si Platelete >= 100000`), recodificación uno a uno, correlación casi perfecta, posibles mezclas de unidades, ceros sospechosos y categóricas. |
| `fetal_health.csv` | `fetal_health` (multiclase) | Filas duplicadas, ceros sospechosos, casi constantes, variable derivada y ausencia de falsos positivos de binaria derivada con clases muy desbalanceadas (`severe_decelerations`). |
| `MASTER_CHART_F1000Research.xlsx` | `GROUPS: DENGUE FEVER OR COMPLICATED DENGUE ` (binario) | Faltantes, filas duplicadas, casi constantes y nombres de columna con espacios al final (advertencia de validación). |
| `winequality-red.csv` | `quality` (multiclase) | Detección del separador `;`, filas duplicadas, objetivo ordinal entero. |
| `winequality-white.csv` | `quality` (multiclase) | Igual que el anterior, con más filas (4 898). |
| `xAPI-Edu-Data.csv` | `Class` (multiclase: L/M/H) | Muchas variables categóricas de texto y ceros sospechosos en conteos. |

Notas:

- En `MASTER_CHART_F1000Research.xlsx` el nombre del objetivo termina en un espacio: debe
  escribirse entre comillas e incluir ese espacio:
  `--objetivo "GROUPS: DENGUE FEVER OR COMPLICATED DENGUE "`.
- Limitación conocida: la columna `Date` del dataset de dengue usa el formato `dd.mm.yy`
  (`01.01.23`), que el detector de fechas todavía no reconoce, por lo que no se informa
  como `posible_fecha`.
