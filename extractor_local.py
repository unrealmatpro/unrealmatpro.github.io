#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import base64
import json
import logging
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URLS = [
    "https://streamxhd.com/",
    "https://streamxhd.st/",
    "https://streamxhd.click/",
    "https://streamxhd.sbs/",
]
LOCAL_OUT = Path(__file__).parent / "output_local"
LOCAL_OUT.mkdir(exist_ok=True)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
TIMEOUT_MS = 30000
WAIT_AFTER_LOAD = 5000

CANALES_NOMBRES = {
    "disney": "DISNEY+",
    "disney1": "DISNEY+ 1", "disney2": "DISNEY+ 2", "disney3": "DISNEY+ 3",
    "disney4": "DISNEY+ 4", "disney5": "DISNEY+ 5", "disney6": "DISNEY+ 6",
    "disney7": "DISNEY+ 7", "disney8": "DISNEY+ 8", "disney9": "DISNEY+ 9",
    "disney10": "DISNEY+ 10", "disney11": "DISNEY+ 11", "disney12": "DISNEY+ 12",
    "disney13": "DISNEY+ 13", "disney14": "DISNEY+ 14", "disney15": "DISNEY+ 15",
    "disney16": "DISNEY+ 16",
    "espn": "ESPN", "espn2": "ESPN 2", "espn3": "ESPN 3", "espn4": "ESPN 4",
    "espn5": "ESPN 5", "espn6": "ESPN 6", "espn7": "ESPN 7",
    "espn2ar": "ESPN 2 AR", "espnar": "ESPN AR", "espnpremium": "ESPN PREMIUM",
    "espnplus1": "ESPN +", "espnplus2": "ESPN + 2", "espndeportes": "ESPN DEPORTES",
    "fox1ar": "FOX SPORTS 1 AR", "fox2ar": "FOX SPORTS 2 AR", "fox3ar": "FOX SPORTS 3 AR",
    "foxone": "FOX ONE", "fox_deportes_usa": "FOX DEPORTES USA",
    "l1max": "LIGA 1 MAX", "max1": "MAX 1", "max2": "MAX 2",
    "premiere1": "PREMIERE 1", "premiere2": "PREMIERE 2", "premiere3": "PREMIERE 3",
    "tigo1": "TIGO SPORTS 1", "tudn_usa": "TUDN USA", "tudnmx": "TUDNMX",
    "canal9mx": "CANAL9MX", "winplus": "WIN SPORTS +", "winsports": "WIN SPORTS",
    "zapping_ec": "ZAPPING EC", "vix1": "VIX 1", "appletv1": "APPLETV1",
    "nba": "NBA TV",
    "nba1": "NBA LEAGUE PASS 1", "nba2": "NBA LEAGUE PASS 2", "nba3": "NBA LEAGUE PASS 3",
    "nba4": "NBA LEAGUE PASS 4", "nba5": "NBA LEAGUE PASS 5", "nba6": "NBA LEAGUE PASS 6",
    "nba7": "NBA LEAGUE PASS 7", "nba8": "NBA LEAGUE PASS 8", "nba9": "NBA LEAGUE PASS 9",
    "nba10": "NBA LEAGUE PASS 10",
    "amazon1": "PRIME VIDEO 1", "amazon2": "PRIME VIDEO 2",
    "dsports": "DSPORTS", "dsportsplus": "DSPORTSPLUS",
    "daznlaliga": "DAZN LALIGA", "sporttvbr1": "SPORTV 1",
    "sporttvbr2": "SPORTV 2", "sporttvbr3": "SPORTV 3",
    "fanatiz1": "FANATIZ 1", "universo": "UNIVERSO",
    "tntsports": "TNT SPORTS", "laligahypermotion": "LALIGA HYPERMOTION",
}

LOG = logging.getLogger("extractor")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    LOG.addHandler(sh)


def normalizar(texto: Optional[str]) -> str:
    if not texto:
        return ""
    return (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ASCII", "ignore")
        .decode("utf-8")
        .upper()
        .strip()
    )


