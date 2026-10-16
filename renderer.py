# renderer.py
# Convierte un architecture.json en un HTML interactivo con SVG.
#
# Uso:
#   python renderer.py architecture.json
#   python renderer.py architecture.json mi_diagrama.html

import html
import json
import sys
from pathlib import Path


NODE_WIDTH = 230
NODE_HEIGHT = 120
COLUMN_GAP = 100
ROW_GAP = 80
MARGIN = 80

TYPE_CONFIG = {
    "table": ("DATABASE", "▣", "table"),
    "process": ("PROCESS", "⚙", "process"),
    "file": ("FILE", "▤", "file"),
    "configuration": ("CONFIGURATION", "⚙", "configuration"),
}


def esc(value):
    return html.escape(str(value or ""))


def normalize(data):
    if not isinstance(data, dict):
        raise ValueError("El JSON debe contener un objeto.")

    nodes = []
    ids = set()

    for raw in data.get("nodes", []):
        if not isinstance(raw, dict):
            continue

        node_id = str(raw.get("id", "")).strip()
        if not node_id or node_id in ids:
            continue

        node_type = str(raw.get("type", "process")).lower()
        if node_type not in TYPE_CONFIG:
            node_type = "process"

        node = {
            "id": node_id,
            "type": node_type,
            "label": str(raw.get("label", node_id)),
            "description": str(raw.get("description", "")),
            "source": str(
                raw.get("source", "Sin fuente de información")
            ),
        }

        nodes.append(node)
        ids.add(node_id)

    edges = []

    for raw in data.get("edges", []):
        if not isinstance(raw, dict):
            continue

        source = str(raw.get("source", "")).strip()
        target = str(raw.get("target", "")).strip()

        if source not in ids or target not in ids:
            continue

        edges.append({
            "source": source,
            "target": target,
            "label": str(raw.get("label", "")),
            "description": str(raw.get("description", "")),
            "source_file": str(
                raw.get("source_file", raw.get("source", ""))
            ),
        })

    return {
        "title": str(data.get("title", "Data Architecture")),
        "nodes": nodes,
        "edges": edges,
    }


def calculate_layout(nodes, edges):
    # Layout por niveles:
    # origen -> transformación -> destino.
    incoming = {n["id"]: [] for n in nodes}
    outgoing = {n["id"]: [] for n in nodes}

    for edge in edges:
        outgoing[edge["source"]].append(edge["target"])
        incoming[edge["target"]].append(edge["source"])

    levels = {}

    roots = [
        node_id
        for node_id in incoming
        if not incoming[node_id]
    ]

    if not roots:
        roots = list(incoming)

    queue = list(roots)

    for node_id in roots:
        levels[node_id] = 0

    while queue:
        current = queue.pop(0)

        for child in outgoing[current]:
            new_level = levels[current] + 1

            if child not in levels:
                levels[child] = new_level
                queue.append(child)
            else:
                levels[child] = max(levels[child], new_level)

    for node in nodes:
        levels.setdefault(node["id"], 0)

    grouped = {}

    for node in nodes:
        grouped.setdefault(levels[node["id"]], []).append(node)

    positions = {}

    for level, level_nodes in grouped.items():
        level_nodes.sort(
            key=lambda n: (n["type"], n["label"].lower())
        )

        total_width = (
            len(level_nodes) * NODE_WIDTH
            + max(0, len(level_nodes) - 1) * COLUMN_GAP
        )

        # Centro aproximado de un canvas de 1400 px.
        start_x = max(
            MARGIN,
            (1400 - total_width) / 2,
        )

        y = MARGIN + level * (NODE_HEIGHT + ROW_GAP)

        for index, node in enumerate(level_nodes):
            positions[node["id"]] = {
                "x": start_x + index * (NODE_WIDTH + COLUMN_GAP),
                "y": y,
                "width": NODE_WIDTH,
                "height": NODE_HEIGHT,
            }

    return positions


