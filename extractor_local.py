#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio, base64, json, logging, os, re, sys, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Tuple
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Dominios base a escanear
BASE_URLS = ["https://streamxhd.com/", "https://streamxhd.st/", "https://streamxhd.click/", "https://streamxhd.sbs/"]
LOCAL_OUT = Path(__file__).parent / "output"
LOCAL_OUT.mkdir(exist_ok=True)
DEBUG_DIR = Path(__file__).parent / "output_debug"
DEBUG_DIR.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TIMEOUT_MS = 30000
WAIT_AFTER_LOAD = 5000

CANALES_NOMBRES = {
    "disney": "DISNEY+", "disney1": "DISNEY+ 1", "disney2": "DISNEY+ 2", "disney3": "DISNEY+ 3", "disney4": "DISNEY+ 4", "disney5": "DISNEY+ 5", "disney6": "DISNEY+ 6", "disney7": "DISNEY+ 7", "disney8": "DISNEY+ 8", "disney9": "DISNEY+ 9", "disney10": "DISNEY+ 10", "disney11": "DISNEY+ 11", "disney12": "DISNEY+ 12", "disney13": "DISNEY+ 13", "disney14": "DISNEY+ 14", "disney15": "DISNEY+ 15", "disney16": "DISNEY+ 16",
    "espn": "ESPN", "espn2": "ESPN 2", "espn3": "ESPN 3", "espn4": "ESPN 4", "espn5": "ESPN 5", "espn6": "ESPN 6", "espn7": "ESPN 7", "espn2ar": "ESPN 2 AR", "espnar": "ESPN AR", "espnpremium": "ESPN PREMIUM", "espnplus1": "ESPN +", "espnplus2": "ESPN + 2", "espndeportes": "ESPN DEPORTES",
    "fox1ar": "FOX SPORTS 1 AR", "fox2ar": "FOX SPORTS 2 AR", "fox3ar": "FOX SPORTS 3 AR", "foxone": "FOX ONE", "fox_deportes_usa": "FOX DEPORTES USA",
    "l1max": "LIGA 1 MAX", "max1": "MAX 1", "max2": "MAX 2", "premiere1": "PREMIERE 1", "premiere2": "PREMIERE 2", "tigo1": "TIGO SPORTS 1", "tudn_usa": "TUDN USA", "winplus": "WIN SPORTS +", "winsports": "WIN SPORTS", "zapping_ec": "ZAPPING EC", "vix1": "VIX 1",
    "nba": "NBA TV", "nba1": "NBA LEAGUE PASS 1", "nba2": "NBA LEAGUE PASS 2", "nba3": "NBA LEAGUE PASS 3", "nba4": "NBA LEAGUE PASS 4", "nba5": "NBA LEAGUE PASS 5", "nba6": "NBA LEAGUE PASS 6", "nba7": "NBA LEAGUE PASS 7", "nba8": "NBA LEAGUE PASS 8", "nba9": "NBA LEAGUE PASS 9",
    "amazon1": "PRIME VIDEO 1", "amazon2": "PRIME VIDEO 2", "dsports": "DSPORTS", "daznlaliga": "DAZN LALIGA", "sporttvbr1": "SPORTV 1", "sporttvbr3": "SPORTV 3", "fanatiz1": "FANATIZ 1", "universo": "UNIVERSO", "tntsports": "TNT SPORTS", "laligahypermotion": "LALIGA HYPERMOTION"
}

LOG = logging.getLogger("extractor")
LOG.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
LOG.addHandler(sh)

def normalizar(texto: str) -> str:
    if not texto: return ""
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8").upper().strip()

def clave_dedup(titulo: str, hora: str) -> str:
    t = re.sub(r"[\-–—_,\.\|]+", " ", normalizar(titulo))
    t = re.sub(r"\s+", " ", t).strip()
    return f"{t}__{(hora or '00:00').zfill(5)}"

