"""
Este codigo fue asistido por herramientas de inteligencia artificial (Claude)
Estudiante: Camila García Torres
Matricula: 2024042033
"""
 
import argparse
import csv
import heapq
import random
import statistics
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set, Callable
 
Coord = Tuple[int, int]
 
# Movimientos ortogonales permitidos (arriba, abajo, izquierda, derecha)
MOVIMIENTOS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
# Incluye la accion de "esperar" (quedarse quieto), usada por el algoritmo genetico
MOVIMIENTOS_CON_ESPERA = MOVIMIENTOS + [(0, 0)]
 

# ==============================================================================
# 1. GENERACION DE MAPAS
# ==============================================================================
# Se implementan los 3 mapas pedidos en el enunciado. Cada generador retorna
# una grilla (lista de listas de caracteres: '.' = libre, '#' = muro) y la
# posicion de la salida.
 
# esto genera las paredes del mapa
def _agregar_muros_perimetrales(grid: List[List[str]]) -> None:
    filas, columnas = len(grid), len(grid[0])
    for c in range(columnas):
        grid[0][c] = '#'
        grid[filas - 1][c] = '#'
    for r in range(filas):
        grid[r][0] = '#'
        grid[r][columnas - 1] = '#'
 
#genera el mapa de cuello de botella 
def generar_mapa_cuello_botella(filas: int = 50, columnas: int = 50):
    """Mapa 1: alta densidad de obstaculos / cuello de botella.
    Un unico pasillo angosto conecta ambas mitades del edificio."""
    grid = [['.' for _ in range(columnas)] for _ in range(filas)]
    _agregar_muros_perimetrales(grid)
 
    muro_columna = columnas // 2
    hueco = filas // 2
    ancho_hueco = 2
    for r in range(1, filas - 1):
        if abs(r - hueco) > ancho_hueco // 2:
            grid[r][muro_columna] = '#'
 
    # Un segundo cuello de botella cerca de la salida para aumentar dificultad
    muro_columna_2 = int(columnas * 0.75)
    hueco_2 = filas // 3
    for r in range(1, filas - 1):
        if abs(r - hueco_2) > ancho_hueco // 2:
            grid[r][muro_columna_2] = '#'
 
    salida = (filas - 2, columnas - 2)
    grid[salida[0]][salida[1]] = '.'
    return grid, salida
 
 
def generar_mapa_laberinto(filas: int = 50, columnas: int = 50):
    """Mapa 2: densidad media / laberinto corporativo.
    Multiples salas conectadas por puertas (huecos) desalineadas."""
    grid = [['.' for _ in range(columnas)] for _ in range(filas)]
    _agregar_muros_perimetrales(grid)
 
    espacio_entre_muros = 7
    ancho_puerta = 4
    columnas_muro = list(range(espacio_entre_muros, columnas - 1, espacio_entre_muros))
    for idx, c in enumerate(columnas_muro):
        # Alterna la puerta entre la parte superior e inferior de la sala
        if idx % 2 == 0:
            centro_puerta = filas // 4
        else:
            centro_puerta = int(filas * 0.7)
        for r in range(1, filas - 1):
            if abs(r - centro_puerta) > ancho_puerta // 2:
                grid[r][c] = '#'
 
    salida = (filas - 2, columnas - 2)
    grid[salida[0]][salida[1]] = '.'
    return grid, salida
 
 
def generar_mapa_abierto(filas: int = 50, columnas: int = 50, densidad_obstaculos: float = 0.08):
    """Mapa 3: baja densidad / dispersion abierta.
    Espacio semiabierto con obstaculos dispersos aleatoriamente."""
    grid = [['.' for _ in range(columnas)] for _ in range(filas)]
    _agregar_muros_perimetrales(grid)
 
    for r in range(1, filas - 1):
        for c in range(1, columnas - 1):
            if random.random() < densidad_obstaculos:
                grid[r][c] = '#'
 
    salida = (filas - 2, columnas - 2)
    grid[salida[0]][salida[1]] = '.'
    return grid, salida
 
 