def build_svg(architecture):
    nodes = architecture["nodes"]
    edges = architecture["edges"]
    positions = calculate_layout(nodes, edges)

    if not positions:
        return '<svg id="diagram" viewBox="0 0 1200 700"></svg>'

    width = max(
        1200,
        int(max(p["x"] + p["width"] for p in positions.values()) + MARGIN)
    )

    height = max(
        700,
        int(max(p["y"] + p["height"] for p in positions.values()) + MARGIN)
    )

    parts = [
        f'''
        <svg id="diagram"
             xmlns="http://www.w3.org/2000/svg"
             viewBox="0 0 {width} {height}">
        <defs>
            <marker id="arrow"
                    markerWidth="10"
                    markerHeight="10"
                    refX="9"
                    refY="3"
                    orient="auto">
                <path d="M0,0 L0,6 L9,3 z" class="arrow-head"/>
            </marker>
            <filter id="shadow">
                <feDropShadow
                    dx="0"
                    dy="7"
                    stdDeviation="7"
                    flood-opacity=".25"/>
            </filter>
        </defs>

        <rect width="{width}" height="{height}"
              class="canvas-background"/>
        '''
    ]

    # Conexiones.
    for edge in edges:
        source = positions[edge["source"]]
        target = positions[edge["target"]]

        x1 = source["x"] + source["width"] / 2
        y1 = source["y"] + source["height"]

        x2 = target["x"] + target["width"] / 2
        y2 = target["y"]

        # Si la conexión va hacia arriba, invertimos los puntos.
        if y2 < y1:
            y1 = source["y"]
            y2 = target["y"] + target["height"]

        middle = (y1 + y2) / 2

        path = (
            f"M {x1} {y1} "
            f"C {x1} {middle}, {x2} {middle}, {x2} {y2}"
        )

        label_x = (x1 + x2) / 2
        label_y = middle - 8

        parts.append(
            f'''
            <g class="edge">
                <path d="{path}"
                      class="edge-line"
                      marker-end="url(#arrow)"/>
                <text x="{label_x}"
                      y="{label_y}"
                      class="edge-label"
                      text-anchor="middle">
                    {esc(edge["label"])}
                </text>
            </g>
            '''
        )

    # Nodos.
    for node in nodes:
        pos = positions[node["id"]]
        type_title, icon, css_type = TYPE_CONFIG[node["type"]]

        label = esc(node["label"])
        description = esc(node["description"])
        source = esc(node["source"])

        parts.append(
            f'''
            <g class="node node-{css_type}"
               data-node-id="{esc(node["id"])}"
               data-type="{esc(node["type"])}"
               data-label="{label}"
               data-description="{description}"
               data-source="{source}"
               transform="translate({pos["x"]},{pos["y"]})"
               tabindex="0">

                <rect width="{NODE_WIDTH}"
                      height="{NODE_HEIGHT}"
                      rx="14"
                      class="node-card"
                      filter="url(#shadow)"/>

                <rect width="{NODE_WIDTH}"
                      height="4"
                      rx="2"
                      class="node-accent"/>

                <text x="20" y="30" class="node-type">
                    {esc(icon)} {esc(type_title)}
                </text>

                <text x="20" y="62" class="node-label">
                    {label}
                </text>

                <text x="20" y="88" class="node-description">
                    {description[:42]}
                </text>

                <text x="20" y="108" class="node-source">
                    {source[:34]}
                </text>
            </g>
            '''
        )

    parts.append("</svg>")
    return "".join(parts)


