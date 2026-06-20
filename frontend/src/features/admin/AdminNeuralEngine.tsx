import { useEffect, useState, useRef, useMemo } from "react";
import ForceGraph3D from "react-force-graph-3d";
import * as THREE from "three";
import SpriteText from "three-spritetext";
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
  z?: number;
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

export function AdminNeuralEngine() {
  const [theme, setTheme] = useState<"amber" | "blue">("amber");
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const [activeNode, setActiveNode] = useState<GraphNode | null>(null);
  
  const fgRef = useRef<any>();

  // Fetch Graph Data & Apply Theme Colors
  useEffect(() => {
    async function loadGraph() {
      try {
        const res = await fetch(`${API_BASE}/api/brain/graph`);
        if (!res.ok) throw new Error("Failed to load graph data");
        const json = await res.json();
        
        json.nodes.forEach((node: GraphNode) => {
          if (theme === "amber") {
            if (node.group === "hub") node.color = "#ffed4a";
            else if (node.group === "domain") node.color = "#f59e0b";
            else if (node.group === "subdomain") node.color = "#fbbf24";
            else node.color = "#fcd34d";
          } else {
            if (node.group === "hub") node.color = "#ffffff";
            else if (node.group === "domain") node.color = "#3b82f6";
            else if (node.group === "subdomain") node.color = "#0ea5e9";
            else node.color = "#38bdf8";
          }
        });

        setData(json);
      } catch (e: any) {
        setError(e.message);
      }
    }
    void loadGraph();
  }, [theme]);

  // Force Directed Tuning (3D) - Dense Circular Organic Brain
  useEffect(() => {
    if (fgRef.current && data) {
      // Pull nodes tightly together into a dense sphere
      fgRef.current.d3Force("charge").strength((node: any) => {
        if (node.group === "hub") return -800;
        if (node.group === "domain") return -150;
        if (node.group === "subdomain") return -40;
        return -15; // cards pack very tight
      });
      // Shorten links to remove stringy appearance
      fgRef.current.d3Force("link").distance((link: any) => {
        if (link.value === 3) return 40; // hub to domain
        if (link.value === 2) return 20;  // domain to subdomain
        return 8; // subdomain to card
      });
    }
  }, [data]);

  const handleNodeClick = (node: GraphNode) => {
    setActiveNode(node);
    if (fgRef.current) {
      const distance = node.group === "card" ? 30 : node.group === "subdomain" ? 60 : 120;
      const distRatio = 1 + distance / Math.max(Math.hypot(node.x || 0, node.y || 0, node.z || 0), 1);

      const newPos = {
        x: (node.x || 0) * distRatio,
        y: (node.y || 0) * distRatio,
        z: (node.z || 0) * distRatio
      };

      fgRef.current.cameraPosition(newPos, node, 1500); // 1.5s smooth transition
    }
  };

  const handleClosePanel = () => {
    if (!activeNode || !data || !fgRef.current) {
      setActiveNode(null);
      return;
    }
    
    // Find parent node link for the "bounce-back" circular traversal
    const parentLink = data.links.find((l: any) => 
      (typeof l.target === "object" ? l.target.id === activeNode.id : l.target === activeNode.id)
    );
    
    let parentNode: GraphNode | null = null;
    if (parentLink) {
      const sourceId = typeof parentLink.source === "object" ? parentLink.source.id : parentLink.source;
      parentNode = data.nodes.find(n => n.id === sourceId) || null;
    }
    
    if (parentNode && parentNode.group !== "hub") {
      // Zoom out to parent node elegantly
      handleNodeClick(parentNode);
    } else {
      setActiveNode(null);
      // Zoom back to a wide orbital view of the whole cluster
      fgRef.current.cameraPosition({ x: 0, y: 0, z: 300 }, { x: 0, y: 0, z: 0 }, 2000);
    }
  };

  const handleBackgroundClick = () => {
    setActiveNode(null);
    if (fgRef.current) {
      fgRef.current.cameraPosition({ x: 0, y: 0, z: 300 }, { x: 0, y: 0, z: 0 }, 2000);
    }
  };

  // Pre-create geometries for performance
  const sphereGeo = useMemo(() => new THREE.SphereGeometry(1, 24, 24), []);
  const hubRingGeo = useMemo(() => new THREE.TorusGeometry(3.5, 0.05, 16, 100), []);

  const nodeThreeObject = (node: GraphNode) => {
    const group = new THREE.Group();
    const isHovered = node.id === hoverNode?.id;
    const isActive = node.id === activeNode?.id;
    
    // Premium Glassmorphic / Physical Material
    const material = new THREE.MeshPhysicalMaterial({ 
      color: node.color,
      emissive: node.color,
      emissiveIntensity: isActive ? 1.5 : isHovered ? 0.8 : (node.group === "card" ? 0.3 : 0.6),
      transparent: true,
      opacity: node.group === "card" ? 0.8 : 0.95,
      roughness: 0.1,
      metalness: 0.5,
      clearcoat: 1.0,
      clearcoatRoughness: 0.1
    });
    
    const sphere = new THREE.Mesh(sphereGeo, material);
    const size = Math.max(1, Math.sqrt(node.val) * 1.5);
    sphere.scale.set(size, size, size);
    group.add(sphere);

    // Hub node gets a single sleek orbital ring instead of cluttered geometry
    if (node.group === "hub") {
      const ringMat = new THREE.MeshBasicMaterial({ 
        color: node.color, 
        transparent: true, 
        opacity: theme === "amber" ? 0.5 : 0.3,
        side: THREE.DoubleSide
      });
      
      const ring = new THREE.Mesh(hubRingGeo, ringMat);
      ring.userData = { axis: new THREE.Vector3(0.5, 1, 0).normalize(), speed: 0.015 };
      group.add(ring);
      group.userData = { isHub: true, rings: [ring] };
    } 
    // High-quality SpriteText labels for major domains
    else if (node.group === "domain" || node.group === "subdomain" || isActive || isHovered) {
      // Hide card labels unless hovered/active to prevent clutter
      if (node.group !== "card" || isActive || isHovered) {
        const sprite = new SpriteText(node.name);
        sprite.fontFace = "Inter, sans-serif";
        sprite.fontWeight = "500";
        sprite.color = "rgba(255,255,255,0.9)";
        sprite.textHeight = node.group === "domain" ? 3 : node.group === "subdomain" ? 1.8 : 1.2;
        
        // Add a slight dark background to make text legible against bright nodes
        sprite.backgroundColor = "rgba(0,0,0,0.4)";
        sprite.padding = 1.5;
        sprite.borderRadius = 2;
        
        sprite.position.y = -(size + sprite.textHeight);
        group.add(sprite);
      }
    }

    return group;
  };

  // Animation loop for the hub ring
  useEffect(() => {
    let animationFrameId: number;
    const animate = () => {
      if (fgRef.current) {
        const scene = fgRef.current.scene();
        scene.traverse((obj: any) => {
          if (obj.userData && obj.userData.isHub && obj.userData.rings) {
            obj.userData.rings.forEach((ring: any) => {
              ring.rotateOnAxis(ring.userData.axis, ring.userData.speed);
            });
          }
        });
      }
      animationFrameId = requestAnimationFrame(animate);
    };
    animate();
    return () => cancelAnimationFrame(animationFrameId);
  }, [data]);

  return (
    <div className="neural-engine-shell" style={{ position: "relative", width: "100%", height: "100%", background: "#020204", overflow: "hidden" }}>
      
      {/* Pane Header matching the Main Platform */}
      <header className="pane-header" style={{ position: "absolute", top: 0, left: 0, right: 0, zIndex: 10, background: "transparent", borderBottom: "none" }}>
        <div>
          <span className="eyebrow">Admin Portal</span>
          <h2 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <div className={`status-dot ${theme === "amber" ? "amber" : "green"}`} style={{ 
              backgroundColor: theme === "amber" ? "var(--brain-accent)" : "#10b981", 
              boxShadow: `0 0 10px ${theme === "amber" ? "var(--brain-glow)" : "rgba(16,185,129,0.5)"}` 
            }} />
            Neural Engine
          </h2>
        </div>
        <div className="status-stack">
          <div className="header-actions">
            <button type="button" className={`ghost-button compact ${theme === "amber" ? "active" : ""}`} onClick={() => setTheme("amber")}>
              Evolution
            </button>
            <button type="button" className={`ghost-button compact ${theme === "blue" ? "active" : ""}`} onClick={() => setTheme("blue")}>
              Deep Blue
            </button>
          </div>
        </div>
      </header>

      {/* Force Graph 3D Canvas */}
      {data && (
        <ForceGraph3D
          ref={fgRef}
          graphData={data}
          nodeThreeObject={nodeThreeObject}
          linkColor={(link: any) => {
             const s = typeof link.source === "object" ? link.source : data.nodes.find(n => n.id === link.source);
             return s?.color ? `${s.color}${theme === "amber" ? "40" : "30"}` : "#222222";
          }}
          linkWidth={(link: any) => link.value === 3 ? 0.8 : 0.3}
          linkDirectionalParticles={(link: any) => (link.value === 3 ? 4 : link.value === 2 ? 2 : 0)}
          linkDirectionalParticleWidth={1.5}
          linkDirectionalParticleSpeed={0.008}
          linkDirectionalParticleColor={(link: any) => {
             const s = typeof link.source === "object" ? link.source : data.nodes.find(n => n.id === link.source);
             return s?.color || "#ffffff";
          }}
          onNodeHover={(node: any) => setHoverNode(node || null)}
          onNodeClick={(node: any) => handleNodeClick(node)}
          onBackgroundClick={handleBackgroundClick}
          backgroundColor="#020204"
          d3AlphaDecay={0.01}
          d3VelocityDecay={0.3} // Higher friction for tighter grouping
          showNavInfo={false}
        />
      )}

      {/* Loading / Error States */}
      {!data && !error && (
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", color: "var(--text-muted)", letterSpacing: "0.1em", zIndex: 5, fontSize: "0.85rem", textTransform: "uppercase" }}>
          Initializing Neural Cluster...
        </div>
      )}
      {error && (
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", color: "var(--status-error)", zIndex: 5 }}>
          {error}
        </div>
      )}

      {/* Minimalist Inspector Panel matching platform aesthetics */}
      {activeNode && (
        <div 
          style={{ 
            position: "absolute", 
            bottom: "2rem", 
            right: "2rem", 
            width: "320px",
            background: "var(--bg-panel)", 
            border: "1px solid var(--border-color)",
            borderRadius: "12px",
            padding: "1.5rem",
            zIndex: 20,
            boxShadow: "0 20px 40px rgba(0,0,0,0.4)",
            animation: "fadeIn 0.3s ease-out forwards"
          }}
        >
          <div style={{ fontSize: "0.65rem", textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-muted)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", backgroundColor: activeNode.color || "var(--text-primary)", boxShadow: `0 0 8px ${activeNode.color}` }}></span>
            {activeNode.group === "card" ? "Expert Card" : activeNode.group}
          </div>
          
          <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem", fontWeight: 500, color: "var(--text-primary)" }}>
            {activeNode.name}
          </h3>
          
          {activeNode.description && (
            <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
              {activeNode.description}
            </p>
          )}
          
          {activeNode.group === "card" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "1rem", borderTop: "1px solid var(--border-color)", paddingTop: "1rem" }}>
              <div>
                <div className="eyebrow">Domain</div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-primary)", textTransform: "capitalize", marginTop: "0.2rem" }}>{activeNode.domain}</div>
              </div>
              <div>
                <div className="eyebrow">Confidence</div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-primary)", textTransform: "capitalize", marginTop: "0.2rem" }}>{activeNode.confidence}</div>
              </div>
            </div>
          )}

          <div style={{ marginTop: "1.5rem", display: "flex", justifyContent: "flex-end" }}>
            <button className="ghost-button compact" onClick={handleClosePanel}>
              Close Inspector
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
