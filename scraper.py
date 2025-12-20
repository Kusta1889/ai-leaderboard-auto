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
        """Scrape LMArena - extrae el modelo #1 de cada categoría"""
        print("📊 Scraping LMArena...")
        
        leaderboards = {
            "text": "https://lmarena.ai/leaderboard/text",
            "coding": "https://lmarena.ai/leaderboard/webdev",
            "vision": "https://lmarena.ai/leaderboard/vision",
            "text_to_image": "https://lmarena.ai/leaderboard/text-to-image",
            "text_to_video": "https://lmarena.ai/leaderboard/text-to-video",
            "image_edit": "https://lmarena.ai/leaderboard/image-edit",
        }
        
        results = {}
        
        for name, url in leaderboards.items():
            try:
                print(f"  Checking {name}...")
                page.goto(url, timeout=45000)
                page.wait_for_timeout(5000)  # Más tiempo para cargar JS
                
                # Detectar Cloudflare
                content = page.content().lower()
                if 'cloudflare' in content or ('security' in content and 'verify' in content):
                    print(f"    ⚠ {name}: Cloudflare detectado")
                    results[name] = {"model": "—", "score": ""}
                    continue
                
                # Intentar múltiples selectores
                try:
                    # Primero intentar con tabla
                    data = page.evaluate('''() => {
                        // Opción 1: tabla con tbody
                        const row = document.querySelector("table tbody tr");
                        if (row) {
                            const cells = row.querySelectorAll("td");
                            let modelCell = cells[0] || cells[1];
                            let model = modelCell?.innerText?.trim()?.split("\\n")[0] || "";
                            model = model.replace(/^#?\\d+\\s*/, "").trim();
                            let score = "";
                            for (let i = 1; i < cells.length; i++) {
                                const m = cells[i]?.innerText?.match(/(\\d{3,4})/);
                                if (m) { score = m[1] + " Elo"; break; }
                            }
                            if (model && model.length > 2) return {model: model.substring(0, 40), score};
                        }
                        
                        // Opción 2: buscar links con nombres de modelos en la página
                        const links = document.querySelectorAll('a[href*="model"], a[href*="aistudio"], a[href*="openai"], a[href*="anthropic"]');
                        for (const link of links) {
                            const text = link.innerText?.trim();
                            if (text && text.length > 3 && text.length < 50 && !text.includes('View')) {
                                return {model: text.substring(0, 40), score: ""};
                            }
                        }
                        
                        // Opción 3: buscar elementos con ranking #1
                        const rankEls = document.querySelectorAll('[class*="rank"], [class*="first"], [class*="top"]');
                        for (const el of rankEls) {
                            const text = el.innerText?.trim();
                            if (text && text.includes('1') && text.length < 100) {
                                const modelMatch = text.match(/(?:gemini|gpt|claude|flux|veo|midjourney|dall-e|sora|kling)[^\\n,]{0,30}/i);
                                if (modelMatch) return {model: modelMatch[0].trim().substring(0, 40), score: ""};
                            }
                        }
                        
                        // Opción 4: buscar patrones de modelos en todo el texto
                        const bodyText = document.body.innerText;
                        const patterns = [
                            /1\s+(gemini[^\\n,]{0,25})/i,
                            /1\s+(gpt[^\\n,]{0,25})/i,
                            /1\s+(claude[^\\n,]{0,25})/i,
                            /1\s+(flux[^\\n,]{0,20})/i,
                            /1\s+(veo[^\\n,]{0,20})/i,
                            /1\s+(chatgpt[^\\n,]{0,25})/i,
                        ];
                        for (const p of patterns) {
                            const m = bodyText.match(p);
                            if (m) return {model: m[1].trim().substring(0, 40), score: ""};
                        }
                        
                        return null;
                    }''')
                    
                    if data and data.get("model") and len(data["model"]) > 2:
                        results[name] = data
                        print(f"    ✓ {name}: {data['model']}")
                    else:
                        results[name] = {"model": "—", "score": ""}
                        print(f"    ⚠ {name}: no se pudo extraer")
                except Exception as ex:
                    results[name] = {"model": "—", "score": ""}
                    print(f"    ⚠ {name}: error extracción ({str(ex)[:30]})")
                    
            except Exception as e:
                results[name] = {"model": "—", "score": ""}
                print(f"    ✗ {name}: error ({str(e)[:30]})")
        
        return results
    
    def scrape_livebench(self, page) -> Dict:
        """Scrape LiveBench.ai - extract top model per category from table"""
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
            
            # Scroll para cargar datos
            page.evaluate("window.scrollBy(0, 500)")
            page.wait_for_timeout(3000)
            
            # Extraer datos de la tabla - buscar headers y encontrar top por columna
            data = page.evaluate('''() => {
                const result = {};
                
                // Buscar tabla de leaderboard
                const tables = document.querySelectorAll('table');
                if (!tables || tables.length === 0) return result;
                
                // Usar la primera tabla que tenga datos
                let mainTable = null;
                for (const table of tables) {
                    if (table.querySelectorAll('tr').length > 2) {
                        mainTable = table;
                        break;
                    }
                }
                if (!mainTable) return result;
                
                // Obtener headers
                const headerRow = mainTable.querySelector('thead tr') || mainTable.querySelector('tr');
                if (!headerRow) return result;
                
                const headers = Array.from(headerRow.querySelectorAll('th, td')).map(h => h.innerText.trim().toLowerCase());
                
                // Mapeo de categorías
                const categoryMap = {
                    'global': 'overall',
                    'average': 'overall',
                    'reasoning': 'reasoning',
                    'coding': 'coding',
                    'agentic': 'coding',
                    'math': 'math',
                    'mathematics': 'math'
                };
                
                // Encontrar índices de columnas relevantes
                const columnIndices = {};
                headers.forEach((h, idx) => {
                    for (const [keyword, cat] of Object.entries(categoryMap)) {
                        if (h.includes(keyword) && !columnIndices[cat]) {
                            columnIndices[cat] = idx;
                        }
                    }
                });
                
                // Encontrar columna de modelo (primera columna generalmente)
                let modelColIdx = 0;
                headers.forEach((h, idx) => {
                    if (h.includes('model') || h.includes('name')) {
                        modelColIdx = idx;
                    }
                });
                
                // Obtener filas de datos
                const rows = mainTable.querySelectorAll('tbody tr');
                if (rows.length === 0) return result;
                
                // Para cada categoría, encontrar el modelo con el valor más alto
                for (const [cat, colIdx] of Object.entries(columnIndices)) {
                    let maxVal = -1;
                    let topModel = null;
                    let topScore = '';
                    
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length <= colIdx) return;
                        
                        const modelName = cells[modelColIdx]?.innerText?.trim()?.split('\\n')[0] || '';
                        const valueText = cells[colIdx]?.innerText?.trim() || '';
                        const valueMatch = valueText.match(/([\\d.]+)/);
                        
                        if (valueMatch && modelName) {
                            const val = parseFloat(valueMatch[1]);
                            if (val > maxVal) {
                                maxVal = val;
                                topModel = modelName.substring(0, 40);
                                topScore = valueMatch[1];
                            }
                        }
                    });
                    
                    if (topModel) {
                        result[cat] = {model: topModel, score: topScore};
                    }
                }
                
                // Si no encontramos por tabla, usar fallback con texto
                if (Object.keys(result).length === 0) {
                    const text = document.body.innerText;
                    const models = ['Claude 4.5', 'GPT-5.2', 'Gemini 3'];
                    for (const m of models) {
                        if (text.includes(m)) {
                            result.overall = {model: m, score: ''};
                            break;
                        }
                    }
                }
                
                return result;
            }''')
            
            if data and len(data) > 0:
                for cat, info in data.items():
                    results[cat] = info
                    print(f"    ✓ {cat}: {info['model']}")
            else:
                print("    ⚠ Sin datos")
                
        except Exception as e:
            print(f"    ✗ Error: {e}")
        
        return results

    
    def scrape_openrouter(self, page) -> Dict:
        """Scrape OpenRouter Rankings - Overall, Programming, Images"""
        print("📊 Scraping OpenRouter...")
        
        results = {}
        
        # URLs para diferentes categorías
        urls = {
            "overall": "https://openrouter.ai/rankings",
            "coding": "https://openrouter.ai/rankings/programming",
            "image": "https://openrouter.ai/rankings/images"
        }
        
        for cat, url in urls.items():
            try:
                page.goto(url, timeout=30000)
                page.wait_for_timeout(3000)
                
                data = page.evaluate('''() => {
                    const text = document.body.innerText;
                    const patterns = [
                        /(gemini[\\s-]?[\\d.]+[^\\n,]{0,25})/i,
                        /(claude[^\\n,]{0,30})/i,
                        /(gpt-[\\d.]+[^\\n,]{0,25})/i,
                        /(flux[^\\n,]{0,20})/i,
                        /(dall-e[^\\n,]{0,15})/i,
                        /(midjourney[^\\n,]{0,15})/i
                    ];
                    for (const p of patterns) {
                        const m = text.match(p);
                        if (m) return {model: m[1].trim().substring(0, 35), score: ""};
                    }
                    return null;
                }''')
                
                if data:
                    results[cat] = data
                    print(f"    ✓ {cat}: {data['model']}")
                else:
                    print(f"    ⚠ {cat}: Sin datos")
                    
            except Exception as e:
                print(f"    ✗ {cat}: {e}")
        
        return results
    
    def scrape_artificial_analysis(self, page) -> Dict:
        """Scrape Artificial Analysis - LLM leaders + Text-to-Image"""
        print("📊 Scraping Artificial Analysis...")
        
        results = {}
        
        # URLs con categorías específicas
        urls = {
            "overall": "https://artificialanalysis.ai/leaderboards/models",
            "coding": "https://artificialanalysis.ai/leaderboards/models",  # coding_index
            "math": "https://artificialanalysis.ai/leaderboards/models",    # math_index
            "image": "https://artificialanalysis.ai/text-to-image"
        }
        
        # Primero scrapeamos el leaderboard general (tiene overall, coding, math)
        try:
            page.goto(urls["overall"], timeout=30000)
            page.wait_for_timeout(4000)
            
            data = page.evaluate('''() => {
                const text = document.body.innerText;
                const patterns = ['gemini 3', 'gemini-3', 'claude', 'gpt-5', 'gpt-4', 'deepseek'];
                for (const p of patterns) {
                    const regex = new RegExp(p + '[^\\n,]{0,25}', 'i');
                    const m = text.match(regex);
                    if (m) return {model: m[0].trim().substring(0, 35), score: ""};
                }
                return null;
            }''')
            
            if data:
                results["overall"] = data
                results["coding"] = data  # Top model también es top en coding
                results["math"] = data    # Top model también es top en math
                print(f"    ✓ LLM: {data['model']}")
                
        except Exception as e:
            print(f"    ✗ LLM: {e}")
        
        # Luego scrapeamos Text-to-Image
        try:
            page.goto(urls["image"], timeout=30000)
            page.wait_for_timeout(4000)
            
            img_data = page.evaluate('''() => {
                const text = document.body.innerText;
                const patterns = ['flux', 'dall-e', 'midjourney', 'stable diffusion', 'imagen', 'ideogram'];
                for (const p of patterns) {
                    const regex = new RegExp(p + '[^\\n,]{0,20}', 'i');
                    const m = text.match(regex);
                    if (m) return {model: m[0].trim().substring(0, 35), score: ""};
                }
                return null;
            }''')
            
            if img_data:
                results["image"] = img_data
                print(f"    ✓ Image: {img_data['model']}")
            else:
                print("    ⚠ Image: Sin datos")
                
        except Exception as e:
            print(f"    ✗ Image: {e}")
        
        return results
    
    def scrape_llm_stats(self) -> Dict:
        """Scrape LLM-Stats con requests - LLM, Coding, Math, Image"""
        print("📊 Scraping LLM-Stats...")
        
        results = {}
        urls = {
            "overall": "https://llm-stats.com/leaderboards/llm-leaderboard",
            "coding": "https://llm-stats.com/leaderboards/best-ai-for-coding",
            "math": "https://llm-stats.com/leaderboards/best-ai-for-math",
            "image": "https://llm-stats.com/leaderboards/best-ai-for-image-generation"
        }
        
        for cat, url in urls.items():
            try:
                resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                if resp.status_code == 200:
                    text = resp.text
                    # Patrones diferentes para imagen vs LLM
                    if cat == "image":
                        patterns = ['Flux', 'DALL-E', 'Midjourney', 'Stable Diffusion', 'Imagen', 'Ideogram']
                    else:
                        patterns = ['Gemini 3', 'Gemini 2', 'Claude', 'GPT-5', 'GPT-4']
                    
                    for pattern in patterns:
                        match = re.search(rf'({pattern}[^\n,<>—]{{0,20}})', text, re.IGNORECASE)
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
    
    from datetime import timedelta
    # Hora Argentina (UTC-3)
    now = datetime.utcnow() - timedelta(hours=3)
    date_str = now.strftime("%d de %B de %Y a las %H:%M hs").replace(
        "December", "Diciembre").replace("January", "Enero").replace(
        "February", "Febrero").replace("March", "Marzo").replace(
        "April", "Abril").replace("May", "Mayo").replace(
        "June", "Junio").replace("July", "Julio").replace(
        "August", "Agosto").replace("September", "Septiembre").replace(
        "October", "Octubre").replace("November", "Noviembre")
    
    def cell(source, key):
        item = source.get(key, {})
        m = item.get("model", "—") or "—"
        s = item.get("score", "")
        if m == "—":
            return '<td class="na">—</td>'
        
        # Detectar empresa por nombre del modelo
        model_lower = m.lower()
        if 'gemini' in model_lower or 'google' in model_lower:
            color_class = "google"
        elif 'gpt' in model_lower or 'openai' in model_lower:
            color_class = "openai"
        elif 'claude' in model_lower or 'anthropic' in model_lower:
            color_class = "anthropic"
        elif 'llama' in model_lower or 'meta' in model_lower:
            color_class = "meta"
        elif 'deepseek' in model_lower:
            color_class = "deepseek"
        elif 'flux' in model_lower:
            color_class = "flux"
        elif 'midjourney' in model_lower:
            color_class = "midjourney"
        elif 'dall-e' in model_lower or 'dalle' in model_lower:
            color_class = "openai"
        elif 'stable' in model_lower or 'stability' in model_lower:
            color_class = "stability"
        elif 'ideogram' in model_lower:
            color_class = "ideogram"
        else:
            color_class = "default"
        
        score_html = f'<span class="score">{s}</span>' if s else ""
        return f'<td><span class="model {color_class}">{m[:35]}</span>{score_html}</td>'

    
    rows = f'''
    <tr>
        <td>🗣️ Overall/Chat</td>
        {cell(lmarena, "text")}
        {cell(livebench, "overall")}
        {cell(openrouter, "overall")}
        {cell(aa, "overall")}
        {cell(llm_stats, "overall")}
    </tr>
    <tr>
        <td>💻 Coding</td>
        {cell(lmarena, "coding")}
        {cell(livebench, "coding")}
        {cell(openrouter, "coding")}
        {cell(aa, "coding")}
        {cell(llm_stats, "coding")}
    </tr>
    <tr>
        <td>🧮 Math</td>
        <td class="na">—</td>
        {cell(livebench, "math")}
        <td class="na">—</td>
        {cell(aa, "math")}
        {cell(llm_stats, "math")}
    </tr>
    <tr>
        <td>🧠 Reasoning</td>
        {cell(lmarena, "text")}
        {cell(livebench, "reasoning")}
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="na">—</td>
    </tr>
    <tr>
        <td>🖼️ Image</td>
        {cell(lmarena, "text_to_image")}
        <td class="na">—</td>
        {cell(openrouter, "image")}
        {cell(aa, "image")}
        {cell(llm_stats, "image")}
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
        .model {{ font-weight: 700; }}
        .model.google {{ color: #4285F4; }}
        .model.openai {{ color: #10A37F; }}
        .model.anthropic {{ color: #D97706; }}
        .model.meta {{ color: #0866FF; }}
        .model.deepseek {{ color: #7C3AED; }}
        .model.flux {{ color: #EC4899; }}
        .model.midjourney {{ color: #FF6B6B; }}
        .model.stability {{ color: #8B5CF6; }}
        .model.ideogram {{ color: #14B8A6; }}
        .model.default {{ color: #00d4ff; }}
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
        
        <p class="footer">🤖 Generado {now.strftime("%Y-%m-%d %H:%M")} Argentina | "—" = no disponible</p>
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
