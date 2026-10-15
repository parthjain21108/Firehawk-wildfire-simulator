"""SVG visuals for the browser dashboard; no image assets or network calls required."""
from __future__ import annotations
from html import escape
from .scenarios import FOREST, SCRUB, FIREBREAK, BUILDING, WATER, BASE

TERRAIN_COLOR = {
    FOREST: "#244c3b", SCRUB: "#49613d", FIREBREAK: "#66717e",
    BUILDING: "#293c59", WATER: "#1e668a", BASE: "#6556d9",
}


def render_map_svg(snapshot: dict, scenario, title: str = "FireHawk", compact: bool = False) -> str:
    terrain = snapshot["terrain"]
    fire = snapshot["fire_status"]
    intensity = snapshot["intensity"]
    drones = snapshot["drones"]
    w, h = scenario.width, scenario.height
    cell = 22 if w <= 24 else 18
    margin_top = 38
    margin_left = 12
    canvas_w = margin_left * 2 + w * cell
    canvas_h = margin_top + h * cell + 28
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {canvas_w} {canvas_h}" preserveAspectRatio="xMidYMid meet" style="display:block;width:100%;height:100%;background:#0b1421" role="img" aria-label="{escape(title)} wildfire simulation map">']
    parts.append(f'<rect width="{canvas_w}" height="{canvas_h}" fill="#0b1421" rx="12"/>')
    parts.append(f'<text x="{margin_left}" y="23" font-family="Inter,Arial,sans-serif" font-size="13" font-weight="700" fill="#e7eef7">{escape(title)}</text>')
    parts.append(f'<text x="{canvas_w - margin_left}" y="23" text-anchor="end" font-family="Inter,Arial,sans-serif" font-size="10" fill="#94a8be">T+{snapshot["step"]} · {scenario.width}×{scenario.height} grid</text>')
    # Subtle terrain cells and boundaries.
    for y in range(h):
        for x in range(w):
            v = terrain[y][x]
            px, py = margin_left + x * cell, margin_top + y * cell
            color = TERRAIN_COLOR.get(v, "#244c3b")
            parts.append(f'<rect x="{px}" y="{py}" width="{cell-1}" height="{cell-1}" rx="2" fill="{color}" stroke="#0b1421" stroke-width="0.6"/>')
            if v == BUILDING:
                # Small building block with windows.
                pad = max(3, cell * 0.22)
                parts.append(f'<rect x="{px+pad}" y="{py+pad}" width="{cell-1-2*pad}" height="{cell-1-2*pad}" rx="1" fill="#bdd3e8" opacity="0.9"/>')
                win = max(1.5, cell * .07)
                parts.append(f'<circle cx="{px+cell*.38}" cy="{py+cell*.38}" r="{win}" fill="#293c59"/><circle cx="{px+cell*.65}" cy="{py+cell*.38}" r="{win}" fill="#293c59"/>')
            elif v == WATER:
                parts.append(f'<path d="M {px+4} {py+cell*.55} q 4 -4 7 0 t 7 0" fill="none" stroke="#7dd3fc" stroke-width="1.2"/>')
            elif v == FIREBREAK:
                parts.append(f'<path d="M {px+4} {py+cell*.72} L {px+cell-5} {py+cell*.28}" stroke="#93a0ad" stroke-width="1" opacity="0.8"/>')
            fs = fire[y][x]
            if fs == 1:
                it = intensity[y][x]
                core = "#ff4b35" if it > .78 else ("#ff7b36" if it > .55 else "#ffb347")
                parts.append(f'<rect x="{px+1.2}" y="{py+1.2}" width="{cell-3.4}" height="{cell-3.4}" rx="3" fill="{core}" opacity="0.94"/>')
                parts.append(f'<circle cx="{px+cell*.5}" cy="{py+cell*.5}" r="{cell*.15}" fill="#fff0b0"/>')
            elif fs == 2:
                parts.append(f'<rect x="{px+2}" y="{py+2}" width="{cell-5}" height="{cell-5}" rx="3" fill="#252b35" opacity="0.95"/>')
                parts.append(f'<path d="M {px+5} {py+cell-6} L {px+cell-6} {py+5}" stroke="#86919e" stroke-width="1.3"/>')
    # Base halo.
    bx, by = scenario.base
    bcx, bcy = margin_left + (bx + .5) * cell, margin_top + (by + .5) * cell
    parts.append(f'<circle cx="{bcx}" cy="{bcy}" r="{cell*.43}" fill="#a89bff" stroke="#ffffff" stroke-width="1.3"/>')
    parts.append(f'<text x="{bcx}" y="{bcy+cell*.13}" text-anchor="middle" font-size="{cell*.55}" font-family="Arial" font-weight="700" fill="#201b46">H</text>')
    # Targets/routes, then aircraft markers.
    drone_colors = ["#76e4ff", "#e4a2ff", "#a3ffb2", "#ffda76", "#ff9e86", "#c8d6ff", "#f2f79b"]
    for i, d in enumerate(drones):
        target = d.get("target")
        if target and d.get("status") not in ("returning", "recharging"):
            tx, ty = target
            cx, cy = margin_left + (d["x"] + .5) * cell, margin_top + (d["y"] + .5) * cell
            ex, ey = margin_left + (tx + .5) * cell, margin_top + (ty + .5) * cell
            parts.append(f'<path d="M {cx} {cy} L {ex} {ey}" stroke="{drone_colors[i % len(drone_colors)]}" stroke-width="1.5" stroke-dasharray="3 3" opacity="0.75"/>')
            parts.append(f'<circle cx="{ex}" cy="{ey}" r="{cell*.30}" fill="none" stroke="{drone_colors[i % len(drone_colors)]}" stroke-width="1.6"/>')
    for i, d in enumerate(drones):
        cx, cy = margin_left + (d["x"] + .5) * cell, margin_top + (d["y"] + .5) * cell
        c = drone_colors[i % len(drone_colors)]
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{cell*.36}" fill="#0c1825" stroke="{c}" stroke-width="2.2"/>')
        parts.append(f'<path d="M {cx-cell*.20} {cy} L {cx+cell*.20} {cy} M {cx} {cy-cell*.20} L {cx} {cy+cell*.20}" stroke="{c}" stroke-width="2" stroke-linecap="round"/>')
        if not compact:
            parts.append(f'<text x="{cx+cell*.25}" y="{cy-cell*.24}" font-family="Arial" font-size="8" font-weight="700" fill="#ffffff">{d["id"]}</text>')
    # Bottom summary.
    m = snapshot.get("metrics", {})
    burnt = m.get("burned_area_cells", 0)
    active = m.get("active_fire_cells", 0)
    damaged = m.get("buildings_damaged", 0)
    footer_y = canvas_h - 9
    parts.append(f'<text x="{margin_left}" y="{footer_y}" font-family="Inter,Arial,sans-serif" font-size="10" fill="#b6c8da">Burned cells: {burnt}   ·   Active fire: {active}   ·   Buildings damaged: {damaged}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def render_explanation_card(title: str, body: str, accent: str = "#69d3ff") -> str:
    return f'''<div style="background:#111d2b;border:1px solid #25384b;border-left:4px solid {accent};border-radius:12px;padding:14px 16px;color:#eaf2fa;font-family:Inter,Arial,sans-serif;margin-bottom:8px">
    <div style="font-size:13px;font-weight:700;margin-bottom:5px">{escape(title)}</div>
    <div style="font-size:12px;line-height:1.55;color:#b9c9d8">{escape(body)}</div></div>'''


def render_animated_mission_html(comparison: dict, default_speed: float = 1.0) -> str:
    """Build a self-contained browser animation for both strategies.

    One simulation tick is presented as one simulated second at 1x speed. Drone
    positions are interpolated cell-by-cell between snapshots while the next
    fire/suppression state appears at each tick boundary. All frames are produced
    by the Python simulator; JavaScript only renders and replays those results.
    """
    import json

    scenario = comparison["scenario"]

    def frame_payload(run):
        frames = []
        for snap in run["history"]:
            frames.append({
                "step": int(snap["step"]),
                "fire": [int(v) for row in snap["fire_status"] for v in row],
                "intensity": [round(float(v), 3) for row in snap["intensity"] for v in row],
                "drones": [{
                    "id": int(d["id"]), "x": float(d["x"]), "y": float(d["y"]),
                    "target": list(d["target"]) if d.get("target") is not None else None,
                    "status": str(d.get("status", "idle")),
                    "water": float(d.get("water", 0)),
                    "water_capacity": float(d.get("water_capacity", 0)),
                    "battery": float(d.get("battery", 0)),
                    "distance_travelled": int(d.get("distance_travelled", 0)),
                    "drops_used": int(d.get("drops_used", 0)),
                } for d in snap["drones"]],
                "metrics": {
                    k: snap["metrics"].get(k, 0) for k in (
                        "burned_area_cells", "active_fire_cells", "buildings_damaged",
                        "buildings_saved", "building_exposure_units", "water_drops_used",
                        "drone_distance_cells", "suppression_actions", "remaining_water",
                        "remaining_battery_pct", "contained_by_end", "peak_active_fire_cells"
                    )
                },
            })
        return frames

    payload = {
        "scenario": {
            "preset": scenario.preset, "seed": int(scenario.seed),
            "width": int(scenario.width), "height": int(scenario.height),
            "steps": int(scenario.steps), "drone_count": int(scenario.drone_count),
            "wind_speed": float(scenario.wind_speed), "dryness": float(scenario.dryness),
            "wind_dir": scenario.wind_dir,
            "terrain": [int(v) for row in scenario.terrain for v in row],
            "base": list(scenario.base),
            "buildings": [list(b) for b in scenario.buildings],
        },
        "baseline": frame_payload(comparison["baseline"]),
        "optimized": frame_payload(comparison["optimized"]),
        "defaultSpeed": float(default_speed),
    }
    data_json = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")

    template = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;padding:0;background:#08111b;color:#eaf2fb;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif}
.viewer{border:1px solid #263d52;border-radius:16px;overflow:hidden;background:#0b1724}
.vhead{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:14px 16px;border-bottom:1px solid #25384b;background:linear-gradient(110deg,#142b40,#0d1b2a)}
.vtitle{font-size:16px;font-weight:850;letter-spacing:.1px}.vsub{font-size:11px;color:#9cb2c7;margin-top:4px}.simtime{font-size:12px;font-weight:800;color:#9be7ff;border:1px solid #315a70;background:#0b2432;border-radius:9px;padding:7px 10px;white-space:nowrap}
.controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px 14px;background:#0b1724;border-bottom:1px solid #21364a}
button,select{background:#14283a;color:#eaf2fb;border:1px solid #304961;border-radius:9px;padding:9px 11px;font-weight:750;font-size:12px;cursor:pointer}button.primary{background:#73dfff;color:#07131d;border-color:#73dfff}button:hover{filter:brightness(1.12)}button:disabled{opacity:.4;cursor:not-allowed}
input[type=range]{accent-color:#72ddff;flex:1;min-width:140px;cursor:pointer}.control-label{font-size:10px;text-transform:uppercase;letter-spacing:.7px;color:#91a9bf;font-weight:800}.timeline-wrap{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid #21364a}.timeline-wrap input{width:100%}.tick-label{color:#a9bfd3;font-size:11px;white-space:nowrap;min-width:66px;text-align:right}
.panels{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px}.panel{min-width:0;border:1px solid #263e53;background:#0d1b29;border-radius:13px;overflow:hidden}.panelhead{padding:11px 12px 8px;display:flex;gap:8px;align-items:start;justify-content:space-between}.pname{font-size:13px;font-weight:850}.pdesc{font-size:10px;color:#8fa7bd;margin-top:3px;line-height:1.35}.dot{width:8px;height:8px;border-radius:99px;display:inline-block;margin-right:5px}.badge{font-size:9px;letter-spacing:.6px;text-transform:uppercase;border-radius:999px;padding:5px 7px;border:1px solid #2b465c;color:#a9c7de;white-space:nowrap}.mapwrap{padding:0 7px 4px}.mapwrap svg{display:block;width:100%;height:auto;border-radius:8px}.metricgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;padding:8px 9px 10px}.mini{border:1px solid #233a4f;background:#101f2d;border-radius:8px;padding:7px 8px;min-width:0}.mlabel{font-size:9px;text-transform:uppercase;letter-spacing:.45px;color:#91a9bf;line-height:1.2}.mvalue{font-size:17px;font-weight:850;color:#f0f7ff;margin-top:4px}.drone-status{display:flex;gap:5px;flex-wrap:wrap;padding:0 9px 10px}.dchip{font-size:9px;color:#bed0e0;border:1px solid #2a4053;background:#0a1622;border-radius:7px;padding:5px 6px}.event{margin:0 12px 12px;padding:10px 12px;border:1px solid #2a4b61;border-radius:10px;background:#0c2432;font-size:11px;color:#c3e7f4;line-height:1.45}.legend{display:flex;gap:11px;flex-wrap:wrap;padding:0 14px 12px;font-size:10px;color:#9db3c8}.legend span{white-space:nowrap}.key{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px;vertical-align:middle}.foot{border-top:1px solid #21364a;padding:10px 14px;color:#7892a9;font-size:10px;line-height:1.45}
@media(max-width:700px){.panels{grid-template-columns:1fr}.vhead{align-items:flex-start}.metricgrid{grid-template-columns:repeat(3,1fr)}.pdesc{max-width:250px}}
</style></head><body>
<div class="viewer">
  <div class="vhead"><div><div class="vtitle">🔥 FireHawk · Live wildfire response</div><div class="vsub" id="envline">Loading the paired mission…</div></div><div class="simtime" id="simtime">T+0 s / 0 s</div></div>
  <div class="controls">
    <button class="primary" id="play">▶ Start live mission</button><button id="back" title="Go back one simulated second">← 1 s</button><button id="next" title="Advance one simulated second">1 s →</button><button id="reset">↺ Reset</button>
    <span class="control-label">Playback</span><select id="speed"><option value="0.5">Slow · 2 s/tick</option><option value="1" selected>Real time · 1 s/tick</option><option value="2">Fast · 0.5 s/tick</option><option value="4">Very fast · 0.25 s/tick</option></select>
  </div>
  <div class="timeline-wrap"><span class="control-label">Mission timeline</span><input id="timeline" type="range" min="0" value="0" step="1"><span class="tick-label" id="ticklabel">0 / 0 s</span></div>
  <div class="panels">
    <div class="panel"><div class="panelhead"><div><div class="pname"><span class="dot" style="background:#ffad62"></span>Nearest-hotspot baseline</div><div class="pdesc">Dispatches drones to the closest active burning cell. It optimizes distance locally, not wildfire risk.</div></div><span class="badge">Simple strategy</span></div><div class="mapwrap" id="map-baseline"></div><div class="metricgrid" id="metrics-baseline"></div><div class="drone-status" id="drones-baseline"></div></div>
    <div class="panel"><div class="panelhead"><div><div class="pname"><span class="dot" style="background:#85f2ac"></span>FireHawk · Fuzzy + GA</div><div class="pdesc">Scores hotspot urgency, then searches for coordinated drone-to-hotspot assignments.</div></div><span class="badge">Soft computing</span></div><div class="mapwrap" id="map-optimized"></div><div class="metricgrid" id="metrics-optimized"></div><div class="drone-status" id="drones-optimized"></div></div>
  </div>
  <div class="event" id="event" aria-live="polite">Press <b>Start live mission</b> to watch drone movement, new ignitions and suppression updates one simulated second at a time. You can pause, step or scrub.</div>
  <div class="legend"><span><i class="key" style="background:#ff633f"></i>Active fire</span><span><i class="key" style="background:#343b45"></i>Burned cell</span><span><i class="key" style="background:#244c3b"></i>Forest</span><span><i class="key" style="background:#66717e"></i>Firebreak</span><span><i class="key" style="background:#bdd3e8"></i>Building</span><span><i class="key" style="background:#1e668a"></i>Water</span><span><i class="key" style="background:#a89bff"></i>Drone base</span><span><i class="key" style="background:#76e4ff"></i>Drone</span></div>
  <div class="foot">Educational simulation only. At 1×, one saved simulator tick is shown as one simulated second; drone positions are animated between computed snapshots. The app computes both complete missions first, then this player visualizes each step.</div>
</div>
<script>
const D = __DATA__;
const S = D.scenario;
const RUNS = {baseline:D.baseline, optimized:D.optimized};
const CELL = 22, ML = 10, MT = 34, SVGW = ML*2 + S.width*CELL, SVGH = MT + S.height*CELL + 42;
const colors = {0:'#244c3b',1:'#49613d',2:'#66717e',3:'#293c59',4:'#1e668a',5:'#6556d9'};
const droneColors = ['#76e4ff','#e4a2ff','#a3ffb2','#ffda76','#ff9e86','#c8d6ff','#f2f79b'];
const ns = 'http://www.w3.org/2000/svg';
const total = Math.max(0, RUNS.baseline.length-1);
document.getElementById('timeline').max = String(total);
document.getElementById('envline').textContent = `${S.preset} · seed ${S.seed} · ${S.drone_count} drones · wind ${S.wind_speed.toFixed(2)} · dryness ${S.dryness.toFixed(2)} · ${S.wind_dir} wind`;
function el(tag, attrs={}, text=''){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,String(v));if(text!=='') n.textContent=text;return n;}
function center(x,y){return [ML+(x+.5)*CELL, MT+(y+.5)*CELL];}
function createMap(prefix,title){
 const host=document.getElementById('map-'+prefix);let svg=el('svg',{viewBox:`0 0 ${SVGW} ${SVGH}`,role:'img','aria-label':title+' animated wildfire map'});
 svg.appendChild(el('rect',{x:0,y:0,width:SVGW,height:SVGH,rx:8,fill:'#0a1420'}));
 svg.appendChild(el('text',{x:ML,y:18,fill:'#e7eef7','font-size':12,'font-weight':800},title));
 svg.appendChild(el('text',{x:SVGW-ML,y:18,'text-anchor':'end',fill:'#94a8be','font-size':9},`${S.width} × ${S.height} grid`));
 for(let y=0;y<S.height;y++)for(let x=0;x<S.width;x++){
   const i=y*S.width+x,v=S.terrain[i],px=ML+x*CELL,py=MT+y*CELL;
   svg.appendChild(el('rect',{x:px,y:py,width:CELL-1,height:CELL-1,rx:2,fill:colors[v]||colors[0],stroke:'#0b1421','stroke-width':.6}));
   if(v===3){const p=4;svg.appendChild(el('rect',{x:px+p,y:py+p,width:CELL-1-p*2,height:CELL-1-p*2,rx:1,fill:'#bdd3e8',opacity:.9}));svg.appendChild(el('circle',{cx:px+8,cy:py+8,r:1.4,fill:'#293c59'}));svg.appendChild(el('circle',{cx:px+15,cy:py+8,r:1.4,fill:'#293c59'}));}
   if(v===4)svg.appendChild(el('path',{d:`M${px+4} ${py+12} q4 -4 7 0 t7 0`,fill:'none',stroke:'#7dd3fc','stroke-width':1.2}));
   if(v===2)svg.appendChild(el('path',{d:`M${px+4} ${py+16} L${px+17} ${py+5}`,stroke:'#93a0ad','stroke-width':1,opacity:.8}));
   svg.appendChild(el('rect',{id:`fire-${prefix}-${i}`,x:px+1,y:py+1,width:CELL-3,height:CELL-3,rx:3,fill:'none',opacity:0}));
   svg.appendChild(el('circle',{id:`flame-${prefix}-${i}`,cx:px+CELL/2,cy:py+CELL/2,r:3.4,fill:'#fff0b0',opacity:0}));
   svg.appendChild(el('path',{id:`ash-${prefix}-${i}`,d:`M${px+5} ${py+CELL-5} L${px+CELL-5} ${py+5}`,stroke:'#86919e','stroke-width':1.3,opacity:0}));
 }
 const [bx,by]=S.base,[bcx,bcy]=center(bx,by);
 svg.appendChild(el('circle',{cx:bcx,cy:bcy,r:CELL*.43,fill:'#a89bff',stroke:'#fff','stroke-width':1.3}));
 svg.appendChild(el('text',{x:bcx,y:bcy+4,'text-anchor':'middle','font-size':12,'font-weight':900,fill:'#201b46'},'H'));
 const g=el('g',{id:`dynamic-${prefix}`});svg.appendChild(g);
 for(let id=1;id<=S.drone_count;id++){
   const route=el('path',{id:`route-${prefix}-${id}`,fill:'none',stroke:droneColors[(id-1)%droneColors.length],'stroke-width':1.6,'stroke-dasharray':'4 3',opacity:.8});svg.appendChild(route);
   const ring=el('circle',{id:`target-${prefix}-${id}`,r:CELL*.31,fill:'none',stroke:droneColors[(id-1)%droneColors.length],'stroke-width':1.5,opacity:0});svg.appendChild(ring);
   const group=el('g',{id:`drone-${prefix}-${id}`,transform:'translate(0,0)'});
   group.appendChild(el('circle',{cx:0,cy:0,r:CELL*.36,fill:'#0c1825',stroke:droneColors[(id-1)%droneColors.length],'stroke-width':2.2}));
   group.appendChild(el('path',{d:`M-${CELL*.2} 0 L${CELL*.2} 0 M0 -${CELL*.2} L0 ${CELL*.2}`,stroke:droneColors[(id-1)%droneColors.length],'stroke-width':2,'stroke-linecap':'round'}));
   group.appendChild(el('circle',{cx:0,cy:0,r:2.3,fill:'#fff'}));
   group.appendChild(el('text',{x:CELL*.26,y:-CELL*.24,'font-size':8,'font-weight':900,fill:'#fff',stroke:'#0b1421','stroke-width':1,'paint-order':'stroke'},`D${id}`));
   g.appendChild(group);
 }
 svg.appendChild(el('text',{x:ML,y:SVGH-12,fill:'#b6c8da','font-size':9,id:`footer-${prefix}`},'Loading metrics…'));
 host.replaceChildren(svg);
}
function setFire(prefix,frame){
 for(let i=0;i<frame.fire.length;i++){
   const f=frame.fire[i], fire=document.getElementById(`fire-${prefix}-${i}`), flame=document.getElementById(`flame-${prefix}-${i}`),ash=document.getElementById(`ash-${prefix}-${i}`);
   if(f===1){const it=frame.intensity[i];fire.setAttribute('fill',it>.78?'#ff4b35':it>.55?'#ff7b36':'#ffb347');fire.setAttribute('opacity','.97');flame.setAttribute('opacity','.95');ash.setAttribute('opacity','0');}
   else if(f===2){fire.setAttribute('fill','#252b35');fire.setAttribute('opacity','.98');flame.setAttribute('opacity','0');ash.setAttribute('opacity','.9');}
   else{fire.setAttribute('fill','none');fire.setAttribute('opacity','0');flame.setAttribute('opacity','0');ash.setAttribute('opacity','0');}
 }
}
function setDronePositions(prefix, fireFrame, drones, routeDrones=null){
 for(const d of drones){
   const [cx,cy]=center(d.x,d.y);document.getElementById(`drone-${prefix}-${d.id}`).setAttribute('transform',`translate(${cx},${cy})`);
   const rd=(routeDrones||drones).find(x=>x.id===d.id)||d;const route=document.getElementById(`route-${prefix}-${d.id}`), ring=document.getElementById(`target-${prefix}-${d.id}`);
   if(rd.target){const [tx,ty]=center(rd.target[0],rd.target[1]);route.setAttribute('d',`M${cx} ${cy} L${tx} ${ty}`);route.setAttribute('opacity','.8');ring.setAttribute('cx',tx);ring.setAttribute('cy',ty);ring.setAttribute('opacity','.95');}
   else{route.setAttribute('d','');route.setAttribute('opacity','0');ring.setAttribute('opacity','0');}
   const c=droneColors[(d.id-1)%droneColors.length];document.getElementById(`drone-${prefix}-${d.id}`).querySelector('circle').setAttribute('stroke',d.status==='suppressing'?'#ff986e':d.status==='returning'?'#c4b5fd':c);
 }
}
function setDetails(prefix,frame){
 const m=frame.metrics;
 const items=[['Active fire',m.active_fire_cells],['Burned area',m.burned_area_cells],['Buildings hit',m.buildings_damaged]];
 document.getElementById('metrics-'+prefix).innerHTML=items.map(([k,v])=>`<div class="mini"><div class="mlabel">${k}</div><div class="mvalue">${v}</div></div>`).join('');
 document.getElementById('drones-'+prefix).innerHTML=frame.drones.map(d=>`<span class="dchip"><b>D${d.id}</b> · ${d.status} · 💧 ${d.water.toFixed(1)} · 🔋 ${Math.round(d.battery)}%</span>`).join('');
 document.getElementById(`footer-${prefix}`).textContent=`T+${frame.step}s · burned ${m.burned_area_cells} · active ${m.active_fire_cells} · damaged ${m.buildings_damaged}`;
}
function renderMode(prefix,idx,positions=null,routeDrones=null){const frame=RUNS[prefix][idx];setFire(prefix,frame);setDronePositions(prefix,frame,positions||frame.drones,routeDrones||frame.drones);setDetails(prefix,frame);}
function renderAll(idx){renderMode('baseline',idx);renderMode('optimized',idx);document.getElementById('timeline').value=String(idx);document.getElementById('ticklabel').textContent=`${idx} / ${total} s`;document.getElementById('simtime').textContent=`T+${idx} s / ${total} s`;}
function interpolate(a,b,p){const dx=b.x-a.x,dy=b.y-a.y,h=Math.abs(dx),v=Math.abs(dy),steps=h+v;if(!steps)return{x:b.x,y:b.y,id:b.id,status:b.status,water:b.water,battery:b.battery,target:b.target};let dist=p*steps,x=a.x,y=a.y;if(dist<=h){x=a.x+Math.sign(dx)*dist;}else{x=b.x;y=a.y+Math.sign(dy)*(dist-h);}return{x,y,id:b.id,status:b.status,water:b.water,battery:b.battery,target:b.target};}
let idx=0,running=false,animating=false;
function eventText(prev,next){let ignitions=0;for(let i=0;i<prev.fire.length;i++)if(prev.fire[i]===0&&next.fire[i]===1)ignitions++;const supp=Math.max(0,(next.metrics.suppression_actions||0)-(prev.metrics.suppression_actions||0));const delta=next.metrics.active_fire_cells-prev.metrics.active_fire_cells;const deltaText=delta>0?`${delta} more active fire cells`:delta<0?`${-delta} fewer active fire cells`:'active fire count unchanged';let msg=`<b>T+${next.step}s:</b> ${ignitions} new ignition(s) · ${supp} cell(s) suppressed · ${deltaText}. `;if(next.metrics.active_fire_cells===0)msg+='No active fire cells remain in this snapshot.';else msg+=`FireHawk and baseline are updated using their own dispatch decisions.`;return msg;}
function updateEvent(prev,next){document.getElementById('event').innerHTML=eventText(prev,next);}
function setPaused(){running=false;document.getElementById('play').textContent='▶ Resume mission';}
function animateNext(){if(idx>=total){renderAll(total);setPaused();return Promise.resolve(false);}if(animating)return Promise.resolve(false);animating=true;const oldIdx=idx,newIdx=idx+1,prevB=RUNS.baseline[oldIdx],nextB=RUNS.baseline[newIdx],prevO=RUNS.optimized[oldIdx],nextO=RUNS.optimized[newIdx];const delay=1000/Number(document.getElementById('speed').value);const begin=performance.now();return new Promise(resolve=>{function draw(now){const p=Math.min(1,(now-begin)/delay);const ib=prevB.drones.map(a=>{const b=nextB.drones.find(x=>x.id===a.id)||a;return interpolate(a,b,p);});const io=prevO.drones.map(a=>{const b=nextO.drones.find(x=>x.id===a.id)||a;return interpolate(a,b,p);});setDronePositions('baseline',prevB,ib,nextB.drones);setDronePositions('optimized',prevO,io,nextO.drones);if(p<1){requestAnimationFrame(draw);}else{idx=newIdx;renderAll(idx);updateEvent(prevO,nextO);animating=false;resolve(true);}}requestAnimationFrame(draw);});}
async function playLoop(){while(running&&idx<total){await animateNext();}running=false;animating=false;document.getElementById('play').textContent=idx>=total?'✓ Mission complete · replay':'▶ Resume mission';}
document.getElementById('play').addEventListener('click',()=>{if(running){setPaused();return;}if(idx>=total){idx=0;renderAll(idx);}running=true;document.getElementById('play').textContent='⏸ Pause mission';playLoop();});
document.getElementById('next').addEventListener('click',async()=>{setPaused();await animateNext();});
document.getElementById('back').addEventListener('click',()=>{setPaused();if(idx>0){const old=idx;idx--;renderAll(idx);updateEvent(RUNS.optimized[idx],RUNS.optimized[old]);}});
document.getElementById('reset').addEventListener('click',()=>{setPaused();idx=0;renderAll(idx);document.getElementById('event').innerHTML='Mission reset. Press <b>Start live mission</b> to watch it unfold.';});
document.getElementById('timeline').addEventListener('input',ev=>{setPaused();idx=Number(ev.target.value);renderAll(idx);const prev=RUNS.optimized[Math.max(0,idx-1)],cur=RUNS.optimized[idx];updateEvent(prev,cur);});
createMap('baseline','NEAREST HOTSPOT');createMap('optimized','FUZZY RISK + GENETIC ASSIGNMENT');renderAll(0);document.getElementById('play').textContent='▶ Start live mission';
</script></body></html>'''
    return template.replace("__DATA__", data_json)
