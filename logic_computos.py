"""logic_computos.py - Motor de cómputos métricos (Alcaldía de Brión).
Todas las medidas en metros, salvo lo indicado. Dosificaciones: manuales."""
import math

def n(x):
    try:
        return float(str(x).replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0

def _mat(dosif, base, desp=0.0):
    """dosif: {'cemento': (coef, 'sacos'), ...}  ->  totales = coef*base*(1+desp)"""
    return {k: (round(n(c) * base * (1 + desp / 100), 3), u) for k, (c, u) in dosif.items()}

def diam_mm(txt):
    """'3/8' o '1/2' = pulgadas; número solo = milímetros."""
    t = str(txt).replace('"', '').strip()
    if "/" in t:
        a, b = t.split("/")
        return n(a) / n(b) * 25.4
    return n(t)

def kg_m(d_mm):
    return d_mm ** 2 / 162.0

# ---------- Preliminares / tierra ----------
def limpieza(filas):
    return {"area_m2": round(sum(n(f["largo"]) * n(f["ancho"]) * (n(f.get("cant")) or 1) for f in filas), 3)}

def excavacion(filas):
    return {"vol_m3": round(sum(n(f["largo"]) * n(f["ancho"]) * n(f["prof"]) * (n(f.get("cant")) or 1) for f in filas), 3)}

def relleno(filas, esponj=0.0):
    v = excavacion(filas)["vol_m3"]
    return {"vol_compactado_m3": v, "vol_suelto_m3": round(v * (1 + n(esponj) / 100), 3)}

# ---------- Concreto ----------
def vol_elemento(e):
    N = n(e.get("cant")) or 1
    if n(e.get("diam")) > 0:                       # sección circular
        return math.pi * (n(e["diam"]) / 2) ** 2 * n(e["alto"]) * N
    return n(e["largo"]) * n(e["ancho"]) * n(e["alto"]) * N

def concreto(elementos, resistencia, dosif, desp=0.0):
    filas = [{**e, "total_m3": round(vol_elemento(e), 3)} for e in elementos]
    total = round(sum(f["total_m3"] for f in filas), 3)
    return {"titulo": f"Concreto de {resistencia} kg/cm²", "filas": filas,
            "total_m3": total, "materiales": _mat(dosif, total, desp)}

# ---------- Acero ----------
def acero(barras, estribos, desp=0.0, largo_comercial=12.0):
    por_diam = {}
    def sumar(d, metros):
        por_diam[d] = por_diam.get(d, 0.0) + metros
    filas = []
    for b in barras:
        m = n(b["long"]) * n(b["nbarras"]) * (n(b.get("cant")) or 1)
        sumar(b["diam"], m); filas.append({**b, "metros": round(m, 2)})
    for e in estribos:
        # long. estribo = perímetro + ganchos (m); cant = piso(largo/sep)+1 por elemento
        lest = 2 * (n(e["a"]) + n(e["b"])) + n(e.get("gancho", 0.10))
        q = (math.floor(n(e["largo"]) / n(e["sep"])) + 1) * (n(e.get("cant")) or 1)
        sumar(e["diam"], lest * q)
        filas.append({**e, "n_estribos": q, "long_estribo": round(lest, 3), "metros": round(lest * q, 2)})
    resumen = {}
    for d, m in por_diam.items():
        m *= 1 + n(desp) / 100
        resumen[d] = {"metros": round(m, 2), "kg": round(m * kg_m(diam_mm(d)), 2),
                      "barras_12m": math.ceil(m / largo_comercial)}
    return {"filas": filas, "por_diametro": resumen,
            "total_kg": round(sum(r["kg"] for r in resumen.values()), 2)}

# ---------- Albañilería ----------
def _area_neta(paredes, vanos):
    a = sum(n(p["largo"]) * n(p["alto"]) * (n(p.get("cant")) or 1) for p in paredes)
    v = sum(n(x["ancho"]) * n(x["alto"]) * (n(x.get("cant")) or 1) for x in vanos)
    return round(a, 3), round(v, 3), round(max(a - v, 0), 3)

def bloques(paredes, vanos, tipo, espesor_cm, rend_m2=12.5, dosif=None, desp=0.0):
    assert tipo in ("concreto", "arcilla") and int(espesor_cm) in (10, 12, 15)
    _, _, neta = _area_neta(paredes, vanos)
    return {"tipo": tipo, "espesor_cm": int(espesor_cm), "area_neta_m2": neta,
            "bloques": math.ceil(neta * n(rend_m2) * (1 + n(desp) / 100)),
            "materiales": _mat(dosif or {}, neta, desp)}

def friso(paredes, vanos, dosif, espesor_cm=1.5, caras=1, desp=0.0):
    _, _, neta = _area_neta(paredes, vanos)
    area = neta * (int(caras) or 1)
    return {"area_m2": round(area, 3), "espesor_cm": espesor_cm, "materiales": _mat(dosif, area, desp)}

# ---------- Acabados ----------
def piso(filas, pieza_a=None, pieza_b=None, dosif=None, desp=10.0):
    area = sum(n(f["largo"]) * n(f["ancho"]) * (n(f.get("cant")) or 1) for f in filas)
    a = area * (1 + n(desp) / 100)
    out = {"area_m2": round(area, 3), "area_con_desp_m2": round(a, 3), "materiales": _mat(dosif or {}, area)}
    if n(pieza_a) and n(pieza_b):
        out["piezas"] = math.ceil(a / (n(pieza_a) * n(pieza_b)))
    return out

def pintura(area_m2, manos, rend_m2_gal):
    return {"area_m2": n(area_m2), "manos": int(n(manos)),
            "galones": round(n(area_m2) * n(manos) / n(rend_m2_gal), 2)}

# ---------- Techos (láminas sobre correas) ----------
def techo(largo_horiz, ancho, pend_pct, lam_largo, lam_ancho_util, solape=0.15,
          sep_correas=1.0, tornillos_lam=8):
    cos = math.cos(math.atan(n(pend_pct) / 100))
    incl = n(largo_horiz) / cos                       # largo del faldón inclinado
    filas = math.ceil(n(ancho) / n(lam_ancho_util))
    por_fila = math.ceil(incl / (n(lam_largo) - n(solape)))
    lam = filas * por_fila
    lineas = math.floor(incl / n(sep_correas)) + 1
    return {"area_inclinada_m2": round(incl * n(ancho), 2), "laminas": lam,
            "correas_lineas": lineas, "correas_metros": round(lineas * n(ancho), 2),
            "correas_6m": math.ceil(lineas * n(ancho) / 6), "tornillos": lam * int(tornillos_lam)}

# ---------- Resumen general ----------
def resumen_general(*partidas_materiales):
    tot = {}
    for mats in partidas_materiales:
        for k, (c, u) in mats.items():
            t = tot.get(k, (0, u)); tot[k] = (round(t[0] + c, 3), u)
    return tot

if __name__ == "__main__":
    d = {"cemento": (8, "sacos"), "arena": (0.55, "m³"), "grava": (0.70, "m³")}
    r = concreto([{"elemento": "Columna", "largo": .3, "ancho": .3, "alto": 3, "cant": 10},
                  {"elemento": "Losa", "largo": 5, "ancho": 4, "alto": .12, "cant": 3}], 210, d)
    print(r["titulo"], r["total_m3"], r["materiales"])
    print(acero([{"diam": "3/8", "long": 3.2, "nbarras": 4, "cant": 10}],
                [{"diam": "1/4", "a": .2, "b": .2, "largo": 3, "sep": .15, "cant": 10}]))
    print(bloques([{"largo": 10, "alto": 2.6}], [{"ancho": 1, "alto": 2.1, "cant": 2}], "arcilla", 15))
    print(techo(6, 4, 15, 3.66, 0.86))
