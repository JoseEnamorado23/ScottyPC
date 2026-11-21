## Métodos del comparador evaluados en la verdad

323 casos de test que no cumplen el objetivo, μ = 0.001, mismas acciones, límites y costos para todos los métodos. El costo es el del prescriptor (suma de cambios ponderados por su costo, sin μ). La verdad es el do-operator del generador con el ruido de cada estudiante.

### Tal como los propone cada método

| Método | P verdadera media | Mejora verdadera media | **% que de verdad llega a 0,80** | Costo medio | Acciones por plan |
|---|---|---|---|---|---|
| Prescriptor causal | 0.755 | +16.1 pp | **42%** (135/323) | 0.869 | 1.74 |
| Sin causalidad (modelo de referencia) | 0.832 | +23.8 pp | **73%** (236/323) | 2.809 | 2.76 |
| Imitar a los casos exitosos | 0.752 | +15.7 pp | **47%** (151/323) | 1.003 | 3.26 |
| Intervención aleatoria | 0.797 | +20.3 pp | **59%** (191/323) | 2.519 | 4.42 |
| Sin intervención | 0.595 | +0.0 pp | **18%** (59/323) | 0.000 | 0.00 |

### A igual costo

Cada método se lleva, caso a caso, al costo del plan del prescriptor: se escala su cambio continuo (sin salirse de los límites) hacia arriba o abajo; los cambios discretos (tutorías, créditos, apoyo financiero) no se escalan: si por sí solos ya superan el presupuesto, se descartan primero los más caros. «Sin intervención» y el prescriptor no cambian.

| Método | P verdadera media | Mejora verdadera media | **% que de verdad llega a 0,80** | Costo medio | Acciones por plan |
|---|---|---|---|---|---|
| Prescriptor causal | 0.755 | +16.1 pp | **42%** (135/323) | 0.869 | 1.74 |
| Sin causalidad (modelo de referencia) | 0.728 | +13.3 pp | **28%** (90/323) | 0.701 | 2.11 |
| Imitar a los casos exitosos | 0.708 | +11.3 pp | **32%** (103/323) | 0.427 | 2.91 |
| Intervención aleatoria | 0.719 | +12.4 pp | **33%** (105/323) | 0.592 | 3.39 |
| Sin intervención | 0.595 | +0.0 pp | **18%** (59/323) | 0.000 | 0.00 |

Casos en que el costo quedó igualado al del prescriptor (±5 %; si no, los límites lo impiden o el método ya costaba menos y no se puede subir más): Imitar a los casos exitosos 72%, Intervención aleatoria 80%, Sin causalidad (modelo de referencia) 62%.
