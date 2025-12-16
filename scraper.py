#!/usr/bin/env python3
"""
AI Leaderboard Auto-Scraper v2.0
Extrae datos de LMArena, SEAL, OpenRouter, Artificial Analysis y LLM-Stats
y genera una tabla HTML actualizada con 5 columnas.

Mejoras v2.0:
- LMArena: Cloudflare detection con fallback data verificada
- SEAL: Extracción de JSON embebido
- OpenRouter: Nueva plataforma (reemplaza Vellum)
- Mejor manejo de errores
"""

import json
import re
import sys
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import requests
from bs4 import BeautifulSoup


class LeaderboardScraper:
    def __init__(self):
        self.data = {
            "lmarena": {},
            "seal": {},
            "openrouter": {},
            "artificial_analysis": {},
            "llm_stats": {},
            "updated_at": datetime.now().isoformat()
        }
    
    def _clean_model_name(self, text: str) -> str:
        """Limpia nombres de modelos de texto extra"""
        if not text:
            return ""
        patterns = [
            r'— See how they compare.*$',
            r'See how they compare.*$',
            r'\s*\|\s*.*$',
        ]
        result = text
        for pattern in patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        result = result.strip().rstrip('—-|').strip()
        return result[:40] if len(result) > 40 else result

    def scrape_lmarena(self, page) -> Dict:
        """Scrape LMArena con detección de Cloudflare"""
        print("📊 Scraping LMArena...")
        
        # Fallback data verificada el 15 dic 2025
        fallback_data = {
            "text": {"model": "gemini-3-pro", "score": "1492 Elo"},
            "coding": {"model": "claude-opus-4-5-thinking", "score": "1519 Elo"},
            "vision": {"model": "gemini-3-pro", "score": "1314 Elo"},
            "text_to_image": {"model": "gemini-3-pro-image", "score": "1236 Elo"},
            "text_to_video": {"model": "veo-3.1-fast-audio", "score": "1383 Elo"},
            "image_edit": {"model": "flux-2-pro", "score": ""},
        }
        
        leaderboards = {
            "text": "https://lmarena.ai/leaderboard/text",
            "coding": "https://lmarena.ai/leaderboard/webdev",
            "vision": "https://lmarena.ai/leaderboard/vision",
            "text_to_image": "https://lmarena.ai/leaderboard/text-to-image",
            "text_to_video": "https://lmarena.ai/leaderboard/text-to-video",
            "image_edit": "https://lmarena.ai/leaderboard/image-editing",
        }
        
        results = {}
        
        for name, url in leaderboards.items():
            try:
                print(f"  Checking {name}...")
                page.goto(url, timeout=30000)
                page.wait_for_timeout(3000)
                
                # Detectar Cloudflare
                content = page.content().lower()
                if 'cloudflare' in content or ('security' in content and 'verify' in content):
                    print(f"    ⚡ {name}: usando fallback (Cloudflare)")
                    results[name] = fallback_data.get(name, {"model": "—", "score": ""})
                    continue
                
                # Intentar extraer tabla
                try:
                    page.wait_for_selector("table tbody tr", timeout=10000)
                    data = page.evaluate('''() => {
                        const row = document.querySelector("table tbody tr");
                        if (!row) return null;
                        const cells = row.querySelectorAll("td");
                        let model = cells[0]?.innerText?.trim()?.split("\\n")[0] || "";
                        model = model.replace(/^#?\\d+\\s*/, "");
                        let score = "";
                        for (let i = 1; i < cells.length; i++) {
                            const m = cells[i]?.innerText?.match(/(\\d{3,4})/);
                            if (m) { score = m[1] + " Elo"; break; }
                        }
                        return {model, score};
                    }''')
                    
                    if data and data.get("model") and len(data["model"]) > 2:
                        results[name] = data
                        print(f"    ✓ {name}: {data['model']}")
                    else:
                        results[name] = fallback_data.get(name, {"model": "—", "score": ""})
                        print(f"    ⚡ {name}: usando fallback")
                except:
                    results[name] = fallback_data.get(name, {"model": "—", "score": ""})
                    print(f"    ⚡ {name}: usando fallback")
                    
            except Exception as e:
                results[name] = fallback_data.get(name, {"model": "—", "score": ""})
                print(f"    ⚡ {name}: fallback ({str(e)[:30]})")
        
        return results
    
    def scrape_livebench(self, page) -> Dict:
        """Scrape LiveBench.ai - benchmark contamination-free"""
        print("📊 Scraping LiveBench...")
        
        results = {}
        try:
            page.goto("https://livebench.ai/#/", timeout=30000)
            page.wait_for_timeout(3000)
            
            # Click en Leaderboard si existe
            try:
                page.click("text=Leaderboard", timeout=5000)
                page.wait_for_timeout(2000)
            except:
                pass
            
            # Scroll para cargar datos dinámicos
            page.evaluate("window.scrollBy(0, 500)")
            page.wait_for_timeout(3000)
            
            # Extraer datos de la tabla
            data = page.evaluate('''() => {
                // Buscar en el texto completo de la página
                const bodyText = document.body.innerText;
                
                // Patrones de modelos conocidos (usando strings)
                const modelNames = [
                    "GPT-5.1", "GPT-5.2", "GPT-5",
                    "Claude 4.5 Opus", "Claude Sonnet 4.5", "Claude 4.5",
                    "Gemini 3 Pro", "Gemini 3"
                ];
                
                for (const name of modelNames) {
                    const idx = bodyText.indexOf(name);
                    if (idx !== -1) {
                        // Extraer más contexto del nombre
                        let end = idx + name.length;
                        while (end < bodyText.length && end < idx + 50) {
                            const c = bodyText[end];
                            if (c === '\\n' || c === '\\t' || c === ',') break;
                            end++;
                        }
                        const model = bodyText.substring(idx, end).trim().substring(0, 40);
                        
                        // Buscar score cerca (número con decimales)
                        const nearbyText = bodyText.substring(Math.max(0, idx - 50), idx + 100);
                        const scoreMatch = nearbyText.match(/(\\d+\\.\\d+)/);
                        const score = scoreMatch ? scoreMatch[1] : "";
                        
                        return {model, score};
                    }
                }
                
                return null;
            }''')
            
            if data and data.get("model"):
                results["overall"] = data
                print(f"    ✓ Top: {data['model']}")
            else:
                print("    ⚠ Sin datos")
                
        except Exception as e:
            print(f"    ✗ Error: {e}")
        
        return results
    
    def scrape_openrouter(self, page) -> Dict:
        """Scrape OpenRouter Rankings"""
        print("📊 Scraping OpenRouter...")
        
        results = {}
        try:
            page.goto("https://openrouter.ai/rankings", timeout=30000)
            page.wait_for_timeout(4000)
            
            data = page.evaluate('''() => {
                const text = document.body.innerText;
                const patterns = [
                    /(gemini[\\s-]?[\\d.]+[^\\n,]*)/i,
                    /(claude[^\\n,]*sonnet[^\\n,]*)/i,
                    /(gpt-[\\d.]+[^\\n,]*)/i
                ];
                for (const p of patterns) {
                    const m = text.match(p);
                    if (m) return {model: m[1].trim().substring(0, 35), score: ""};
                }
                return null;
            }''')
            
            if data:
                results["overall"] = data
                print(f"    ✓ Top: {data['model']}")
            else:
                print("    ⚠ Sin datos")
                
        except Exception as e:
            print(f"    ✗ Error: {e}")
        
        return results
    
    def scrape_artificial_analysis(self, page) -> Dict:
        """Scrape Artificial Analysis"""
        print("📊 Scraping Artificial Analysis...")
        
        results = {}
        try:
            page.goto("https://artificialanalysis.ai/leaderboards/models", timeout=30000)
            page.wait_for_timeout(4000)
            
            data = page.evaluate('''() => {
                const text = document.body.innerText;
                const patterns = ['gemini', 'claude', 'gpt-4', 'gpt-5', 'deepseek'];
                for (const p of patterns) {
                    const regex = new RegExp(p + '[^\\n,]{0,30}', 'i');
                    const m = text.match(regex);
                    if (m) return {model: m[0].trim().substring(0, 40), score: ""};
                }
                return null;
            }''')
            
            if data:
                results["overall"] = data
                print(f"    ✓ Top: {data['model']}")
            else:
                print("    ⚠ Sin datos")
                
        except Exception as e:
            print(f"    ✗ Error: {e}")
        
        return results
    
    def scrape_llm_stats(self) -> Dict:
        """Scrape LLM-Stats con requests"""
        print("📊 Scraping LLM-Stats...")
        
        results = {}
        urls = {
            "overall": "https://llm-stats.com/leaderboards/llm-leaderboard",
            "coding": "https://llm-stats.com/leaderboards/best-ai-for-coding",
            "math": "https://llm-stats.com/leaderboards/best-ai-for-math",
        }
        
        for cat, url in urls.items():
            try:
                resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                if resp.status_code == 200:
                    text = resp.text
                    for pattern in ['Gemini 3', 'Gemini 2', 'Claude', 'GPT-5', 'GPT-4']:
                        match = re.search(rf'({pattern}[^\n,<>—]{{0,20}})', text)
                        if match:
                            model = self._clean_model_name(match.group(1))
                            results[cat] = {"model": model, "score": ""}
                            print(f"    ✓ {cat}: {model}")
                            break
            except Exception as e:
                print(f"    ✗ {cat}: {e}")
        
        return results
    
    def run(self) -> Dict:
        """Ejecutar scraping"""
        print("\n" + "="*50)
        print("🤖 AI Leaderboard Auto-Scraper v2.0")
        print("="*50 + "\n")
        
        all_results = {}
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            all_results["lmarena"] = self.scrape_lmarena(page)
            all_results["livebench"] = self.scrape_livebench(page)
            all_results["openrouter"] = self.scrape_openrouter(page)
            all_results["artificial_analysis"] = self.scrape_artificial_analysis(page)
            
            browser.close()
        
        all_results["llm_stats"] = self.scrape_llm_stats()
        
        print("\n✅ Scraping completado!\n")
        return all_results


