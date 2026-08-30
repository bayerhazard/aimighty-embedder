"""AIM Qwen3 Embedding dashboard — AImighty design-guide format.

Hanseatenblau #051729 + Gold #caa960, --am-* spacing (Einheit 0.25rem),
self-hosted Geist fonts (base64 woff2, no external loading), DE/EN toggle.
Format transferred from the OmniVoice TTS dashboard (adf17dad).
"""

import json

_DASHBOARD_CSS = """:root{
  --am-skalierung:1;
  --am-einheit:0.25rem;
  --am-raum-1:calc(var(--am-einheit)*1*var(--am-skalierung));
  --am-raum-2:calc(var(--am-einheit)*2*var(--am-skalierung));
  --am-raum-3:calc(var(--am-einheit)*3*var(--am-skalierung));
  --am-raum-4:calc(var(--am-einheit)*4*var(--am-skalierung));
  --am-raum-6:calc(var(--am-einheit)*6*var(--am-skalierung));
  --am-raum-8:calc(var(--am-einheit)*8*var(--am-skalierung));
  --blau:#051729;
  --flaeche-1:#0a2238;
  --flaeche-2:#142e47;
  --gold:#caa960;
  --gold-hell:#d8bc75;
  --handlung:#caa960;
  --auf-handlung:#051729;
  --text:#e8eef4;
  --text-stark:#ffffff;
  --text-dim:#8fa3b8;
  --rand:var(--flaeche-2);
  --rand-marke:color-mix(in oklab, var(--gold) 44%, transparent);
  --marke-flaeche:color-mix(in oklab, var(--gold) 12%, transparent);
  --radius:0.5rem;
  --kurve:cubic-bezier(0.2,0,0,1);
  --schrift:'Geist',system-ui,sans-serif;
  --mono:'Geist Mono',ui-monospace,monospace;
}
*,*::before,*::after{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:var(--schrift);font-size:0.9375rem;line-height:1.5;background:var(--blau);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.container{width:min(100% - var(--am-raum-8),60rem);margin-inline:auto;padding-block:var(--am-raum-6)}
.header{display:flex;align-items:center;justify-content:space-between;gap:var(--am-raum-4);margin-bottom:var(--am-raum-6);padding-block:var(--am-raum-1) var(--am-raum-4);border-bottom:1px solid var(--flaeche-2)}
.header h1{display:flex;align-items:center;gap:var(--am-raum-2);font-size:clamp(1.35rem,1.1rem + 1vw,1.6rem);font-weight:700;letter-spacing:-0.02em;color:var(--text-stark);line-height:1.15;margin:0}
.brand-logo{height:2.25rem;width:auto;flex-shrink:0;display:block}
.header .subtitle{font-size:0.82rem;color:var(--text-dim);margin-top:var(--am-raum-1)}
.lang-toggle{display:inline-flex;gap:2px;background:var(--flaeche-1);border:1px solid var(--flaeche-2);border-radius:0.375rem;padding:2px;flex-shrink:0}
.lang-toggle button{border:none;background:transparent;color:var(--text-dim);font-family:var(--mono);font-size:0.68rem;font-weight:600;letter-spacing:0.1em;padding:var(--am-raum-1) var(--am-raum-2);border-radius:0.25rem;cursor:pointer;transition:color 120ms var(--kurve),background-color 120ms var(--kurve)}
.lang-toggle button.active{color:var(--auf-handlung);background:var(--gold)}
.card{background:var(--flaeche-1);border:1px solid var(--flaeche-2);border-radius:var(--radius);padding:var(--am-raum-4);margin-bottom:var(--am-raum-4)}
.card-title{display:flex;align-items:center;gap:var(--am-raum-2);font-size:0.95rem;font-weight:600;color:var(--text-stark);margin-bottom:var(--am-raum-3)}
.icon{color:var(--gold)}
.status{display:flex;align-items:center;gap:var(--am-raum-2);font-size:0.85rem;color:var(--text-dim);min-height:1.5rem;margin-bottom:var(--am-raum-4)}
.status .dot{width:0.5rem;height:0.5rem;border-radius:50%;background:{status_color};flex-shrink:0}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:var(--am-raum-3)}
.meta-item{padding:var(--am-raum-3);background:var(--flaeche-2);border:1px solid var(--flaeche-2);border-radius:0.375rem}
.meta-label{font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--text-dim);font-weight:700}
.meta-value{margin-top:var(--am-raum-1);color:var(--text-stark);font-size:0.95rem;font-weight:600;font-family:var(--mono)}
.endpoints{display:grid;gap:var(--am-raum-2)}
.endpoint{display:flex;align-items:center;gap:var(--am-raum-3);padding:var(--am-raum-2) var(--am-raum-3);background:var(--flaeche-2);border:1px solid var(--flaeche-2);border-radius:0.375rem;font-family:var(--mono);font-size:0.85rem}
.method{flex-shrink:0;font-weight:700;font-size:0.7rem;padding:0.2rem 0.5rem;border-radius:0.25rem;letter-spacing:0.05em}
.method.GET{background:color-mix(in oklab, var(--gold) 18%, transparent);color:var(--gold-hell)}
.method.POST{background:var(--flaeche-1);color:var(--text)}
.path{color:var(--text-stark);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.desc{color:var(--text-dim);font-size:0.78rem;font-family:var(--schrift)}
pre{margin:0;padding:var(--am-raum-3);background:var(--flaeche-2);border:1px solid var(--flaeche-2);border-radius:0.375rem;font-family:var(--mono);font-size:0.8rem;color:var(--text);overflow-x:auto;line-height:1.6}
pre .kw{color:var(--gold-hell)}
pre .str{color:#55c483}
h2{font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;color:var(--text-dim);margin:var(--am-raum-4) 0 var(--am-raum-2)}
.foot{display:flex;align-items:center;justify-content:space-between;gap:var(--am-raum-4);margin-top:var(--am-raum-4);padding-top:var(--am-raum-3);border-top:1px solid var(--flaeche-2);font-size:0.8rem;color:var(--text-dim);flex-wrap:wrap}
.foot .health{display:flex;align-items:center;gap:var(--am-raum-2)}
.foot b{color:var(--text)}
a{color:var(--gold);text-decoration:none;transition:color 120ms var(--kurve)}
a:hover{color:var(--gold-hell)}
@media (max-width:40rem){.header{flex-direction:column;align-items:flex-start}.foot{flex-direction:column;align-items:flex-start}}"""

