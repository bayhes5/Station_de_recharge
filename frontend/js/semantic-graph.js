import cytoscape from "cytoscape";

const TYPE_LABELS = {
    station: "Station",
    borne: "Borne",
    emplacement: "Emplacement",
    device: "ESP32",
    sensor: "Capteur",
    session: "Session",
    alert: "Alerte",
    technician: "Technicien",
};

const TYPE_ORDER = ["station", "borne", "emplacement", "device", "sensor", "session", "alert", "technician"];

document.addEventListener("DOMContentLoaded", async () => {
    const status = document.getElementById("semantic-status");
    const stationFilter = document.getElementById("semantic-station-filter");
    const searchInput = document.getElementById("semantic-search");
    const refreshButton = document.getElementById("semantic-refresh");
    const fitButton = document.getElementById("semantic-fit");
    const zoomInButton = document.getElementById("semantic-zoom-in");
    const zoomOutButton = document.getElementById("semantic-zoom-out");
    const zoomLevel = document.getElementById("semantic-zoom-level");
    const graphHost = document.getElementById("semantic-graph");
    const legendHost = document.getElementById("semantic-legend");
    const detailsHost = document.getElementById("semantic-details-content");

    let graph = { nodes: [], edges: [] };
    let selectedNodeId = "";
    let cy = null;

    const session = await window.AuthAPI.ensureSession();
    if (!session?.user?.is_staff) {
        window.location.href = "/dashboard.html";
        return;
    }

    window.AppNavigation?.render(session, {
        active: "semantic",
        preferredRole: "admin",
    });

    refreshButton.addEventListener("click", loadGraph);
    fitButton.addEventListener("click", fitGraph);
    zoomInButton.addEventListener("click", () => setZoom((cy?.zoom() || 1) * 1.22));
    zoomOutButton.addEventListener("click", () => setZoom((cy?.zoom() || 1) / 1.22));
    stationFilter.addEventListener("change", render);
    searchInput.addEventListener("input", render);

    renderLegend();
    await loadGraph();

    async function loadGraph() {
        setStatus("Chargement du graphe métier...");
        refreshButton.disabled = true;

        try {
            graph = await window.AuthAPI.getSemanticNetwork();
            selectedNodeId = "";
            populateStationFilter(graph.nodes);
            render();
            setStatus("");
        } catch (error) {
            const message = error.status === 404
                ? "La visualisation sémantique n'est pas disponible."
                : error.message || "Impossible de charger le graphe métier.";
            setStatus(message, "error");
            graphHost.replaceChildren(createEmptyState(message));
        } finally {
            refreshButton.disabled = false;
        }
    }

    function render() {
        const filtered = filterGraph(graph);
        renderGraph(filtered.nodes, filtered.edges);
        renderDetails(filtered.nodes.find((node) => node.id === selectedNodeId) || null);
    }

    function filterGraph(sourceGraph) {
        const stationId = stationFilter.value;
        const query = normalize(searchInput.value);

        const matchedNodes = sourceGraph.nodes.filter((node) => {
            const inStation = !stationId
                || node.station_id === stationId
                || node.station_ids?.includes(stationId)
                || (node.type === "station" && node.station_id === stationId);
            const text = normalize([
                node.label,
                TYPE_LABELS[node.type],
                node.subtitle,
                node.status,
                node.firmware_status,
                node.ip_address,
                node.hardware_mac,
            ].filter(Boolean).join(" "));
            return inStation && (!query || text.includes(query));
        });

        const nodeIds = new Set(matchedNodes.map((node) => node.id));
        const connectedEdges = sourceGraph.edges.filter(
            (edge) => nodeIds.has(edge.from) && nodeIds.has(edge.to)
        );

        return { nodes: matchedNodes, edges: connectedEdges };
    }

    function renderGraph(nodes, edges) {
        if (!nodes.length) {
            graphHost.replaceChildren(createEmptyState("Aucun élément ne correspond aux filtres."));
            renderDetails(null);
            return;
        }

        if (!cy) {
            cy = createCytoscape(graphHost);
            cy.on("tap", "node", (event) => {
                selectedNodeId = event.target.id();
                renderDetails(event.target.data("raw"));
            });
            cy.on("tap", (event) => {
                if (event.target === cy) {
                    selectedNodeId = "";
                    renderDetails(null);
                }
            });
            cy.on("zoom pan", updateZoomLabel);
        }

        const elements = [
            ...nodes.map((node) => ({
                data: {
                    ...node,
                    id: node.id,
                    label: node.label,
                    typeLabel: TYPE_LABELS[node.type] || node.type,
                    displayStatus: node.status || node.subtitle || "",
                    raw: node,
                },
            })),
            ...edges.map((edge, index) => ({
                data: {
                    id: `edge:${index}:${edge.from}:${edge.to}`,
                    source: edge.from,
                    target: edge.to,
                    label: edge.label || "",
                },
            })),
        ];

        cy.elements().remove();
        cy.add(elements);
        runLayout(nodes);
        applySelection();
        updateZoomLabel();
    }

    function createCytoscape(container) {
        return cytoscape({
            container,
            boxSelectionEnabled: false,
            minZoom: 0.35,
            maxZoom: 3.5,
            wheelSensitivity: 0.18,
            style: [
                {
                    selector: "node",
                    style: {
                        "shape": "round-rectangle",
                        "width": 178,
                        "height": 74,
                        "background-color": "#f8fafc",
                        "border-width": 2,
                        "border-color": "#98a2b3",
                        "label": "data(label)",
                        "font-family": "Inter, Segoe UI, Arial, sans-serif",
                        "font-size": 12,
                        "font-weight": 800,
                        "color": "#17202e",
                        "text-wrap": "wrap",
                        "text-max-width": 150,
                        "text-valign": "center",
                        "text-halign": "center",
                        "overlay-padding": 8,
                    },
                },
                { selector: "node[type = 'station']", style: typedNode("#087f8c", "#e5f6f7") },
                { selector: "node[type = 'borne']", style: typedNode("#475467", "#eef2f7") },
                { selector: "node[type = 'emplacement']", style: typedNode("#147d52", "#e7f6ee") },
                { selector: "node[type = 'device']", style: typedNode("#6941c6", "#f2edff") },
                { selector: "node[type = 'sensor']", style: typedNode("#b7791f", "#fff7df") },
                { selector: "node[type = 'session']", style: typedNode("#0b6fba", "#e8f3ff") },
                { selector: "node[type = 'alert']", style: typedNode("#c23934", "#fdeceb") },
                { selector: "node[type = 'technician']", style: typedNode("#344054", "#f2f4f7") },
                {
                    selector: "node:selected",
                    style: {
                        "border-width": 4,
                        "shadow-blur": 20,
                        "shadow-opacity": 0.24,
                        "shadow-color": "#17202e",
                    },
                },
                {
                    selector: "edge",
                    style: {
                        "curve-style": "bezier",
                        "width": 2,
                        "line-color": "#98a2b3",
                        "target-arrow-color": "#98a2b3",
                        "target-arrow-shape": "triangle",
                        "label": "data(label)",
                        "font-size": 10,
                        "font-weight": 800,
                        "color": "#344054",
                        "text-background-color": "#ffffff",
                        "text-background-opacity": 0.96,
                        "text-background-padding": 4,
                        "text-background-shape": "round-rectangle",
                        "text-rotation": "autorotate",
                    },
                },
            ],
        });
    }

    function typedNode(borderColor, backgroundColor) {
        return {
            "border-color": borderColor,
            "background-color": backgroundColor,
        };
    }

    function runLayout(nodes) {
        const roots = nodes
            .filter((node) => node.type === "station")
            .map((node) => `#${CSS.escape(node.id)}`)
            .join(", ");
        cy.layout({
            name: "breadthfirst",
            directed: true,
            roots: roots || undefined,
            padding: 46,
            spacingFactor: 1.18,
            avoidOverlap: true,
            nodeDimensionsIncludeLabels: true,
            maximal: true,
            transform: (_node, position) => ({ x: position.y, y: position.x }),
        }).run();
        cy.fit(cy.elements(), 44);
    }

    function applySelection() {
        cy.nodes().unselect();
        if (selectedNodeId) {
            cy.getElementById(selectedNodeId).select();
        }
    }

    function setZoom(nextZoom) {
        if (!cy) return;
        const level = Math.min(Math.max(nextZoom, cy.minZoom()), cy.maxZoom());
        cy.zoom({
            level,
            renderedPosition: {
                x: graphHost.clientWidth / 2,
                y: graphHost.clientHeight / 2,
            },
        });
        updateZoomLabel();
    }

    function fitGraph() {
        if (!cy) return;
        cy.fit(cy.elements(), 44);
        updateZoomLabel();
    }

    function updateZoomLabel() {
        if (!cy) {
            zoomLevel.textContent = "100 %";
            return;
        }
        zoomLevel.textContent = `${Math.round(cy.zoom() * 100)} %`;
        zoomOutButton.disabled = cy.zoom() <= cy.minZoom() + 0.01;
        zoomInButton.disabled = cy.zoom() >= cy.maxZoom() - 0.01;
    }

    function renderDetails(node) {
        detailsHost.replaceChildren();
        if (!node) {
            detailsHost.textContent = "Sélectionnez un élément du graphe.";
            return;
        }

        const title = document.createElement("h2");
        title.textContent = node.label;
        const type = document.createElement("p");
        type.className = "semantic-detail-type";
        type.textContent = TYPE_LABELS[node.type] || node.type;
        const list = document.createElement("dl");
        list.className = "semantic-detail-list";

        detailRow(list, "Statut", node.status);
        detailRow(list, "Détail", node.subtitle);
        detailRow(list, "Firmware", node.firmware_status);
        detailRow(list, "Adresse IP", node.ip_address);
        detailRow(list, "Adresse MAC", node.hardware_mac);
        detailRow(list, "Dernier signal", formatDateTime(node.last_seen));
        detailRow(list, "Dernière mesure", node.latest_value !== null && node.latest_value !== undefined ? String(node.latest_value) : "");
        detailRow(list, "Mesure reçue le", formatDateTime(node.latest_at));

        detailsHost.append(title, type, list);
    }

    function renderLegend() {
        legendHost.replaceChildren();
        TYPE_ORDER.forEach((type) => {
            const item = document.createElement("span");
            item.className = `semantic-legend-item semantic-legend-${type}`;
            item.textContent = TYPE_LABELS[type];
            legendHost.appendChild(item);
        });
    }

    function populateStationFilter(nodes) {
        const currentValue = stationFilter.value;
        const stations = nodes
            .filter((node) => node.type === "station")
            .sort((a, b) => a.label.localeCompare(b.label));

        stationFilter.replaceChildren(new Option("Toutes les stations", ""));
        stations.forEach((station) => {
            stationFilter.appendChild(new Option(station.label, station.station_id));
        });
        stationFilter.value = stations.some((station) => station.station_id === currentValue) ? currentValue : "";
    }

    function detailRow(list, label, value) {
        if (!value) return;
        const dt = document.createElement("dt");
        dt.textContent = label;
        const dd = document.createElement("dd");
        dd.textContent = value;
        list.append(dt, dd);
    }

    function createEmptyState(message) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = message;
        return empty;
    }

    function setStatus(message, variant = "") {
        status.textContent = message;
        status.className = `status${variant ? ` ${variant}` : ""}`;
    }
});

function normalize(value) {
    return String(value ?? "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function formatDateTime(value) {
    if (!value) return "";
    return new Date(value).toLocaleString("fr-FR");
}
