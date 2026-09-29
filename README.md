# Tarea 1: Escape de la Torre

Simulación de evacuación de un edificio en llamas, donde agentes deben alcanzar
la única salida disponible evitando el fuego y gestionando la congestión de
los pasillos, utilizando distintos paradigmas de búsqueda de Inteligencia
Artificial.

Se implementaron 5 algoritmos de navegación, todos intercambiables entre sí:

| Categoría | Algoritmo | Considera congestión |
|---|---|---|
| Búsqueda no informada | BFS (Breadth-First Search) | No |
| Búsqueda no informada | UCS (Uniform Cost Search / Dijkstra) | Sí |
| Búsqueda informada | A* (heurística Manhattan) | Sí |
| Búsqueda informada | Greedy Best-First Search (heurística Manhattan) | No |
| Optimización bioinspirada | Algoritmo Genético propio | Sí |

Y 3 mapas de prueba con distinta dificultad topológica:

- `cuello_de_botella`: pasillos angostos que convergen hacia la salida.
- `laberinto`: múltiples salas conectadas por puertas desalineadas.
- `abierto`: espacio semiabierto con obstáculos dispersos aleatoriamente.

## Requisitos

- Python 3.8 o superior.
- No requiere librerías externas (solo módulos de la librería estándar:
  `heapq`, `collections`, `random`, `statistics`, `csv`, `dataclasses`,
  `argparse`).

## Cómo ejecutar

### Demo visual (una simulación pequeña, imprime el mapa turno a turno)

```bash
python escape_torre.py --demo --algoritmo astar
```

El parámetro `--algoritmo` acepta: `bfs`, `ucs`, `astar`, `greedy`, `genetico`.

### Benchmark completo

Corre las 15 combinaciones (3 mapas × 5 algoritmos), repitiendo cada una
`--iteraciones` veces, y guarda los resultados en un CSV.

```bash
python escape_torre.py --benchmark --iteraciones 200 --agentes 150
```

Parámetros disponibles:

| Flag | Descripción | Valor por defecto |
|---|---|---|
| `--iteraciones` | Repeticiones por combinación mapa/algoritmo | 5 |
| `--agentes` | N° de agentes por simulación | 40 |
| `--tam-mapa` | Tamaño de la grilla (NxN) | 50 |
| `--salida-csv` | Archivo CSV de salida | `resultados_benchmark.csv` |

## Métricas reportadas

Por cada combinación mapa/algoritmo, el benchmark calcula:

- **Tasa de supervivencia**: porcentaje de agentes que evacuaron con éxito.
- **Estadísticos de los turnos** que demoró el último sobreviviente en
  evacuar: media, desviación estándar, mínimo y máximo.

Los resultados se guardan en el CSV indicado (por defecto
`resultados_benchmark.csv`), con una fila por combinación mapa/algoritmo.

## Uso de IA Generativa

Parte del código base de este proyecto (estructura general, algoritmos de
búsqueda y algoritmo genético) fue generado con asistencia de IA generativa
(Claude)
