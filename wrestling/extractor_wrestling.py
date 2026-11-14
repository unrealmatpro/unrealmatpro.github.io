#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio, base64, json, logging, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ─── CONFIGURACIÓN ───
BASE_URL = "https://1max.top/"
LOCAL_OUT = Path(__file__).parent / "output_local_wrestling"
LOCAL_OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TIMEOUT_MS = 30000

LOG = logging.getLogger("wrestling")
LOG.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
LOG.addHandler(sh)

# Enlaces fijos en español (proporcionados por el usuario)
# Puedes agregar más aquí en el futuro y se asignarán al evento que coincida
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
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = await browser.new_context(user_agent=UA)
            page = await context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            await page.wait_for_timeout(5000)

            soup = BeautifulSoup(await page.content(), "lxml")
            
            # Buscamos los títulos con el estilo que nos pasaste
            titulos = soup.find_all("span", style=re.compile(r"font-size:\s*25px"))
            
            for idx, t_tag in enumerate(titulos):
                raw_title = t_tag.text.strip()
                if not raw_title: continue

                # Limpiar título (quitar "Adfree", "Live", "Source 1", etc.)
                titulo_limpio = re.sub(r"^(Adfree|Live|Watch)\s+", "", raw_title, flags=re.IGNORECASE)
                titulo_limpio = re.sub(r"\s+(Live|Source\s+\d+)$", "", titulo_limpio, flags=re.IGNORECASE).strip()
                
                marca = clasificar_marca(titulo_limpio)
                if marca == "OTHER": continue # Omitimos si no es de las 4 marcas

                servidores_live = []
                servidores_replay = []

                # Buscar todos los enlaces (a) hasta el próximo título
                next_node = t_tag.parent.find_next_sibling()
                while next_node and not (next_node.name == "span" and next_node.get("style") and "25px" in next_node.get("style")):
                    # Si es un enlace directo o un contenedor de enlaces
                    links = next_node.find_all("a") if next_node.name != "a" else [next_node]
                    for a in links:
                        href = a.get("href")
                        if not href: continue
                        
                        texto_link = a.text.strip()
                        tipo_link = "m3u8" if ".m3u8" in href else "iframe"
                        
                        # Clasificación según el texto
                        if any(k in texto_link for k in ["CatchUp", "Stream", "Live", "Direct"]):
                            servidores_live.append({"nombre": texto_link, "url": href, "tipo": tipo_link})
                        elif any(k in texto_link for k in ["Part", "PvP", "Fullshow", "Download"]):
                            servidores_replay.append({"nombre": texto_link, "url": href, "tipo": tipo_link})
                    
                    next_node = next_node.find_next_sibling()

                # Ordenar repeticiones (Prioridad: FHD > HD > PvP > Part)
                def score_replay(s):
                    n = s["nombre"].upper()
                    if "FHD" in n and "FULLSHOW" in n: return 1
                    if "HD" in n and "FULLSHOW" in n: return 2
                    if "PVP" in n: return 3
                    if "PART" in n: return 4
                    return 5
                servidores_replay.sort(key=score_replay)

                # Si hay links en vivo, agregamos el evento
                if servidores_live:
                    # Agregamos los links fijos de español a TODOS los eventos en vivo por ahora
                    # En un futuro se podría hacer un match inteligente
                    if marca in ["WWE", "AEW", "TNA", "NJPW"]:
                         for sl in SPANISH_LINKS:
                             servidores_live.append(sl)

                    eventos.append({
                        "id": f"wr_live_{idx}",
                        "titulo": titulo_limpio,
                        "torneo": marca,
                        "tipo": "EN VIVO",
                        "servidores": servidores_live
                    })
                
                # Si hay repeticiones, agregamos un evento de tipo REPLAY
                if servidores_replay:
                    eventos.append({
                        "id": f"wr_replay_{idx}",
                        "titulo": titulo_limpio,
                        "torneo": marca,
                        "tipo": "REPLAY",
                        "servidores": servidores_replay
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
    
    if not eventos:
        LOG.warning("No se encontraron eventos de wrestling.")
        return 1

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
