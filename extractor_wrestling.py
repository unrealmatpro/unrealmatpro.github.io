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
TIMEOUT_MS = 45000 

LOG = logging.getLogger("wrestling")
LOG.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
LOG.addHandler(sh)

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
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        try:
            context = await browser.new_context(user_agent=UA)
            page = await context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            await page.wait_for_timeout(8000)

            soup = BeautifulSoup(await page.content(), "lxml")
            
            # NUEVA LÓGICA: Escaneo secuencial (Títulos y Links en el orden del DOM)
            events = {}
            current_title = None
            current_brand = None
            
            for tag in soup.find_all(["span", "a"]):
                if tag.name == "span":
                    style = tag.get("style", "")
                    if "font-size: 25px" in style or "font-size:25px" in style:
                        raw_title = tag.text.strip()
                        titulo_limpio = re.sub(r"^(Adfree|Live|Watch)\s+", "", raw_title, flags=re.IGNORECASE)
                        titulo_limpio = re.sub(r"\s+(Live|Source\s+\d+)$", "", titulo_limpio, flags=re.IGNORECASE).strip()
                        marca = clasificar_marca(titulo_limpio)
                        
                        if marca != "OTHER":
                            current_title = titulo_limpio
                            current_brand = marca
                            if current_title not in events:
                                events[current_title] = {"titulo": current_title, "torneo": current_brand, "live": [], "replay": []}
                        else:
                            current_title = None
                
                elif tag.name == "a" and current_title:
                    href = tag.get("href")
                    if not href: continue
                    texto = tag.text.strip()
                    tipo = "m3u8" if ".m3u8" in href else "iframe"
                    
                    # Clasificar link
                    if any(k in texto for k in ["CatchUp", "Stream", "Live", "Direct"]):
                        events[current_title]["live"].append({"nombre": texto, "url": href, "tipo": tipo})
                    elif any(k in texto for k in ["Part", "PvP", "Fullshow", "Download"]):
                        events[current_title]["replay"].append({"nombre": texto, "url": href, "tipo": tipo})

            # Convertir diccionario a lista para el JSON
            lista_final = []
            idx = 0
            for titulo, data in events.items():
                if data["live"]:
                    # Agregamos los links fijos en español
                    for sl in SPANISH_LINKS:
                        data["live"].append(sl)
                    lista_final.append({
                        "id": f"wr_live_{idx}", "titulo": data["titulo"], "torneo": data["torneo"],
                        "tipo": "EN VIVO", "servidores": data["live"]
                    })
                    idx += 1
                
                if data["replay"]:
                    # Ordenar repeticiones (FHD > HD > PvP > Part)
                    data["replay"].sort(key=lambda x: (0 if "FHD" in x["nombre"].upper() else (1 if "HD" in x["nombre"].upper() else (2 if "PVP" in x["nombre"].upper() else 3))))
                    lista_final.append({
                        "id": f"wr_replay_{idx}", "titulo": data["titulo"], "torneo": data["torneo"],
                        "tipo": "REPLAY", "servidores": data["replay"]
                    })
                    idx += 1

            await context.close()
            return lista_final
            
        except Exception as e:
            LOG.error(f"Error scrapeando: {e}")
            return []
        finally:
            await browser.close()

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
    
    if not eventos:
        LOG.warning("No se encontraron eventos en 1max.top. Usando fallback con enlaces en español.")
        eventos.append({
            "id": "wr_fallback_live", "titulo": "SEÑALES DE WRESTLING (ESPAÑOL)", "torneo": "WWE",
            "tipo": "EN VIVO", "servidores": SPANISH_LINKS
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
