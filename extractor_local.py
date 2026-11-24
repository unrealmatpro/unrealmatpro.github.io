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

KEYWORDS_FUTBOL = [
    "FUTBOL", "FÚTBOL", "SOCCER", "LIGA", "PREMIER", "LA LIGA", "SERIE A",
    "BUNDESLIGA", "LIGUE 1", "CHAMPIONS", "LIBERTADORES", "SUDAMERICANA",
    "COPA", "MUNDIAL", "FIFA", "ELIMINATORIAS", "MLS", "EREDIVISIE",
    "URUGUAY", "ARGENTINA", "BRASIL", "MEXICO", "MÉXICO", "CHILE", "COLOMBIA",
    "PERU", "PERÚ", "ECUADOR", "PARAGUAY", "PEÑAROL", "NACIONAL", "RIVER",
    "BOCA", "REAL MADRID", "BARCELONA", "ATLETICO", "ATLÉTICO", "ARSENAL",
    "LIVERPOOL", "MANCHESTER", "CHELSEA", "CITY", "UNITED", "JUVENTUS",
    "INTER", "MILAN", "NAPOLI", "BAYERN", "DORTMUND", "PSG", "OPORTO", "PORTO",
    "BENFICA", "SPORTING", "FLAMENGO", "PALMEIRAS", "SAO PAULO", "BOTAFOGO",
]

KEYWORDS_NBA = [
    "NBA", "BASKET", "BÁSQUET", "BALONCESTO", "BASKETBALL", "EUROLIGA",
    "EUROLEAGUE", "WNBA", "G LEAGUE", "LAKERS", "CELTICS", "WARRIORS",
    "BUCKS", "NUGGETS", "HEAT", "SUNS", "MAVERICKS", "CLIPPERS", "KNICKS",
    "76ERS", "SIXERS", "BULLS", "CAVALIERS", "THUNDER", "TIMBERWOLVES",
    "KINGS", "PELICANS", "PACERS", "MAGIC", "HAWKS", "RAPTORS", "NETS",
    "BLAZERS", "JAZZ", "SPURS", "ROCKETS", "PISTONS", "HORNETS", "WIZARDS",
]

KEYWORDS_F1 = [
    "FORMULA 1", "FÓRMULA 1", "F1", "GRAND PRIX", "GRAN PREMIO", "GP ",
    "QUALIFYING", "CLASIFICACION", "CLASIFICACIÓN", "QUALY", "PRACTICE",
    "PRÁCTICA", "FP1", "FP2", "FP3", "SPRINT", "FIA", "MOTOGP", "MOTO GP",
    "NASCAR", "INDYCAR",
]

KEYWORDS_OTROS_ESTRICTO = [
    "NFL", "MLB", "NHL", "BASEBALL", "BÉISBOL", "BEISBOL", "HOCKEY",
    "FOOTBALL AMERICANO", "AMERICAN FOOTBALL",
]


def normalizar(texto: str) -> str:
    if not texto:
        return ""
    mapa = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNAEIOUUN")
    return re.sub(r"\s+", " ", texto.translate(mapa).upper()).strip()


def clasificar_evento(titulo: str, torneo: str = "") -> str:
    txt = normalizar(f"{titulo or ''} {torneo or ''}")
    if not txt:
        return "descartado"

    if re.search(r"\bF1\b|\bFORMULA\s*1\b|\bFÓRMULA\s*1\b", txt) or any(k in txt for k in KEYWORDS_F1):
        return "f1"

    if re.search(r"\bNBA\b|\bBASKET\b|\bBÁSQUET\b|\bBALONCESTO\b", txt) or any(k in txt for k in KEYWORDS_NBA):
        return "nba"

    if re.search(r"\bNFL\b|\bMLB\b|\bNHL\b", txt) or any(k in txt for k in KEYWORDS_OTROS_ESTRICTO):
        return "otros"

    if re.search(r"\bFUTBOL\b|\bFÚTBOL\b|\bSOCCER\b", txt) or any(k in txt for k in KEYWORDS_FUTBOL):
        return "futbol"

    return "futbol"


def normalizar_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("http://"):
        u = "https://" + u[7:]
    if not u.startswith("https://"):
        return ""
    return u


def cargar_previos(nombre_archivo: str) -> list:
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


def guardar_json(nombre_archivo: str, deporte: str, eventos: list) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "deporte": deporte,
        "actualizado_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(eventos),
        "eventos": eventos,
    }
    contenido = json.dumps(payload, ensure_ascii=False, indent=2)
    (OUTPUT_DIR / nombre_archivo).write_text(contenido, encoding="utf-8")
    return contenido


def subir_github(ruta_repo: str, contenido_str: str, mensaje_commit: str) -> None:
    if not GITHUB_TOKEN or not GITHUB_USER or not GITHUB_REPO:
        print(f"[INFO] Sin GITHUB_TOKEN; guardado local en {ruta_repo}")
        return

    ruta_enc = urllib.parse.quote(ruta_repo.strip("/"))
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{ruta_enc}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "UNREALMAT-Scraper/3.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    sha = None
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            sha = json.loads(resp.read().decode("utf-8")).get("sha")
    except Exception:
        sha = None

    body = {
        "message": mensaje_commit,
        "content": base64.b64encode(contenido_str.encode("utf-8")).decode("ascii"),
        "branch": "main",
    }
    if sha:
        body["sha"] = sha

    try:
        req_put = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req_put, timeout=20) as resp_put:
            if resp_put.status in (200, 201):
                print(f"[OK] Subido a GitHub: {ruta_repo}")
    except Exception as exc:
        print(f"[WARN] Error subiendo {ruta_repo}: {exc}")