F1_KEYWORDS = [normalizar(k) for k in ["F1", "FORMULA 1", "MOTOGP", "MOTO GP", "PRACTICA", "FREE PRACTICE", "CLASIFICACION", "QUALY", "SPRINT", "GRAND PRIX", "GRAN PREMIO", "VERSTAPPEN", "HAMILTON", "LECLERC", "SAINZ", "ALONSO", "PEREZ", "RED BULL", "FERRARI", "MCLAREN", "FP1", "FP2", "FP3", "ON BOARD", "COLAPINTO", "QATAR"]]
NBA_KEYWORDS = [normalizar(k) for k in ["NBA", "BASKET", "BALONCESTO", "LAKERS", "CELTICS", "BULLS", "HEAT", "WARRIORS", "BUCKS", "SUNS", "MAVERICKS", "KNICKS", "BLAZERS", "NETS", "76ERS", "SIXERS", "NUGGETS", "CLIPPERS", "SPURS", "ROCKETS", "GRIZZLIES", "PELICANS", "THUNDER", "TIMBERWOLVES", "CAVALIERS", "PISTONS", "PACERS", "HORNETS", "WIZARDS", "MAGIC", "HAWKS", "RAPTORS", "KINGS", "JAZZ"]]
NFL_KEYWORDS = [normalizar(k) for k in ["NFL", "RAVENS", "JAGUARS", "CHIEFS", "PATRIOTS", "COWBOYS", "PACKERS", "49ERS", "EAGLES", "STEELERS", "BRONCOS", "VIKINGS", "BILLS", "DOLPHINS", "LIONS", "BENGALS", "TEXANS", "SEAHAWKS", "FALCONS", "SAINTS", "RAMS", "CHARGERS", "RAIDERS", "BEARS", "COMMANDERS", "BUCCANEERS", "CARDINALS", "TITANS", "COLTS", "GIANTS", "JETS", "PANTHERS", "BROWNS"]]
MLB_KEYWORDS = [normalizar(k) for k in ["MLB", "BASEBALL", "BEISBOL", "YANKEES", "DODGERS", "RED SOX", "METS", "ASTROS", "BRAVES", "PADRES", "PHILLIES", "CUBS", "CARDINALS", "MARINERS", "ORIOLES", "RANGERS", "GUARDIANS", "TWINS", "BREWERS", "BLUE JAYS", "GIANTS", "WHITE SOX", "TIGERS", "ROYALS", "PIRATES", "REDS", "ROCKIES", "DIAMONDBACKS", "ATHLETICS", "ANGELS", "RAYS", "MARLINS", "NATIONALS"]]
NHL_KEYWORDS = [normalizar(k) for k in ["NHL", "HOCKEY", "AVALANCHE", "MAPLE LEAFS", "WILD", "CANADIENS", "CAPITALS", "SENATORS", "DEVILS", "JETS", "PANTHERS", "BLUE JACKETS", "PREDATORS", "ISLANDERS", "SHARKS", "OILERS", "RANGERS", "FLYERS", "CANUCKS", "BRUINS", "LIGHTNING", "STARS", "GOLDEN KNIGHTS", "HURRICANES", "PENGUINS", "BLACKHAWKS", "BLUES", "FLAMES", "KRAKEN", "DUCKS", "COYOTES", "SABRES"]]
UFC_KEYWORDS = [normalizar(k) for k in ["UFC", "MMA", "BOXING", "BOXEO", "PELEA", "FIGHT", "BELLATOR", "PFL", "ONE CHAMPIONSHIP", "CANELO", "MCGREGOR", "MAKHACHEV", "JONES", "NOCHE DE PELEA"]]
WRESTLING_KEYWORDS = [normalizar(k) for k in ["WWE", "AEW", "TNA", "NJPW", "IMPACT", "SMACKDOWN", "RAW", "WRESTLEMANIA", "ROYAL RUMBLE", "SUMMERSLAM", "SURVIVOR SERIES", "DYNAMITE", "RAMPAGE", "COLLISION", "WRESTLING"]]

