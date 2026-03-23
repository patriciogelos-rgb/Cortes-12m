import streamlit as st
from collections import Counter
import itertools, csv, io
STOCK_LEN = 12.0
EPS = 1e-9

st.title("Optimizador cortes - Barras 12.0 m (local)")
st.markdown("Pegá aquí cada línea: largo (m), cantidad  — ejemplo: 10*1.50")

input_text = st.text_area("Entradas (cantidadlargo) por línea — ejemplo: 10*1.5", height=200, value="10*1.5\n10*1.20")
use_pulp = st.checkbox("Intentar solución óptima con PuLP (si está instalado)", value=True)
max_patterns = st.number_input("Máx patrones a generar (PuLP)", min_value=100, max_value=10000, value=3000, step=100)

def parse_input(txt):
    dem = []
    for line in txt.strip().splitlines():
        if not line.strip(): 
            continue
        s = line.strip()
        # permitir separador '' formato: cantidadlargo (ej. 102.5)
        try:
            if '' in s:
                parts = s.split('*')
                q = int(float(parts[0].strip()))
                l = float(parts[1].strip())
            else:
                # aceptar también formato antiguo: largo,cantidad o largo;cantidad
                parts = s.replace(';',',').split(',')
                l = float(parts[0].strip())
                q = int(float(parts[1].strip())) if len(parts) > 1 else 1
            if l <= 0 or q <= 0:
                st.warning(f"Línea ignorada (valores no válidos): {line}")
                continue
            if l > STOCK_LEN + EPS:
                st.warning(f"Largo {l} > {STOCK_LEN} m (se ignora).")
                continue
            dem.append((round(l,6), q))
        except Exception:
            st.warning(f"Línea inválida: {line}")
    return dem

def aggregate_demand(demand):
    from collections import Counter
    cnt = Counter()
    for L, q in demand:
        cnt[round(L,6)] += int(q)
    return sorted([(L, cnt[L]) for L in cnt])

def ffd_solution(demand, stock_len=STOCK_LEN):
    pieces = []
    for L, q in demand:
        pieces += [L]*q
    pieces.sort(reverse=True)
    bins = []
    cuts = []
    for p in pieces:
        placed = False
        for i, rem in enumerate(bins):
            if rem + EPS >= p:
                bins[i] -= p
                cuts[i].append(p)
                placed = True
                break
        if not placed:
            bins.append(stock_len - p)
            cuts.append([p])
    total_waste = sum(bins)
    return cuts, total_waste