_DASHBOARD_I18N = {
    "de": {
        "title": "AIM Qwen3 Embedding",
        "subtitle": "Qwen3-Embedding-4B INT8 via OpenVINO auf CPU — OpenAI-kompatible API",
        "statusTitle": "Status",
        "mModel": "Modell",
        "mDevice": "Gerät",
        "mMode": "Modus",
        "mMaxTokens": "Max. Tokens",
        "apiTitle": "API-Endpunkte",
        "eEmbed": "Embeddings erzeugen (OpenAI-kompatibel)",
        "eModels": "Verfügbare Modelle auflisten",
        "eHealth": "Liveness-Probe",
        "quickTitle": "Schnellstart",
        "cfgModel": "Modell",
    },
    "en": {
        "title": "AIM Qwen3 Embedding",
        "subtitle": "Qwen3-Embedding-4B INT8 via OpenVINO on CPU — OpenAI-compatible API",
        "statusTitle": "Status",
        "mModel": "Model",
        "mDevice": "Device",
        "mMode": "Mode",
        "mMaxTokens": "Max tokens",
        "apiTitle": "API Endpoints",
        "eEmbed": "Generate embeddings (OpenAI-compatible)",
        "eModels": "List available models",
        "eHealth": "Liveness probe",
        "quickTitle": "Quick start",
        "cfgModel": "Model",
    },
}


