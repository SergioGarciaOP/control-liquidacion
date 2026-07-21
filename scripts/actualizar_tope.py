#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robot de actualización del tope MOPRE (base imponible máxima SIPA).

Corre en GitHub Actions varias veces por mes. Mantiene data/topes.json con dos fuentes:

1) OFICIAL: página "Indicadores Monetarios de la Seguridad Social" (Ministerio de
   Capital Humano). Publica el valor redondeado a pesos y suele atrasarse unos meses,
   pero es la confirmación oficial. https://www.argentina.gob.ar/trabajo/seguridadsocial/imss

2) ESTIMADO POR IPC: la movilidad del Decreto 274/2024 define
   tope[m] = round(tope[m-1] × (1 + IPC de m-2 con 2 decimales), 2).
   Verificado al centavo contra las Resoluciones ANSES 74, 110, 139 y 186 de 2026.
   El IPC sale de la API oficial de Series de Tiempo (apis.datos.gob.ar).

Salvaguardas:
- AUTOTEST en cada corrida: el método por IPC debe reproducir exactamente las anclas
  históricas conocidas; si no lo hace, no se estima nada ese mes y se registra alerta.
- Cruce: cuando la fuente oficial publica un período ya estimado, se comparan
  (tolerancia $1 por redondeo). Coincide → "confirmado". No coincide → alerta.
- Nunca pisa un valor "confirmado" ni uno cargado como "manual".
- Si algo falla, el JSON queda igual y el campo "alertas" explica qué pasó;
  la app muestra el aviso para cargar a mano ese mes.