def pulp_optimize(demand, stock_len=STOCK_LEN, max_patterns=500):
    try:
        import pulp
    except Exception:
        return None, None, "PuLP no instalado"
    types = [(i, L, q) for i, (L, q) in enumerate(demand)]
    max_per_type = [int(stock_len // L) for (_, L, _) in types]
    patterns = []
    ranges = [range(0, m+1) for m in max_per_type]
    for comb in itertools.product(*ranges):
        total_len = sum(comb[i]*types[i][1] for i in range(len(types)))
        if total_len <= stock_len + EPS and sum(comb) > 0:
            patterns.append(tuple(comb))
        if len(patterns) >= max_patterns:
            break
    if not patterns:
        return None, None, "No hay patrones generados"
    prob = pulp.LpProblem('cutting_stock', pulp.LpMinimize)
    x = [pulp.LpVariable(f'x_{j}', lowBound=0, cat='Integer') for j in range(len(patterns))]
    prob += pulp.lpSum(x[j] for j in range(len(patterns)))
    for i, (_, L, q) in enumerate(types):
        prob += pulp.lpSum(patterns[j][i]*x[j] for j in range(len(patterns))) >= q
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    status = pulp.LpStatus[prob.status]
    if status not in ('Optimal','Integer Feasible'):
        return None, None, f"Estado: {status}"
    used = {patterns[j]: int(pulp.value(x[j])) for j in range(len(patterns)) if pulp.value(x[j]) >= 0.5}
    cuts = []
    for patt, cnt in used.items():
        for _ in range(cnt):
            bar_cuts = []
            for ii, num in enumerate(patt):
                bar_cuts += [types[ii][1]]*num
            cuts.append(bar_cuts)
    waste = sum(stock_len - sum(bar) for bar in cuts)
    return cuts, waste, "OK"

def summarize_text(cuts, waste):
    out = io.StringIO()
    out.write(f"Barras usadas: {len(cuts)}\n")
    out.write(f"Desperdicio total: {waste:.3f} m  (media: {waste/len(cuts):.3f} m)\n\n")
    
    # Contar piezas obtenidas
    cnt = Counter()
    for c in cuts:
        for p in c:
            cnt[round(p, 6)] += 1
            
    out.write("Piezas obtenidas (largo : cantidad):\n")
    
    # Resumir el total por largo
    for L, q in sorted(cnt.items()):
        out.write(f"  {L:.3f} m : {q}\n")
    
    out.write("\nPatrones (por barra):\n")
    bar_summary = Counter()  # Usar esta estructura para contar patrones

    # Generar detalle de patrones y contar repeticiones
    for c in cuts:
        cut_details = " + ".join(f"{x:.3f}" for x in c)
        bar_summary[cut_details] += 1  # Contar patrones

     # Resumir los patrones únicos con desperdicio por barra (formato: patrón  xN  Waste Y.YY m)
    for pattern, count in bar_summary.items():
        pieces = [float(x) for x in pattern.split(' + ')]
        waste_per_bar = STOCK_LEN - sum(pieces)
        waste_str = f"{waste_per_bar:.2f}"
        out.write(f"  {' + '.join(f'{p:.3f}' for p in pieces)}  x{count}  Waste {waste_str} m\n")

    # Calcular desperdicio total acumulado
    total_waste = sum(STOCK_LEN - sum(c) for c in cuts)
    out.write(f"\nDesperdicio total acumulado: {total_waste:.3f} m\n")

    return out.getvalue()

def export_csv_bytes(cuts, waste):
    f = io.StringIO()
    writer = csv.writer(f)

    # Encabezados generales
    writer.writerow(['Resumen de Cortes'])
    writer.writerow(['Barras usadas', len(cuts)])
    writer.writerow(['Desperdicio total (m)', waste])
    writer.writerow([])
    
    # Piezas obtenidas
    writer.writerow(['Piezas obtenidas (largo : cantidad):'])
    cnt = Counter()
    for c in cuts:
        for p in c:
            cnt[round(p, 6)] += 1
            
    for L, q in sorted(cnt.items()):
        writer.writerow([f"{L:.3f} m", q])
    
    writer.writerow([])
    writer.writerow(['Patrones (por barra):'])
    
    bar_summary = Counter()
    for i, c in enumerate(cuts, 1):
        cut_details = " + ".join(f"{x:.3f}" for x in c)
        writer.writerow([f"{i}", cut_details, f"Total {sum(c):.3f} m", f"Waste {STOCK_LEN - sum(c):.3f} m"])
        
        # Contar patrones
        bar_summary[tuple(c)] += 1
    
    writer.writerow([])
    writer.writerow(['Resumen de cortado:'])
    for cuts_pattern, count in bar_summary.items():
       cut_details = " + ".join(f"{x:.3f}" for x in cuts_pattern)
       # calcular desperdicio por barra para este patrón
       waste_per_bar = STOCK_LEN - sum(cuts_pattern)
       writer.writerow([f"{cut_details}", f"x{count}", f"Waste {waste_per_bar:.2f} m"])


    return f.getvalue().encode('utf-8')

# Función para ajustar cortes a la demanda
def trim_cuts_to_demand(cuts, demand):
    from collections import Counter
    # Contar la producción actual
    prod = Counter()
    for c in cuts:
        for p in c:
            prod[round(p, 6)] += 1

    # Crear un dict de demanda
    req = {round(L, 6): q for (L, q) in demand}
    
    # Eliminar piezas sobrantes
    for p in list(prod.keys()):
        if prod[p] > req.get(p, 0):
            surplus = prod[p] - req.get(p, 0)
            for _ in range(surplus):
                # Intentamos eliminar la primera aparición de la pieza
                for cut in cuts:
                    if p in cut:
                        cut.remove(p)
                        break  # Solo quita una por iteración

    # Filtrar cortes vacíos
    cuts = [cut for cut in cuts if cut]
    return cuts

demand_raw = parse_input(input_text)
demand = aggregate_demand(demand_raw)
def aggregate_demand(demand):
    from collections import Counter
    cnt = Counter()
    for L, q in demand:
        cnt[round(L,6)] += int(q)
    return sorted([(L, cnt[L]) for L in cnt])
if not demand:
    st.error("No hay entradas válidas.")
    st.stop()

st.write("Demanda:")
for L,q in demand:
    st.write(f" - {q} × {L} m")

if st.button("Calcular patrones"):
    cuts_opt = None
    waste_opt = None
    msg = ""
    if use_pulp:
        cuts_opt, waste_opt, msg = pulp_optimize(demand, STOCK_LEN, max_patterns)
        if cuts_opt is None:
            st.info(f"PuLP no disponible/óptimo: {msg}. Usando heurística FFD.")
    if cuts_opt is None:
        cuts_opt, waste_opt = ffd_solution(demand, STOCK_LEN)
        method = "Heurística FFD"
    else:
        method = "PuLP (óptimo)"
    st.subheader(f"Resultado ({method})")
    cuts_trimmed = trim_cuts_to_demand(cuts_opt, demand)
    waste_trimmed = sum(STOCK_LEN - sum(c) for c in cuts_trimmed)
    st.text(summarize_text(cuts_trimmed, waste_trimmed))
    csv_bytes = export_csv_bytes(cuts_trimmed, waste_trimmed)
    st.download_button("Descargar CSV", data=csv_bytes, file_name="patrones_corte.csv", mime="text/csv")
