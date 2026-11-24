import asyncio
import base64
import datetime
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER = os.environ.get("GITHUB_USER", "unrealmat-coder")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "unrealmat-tv")

BASE_URLS = [
    "https://streamxhd.sbs",
]

OUTPUT_DIR = Path("output")

DEPORTE_KEYWORDS = {
    "futbol": [
        "FUTBOL", "FÚTBOL", "SOCCER", "LIGA", "PREMIER LEAGUE", "LA LIGA",
        "SERIE A", "BUNDESLIGA", "LIGUE 1", "CHAMPIONS", "LIBERTADORES",
        "SUDAMERICANA", "COPA", "MUNDIAL", "FIFA", "ELIMINATORIAS",
        "URUGUAY", "ARGENTINA", "BRASIL", "MEXICO", "MÉXICO", "MLS",
        "EREDIVISIE", "PRIMEIRA LIGA", "CONCACAF", "EUROPA LEAGUE",
        "CONFERENCE LEAGUE", "FA CUP", "CARABAO", "COPA DEL REY",
        "COPA ITALIA", "DFB POKAL", "VELEZ", "VÉLEZ", "RIVER", "BOCA",
        "PEÑAROL", "NACIONAL", "FLAMENGO", "PALMEIRAS", "REAL MADRID",
        "BARCELONA", "ATLETICO", "ATLÉTICO", "ARSENAL", "LIVERPOOL",
        "MANCHESTER", "CHELSEA", "CITY", "UNITED", "JUVENTUS", "INTER",
        "MILAN", "NAPOLI", "BAYERN", "DORTMUND", "PSG", "BENFICA", "PORTO",
    ],
    "nba": [
        "NBA", "BASKET", "BÁSQUET", "BALONCESTO", "BASKETBALL", "EUROLIGA",
        "EUROLEAGUE", "WNBA", "G LEAGUE", "SUMMER LEAGUE", "LAKERS",
        "CELTICS", "WARRIORS", "BUCKS", "NUGGETS", "HEAT", "SUNS",
        "MAVERICKS", "CLIPPERS", "KNICKS", "76ERS", "SIXERS", "BULLS",
        "CAVALIERS", "THUNDER", "TIMBERWOLVES", "KINGS", "PELICANS",
        "PACERS", "MAGIC", "HAWKS", "RAPTORS", "NETS", "BLAZERS",
        "JAZZ", "SPURS", "ROCKETS", "PISTONS", "HORNETS", "WIZARDS",
    ],
    "f1": [
        "FORMULA 1", "FÓRMULA 1", "F1", "GRAND PRIX", "GRAN PREMIO",
        "GP ", "QUALIFYING", "CLASIFICACION", "CLASIFICACIÓN", "QUALY",
        "FREE PRACTICE", "PRACTICA", "PRÁCTICA", "FP1", "FP2", "FP3",
        "SPRINT", "FIA", "CIRCUITO", "MOTO GP", "MOTOGP", "NASCAR", "INDYCAR",
    ],
    "otros": [
        "NFL", "MLB", "NHL", "BASEBALL", "BÉISBOL", "BEISBOL", "HOCKEY",
        "AMERICAN FOOTBALL", "FOOTBALL AMERICANO", "SUPER BOWL", "TENNIS",
        "TENIS", "ATP", "WTA", "UFC", "BOXEO", "BOXING", "GOLF", "PGA",
        "RUGBY", "VOLEY", "VOLEIBOL", "HANDBALL", "BALONMANO", "FUTSAL",
    ],
}

REGEX_POR_DEPORTE = {
    "futbol": [r"\bFUTBOL\b", r"\bFÚTBOL\b", r"\bSOCCER\b", r"\bFIFA\b", r"\bMLS\b"],
    "nba": [r"\bNBA\b", r"\bWNBA\b", r"\bBASKET\b", r"\bBÁSQUET\b", r"\bBALONCESTO\b"],
    "f1": [r"\bF1\b", r"\bFORMULA\s*1\b", r"\bFÓRMULA\s*1\b", r"\bGP\b", r"\bMOTOGP\b", r"\bNASCAR\b"],
    "otros": [r"\bNFL\b", r"\bMLB\b", r"\bNHL\b", r"\bUFC\b", r"\bATP\b", r"\bWTA\b", r"\bPGA\b"],
}


def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    reemplazos = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNAEIOUUN")
    return re.sub(r"\s+", " ", texto.translate(reemplazos).upper()).strip()