CSS = '''
:root {
    --bg: #020817;
    --panel: #0b1220;
    --panel2: #111827;
    --border: #26344c;
    --text: #e7eef8;
    --muted: #8b9bb3;
    --cyan: #00d9ff;
    --green: #00d084;
    --purple: #9b7cff;
    --orange: #ff9f1c;
}

* {
    box-sizing: border-box;
}

html, body {
    width: 100%;
    height: 100%;
    margin: 0;
}

body {
    overflow: hidden;
    color: var(--text);
    font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    background:
        radial-gradient(
            circle at 20% 10%,
            #0c1d3b 0,
            transparent 35%
        ),
        radial-gradient(
            circle at 80% 80%,
            #141936 0,
            transparent 30%
        ),
        var(--bg);
}

.app {
    width: 100vw;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.header {
    height: 72px;
    min-height: 72px;
    padding: 0 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(5, 11, 25, .88);
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(15px);
    z-index: 20;
}

.brand {
    display: flex;
    align-items: center;
    gap: 12px;
}

.brand-icon {
    width: 38px;
    height: 38px;
    display: grid;
    place-items: center;
    border: 1px solid var(--cyan);
    border-radius: 10px;
    color: var(--cyan);
    box-shadow: 0 0 25px rgba(0,217,255,.12);
}

.title {
    font-size: 18px;
    font-weight: 750;
}

.subtitle {
    margin-top: 2px;
    color: var(--muted);
    font-size: 12px;
}

.actions {
    display: flex;
    gap: 8px;
}

button {
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--panel);
    color: var(--text);
    cursor: pointer;
}

button:hover {
    background: var(--panel2);
    border-color: #53627b;
}

.workspace {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: hidden;
}

.viewport {
    position: absolute;
    inset: 0;
    overflow: hidden;
    cursor: grab;
}

.viewport.dragging {
    cursor: grabbing;
}

#diagram {
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 0 0;
    user-select: none;
}

.canvas-background {
    fill: #050b16;
}

.edge-line {
    fill: none;
    stroke: #64748b;
    stroke-width: 2;
}

.arrow-head {
    fill: #64748b;
}

.edge-label {
    fill: #aab7c9;
    font-size: 12px;
    font-weight: 650;
}

.node {
    cursor: pointer;
    outline: none;
}

.node-card {
    fill: #0d1626;
    stroke: #2a3851;
    stroke-width: 1.2;
}

.node:hover .node-card,
.node:focus .node-card {
    stroke: var(--cyan);
    stroke-width: 1.8;
}

.node-accent {
    fill: var(--cyan);
}

.node-process .node-accent {
    fill: var(--green);
}

.node-file .node-accent {
    fill: var(--purple);
}

.node-configuration .node-accent {
    fill: var(--orange);
}

.node-type {
    fill: #8da0ba;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
}

.node-label {
    fill: #f1f6ff;
    font-size: 16px;
    font-weight: 700;
}

.node-description {
    fill: #9eacc0;
    font-size: 11px;
}

.node-source {
    fill: #62728b;
    font-size: 9px;
}

.inspector {
    display: none;
    position: absolute;
    top: 20px;
    right: 20px;
    width: 330px;
    max-height: calc(100% - 40px);
    overflow: auto;
    padding: 18px;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: rgba(8,15,29,.95);
    backdrop-filter: blur(18px);
    box-shadow: 0 20px 60px rgba(0,0,0,.35);
    z-index: 10;
}

.inspector.visible {
    display: block;
}

.inspector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.inspector h2 {
    margin: 0;
    font-size: 16px;
}

.field {
    margin-top: 16px;
}

.field-label {
    color: #70819b;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.field-value {
    margin-top: 5px;
    font-size: 13px;
    line-height: 1.45;
    overflow-wrap: anywhere;
}

.legend,
.zoom {
    position: absolute;
    bottom: 18px;
    z-index: 10;
}

.legend {
    left: 18px;
    display: flex;
    gap: 14px;
    padding: 9px 12px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: rgba(7,14,27,.88);
    color: var(--muted);
    font-size: 11px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
}

.dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.dot-table {
    background: var(--cyan);
}

.dot-process {
    background: var(--green);
}

.dot-file {
    background: var(--purple);
}

.dot-configuration {
    background: var(--orange);
}

.zoom {
    right: 18px;
    display: flex;
    gap: 5px;
}

.zoom button {
    width: 36px;
    height: 36px;
    padding: 0;
}

.light {
    --bg: #f4f7fb;
    --panel: #fff;
    --panel2: #eef2f8;
    --border: #d6deea;
    --text: #172033;
    --muted: #65728a;
}

.light .header {
    background: rgba(255,255,255,.9);
}

.light .canvas-background {
    fill: #f7f9fc;
}

.light .node-card {
    fill: #fff;
    stroke: #ccd6e4;
}

.light .node-label {
    fill: #182235;
}
'''


