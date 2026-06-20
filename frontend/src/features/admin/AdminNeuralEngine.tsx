import { useEffect, useState, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { API_BASE } from "../../lib/api/client";

// --- Types ---
type NodeGroup = "hub" | "domain" | "subdomain" | "card";

interface GraphNode {
  id: string;
  name: string;
  group: NodeGroup;
  val: number;
  domain?: string;
  confidence?: string;
  description?: string;
  x?: number;
  y?: number;
  color?: string;
}

interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  value: number;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

// --- Aesthetics ---
const COLORS: Record<string, string> = {
  hub: "#ffffff",
  vc: "#3b82f6", // Blue
  startup: "#8b5cf6", // Purple
  finance: "#10b981", // Emerald
  regulation: "#f43f5e", // Rose
  macro: "#f59e0b", // Amber
  fintech_infra: "#0ea5e9", // Sky
  general: "#64748b", // Slate
};

export function AdminNeuralEngine() {
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const [activeNode, setActiveNode] = useState<GraphNode | null>(null);
  
  const fgRef = useRef<any>();

  // Fetch Graph Data
  useEffect(() => {
    async function loadGraph() {
      try {
        const res = await fetch(`${API_BASE}/api/brain/graph`);
        if (!res.ok) throw new Error("Failed to load graph data");
        const json = await res.json();
        
        // Pre-assign colors based on domain
        json.nodes.forEach((node: GraphNode) => {
          if (node.group === "hub") {
            node.color = COLORS.hub;
          } else {
            node.color = COLORS[node.domain || "general"] || COLORS.general;
          }
        });

        setData(json);
      } catch (e: any) {
        setError(e.message);
      }
    }
    void loadGraph();
  }, []);

  // Force Directed Tuning
  useEffect(() => {
    if (fgRef.current) {
      // Tune the d3 forces for a dense, circular, growing cluster
      fgRef.current.d3Force("charge").strength((node: any) => {
        if (node.group === "hub") return -1000;
        if (node.group === "domain") return -250;
        if (node.group === "subdomain") return -100;
        return -40;
      });
      fgRef.current.d3Force("link").distance((link: any) => {
        if (link.value === 3) return 90; // hub to domain
        if (link.value === 2) return 40; // domain to subdomain
        return 15; // subdomain to card
      });
      // Give it a subtle centering force to keep the hub anchored
      fgRef.current.d3Force("center").x(0).y(0).strength(0.08);
    }
  }, [data]);

  const handleNodeClick = (node: GraphNode) => {
    setActiveNode(node);
    if (fgRef.current) {
      // Dynamic zoom based on node type
      let targetZoom = 8;
      if (node.group === "hub") targetZoom = 2;
      if (node.group === "domain") targetZoom = 4;
      if (node.group === "subdomain") targetZoom = 6;
      if (node.group === "card") targetZoom = 10;

      fgRef.current.centerAt(node.x, node.y, 1000);
      fgRef.current.zoom(targetZoom, 2000);
    }
  };

  const handleClosePanel = () => {
    if (!activeNode || !data || !fgRef.current) {
      setActiveNode(null);
      return;
    }
    
    // Find parent node link
    const parentLink = data.links.find((l: any) => 
      (typeof l.target === "object" ? l.target.id === activeNode.id : l.target === activeNode.id)
    );
    
    let parentNode: GraphNode | null = null;
    if (parentLink) {
      const sourceId = typeof parentLink.source === "object" ? parentLink.source.id : parentLink.source;
      parentNode = data.nodes.find(n => n.id === sourceId) || null;
    }
    
    if (parentNode) {
      handleNodeClick(parentNode);
    } else {
      setActiveNode(null);
      fgRef.current.zoomToFit(1000, 50);
    }
  };

  const handleBackgroundClick = () => {
    setActiveNode(null);
    if (fgRef.current) {
      fgRef.current.zoomToFit(1000, 50);
    }
  };

  // Node rendering custom drawing
  const paintNode = (node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const isHovered = node.id === hoverNode?.id;
    const isActive = node.id === activeNode?.id;
    const size = node.val;
    const color = node.color || "#fff";
    const time = Date.now() / 1000;

    // Pulse effect
    const pulse = isActive ? Math.abs(Math.sin(time * 3)) * 12 : 0;

    // Draw scanning ring for active node
    if (isActive) {
      ctx.beginPath();
      ctx.arc(node.x!, node.y!, size * 2.8 + (Math.sin(time * 4) * 2), 0, 2 * Math.PI, false);
      ctx.strokeStyle = `rgba(255, 255, 255, ${0.4 + Math.sin(time * 8) * 0.2})`;
      ctx.lineWidth = 1.5 / globalScale;
      ctx.setLineDash([4 / globalScale, 4 / globalScale]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Glow effect - more intense on active/hover
    const isCore = node.group === "hub" || node.group === "domain";
    ctx.beginPath();
    ctx.arc(node.x!, node.y!, size * (isActive ? 1.8 : isHovered ? 1.4 : 1), 0, 2 * Math.PI, false);
    ctx.fillStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = isActive ? 25 + pulse : isHovered ? 15 : isCore ? 8 : 2;
    ctx.fill();
    ctx.shadowBlur = 0; // reset

    // Minimalist Labels: only draw labels if zoomed in close or if hovered/active
    if (globalScale > 3 || isHovered || isActive || node.group === "hub" || node.group === "domain") {
      const fontSize = (node.group === "hub" ? 14 : node.group === "domain" ? 8 : 4) / globalScale;
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = isActive ? "#ffffff" : "rgba(255, 255, 255, 0.8)";
      ctx.fillText(node.name, node.x!, node.y! + size + (fontSize * 1.5));
    }
  };

  const cinematicBg = {
    position: "relative" as const,
    width: "100%",
    height: "100%",
    backgroundColor: "#030305",
    backgroundImage: `
      radial-gradient(circle at 50% 50%, rgba(16, 185, 129, 0.08) 0%, rgba(0, 0, 0, 0.9) 80%),
      linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px)
    `,
    backgroundSize: "100% 100%, 60px 60px, 60px 60px",
    backgroundPosition: "center center",
    overflow: "hidden",
    color: "#fff",
    fontFamily: "Inter, sans-serif"
  };

  return (
    <div style={cinematicBg}>
      
      {/* Top Navbar */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, padding: "1.5rem 2rem", display: "flex", justifyContent: "space-between", alignItems: "center", zIndex: 10, pointerEvents: "none" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "#10b981", boxShadow: "0 0 15px #10b981, 0 0 30px #10b981", animation: "pulse 2s infinite" }} />
          <h1 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 500, letterSpacing: "0.2em", textTransform: "uppercase", textShadow: "0 0 10px rgba(16,185,129,0.5)" }}>Sift Neural Engine</h1>
        </div>
      </div>

      {/* Force Graph Canvas */}
      {data && (
        <ForceGraph2D
          ref={fgRef}
          graphData={data}
          nodeLabel={() => ""} // Disable default tooltip to use custom glassmorphic overlay
          nodeCanvasObject={paintNode}
          nodeRelSize={1}
          linkColor={(link: any) => {
             const s = typeof link.source === "object" ? link.source : data.nodes.find(n => n.id === link.source);
             return s?.color ? `${s.color}25` : "#222222";
          }}
          linkWidth={(link: any) => link.value === 3 ? 1.5 : 0.5}
          linkDirectionalParticles={(link: any) => (link.value === 3 ? 5 : link.value === 2 ? 3 : 1)} // Heavy data flow on cores
          linkDirectionalParticleWidth={(link: any) => link.value === 3 ? 2.5 : 1.5}
          linkDirectionalParticleSpeed={0.008}
          linkDirectionalParticleColor={(link: any) => {
             const s = typeof link.source === "object" ? link.source : data.nodes.find(n => n.id === link.source);
             return s?.color || "#ffffff";
          }}
          onNodeHover={(node: any) => setHoverNode(node || null)}
          onNodeClick={(node: any) => handleNodeClick(node)}
          onBackgroundClick={handleBackgroundClick}
          backgroundColor="rgba(0,0,0,0)" // Transparent so our stunning CSS background shows through
          d3AlphaDecay={0.015} // Extremely fluid, long settling
          d3VelocityDecay={0.25}
        />
      )}

      {/* Loading / Error States */}
      {!data && !error && (
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", color: "#52525b", letterSpacing: "0.1em" }}>
          INITIALIZING TOPOLOGY...
        </div>
      )}
      {error && (
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", color: "#f43f5e" }}>
          {error}
        </div>
      )}

      {/* Glassmorphic Active Node Inspector */}
      {activeNode && (
        <div 
          style={{ 
            position: "absolute", 
            bottom: "2rem", 
            right: "2rem", 
            width: "350px",
            background: "rgba(10, 10, 10, 0.65)", 
            backdropFilter: "blur(24px) saturate(150%)", 
            WebkitBackdropFilter: "blur(24px) saturate(150%)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderTop: "1px solid rgba(255, 255, 255, 0.15)",
            borderRadius: "16px",
            padding: "1.75rem",
            zIndex: 20,
            boxShadow: "0 30px 60px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.1)",
            animation: "fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards"
          }}
        >
          <div style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.1em", color: activeNode.color || "#a1a1aa", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", backgroundColor: activeNode.color || "#fff", boxShadow: `0 0 8px ${activeNode.color}` }}></span>
            {activeNode.group === "card" ? "Expert Card" : activeNode.group}
          </div>
          <h2 style={{ margin: "0 0 0.5rem 0", fontSize: "1.25rem", fontWeight: 400, lineHeight: 1.3 }}>{activeNode.name}</h2>
          
          {activeNode.description && (
            <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "#a1a1aa", lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
              {activeNode.description}
            </p>
          )}
          
          {activeNode.group === "card" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "1rem", borderTop: "1px solid rgba(255, 255, 255, 0.1)", paddingTop: "1rem" }}>
              <div>
                <div style={{ fontSize: "0.65rem", color: "#71717a", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.2rem" }}>Domain</div>
                <div style={{ fontSize: "0.85rem", color: "#e4e4e7", textTransform: "capitalize" }}>{activeNode.domain}</div>
              </div>
              <div>
                <div style={{ fontSize: "0.65rem", color: "#71717a", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.2rem" }}>Confidence</div>
                <div style={{ fontSize: "0.85rem", color: "#e4e4e7", textTransform: "capitalize" }}>{activeNode.confidence}</div>
              </div>
            </div>
          )}

          <div style={{ marginTop: "1.5rem", textAlign: "right" }}>
            <button 
              onClick={handleClosePanel}
              style={{ background: "transparent", border: "none", color: "#a1a1aa", cursor: "pointer", fontSize: "0.8rem", padding: "0.25rem 0" }}
            >
              Close
            </button>
          </div>
        </div>
      )}

      <style>
        {`
          @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}
      </style>
    </div>
  );
}