async def extraer_de_url(page, base_url: str) -> list:
    await page.goto(base_url, wait_until="networkidle", timeout=40000)
    await page.wait_for_timeout(3000)

    raw = await page.evaluate(
        """
        () => {
            const origin = window.location.origin;
            const out = [];
            const seen = new Set();

            // Buscar enlaces internos o de canales que parezcan eventos/transmisiones
            const links = Array.from(document.querySelectorAll('a[href]'));
            for (const a of links) {
                const href = a.href || '';
                if (!href || href.startsWith('javascript:') || href.endsWith('#')) continue;
                const parent = a.closest('tr, li, article, .match, .evento, .event, .row, .card, .item, div') || a.parentElement;
                const textoBloque = ((parent && parent.innerText) || a.innerText || '').trim();
                if (!textoBloque || textoBloque.length < 4 || textoBloque.length > 600) continue;

                const lineas = textoBloque.split(/\\r?\\n/).map(s => s.trim()).filter(Boolean);
                const titulo = (a.innerText || '').trim().length >= 4 ? (a.innerText || '').trim() : lineas[0];
                if (!titulo || titulo.length < 3) continue;

                const clave = `${titulo.toUpperCase()}|${href}`;
                if (seen.has(clave)) continue;
                seen.add(clave);

                out.push({
                    titulo,
                    bloque: textoBloque,
                    url: href,
                    nombreCanal: (a.innerText || a.getAttribute('title') || 'Canal').trim(),
                    mismoOrigen: href.startsWith(origin)
                });
            }
            return out;
        }
        """
    )

    agrupados_por_evento = {}
    for item in raw:
        url_norm = normalizar_url(item.get("url", ""))
        if not url_norm:
            continue

        lineas = [l.strip() for l in (item.get("bloque") or "").splitlines() if l.strip()]
        titulo = (item.get("titulo") or (lineas[0] if lineas else "Evento")).strip()
        torneo = lineas[1] if len(lineas) > 1 and lineas[1] != titulo else ""
        hora_m = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", " ".join(lineas))
        hora = hora_m.group(0) if hora_m else "00:00"
        if len(hora) == 4:
            hora = "0" + hora

        clave_ev = re.sub(r"[^A-Z0-9]", "", normalizar(titulo))
        if not clave_ev:
            continue

        nombre_srv = (item.get("nombreCanal") or "Opción").strip()
        if len(nombre_srv) > 28 or normalizar(nombre_srv) == normalizar(titulo):
            nombre_srv = "Canal"

        if clave_ev not in agrupados_por_evento:
            agrupados_por_evento[clave_ev] = {
                "titulo": titulo,
                "torneo": torneo,
                "fecha_completa": "",
                "hora": hora,
                "status": "EN VIVO",
                "servidores": [{"nombre": nombre_srv, "url": url_norm}],
            }
        else:
            srvs = agrupados_por_evento[clave_ev]["servidores"]
            if not any(s["url"] == url_norm for s in srvs):
                srvs.append({"nombre": f"Opción {len(srvs) + 1}" if nombre_srv == "Canal" else nombre_srv, "url": url_norm})

    return list(agrupados_por_evento.values())


async def recolectar() -> dict:
    por_deporte = {"futbol": [], "nba": [], "f1": [], "otros": []}

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
                eventos = await extraer_de_url(page, base_url)
                print(f"[SCRAPE] {len(eventos)} eventos detectados en {base_url}")
                for ev in eventos:
                    cat = clasificar_evento(ev.get("titulo", ""), ev.get("torneo", ""))
                    if cat in por_deporte:
                        por_deporte[cat].append(ev)
            except Exception as exc:
                print(f"[WARN] Error en {base_url}: {exc}")

        await browser.close()

    return por_deporte


def ejecutar() -> None:
    inicio = time.time()
    datos = asyncio.run(recolectar())
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    destinos = [
        ("futbol", "agenda_futbol.json", "FUTBOL"),
        ("nba", "agenda_nba.json", "NBA"),
        ("f1", "agenda_f1.json", "F1"),
    ]

    for clave, archivo, etiqueta in destinos:
        lista = datos.get(clave, [])
        if len(lista) == 0:
            previos = cargar_previos(archivo)
            if len(previos) > 0:
                lista = previos
                print(f"[INFO] {archivo}: 0 nuevos, se mantienen {len(previos)} eventos anteriores")

        contenido = guardar_json(archivo, etiqueta, lista)
        subir_github(f"output/{archivo}", contenido, f"chore: actualizar {archivo} ({ts})")

    print(
        f"[RESUMEN] Fútbol: {len(datos['futbol'])} | NBA: {len(datos['nba'])} | "
        f"F1: {len(datos['f1'])} | Otros: {len(datos['otros'])} | Tiempo: {time.time() - inicio:.1f}s"
    )


if __name__ == "__main__":
    ejecutar()