MAPAS_DISPONIBLES: Dict[str, Callable] = {
    "cuello_de_botella": generar_mapa_cuello_botella,
    "laberinto": generar_mapa_laberinto,
    "abierto": generar_mapa_abierto,
}
 
 
# ==============================================================================
# 2. CLASE ENTORNO (grilla, fuego, congestion)
# ==============================================================================
 
class Entorno:
    """Representa el estado dinamico del edificio: muros fijos, fuego,
    y ocupacion de cada celda (usada para calcular el costo de congestion)."""
 
    def __init__(self, grid: List[List[str]], salida: Coord,
                 prob_propagacion: float = 0.35, k_turnos_fuego: int = 4,
                 factor_congestion: float = 0.6):
        self.grid_original = grid
        self.filas = len(grid)
        self.columnas = len(grid[0])
        self.salida = salida
        self.prob_propagacion = prob_propagacion
        self.k_turnos_fuego = k_turnos_fuego
        self.factor_congestion = factor_congestion
 
        self.fuego: Set[Coord] = set()
        self.ocupacion: Dict[Coord, int] = defaultdict(int)
        self.turno = 0
 
        self._iniciar_fuego()
 
    def _iniciar_fuego(self) -> None:
        """El incendio comienza en una celda libre, alejada de la salida,
        elegida de forma aleatoria para introducir no-determinismo entre
        iteraciones (segun aclaracion del profesor)."""
        candidatas = []
        for r in range(1, self.filas - 1):
            for c in range(1, self.columnas - 1):
                pos = (r, c)
                if self.grid_original[r][c] != '#' and pos != self.salida:
                    dist = abs(r - self.salida[0]) + abs(c - self.salida[1])
                    if dist > (self.filas + self.columnas) // 3:
                        candidatas.append(pos)
        origen = random.choice(candidatas) if candidatas else (1, 1)
        self.fuego.add(origen)
 
    def es_transitable(self, pos: Coord) -> bool:
        r, c = pos
        if not (0 <= r < self.filas and 0 <= c < self.columnas):
            return False
        if self.grid_original[r][c] == '#':
            return False
        if pos in self.fuego:
            return False
        return True
 
    def costo_celda(self, pos: Coord) -> float:
        """Costo de atravesar una celda: base 1 + penalizacion CUADRATICA
        segun su nivel de ocupacion actual (congestion)."""
        ocupacion_actual = self.ocupacion.get(pos, 0)
        return 1.0 + self.factor_congestion * (ocupacion_actual ** 2)
 
    def vecinos(self, pos: Coord) -> List[Coord]:
        r, c = pos
        candidatos = [(r + dr, c + dc) for dr, dc in MOVIMIENTOS]
        return [p for p in candidatos if self.es_transitable(p)]
 
    def propagar_fuego(self) -> None:
        """Cada k_turnos_fuego, el fuego avanza a celdas adyacentes libres
        de forma PROBABILISTICA (no determinista)."""
        if self.turno % self.k_turnos_fuego != 0:
            return
        nuevas_celdas = set()
        for (r, c) in self.fuego:
            for dr, dc in MOVIMIENTOS:
                vecino = (r + dr, c + dc)
                if not (0 <= vecino[0] < self.filas and 0 <= vecino[1] < self.columnas):
                    continue
                if self.grid_original[vecino[0]][vecino[1]] == '#':
                    continue
                if vecino in self.fuego or vecino == self.salida:
                    continue
                if random.random() < self.prob_propagacion:
                    nuevas_celdas.add(vecino)
        self.fuego |= nuevas_celdas
 
    def avanzar_turno(self) -> None:
        self.turno += 1
        self.propagar_fuego()
 
    def celdas_alcanzables_desde_salida(self) -> Set[Coord]:
        """Calcula (via BFS puro) el conjunto de celdas libres desde las
        cuales existe un camino hasta la salida. Se usa para no generar
        agentes en zonas del mapa desconectadas de la salida."""
        visitados = {self.salida}
        cola = deque([self.salida])
        while cola:
            actual = cola.popleft()
            for vecino in self.vecinos(actual):
                if vecino not in visitados:
                    visitados.add(vecino)
                    cola.append(vecino)
        return visitados
 
 