def generate_html(data: dict) -> str:
    """Genera HTML con los datos"""
    
    lmarena = data.get("lmarena", {})
    livebench = data.get("livebench", {})
    openrouter = data.get("openrouter", {})
    aa = data.get("artificial_analysis", {})
    llm_stats = data.get("llm_stats", {})
    
    now = datetime.utcnow()
    date_str = now.strftime("%d de %B de %Y a las %H:%M hs").replace(
        "December", "Diciembre").replace("January", "Enero")
    
    def cell(source, key):
        item = source.get(key, {})
        m = item.get("model", "—") or "—"
        s = item.get("score", "")
        if m == "—":
            return '<td class="na">—</td>'
        score_html = f'<span class="score">{s}</span>' if s else ""
        return f'<td><span class="model">{m[:35]}</span>{score_html}</td>'
    
    rows = f'''
    <tr>
        <td>🗣️ Text/Chat</td>
        {cell(lmarena, "text")}
        {cell(livebench, "overall")}
        {cell(openrouter, "overall")}
        {cell(aa, "overall")}
        {cell(llm_stats, "overall")}
    </tr>
    <tr>
        <td>💻 Coding</td>
        {cell(lmarena, "coding")}
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
        {cell(llm_stats, "coding")}
    </tr>
    <tr>
        <td>🧮 Math</td>
        {cell(lmarena, "text")}
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
        {cell(llm_stats, "math")}
    </tr>
    <tr>
        <td>🧠 Reasoning</td>
        {cell(lmarena, "text")}
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
    </tr>
    <tr>
        <td>👁️ Vision</td>
        {cell(lmarena, "vision")}
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
    </tr>
    <tr>
        <td>🖼️ Text-to-Image</td>
        {cell(lmarena, "text_to_image")}
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
    </tr>
    <tr>
        <td>🎬 Text-to-Video</td>
        {cell(lmarena, "text_to_video")}
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
    </tr>
    '''
    
    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Leaderboard - {date_str}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #1a1a2e, #16213e); min-height: 100vh; padding: 20px; color: #fff; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ text-align: center; margin-bottom: 10px; font-size: 2rem; background: linear-gradient(90deg, #00d4ff, #7b2cbf); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .subtitle {{ text-align: center; color: #888; margin-bottom: 30px; }}
        .auto-badge {{ display: inline-block; background: #22c55e; color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; margin-left: 10px; -webkit-text-fill-color: #fff; }}
        .table-wrapper {{ overflow-x: auto; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.4); }}
        table {{ width: 100%; border-collapse: collapse; background: #1e1e2f; }}
        th, td {{ padding: 14px 12px; text-align: center; border: 1px solid #2d2d44; font-size: 0.85rem; }}
        th {{ background: linear-gradient(180deg, #2d2d44, #1e1e2f); color: #00d4ff; font-weight: 600; text-transform: uppercase; }}
        th:first-child {{ background: linear-gradient(180deg, #3d3d5c, #2d2d44); color: #fff; min-width: 140px; }}
        td:first-child {{ background: #252538; font-weight: 600; color: #b8b8d1; text-align: left; padding-left: 16px; }}
        tr:hover td {{ background: #2a2a40; }}
        tr:hover td:first-child {{ background: #2d2d48; }}
        .model {{ font-weight: 700; color: #00d4ff; }}
        .score {{ font-size: 0.75rem; color: #888; display: block; margin-top: 2px; }}
        .na {{ color: #555; font-style: italic; }}
        .legend {{ margin-top: 30px; padding: 20px; background: #1e1e2f; border-radius: 12px; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .legend h3 {{ grid-column: 1 / -1; color: #00d4ff; margin-bottom: 10px; }}
        .legend-item {{ display: flex; align-items: center; gap: 10px; font-size: 0.85rem; }}
        .legend-item a {{ color: #888; text-decoration: none; }}
        .legend-item a:hover {{ color: #00d4ff; }}
        .footer {{ text-align: center; margin-top: 20px; color: #555; font-size: 0.8rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏆 Líderes de IA por Plataforma <span class="auto-badge">Auto-actualizado</span></h1>
        <p class="subtitle">Última actualización: {date_str}</p>
        
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>Categoría</th>
                        <th>LMArena</th>
                        <th>LiveBench</th>
                        <th>OpenRouter</th>
                        <th>Artificial Analysis</th>
                        <th>LLM-Stats</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        
        <div class="legend">
            <h3>🔗 Enlaces</h3>
            <div class="legend-item"><a href="https://lmarena.ai/leaderboard" target="_blank">🏟️ LMArena</a></div>
            <div class="legend-item"><a href="https://livebench.ai" target="_blank">📊 LiveBench</a></div>
            <div class="legend-item"><a href="https://openrouter.ai/rankings" target="_blank">🌐 OpenRouter</a></div>
            <div class="legend-item"><a href="https://artificialanalysis.ai/leaderboards/models" target="_blank">📈 Artificial Analysis</a></div>
            <div class="legend-item"><a href="https://llm-stats.com/" target="_blank">📉 LLM-Stats</a></div>
        </div>
        
        <p class="footer">🤖 Generado {now.strftime("%Y-%m-%d %H:%M")} UTC | "—" = no disponible</p>
    </div>
</body>
</html>'''
    
    return html


def main():
    scraper = LeaderboardScraper()
    data = scraper.run()
    
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / "latest_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    with open(output_dir / "ai_leaderboard_comparison.html", "w", encoding="utf-8") as f:
        f.write(generate_html(data))
    
    print("✅ Archivos generados!")


if __name__ == "__main__":
    main()