def render_dashboard(*, model_ready, model_name, device, mode_label_en, mode_label_de,
                     status_text_en, status_text_de, status_color, max_length, fonts_css):
    """Return the full HTML dashboard page."""
    i18n_json = json.dumps(_DASHBOARD_I18N, ensure_ascii=False)
    dyn_json = json.dumps({
        "status": {"en": status_text_en, "de": status_text_de},
        "mode": {"en": mode_label_en, "de": mode_label_de},
    }, ensure_ascii=False)
    css = fonts_css + "\n" + _DASHBOARD_CSS.replace("{status_color}", status_color)
    logo = (
        '<svg class="brand-logo" viewBox="0 0 150 150" fill="none" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="AImighty">'
        '<path d="M130 26.625V68.5625C130 85.9792 124.815 101.82 114.445 116.086'
        'C104.076 130.352 90.9271 139.49 75 143.5C59.0729 139.49 45.9245 130.352 '
        '35.5547 116.086C25.1849 101.82 20 85.9792 20 68.5625V26.625L75 6L130 26.625Z'
        'M57.7139 40.9248L36.2246 100.523H47.6416L52.5938 86.4219H76.1816L81.1338 '
        '100.523H92.5498L71.0605 40.9248H57.7139ZM94.6123 100.523H105.525V40.9248H94.6123'
        'V100.523ZM72.9912 77.1035H55.7832L64.4297 51.9209L72.9912 77.1035Z" '
        'fill="#CAA960"/></svg>'
    )
    head = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="terminus-language" content="en-US"/>\n'
        '<title>AIM Qwen3 Embedding — Dashboard</title>\n'
        f'<style>{css}</style>\n</head>\n<body>\n'
    )
    body = f"""<div class="container">

  <header class="header">
    <div>
      <h1>
        {logo}
        <span data-i18n="title">AIM Qwen3 Embedding</span>
      </h1>
      <div class="subtitle" data-i18n="subtitle">Qwen3-Embedding-4B INT8 via OpenVINO on CPU — OpenAI-compatible API</div>
    </div>
    <div class="lang-toggle" role="group" aria-label="Language">
      <button type="button" data-lang="de">DE</button>
      <button type="button" data-lang="en" class="active">EN</button>
    </div>
  </header>

  <section class="card" aria-labelledby="statusTitle">
    <div class="card-title" id="statusTitle"><span class="icon">&#9679;</span><span data-i18n="statusTitle">Status</span></div>
    <div class="status"><span class="dot"></span><span data-i18n-dyn="status">{status_text_en}</span></div>
    <div class="meta">
      <div class="meta-item"><div class="meta-label" data-i18n="mModel">Model</div><div class="meta-value">{model_name}</div></div>
      <div class="meta-item"><div class="meta-label" data-i18n="mDevice">Device</div><div class="meta-value">{device}</div></div>
      <div class="meta-item"><div class="meta-label" data-i18n="mMode">Mode</div><div class="meta-value" data-i18n-dyn="mode">{mode_label_en}</div></div>
      <div class="meta-item"><div class="meta-label" data-i18n="mMaxTokens">Max tokens</div><div class="meta-value">{max_length}</div></div>
    </div>
  </section>

  <section class="card" aria-labelledby="apiTitle">
    <div class="card-title" id="apiTitle"><span class="icon">&#9702;</span><span data-i18n="apiTitle">API Endpoints</span></div>
    <div class="endpoints">
      <div class="endpoint"><span class="method POST">POST</span><span class="path">/v1/embeddings</span><span class="desc" data-i18n="eEmbed">Generate embeddings (OpenAI-compatible)</span></div>
      <div class="endpoint"><span class="method GET">GET</span><span class="path">/v1/models</span><span class="desc" data-i18n="eModels">List available models</span></div>
      <div class="endpoint"><span class="method GET">GET</span><span class="path">/health</span><span class="desc" data-i18n="eHealth">Liveness probe</span></div>
    </div>
  </section>

  <section class="card" aria-labelledby="quickTitle">
    <div class="card-title" id="quickTitle"><span class="icon">&#9656;</span><span data-i18n="quickTitle">Quick start</span></div>
    <pre><span class="kw">curl</span> -X POST <span class="str">"$ENDPOINT/v1/embeddings"</span> \\
  -H <span class="str">"Content-Type: application/json"</span> \\
  -d <span class="str">'{{"input": "Hello world", "model": "{model_name}"}}'</span></pre>
  </section>

  <footer class="foot">
    <div class="health"><span class="dot" style="width:0.5rem;height:0.5rem;border-radius:50%;background:{status_color};display:inline-block"></span><span data-i18n-dyn="status">{status_text_en}</span></div>
    <div class="cfg"><span><b data-i18n="cfgModel">Model</b>: Qwen3-Embedding-4B INT8</span></div>
  </footer>
</div>
"""
    script = _SCRIPT_TPL.replace("__I18N__", i18n_json).replace("__DYN__", dyn_json)
    return head + body + script + "</body>\n</html>\n"


_SCRIPT_TPL = """<script>
const I18N = __I18N__;
const DYN = __DYN__;
function applyLang(l){
  document.documentElement.lang = l;
  document.querySelectorAll('[data-i18n]').forEach(function(el){
    const k = el.getAttribute('data-i18n');
    if (I18N[l] && I18N[l][k] !== undefined) el.textContent = I18N[l][k];
  });
  document.querySelectorAll('[data-i18n-dyn]').forEach(function(el){
    const k = el.getAttribute('data-i18n-dyn');
    if (DYN[k] && DYN[k][l] !== undefined) el.textContent = DYN[k][l];
  });
  document.querySelectorAll('.lang-toggle button').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-lang') === l);
  });
}
document.querySelectorAll('.lang-toggle button').forEach(function(b){
  b.addEventListener('click', function(){ applyLang(b.getAttribute('data-lang')); });
});
applyLang('en');
</script>"""