def clasificar_deporte(titulo: str, torneo: str = "") -> str:
    texto = normalizar_texto(f"{titulo or ''} {torneo or ''}")
    if not texto:
        return "otros"

    puntajes = {"futbol": 0, "nba": 0, "f1": 0, "otros": 0}
    for deporte, patrones in REGEX_POR_DEPORTE.items():
        for patron in patrones:
            if re.search(patron, texto):
                puntajes[deporte] += 3

    for deporte, palabras in DEPORTE_KEYWORDS.items():
        for kw in palabras:
            kw_norm = normalizar_texto(kw)
            if kw_norm and kw_norm in texto:
                puntajes[deporte] += 1

    if puntajes["otros"] >= 3 and puntajes["f1"] == 0 and puntajes["nba"] == 0 and puntajes["futbol"] == 0:
        return "otros"

    mejor_deporte = max(puntajes.items(), key=lambda item: item[1])
    return mejor_deporte[0] if mejor_deporte[1] > 0 else "otros"


def normalizar_url_stream(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    limpia = url.strip()
    if limpia.startswith("//"):
        limpia = "https:" + limpia
    elif limpia.startswith("http://"):
        limpia = "https://" + limpia[7:]
    if not limpia.startswith("https://"):
        return ""
    return limpia


def construir_payload_archivo(deporte: str, eventos: list, conservado_previo: bool = False) -> dict:
    return {
        "deporte": deporte,
        "actualizado_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(eventos),
        "conservado_previo": conservado_previo,
        "eventos": eventos,
    }


def cargar_eventos_previos(nombre_archivo: str) -> list:
    ruta = OUTPUT_DIR / nombre_archivo
    if not ruta.exists():
        return []
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("eventos"), list):
            return data["eventos"]
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def guardar_json_local(nombre_archivo: str, payload: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ruta = OUTPUT_DIR / nombre_archivo
    ruta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def subir_github(ruta_repo: str, contenido_str: str, mensaje_commit: str) -> None:
    if not GITHUB_TOKEN or not GITHUB_USER or not GITHUB_REPO:
        print(f"[INFO] GITHUB_TOKEN no configurado; se omite subida API para {ruta_repo}")
        return

    ruta_encoded = urllib.parse.quote(ruta_repo.strip("/"))
    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{ruta_encoded}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "UNREALMAT-Extractor/2.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    sha_actual = None
    try:
        req_get = urllib.request.Request(api_url, headers=headers, method="GET")
        with urllib.request.urlopen(req_get, timeout=15) as resp:
            data_get = json.loads(resp.read().decode("utf-8"))
            sha_actual = data_get.get("sha")
    except Exception:
        sha_actual = None

    cuerpo = {
        "message": mensaje_commit,
        "content": base64.b64encode(contenido_str.encode("utf-8")).decode("ascii"),
        "branch": "main",
    }
    if sha_actual:
        cuerpo["sha"] = sha_actual

    try:
        req_put = urllib.request.Request(
            api_url,
            data=json.dumps(cuerpo).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req_put, timeout=20) as resp_put:
            if resp_put.status in (200, 201):
                print(f"[OK] Subido a GitHub: {ruta_repo}")
    except Exception as exc:
        print(f"[WARN] Error subiendo {ruta_repo} a GitHub: {exc}")


def deduplicar_eventos(eventos: list) -> list:
    mapa = {}
    for ev in eventos:
        titulo_limpio = re.sub(r"[^A-Z0-9]", "", normalizar_texto(ev.get("titulo", "")))
        fecha_str = (ev.get("fecha_completa") or ev.get("hora") or "").strip()
        clave = f"{titulo_limpio}|{fecha_str}"

        servidores_validos = []
        urls_vistas = set()
        for srv in ev.get("servidores", []):
            url_norm = normalizar_url_stream(srv.get("url", ""))
            if not url_norm or url_norm in urls_vistas:
                continue
            urls_vistas.add(url_norm)
            servidores_validos.append({
                "nombre": (srv.get("nombre") or "Opción").strip(),
                "url": url_norm,
            })

        ev_limpio = {
            "titulo": (ev.get("titulo") or "Evento").strip(),
            "torneo": (ev.get("torneo") or "").strip(),
            "fecha_completa": (ev.get("fecha_completa") or "").strip(),
            "hora": (ev.get("hora") or "00:00").strip(),
            "status": (ev.get("status") or "EN VIVO").strip(),
            "servidores": servidores_validos,
        }

        if clave not in mapa:
            mapa[clave] = ev_limpio
        else:
            existente = mapa[clave]
            urls_existentes = {s["url"] for s in existente["servidores"]}
            for s in ev_limpio["servidores"]:
                if s["url"] not in urls_existentes:
                    existente["servidores"].append(s)
                    urls_existentes.add(s["url"])

    return list(mapa.values())


async def _extraer_de_pagina(page, base_url: str) -> list:
    await page.goto(base_url, wait_until="domcontentloaded", timeout=35000)
    await page.wait_for_timeout(3000)

    items_raw = await page.evaluate(
        """
        () => {
            const resultados = [];
            const vistos = new Set();
            const candidatos = document.querySelectorAll(
                'li, tr, article, .card, .item, .evento, .event-row, .match-item, .agenda-item, a[href]'
            );

            candidatos.forEach((el) => {
                const texto = (el.innerText || '').trim();
                if (!texto || texto.length < 5 || texto.length > 500) return;

                const enlaces = Array.from(el.querySelectorAll('a[href]')).map((a) => ({
                    nombre: (a.innerText || a.getAttribute('title') || 'Canal').trim(),
                    url: a.href || a.getAttribute('href') || ''
                }));
                if (el.tagName === 'A' && el.href) {
                    enlaces.push({
                        nombre: (el.innerText || 'Canal').trim(),
                        url: el.href
                    });
                }

                const enlacesValidos = enlaces.filter((e) => e.url && !e.url.startsWith('javascript:') && e.url !== window.location.href + '#');
                if (enlacesValidos.length === 0 && !/\\b([01]?\\d|2[0-3]):[0-5]\\d\\b/.test(texto)) return;

                const firma = texto.slice(0, 120);
                if (vistos.has(firma)) return;
                vistos.add(firma);

                resultados.push({ texto, enlaces: enlacesValidos });
            });
            return resultados;
        }
        """
    )

    extraidos = []
    for item in items_raw:
        lineas = [ln.strip() for ln in (item.get("texto") or "").splitlines() if ln.strip()]
        if not lineas:
            continue

        titulo = lineas[0]
        torneo = lineas[1] if len(lineas) > 1 else ""
        hora_match = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", " ".join(lineas))
        hora = hora_match.group(0) if hora_match else "00:00"
        if len(hora) == 4:
            hora = "0" + hora

        fecha_match = re.search(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2})?\b", " ".join(lineas))
        fecha_completa = fecha_match.group(0) if fecha_match else ""

        servidores = []
        for idx, enl in enumerate(item.get("enlaces", [])):
            url_abs = urllib.parse.urljoin(base_url, enl.get("url", ""))
            url_norm = normalizar_url_stream(url_abs)
            if url_norm:
                nombre_srv = enl.get("nombre") or f"Opción {idx + 1}"
                if len(nombre_srv) > 30:
                    nombre_srv = f"Opción {idx + 1}"
                servidores.append({"nombre": nombre_srv, "url": url_norm})

        if servidores or len(titulo) > 5:
            extraidos.append({
                "titulo": titulo,
                "torneo": torneo,
                "fecha_completa": fecha_completa,
                "hora": hora,
                "status": "EN VIVO",
                "servidores": servidores,
            })

    return extraidos