def clave_dedup(titulo: str, hora: str) -> str:
    t = re.sub(r"[\-–—_,\.\|/]+", " ", normalizar(titulo))
    t = re.sub(r"\s+", " ", t).strip()
    return f"{t}__{(hora or '00:00').zfill(5)}"


FUTBOL_KEYWORDS = [
    normalizar(k)
    for k in [
        "FUTBOL", "FOOTBALL", "SOCCER", "CHAMPIONS LEAGUE", "EUROPA LEAGUE",
        "CONFERENCE LEAGUE", "COPA LIBERTADORES", "COPA SUDAMERICANA",
        "PREMIER LEAGUE", "LA LIGA", "LALIGA", "SERIE A", "BUNDESLIGA",
        "LIGUE 1", "BRASILEIRAO", "LIGA ARGENTINA", "LIGA PROFESIONAL",
        "LIGA COLOMBIA", "LIGA ECUADOR", "LIGA MX", "MLS", "MUNDIAL",
        "WORLD CUP", "NATIONS LEAGUE", "COPA AMERICA", "ELIMINATORIAS",
        "COPA DEL REY", "FA CUP", "COPA DE RUSIA", "CHAMPIONSHIP",
        "PRIMERA B", "SUB-17", "SUB-20", "VS",
    ]
]

F1_KEYWORDS = [
    normalizar(k)
    for k in [
        "F1", "FORMULA 1", "FORMULA ONE", "MOTOGP", "MOTO GP", "PRACTICA",
        "FREE PRACTICE", "CLASIFICACION", "QUALIFYING", "QUALY", "SPRINT",
        "GRAND PRIX", "GRAN PREMIO", "VERSTAPPEN", "HAMILTON", "LECLERC",
        "SAINZ", "ALONSO", "PEREZ", "RED BULL", "FERRARI", "MCLAREN",
        "FP1", "FP2", "FP3", "ON BOARD", "COLAPINTO",
    ]
]

NBA_KEYWORDS = [
    normalizar(k)
    for k in [
        "NBA", "BASKETBALL", "BASKET", "BALONCESTO", "LAKERS", "CELTICS",
        "BULLS", "HEAT", "WARRIORS", "BUCKS", "SUNS", "MAVERICKS", "KNICKS",
        "BLAZERS", "NETS", "76ERS", "SIXERS", "NUGGETS", "CLIPPERS", "SPURS",
        "ROCKETS", "GRIZZLIES", "PELICANS", "THUNDER", "TIMBERWOLVES",
        "CAVALIERS", "PISTONS", "PACERS", "HORNETS", "WIZARDS", "MAGIC",
        "HAWKS", "RAPTORS", "KINGS", "JAZZ",
    ]
]

OTROS_KEYWORDS = [
    normalizar(k)
    for k in [
        "NFL", "AMERICAN FOOTBALL", "MLB", "BASEBALL", "BEISBOL",
        "BEISBOL COLOMBIANO", "NHL", "HOCKEY", "TENIS", "TENNIS", "ATP",
        "WTA", "UFC", "BOXEO", "BOXING", "GOLF", "RUGBY", "WRESTLING",
        "WWE", "AEW", "NJPW", "TNA", "PADEL", "VOLEY", "VOLLEYBALL",
        "HANDBALL", "BALONMANO", "CICLISMO", "CYCLING",
    ]
]

SERVER_URL_RE = re.compile(
    r"https?://(?:[a-z0-9\-]+\.)*streamxhd\.[a-z]+/(?:live[0-9]*\.php\?[^\"'\s<>]+|[^\s\"'<>]*(?:stream|id|ch|c)=[A-Za-z0-9_\-]+)",
    re.IGNORECASE,
)


def _normalizar_url_stream(raw_url: str, base_url: str) -> Optional[str]:
    if not raw_url:
        return None
    s = str(raw_url).strip()
    if "iframe" in s.lower() and "<" in s:
        m = re.search(r'src=["\']([^"\']+)["\']', s, re.IGNORECASE)
        if m:
            s = m.group(1).strip()
    if "onclick" in s.lower() or "window.open" in s.lower() or "location" in s.lower():
        m = re.search(
            r"(https?://[^\s\'\")<>]+|/[^\s\'\")<>]*live[0-9]*\.php[^\s\'\")<>]*)",
            s,
            re.IGNORECASE,
        )
        if m:
            s = m.group(1).strip()

    if s.startswith("/"):
        s = urljoin(base_url, s)

    match = SERVER_URL_RE.search(s)
    if match:
        return match.group(0)
    if "streamxhd" in s.lower() and (s.startswith("http://") or s.startswith("https://")):
        return s
    return None


