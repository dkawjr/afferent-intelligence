"""build_frontend.py — generate the Afferent Intelligence frontend (index.html).

Reads the verified inventory (inventory/vitaldb.json) and the curated ALIAS_TABLE
from lookup.py and bakes them into a single self-contained index.html.

The page has two modes:
  * AI mode    — when served by app.py with ANTHROPIC_API_KEY set, the decompose
    step is performed by Claude (handles free-form phrasing) via /api/feasibility.
  * Offline    — when opened as a file, or when no API key is configured, a built-in
    keyword matcher does the decomposition. The resolver, inventory, and verdict
    logic are identical either way; only concept *detection* differs.

Either way, the inventory is the single source of truth — re-run after editing it:
    py build_frontend.py
"""

from __future__ import annotations

import json
from pathlib import Path

from lookup import ALIAS_TABLE, load_inventory

ROOT = Path(__file__).parent
OUT = ROOT / "index.html"


def collect() -> tuple[list[dict], dict, dict, object]:
    inv = load_inventory()
    entries = [
        {
            "id": e.id,
            "name": e.name,
            "aliases": e.aliases,
            "status": e.status.value,
            "category": e.category,
            "confidence": e.confidence_level.value,
            "track": e.vitaldb_track,
            "units": e.units,
            "missingness": e.missingness,
            "common_mistakes": e.common_mistakes,
        }
        for e in inv.variables
    ]
    mpath = ROOT / "examples" / "manifest.json"
    example = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else None
    dpath = ROOT / "datasets.json"
    datasets = json.loads(dpath.read_text(encoding="utf-8"))["datasets"] if dpath.exists() else []
    return entries, dict(ALIAS_TABLE), dict(inv.scope), example, datasets


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Afferent Intelligence — VitalDB feasibility triage</title>
<style>
  :root {
    --bg:#f5f7fa; --card:#fff; --ink:#0f172a; --muted:#64748b; --line:#e2e8f0;
    --accent:#0f766e; --accent-soft:#ccfbf1;
    --green:#15803d; --green-bg:#ecfdf5; --green-line:#a7f3d0;
    --amber:#b45309; --amber-bg:#fffbeb; --amber-line:#fde68a;
    --red:#b91c1c; --red-bg:#fef2f2; --red-line:#fecaca;
    --slate:#475569; --slate-bg:#f1f5f9; --slate-line:#cbd5e1;
    --shadow:0 1px 2px rgba(15,23,42,.04), 0 8px 24px rgba(15,23,42,.06);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:15px/1.55 -apple-system,"Segoe UI",Roboto,Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
  .wrap{max-width:860px;margin:0 auto;padding:40px 22px 90px}

  header.brand{display:flex;align-items:center;gap:14px}
  .logo{width:42px;height:42px;flex:none}
  .brand h1{font-size:24px;margin:0;letter-spacing:-.02em;font-weight:680}
  .brand .sub{color:var(--muted);font-size:13.5px;margin-top:2px}
  .modebadge{margin-left:auto;font-size:11.5px;font-weight:650;padding:5px 11px;border-radius:999px;
    border:1px solid var(--line);background:#fff;color:var(--muted);white-space:nowrap}
  .modebadge.ai{color:var(--accent);border-color:var(--accent-soft);background:#f0fdfa}
  .modebadge .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:currentColor;margin-right:6px;vertical-align:middle}

  .tagline{margin:18px 0 26px;padding:14px 16px;background:var(--card);border:1px solid var(--line);
    border-radius:12px;box-shadow:var(--shadow);font-size:14px;color:#334155}
  .tagline b{color:var(--accent)}

  .panel{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:18px}
  label.lbl{display:block;font-size:12.5px;font-weight:650;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
  textarea{width:100%;min-height:80px;resize:vertical;padding:12px 14px;border:1px solid var(--line);
    border-radius:10px;font:inherit;color:var(--ink);background:#fcfdfe;outline:none}
  textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
  .row{display:flex;gap:10px;align-items:center;margin-top:12px;flex-wrap:wrap}
  button.go{background:var(--accent);color:#fff;border:0;border-radius:10px;padding:11px 20px;font:inherit;font-weight:620;cursor:pointer}
  button.go:hover{background:#0c5e57}
  button.go:disabled{opacity:.55;cursor:default}
  .hint{color:var(--muted);font-size:12.5px}
  .examples{margin-top:16px}
  .chips{display:flex;flex-wrap:wrap;gap:8px}
  .chip{background:#f8fafc;border:1px solid var(--line);color:#334155;border-radius:999px;padding:6px 12px;font-size:13px;cursor:pointer}
  .chip:hover{border-color:var(--accent);color:var(--accent);background:#fff}

  #result{margin-top:24px;display:none}
  .verdict{border-radius:14px;padding:18px 20px;border:1px solid;box-shadow:var(--shadow)}
  .verdict .vtop{display:flex;align-items:center;gap:12px}
  .vbadge{font-size:12px;font-weight:750;letter-spacing:.06em;text-transform:uppercase;padding:5px 11px;border-radius:999px;white-space:nowrap}
  .verdict h2{margin:0;font-size:19px;letter-spacing:-.01em}
  .verdict p.reason{margin:12px 0 0;font-size:14.5px;color:#1e293b}
  .v-FEASIBLE{background:var(--green-bg);border-color:var(--green-line)} .v-FEASIBLE .vbadge{background:var(--green);color:#fff} .v-FEASIBLE h2{color:var(--green)}
  .v-FEASIBLE_WITH_CAVEATS{background:var(--amber-bg);border-color:var(--amber-line)} .v-FEASIBLE_WITH_CAVEATS .vbadge{background:var(--amber);color:#fff} .v-FEASIBLE_WITH_CAVEATS h2{color:var(--amber)}
  .v-NOT_FEASIBLE{background:var(--red-bg);border-color:var(--red-line)} .v-NOT_FEASIBLE .vbadge{background:var(--red);color:#fff} .v-NOT_FEASIBLE h2{color:var(--red)}
  .v-INSUFFICIENT_INFO{background:var(--slate-bg);border-color:var(--slate-line)} .v-INSUFFICIENT_INFO .vbadge{background:var(--slate);color:#fff} .v-INSUFFICIENT_INFO h2{color:var(--slate)}

  .seclabel{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:650;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:26px 0 10px}
  .tagchip{font-size:10px;font-weight:700;letter-spacing:.04em;padding:2px 7px;border-radius:5px;text-transform:none}
  .tag-ai{background:#eef2ff;color:#4338ca;border:1px solid #c7d2fe}
  .tag-verified{background:var(--green-bg);color:var(--green);border:1px solid var(--green-line)}

  .peco{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
  .peco .cell{border:1px solid var(--line);border-radius:10px;background:#fbfcfe;padding:10px 12px}
  .peco .k{font-size:11px;font-weight:700;letter-spacing:.04em;color:#6366f1;text-transform:uppercase}
  .peco .val{font-size:14px;margin-top:3px;color:#1e293b}

  .ct{display:grid;gap:10px}
  .crow{border:1px solid var(--line);border-radius:12px;background:var(--card);box-shadow:var(--shadow);overflow:hidden}
  .crow>summary{list-style:none;cursor:pointer;padding:13px 15px;display:flex;align-items:center;gap:12px}
  .crow>summary::-webkit-details-marker{display:none}
  .pill{font-size:11px;font-weight:720;letter-spacing:.04em;padding:4px 9px;border-radius:6px;white-space:nowrap;flex:none}
  .p-CONFIRMED{background:var(--green-bg);color:var(--green);border:1px solid var(--green-line)}
  .p-CONFIRMED_ABSENT{background:var(--red-bg);color:var(--red);border:1px solid var(--red-line)}
  .p-NOT_IN_INVENTORY{background:var(--slate-bg);color:var(--slate);border:1px solid var(--slate-line)}
  .cname{font-weight:620}
  .role{font-size:10.5px;color:var(--muted);border:1px solid var(--line);padding:2px 7px;border-radius:5px;text-transform:uppercase;letter-spacing:.03em}
  .role.outcome{color:var(--accent);border-color:var(--accent-soft);background:#f0fdfa}
  .cmeta{color:var(--muted);font-size:12.5px;margin-left:auto;text-align:right}
  .cbody{padding:0 15px 14px;border-top:1px dashed var(--line);margin-top:2px}
  .cbody .kv{margin-top:10px;font-size:13.5px}
  .cbody .kv b{color:#334155}
  .mono{font-family:ui-monospace,"Cascadia Code",Consolas,monospace;font-size:12.5px;background:#f8fafc;border:1px solid var(--line);padding:1px 6px;border-radius:5px}

  .reframe{border:1px solid var(--accent-soft);background:#f0fdfa;border-radius:12px;padding:15px;margin-top:12px}
  .reframe .h{font-weight:650;color:var(--accent);font-size:14px;margin-bottom:6px}
  .reframe ul{margin:8px 0 0;padding-left:18px}
  .reframe li{margin:3px 0}
  .tag-guide{background:#f1f5f9;color:var(--slate);border:1px solid var(--slate-line)}
  .helper{border:1px solid var(--line);background:var(--card);border-radius:12px;padding:16px;box-shadow:var(--shadow)}
  .helper .htxt{font-size:13.5px;color:#334155}
  .suglist{display:grid;gap:8px;margin-top:12px}
  .sugq{border:1px solid var(--line);border-radius:10px;padding:11px 13px;cursor:pointer;background:#fbfcfe;transition:border-color .12s,background .12s}
  .sugq:hover{border-color:var(--accent);background:#fff}
  .sugq .sq{font-weight:600;font-size:14px;color:#1e293b}
  .sugq .sq::before{content:"↳ ";color:var(--accent)}
  .sugq .sw{font-size:12.5px;color:var(--muted);margin-top:3px}
  .vocabh{font-size:11.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);margin:16px 0 8px}
  .vocab{display:grid;gap:6px}
  .vg{font-size:12.5px;color:#475569}
  .vgk{display:inline-block;min-width:148px;font-weight:650;color:var(--accent)}

  /* study toolkit (after a feasible verdict) */
  .toolkit{border:1px solid var(--line);background:var(--card);border-radius:12px;box-shadow:var(--shadow);padding:16px}
  .checklist{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:7px}
  .checklist li{display:flex;gap:10px;align-items:flex-start;font-size:13.5px;color:#1e293b}
  .checklist input{margin-top:3px;width:16px;height:16px;accent-color:var(--accent);flex:none}
  .checklist li.done span{color:var(--muted);text-decoration:line-through}
  .tkbtns{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
  .btn-pay{background:var(--accent);color:#fff;border:0;border-radius:10px;padding:10px 16px;font:inherit;font-weight:620;cursor:pointer}
  .btn-pay:hover{background:#0c5e57}
  .btn-ghost{background:#fff;color:#334155;border:1px solid var(--line);border-radius:10px;padding:10px 16px;font:inherit;font-weight:600;cursor:pointer}
  .btn-ghost:hover{border-color:var(--accent);color:var(--accent)}
  .savedflag{font-size:12.5px;color:var(--accent);align-self:center}

  /* scope form */
  .scopeform{margin-top:14px;border-top:1px dashed var(--line);padding-top:14px;display:none}
  .ff{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .ff .f{display:flex;flex-direction:column;gap:4px}
  .ff .f.full{grid-column:1/3}
  .ff label{font-size:11.5px;font-weight:650;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
  .ff input[type=text],.ff input[type=number],.ff select,.ff textarea{border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:inherit;background:#fcfdfe}
  .ff textarea{min-height:54px;resize:vertical}
  .covbox{display:flex;flex-wrap:wrap;gap:8px}
  .covbox label{display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:500;text-transform:none;letter-spacing:0;color:#334155;border:1px solid var(--line);border-radius:8px;padding:5px 9px;cursor:pointer}
  .covbox input{accent-color:var(--accent)}

  /* paywall modal */
  .modal{position:fixed;inset:0;background:rgba(15,23,42,.45);display:flex;align-items:center;justify-content:center;z-index:50}
  .modal .box{background:#fff;border-radius:16px;max-width:420px;width:92%;padding:24px;box-shadow:0 20px 60px rgba(15,23,42,.3)}
  .modal h3{margin:0 0 6px;font-size:18px}
  .modal .price{font-size:34px;font-weight:720;color:var(--accent);margin:8px 0}
  .modal ul{margin:6px 0 16px;padding-left:18px;font-size:13px;color:#334155}
  .modal .demo{font-size:11.5px;color:var(--muted);background:#f8fafc;border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:14px}
  .modal .mbtns{display:flex;gap:10px;justify-content:flex-end}

  /* scope results */
  .scoperes{margin-top:16px}
  .plotgrid{display:grid;gap:14px;margin-top:6px}
  .plotcard{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff;box-shadow:var(--shadow)}
  .plotcard img{width:100%;display:block;border-bottom:1px solid var(--line)}
  .plotcard .pc{padding:10px 13px}
  .plotcard .pt{font-weight:620;font-size:13.5px}
  .plotcard .pr{font-size:12.5px;color:var(--muted);margin-top:2px}
  .filelist{display:grid;gap:6px;margin-top:6px}
  .filerow{display:flex;align-items:center;gap:10px;border:1px solid var(--line);border-radius:8px;padding:9px 12px;font-size:13.5px;background:#fbfcfe}
  .filerow .fn{font-family:ui-monospace,Consolas,monospace;font-size:12.5px}
  .filerow a{margin-left:auto}
  .sapblock{font-size:13.5px;color:#1e293b;margin-top:6px}
  .sapblock .k{font-weight:650;color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:.04em;margin-top:10px}

  /* ideas board */
  .ideacard{border:1px solid var(--line);border-radius:10px;padding:11px 13px;margin-top:8px;background:#fbfcfe}
  .ideacard .ih{display:flex;align-items:center;gap:10px}
  .ideacard .iq{font-weight:600;font-size:13.5px;cursor:pointer}
  .ideacard .idate{font-size:11.5px;color:var(--muted);margin-left:auto}
  .ideacard .irm{cursor:pointer;color:var(--muted);font-size:13px;border:0;background:none}
  .miniv{font-size:10px;font-weight:700;padding:2px 7px;border-radius:5px}
  .countbadge{background:var(--accent);color:#fff;border-radius:999px;font-size:11px;padding:1px 8px;margin-left:6px}

  details.card{margin-top:14px;background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);padding:4px 16px}
  details.card summary{cursor:pointer;font-weight:620;padding:12px 0}
  details.card .inner{padding:4px 0 16px;color:#334155;font-size:13.5px}
  .profile{display:grid;grid-template-columns:repeat(2,1fr);gap:8px 18px;margin-top:6px}
  .profile .p{border-left:3px solid var(--accent-soft);padding:2px 0 2px 10px}
  .profile .p .k{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
  .profile .p .v{font-size:13.5px}
  .haves{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  .have{font-size:12px;padding:3px 9px;border-radius:6px;border:1px solid var(--green-line);background:var(--green-bg);color:var(--green)}
  .lack{font-size:12px;padding:3px 9px;border-radius:6px;border:1px solid var(--red-line);background:var(--red-bg);color:var(--red)}
  details.card ol{padding-left:18px}

  footer{margin-top:34px;color:var(--muted);font-size:12px;text-align:center;line-height:1.7}
  footer .nope{color:var(--red);font-weight:600}
  a{color:var(--accent)}
  .spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--accent-soft);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite;vertical-align:middle;margin-right:6px}
  @keyframes spin{to{transform:rotate(360deg)}}

  /* ============================ polish ============================ */
  :root{
    --bg:#f3f6f9; --card:#ffffff; --ink:#0b1220; --muted:#6b7686; --line:#e6eaf0;
    --accent:#0d7a72; --accent-soft:#d4f4ef;
    --shadow:0 1px 2px rgba(16,24,40,.04),0 10px 30px rgba(16,24,40,.07);
  }
  body{background:radial-gradient(1100px 560px at 50% -220px,#e9f5f3 0%,var(--bg) 58%);color:var(--ink)}
  .wrap{max-width:884px}
  .brand h1{font-family:"Iowan Old Style","Palatino Linotype",Georgia,serif;font-weight:700;letter-spacing:-.015em}
  .modebadge{box-shadow:var(--shadow)}
  .tagline{border-radius:14px;line-height:1.6}
  .panel{border-radius:18px;padding:20px}
  textarea{border-radius:12px;font-size:15.5px}
  button.go,.btn-pay{background:linear-gradient(180deg,#12877e,#0c6b63);box-shadow:0 6px 16px rgba(13,122,114,.22);transition:transform .08s,box-shadow .12s;border-radius:11px}
  button.go:hover,.btn-pay:hover{transform:translateY(-1px);box-shadow:0 9px 22px rgba(13,122,114,.28)}
  .chip{transition:all .12s;border-radius:999px}
  .verdict{position:relative;border-radius:16px;padding:20px 22px 20px 26px;overflow:hidden}
  .verdict::before{content:"";position:absolute;left:0;top:0;bottom:0;width:6px}
  .v-FEASIBLE::before{background:var(--green)} .v-FEASIBLE_WITH_CAVEATS::before{background:var(--amber)}
  .v-NOT_FEASIBLE::before{background:var(--red)} .v-INSUFFICIENT_INFO::before{background:var(--slate)}
  .seclabel{margin-top:24px}
  .crow{border-radius:13px;transition:border-color .12s,box-shadow .12s}
  .crow:hover{border-color:#cbd5e1}
  details.card{border-radius:14px}

  /* secondary buttons + action row */
  .actionsrow{display:flex;gap:9px;flex-wrap:wrap;margin-top:14px}
  .btn-mini{font-size:12.5px;font-weight:600;border:1px solid var(--line);background:#fff;border-radius:10px;padding:7px 13px;cursor:pointer;color:#334155;transition:all .12s}
  .btn-mini:hover{border-color:var(--accent);color:var(--accent);transform:translateY(-1px)}

  /* study at a glance */
  .glance{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
  .glance .g{border:1px solid var(--line);border-radius:13px;background:#fbfdfe;padding:12px 13px}
  .glance .g .gk{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
  .glance .g .gv{font-size:14px;margin-top:3px;color:#10243a;font-weight:650;line-height:1.35}
  .glance .g .gs{font-size:11.5px;color:var(--muted);margin-top:3px}
  .layerchip,.avail{font-size:10px;font-weight:700;padding:2px 7px;border-radius:5px;letter-spacing:.02em}
  .layerchip{background:#eef2ff;color:#4338ca;border:1px solid #c7d2fe}
  .avail{background:#fff7ed;color:#9a3412;border:1px solid #fed7aa}

  /* pricing menu */
  .menu{display:grid;gap:8px;margin-top:8px}
  .mrow{display:flex;align-items:center;gap:11px;border:1px solid var(--line);border-radius:11px;padding:11px 13px;cursor:pointer;background:#fff;transition:border-color .12s}
  .mrow:hover{border-color:var(--accent)}
  .mrow input{accent-color:var(--accent);width:16px;height:16px}
  .mrow .ml{font-size:13.5px;font-weight:600;color:#1e293b}
  .mrow .mp{margin-left:auto;font-weight:750;color:var(--accent)}
  .mbundle{border-style:dashed;background:#f0fdfa}
  .mtotal{display:flex;align-items:center;margin-top:12px;font-weight:700;font-size:14px}
  .mtotal .mt{margin-left:auto;font-size:22px;color:var(--accent)}
  .notoffered{font-size:11.5px;color:var(--muted);margin-top:10px;border-top:1px dashed var(--line);padding-top:9px}
  .notoffered b{color:#b91c1c}

  /* discussion mode */
  .discuss{margin:18px 0 0;border:1px solid var(--line);border-radius:16px;background:var(--card);box-shadow:var(--shadow);padding:16px;display:none}
  .discuss h3{margin:0 0 4px;font-size:16px}
  .dmsgs{display:flex;flex-direction:column;gap:10px;max-height:400px;overflow:auto;padding:6px 2px;margin-top:10px}
  .dmsg{max-width:88%;padding:10px 13px;border-radius:13px;font-size:13.8px;line-height:1.5;white-space:pre-wrap}
  .dmsg.user{align-self:flex-end;background:var(--accent);color:#fff;border-bottom-right-radius:4px}
  .dmsg.bot{align-self:flex-start;background:#f1f5f9;color:#1e293b;border-bottom-left-radius:4px}
  .dinrow{display:flex;gap:8px;margin-top:12px}
  .dinrow input{flex:1;border:1px solid var(--line);border-radius:11px;padding:11px 13px;font:inherit;background:#fcfdfe}
  .dinrow input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}

  /* novelty */
  .novlist{display:grid;gap:8px;margin-top:6px}
  .novrow{border:1px solid var(--line);border-radius:11px;padding:10px 13px;background:#fbfdfe}
  .novrow .nt{font-size:13.5px;font-weight:600;color:#10243a;line-height:1.4}
  .novrow .nm{font-size:12px;color:var(--muted);margin-top:3px}
  .novassess{border-radius:11px;padding:11px 13px;margin-bottom:8px;font-size:13.5px;line-height:1.5}
  .na-likely_done{background:var(--red-bg);border:1px solid var(--red-line);color:#7f1d1d}
  .na-partially_addressed{background:var(--amber-bg);border:1px solid var(--amber-line);color:#7c2d12}
  .na-appears_novel{background:var(--green-bg);border:1px solid var(--green-line);color:#14532d}
  .na-uncertain{background:var(--slate-bg);border:1px solid var(--slate-line);color:#334155}

  /* researcher insights */
  .vprofile{display:flex;align-items:center;gap:11px;background:var(--green-bg);border:1px solid var(--green-line);border-radius:12px;padding:11px 14px;margin-top:12px}
  .vprofile .vn{font-weight:650;font-size:14.5px}
  .vprofile .vmeta{font-size:12.5px;color:var(--muted);margin-top:1px}
  .vok{font-size:11px;font-weight:700;color:#fff;background:var(--green);border-radius:999px;padding:4px 10px;white-space:nowrap}
  .topicchips{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
  .topicchip{font-size:12px;background:#eef2ff;color:#4338ca;border:1px solid #c7d2fe;border-radius:999px;padding:3px 11px}
  .recgrid{display:grid;gap:10px;margin-top:4px}
  .reccard{border:1px solid var(--line);border-radius:14px;background:#fbfdfe;padding:13px 15px}
  .reccard .rh{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .reccard .rn{font-weight:680;font-size:15px}
  .fitbadge{font-size:10px;font-weight:700;padding:3px 8px;border-radius:6px;text-transform:uppercase;letter-spacing:.03em}
  .fit-strong{background:var(--green-bg);color:var(--green);border:1px solid var(--green-line)}
  .fit-moderate{background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber-line)}
  .fit-exploratory{background:var(--slate-bg);color:var(--slate);border:1px solid var(--slate-line)}
  .reccard .racc{margin-left:auto;font-size:11.5px;color:var(--muted)}
  .reccard .rw{font-size:13px;color:#334155;margin-top:6px;line-height:1.45}
  .reccard .rlit{margin-top:9px;border-top:1px dashed var(--line);padding-top:8px;display:grid;gap:3px}

  /* ===================== Apple-esque refinement ===================== */
  :root{
    --bg:#fbfbfd; --card:#ffffff; --ink:#1d1d1f; --muted:#6e6e73; --line:#e4e4e9;
    --accent:#0a7d74; --accent-2:#0a6a62; --accent-soft:#e3f4f1;
    --green:#1c7d3f; --green-bg:#eef9f1; --green-line:#cbe9d3;
    --amber:#9a6212; --amber-bg:#fdf6ea; --amber-line:#f0e0bf;
    --red:#c0392b; --red-bg:#fdf0ee; --red-line:#f4d3cd;
    --slate:#5b6573; --slate-bg:#f3f4f6; --slate-line:#dfe2e7;
    --shadow:0 1px 1px rgba(0,0,0,.03),0 14px 44px rgba(0,0,0,.07);
    --radius:22px;
  }
  *{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
  body{background:linear-gradient(180deg,#ffffff 0%,#f4f5f7 100%);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,Helvetica,Arial,sans-serif;letter-spacing:-.011em}
  .wrap{max-width:824px;padding:58px 24px 110px}
  header.brand{gap:15px;align-items:center}
  .logo{width:44px;height:44px}
  .brand h1{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",sans-serif;font-size:30px;font-weight:700;letter-spacing:-.03em}
  .brand .sub{font-size:15px;color:var(--muted);letter-spacing:-.01em;margin-top:3px}
  .modebadge{font-size:12px;font-weight:550;border-radius:999px;background:rgba(255,255,255,.65);
    -webkit-backdrop-filter:saturate(180%) blur(14px);backdrop-filter:saturate(180%) blur(14px);border:1px solid var(--line);box-shadow:none}
  .modebadge.ai{color:var(--accent);background:var(--accent-soft);border-color:transparent}
  .tagline{font-size:17px;line-height:1.6;color:#3a3a3c;background:transparent;border:0;box-shadow:none;padding:8px 2px 0;margin:24px 0 30px}
  .tagline b{color:var(--ink);font-weight:600}
  .panel{border-radius:var(--radius);padding:26px;background:rgba(255,255,255,.74);
    -webkit-backdrop-filter:saturate(180%) blur(20px);backdrop-filter:saturate(180%) blur(20px);border:1px solid rgba(0,0,0,.06);box-shadow:var(--shadow)}
  label.lbl{font-size:11.5px;letter-spacing:.03em;color:var(--muted)}
  textarea{border-radius:15px;border:1px solid var(--line);background:#fff;font-size:17px;padding:15px 16px;line-height:1.45}
  textarea:focus{border-color:var(--accent);box-shadow:0 0 0 4px var(--accent-soft)}
  button.go,.btn-pay{background:var(--accent);border-radius:980px;padding:12px 22px;font-weight:580;font-size:15px;letter-spacing:-.01em;box-shadow:none;transition:background .15s ease,transform .1s ease}
  button.go:hover,.btn-pay:hover{background:var(--accent-2);transform:translateY(-1px)}
  .btn-ghost{border-radius:980px;border:1px solid var(--line);background:#fff;font-weight:550;padding:11px 18px;color:#1d1d1f}
  .btn-ghost:hover{background:#f5f5f7;border-color:#cfcfd6;color:var(--ink);transform:none}
  .btn-mini{border-radius:980px;padding:8px 15px;font-weight:550}
  .btn-mini:hover{transform:none;background:#f5f5f7}
  .chip{border-radius:980px;background:#fff;border:1px solid var(--line);padding:8px 14px;font-size:13.5px;color:#3a3a3c}
  .chip:hover{background:#f5f5f7;border-color:#cfcfd6;color:var(--ink)}
  .hint{font-size:12.5px;color:var(--muted)}
  .verdict{border-radius:var(--radius);padding:26px 28px;border:1px solid rgba(0,0,0,.05);box-shadow:var(--shadow)}
  .verdict::before{display:none}
  .verdict h2{font-size:23px;letter-spacing:-.022em;font-weight:680}
  .vbadge{border-radius:980px;font-weight:650;letter-spacing:.03em}
  .verdict p.reason{font-size:16px;line-height:1.6;color:#3a3a3c}
  .seclabel{font-size:11.5px;letter-spacing:.04em;color:var(--muted);margin:30px 0 12px}
  .tagchip{border-radius:980px}
  .crow{border-radius:16px;border-color:var(--line)}
  .crow:hover{border-color:#cfcfd6;box-shadow:0 8px 24px rgba(0,0,0,.05)}
  .pill{border-radius:980px}
  details.card{border-radius:18px;border-color:rgba(0,0,0,.06);box-shadow:var(--shadow)}
  .glance .g{border-radius:16px;background:#fff;border-color:var(--line)}
  .toolkit,.helper,.discuss{border-radius:18px;box-shadow:var(--shadow);border-color:rgba(0,0,0,.06)}
  .mrow{border-radius:14px;border-color:var(--line)}
  .mrow:hover{background:#f9f9fb}
  .mtotal .mt{font-weight:700;letter-spacing:-.01em}
  .sugq{border-radius:14px}
  .plotcard{border-radius:16px}
  .filerow{border-radius:12px}
  .ideacard{border-radius:14px}
  .modal{-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);background:rgba(0,0,0,.3)}
  .modal .box{border-radius:26px;padding:30px;box-shadow:0 30px 90px rgba(0,0,0,.35)}
  .modal .price{font-weight:700;letter-spacing:-.02em}
  .dmsg{border-radius:18px;font-size:14px}
  .dmsg.user{background:var(--accent)}
  .dinrow input{border-radius:980px;padding:12px 16px}
  footer{font-size:12.5px;color:var(--muted);margin-top:46px}
  @media (max-width:640px){
    html,body{overflow-x:hidden}
    .wrap{padding:30px 15px 80px}
    header.brand{flex-wrap:wrap;gap:12px}
    .brand>div{flex:1 1 auto;min-width:0}
    .brand h1{font-size:25px}
    .brand .sub{font-size:13px}
    .modebadge{flex-basis:100%;margin-left:0;text-align:center}
    .tagline{font-size:15.5px;margin:18px 0 22px}
    .panel{padding:18px;border-radius:18px}
    textarea{font-size:16px}
    .row{gap:8px}
    .row .go,.row .btn-ghost{flex:1 1 auto;text-align:center}
    .verdict{padding:20px 18px;border-radius:18px}
    .verdict h2{font-size:20px}
    .verdict p.reason{font-size:15px}
    .glance,.peco,.ff,.profile{grid-template-columns:1fr}
    .crow>summary{flex-wrap:wrap;row-gap:6px}
    .cmeta{margin-left:0;width:100%;text-align:left}
    .vgk{min-width:0;display:block;margin-bottom:1px}
    .tkbtns{flex-direction:column;align-items:stretch}
    .tkbtns>*{width:100%;text-align:center}
    .actionsrow .btn-mini{flex:1 1 auto;text-align:center}
    .dinrow{flex-direction:column}
    .dinrow .go{width:100%}
    .mtotal .mt{font-size:20px}
    .modal .box{padding:22px;border-radius:22px}
    .plotcard img{height:auto}
    .filerow{flex-wrap:wrap;row-gap:4px}
    .filerow a{margin-left:0}
  }
  @media (max-width:380px){ .brand h1{font-size:22px} .verdict h2{font-size:18px} }
</style>
</head>
<body>
<div class="wrap">

  <header class="brand">
    <svg class="logo" viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <circle cx="24" cy="24" r="9" fill="#0f766e"/>
      <circle cx="24" cy="24" r="9" stroke="#0f766e" stroke-opacity=".25" stroke-width="6"/>
      <g stroke="#0f766e" stroke-width="2.4" stroke-linecap="round">
        <path d="M5 9 L15 17"/><path d="M5 24 L13 24"/><path d="M5 39 L15 31"/>
        <path d="M43 9 L33 17"/><path d="M43 24 L35 24"/><path d="M43 39 L33 31"/>
      </g>
      <g fill="#0f766e">
        <circle cx="15" cy="17" r="2"/><circle cx="13" cy="24" r="2"/><circle cx="15" cy="31" r="2"/>
        <circle cx="33" cy="17" r="2"/><circle cx="35" cy="24" r="2"/><circle cx="33" cy="31" r="2"/>
      </g>
    </svg>
    <div>
      <h1>Afferent Intelligence</h1>
      <div class="sub">Research feasibility triage for VitalDB — before you spend months on it</div>
    </div>
    <span class="modebadge" id="modebadge"><span class="dot"></span>checking…</span>
  </header>

  <div class="tagline">
    Describe a perioperative study question in plain English. Afferent decomposes it (<b>PECO</b>),
    resolves the required variables against a <b>verified inventory</b> of what VitalDB actually
    records, and returns a feasibility verdict. Its most valuable output is a <b>trustworthy&nbsp;“no.”</b>
    The no-guessing rule means it never claims a variable exists unless the inventory confirms it.
  </div>

  <div class="panel">
    <label class="lbl" for="q">Your research question</label>
    <textarea id="q" placeholder="e.g. Can intraoperative burst suppression predict whether a patient develops delirium afterward?"></textarea>
    <div class="row">
      <button class="go" id="run">Check feasibility</button>
      <button class="btn-ghost" id="discussbtn">💬 Discuss an idea</button>
      <span class="hint">Single-center (SNUH) · intraoperative + in-hospital + &plusmn;90-day labs</span>
    </div>
    <div class="examples">
      <div class="lbl">Try one</div>
      <div class="chips" id="examples"></div>
    </div>
  </div>

  <div class="discuss" id="discuss">
    <h3>Idea discussion</h3>
    <div style="font-size:13px;color:var(--muted)">Brainstorm and sharpen a question with a VitalDB-grounded partner. It points you toward variables the dataset actually has — and won't write your paper. When a question feels solid, run it through the feasibility check.</div>
    <div class="dmsgs" id="dmsgs"></div>
    <div class="dinrow">
      <input type="text" id="dinput" placeholder="e.g. I'm interested in anesthesia depth and recovery — what's doable here?">
      <button class="go" id="dsend">Send</button>
    </div>
  </div>

  <details class="card" id="researchcard">
    <summary>For researchers — get verified &amp; personalized <span class="countbadge" id="verchip" style="display:none">✓</span></summary>
    <div class="inner">
      <div style="font-size:13.5px;color:var(--muted)">Verify with your ORCID to get dataset recommendations, knowledge-base gaps, relevant literature, and collaboration advice tuned to your work. ORCID is verified via its public API; Google Scholar is an optional link.</div>
      <div class="ff" style="margin-top:12px">
        <div class="f"><label>ORCID iD</label><input type="text" id="orcid" placeholder="0000-0000-0000-0000"></div>
        <div class="f"><label>Google Scholar URL (optional)</label><input type="text" id="scholar" placeholder="https://scholar.google.com/citations?user=…"></div>
        <div class="f full"><label>Research interests (optional)</label><input type="text" id="interests" placeholder="e.g. intraoperative hemodynamics, AKI prediction, ICU sepsis"></div>
      </div>
      <div class="tkbtns"><button class="btn-pay" id="verifybtn">Verify &amp; personalize</button></div>
      <div id="profileres"></div>
    </div>
  </details>

  <details class="card" id="ideascard" style="display:none">
    <summary>My ideas <span class="countbadge" id="ideacount">0</span></summary>
    <div class="inner" id="ideasbody"></div>
  </details>

  <div id="result"></div>

  <details class="card" id="profilecard">
    <summary>VitalDB dataset profile</summary>
    <div class="inner" id="profilebody"></div>
  </details>

  <details class="card">
    <summary>How this works &amp; the no-guessing rule</summary>
    <div class="inner">
      <ol>
        <li><b>Decompose</b> (inference) — your question becomes PECO and a list of required clinical concepts.
            In AI mode this is done by the model so it handles free-form phrasing; offline, a keyword matcher does it.</li>
        <li><b>Resolve</b> (verified facts) — each concept is checked against the inventory:
            <span class="mono">CONFIRMED</span>, <span class="mono">CONFIRMED_ABSENT</span>, or <span class="mono">NOT_IN_INVENTORY</span>.
            <b>Status comes only from the inventory, never from the model</b> — that is the no-guessing rule.</li>
        <li><b>Verdict</b> — any confirmed-absent concept &rarr; <b>NOT_FEASIBLE</b>; anything unverified &rarr;
            <b>INSUFFICIENT_INFO</b>; otherwise <b>FEASIBLE</b> / <b>FEASIBLE_WITH_CAVEATS</b>.</li>
      </ol>
      <p>Inference (PECO, suggested reframes) and verified facts (the inventory truth table) are shown in
      separate sections on purpose — the engine's trust comes from never blurring the two.</p>
      <p><b>Source:</b> VitalDB data descriptor (Lee et&nbsp;al., <i>Scientific Data</i> 2022) and PhysioNet
      vitaldb 1.0.0. Inventory: <span id="ic"></span> concepts catalogued.</p>
    </div>
  </details>

  <footer>
    Afferent Intelligence · feasibility triage, not clinical advice.<br/>
    A confident <span class="nope">“no”</span> that saves a doomed protocol is the product.
  </footer>
</div>

<script>
const ENTRIES = /*__ENTRIES__*/;
const ALIASES = /*__ALIASES__*/;
const SCOPE   = /*__SCOPE__*/;
const SOURCE_URL = "https://www.nature.com/articles/s41597-022-01411-5";

const EXAMPLES = [
  "Can intraoperative burst suppression predict postoperative delirium?",
  "Is intraoperative hypotension associated with postoperative acute kidney injury?",
  "Does low intraoperative cardiac output predict in-hospital mortality?",
  "Does intraoperative mean arterial pressure predict 30-day mortality?",
  "Is ASA physical status associated with intraoperative oxygen desaturation?",
  "Do genetic markers modify a patient's response to anesthetic depth?"
];

let AI_ENABLED = false;
let DEMO = false;           // true when no backend (e.g. static GitHub Pages) — show illustrative previews
let CURRENT = null;
// defaults so the pricing menu renders even with no backend; /api/health overrides these
let PRICING = {
  plan:{label:"Statistical analysis plan",price:15}, extraction:{label:"VitalDB data-extraction script",price:10},
  dictionary:{label:"Data dictionary & variable manifest",price:5}, figures:{label:"Suggested figures (templates + code)",price:12},
  power:{label:"Power / sample-size estimate",price:12}, github:{label:"Private GitHub repo (clone-ready)",price:8}
};
let BUNDLE = {label:"Full scoping pack (everything)", price:49};
let NOVELTY_PRICE = 9;
const EXAMPLE = /*__EXAMPLE__*/;   // sample scoping pack manifest baked at build time
const NOVELTY_EXAMPLE = [
  {title:"Relationship between Intraoperative Hypotension and Acute Kidney and Myocardial Injury after Noncardiac Surgery: A Retrospective Cohort Analysis", journal:"Anesthesiology", year:"2017", pmid:"28296809", url:"https://pubmed.ncbi.nlm.nih.gov/28296809/"},
  {title:"Intraoperative hypotension and postoperative acute kidney injury: A systematic review", journal:"American Journal of Surgery", year:"2024", pmid:"38040526", url:"https://pubmed.ncbi.nlm.nih.gov/38040526/"},
  {title:"Intraoperative hypotension and the risk of postoperative adverse outcomes: a systematic review", journal:"British Journal of Anaesthesia", year:"2018", pmid:"30236233", url:"https://pubmed.ncbi.nlm.nih.gov/30236233/"}
];
const DATASETS = /*__DATASETS__*/;
const GAPS_ABSENT = ENTRIES.filter(e=>e.status==="CONFIRMED_ABSENT").map(e=>e.name+" — not recorded in VitalDB; needs a dataset with ward or post-discharge follow-up.");
const COLLAB_GENERIC = [
  "Pair clinical domain expertise with a methods/statistics collaborator before locking the analysis plan.",
  "Find a co-author who already holds credentialed access (e.g. PhysioNet) for datasets that require it.",
  "Post the question in the dataset's community (PhysioNet forums, dataset listserv) to surface prior or parallel work."
];
const ORCID_RE=/^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/;

// ---- next-steps checklist (what to do after a question is feasible) ----
const CHECKLIST = [
  "Lock the PECO and pick primary vs secondary outcomes.",
  "Operationalize exposure & outcome (thresholds, durations, time windows).",
  "Define cohort inclusion/exclusion, then estimate the analyzable N on the relevant track subset.",
  "Pre-register the analysis plan (e.g. OSF) before touching the outcome data.",
  "Generate the scoping pack: analysis plan, extraction script, data dictionary, figure templates.",
  "Extract the data and audit completeness / informative missingness.",
  "Have a statistician review the model choice and power.",
  "Run the analysis on real data → make figures → then (separately) write it up."
];

// ---- local persistence (ideas + checklist state) ----
const LS_IDEAS="afferent_ideas", LS_CHECKS="afferent_checks";
const qkey = q => (q||"").trim().toLowerCase();
function getIdeas(){ try{return JSON.parse(localStorage.getItem(LS_IDEAS))||[]}catch(e){return[]} }
function setIdeas(a){ localStorage.setItem(LS_IDEAS, JSON.stringify(a)); }
function getChecks(){ try{return JSON.parse(localStorage.getItem(LS_CHECKS))||{}}catch(e){return{}} }
function setChecks(o){ localStorage.setItem(LS_CHECKS, JSON.stringify(o)); }

// ---- shared inventory index (mirror of lookup.py) ----
const norm = s => s.trim().toLowerCase().replace(/[\s\-\/]+/g,"_");
const INDEX = {};
for(const e of ENTRIES){ if(!(e.id in INDEX)) INDEX[e.id]=e; for(const a of e.aliases){const k=norm(a); if(!(k in INDEX)) INDEX[k]=e;} }
const CONFIRMED_OUTCOMES = ENTRIES.filter(e=>e.category==="outcome" && e.status==="CONFIRMED").map(e=>({id:e.id,name:e.name}));

// well-formed, VitalDB-answerable example questions (offline fallback suggestions)
const SUGGESTED = [
  "Does intraoperative hypotension (MAP < 65 mmHg) predict postoperative AKI?",
  "Is intraoperative burst suppression associated with patient age?",
  "Does low intraoperative cardiac output predict in-hospital mortality?",
  "Is ASA physical status associated with intraoperative SpO2 desaturation?"
];

// vocabulary the engine recognizes, grouped (built from the confirmed inventory)
const CATLABEL={signal:"Signals",hemodynamic:"Hemodynamics",respiratory:"Respiratory",
  demographic:"Demographics & case",intraoperative:"Intraop drugs/fluids",laboratory:"Labs",outcome:"In-hospital outcomes"};
const VOCAB=(function(){
  const g={};
  for(const e of ENTRIES){ if(e.status!=="CONFIRMED")continue;
    const k=CATLABEL[e.category]||e.category;
    (g[k]=g[k]||[]).push(e.name.replace(/\s*\(.*?\)\s*/g," ").trim()); }
  const order=["Signals","Hemodynamics","Respiratory","Demographics & case","Intraop drugs/fluids","Labs","In-hospital outcomes"];
  return order.filter(o=>g[o]).map(o=>({group:o,items:g[o].slice(0,6)}));
})();

function resolveOne(concept){
  const key=norm(concept); let entry=null;
  const tid=ALIASES[key]; if(tid) entry=INDEX[tid];
  if(!entry) entry=INDEX[key];
  if(!entry) return {label:concept,status:"NOT_IN_INVENTORY",resolved_id:null,entry:null};
  const status=entry.status==="CONFIRMED"?"CONFIRMED":"CONFIRMED_ABSENT";
  return {label:concept,status,resolved_id:entry.id,entry};
}

// ---- offline keyword concept extraction ----
let PHRASES=null;
function buildPhrases(){
  const seen=new Set(),out=[];
  const add=(raw,id)=>{const p=raw.toLowerCase().replace(/[^a-z0-9]+/g," ").trim(); if(p.length<3)return;
    const k=p+"=>"+id; if(seen.has(k))return; seen.add(k); out.push({p,id});};
  for(const [k,v] of Object.entries(ALIASES)) add(k,v);
  for(const e of ENTRIES){ add(e.name,e.id); for(const a of e.aliases) add(a,e.id);}
  out.sort((a,b)=>b.p.length-a.p.length); return out;
}
function extractConcepts(q){
  if(!PHRASES)PHRASES=buildPhrases();
  let hay=" "+q.toLowerCase().replace(/[^a-z0-9]+/g," ").trim().replace(/\s+/g," ")+" ";
  const found=[],ids=new Set();
  for(const {p,id} of PHRASES){const needle=" "+p+" ";
    if(hay.indexOf(needle)!==-1){hay=hay.split(needle).join("  "+" ".repeat(p.length)+"  ");
      if(!ids.has(id)){ids.add(id);found.push({phrase:p,id});}}}
  return found;
}

// ---- verdict (shared) ----
function deriveVerdict(res){
  if(res.length===0) return {v:"INSUFFICIENT_INFO",title:"No clinical concepts recognized",
    reason:"Name the exposure and the outcome explicitly — e.g. “burst suppression” (exposure) and “postoperative delirium” (outcome)."};
  const absent=res.filter(r=>r.status==="CONFIRMED_ABSENT");
  const notin=res.filter(r=>r.status==="NOT_IN_INVENTORY");
  if(absent.length) return {v:"NOT_FEASIBLE",title:"Not feasible in VitalDB",
    reason:"VitalDB does not collect: "+absent.map(r=>r.entry.name).join("; ")+". This is the data boundary — no modelling can recover a variable that was never recorded."};
  if(notin.length) return {v:"INSUFFICIENT_INFO",title:"Insufficient information — not yet verified",
    reason:"Not in the verified inventory: "+notin.map(r=>r.label).join(", ")+". Per the no-guessing rule, these must be checked against VitalDB documentation before a verdict."};
  const soft=res.filter(r=>r.entry.confidence!=="high");
  if(soft.length) return {v:"FEASIBLE_WITH_CAVEATS",title:"Feasible — with caveats",
    reason:"Every required variable is present, but some are device-subset, case-total, or derived rather than pre-labelled: "+soft.map(r=>r.entry.name).join("; ")+". Check coverage and definitions before committing."};
  return {v:"FEASIBLE",title:"Feasible in VitalDB",
    reason:"Every required variable is confirmed present at high confidence. Verify cohort size on the relevant device/track subset, then proceed."};
}

// ---- build a unified result object ----
function offlineResult(q){
  const concepts=extractConcepts(q).map(c=>{
    const r=resolveOne(c.phrase);
    r.role=(r.entry&&r.entry.category==="outcome")?"outcome":"variable";
    return r;
  });
  const verdict=deriveVerdict(concepts);
  let suggestion=null;
  if(verdict.v==="NOT_FEASIBLE") suggestion={reframe:null,alternatives:CONFIRMED_OUTCOMES};
  return {mode:"offline",question:q,peco:null,concepts,verdict,suggestion,rewrites:null};
}

function aiResultToUnified(data){
  const concepts=data.concepts.map(c=>({label:c.label,role:c.role,status:c.status,resolved_id:c.resolved_id,entry:c.entry}));
  // re-derive the verdict label/title/reason locally for consistent copy
  const v=deriveVerdict(concepts.map(c=>({label:c.label,status:c.status,entry:c.entry})));
  return {mode:"ai",question:data.question,peco:data.peco,concepts,verdict:v,suggestion:data.suggestion,rewrites:data.rewrites||null};
}

function renderReframeHelper(R){
  const hasAI = R.rewrites && R.rewrites.length;
  let h=`<div class="seclabel">How to ask this so Afferent can answer it <span class="tagchip ${hasAI?"tag-ai":"tag-guide"}">${hasAI?"AI-inferred":"guide"}</span></div>`;
  h+=`<div class="helper">`;
  h+=`<div class="htxt">A question Afferent can resolve names a <b>population</b>, an <b>exposure</b>, and an <b>outcome</b>, and stays inside VitalDB's window (intraoperative signals + in-hospital outcomes + &plusmn;90-day labs). Pick a reformulation below, or mention concepts from the vocabulary.</div>`;
  const sugs = hasAI ? R.rewrites : SUGGESTED.map(q=>({question:q,why:null}));
  h+=`<div class="suglist">`;
  for(const s of sugs){
    h+=`<div class="sugq" data-q="${esc(s.question)}"><div class="sq">${esc(s.question)}</div>${s.why?`<div class="sw">${esc(s.why)}</div>`:""}</div>`;
  }
  h+=`</div>`;
  h+=`<div class="vocabh">Concepts Afferent recognizes</div><div class="vocab">`;
  for(const g of VOCAB){ h+=`<div class="vg"><span class="vgk">${esc(g.group)}</span> ${g.items.map(esc).join(" · ")}</div>`; }
  h+=`</div></div>`;
  return h;
}

// ---- rendering ----
const CONF={high:"high confidence",medium:"medium confidence",low:"low confidence"};
function esc(s){return (s==null?"":String(s)).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function dataLayer(e){ if(!e)return""; const t=e.track||"";
  if(e.category==="outcome")return"in-hospital outcome";
  if(/lab_data/i.test(t)||e.category==="laboratory")return"lab series (±90d)";
  if(/^clinical_info/.test(t))return"clinical table";
  if(/derived from/i.test(t))return"derived";
  return"intraop track"; }
function availability(e){ if(!e)return""; const m=(e.missingness||"").toLowerCase();
  if(/subset|device|only when|arterial line|bis module|advanced monitor|invos|orchestra/.test(m))return"device subset";
  if(/case total|case-total|estimated|clinician-estimated/.test(m))return"case-level total";
  if(/derived|derivable/.test(m))return"derived endpoint";
  if(/near-complete|mostly complete|well populated|near complete/.test(m))return"broad coverage";
  return""; }

function renderResult(R){
  CURRENT=R;
  let h="";
  // verdict
  h+=`<div class="verdict v-${R.verdict.v}"><div class="vtop"><span class="vbadge">${R.verdict.v.replace(/_/g," ")}</span><h2>${esc(R.verdict.title)}</h2></div><p class="reason">${esc(R.verdict.reason)}</p></div>`;

  // reframe helper — the most useful thing to show when we couldn't resolve the question
  if(R.verdict.v==="INSUFFICIENT_INFO"){ h+=renderReframeHelper(R); }

  // free report + (feasible) novelty scan
  h+=`<div class="actionsrow"><button class="btn-mini" id="dlreport">↓ Feasibility report (free)</button>`;
  if(R.verdict.v.indexOf("FEASIBLE")===0) h+=`<button class="btn-mini" id="novbtn">Prior-work / novelty scan — $${NOVELTY_PRICE}</button>`;
  h+=`</div><div id="novres"></div>`;

  // study at a glance (feasible)
  if(R.verdict.v.indexOf("FEASIBLE")===0){ h+=renderGlance(R); }

  // PECO (inference) — only in AI mode
  if(R.peco){
    h+=`<div class="seclabel">Question decomposition <span class="tagchip tag-ai">AI-inferred</span></div>`;
    h+=`<div class="peco">`;
    h+=`<div class="cell"><div class="k">Population</div><div class="val">${esc(R.peco.population)}</div></div>`;
    h+=`<div class="cell"><div class="k">Exposure</div><div class="val">${esc(R.peco.exposure)}</div></div>`;
    h+=`<div class="cell"><div class="k">Comparator</div><div class="val">${esc(R.peco.comparator)}</div></div>`;
    h+=`<div class="cell"><div class="k">Outcome</div><div class="val">${esc(R.peco.outcome)}</div></div>`;
    h+=`</div>`;
  }

  // truth table (verified facts)
  if(R.concepts.length){
    h+=`<div class="seclabel">Concepts resolved against the inventory <span class="tagchip tag-verified">Verified facts</span></div><div class="ct">`;
    for(const r of R.concepts){
      const isOut=r.entry&&r.entry.category==="outcome";
      const roleTxt=r.role||(isOut?"outcome":"variable");
      const lay=dataLayer(r.entry), av=availability(r.entry);
      let track=r.entry?(r.entry.track?`<span class="mono">${esc(r.entry.track)}</span>`:""):`<span class="mono">unverified</span>`;
      h+=`<details class="crow"${r.status!=="CONFIRMED"?" open":""}><summary>`;
      h+=`<span class="pill p-${r.status}">${r.status.replace(/_/g," ")}</span>`;
      h+=`<span class="cname">${esc(r.entry?r.entry.name:r.label)}</span> <span class="role ${isOut?"outcome":""}">${esc(roleTxt)}</span>`;
      if(lay) h+=` <span class="layerchip">${esc(lay)}</span>`;
      if(av) h+=` <span class="avail">${esc(av)}</span>`;
      h+=`<span class="cmeta">${r.entry?esc(CONF[r.entry.confidence]||""):"not in inventory"}</span></summary>`;
      h+=`<div class="cbody">`;
      if(r.entry){
        h+=`<div class="kv"><b>Where:</b> ${track}${r.entry.units?" · "+esc(r.entry.units):""}${lay?" · "+esc(lay):""}${av?" · <i>"+esc(av)+"</i>":""}</div>`;
        h+=`<div class="kv"><b>Missingness:</b> ${esc(r.entry.missingness)}</div>`;
        h+=`<div class="kv"><b>Common mistake:</b> ${esc(r.entry.common_mistakes)}</div>`;
      } else {
        h+=`<div class="kv">Matched the question but is not in the verified inventory, so no claim is made either way. Verify against VitalDB documentation and add it before relying on it.</div>`;
      }
      h+=`</div></details>`;
    }
    h+=`</div>`;
  }

  // suggested reframe (inference) — the helpful no
  if(R.suggestion){
    h+=`<div class="seclabel">What you could study instead <span class="tagchip tag-ai">AI-inferred</span></div>`;
    h+=`<div class="reframe">`;
    if(R.suggestion.reframe){ h+=`<div class="h">Suggested reframe</div><div>${esc(R.suggestion.reframe)}</div>`; }
    else { h+=`<div class="h">The blocking variable isn't recorded — but related questions are answerable.</div>`; }
    if(R.suggestion.alternatives&&R.suggestion.alternatives.length){
      h+=`<div style="margin-top:8px;font-size:13px;color:#334155">Confirmed in-hospital outcomes you could pivot to:</div><ul>`;
      for(const a of R.suggestion.alternatives) h+=`<li>${esc(a.name)}</li>`;
      h+=`</ul>`;
    }
    h+=`</div>`;
  }

  // study toolkit (only when feasible)
  if(R.verdict.v.indexOf("FEASIBLE")===0){ h+=renderToolkit(R); }

  const el=document.getElementById("result");
  el.innerHTML=h; el.style.display="block";
  el.querySelectorAll(".sugq").forEach(n=>n.addEventListener("click",()=>{
    const q=n.getAttribute("data-q"); qEl.value=q; runQuery(q);
  }));
  const rb=el.querySelector("#dlreport"); if(rb) rb.addEventListener("click",()=>downloadReport(R));
  const nb=el.querySelector("#novbtn"); if(nb) nb.addEventListener("click",()=>onNovelty(R));
  if(R.verdict.v.indexOf("FEASIBLE")===0) wireToolkit(el,R);
  el.scrollIntoView({behavior:"smooth",block:"start"});
}

function renderGlance(R){
  const conf=R.concepts.filter(c=>c.status==="CONFIRMED");
  const outs=conf.filter(c=>c.role==="outcome"||(c.entry&&c.entry.category==="outcome"));
  const exps=conf.filter(c=>!outs.includes(c)&&c.role!=="covariate");
  const layers=[...new Set(conf.map(c=>dataLayer(c.entry)).filter(Boolean))];
  const caveats=conf.filter(c=>c.entry&&c.entry.confidence!=="high").length;
  const nm=c=>c.entry?c.entry.name:c.label;
  let h=`<div class="seclabel">Study at a glance <span class="tagchip tag-verified">verified variables</span></div><div class="glance">`;
  h+=`<div class="g"><div class="gk">Exposure(s)</div><div class="gv">${esc(exps.map(nm).join(", ")||"—")}</div></div>`;
  h+=`<div class="g"><div class="gk">Outcome(s)</div><div class="gv">${esc(outs.map(nm).join(", ")||"—")}</div></div>`;
  h+=`<div class="g"><div class="gk">Confirmed variables</div><div class="gv">${conf.length}</div><div class="gs">${caveats} with coverage caveats</div></div>`;
  h+=`<div class="g"><div class="gk">Data layers</div><div class="gv" style="font-size:12.5px">${esc(layers.join(" · ")||"—")}</div><div class="gs">where they live in VitalDB</div></div>`;
  h+=`<div class="g"><div class="gk">Design</div><div class="gv">Retrospective cohort</div><div class="gs">single-center, observational</div></div>`;
  h+=`<div class="g"><div class="gk">Watch for</div><div class="gv">Confounding & missingness</div><div class="gs">adjust + report completeness</div></div>`;
  return h+`</div>`;
}

function downloadReport(R){
  let m=`# Afferent Intelligence — feasibility report\n\n**Question:** ${R.question}\n\n`;
  m+=`**Verdict:** ${R.verdict.v.replace(/_/g," ")} — ${R.verdict.title}\n\n${R.verdict.reason}\n\n`;
  if(R.peco){ m+=`## PECO\n- Population: ${R.peco.population}\n- Exposure: ${R.peco.exposure}\n- Comparator: ${R.peco.comparator}\n- Outcome: ${R.peco.outcome}\n\n`; }
  m+=`## Concepts resolved against the verified inventory\n`;
  for(const c of R.concepts){ m+=`- **${c.entry?c.entry.name:c.label}** — ${c.status.replace(/_/g," ")}`;
    if(c.entry){ m+=` (${c.entry.track||"n/a"}; ${c.entry.confidence} confidence)\n  - missingness: ${c.entry.missingness}\n`; } else m+=`\n`; }
  m+=`\n_Generated by Afferent Intelligence. Source: VitalDB data descriptor (Lee et al., Scientific Data 2022). This report documents feasibility; it does not write the paper._\n`;
  const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([m],{type:"text/markdown"}));
  a.download="feasibility_report.md"; a.click(); URL.revokeObjectURL(a.href);
}

// ---- novelty scan (PubMed) ----
function onNovelty(R){
  openCheckout("Prior-work / novelty scan", R.question, NOVELTY_PRICE,
    ["PubMed related-work search on your exposure & outcome","Calibrated AI read of overlap (when AI mode is on)"],
    ()=>runNovelty(R));
}
async function runNovelty(R){
  const box=document.getElementById("novres");
  if(DEMO){ renderNovelty(box,{articles:NOVELTY_EXAMPLE, demo:true}); return; }
  box.innerHTML=`<div class="helper" style="margin-top:10px"><span class="spinner"></span> Searching PubMed for related work…</div>`;
  try{
    const r=await fetch("/api/novelty",{method:"POST",headers:{"content-type":"application/json"},
      body:JSON.stringify({question:R.question,concepts:R.concepts.map(c=>({label:c.label}))})});
    renderNovelty(box,await r.json());
  }catch(e){ box.innerHTML=`<div class="helper" style="margin-top:10px">Novelty scan needs the backend running (PubMed lookup happens server-side).</div>`; }
}
function renderNovelty(box,d){
  let h=`<div class="seclabel">Prior work / novelty <span class="tagchip ${d.assessment?"tag-ai":"tag-guide"}">${d.assessment?"AI-assessed":(d.demo?"example (real citations)":"PubMed")}</span></div>`;
  if(d.assessment) h+=`<div class="novassess na-${d.assessment.level}"><b>${d.assessment.level.replace(/_/g," ")}.</b> ${esc(d.assessment.summary)}</div>`;
  if(d.articles&&d.articles.length){ h+=`<div class="novlist">`;
    for(const a of d.articles) h+=`<div class="novrow"><div class="nt"><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a></div><div class="nm">${esc(a.journal)} · ${esc(a.year)} · PMID ${esc(a.pmid)}</div></div>`;
    h+=`</div>`;
  } else h+=`<div class="helper">No closely-related PubMed results surfaced — which may itself suggest novelty (or that the phrasing needs refining).</div>`;
  h+=`<div style="margin-top:8px;font-size:11.5px;color:var(--muted)">Related-work scan only — not an exhaustive systematic review. Assessment is judged from the titles above.</div>`;
  box.innerHTML=h;
}

// ---- generic demo checkout ----
function openCheckout(title, sub, price, lines, onPay){
  const m=document.createElement("div"); m.className="modal";
  m.innerHTML=`<div class="box"><h3>${esc(title)}</h3><div style="font-size:13px;color:#334155"><i>${esc(sub)}</i></div>`+
    `<div class="price">$${price}.00</div><ul>${lines.map(l=>`<li>${esc(l)}</li>`).join("")}</ul>`+
    `<div class="demo">Demo checkout — <b>no real charge</b>. In production this is a Stripe Checkout session; the deliverable releases on payment success. It does <b>not</b> write your paper.</div>`+
    `<div class="mbtns"><button class="btn-ghost" id="mc">Cancel</button><button class="btn-pay" id="mp">Pay $${price} &amp; run</button></div></div>`;
  document.body.appendChild(m);
  m.querySelector("#mc").addEventListener("click",()=>m.remove());
  m.addEventListener("click",e=>{if(e.target===m)m.remove();});
  m.querySelector("#mp").addEventListener("click",()=>{ m.remove(); onPay(); });
}

// ---- feasible-study toolkit: checklist + save + scope ----
function renderChecklist(q){
  const st=getChecks()[qkey(q)]||{};
  let h=`<ul class="checklist">`;
  CHECKLIST.forEach((t,i)=>{ const done=!!st[i];
    h+=`<li class="${done?"done":""}"><input type="checkbox" data-ci="${i}" ${done?"checked":""}><span>${esc(t)}</span></li>`; });
  return h+`</ul>`;
}
function renderToolkit(R){
  const saved=getIdeas().some(x=>qkey(x.question)===qkey(R.question));
  let h=`<div class="seclabel">After you settle on this question <span class="tagchip tag-guide">workflow</span></div>`;
  h+=`<div class="toolkit"><div style="font-size:13px;color:var(--muted)">An organized path from a good question to results — Afferent does the scoped grunt-work, not the paper.</div>`;
  h+=renderChecklist(R.question);
  h+=`<div class="tkbtns">`;
  h+=`<button class="btn-pay" id="scopebtn">Scope this study &amp; pricing →</button>`;
  h+=saved?`<span class="savedflag">★ saved to ideas</span>`:`<button class="btn-ghost" id="saveidea">＋ Save to ideas</button>`;
  h+=`</div>`;
  h+=`<div class="scopeform" id="scopeform"></div>`;
  h+=`<div class="scoperes" id="scoperes"></div>`;
  h+=`</div>`;
  return h;
}
function wireToolkit(el,R){
  el.querySelectorAll(".checklist input").forEach(cb=>cb.addEventListener("change",()=>{
    const i=cb.getAttribute("data-ci"), ch=getChecks(), k=qkey(R.question);
    ch[k]=ch[k]||{}; ch[k][i]=cb.checked; setChecks(ch);
    cb.closest("li").classList.toggle("done",cb.checked);
  }));
  const sb=el.querySelector("#saveidea");
  if(sb) sb.addEventListener("click",()=>{ saveIdea(R); sb.outerHTML=`<span class="savedflag">★ saved to ideas</span>`; });
  el.querySelector("#scopebtn").addEventListener("click",()=>toggleScopeForm(R));
}

// ---- scope form ----
function toggleScopeForm(R){
  const f=document.getElementById("scopeform");
  if(f.style.display==="block"){ f.style.display="none"; return; }
  f.innerHTML=buildScopeForm(R); f.style.display="block";
  f.querySelectorAll(".pitem,#it_bundle").forEach(c=>c.addEventListener("change",updateTotal));
  updateTotal();
  f.querySelector("#genscope").addEventListener("click",()=>{
    const ord=gatherItems(); if(!ord.items.length){ alert("Pick at least one deliverable."); return; }
    openCheckout("Scoping pack", R.question, ord.total, ord.lines, ()=>generateScope(R));
  });
  f.scrollIntoView({behavior:"smooth",block:"nearest"});
}
function buildScopeForm(R){
  const confirmed=R.concepts.filter(c=>c.status==="CONFIRMED");
  const cov=confirmed.map(c=>`<label><input type="checkbox" class="cov" value="${esc(c.label)}">${esc(c.label)}</label>`).join("");
  return `<div class="seclabel" style="margin-top:0">Scoping parameters <span class="tagchip tag-guide">you specify</span></div>
  <div class="ff">
    <div class="f"><label>Age min</label><input type="number" id="age_min" placeholder="e.g. 18"></div>
    <div class="f"><label>Age max</label><input type="number" id="age_max" placeholder="e.g. 90"></div>
    <div class="f"><label>ASA classes</label><input type="text" id="asa" placeholder="e.g. 1, 2, 3"></div>
    <div class="f"><label>Surgery type / department contains</label><input type="text" id="surgery_type" placeholder="e.g. Colorectal"></div>
    <div class="f"><label>Anesthesia type</label><select id="anesthesia_type"><option value="any">any</option><option>General</option><option>Spinal</option><option>TIVA</option></select></div>
    <div class="f"><label>Emergency surgery</label><select id="emergency"><option value="any">any</option><option value="yes">emergency only</option><option value="no">elective only</option></select></div>
    <div class="f full"><label>Exposure operationalization</label><textarea id="exposure_def" placeholder="e.g. intraoperative hypotension = cumulative minutes with MAP < 65 mmHg"></textarea></div>
    <div class="f full"><label>Outcome operationalization</label><textarea id="outcome_def" placeholder="e.g. AKI = KDIGO stage ≥1 from pre-op vs peak post-op creatinine within 7 days"></textarea></div>
    <div class="f"><label>Time window</label><input type="text" id="time_window" placeholder="e.g. induction → end of surgery"></div>
    <div class="f"><label>Primary analysis preference</label><input type="text" id="primary_analysis" placeholder="e.g. multivariable logistic regression"></div>
    <div class="f full"><label>Covariates to adjust for</label><div class="covbox">${cov||"<span style='color:var(--muted);font-size:12.5px'>no confirmed covariates detected</span>"}</div></div>
    <div class="f full"><label>Notes</label><textarea id="sample_note" placeholder="anything else to scope"></textarea></div>
  </div>` + buildMenu() + `
  <div class="tkbtns"><button class="btn-pay" id="genscope">Review &amp; pay</button></div>`;
}
function buildMenu(){
  let m=`<div class="seclabel">Deliverables &amp; pricing <span class="tagchip tag-guide">choose</span></div><div class="menu">`;
  for(const [k,v] of Object.entries(PRICING)) m+=`<label class="mrow"><input type="checkbox" class="pitem" value="${k}" ${k==="github"?"":"checked"}><span class="ml">${esc(v.label)}</span><span class="mp">$${v.price}</span></label>`;
  m+=`<label class="mrow mbundle"><input type="checkbox" id="it_bundle"><span class="ml">${esc(BUNDLE.label)} — best value</span><span class="mp">$${BUNDLE.price}</span></label>`;
  m+=`</div><div class="mtotal">Total<span class="mt" id="mt">$0</span></div>`;
  m+=`<div class="notoffered">Not offered: <b>manuscript writing, results interpretation, or causal claims.</b> Afferent scopes the study; you and your statistician run and write it.</div>`;
  return m;
}
function gatherItems(){
  const b=document.getElementById("it_bundle");
  if(b&&b.checked) return {items:["bundle"],total:BUNDLE.price,lines:[BUNDLE.label+" — $"+BUNDLE.price]};
  const sel=[...document.querySelectorAll(".pitem:checked")].map(c=>c.value);
  const total=sel.reduce((s,k)=>s+((PRICING[k]&&PRICING[k].price)||0),0);
  const lines=sel.map(k=>PRICING[k].label+" — $"+PRICING[k].price);
  return {items:sel,total,lines};
}
function updateTotal(){ const t=document.getElementById("mt"); if(t) t.textContent="$"+gatherItems().total; }
function gatherParams(){
  const v=id=>{const e=document.getElementById(id);return e?e.value.trim():"";};
  const asa=v("asa").split(",").map(s=>s.trim()).filter(Boolean).map(s=>/^\d+$/.test(s)?("ASA "+s):s);
  const covs=[...document.querySelectorAll(".cov:checked")].map(c=>c.value);
  return {age_min:v("age_min"),age_max:v("age_max"),asa,surgery_type:v("surgery_type"),
    anesthesia_type:v("anesthesia_type"),emergency:v("emergency"),exposure_def:v("exposure_def"),
    outcome_def:v("outcome_def"),time_window:v("time_window"),primary_analysis:v("primary_analysis"),
    covariates:covs,sample_note:v("sample_note")};
}

function demoScope(R){
  const res=document.getElementById("scoperes");
  if(!EXAMPLE){ res.innerHTML=`<div class="helper">Example pack unavailable in this build.</div>`; return; }
  const ord=gatherItems();
  const items = ord.items[0]==="bundle" ? [{label:BUNDLE.label,price:BUNDLE.price}]
              : ord.items.map(k=>({label:PRICING[k].label,price:PRICING[k].price}));
  const data=Object.assign({},EXAMPLE,{run_id:"example",order:{items,total:ord.total}});
  renderScopeResults(res,data);
}
async function generateScope(R){
  if(DEMO) return demoScope(R);
  const res=document.getElementById("scoperes");
  res.innerHTML=`<div class="verdict v-INSUFFICIENT_INFO"><div class="vtop"><span class="vbadge"><span class="spinner"></span>building</span><h2>Generating your scoping pack…</h2></div></div>`;
  const params=gatherParams(); const {items}=gatherItems();
  const concepts=R.concepts.map(c=>({label:c.label,role:c.role,status:c.status,resolved_id:c.resolved_id}));
  try{
    const r=await fetch("/api/scope",{method:"POST",headers:{"content-type":"application/json"},
      body:JSON.stringify({question:R.question,concepts,params,items})});
    const data=await r.json();
    if(data.error){ res.innerHTML=`<div class="helper">${esc(data.error)}</div>`; return; }
    renderScopeResults(res,data);
  }catch(e){
    res.innerHTML=`<div class="helper">Scoping needs the backend running (it generates files + figures server-side). Start it with <span class="mono">py -m uvicorn app:app</span> and open http://127.0.0.1:8000.</div>`;
  }
}
function renderScopeResults(res,data){
  let h=`<div class="seclabel">Your scoping pack ${data.ai_enriched?'<span class="tagchip tag-ai">AI-planned</span>':'<span class="tagchip tag-guide">templated</span>'}</div>`;
  if(data.order){ h+=`<div class="sapblock"><div class="k">Order</div><div>${data.order.items.map(i=>esc(i.label)+" ($"+i.price+")").join(" · ")} — <b>$${data.order.total}</b> <span style="color:var(--muted)">(demo, not charged)</span></div></div>`; }
  h+=`<div class="sapblock">`;
  h+=`<div class="k">Design</div><div>${esc(data.design)}</div>`;
  h+=`<div class="k">Primary analysis</div><div>${esc(data.primary_analysis)}</div>`;
  if(data.models&&data.models.length){ h+=`<div class="k">Candidate models</div><div>${data.models.map(esc).join("; ")}</div>`; }
  if(data.covariates&&data.covariates.length){ h+=`<div class="k">Covariates</div><div>${data.covariates.map(esc).join(", ")}</div>`; }
  if(data.limitations&&data.limitations.length){ h+=`<div class="k">Key limitations (grounded)</div><div>${data.limitations.map(esc).join(" · ")}</div>`; }
  h+=`</div>`;
  if(data.plots&&data.plots.length){
    h+=`<div class="seclabel">Suggested figures <span class="tagchip tag-guide">illustrative</span></div><div class="plotgrid">`;
    for(const p of data.plots) h+=`<div class="plotcard"><img src="${esc(p.url)}" alt="${esc(p.title)}"><div class="pc"><div class="pt">${esc(p.title)}</div><div class="pr">${esc(p.rationale||"")}</div></div></div>`;
    h+=`</div>`;
  }
  if(data.has_github){
    h+=`<div class="seclabel">Private GitHub repo <span class="tagchip tag-guide">clone-ready</span></div>`;
    if(data.github_repo_url){
      h+=`<div class="reframe"><div class="h">Repo created</div><div>Your private repo: <a href="${esc(data.github_repo_url)}" target="_blank" rel="noopener">${esc(data.github_repo_url)}</a>. Download the pack and follow <span class="mono">GITHUB_SETUP.md</span> to push.</div></div>`;
    } else {
      h+=`<div class="helper">The pack is laid out as a clone-ready repo (<span class="mono">.gitignore</span>, <span class="mono">requirements.txt</span>, <span class="mono">GITHUB_SETUP.md</span>). Download it, then: <span class="mono">gh repo create afferent-study --private --source=. --push</span>.<br><span style="color:var(--muted)">Auto-provisioning a private repo needs a connected GitHub account — set <span class="mono">GITHUB_TOKEN</span> on the server (the production OAuth step) and it's created for you.</span></div>`;
    }
  }
  h+=`<div class="seclabel">Download</div>`;
  h+=`<div class="filelist"><div class="filerow"><span class="fn">scoping_pack.zip</span><span style="color:var(--muted);font-size:12.5px">everything below, zipped</span><a class="btn-pay" href="${esc(data.download_url)}" download>Download pack</a></div>`;
  const base=data.filebase||("/api/scope/file/"+data.run_id+"/");
  for(const f of (data.files||[])){
    if(f.name.endsWith(".png")) continue;
    h+=`<div class="filerow"><span class="fn">${esc(f.name)}</span><a href="${esc(base)}${esc(f.name)}" target="_blank">view</a></div>`;
  }
  h+=`</div><div style="margin-top:10px;font-size:12px;color:var(--muted)">Reminder: this scopes the study — it does not write the paper. Figures are synthetic previews; run the extraction script to produce real ones.</div>`;
  res.innerHTML=h;
  res.scrollIntoView({behavior:"smooth",block:"nearest"});
}

// ---- ideas board ----
function saveIdea(R){
  const ideas=getIdeas();
  if(ideas.some(x=>qkey(x.question)===qkey(R.question))) return;
  ideas.unshift({question:R.question,verdict:R.verdict.v,date:new Date().toISOString().slice(0,10),
    concepts:R.concepts.map(c=>({label:c.label,role:c.role,status:c.status,resolved_id:c.resolved_id}))});
  setIdeas(ideas); renderIdeas();
}
function removeIdea(q){ setIdeas(getIdeas().filter(x=>qkey(x.question)!==qkey(q))); renderIdeas(); }
function renderIdeas(){
  const ideas=getIdeas(), card=document.getElementById("ideascard");
  document.getElementById("ideacount").textContent=ideas.length;
  card.style.display=ideas.length?"block":"none";
  if(!ideas.length) return;
  const VC={FEASIBLE:["#15803d","#ecfdf5"],FEASIBLE_WITH_CAVEATS:["#b45309","#fffbeb"],NOT_FEASIBLE:["#b91c1c","#fef2f2"],INSUFFICIENT_INFO:["#475569","#f1f5f9"]};
  let h="";
  for(const it of ideas){ const c=VC[it.verdict]||VC.INSUFFICIENT_INFO;
    const st=getChecks()[qkey(it.question)]||{}; const done=Object.values(st).filter(Boolean).length;
    h+=`<div class="ideacard"><div class="ih"><span class="miniv" style="color:${c[0]};background:${c[1]}">${it.verdict.replace(/_/g," ")}</span>`;
    h+=`<span class="iq" data-q="${esc(it.question)}">${esc(it.question)}</span>`;
    h+=`<span class="idate">${esc(it.date)} · ${done}/${CHECKLIST.length} steps</span>`;
    h+=`<button class="irm" data-rm="${esc(it.question)}" title="remove">✕</button></div></div>`;
  }
  const body=document.getElementById("ideasbody"); body.innerHTML=h;
  body.querySelectorAll(".iq").forEach(n=>n.addEventListener("click",()=>{const q=n.getAttribute("data-q");qEl.value=q;runQuery(q);}));
  body.querySelectorAll(".irm").forEach(n=>n.addEventListener("click",()=>removeIdea(n.getAttribute("data-rm"))));
}

// ---- query driver: try API, fall back to offline ----
async function runQuery(q){
  const btn=document.getElementById("run");
  const el=document.getElementById("result");
  if(AI_ENABLED){
    btn.disabled=true; el.style.display="block";
    el.innerHTML=`<div class="verdict v-INSUFFICIENT_INFO"><div class="vtop"><span class="vbadge"><span class="spinner"></span>thinking</span><h2>Decomposing your question…</h2></div></div>`;
    try{
      const resp=await fetch("/api/feasibility",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({question:q})});
      const data=await resp.json();
      btn.disabled=false;
      if(data.mode==="ai"){ renderResult(aiResultToUnified(data)); return; }
      // no_ai / error -> graceful offline fallback
    }catch(e){ btn.disabled=false; /* network error -> offline */ }
  }
  renderResult(offlineResult(q));
}

// ---- dataset profile card ----
function renderDatasetProfile(){
  const s=SCOPE||{};
  const rows=[
    ["Center", s.center||"Seoul National University Hospital (single center)"],
    ["Cases", (s.n_cases_approx||6388)+" surgical cases"],
    ["Clinical parameters", (s.clinical_info_parameters||74)+" per case"],
    ["Lab tests", (s.lab_timeseries_tests||34)+" tests, "+(s.lab_window||"±90 days")],
  ];
  let h=`<div class="profile">`;
  for(const [k,v] of rows) h+=`<div class="p"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`;
  h+=`</div>`;
  h+=`<div style="margin-top:12px;font-size:12.5px;color:var(--muted)">What's reachable</div><div class="haves">`;
  for(const x of ["intraoperative waveforms/numerics","in-hospital mortality","ICU & hospital LOS","derivable AKI (postop creatinine)","intraop drugs/fluids/transfusion"]) h+=`<span class="have">${esc(x)}</span>`;
  h+=`</div><div style="margin-top:10px;font-size:12.5px;color:var(--muted)">What's absent</div><div class="haves">`;
  for(const x of ["postoperative delirium","POCD / cognitive testing","30-day / post-discharge mortality","readmission","ward pain / PONV","genetics"]) h+=`<span class="lack">${esc(x)}</span>`;
  h+=`</div><div style="margin-top:12px;font-size:12.5px"><a href="${SOURCE_URL}" target="_blank" rel="noopener">VitalDB data descriptor (Lee et al., Scientific Data 2022) →</a></div>`;
  document.getElementById("profilebody").innerHTML=h;
}

// ---- researcher verification + personalized insights ----
async function orcidClient(orcid){
  const r=await fetch(`https://pub.orcid.org/v3.0/${orcid}/record`,{headers:{Accept:"application/json"}});
  if(!r.ok) throw new Error("orcid"); const d=await r.json();
  const nm=(d.person&&d.person.name)||{};
  const name=[(nm["given-names"]||{}).value,(nm["family-name"]||{}).value].filter(Boolean).join(" ")||null;
  const groups=(((d["activities-summary"]||{}).works||{}).group)||[];
  const works=[],seen=new Set();
  for(const g of groups){ const ws=g["work-summary"]||[]; const t=ws[0]&&ws[0].title&&ws[0].title.title&&ws[0].title.title.value; if(t&&!seen.has(t)){seen.add(t);works.push(t);} }
  return {name,works:works.slice(0,30)};
}
function detInsights(works,interests){
  const text=(works.join(" ")+" "+interests).toLowerCase();
  const scored=DATASETS.map(d=>({d,score:d.tags.reduce((s,t)=>s+(text.includes(t)?1:0),0)})).sort((a,b)=>b.score-a.score);
  const datasets=scored.slice(0,4).map(({d,score})=>({name:d.name,fit:score>=3?"strong":(score>=1?"moderate":"exploratory"),why:d.strengths,access:d.access}));
  const topics=[...new Set(DATASETS.flatMap(d=>d.tags))].filter(t=>text.includes(t)).slice(0,8);
  return {topics,datasets,gaps:GAPS_ABSENT.slice(0,4),collaboration:COLLAB_GENERIC,literature:[],ai:false};
}
async function verifyPersonalize(){
  const orcid=(document.getElementById("orcid").value||"").trim().replace("https://orcid.org/","").replace(/\/$/,"");
  const scholar=(document.getElementById("scholar").value||"").trim();
  const interests=(document.getElementById("interests").value||"").trim();
  const box=document.getElementById("profileres");
  box.innerHTML=`<div class="helper" style="margin-top:12px"><span class="spinner"></span> Verifying &amp; personalizing…</div>`;
  let profile={};
  try{
    if(!DEMO){
      const r=await fetch("/api/verify",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({orcid,scholar_url:scholar})});
      profile=await r.json();
    } else if(ORCID_RE.test(orcid)){
      const o=await orcidClient(orcid); profile={verified:true,orcid,name:o.name,works:o.works,scholar_url:scholar||null};
    } else if(scholar){ profile={verified:false,scholar_url:scholar,note:"Google Scholar linked — add an ORCID iD for verified status."};
    } else { profile={error:"Provide an ORCID iD (0000-0000-0000-0000) or a Google Scholar URL."}; }
  }catch(e){ profile={error:"Verification failed — double-check the ORCID iD."}; }
  if(profile.error){ box.innerHTML=`<div class="helper" style="margin-top:12px">${esc(profile.error)}</div>`; return; }
  const works=profile.works||[];
  let ins;
  if(!DEMO && (works.length||interests)){
    try{ const r=await fetch("/api/profile",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({works,interests})}); ins=await r.json(); if(ins.error) ins=detInsights(works,interests); }
    catch(e){ ins=detInsights(works,interests); }
  } else { ins=detInsights(works,interests); }
  saveProfile(profile,ins,interests);
  renderProfile(box,profile,ins);
}
function renderProfile(box,profile,ins){
  ins=ins||{}; let h="";
  if(profile.verified){ h+=`<div class="vprofile"><span class="vok">✓ Verified</span><div><div class="vn">${esc(profile.name||"Researcher")}</div><div class="vmeta">ORCID ${esc(profile.orcid)} · ${(profile.works||[]).length} works${profile.scholar_url?" · Scholar linked":""}</div></div></div>`; }
  else { h+=`<div class="helper" style="margin-top:12px">${esc(profile.note||"Linked (unverified). Add an ORCID iD for a verified badge.")}</div>`; }
  if(ins.topics&&ins.topics.length){ h+=`<div class="seclabel">Your topics <span class="tagchip ${ins.ai?"tag-ai":"tag-guide"}">${ins.ai?"AI-inferred":"keyword-matched"}</span></div><div class="topicchips">${ins.topics.map(t=>`<span class="topicchip">${esc(t)}</span>`).join("")}</div>`; }
  const litByDs={}; (ins.literature||[]).forEach(l=>litByDs[l.dataset]=l.articles);
  if(ins.datasets&&ins.datasets.length){
    h+=`<div class="seclabel">Recommended datasets <span class="tagchip tag-verified">catalog facts + match</span></div><div class="recgrid">`;
    for(const d of ins.datasets){
      h+=`<div class="reccard"><div class="rh"><span class="rn">${esc(d.name)}</span><span class="fitbadge fit-${d.fit}">${esc(d.fit)} fit</span><span class="racc">${esc(d.access)}</span></div><div class="rw">${esc(d.why)}</div>`;
      const arts=litByDs[d.name];
      if(arts&&arts.length){ h+=`<div class="rlit"><div style="font-size:11.5px;color:var(--muted)">Recent work in your area:</div>`+arts.map(a=>`<div><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a> <span style="color:var(--muted);font-size:11.5px">(${esc(a.journal)}, ${esc(a.year)})</span></div>`).join("")+`</div>`; }
      h+=`</div>`;
    }
    h+=`</div>`;
  }
  if(ins.gaps&&ins.gaps.length){ h+=`<div class="seclabel">Knowledge-base gaps <span class="tagchip ${ins.ai?"tag-ai":"tag-guide"}">${ins.ai?"AI-inferred":"from inventory"}</span></div><ul class="checklist">${ins.gaps.map(g=>`<li><span>${esc(g)}</span></li>`).join("")}</ul>`; }
  if(ins.collaboration&&ins.collaboration.length){ h+=`<div class="seclabel">Collaboration advice <span class="tagchip tag-ai">advice</span></div><ul class="checklist">${ins.collaboration.map(c=>`<li><span>${esc(c)}</span></li>`).join("")}</ul>`; }
  if(DEMO){ h+=`<div style="margin-top:10px;font-size:11.5px;color:var(--muted)">Demo: ORCID verification is live; recommendations use keyword matching. With the backend, the model tailors recommendations and pulls live PubMed literature per dataset.</div>`; }
  box.innerHTML=h;
  const vc=document.getElementById("verchip"); if(profile.verified&&vc){ vc.style.display="inline-block"; vc.textContent="✓ "+(profile.name?profile.name.split(" ").slice(-1)[0]:"verified"); }
}
function saveProfile(profile,ins,interests){ try{ localStorage.setItem("afferent_profile",JSON.stringify({profile,ins,interests})); }catch(e){} }
function restoreProfile(){ try{ const s=JSON.parse(localStorage.getItem("afferent_profile")); if(s&&s.profile){ renderProfile(document.getElementById("profileres"),s.profile,s.ins||{}); if(s.profile.orcid) document.getElementById("orcid").value=s.profile.orcid; if(s.interests) document.getElementById("interests").value=s.interests; } }catch(e){} }

// ---- wire up ----
const qEl=document.getElementById("q");
document.getElementById("run").addEventListener("click",()=>{const v=qEl.value.trim(); if(v) runQuery(v);});
qEl.addEventListener("keydown",e=>{if((e.metaKey||e.ctrlKey)&&e.key==="Enter"){const v=qEl.value.trim(); if(v) runQuery(v);}});
const exWrap=document.getElementById("examples");
for(const ex of EXAMPLES){const c=document.createElement("span");c.className="chip";c.textContent=ex;c.addEventListener("click",()=>{qEl.value=ex;runQuery(ex);});exWrap.appendChild(c);}
document.getElementById("ic").textContent=ENTRIES.length;
renderDatasetProfile();
renderIdeas();
document.getElementById("verifybtn").addEventListener("click",verifyPersonalize);
restoreProfile();

// ---- idea discussion mode ----
const DMSGS=[];
function pushMsg(role,content){ DMSGS.push({role,content});
  const box=document.getElementById("dmsgs");
  box.innerHTML=DMSGS.map(m=>`<div class="dmsg ${m.role==="user"?"user":"bot"}">${esc(m.content)}</div>`).join("");
  box.scrollTop=box.scrollHeight;
}
async function sendDiscuss(){
  const inp=document.getElementById("dinput"); const t=inp.value.trim(); if(!t) return;
  pushMsg("user",t); inp.value="";
  if(DEMO){ pushMsg("assistant","(demo preview) In the live version I help you sharpen this into a feasible VitalDB question — proposing concrete intraoperative exposures and in-hospital outcomes, and steering away from what VitalDB can't measure (delirium, 30-day mortality, readmission). Try the feasibility search above to see the grounded engine in action."); return; }
  if(!AI_ENABLED){ pushMsg("assistant","Discussion mode needs AI mode — set ANTHROPIC_API_KEY on the server and restart, then reload the page."); return; }
  const history=DMSGS.slice();
  const box=document.getElementById("dmsgs");
  const tip=document.createElement("div"); tip.className="dmsg bot"; tip.innerHTML='<span class="spinner"></span>thinking…';
  box.appendChild(tip); box.scrollTop=box.scrollHeight;
  const send=document.getElementById("dsend"); send.disabled=true;
  try{
    const r=await fetch("/api/discuss",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({messages:history})});
    const d=await r.json(); tip.remove();
    pushMsg("assistant", d.reply || d.message || "(no reply)");
  }catch(e){ tip.remove(); pushMsg("assistant","Discussion needs the backend running (the model call happens server-side)."); }
  send.disabled=false;
}
document.getElementById("discussbtn").addEventListener("click",()=>{
  const d=document.getElementById("discuss");
  const show=d.style.display!=="block"; d.style.display=show?"block":"none";
  if(show&&!DMSGS.length){ pushMsg("assistant", AI_ENABLED
    ? "What clinical question or area are you curious about? Tell me the rough idea and I'll help shape it into something VitalDB can actually answer."
    : "Heads up: discussion mode is most useful in AI mode (set ANTHROPIC_API_KEY on the server). You can still browse the examples and run the feasibility check."); }
  if(show) d.scrollIntoView({behavior:"smooth",block:"nearest"});
});
document.getElementById("dsend").addEventListener("click",sendDiscuss);
document.getElementById("dinput").addEventListener("keydown",e=>{ if(e.key==="Enter") sendDiscuss(); });

// ---- detect mode via /api/health ----
(async function detectMode(){
  const badge=document.getElementById("modebadge");
  try{
    const r=await fetch("/api/health"); const h=await r.json();
    if(h.pricing) PRICING=h.pricing; if(h.bundle) BUNDLE=h.bundle; if(h.novelty_price) NOVELTY_PRICE=h.novelty_price;
    if(h.ai_enabled){ AI_ENABLED=true; badge.className="modebadge ai"; badge.innerHTML=`<span class="dot"></span>AI mode · ${esc(h.model)}`; }
    else { badge.className="modebadge"; badge.innerHTML=`<span class="dot"></span>offline · keyword matcher (no API key)`; }
  }catch(e){
    DEMO=true;
    badge.className="modebadge"; badge.innerHTML=`<span class="dot"></span>demo · static preview`;
  }
})();
</script>
</body>
</html>
"""


def main() -> int:
    entries, aliases, scope, example, datasets = collect()
    html = (
        TEMPLATE
        .replace("/*__ENTRIES__*/", json.dumps(entries, ensure_ascii=False))
        .replace("/*__ALIASES__*/", json.dumps(aliases, ensure_ascii=False))
        .replace("/*__SCOPE__*/", json.dumps(scope, ensure_ascii=False))
        .replace("/*__EXAMPLE__*/", json.dumps(example, ensure_ascii=False))
        .replace("/*__DATASETS__*/", json.dumps(datasets, ensure_ascii=False))
    )
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.name} ({len(html):,} bytes) - {len(entries)} concepts, {len(datasets)} datasets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