async def recolectar_todos() -> dict:
    agrupados = {"futbol": [], "nba": [], "f1": [], "otros": []}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
        )
        page = await context.new_page()

        for base_url in BASE_URLS:
            try:
                print(f"[SCRAPE] Consultando {base_url} ...")
                eventos_url = await _extraer_de_pagina(page, base_url)
                print(f"[SCRAPE] {len(eventos_url)} elementos detectados en {base_url}")
                for ev in eventos_url:
                    deporte = clasificar_deporte(ev.get("titulo", ""), ev.get("torneo", ""))
                    agrupados[deporte].append(ev)
            except Exception as exc:
                print(f"[WARN] Fallo en {base_url}: {exc}")

        await browser.close()

    for deporte in agrupados:
        agrupados[deporte] = deduplicar_eventos(agrupados[deporte])

    return agrupados


def ejecutar() -> None:
    inicio = time.time()
    datos = asyncio.run(recolectar_todos())

    mapa_archivos = {
        "futbol": "agenda_futbol.json",
        "nba": "agenda_nba.json",
        "f1": "agenda_f1.json",
    }

    ts_commit = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for deporte, nombre_archivo in mapa_archivos.items():
        eventos_nuevos = datos[deporte]
        conservado_previo = False

        if len(eventos_nuevos) == 0:
            previos = cargar_eventos_previos(nombre_archivo)
            if len(previos) > 0:
                eventos_nuevos = previos
                conservado_previo = True
                print(f"[INFO] {nombre_archivo}: 0 eventos nuevos; se conservan {len(previos)} eventos previos.")

        payload = construir_payload_archivo(deporte, eventos_nuevos, conservado_previo=conservado_previo)
        ruta_local = guardar_json_local(nombre_archivo, payload)
        contenido_str = ruta_local.read_text(encoding="utf-8")
        subir_github(
            f"output/{nombre_archivo}",
            contenido_str,
            f"chore(data): actualizar {nombre_archivo} ({ts_commit})",
        )

    print(
        f"[RESUMEN] Fútbol: {len(datos['futbol'])} | NBA: {len(datos['nba'])} | "
        f"F1: {len(datos['f1'])} | Otros (NFL/MLB/NHL/etc.): {len(datos['otros'])} | "
        f"Tiempo: {time.time() - inicio:.1f}s"
    )


if __name__ == "__main__":
    ejecutar()