"""
import json
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

RUTA_JSON = Path(__file__).resolve().parent.parent / "data" / "topes.json"
URL_IMSS = "https://www.argentina.gob.ar/trabajo/seguridadsocial/imss"
API_SERIES = "https://apis.datos.gob.ar/series/api/series/"
API_BUSQUEDA = "https://apis.datos.gob.ar/series/api/search/"
# Candidatos conocidos de la serie IPC Nivel General Nacional (índice, mensual).
# Si ninguno valida el autotest, se buscan alternativas vía el buscador de la API.
SERIES_IPC_CANDIDATAS = [
    "148.3_INIVELNAL_DICI_M_26",
    "145.3_INGNACNAL_DICI_M_38",
    "101.1_I2NG_2016_M_22",
]
# Anclas verificadas contra resoluciones ANSES (valor exacto con centavos).
ANCLAS = {
    "202604": 4162912.57,   # Res. ANSES 74/2026
    "202605": 4303619.01,   # Res. ANSES 110/2026
    "202606": 4414652.38,   # Res. ANSES 139/2026
    "202607": 4509567.41,   # Res. ANSES 186/2026
}
# Movilidades publicadas en esas resoluciones (para el autotest del IPC):
# período_tope -> (mes_IPC, % con 2 decimales)
MOVILIDADES_CONOCIDAS = {
    "202605": ("2026-03", 3.38),
    "202606": ("2026-04", 2.58),
    "202607": ("2026-05", 2.15),
}
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def descargar(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (control-liquidacion-bot)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def texto_plano(html):
    """Quita etiquetas y normaliza espacios para que los patrones sean tolerantes."""
    t = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&aacute;", "á").replace("&iacute;", "í")
    t = t.replace("&oacute;", "ó").replace("&eacute;", "é").replace("&uacute;", "ú")
    return re.sub(r"\s+", " ", t)


def parsear_monto(s):
    """'$ 4.162.913' o '4.162.912,57' -> float."""
    s = s.strip().replace("$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    return float(s)


def parsear_imss(html):
    """Devuelve (periodo 'AAAAMM', valor_redondeado) o (None, None)."""
    t = texto_plano(html)
    m_per = re.search(r"Publicaci[oó]n\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s*/\s*(\d{4})", t)
    m_val = re.search(r"Base\s+m[aá]xima\s+imponible\D{0,60}?\$?\s*([\d\.\,]+)", t, re.I)
    if not m_per or not m_val:
        return None, None
    mes_nombre = m_per.group(1).lower()
    anio = m_per.group(2)
    try:
        mes = MESES.index(mes_nombre)
    except ValueError:
        return None, None
    periodo = f"{anio}{mes:02d}"
    return periodo, parsear_monto(m_val.group(1))


def obtener_ipc(descargar_fn=descargar):
    """
    Devuelve dict {'AAAA-MM': variacion_%_2dec} del IPC nivel general nacional,
    o None si ninguna serie pasa el autotest.
    """
    candidatas = list(SERIES_IPC_CANDIDATAS)
    # ampliar candidatas con el buscador de la API
    try:
        q = urllib.parse.urlencode({"q": "ipc nivel general nacional indice", "limit": 10})
        data = json.loads(descargar_fn(f"{API_BUSQUEDA}?{q}"))
        for item in data.get("data", []):
            sid = item.get("field", {}).get("id") or item.get("id")
            if sid and sid not in candidatas:
                candidatas.append(sid)
    except Exception:
        pass  # el buscador es opcional; seguimos con las candidatas fijas

    for sid in candidatas:
        try:
            q = urllib.parse.urlencode({
                "ids": sid, "representation_mode": "percent_change",
                "start_date": "2026-01-01", "limit": 1000, "format": "json"})
            data = json.loads(descargar_fn(f"{API_SERIES}?{q}"))
            vars_pct = {}
            for fecha, valor in data.get("data", []):
                if valor is None:
                    continue
                vars_pct[fecha[:7]] = round(float(valor) * 100, 2)
            # AUTOTEST: debe reproducir las movilidades conocidas
            if all(abs(vars_pct.get(mes_ipc, -999) - pct) < 0.005
                   for (mes_ipc, pct) in MOVILIDADES_CONOCIDAS.values()):
                return vars_pct
        except Exception:
            continue
    return None


def periodo_siguiente(p):
    a, m = int(p[:4]), int(p[4:])
    m += 1
    if m == 13:
        a, m = a + 1, 1
    return f"{a}{m:02d}"


def mes_ipc_para(periodo_tope):
    """El tope del período m usa el IPC de m-2. Devuelve 'AAAA-MM'."""
    a, m = int(periodo_tope[:4]), int(periodo_tope[4:])
    m -= 2
    if m <= 0:
        a, m = a - 1, m + 12
    return f"{a}-{m:02d}"


def main():
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if RUTA_JSON.exists():
        doc = json.loads(RUTA_JSON.read_text(encoding="utf-8"))
    else:
        doc = {"topes": {}, "alertas": [], "actualizado": None}
    topes = doc.setdefault("topes", {})
    alertas = []

    # sembrar anclas si faltan
    for per, val in ANCLAS.items():
        if per not in topes:
            topes[per] = {"valor": val, "fuente": "resolución ANSES (ancla verificada)",
                          "estado": "confirmado"}

    # ---------- 1) Fuente oficial (IMSS) ----------
    per_imss = val_imss = None
    try:
        per_imss, val_imss = parsear_imss(descargar(URL_IMSS))
    except Exception as e:
        alertas.append(f"No se pudo leer la página oficial IMSS: {e}")
    if per_imss and val_imss:
        actual = topes.get(per_imss)
        if actual is None:
            topes[per_imss] = {"valor": val_imss, "fuente": "IMSS (oficial, redondeado a pesos)",
                               "estado": "confirmado"}
        elif actual["estado"] == "estimado":
            if abs(round(actual["valor"]) - round(val_imss)) <= 1:
                actual["estado"] = "confirmado"
                actual["fuente"] += " · confirmado por IMSS"
            else:
                alertas.append(
                    f"CRUCE FALLIDO en {per_imss}: estimado {actual['valor']:.2f} vs "
                    f"oficial IMSS {val_imss:.2f}. Verificar a mano la resolución ANSES.")
    elif per_imss is None:
        alertas.append("La página IMSS cambió de formato: no se encontró período o valor.")

    # ---------- 2) Estimación por IPC ----------
    ipc = obtener_ipc()
    if ipc is None:
        alertas.append("El método por IPC no pasó el autotest este mes: no se estimó ningún "
                       "período nuevo. Cargar el tope a mano si hace falta.")
    else:
        # avanzar desde el último período confirmado/manual con valor exacto
        base = max((p for p, d in topes.items()
                    if d["estado"] in ("confirmado", "manual")), default=None)
        if base:
            per = periodo_siguiente(base)
            valor = topes[base]["valor"]
            for _ in range(12):  # nunca más de un año hacia adelante
                mes_ipc = mes_ipc_para(per)
                if mes_ipc not in ipc:
                    break
                valor = round(valor * (1 + ipc[mes_ipc] / 100), 2)
                previo = topes.get(per)
                if previo is None:
                    topes[per] = {"valor": valor,
                                  "fuente": f"calculado por movilidad (IPC {mes_ipc}: {ipc[mes_ipc]:.2f}%)",
                                  "estado": "estimado"}
                elif previo["estado"] == "estimado" and abs(previo["valor"] - valor) > 0.005:
                    previo["valor"] = valor
                    previo["fuente"] = f"calculado por movilidad (IPC {mes_ipc}: {ipc[mes_ipc]:.2f}%)"
                per = periodo_siguiente(per)

    doc["alertas"] = alertas
    doc["actualizado"] = ahora
    RUTA_JSON.parent.mkdir(parents=True, exist_ok=True)
    RUTA_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True),
                         encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True))
    print(f"\nOK: {len(topes)} períodos, {len(alertas)} alertas.", file=sys.stderr)


if __name__ == "__main__":
    main()
