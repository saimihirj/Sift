import { useEffect, useState, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Link } from "react-router-dom";
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

export function DashboardScreen() {
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
      // Tune the d3 forces to spread things out beautifully without overlapping
      fgRef.current.d3Force("charge").strength(-120);
      fgRef.current.d3Force("link").distance(40);
      fgRef.current.d3Force("collide", null); // we can add a collision force if needed later
    }
  }, [data]);

  const handleNodeClick = (node: GraphNode) => {
    setActiveNode(node);
    if (fgRef.current) {
      fgRef.current.centerAt(node.x, node.y, 1000);
      fgRef.current.zoom(8, 2000);
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

    // Glow effect
    ctx.beginPath();
    ctx.arc(node.x!, node.y!, size * (isActive ? 1.5 : 1), 0, 2 * Math.PI, false);
    ctx.fillStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = isHovered || isActive ? 15 : 5;
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

  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh", backgroundColor: "#0a0a0a", overflow: "hidden", color: "#fff", fontFamily: "Inter, sans-serif" }}>
      
      {/* Top Navbar */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, padding: "1.5rem 2rem", display: "flex", justifyContent: "space-between", alignItems: "center", zIndex: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "#10b981", boxShadow: "0 0 10px #10b981" }} />
          <h1 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 500, letterSpacing: "0.1em", textTransform: "uppercase" }}>Neural Engine Cluster</h1>
        </div>
        <Link to="/" style={{ color: "#a1a1aa", textDecoration: "none", fontSize: "0.9rem", border: "1px solid #3f3f46", padding: "0.5rem 1rem", borderRadius: "4px", transition: "all 0.2s" }}>
          Exit View
        </Link>
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
             // Subtle link coloring based on source
             const s = typeof link.source === "object" ? link.source : data.nodes.find(n => n.id === link.source);
             return s?.color ? `${s.color}40` : "#333333";
          }}
          linkWidth={1}
          linkDirectionalParticles={(link: any) => (link.value === 3 ? 4 : link.value === 2 ? 2 : 1)} // More particles for core branches
          linkDirectionalParticleWidth={1.5}
          linkDirectionalParticleSpeed={0.005}
          linkDirectionalParticleColor={(link: any) => {
             const s = typeof link.source === "object" ? link.source : data.nodes.find(n => n.id === link.source);
             return s?.color || "#ffffff";
          }}
          onNodeHover={(node: any) => setHoverNode(node || null)}
          onNodeClick={(node: any) => handleNodeClick(node)}
          onBackgroundClick={handleBackgroundClick}
          backgroundColor="#0a0a0a"
          d3AlphaDecay={0.05} // Keep it floating longer
          d3VelocityDecay={0.2}
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
            background: "rgba(24, 24, 27, 0.7)", 
            backdropFilter: "blur(12px)", 
            WebkitBackdropFilter: "blur(12px)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "12px",
            padding: "1.5rem",
            zIndex: 20,
            boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
            animation: "fadeIn 0.3s ease-out forwards"
          }}
        >
          <div style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.1em", color: activeNode.color || "#a1a1aa", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", backgroundColor: activeNode.color || "#fff", boxShadow: `0 0 8px ${activeNode.color}` }}></span>
            {activeNode.group === "card" ? "Expert Card" : activeNode.group}
          </div>
          <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.25rem", fontWeight: 400, lineHeight: 1.3 }}>{activeNode.name}</h2>
          
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
              onClick={() => setActiveNode(null)}
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