JS = '''
const viewport = document.getElementById("viewport");
const diagram = document.getElementById("diagram");
const inspector = document.getElementById("inspector");

let scale = 1;
let offsetX = 0;
let offsetY = 0;
let dragging = false;
let startX = 0;
let startY = 0;


function renderTransform() {
    diagram.style.transform =
        `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
}


function zoomAt(factor, clientX, clientY) {
    const oldScale = scale;
    const newScale = Math.min(
        2.5,
        Math.max(.25, scale * factor)
    );

    const rect = viewport.getBoundingClientRect();

    const x = clientX - rect.left;
    const y = clientY - rect.top;

    offsetX = x - (x - offsetX) * (newScale / oldScale);
    offsetY = y - (y - offsetY) * (newScale / oldScale);

    scale = newScale;

    renderTransform();
}


viewport.addEventListener("mousedown", (event) => {
    if (event.target.closest(".node")) {
        return;
    }

    dragging = true;
    viewport.classList.add("dragging");

    startX = event.clientX - offsetX;
    startY = event.clientY - offsetY;
});


window.addEventListener("mousemove", (event) => {
    if (!dragging) {
        return;
    }

    offsetX = event.clientX - startX;
    offsetY = event.clientY - startY;

    renderTransform();
});


window.addEventListener("mouseup", () => {
    dragging = false;
    viewport.classList.remove("dragging");
});


viewport.addEventListener("wheel", (event) => {
    event.preventDefault();

    zoomAt(
        event.deltaY < 0 ? 1.1 : .9,
        event.clientX,
        event.clientY
    );
}, { passive: false });


document.querySelectorAll(".node").forEach((node) => {
    node.addEventListener("click", (event) => {
        event.stopPropagation();

        document.getElementById("inspector-title").textContent =
            node.dataset.label;

        document.getElementById("inspector-type").textContent =
            node.dataset.type;

        document.getElementById("inspector-description").textContent =
            node.dataset.description || "Sin descripción";

        document.getElementById("inspector-source").textContent =
            node.dataset.source || "Sin fuente de información";

        inspector.classList.add("visible");
    });
});


document.getElementById("close-inspector").addEventListener(
    "click",
    () => inspector.classList.remove("visible")
);


document.getElementById("zoom-in").addEventListener("click", () => {
    zoomAt(1.15, innerWidth / 2, innerHeight / 2);
});


document.getElementById("zoom-out").addEventListener("click", () => {
    zoomAt(.87, innerWidth / 2, innerHeight / 2);
});


document.getElementById("reset-view").addEventListener("click", () => {
    scale = 1;
    offsetX = 0;
    offsetY = 0;
    renderTransform();
});


document.getElementById("theme").addEventListener("click", () => {
    document.body.classList.toggle("light");

    document.getElementById("theme").textContent =
        document.body.classList.contains("light")
            ? "Dark"
            : "Light";
});


document.getElementById("export-svg").addEventListener("click", () => {
    const svg = document.getElementById("diagram");

    const source = new XMLSerializer()
        .serializeToString(svg);

    const blob = new Blob(
        [source],
        { type: "image/svg+xml;charset=utf-8" }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "architecture.svg";

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
});


renderTransform();
'''


def build_html(architecture):
    svg = build_svg(architecture)
    title = esc(architecture["title"])

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>

<style>
{CSS}
</style>
</head>

<body>

<div class="app">

    <header class="header">

        <div class="brand">
            <div class="brand-icon">◇</div>

            <div>
                <div class="title">{title}</div>
                <div class="subtitle">
                    Data Architecture
                </div>
            </div>
        </div>

        <div class="actions">
            <button id="theme">Light</button>
            <button id="reset-view">Reset</button>
            <button id="export-svg">↓ Export SVG</button>
        </div>

    </header>

    <main class="workspace">

        <div id="viewport" class="viewport">
            {svg}
        </div>

        <aside id="inspector" class="inspector">

            <div class="inspector-header">
                <h2 id="inspector-title">Node</h2>

                <button id="close-inspector">
                    ×
                </button>
            </div>

            <div class="field">
                <div class="field-label">Tipo</div>
                <div id="inspector-type"
                     class="field-value"></div>
            </div>

            <div class="field">
                <div class="field-label">Descripción</div>
                <div id="inspector-description"
                     class="field-value"></div>
            </div>

            <div class="field">
                <div class="field-label">Fuente</div>
                <div id="inspector-source"
                     class="field-value"></div>
            </div>

        </aside>

        <div class="legend">
            <div class="legend-item">
                <span class="dot dot-table"></span>
                Table
            </div>

            <div class="legend-item">
                <span class="dot dot-process"></span>
                Process
            </div>

            <div class="legend-item">
                <span class="dot dot-file"></span>
                File
            </div>

            <div class="legend-item">
                <span class="dot dot-configuration"></span>
                Config
            </div>
        </div>

        <div class="zoom">
            <button id="zoom-out">−</button>
            <button id="zoom-in">+</button>
        </div>

    </main>
</div>

<script>
{JS}
</script>

</body>
</html>
'''


def render_file(input_path, output_path=None):
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {input_file}"
        )

    with input_file.open("r", encoding="utf-8") as file:
        data = json.load(file)

    architecture = normalize(data)

    if output_path:
        output_file = Path(output_path)
    else:
        output_file = input_file.with_name("architecture.html")

    output_file.write_text(
        build_html(architecture),
        encoding="utf-8",
    )

    return output_file


def main():
    if len(sys.argv) < 2:
        print(
            "Uso: python renderer.py architecture.json "
            "[architecture.html]"
        )
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        output = render_file(input_path, output_path)
        print(f"HTML generado: {output}")
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