# ==============================================================================
# 3. AGENTE
# ==============================================================================
 
@dataclass
class Agente:
    id: int
    pos: Coord
    vivo: bool = True
    evacuado: bool = False
    turno_evacuacion: int = -1
    ruta: List[Coord] = field(default_factory=list)
 
 
# ==============================================================================
# 4. FUNCIONES AUXILIARES DE BUSQUEDA
# ==============================================================================
 
def heuristica_manhattan(a: Coord, b: Coord) -> float:
    """Heuristica admisible: como el movimiento es ortogonal y el costo
    minimo por celda es 1, la distancia Manhattan nunca sobreestima el
    costo real restante hasta la meta."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
 
 
def _reconstruir_camino(padre: Dict[Coord, Coord], inicio: Coord, fin: Coord) -> List[Coord]:
    camino = []
    actual = fin
    while actual != inicio:
        camino.append(actual)
        actual = padre[actual]
    camino.reverse()
    return camino
 
 
# ==============================================================================
# 5. BUSQUEDA NO INFORMADA: BFS y UCS
# ==============================================================================
 
def bfs(entorno: Entorno, inicio: Coord, fin: Coord) -> Optional[List[Coord]]:
    """Breadth-First Search: minimiza el NUMERO DE PASOS, ignorando el
    costo de congestion."""
    if inicio == fin:
        return []
    visitados = {inicio}
    padre: Dict[Coord, Coord] = {}
    cola = deque([inicio])
    while cola:
        actual = cola.popleft()
        for vecino in entorno.vecinos(actual):
            if vecino not in visitados:
                visitados.add(vecino)
                padre[vecino] = actual
                if vecino == fin:
                    return _reconstruir_camino(padre, inicio, fin)
                cola.append(vecino)
    return None
 
 
def ucs(entorno: Entorno, inicio: Coord, fin: Coord) -> Optional[List[Coord]]:
    """Uniform Cost Search (Dijkstra): minimiza el COSTO ACUMULADO,
    tomando en cuenta la penalizacion por congestion de cada celda."""
    contador = 0  # desempata en el heap sin comparar tuplas de coordenadas
    frontera = [(0.0, contador, inicio)]
    costo_acumulado = {inicio: 0.0}
    padre: Dict[Coord, Coord] = {}
    visitados: Set[Coord] = set()
 
    while frontera:
        costo, _, actual = heapq.heappop(frontera)
        if actual in visitados:
            continue
        visitados.add(actual)
        if actual == fin:
            return _reconstruir_camino(padre, inicio, fin)
 
        for vecino in entorno.vecinos(actual):
            nuevo_costo = costo_acumulado[actual] + entorno.costo_celda(vecino)
            if vecino not in costo_acumulado or nuevo_costo < costo_acumulado[vecino]:
                costo_acumulado[vecino] = nuevo_costo
                padre[vecino] = actual
                contador += 1
                heapq.heappush(frontera, (nuevo_costo, contador, vecino))
    return None
 
 
# ==============================================================================
# 6. BUSQUEDA INFORMADA: A* y Greedy Best-First
# ==============================================================================
 
def a_estrella(entorno: Entorno, inicio: Coord, fin: Coord) -> Optional[List[Coord]]:
    """A*: combina el costo real acumulado (g) con la heuristica (h),
    garantizando optimalidad gracias a que h es admisible."""
    contador = 0
    frontera = [(heuristica_manhattan(inicio, fin), 0.0, contador, inicio)]
    costo_acumulado = {inicio: 0.0}
    padre: Dict[Coord, Coord] = {}
    visitados: Set[Coord] = set()
 
    while frontera:
        _, costo, _, actual = heapq.heappop(frontera)
        if actual in visitados:
            continue
        visitados.add(actual)
        if actual == fin:
            return _reconstruir_camino(padre, inicio, fin)
 
        for vecino in entorno.vecinos(actual):
            nuevo_costo = costo_acumulado[actual] + entorno.costo_celda(vecino)
            if vecino not in costo_acumulado or nuevo_costo < costo_acumulado[vecino]:
                costo_acumulado[vecino] = nuevo_costo
                prioridad = nuevo_costo + heuristica_manhattan(vecino, fin)
                padre[vecino] = actual
                contador += 1
                heapq.heappush(frontera, (prioridad, nuevo_costo, contador, vecino))
    return None
 
 
def greedy_best_first(entorno: Entorno, inicio: Coord, fin: Coord) -> Optional[List[Coord]]:
    """Greedy Best-First Search: se guia UNICAMENTE por la heuristica,
    por lo que es mas rapido que A* pero no garantiza el camino optimo."""
    contador = 0
    frontera = [(heuristica_manhattan(inicio, fin), contador, inicio)]
    padre: Dict[Coord, Coord] = {}
    visitados = {inicio}
 
    while frontera:
        _, _, actual = heapq.heappop(frontera)
        if actual == fin:
            return _reconstruir_camino(padre, inicio, fin)
        for vecino in entorno.vecinos(actual):
            if vecino not in visitados:
                visitados.add(vecino)
                padre[vecino] = actual
                contador += 1
                heapq.heappush(frontera, (heuristica_manhattan(vecino, fin), contador, vecino))
    return None
 
 
# ==============================================================================
# 7. OPTIMIZACION BIOINSPIRADA: ALGORITMO GENETICO
# ==============================================================================
# Cada individuo es una secuencia de movimientos (incluyendo "esperar").
# El algoritmo evoluciona una poblacion de rutas buscando minimizar la
# distancia final a la salida y el costo total (congestion) del camino.
 
def _simular_individuo(entorno: Entorno, inicio: Coord, individuo: List[Coord]) -> List[Coord]:
    pos = inicio
    camino = [pos]
    for mov in individuo:
        candidata = (pos[0] + mov[0], pos[1] + mov[1])
        if entorno.es_transitable(candidata):
            pos = candidata
        camino.append(pos)
        if pos == entorno.salida:
            break
    return camino
 
 
def _fitness_individuo(entorno: Entorno, inicio: Coord, individuo: List[Coord]) -> float:
    camino = _simular_individuo(entorno, inicio, individuo)
    pos_final = camino[-1]
    distancia_restante = heuristica_manhattan(pos_final, entorno.salida)
    costo_total = sum(entorno.costo_celda(p) for p in camino[1:])
    bono_llegada = 500.0 if pos_final == entorno.salida else 0.0
    # Se penaliza la distancia restante fuertemente, el costo de congestion
    # y levemente la longitud del camino (para preferir rutas mas cortas)
    return bono_llegada - distancia_restante * 15.0 - costo_total - len(camino) * 0.2
 
 
def _seleccion_torneo(poblacion: List[List[Coord]], puntajes: Dict[int, float], k: int = 5) -> List[Coord]:
    participantes = random.sample(range(len(poblacion)), min(k, len(poblacion)))
    mejor_idx = max(participantes, key=lambda i: puntajes[i])
    return poblacion[mejor_idx]
 
 
def _cruzar(padre1: List[Coord], padre2: List[Coord]) -> List[Coord]:
    if len(padre1) < 2:
        return padre1[:]
    punto = random.randint(1, len(padre1) - 1)
    return padre1[:punto] + padre2[punto:]
 
 
def _mutar(individuo: List[Coord], prob_mutacion: float = 0.08) -> List[Coord]:
    nuevo = individuo[:]
    for i in range(len(nuevo)):
        if random.random() < prob_mutacion:
            nuevo[i] = random.choice(MOVIMIENTOS_CON_ESPERA)
    return nuevo
 
 
def algoritmo_genetico(entorno: Entorno, inicio: Coord, fin: Coord,
                        tam_poblacion: int = 30, generaciones: int = 20) -> Optional[List[Coord]]:
    """Algoritmo genetico propio para planificar la ruta de un agente.
    Se re-ejecuta en cada replanificacion para adaptarse al entorno
    dinamico (fuego y congestion actuales)."""
    distancia_inicial = int(heuristica_manhattan(inicio, fin))
    longitud_individuo = max(6, min(distancia_inicial * 2 + 6, 80))
 
    poblacion = [
        [random.choice(MOVIMIENTOS_CON_ESPERA) for _ in range(longitud_individuo)]
        for _ in range(tam_poblacion)
    ]
 
    mejor_individuo = poblacion[0]
    mejor_fitness = float('-inf')
 
    for _ in range(generaciones):
        puntajes = {i: _fitness_individuo(entorno, inicio, ind) for i, ind in enumerate(poblacion)}
        orden = sorted(puntajes, key=lambda i: puntajes[i], reverse=True)
 
        if puntajes[orden[0]] > mejor_fitness:
            mejor_fitness = puntajes[orden[0]]
            mejor_individuo = poblacion[orden[0]]
 
        n_elite = max(2, tam_poblacion // 10)
        nueva_poblacion = [poblacion[i] for i in orden[:n_elite]]
 
        while len(nueva_poblacion) < tam_poblacion:
            padre1 = _seleccion_torneo(poblacion, puntajes)
            padre2 = _seleccion_torneo(poblacion, puntajes)
            hijo = _mutar(_cruzar(padre1, padre2))
            nueva_poblacion.append(hijo)
 
        poblacion = nueva_poblacion
 
    camino = _simular_individuo(entorno, inicio, mejor_individuo)
    ruta = camino[1:]
    return ruta if ruta else None
 
 
# ==============================================================================
# 8. VISUALIZACION SIMPLE EN CONSOLA (interfaz opcional/minima)
# ==============================================================================
 
def imprimir_mapa(entorno: Entorno, agentes: List[Agente]) -> None:
    posiciones_agentes = {a.pos for a in agentes if a.vivo and not a.evacuado}
    for r in range(entorno.filas):
        fila_str = []
        for c in range(entorno.columnas):
            pos = (r, c)
            if pos == entorno.salida:
                fila_str.append('S')
            elif pos in entorno.fuego:
                fila_str.append('*')
            elif pos in posiciones_agentes:
                fila_str.append('A')
            elif entorno.grid_original[r][c] == '#':
                fila_str.append('#')
            else:
                fila_str.append('.')
        print(''.join(fila_str))
 
 
# ==============================================================================
# 9. SIMULADOR (motor de una corrida)
# ==============================================================================
 
ALGORITMOS_DISPONIBLES: Dict[str, Callable] = {
    "bfs": bfs,
    "ucs": ucs,
    "astar": a_estrella,
    "greedy": greedy_best_first,
    "genetico": algoritmo_genetico,
}
 
# El algoritmo genetico es mucho mas costoso computacionalmente, asi que
# replanifica con menor frecuencia para mantener tiempos de ejecucion razonables.
INTERVALO_REPLAN_POR_ALGORITMO = {
    "bfs": 5,
    "ucs": 5,
    "astar": 5,
    "greedy": 5,
    "genetico": 10,
}
 
 
class Simulador:
    """Ejecuta una unica simulacion de evacuacion: crea los agentes,
    los mueve turno a turno de forma SIMULTANEA, gestiona la propagacion
    del fuego y calcula las metricas finales."""
 
    def __init__(self, entorno: Entorno, num_agentes: int, algoritmo: str,
                 max_turnos: int = 400):
        if algoritmo not in ALGORITMOS_DISPONIBLES:
            raise ValueError(f"Algoritmo desconocido: {algoritmo}")
        self.entorno = entorno
        self.algoritmo = algoritmo
        self.funcion_busqueda = ALGORITMOS_DISPONIBLES[algoritmo]
        self.max_turnos = max_turnos
        self.intervalo_replan = INTERVALO_REPLAN_POR_ALGORITMO[algoritmo]
        self.agentes = self._crear_agentes(num_agentes)
 
    def _crear_agentes(self, num_agentes: int) -> List[Agente]:
        alcanzables = self.entorno.celdas_alcanzables_desde_salida()
        posiciones_libres = [p for p in alcanzables if p != self.entorno.salida]
        random.shuffle(posiciones_libres)
        n = min(num_agentes, len(posiciones_libres))
        return [Agente(id=i, pos=posiciones_libres[i]) for i in range(n)]
 
    def _replanificar(self, agente: Agente) -> None:
        nueva_ruta = self.funcion_busqueda(self.entorno, agente.pos, self.entorno.salida)
        agente.ruta = nueva_ruta if nueva_ruta else []
 
    def ejecutar(self, verbose: bool = False) -> Dict[str, float]:
        for agente in self.agentes:
            self._replanificar(agente)
 
        turno = 0
        ultimo_turno_evacuacion = 0
 
        while turno < self.max_turnos:
            activos = [a for a in self.agentes if a.vivo and not a.evacuado]
            if not activos:
                break
            turno += 1
 
            # --- Fase 1: cada agente decide su proxima celda deseada ---
            destinos: Dict[int, Coord] = {}
            for agente in activos:
                if not agente.ruta:
                    self._replanificar(agente)
                if agente.ruta and not self.entorno.es_transitable(agente.ruta[0]):
                    # El fuego bloqueo la ruta planeada: hay que replanificar
                    self._replanificar(agente)
                destinos[agente.id] = agente.ruta[0] if agente.ruta else agente.pos
 
            # --- Fase 2: TODOS los agentes se mueven de forma simultanea ---
            for agente in activos:
                siguiente = destinos[agente.id]
                if agente.ruta and siguiente == agente.ruta[0]:
                    agente.ruta.pop(0)
                agente.pos = siguiente
 
            # --- Fase 3: recalcular ocupacion de celdas (para el costo futuro) ---
            self.entorno.ocupacion = defaultdict(int)
            for agente in activos:
                if agente.pos != self.entorno.salida:
                    self.entorno.ocupacion[agente.pos] += 1
 
            # --- Fase 4: replanificacion periodica (reaccion a la congestion) ---
            if turno % self.intervalo_replan == 0:
                for agente in activos:
                    if agente.pos != self.entorno.salida:
                        self._replanificar(agente)
 
            # --- Fase 5: revisar bajas por fuego ---
            for agente in activos:
                if agente.pos in self.entorno.fuego:
                    agente.vivo = False
 
            # --- Fase 6: revisar evacuaciones exitosas ---
            for agente in activos:
                if agente.vivo and agente.pos == self.entorno.salida:
                    agente.evacuado = True
                    agente.turno_evacuacion = turno
                    ultimo_turno_evacuacion = max(ultimo_turno_evacuacion, turno)
 
            # --- Fase 7: el entorno avanza (propagacion del fuego) ---
            self.entorno.avanzar_turno()
 
            if verbose:
                print(f"\n--- Turno {turno} (fuego: {len(self.entorno.fuego)} celdas) ---")
                imprimir_mapa(self.entorno, self.agentes)
 
        total = len(self.agentes)
        sobrevivientes = sum(1 for a in self.agentes if a.evacuado)
        return {
            "tasa_supervivencia": sobrevivientes / total if total else 0.0,
            "turnos_ultimo_sobreviviente": ultimo_turno_evacuacion,
            "sobrevivientes": sobrevivientes,
            "total_agentes": total,
        }
 
 
# ==============================================================================
# 10. MOTOR DE BENCHMARKING
# ==============================================================================
 
def ejecutar_benchmark(mapas: Dict[str, Callable], algoritmos: List[str],
                        num_iteraciones: int, num_agentes: int,
                        tam_mapa: int = 50) -> List[Dict]:
    """Ejecuta cada combinacion (mapa, algoritmo) 'num_iteraciones' veces,
    tal como exige el enunciado (min. 80, ideal 200), y calcula las
    metricas obligatorias: tasa de supervivencia y estadisticos de los
    turnos que demoro el ultimo sobreviviente en evacuar."""
    resultados = []
 
    for nombre_mapa, generador in mapas.items():
        for algoritmo in algoritmos:
            tasas_supervivencia = []
            turnos_totales = []
 
            for iteracion in range(num_iteraciones):
                grid, salida = generador(tam_mapa, tam_mapa)
                entorno = Entorno(grid, salida)
                simulador = Simulador(entorno, num_agentes, algoritmo)
                metricas = simulador.ejecutar()
 
                tasas_supervivencia.append(metricas["tasa_supervivencia"])
                turnos_totales.append(metricas["turnos_ultimo_sobreviviente"])
 
            resultados.append({
                "mapa": nombre_mapa,
                "algoritmo": algoritmo,
                "iteraciones": num_iteraciones,
                "tasa_supervivencia_media": statistics.mean(tasas_supervivencia),
                "turnos_media": statistics.mean(turnos_totales),
                "turnos_desviacion": statistics.stdev(turnos_totales) if len(turnos_totales) > 1 else 0.0,
                "turnos_min": min(turnos_totales),
                "turnos_max": max(turnos_totales),
            })
            print(f"[OK] mapa={nombre_mapa:18s} algoritmo={algoritmo:10s} "
                  f"supervivencia={resultados[-1]['tasa_supervivencia_media']*100:5.1f}%  "
                  f"turnos(media)={resultados[-1]['turnos_media']:6.1f}")
 
    return resultados
 
 
def guardar_resultados_csv(resultados: List[Dict], ruta_archivo: str = "resultados_benchmark.csv") -> None:
    if not resultados:
        return
    with open(ruta_archivo, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(resultados[0].keys()))
        escritor.writeheader()
        escritor.writerows(resultados)
    print(f"\nResultados guardados en: {ruta_archivo}")
 
 
# ==============================================================================
# 11. FUNCION PRINCIPAL / CLI
# ==============================================================================
 
def ejecutar_demo(algoritmo: str = "astar", num_agentes: int = 15, tam_mapa: int = 30) -> None:
    """Corre una unica simulacion pequena mostrando el mapa turno a turno,
    util para verificar visualmente el comportamiento de un algoritmo."""
    print(f"Demo con algoritmo='{algoritmo}', {num_agentes} agentes, mapa {tam_mapa}x{tam_mapa}\n")
    grid, salida = generar_mapa_cuello_botella(tam_mapa, tam_mapa)
    entorno = Entorno(grid, salida)
    simulador = Simulador(entorno, num_agentes, algoritmo, max_turnos=60)
    metricas = simulador.ejecutar(verbose=True)
    print("\n=== RESULTADO FINAL ===")
    print(f"Tasa de supervivencia: {metricas['tasa_supervivencia']*100:.1f}%")
    print(f"Turnos del ultimo sobreviviente: {metricas['turnos_ultimo_sobreviviente']}")
 
 
def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de evacuacion - Tarea 1 IA")
    parser.add_argument("--demo", action="store_true", help="Corre una simulacion visual pequena")
    parser.add_argument("--benchmark", action="store_true", help="Corre el benchmark completo")
    parser.add_argument("--algoritmo", default="astar", choices=list(ALGORITMOS_DISPONIBLES.keys()),
                         help="Algoritmo a usar en --demo")
    parser.add_argument("--iteraciones", type=int, default=5,
                         help="Iteraciones por combinacion mapa/algoritmo (el enunciado pide 200; "
                              "usar un valor bajo aqui solo para pruebas rapidas)")
    parser.add_argument("--agentes", type=int, default=40,
                         help="Numero de agentes por simulacion (el enunciado sugiere 80-300)")
    parser.add_argument("--tam-mapa", type=int, default=50, help="Tamano del mapa (NxN)")
    parser.add_argument("--salida-csv", default="resultados_benchmark.csv",
                         help="Archivo CSV donde guardar los resultados del benchmark")
    args = parser.parse_args()
 
    if args.demo:
        ejecutar_demo(algoritmo=args.algoritmo, num_agentes=min(args.agentes, 20),
                      tam_mapa=min(args.tam_mapa, 30))
        return
 
    if args.benchmark:
        print("Ejecutando benchmark (esto puede tardar varios minutos, especialmente 'genetico')...\n")
        algoritmos = list(ALGORITMOS_DISPONIBLES.keys())
        resultados = ejecutar_benchmark(
            mapas=MAPAS_DISPONIBLES,
            algoritmos=algoritmos,
            num_iteraciones=args.iteraciones,
            num_agentes=args.agentes,
            tam_mapa=args.tam_mapa,
        )
        guardar_resultados_csv(resultados, args.salida_csv)
        return
 
    print("No se especifico ninguna accion. Usa --demo o --benchmark (ver --help).")
 
 
if __name__ == "__main__":
    main()
 