import os, json, uuid
from flask import Flask, render_template, request, send_file, redirect, url_for

import logic_computos as lc
from logic_computos_word import generar_word

app = Flask(__name__)
CARPETA = "descargas"
os.makedirs(CARPETA, exist_ok=True)


def _rows(nombre):
    """Lee un campo hidden con JSON (lista de dicts) enviado por el formulario."""
    raw = request.form.get(nombre, "[]")
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []


def _f(nombre, default=0):
    v = request.form.get(nombre, "")
    return v if v not in (None, "",) else default


def _num(x, default=0.0):
    """Convierte a float aceptando coma decimal."""
    try:
        return float(str(x).replace(",", ".").strip() or default)
    except ValueError:
        return float(default)


@app.route("/")
def index():
    return render_template("computos_form.html")


@app.route("/generar", methods=["POST"])
def generar():
    f = request.form
    secciones = []

    # ---------- Preliminares ----------
    filas_limp = _rows("limpieza_filas")
    if filas_limp:
        r = lc.limpieza(filas_limp)
        secciones.append({"titulo": "Limpieza y Replanteo",
            "cols": ["Largo (m)", "Ancho (m)", "Cant."],
            "filas": [[x.get("largo"), x.get("ancho"), x.get("cant") or 1] for x in filas_limp],
            "pie": ["TOTAL", "", r["area_m2"]]})

    filas_exc = _rows("excavacion_filas")
    if filas_exc:
        r = lc.excavacion(filas_exc)
        secciones.append({"titulo": "Excavación",
            "cols": ["Largo (m)", "Ancho (m)", "Prof. (m)", "Cant."],
            "filas": [[x.get("largo"), x.get("ancho"), x.get("prof"), x.get("cant") or 1] for x in filas_exc],
            "pie": ["TOTAL", "", "", r["vol_m3"]]})
        esponj = _f("relleno_esponj", 0)
        if float(esponj or 0) > 0:
            rr = lc.relleno(filas_exc, esponj)
            secciones.append({"titulo": "Relleno Compactado", "cols": ["Concepto", "Volumen (m³)"],
                "filas": [["Volumen compactado", rr["vol_compactado_m3"]],
                          ["Volumen suelto (esponjado)", rr["vol_suelto_m3"]]], "pie": None})

    # ---------- Concreto ----------
    elementos = _rows("concreto_elementos")
    if elementos:
        resistencia = _f("concreto_resistencia", "210")
        dosif = {"Cemento": (_f("concreto_cemento", 0), "sacos"),
                 "Arena": (_f("concreto_arena", 0), "m³"),
                 "Grava": (_f("concreto_grava", 0), "m³"),
                 "Agua": (_f("concreto_agua", 0), "L")}
        desp = float(_f("concreto_desperdicio", 0) or 0)
        r = lc.concreto(elementos, resistencia, dosif, desp)
        secciones.append({"titulo": r["titulo"],
            "cols": ["Elemento", "Largo", "Ancho", "Alto", "Diám.", "Cant.", "Total m³"],
            "filas": [[e.get("elemento", "-"), e.get("largo", "-"), e.get("ancho", "-"), e.get("alto", "-"),
                       e.get("diam", "-"), e.get("cant") or 1, e["total_m3"]] for e in r["filas"]],
            "pie": ["TOTAL", "", "", "", "", "", r["total_m3"]]})
        mats = [[k, u, v] for k, (v, u) in r["materiales"].items() if v]
        if mats:
            secciones.append({"titulo": f"Materiales — Concreto {resistencia} kg/cm²",
                "cols": ["Material", "Unidad", "Cantidad"], "filas": mats, "pie": None})

    # ---------- Acero ----------
    barras = _rows("acero_barras")
    estribos = _rows("acero_estribos")
    if barras or estribos:
        desp = float(_f("acero_desperdicio", 0) or 0)
        r = lc.acero(barras, estribos, desp)
        filas_a = [["Barra", b.get("diam"), b.get("long"), b.get("nbarras"), b.get("cant") or 1, "-", "-", b["metros"]]
                   for b in r["filas"] if "n_estribos" not in b]
        filas_a += [["Estribo", e.get("diam"), e.get("largo"), "-", e.get("cant") or 1,
                     e["n_estribos"], e["long_estribo"], e["metros"]] for e in r["filas"] if "n_estribos" in e]
        secciones.append({"titulo": "Acero de Refuerzo",
            "cols": ["Tipo", "Diám.", "Long./Largo", "N° barras", "Cant. elem.", "N° estribos", "Long. c/u", "Total m"],
            "filas": filas_a, "pie": None})
        resumen = [[d, v["metros"], v["kg"], v["barras_6m"]] for d, v in r["por_diametro"].items()]
        resumen.append(["TOTAL", "", r["total_kg"], ""])
        secciones.append({"titulo": "Resumen de Acero por Diámetro",
            "cols": ["Diámetro", "Metros", "Kg", "Barras de 6 m"], "filas": resumen, "pie": None})

    # ---------- Bloques ----------
    paredes_b = _rows("bloques_paredes")
    if paredes_b:
        vanos_b = _rows("bloques_vanos")
        tipo = _f("bloques_tipo", "concreto")
        esp = _f("bloques_espesor", "15")
        rend = _f("bloques_rendimiento", 12.5)
        dosif = {"Cemento": (_f("bloques_cemento", 0), "sacos"), "Arena": (_f("bloques_arena", 0), "m³")}
        r = lc.bloques(paredes_b, vanos_b, tipo, esp, rend, dosif)
        secciones.append({"titulo": f"Pega de Bloques de {tipo.capitalize()} ({esp} cm)",
            "cols": ["Concepto", "Cantidad"],
            "filas": [["Área neta de pared", f'{r["area_neta_m2"]} m²'], ["Bloques necesarios", r["bloques"]]] +
                     [[k, f'{v} {u}'] for k, (v, u) in r["materiales"].items() if v], "pie": None})

    # ---------- Friso ----------
    paredes_f = _rows("friso_paredes")
    if paredes_f:
        vanos_f = _rows("friso_vanos")
        mats_f = _rows("friso_materiales")
        dosif = {m["material"]: (m.get("cantidad", 0), m.get("unidad", "")) for m in mats_f if m.get("material")}
        r = lc.friso(paredes_f, vanos_f, dosif, _f("friso_espesor", 2.0), _f("friso_caras", 1))
        secciones.append({"titulo": "Friso / Revestimiento", "cols": ["Concepto", "Cantidad"],
            "filas": [["Área a frisar", f'{r["area_m2"]} m²']] +
                     [[k, f'{v} {u}'] for k, (v, u) in r["materiales"].items() if v], "pie": None})

    # ---------- Estuco ----------
    paredes_e = _rows("estuco_paredes")
    if paredes_e:
        vanos_e = _rows("estuco_vanos")
        dosif = {"Cemento": (_f("estuco_cemento", 0), "sacos"), "Arena": (_f("estuco_arena", 0), "m³")}
        r = lc.estuco(paredes_e, vanos_e, dosif, _f("estuco_espesor", 0.3), _f("estuco_caras", 1))
        secciones.append({"titulo": "Estuco", "cols": ["Concepto", "Cantidad"],
            "filas": [["Área a estucar", f'{r["area_m2"]} m²']] +
                     [[k, f'{v} {u}'] for k, (v, u) in r["materiales"].items() if v], "pie": None})

    # ---------- Piso de Cemento ----------
    filas_p = _rows("piso_filas")
    if filas_p:
        color = bool(_f("piso_color", ""))
        dosif = {"Cemento": (_f("piso_cemento", 0), "sacos"), "Arena": (_f("piso_arena", 0), "m³")}
        r = lc.piso(filas_p, dosif, _f("piso_desperdicio", 5), color, _f("piso_pigmento", 0))
        filas_out = [["Área", f'{r["area_m2"]} m²'], ["Área con desperdicio", f'{r["area_con_desp_m2"]} m²']]
        filas_out += [[k, f'{v} {u}'] for k, (v, u) in r["materiales"].items() if v]
        secciones.append({"titulo": "Piso de Cemento", "cols": ["Concepto", "Cantidad"], "filas": filas_out, "pie": None})

    # ---------- Cerámica ----------
    filas_c = _rows("ceramica_filas")
    if filas_c:
        pa, pb = _f("ceramica_pieza_a"), _f("ceramica_pieza_b")
        r = lc.ceramica(filas_c, pa or None, pb or None, _f("ceramica_pego", 4.5), 25, _f("ceramica_desperdicio", 10))
        filas_out = [["Área", f'{r["area_m2"]} m²'], ["Área con desperdicio", f'{r["area_con_desp_m2"]} m²']]
        if "piezas" in r:
            filas_out.append(["Piezas necesarias", r["piezas"]])
        filas_out += [["Pego (adhesivo cerámico)", f'{r["pego_kg"]} kg'], ["Pego en sacos de 25 kg", r["pego_sacos"]]]
        secciones.append({"titulo": "Cerámica", "cols": ["Concepto", "Cantidad"], "filas": filas_out, "pie": None})

    # ---------- Pintura ----------
    if _f("pintura_area"):
        r = lc.pintura(_f("pintura_area"), _f("pintura_manos", 2), _f("pintura_rendimiento", 35))
        secciones.append({"titulo": "Pintura", "cols": ["Concepto", "Cantidad"],
            "filas": [["Área", f'{r["area_m2"]} m²'], ["Manos", r["manos"]],
                      ["Galones necesarios", r["galones"]], ["Cuñetes (5 gal c/u)", r["cunetes"]]],
            "pie": None})

    # ---------- Techo: Estructura Metálica (Correas) ----------
    if _f("techo_largo"):
        r_est = lc.estructura_techo(
            _f("techo_largo"),
            _f("techo_ancho"),
            _f("techo_pendiente", 15),
            _f("techo_sep_correas", 0.80),
        )
        secciones.append({
            "titulo": "Estructura Metálica de Techo (Correas)",
            "cols": ["Concepto", "Cantidad"],
            "filas": [
                ["Área de referencia", f'{r_est["area_inclinada_m2"]} m²'],
                ["Líneas de correas", r_est["correas_lineas"]],
                ["Metros de correa", f'{r_est["correas_metros"]} m'],
                ["Correas de 6 m", r_est["correas_6m"]],
            ],
            "pie": None,
        })

        # ---------- Techo: Cubierta y Fijaciones ----------
        # Volados (aleros) manuales, en metros, por lado. Cada uno es opcional (vacío = 0),
        # así se pueden usar 1, 2, 3 o los 4. Solo afectan la cubierta, no las correas.
        v_largo_1 = max(_num(_f("techo_volado_largo_1", 0)), 0.0)  # extremo 1 del largo (sentido de la pendiente)
        v_largo_2 = max(_num(_f("techo_volado_largo_2", 0)), 0.0)  # extremo 2 del largo
        v_ancho_1 = max(_num(_f("techo_volado_ancho_1", 0)), 0.0)  # lateral 1 (ancho)
        v_ancho_2 = max(_num(_f("techo_volado_ancho_2", 0)), 0.0)  # lateral 2 (ancho)
        largo_cub = _num(_f("techo_largo")) + v_largo_1 + v_largo_2
        ancho_cub = _num(_f("techo_ancho")) + v_ancho_1 + v_ancho_2
        r_cub = lc.cubierta_techo(
            largo_cub,
            ancho_cub,
            _f("techo_pendiente", 15),
            _f("techo_lam_largo", 3.66),
            _f("techo_lam_ancho", 0.86),
            _f("techo_solape", 0.15),
            _f("techo_tornillos", 8),
        )
        filas_cub = []
        if v_largo_1 or v_largo_2 or v_ancho_1 or v_ancho_2:
            for etiqueta, v in [("Volado largo - lado 1", v_largo_1), ("Volado largo - lado 2", v_largo_2),
                                ("Volado ancho - lado 1", v_ancho_1), ("Volado ancho - lado 2", v_ancho_2)]:
                if v:
                    filas_cub.append([etiqueta, f"{v:g} m"])
            filas_cub.append(["Dimensiones de cubierta con volados", f"{largo_cub:g} x {ancho_cub:g} m"])
        filas_cub += [
            ["Área inclinada de cubierta", f'{r_cub["area_inclinada_m2"]} m²'],
            ["Láminas", r_cub["laminas"]],
            ["Tornillos con arandela", r_cub["tornillos"]],
        ]
        secciones.append({
            "titulo": "Cubierta de Techo (Láminas y Fijaciones)",
            "cols": ["Concepto", "Cantidad"],
            "filas": filas_cub,
            "pie": None,
        })

    # ---------- Malla Electrosoldada ----------
    filas_malla = _rows("malla_filas")
    if filas_malla:
        r = lc.malla_electrosoldada(filas_malla, _f("malla_area_rollo", 50), _f("malla_desperdicio", 10))
        secciones.append({"titulo": "Malla Electrosoldada", "cols": ["Concepto", "Cantidad"],
            "filas": [["Área a cubrir", f'{r["area_m2"]} m²'], ["Área con desperdicio", f'{r["area_con_desp_m2"]} m²'],
                      ["Área por rollo/lámina", f'{r["area_rollo_m2"]} m²'], ["Rollos/láminas necesarios", r["rollos"]]],
            "pie": None})

    # ---------- Capítulos de ítems manuales (eléctrico, sanitario, puertas, otros) ----------
    def _capitulo_items(campo, titulo):
        rows = _rows(campo)
        filas = [[r.get("item", "-"), r.get("unidad", "-"), r.get("cantidad")]
                 for r in rows if r.get("item") and n(r.get("cantidad")) > 0]
        if filas:
            total = sum(n(r.get("cantidad")) for r in rows if r.get("item"))
            secciones.append({"titulo": titulo, "cols": ["Ítem", "Unidad", "Cantidad"],
                               "filas": filas, "pie": None})

    def n(x):
        try:
            return float(str(x).replace(",", ".").strip() or 0)
        except ValueError:
            return 0.0

    _capitulo_items("electricas_items", "Instalaciones Eléctricas")
    _capitulo_items("sanitarias_items", "Instalaciones Sanitarias")
    _capitulo_items("puertas_items", "Puertas y Carpintería")
    _capitulo_items("otros_items", "Otros Ítems")

    if not secciones:
        return redirect(url_for("index"))

    generales = [(k2, f[k1]) for k1, k2 in [
        ("obra", "Obra / Proyecto"), ("ubicacion", "Ubicación"), ("parroquia", "Parroquia"),
        ("fecha", "Fecha"), ("responsable", "Elaborado por")] if f.get(k1)]

    datos = {"direccion": _f("direccion", "completo"), "titulo": "CÓMPUTOS MÉTRICOS",
             "generales": generales, "secciones": secciones}
    nombre = f"computos_{uuid.uuid4().hex[:8]}.docx"
    generar_word(datos, os.path.join(CARPETA, nombre))
    return render_template("computos_listo.html", archivo=nombre)


@app.route("/descargar/<nombre>")
def descargar(nombre):
    return send_file(os.path.join(CARPETA, nombre), as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
