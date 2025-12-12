# 🏆 AI Leaderboard Auto-Updater

Tabla comparativa de líderes de modelos de IA que se actualiza **automáticamente todos los días**.

## 📊 ¿Qué hace?

- Extrae datos de [LMArena](https://lmarena.ai/leaderboard), [Vellum](https://vellum.ai/llm-leaderboard) y otras plataformas
- Genera una tabla HTML bonita con los rankings actuales
- Se ejecuta automáticamente cada día a las 8:00 AM UTC via GitHub Actions

## 🚀 Ver la tabla actualizada

👉 **[Ver tabla de líderes](output/ai_leaderboard_comparison.html)** (clic derecho → "Abrir en nueva pestaña" o descargá el archivo)

---

# 📖 GUÍA PARA PRINCIPIANTES EN GITHUB

## Paso 1: Crear cuenta en GitHub (si no tenés)

Ya tenés cuenta, así que pasá al siguiente paso ✓

## Paso 2: Crear un nuevo repositorio

1. Andá a [github.com](https://github.com) y logueate
2. Hacé clic en el botón verde **"New"** (arriba a la izquierda) o andá a [github.com/new](https://github.com/new)
3. Completá:
   - **Repository name**: `ai-leaderboard-auto`
   - **Description**: `Tabla de líderes de IA auto-actualizada`
   - ✅ Marcá **"Public"** (gratis para GitHub Actions)
   - ❌ NO marques "Add a README file"
4. Clic en **"Create repository"**

## Paso 3: Subir los archivos

### Opción A: Desde la web (más fácil)

1. En tu repo vacío, vas a ver un link que dice **"uploading an existing file"** - hacé clic ahí
2. Arrastrá TODOS los archivos de esta carpeta (incluyendo las carpetas `.github`, `output`, etc.)
3. Abajo escribí un mensaje como: `Initial commit`
4. Clic en **"Commit changes"**

### Opción B: Usando Git (si querés aprender)

```bash
# En tu computadora, abrí una terminal/CMD en la carpeta del proyecto

# 1. Inicializar git
git init

# 2. Agregar todos los archivos
git add .

# 3. Crear el primer commit
git commit -m "🚀 Initial commit"

# 4. Conectar con GitHub (reemplazá TU_USUARIO)
git remote add origin https://github.com/TU_USUARIO/ai-leaderboard-auto.git

# 5. Subir
git branch -M main
git push -u origin main
```

## Paso 4: Habilitar GitHub Actions

1. En tu repositorio, andá a la pestaña **"Actions"** (arriba)
2. Si te pregunta, hacé clic en **"I understand my workflows, go ahead and enable them"**
3. ¡Listo! Ya está habilitado

## Paso 5: Ejecutar manualmente (primera vez)

1. En la pestaña **"Actions"**, vas a ver el workflow **"🤖 Update AI Leaderboard"**
2. Hacé clic en él
3. A la derecha, clic en el botón **"Run workflow"** → **"Run workflow"**
4. Esperá unos minutos mientras se ejecuta (podés ver el progreso)
5. Cuando termine (check verde ✓), andá a la carpeta `output/` de tu repo
6. ¡Vas a ver el archivo HTML actualizado!

## Paso 6: (Opcional) Publicar como página web

Podés hacer que la tabla sea una página web pública:

1. En tu repo, andá a **Settings** → **Pages** (en el menú izquierdo)
2. En "Source", seleccioná **"Deploy from a branch"**
3. Seleccioná **"main"** y **"/ (root)"**
4. Clic en **"Save"**
5. Esperá 1-2 minutos
6. Tu tabla estará disponible en: `https://TU_USUARIO.github.io/ai-leaderboard-auto/output/ai_leaderboard_comparison.html`

---

## 🔧 Configuración

### Cambiar horario de actualización

Editá `.github/workflows/update-leaderboard.yml` y cambiá la línea:

```yaml
- cron: '0 8 * * *'  # 8:00 AM UTC = 5:00 AM Argentina
```

Formato cron: `minuto hora día mes día-semana`

Ejemplos:
- `'0 12 * * *'` = Todos los días a las 12:00 PM UTC
- `'0 8 * * 1'` = Todos los lunes a las 8:00 AM UTC
- `'0 */6 * * *'` = Cada 6 horas

### Agregar más plataformas

Editá `scraper.py` y agregá nuevas funciones de scraping.

---

## 📁 Estructura del proyecto

```
ai-leaderboard-auto/
├── .github/
│   └── workflows/
│       └── update-leaderboard.yml  ← Automatización
├── output/
│   ├── ai_leaderboard_comparison.html  ← TABLA GENERADA
│   └── latest_data.json  ← Datos en JSON
├── templates/
│   └── (templates opcionales)
├── scraper.py  ← Script principal
├── requirements.txt  ← Dependencias
└── README.md  ← Este archivo
```

---

## ❓ Problemas comunes

### "Actions disabled"
Andá a Settings → Actions → General → y habilitá "Allow all actions"

### El workflow falla
1. Andá a Actions → hacé clic en el workflow fallido
2. Mirá los logs para ver el error
3. Los errores más comunes son timeouts (LMArena está caído momentáneamente)

### No veo cambios
Puede que los rankings no hayan cambiado. Revisá `output/latest_data.json` para ver qué datos se extrajeron.

---

## 📜 Licencia

MIT - Usalo como quieras 🎉

---

Hecho con ❤️ y Claude