# ⬇️ REGEX ACTUALIZADO: Captura la URL completa (con dominio) y el path con los parámetros.
# Acepta streamxhd.com, streamxhd1.com, streamxhd2.com, etc.
SERVER_URL_RE = re.compile(r"(https?://streamxhd\d*\.[a-z]+/(?:live\d*\.php\?[^\s\"'<>]+))")
GENERIC_STREAM_RE = re.compile(r"(https?://streamxhd\d*\.[a-z]+/[^\s\"'<>]+\.php\?[^\s\"'<>]+)")

def extraer_stream_id(full_url: str) -> str:
    """Extrae el ID de canal (stream=xxx) de una URL."""
    try:
        qs = full_url.split("?")[1] if "?" in full_url else ""
        for part in qs.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                if k in ("stream", "channel", "id"):
                    return v.lower()
        return full_url.split("/")[-1].split("?")[0].lower()
    except Exception:
        return ""

async def _scrape_url(url: str) -> List[Dict]:
    eventos: List[Dict] = []
    stats = {"total_articles": 0, "sin_titulo": 0, "sin_servidores": 0, "ok": 0}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = await browser.new_context(user_agent=UA, locale="es-ES")
            page = await context.new_page()
            LOG.info(f"Probando: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            await page.wait_for_timeout(WAIT_AFTER_LOAD)

            html_content = await page.content()
            soup = BeautifulSoup(html_content, "lxml")
            articles = soup.find_all("article", class_="event")
            stats["total_articles"] = len(articles)
            LOG.info(f"Encontrados {len(articles)} partidos válidos en {url}")

            for idx, art in enumerate(articles):
                event_id = art.get("data-event-card")
                meta_text = ""
                if event_id:
                    try:
                        meta_text = base64.b64decode(event_id).decode('utf-8', errors='ignore')
                    except Exception:
                        pass

                # ==== TÍTULO ====
                titulo = None
                h2 = art.find("h2", class_="event-title")
                if h2 and h2.text.strip():
                    titulo = h2.text.strip()
                if not titulo:
                    any_h2 = art.find("h2")
                    if any_h2 and any_h2.text.strip():
                        titulo = any_h2.text.strip()
                if not titulo and meta_text:
                    partes = meta_text.split('|')
                    if len(partes) > 0 and partes[0].strip():
                        titulo = partes[0].strip()
                if not titulo:
                    name_div = art.find(class_="compact-list-name")
                    if name_div and name_div.text.strip():
                        titulo = name_div.text.strip()

                if not titulo or len(titulo) < 3:
                    stats["sin_titulo"] += 1
                    continue

                # ==== FECHA/HORA ====
                time_div = art.find("div", class_="event-time") or art.find("span", class_="compact-list-time")
                fecha_completa = None
                time_str = "00:00"
                if time_div:
                    raw_date = time_div.get("data-full-time") or time_div.get("data-time")
                    if raw_date:
                        if "T" in raw_date:
                            fecha_completa = raw_date
                            if not ("+" in raw_date or "-" in raw_date.split("T")[1]):
                                fecha_completa += "-05:00"
                        else:
                            fecha_completa = raw_date.replace(" ", "T") + ":00-05:00"
                    match = re.search(r"(\d{1,2}:\d{2})", time_div.text)
                    if match:
                        time_str = match.group(1).zfill(5)

                # ==== STATUS ====
                status_elem = art.find(class_="status") or art.find(class_="compact-list-status")
                status_text = status_elem.text.strip().upper() if status_elem else "PRONTO"
                if "VIVO" in status_text: status_text = "EN VIVO"
                elif "FINAL" in status_text: status_text = "FINALIZADO"
                elif "PRONTO" in status_text: status_text = "PRONTO"

                # ==== TORNEO ====
                torneo = "DEPORTE"
                if meta_text:
                    partes = meta_text.split('|')
                    if len(partes) >= 4:
                        torneo = partes[-1]
                if torneo == "DEPORTE":
                    league_tag = art.find("span", class_="compact-list-league")
                    if league_tag: torneo = league_tag.text.strip()

                # ==== SPORT HINT ====
                sport_hint = ""
                for tag in art.find_all("span", class_="tag"):
                    tag_txt = tag.text.strip()
                    if "Football" in tag_txt or "Soccer" in tag_txt: sport_hint = "FUTBOL"
                    elif "Basketball" in tag_txt: sport_hint = "NBA"
                    elif "Hockey" in tag_txt: sport_hint = "NHL"
                    elif "Baseball" in tag_txt: sport_hint = "MLB"
                    elif "NFL" in tag_txt or "American Football" in tag_txt: sport_hint = "NFL"
                    elif "Racing" in tag_txt or "Motor" in tag_txt or "Formula" in tag_txt: sport_hint = "F1"
                    elif "Wrestling" in tag_txt: sport_hint = "WRESTLING"
                    elif "MMA" in tag_txt or "UFC" in tag_txt or "Fight" in tag_txt: sport_hint = "UFC"

                # ==== SERVIDORES (3 estrategias en orden) ====
                servidores = []
                seen = set()

                # Estrategia 1: div.compact-server-row (contiene nombre + url + botones)
                rows = art.find_all("div", class_="compact-server-row")
                for row in rows:
                    name_div = row.find("div", class_="compact-server-name")
                    name = ""
                    if name_div:
                        name = name_div.get("title") or name_div.text.strip()
                        # Limpiar el número inicial (ej: "1 Disney +" → "Disney +")
                        name = re.sub(r"^\d+\s*", "", name).strip()

                    url_div = row.find("div", class_="compact-server-url")
                    stream_url = ""
                    if url_div:
                        stream_url = url_div.get("title") or url_div.text.strip()

                    btn = row.find("button", class_="compact-server-action")
                    if not stream_url and btn:
                        stream_url = btn.get("data-url") or btn.get("data-copy") or ""

                    if stream_url and "streamxhd" in stream_url:
                        # Buscamos la URL completa
                        m = SERVER_URL_RE.search(stream_url) or GENERIC_STREAM_RE.search(stream_url)
                        if m:
                            full_url = m.group(1) # Ahora captura el grupo 1 que es la URL completa
                            stream_id = extraer_stream_id(full_url)
                            display_name = name if name else CANALES_NOMBRES.get(stream_id, stream_id.upper())
                            if full_url not in seen:
                                seen.add(full_url)
                                servidores.append({"nombre": display_name, "url": full_url})

                # Estrategia 2: botones con data-url / data-copy
                if not servidores:
                    for btn in art.find_all("button", class_="compact-server-action") + art.find_all("button", class_="server"):
                        stream_url = btn.get("data-url") or btn.get("data-copy") or ""
                        if "iframe" in stream_url or "<" in stream_url:
                            m = re.search(r'src=["\']([^"\']+)["\']', stream_url)
                            if m: stream_url = m.group(1)
                        if stream_url and "streamxhd" in stream_url:
                            m = SERVER_URL_RE.search(stream_url) or GENERIC_STREAM_RE.search(stream_url)
                            if m:
                                full_url = m.group(1)
                                stream_id = extraer_stream_id(full_url)
                                if full_url not in seen:
                                    seen.add(full_url)
                                    servidores.append({"nombre": CANALES_NOMBRES.get(stream_id, stream_id.upper()), "url": full_url})

                # Estrategia 3: divs .compact-server-url con title o texto
                if not servidores:
                    for srv_div in art.find_all("div", class_="compact-server-url"):
                        stream_url = srv_div.get("title") or srv_div.text.strip()
                        if stream_url and "streamxhd" in stream_url:
                            m = SERVER_URL_RE.search(stream_url) or GENERIC_STREAM_RE.search(stream_url)
                            if m:
                                full_url = m.group(1)
                                stream_id = extraer_stream_id(full_url)
                                if full_url not in seen:
                                    seen.add(full_url)
                                    servidores.append({"nombre": CANALES_NOMBRES.get(stream_id, stream_id.upper()), "url": full_url})

                # REGLA DE ORO: descartar sin servidores
                if not servidores:
                    stats["sin_servidores"] += 1
                    continue

                stats["ok"] += 1
                eventos.append({
                    "id": f"evt_{idx}",
                    "titulo": titulo,
                    "hora": time_str,
                    "fecha_completa": fecha_completa,
                    "status": status_text,
                    "servidores": servidores,
                    "torneo": torneo,
                    "sport_hint": sport_hint,
                    "source": "json"
                })

            if eventos:
                LOG.info(f"✅ {url}: {stats['ok']} eventos válidos (descartados: {stats['sin_titulo']} sin título, {stats['sin_servidores']} sin servidores)")
                return eventos

            LOG.warning(f"⚠️ {url}: 0 eventos válidos. Stats: {stats}")
            debug_file = DEBUG_DIR / f"debug_{url.replace('https://','').replace('/','_').replace('.','_')}.html"
            try:
                debug_file.write_text(html_content, encoding="utf-8")
                LOG.warning(f"📄 HTML guardado en {debug_file}")
            except Exception as e:
                LOG.error(f"No se pudo guardar HTML de debug: {e}")

            await context.close()
        except Exception as e:
            LOG.error(f"Error en {url}: {e}")
        finally:
            await browser.close()
    return eventos

async def obtener_eventos() -> List[Dict]:
    todos_los_eventos = []
    # Iteramos sobre TODAS las URLs base para recopilar eventos de todas
    for url in BASE_URLS:
        try:
            LOG.info(f"--- Iniciando scraping en {url} ---")
            eventos = await _scrape_url(url)
            if eventos:
                todos_los_eventos.extend(eventos)
                LOG.info(f"Se agregaron {len(eventos)} eventos de {url}")
            else:
                LOG.warning(f"No se encontraron eventos en {url}")
        except Exception as e:
            LOG.error(f"Fallo total en {url}: {e}")
    
    # La deduplicación se encargará de fusionar los eventos repetidos y agregar los servidores faltantes
    return todos_los_eventos

def deduplicar_eventos(eventos: List[Dict]) -> List[Dict]:
    dedup: Dict[str, Dict] = {}
    for e in eventos:
        clave = clave_dedup(e["titulo"], e["hora"])
        if clave not in dedup:
            dedup[clave] = e
        else:
            # Si el evento ya existe, fusionamos los servidores
            urls_vistas = {s["url"] for s in dedup[clave]["servidores"]}
            for srv in e["servidores"]:
                if srv["url"] not in urls_vistas: 
                    dedup[clave]["servidores"].append(srv)
            
            # Actualizamos el estado si es más relevante (EN VIVO > PRONTO > FINALIZADO)
            if e["status"] == "EN VIVO": 
                dedup[clave]["status"] = "EN VIVO"
            elif e["status"] == "PRONTO" and dedup[clave]["status"] == "FINALIZADO": 
                dedup[clave]["status"] = "PRONTO"
                
    return list(dedup.values())

def clasificar_evento(titulo: str, torneo: str, sport_hint: str) -> Tuple[str, str]:
    t = normalizar(titulo)
    torneo_upper = normalizar(torneo)
    hint_upper = normalizar(sport_hint)

    if hint_upper == "F1" or re.search(r"\bF1\b", torneo_upper) or re.search(r"\bF1\b", t) or any(k in t or k in torneo_upper for k in F1_KEYWORDS):
        return "f1", torneo
    if hint_upper == "NBA" or re.search(r"\bNBA\b", torneo_upper) or re.search(r"\bNBA\b", t) or any(k in t or k in torneo_upper for k in NBA_KEYWORDS):
        return "nba", torneo
    if hint_upper == "NFL" or re.search(r"\bNFL\b", torneo_upper) or re.search(r"\bNFL\b", t) or any(k in t or k in torneo_upper for k in NFL_KEYWORDS):
        return "otros", torneo if torneo_upper and torneo_upper != "DEPORTE" else "NFL"
    if hint_upper == "MLB" or re.search(r"\bMLB\b", torneo_upper) or re.search(r"\bMLB\b", t) or any(k in t or k in torneo_upper for k in MLB_KEYWORDS):
        return "otros", torneo if torneo_upper and torneo_upper != "DEPORTE" else "MLB"
    if hint_upper == "NHL" or re.search(r"\bNHL\b", torneo_upper) or re.search(r"\bNHL\b", t) or any(k in t or k in torneo_upper for k in NHL_KEYWORDS):
        return "otros", torneo if torneo_upper and torneo_upper != "DEPORTE" else "NHL"
    if hint_upper == "UFC" or re.search(r"\bUFC\b", torneo_upper) or re.search(r"\bUFC\b", t) or any(k in t or k in torneo_upper for k in UFC_KEYWORDS):
        return "otros", torneo if torneo_upper and torneo_upper != "DEPORTE" else "UFC"
    if hint_upper == "WRESTLING" or re.search(r"\bWWE\b", torneo_upper) or re.search(r"\bWWE\b", t) or any(k in t or k in torneo_upper for k in WRESTLING_KEYWORDS):
        return "otros", torneo if torneo_upper and torneo_upper != "DEPORTE" else "WRESTLING"
    return "futbol", torneo

def clasificar_eventos(eventos: List[Dict]) -> Dict[str, List[Dict]]:
    clasificados = {"futbol": [], "nba": [], "f1": [], "otros": []}
    for e in eventos:
        deporte, torneo_final = clasificar_evento(e["titulo"], e.get("torneo", ""), e.get("sport_hint", ""))
        e["torneo"] = torneo_final
        e["deporte"] = deporte.upper()
        e.pop("sport_hint", None)
        clasificados[deporte].append(e)
    return clasificados

def generar_agenda_all(clasificados: Dict[str, List[Dict]], ahora_iso: str) -> str:
    todos = []
    for deporte, lista in clasificados.items():
        for e in lista:
            ev = dict(e)
            ev["deporte_upper"] = deporte.upper()
            todos.append(ev)
    todos.sort(key=lambda x: x.get("fecha_completa") or "")
    payload = {"fecha_actualizacion": ahora_iso, "total": len(todos), "eventos": todos}
    return json.dumps(payload, ensure_ascii=False, indent=2)

async def main():
    eventos_crudos = await obtener_eventos()
    if not eventos_crudos:
        LOG.error("❌ No se extrajeron eventos válidos.")
        return 1

    eventos = deduplicar_eventos(eventos_crudos)
    clasificados = clasificar_eventos(eventos)
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    LOG.info(f"Clasificación → Fútbol={len(clasificados['futbol'])} NBA={len(clasificados['nba'])} F1={len(clasificados['f1'])} OTROS={len(clasificados['otros'])}")

    for deporte, lista in clasificados.items():
        payload = {"fecha_actualizacion": ahora, "total": len(lista), "eventos": lista}
        contenido_json = json.dumps(payload, ensure_ascii=False, indent=2)
        (LOCAL_OUT / f"agenda_{deporte}.json").write_text(contenido_json, encoding="utf-8")
        LOG.info(f"✅ Guardado agenda_{deporte}.json ({len(lista)} eventos)")

    contenido_all = generar_agenda_all(clasificados, ahora)
    (LOCAL_OUT / "agenda_all.json").write_text(contenido_all, encoding="utf-8")
    LOG.info("✅ Guardado agenda_all.json (unificado)")

    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
