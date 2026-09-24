"""logic_computos_word.py - Genera el Word de cómputos con el membrete de Brión.
Usa assets/plantilla_computos.docx (membrete en el encabezado, cuerpo vacío)."""
import os, zipfile
from xml.sax.saxutils import escape as esc

PLANTILLA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "plantilla_computos.docx")
AZUL, ANCHO = "1A365D", 10600
SECRETARIA = "SECRETARÍA PARA LA TRANSFORMACIÓN DE LAS CIUDADES HUMANAS Y SERVICIOS"
ING, HAB = "DIRECCIÓN DE INGENIERÍA MUNICIPAL", "DIRECCIÓN DE HÁBITAT Y VIVIENDA"
# Desplegable del formulario -> (línea 1, línea 2) del membrete
DIRECCIONES = {
    "habitat": ("", HAB),
    "ingenieria": ("", ING),
    "completo": (SECRETARIA, f"{ING} - {HAB}"),
}
F = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial" w:eastAsia="Arial"/>'

def _p(txt, sz=18, bold=False, color=None, jc="left", after=80, keep=False):
    c = f'<w:color w:val="{color}"/>' if color else ""
    return (f'<w:p><w:pPr>{"<w:keepNext/>" if keep else ""}<w:spacing w:before="0" w:after="{after}"/>'
            f'<w:jc w:val="{jc}"/></w:pPr><w:r><w:rPr>{F}{"<w:b/>" if bold else ""}{c}<w:sz w:val="{sz}"/></w:rPr>'
            f'<w:t xml:space="preserve">{esc(str(txt))}</w:t></w:r></w:p>')

def _cell(txt, w, head=False, bold=False, jc="left"):
    shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{"E8EEF5" if head else "FFFFFF"}"/>'
    return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shd}<w:vAlign w:val="center"/></w:tcPr>'
            f'{_p(txt, 16, head or bold, AZUL if head else None, jc, 0)}</w:tc>')

def tabla(cols, filas, pie=None):
    """cols: encabezados; filas: listas de texto; pie: fila de totales (opcional)."""
    k = len(cols)
    w0 = 2400 if k > 2 else ANCHO // k
    ws = [w0] + [(ANCHO - w0) // (k - 1)] * (k - 1) if k > 1 else [ANCHO]
    bd = "".join(f'<w:{s} w:val="single" w:sz="6" w:space="0" w:color="{AZUL}"/>'
                 for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in ws)
    def row(vals, head=False, bold=False):
        cs = "".join(_cell(v, ws[i], head, bold, "left" if i == 0 else "center") for i, v in enumerate(vals))
        return f'<w:tr><w:trPr><w:cantSplit/>{"<w:tblHeader/>" if head else ""}</w:trPr>{cs}</w:tr>'
    body = row(cols, head=True) + "".join(row(f) for f in filas) + (row(pie, bold=True) if pie else "")
    return (f'<w:tbl><w:tblPr><w:tblW w:type="dxa" w:w="{ANCHO}"/><w:jc w:val="center"/>'
            f'<w:tblBorders>{bd}</w:tblBorders><w:tblLayout w:type="fixed"/>'
            f'<w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr>'
            f'<w:tblGrid>{grid}</w:tblGrid>{body}</w:tbl>' + _p("", 8, after=120))

def generar_word(datos, salida, plantilla=PLANTILLA):
    """datos = {'direccion': 'habitat'|'ingenieria'|'completo', 'titulo': str,
                'generales': [(campo, valor), ...],
                'secciones': [{'titulo': str, 'cols': [...], 'filas': [[...]], 'pie': [...]|None, 'nota': str|None}]}"""
    b = [_p(datos.get("titulo", "CÓMPUTOS MÉTRICOS"), 21, True, AZUL, "center", 160)]
    gen = datos.get("generales") or []
    if gen:
        b.append(_p("I. DATOS GENERALES", 20, True, AZUL, keep=True))
        b.append(tabla(["Campo", "Detalle"], [[a, v] for a, v in gen]))
    for i, s in enumerate(datos["secciones"], 2 if gen else 1):
        b.append(_p(f'{["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV"][i]}. {s["titulo"].upper()}',
                    20, True, AZUL, keep=True))
        b.append(tabla(s["cols"], s["filas"], s.get("pie")))
        if s.get("nota"):
            b.append(_p(s["nota"], 16, after=120))
    zin = zipfile.ZipFile(plantilla)
    l1, l2 = DIRECCIONES.get(datos.get("direccion", "completo"), DIRECCIONES["completo"])
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            raw = zin.read(it.filename)
            if it.filename == "word/document.xml":
                raw = raw.decode("utf8").replace("<!--BODY-->", "".join(b)).encode("utf8")
            elif it.filename == "word/header1.xml":
                h = raw.decode("utf8")
                h = h.replace(esc(SECRETARIA), esc(l1)).replace(esc(f"{ING} - {HAB}"), esc(l2))
                raw = h.encode("utf8")
            zout.writestr(it, raw)
    return salida

if __name__ == "__main__":
    import logic_computos as lc
    d = {"cemento": (8, "sacos"), "arena": (0.55, "m³"), "grava": (0.70, "m³")}
    c = lc.concreto([{"largo": .3, "ancho": .3, "alto": 3, "cant": 10}, {"largo": 5, "ancho": 4, "alto": .12, "cant": 3}], 210, d)
    filas = [["Columna", .3, .3, 3, "-", 10, 2.7], ["Losa", 5, 4, .12, "-", 3, 7.2]]
    mats = [[k, v, u] for k, (v, u) in c["materiales"].items()]
    for dr in DIRECCIONES:
        generar_word({"direccion": dr, "titulo": "CÓMPUTOS MÉTRICOS", "generales": [("Obra", "Prueba")],
            "secciones": [{"titulo": c["titulo"], "cols": ["Elemento", "Largo", "Ancho", "Alto", "Diám.", "Cant.", "Total m³"],
                           "filas": filas, "pie": ["TOTAL", "", "", "", "", "", c["total_m3"]]},
                          {"titulo": "Materiales", "cols": ["Material", "Cantidad", "Unidad"], "filas": mats}]},
            f"/tmp/prueba_{dr}.docx")
    print("ok")
