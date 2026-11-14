#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio, base64, json, logging, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://1max.top/"
LOCAL_OUT = Path(__file__).parent / "output_local_wrestling"
LOCAL_OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TIMEOUT_MS = 45000 # Aumentado a 45s por si la web tarda

LOG = logging.getLogger("wrestling")
LOG.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
LOG.addHandler(sh)

# Enlaces fijos en español (se usarán si el scraping de 1max falla o se complementará)
SPANISH_LINKS = [
    { "nombre": "ES: VKVideo", "url": "https://live.vkvideo.ru/app/embed/noobcraftero", "tipo": "iframe" },
    { "nombre": "ES: RingMotif", "url": "https://ringmotif.net/e/jmekma4q2tzcn", "tipo": "iframe" },
    { "nombre": "ES: BozzTV", "url": "https://183.bozztv.com/giatv/giatv-BiblieMatches/BiblieMatches/playlist.m3u8", "tipo": "m3u8" },
    { "nombre": "ES: HLS Stream 1", "url": "https://81j8b6.a737cozfwjmm.net:8443/hls/7i3bhp9zq8spc.m3u8?s=597qVniU09e_UstrppKsww&e=1794638911", "tipo": "m3u8" }
]

def normalizar(texto: str) -> str:
    if not texto: return ""
    import unicodedata
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8").upper().strip()

def clasificar_marca(titulo: str) -> str:
    t = normalizar(titulo)
    if any(k in t for k in ["WWE", "RAW", "SMACKDOWN", "NXT", "CROWN JEWEL", "SURVIVOR", "MONEY IN THE BANK", "ROYAL RUMBLE", "WRESTLEMANIA"]): return "WWE"
    if any(k in t for k in ["AEW", "DYNAMITE", "COLLISION", "RAMPAGE", "FULL GEAR", "ALL IN", "ALL OUT", "REVOLUTION"]): return "AEW"
    if any(k in t for k in ["TNA", "IMPACT", "BOUND FOR GLORY", "HARD TO KILL"]): return "TNA"
    if any(k in t for k in ["NJPW", "WRESTLE KINGDOM", "G1 CLIMAX", "DOMINION"]): return "NJPW"
    return "OTHER"

async def scrape_1max():
    LOG.info(f"Scrapeando: {BASE_URL}")
    eventos = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        try:
            context = await browser.new_context(user_agent=UA)
            page = await context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            await page.wait_for_timeout(8000) # Damos 8 segundos para que cargue todo

            soup = BeautifulSoup(await page.content(), "lxml")
            
            # Buscamos los títulos con el estilo que nos pasaste, o cualquier etiqueta que diga "Live"
            titulos = soup.find_all("span", style=re.compile(r"font-size:\s*25px"))
            
            # Si no encuentra ninguno con el estilo, busca en los H1, H2 o textos destacados
            if not titulos:
                titulos = soup.find_all(lambda tag: tag.name in ["h1", "h2", "h3", "span", "div"] and tag.text and ("LIVE" in tag.text.upper() or "AEW" in tag.text.upper() or "WWE" in tag.text.upper()) and len(tag.text) < 60)

            LOG.info(f"Posibles títulos encontrados: {len(titulos)}")

            for idx, t_tag in enumerate(titulos):
                raw_title = t_tag.text.strip()
                if not raw_title: continue

                # Limpiar título
                titulo_limpio = re.sub(r"^(Adfree|Live|Watch)\s+", "", raw_title, flags=re.IGNORECASE)
                titulo_limpio = re.sub(r"\s+(Live|Source\s+\d+)$", "", titulo_limpio, flags=re.IGNORECASE).strip()
                
                marca = clasificar_marca(titulo_limpio)
                if marca == "OTHER": continue

                servidores_live = []
                servidores_replay = []

                next_node = t_tag.parent.find_next_sibling() if t_tag.parent else t_tag.find_next_sibling()
                
                # Iteramos sobre los siguientes elementos
                count = 0
                while next_node and count < 10: # Límite de 10 elementos para no leer toda la página
                    count += 1
                    if next_node.name == "span" and next_node.get("style") and "25px" in next_node.get("style"):
                        break # Es el siguiente título, nos detenemos

                    links = next_node.find_all("a") if next_node.name != "a" else [next_node]
                    for a in links:
                        href = a.get("href")
                        if not href: continue
                        
                        texto_link = a.text.strip()
                        tipo_link = "m3u8" if ".m3u8" in href else "iframe"
                        
                        if any(k in texto_link for k in ["CatchUp", "Stream", "Live", "Direct"]):
                            servidores_live.append({"nombre": texto_link, "url": href, "tipo": tipo_link})
                        elif any(k in texto_link for k in ["Part", "PvP", "Fullshow", "Download"]):
                            servidores_replay.append({"nombre": texto_link, "url": href, "tipo": tipo_link})
                    
                    next_node = next_node.find_next_sibling()

                # Agregar links de español a los eventos en vivo
                if servidores_live:
                    for sl in SPANISH_LINKS:
                        servidores_live.append(sl)
                        
                    eventos.append({
                        "id": f"wr_live_{idx}", "titulo": titulo_limpio, "torneo": marca,
                        "tipo": "EN VIVO", "servidores": servidores_live
                    })
                
                if servidores_replay:
                    eventos.append({
                        "id": f"wr_replay_{idx}", "titulo": titulo_limpio, "torneo": marca,
                        "tipo": "REPLAY", "servidores": servidores_replay
                    })
                    
            await context.close()
        except Exception as e:
            LOG.error(f"Error scrapeando: {e}")
        finally:
            await browser.close()
            
    return eventos

def subir_github(token: str, user: str, repo: str, path_repo: str, contenido: str) -> bool:
    api = f"https://api.github.com/repos/{user}/{repo}/contents/{path_repo}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    r = requests.get(api, headers=headers, timeout=20)
    sha = r.json().get("sha") if r.status_code == 200 else None
    data = {"message": f"chore: update wrestling", "content": base64.b64encode(contenido.encode()).decode(), "branch": "main"}
    if sha: data["sha"] = sha
    resp = requests.put(api, headers=headers, json=data, timeout=30)
    return resp.status_code in (200, 201)

async def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token: sys.exit(1)
    
    repo_full = os.environ.get("GITHUB_REPOSITORY", "unrealmatpro/unrealmatpro.github.io")
    user, repo = repo_full.split("/")

    eventos = await scrape_1max()
    
    # FALLBACK: Si no se encontraron eventos (por bloqueo o cambios), inyectamos un evento genérico
    # para que el blog no se vea vacío y los usuarios puedan usar los links en español.
    if not eventos:
        LOG.warning("No se encontraron eventos en 1max.top. Usando fallback con enlaces en español.")
        eventos.append({
            "id": "wr_fallback_live",
            "titulo": "SEÑALES DE WRESTLING (ESPAÑOL)",
            "torneo": "WWE",
            "tipo": "EN VIVO",
            "servidores": SPANISH_LINKS
        })

    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {"fecha_actualizacion": ahora, "total": len(eventos), "eventos": eventos}
    
    ok = subir_github(token, user, repo, "output/agenda_wrestling.json", json.dumps(payload, ensure_ascii=False, indent=2))
    if ok:
        LOG.info(f"✅ Subido agenda_wrestling.json ({len(eventos)} eventos)")
    else:
        LOG.error("❌ Falló subida de agenda_wrestling.json")
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