def _extraer_stream_id(url: str) -> str:
    m = re.search(r"(?:stream|id|ch|c)=([A-Za-z0-9_\-]+)", url, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    m_path = re.search(r"/([A-Za-z0-9_\-]+)\.php", url, re.IGNORECASE)
    return m_path.group(1).lower() if m_path else "canal"


def _extraer_servidores(art, base_url: str) -> List[Dict[str, str]]:
    servidores: List[Dict[str, str]] = []
    vistas = set()

    candidatos = art.find_all(["button", "a", "div", "span", "li", "iframe"])

    for el in candidatos:
        clases = " ".join(el.get("class") or []).lower()
        es_candidato_claro = any(
            k in clases
            for k in ["server", "canal", "stream", "opcion", "option", "link", "play", "source"]
        ) or el.name in ("a", "iframe")

        atributos_posibles = [
            el.get("data-url"),
            el.get("data-copy"),
            el.get("data-target"),
            el.get("data-stream"),
            el.get("data-href"),
            el.get("data-src"),
            el.get("data-link"),
            el.get("data-channel"),
            el.get("href") if el.name == "a" else None,
            el.get("src") if el.name == "iframe" else None,
            el.get("onclick"),
        ]

        for attr_val in atributos_posibles:
            if not attr_val:
                continue
            url_limpia = _normalizar_url_stream(attr_val, base_url)
            if not url_limpia or url_limpia in vistas:
                continue
            if not es_candidato_claro and "streamxhd" not in url_limpia.lower():
                continue

            vistas.add(url_limpia)
            stream_id = _extraer_stream_id(url_limpia)
            texto_btn = " ".join(el.get_text(" ", strip=True).split())
            nombre = (
                CANALES_NOMBRES.get(stream_id)
                or (texto_btn.upper() if texto_btn and len(texto_btn) <= 35 else stream_id.upper())
            )
            servidores.append({"nombre": nombre, "url": url_limpia})

    return servidores


async def _scrape_url(url: str) -> List[Dict]:
    eventos: List[Dict] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = await browser.new_context(user_agent=UA, locale="es-ES")
            page = await context.new_page()
            LOG.info(f"Probando: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            await page.wait_for_timeout(WAIT_AFTER_LOAD)

            soup = BeautifulSoup(await page.content(), "lxml")
            articles = soup.find_all("article", class_="event")
            LOG.info(f"Encontrados {len(articles)} partidos válidos en {url}")

            for idx, art in enumerate(articles):
                event_id = art.get("data-event-card")
                meta_text = ""
                if event_id:
                    try:
                        meta_text = base64.b64decode(event_id).decode("utf-8", errors="ignore")
                    except Exception:
                        meta_text = ""

                h2 = art.find(["h2", "h3"], class_=re.compile(r"event-title|title", re.I))
                titulo = h2.get_text(" ", strip=True) if h2 else None
                if (not titulo or len(titulo) < 3) and meta_text:
                    partes = [x.strip() for x in meta_text.split("|") if x.strip()]
                    if partes:
                        titulo = partes[0]

                if not titulo or len(titulo.strip()) < 3:
                    continue
                titulo = " ".join(titulo.split())

                time_div = (
                    art.find("div", class_="event-time")
                    or art.find("span", class_="compact-list-time")
                    or art.find(class_=re.compile(r"time|hora", re.I))
                )
                fecha_completa = None
                time_str = "00:00"
                if time_div:
                    raw_date = (
                        time_div.get("data-full-time")
                        or time_div.get("data-time")
                        or time_div.get("data-timestamp")
                    )
                    if raw_date:
                        raw_date = str(raw_date).strip()
                        if "T" in raw_date:
                            fecha_completa = raw_date
                            if not re.search(r"(Z|[+-]\d{2}:?\d{2})$", raw_date):
                                fecha_completa += "-05:00"
                        elif re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", raw_date):
                            fecha_completa = raw_date.replace(" ", "T")[:16] + ":00-05:00"

                    match = re.search(r"\b(\d{1,2}:\d{2})\b", time_div.get_text(" ", strip=True))
                    if match:
                        time_str = match.group(1).zfill(5)

                status_elem = art.find(class_=re.compile(r"status", re.I))
                status_raw = status_elem.get_text(" ", strip=True).upper() if status_elem else "PRONTO"
                if "VIVO" in status_raw or "LIVE" in status_raw:
                    status_text = "EN VIVO"
                elif "FINAL" in status_raw or "FT" in status_raw:
                    status_text = "FINALIZADO"
                else:
                    status_text = "PRONTO"

                torneo = "DEPORTE"
                if meta_text:
                    partes = [x.strip() for x in meta_text.split("|") if x.strip()]
                    if len(partes) >= 4:
                        torneo = partes[-1]
                if torneo == "DEPORTE":
                    league_tag = art.find(["span", "div"], class_=re.compile(r"league|torneo|comp", re.I))
                    if league_tag and league_tag.get_text(strip=True):
                        torneo = league_tag.get_text(" ", strip=True)

                sport_hint = ""
                for tag in art.find_all(["span", "div"]):
                    tag_txt = normalizar(tag.get_text(" ", strip=True))
                    if not tag_txt or len(tag_txt) > 40:
                        continue
                    if any(w in tag_txt for w in ["FOOTBALL", "SOCCER", "FUTBOL"]):
                        sport_hint = "FUTBOL"
                        break
                    if any(w in tag_txt for w in ["BASKETBALL", "NBA", "BALONCESTO"]):
                        sport_hint = "NBA"
                        break
                    if any(w in tag_txt for w in ["FORMULA", "MOTOR", "RACING", "F1", "MOTOGP"]):
                        sport_hint = "F1"
                        break
                    if any(
                        w in tag_txt
                        for w in ["BASEBALL", "BEISBOL", "MLB", "NFL", "NHL", "TENNIS", "UFC", "BOXING"]
                    ):
                        sport_hint = "OTROS"
                        break

                servidores = _extraer_servidores(art, url)
                if not servidores:
                    continue

                eventos.append(
                    {
                        "id": f"evt_{idx}",
                        "titulo": titulo,
                        "hora": time_str,
                        "fecha_completa": fecha_completa,
                        "status": status_text,
                        "servidores": servidores,
                        "torneo": torneo,
                        "sport_hint": sport_hint,
                    }
                )

            if eventos:
                return eventos
        except Exception as e:
            LOG.error(f"Error en {url}: {e}")
        finally:
            await browser.close()
    return eventos


async def obtener_eventos() -> List[Dict]:
    for url in BASE_URLS:
        try:
            eventos = await _scrape_url(url)
            if eventos:
                return eventos
        except Exception as e:
            LOG.error(f"Fallo total en {url}: {e}")
    return []


def deduplicar_eventos(eventos: List[Dict]) -> List[Dict]:
    prioridad_status = {"EN VIVO": 3, "PRONTO": 2, "FINALIZADO": 1}
    dedup: Dict[str, Dict] = {}
    for e in eventos:
        clave = clave_dedup(e["titulo"], e["hora"])
        if clave not in dedup:
            dedup[clave] = e
        else:
            actual = dedup[clave]
            urls_vistas = {s["url"] for s in actual["servidores"]}
            for srv in e["servidores"]:
                if srv["url"] not in urls_vistas:
                    actual["servidores"].append(srv)
                    urls_vistas.add(srv["url"])
            if prioridad_status.get(e["status"], 0) > prioridad_status.get(actual["status"], 0):
                actual["status"] = e["status"]
            if (not actual.get("fecha_completa")) and e.get("fecha_completa"):
                actual["fecha_completa"] = e["fecha_completa"]
    return list(dedup.values())


def clasificar_evento(titulo: str, torneo: str, sport_hint: str) -> Tuple[str, str]:
    t = normalizar(titulo)
    torneo_upper = normalizar(torneo)
    hint_upper = normalizar(sport_hint)

    if (
        hint_upper == "F1"
        or re.search(r"\bF1\b", torneo_upper)
        or re.search(r"\bF1\b", t)
        or any(k in t or k in torneo_upper for k in F1_KEYWORDS)
    ):
        return "f1", torneo

    if (
        hint_upper == "NBA"
        or re.search(r"\bNBA\b", torneo_upper)
        or re.search(r"\bNBA\b", t)
        or any(k in t or k in torneo_upper for k in NBA_KEYWORDS)
    ):
        return "nba", torneo

    if hint_upper == "OTROS" or any(k in t or k in torneo_upper for k in OTROS_KEYWORDS):
        return "otros", torneo if torneo_upper and torneo_upper != "DEPORTE" else "OTROS"

    if hint_upper == "FUTBOL" or any(k in t or k in torneo_upper for k in FUTBOL_KEYWORDS):
        return "futbol", torneo

    return "otros", torneo if torneo_upper and torneo_upper != "DEPORTE" else "OTROS"


def clasificar_eventos(eventos: List[Dict]) -> Dict[str, List[Dict]]:
    clasificados: Dict[str, List[Dict]] = {"futbol": [], "nba": [], "f1": [], "otros": []}
    claves_asignadas = set()

    for e in eventos:
        deporte, torneo_final = clasificar_evento(
            e["titulo"], e.get("torneo", ""), e.get("sport_hint", "")
        )
        clave_unica = f"{deporte}:{clave_dedup(e['titulo'], e['hora'])}"
        if clave_unica in claves_asignadas:
            continue
        claves_asignadas.add(clave_unica)

        copia = dict(e)
        copia["torneo"] = torneo_final
        copia["deporte"] = deporte.upper()
        copia.pop("sport_hint", None)
        clasificados[deporte].append(copia)

    return clasificados


def subir_github(token: str, user: str, repo: str, path_repo: str, contenido: str) -> bool:
    api = f"https://api.github.com/repos/{user}/{repo}/contents/{path_repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        r = requests.get(api, headers=headers, timeout=20)
        sha = r.json().get("sha") if r.status_code == 200 else None
        data = {
            "message": f"chore: update {path_repo}",
            "content": base64.b64encode(contenido.encode("utf-8")).decode("ascii"),
            "branch": "main",
        }
        if sha:
            data["sha"] = sha
        resp = requests.put(api, headers=headers, json=data, timeout=30)
        ok = resp.status_code in (200, 201)
        if not ok:
            LOG.warning(f"No se pudo subir {path_repo} (HTTP {resp.status_code}): {resp.text[:200]}")
        return ok
    except Exception as exc:
        LOG.error(f"Error subiendo {path_repo} a GitHub: {exc}")
        return False


async def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        LOG.error("Falta GITHUB_TOKEN o GH_TOKEN en el entorno.")
        return 1

    repo_full = os.environ.get("GITHUB_REPOSITORY", "unrealmatpro/unrealmatpro.github.io")
    if "/" not in repo_full:
        LOG.error(f"GITHUB_REPOSITORY inválido: {repo_full}")
        return 1
    user, repo = repo_full.split("/", 1)

    eventos_crudos = await obtener_eventos()
    if not eventos_crudos:
        LOG.error("❌ No se extrajeron eventos válidos.")
        return 1

    eventos = deduplicar_eventos(eventos_crudos)
    clasificados = clasificar_eventos(eventos)
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    LOG.info(
        f"Clasificación → Fútbol={len(clasificados['futbol'])} "
        f"NBA={len(clasificados['nba'])} "
        f"F1={len(clasificados['f1'])} "
        f"OTROS={len(clasificados['otros'])}"
    )

    for deporte, lista in clasificados.items():
        payload = {
            "fecha_actualizacion": ahora,
            "total": len(lista),
            "eventos": lista,
        }
        contenido_json = json.dumps(payload, ensure_ascii=False, indent=2)
        (LOCAL_OUT / f"agenda_{deporte}.json").write_text(contenido_json, encoding="utf-8")
        subir_github(token, user, repo, f"output/agenda_{deporte}.json", contenido_json)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
