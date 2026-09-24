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
                 "Grava": (_f("concreto_grava", 0), "m³")}
        desp = float(_f("concreto_desperdicio", 0) or 0)
        r = lc.concreto(elementos, resistencia, dosif, desp)
        secciones.append({"titulo": r["titulo"],
            "cols": ["Elemento", "Largo", "Ancho", "Alto", "Diám.", "Cant.", "Total m³"],
            "filas": [[e.get("elemento", "-"), e.get("largo", "-"), e.get("ancho", "-"), e.get("alto", "-"),
                       e.get("diam", "-"), e.get("cant") or 1, e["total_m3"]] for e in r["filas"]],
            "pie": ["TOTAL", "", "", "", "", "", r["total_m3"]]})
        mats = [[k, v, u] for k, (v, u) in r["materiales"].items() if v]
        if mats:
            secciones.append({"titulo": f"Materiales — Concreto {resistencia} kg/cm²",
                "cols": ["Material", "Cantidad", "Unidad"], "filas": mats, "pie": None})

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
        resumen = [[d, v["metros"], v["kg"], v["barras_12m"]] for d, v in r["por_diametro"].items()]
        resumen.append(["TOTAL", "", r["total_kg"], ""])
        secciones.append({"titulo": "Resumen de Acero por Diámetro",
            "cols": ["Diámetro", "Metros", "Kg", "Barras de 12 m"], "filas": resumen, "pie": None})

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
        dosif = {"Cemento": (_f("friso_cemento", 0), "sacos"), "Arena": (_f("friso_arena", 0), "m³")}
        r = lc.friso(paredes_f, vanos_f, dosif, _f("friso_espesor", 1.5), _f("friso_caras", 1))
        secciones.append({"titulo": "Friso / Revestimiento", "cols": ["Concepto", "Cantidad"],
            "filas": [["Área a frisar", f'{r["area_m2"]} m²']] +
                     [[k, f'{v} {u}'] for k, (v, u) in r["materiales"].items() if v], "pie": None})

    # ---------- Piso ----------
    filas_p = _rows("piso_filas")
    if filas_p:
        pa, pb = _f("piso_pieza_a"), _f("piso_pieza_b")
        dosif = {"Cemento": (_f("piso_cemento", 0), "sacos"), "Arena": (_f("piso_arena", 0), "m³")}
        r = lc.piso(filas_p, pa or None, pb or None, dosif, _f("piso_desperdicio", 10))
        filas_out = [["Área", f'{r["area_m2"]} m²'], ["Área con desperdicio", f'{r["area_con_desp_m2"]} m²']]
        if "piezas" in r:
            filas_out.append(["Piezas necesarias", r["piezas"]])
        filas_out += [[k, f'{v} {u}'] for k, (v, u) in r["materiales"].items() if v]
        secciones.append({"titulo": "Piso / Cerámica", "cols": ["Concepto", "Cantidad"], "filas": filas_out, "pie": None})

    # ---------- Pintura ----------
    if _f("pintura_area"):
        r = lc.pintura(_f("pintura_area"), _f("pintura_manos", 2), _f("pintura_rendimiento", 35))
        secciones.append({"titulo": "Pintura", "cols": ["Concepto", "Cantidad"],
            "filas": [["Área", f'{r["area_m2"]} m²'], ["Manos", r["manos"]], ["Galones necesarios", r["galones"]]],
            "pie": None})

    # ---------- Techo ----------
    if _f("techo_largo"):
        r = lc.techo(_f("techo_largo"), _f("techo_ancho"), _f("techo_pendiente", 15),
                     _f("techo_lam_largo", 3.66), _f("techo_lam_ancho", 0.86),
                     _f("techo_solape", 0.15), _f("techo_sep_correas", 1.0), _f("techo_tornillos", 8))
        secciones.append({"titulo": "Techo (Láminas y Correas)", "cols": ["Concepto", "Cantidad"],
            "filas": [["Área inclinada", f'{r["area_inclinada_m2"]} m²'], ["Láminas", r["laminas"]],
                      ["Líneas de correas", r["correas_lineas"]], ["Metros de correa", f'{r["correas_metros"]} m'],
                      ["Correas de 6 m", r["correas_6m"]], ["Tornillos", r["tornillos"]]], "pie": None})

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
