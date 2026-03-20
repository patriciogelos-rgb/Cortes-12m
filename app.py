import streamlit as st
from collections import Counter
import itertools, csv, io
STOCK_LEN = 12.0
EPS = 1e-9

st.title("Optimizador cortes - Barras 12.0 m (local)")
st.markdown("Pegá aquí cada línea: largo (m), cantidad  — ejemplo: 1.57,20")

input_text = st.text_area("Entradas (largo,cantidad)", height=200, value="1.57,20\n8.60,15\n4.26,6\n3.27,20")
use_pulp = st.checkbox("Intentar solución óptima con PuLP (si está instalado)", value=True)
max_patterns = st.number_input("Máx patrones a generar (PuLP)", min_value=50, max_value=2000, value=500, step=50)

def parse_input(txt):
    dem = []
    for line in txt.strip().splitlines():
        if not line.strip(): continue
        parts = line.replace(';',',').split(',')
        try:
            l = float(parts[0].strip())
            q = int(float(parts[1].strip())) if len(parts)>1 else 1
            if l<=0 or q<=0: continue
            if l > STOCK_LEN + EPS:
                st.warning(f"Largo {l} > {STOCK_LEN} m (se ignora).")
                continue
            dem.append((round(l,6), q))
        except Exception:
            st.warning(f"Línea inválida: {line}")
    return dem

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
    
    # Ahora resumimos el total por largo
    total_bars = Counter()
    for length, quantity in cnt.items():
        total_bars[length] += quantity

    # Formateamos el resultado
    for L, q in sorted(total_bars.items()):
        out.write(f"  {L:.3f} m : {q}\n")  # Resumen de piezas
    
    out.write("\nPatrones (por barra):\n")
    bar_summary = Counter()  # Usaremos esto para resumir las barras cortadas

    # Generar detalle de patrones y contar repeticiones
    for i, c in enumerate(cuts, 1):
        cut_details = " + ".join(f"{x:.3f}" for x in c)
        out.write(f" {i:2d}: " + cut_details + f"  => total {sum(c):.3f} m, waste {STOCK_LEN - sum(c):.3f} m\n")
        bar_summary[tuple(c)] += 1  # Contar cada patrón

    out.write("\nResumen de cortado:\n")
    for cuts_pattern, count in bar_summary.items():
        cut_details = " + ".join(f"{x:.3f}" for x in cuts_pattern)
        out.write(f"  {cut_details}  x{count}\n")  # Mostrar patrón y su cantidad

    cnt = Counter()
    for c in cuts:
        for p in c:
            cnt[round(p,6)] += 1
    out.write("Piezas obtenidas (largo : cantidad):\n")
    for L, q in sorted(cnt.items()):
        out.write(f"  {L:.3f} m : {q}\n")
    out.write("\nPatrones (por barra):\n")
    for i, c in enumerate(cuts,1):
        out.write(f" {i:2d}: " + " + ".join(f"{x:.3f}" for x in c) + f"  => total {sum(c):.3f} m, waste {STOCK_LEN - sum(c):.3f} m\n")
>>>>>>> e9d5f6b7847ea9ae94c54fc88535513aa650c78c
    total_waste = sum(STOCK_LEN - sum(c) for c in cuts)
    out.write(f"\nDesperdicio total acumulado: {total_waste:.3f} m\n")
    return out.getvalue()

def export_csv_bytes(cuts):
    f = io.StringIO()
    writer = csv.writer(f)
    writer.writerow(['Barra','Cortes (m)','Total cortado (m)','Desperdicio (m)'])
    for i,c in enumerate(cuts,1):
        writer.writerow([i, ' + '.join(f"{x:.3f}" for x in c), f"{sum(c):.3f}", f"{STOCK_LEN - sum(c):.3f}"])
    return f.getvalue().encode('utf-8')

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
            # Eliminar la cantidad sobrante
            surplus = prod[p] - req.get(p, 0)
            # Descartar piezas hasta que la producción cumpla con la demanda
            for i in range(surplus):
                for cut in cuts:
                    if p in cut:  # Si la pieza está en la barra
                        cut.remove(p)
                        break  # Solo quitar una por iteración

    # Filtrar cortes vacíos
    cuts = [cut for cut in cuts if cut]
    return cuts

demand = parse_input(input_text)
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

    csv_bytes = export_csv_bytes(cuts_opt)
    st.download_button("Descargar CSV", data=csv_bytes, file_name="patrones_corte.csv", mime="text/csv")
