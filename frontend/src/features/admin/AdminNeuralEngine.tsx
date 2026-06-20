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

  // Force Directed Tuning (3D)
  useEffect(() => {
    if (fgRef.current) {
      // Tune the d3 forces for a dense 3D cluster
      fgRef.current.d3Force("charge").strength((node: any) => {
        if (node.group === "hub") return -2000;
        if (node.group === "domain") return -400;
        if (node.group === "subdomain") return -100;
        return -30;
      });
      fgRef.current.d3Force("link").distance((link: any) => {
        if (link.value === 3) return 120; // hub to domain
        if (link.value === 2) return 50;  // domain to subdomain
        return 15; // subdomain to card
      });
    }
  }, [data]);

  const handleNodeClick = (node: GraphNode) => {
    setActiveNode(node);
    if (fgRef.current) {
      // Calculate a position slightly offset from the node to look at it
      const distance = node.group === "card" ? 60 : node.group === "subdomain" ? 120 : 250;
      const distRatio = 1 + distance / Math.hypot(node.x || 0, node.y || 0, node.z || 0);

      const newPos = {
        x: (node.x || 0) * distRatio,
        y: (node.y || 0) * distRatio,
        z: (node.z || 0) * distRatio
      };

      fgRef.current.cameraPosition(newPos, node, 2000); // 2000 ms transition
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
      // Zoom out to see whole cluster
      fgRef.current.cameraPosition({ x: 0, y: 0, z: 800 }, { x: 0, y: 0, z: 0 }, 2000);
    }
  };

  const handleBackgroundClick = () => {
    setActiveNode(null);
    if (fgRef.current) {
      fgRef.current.cameraPosition({ x: 0, y: 0, z: 800 }, { x: 0, y: 0, z: 0 }, 2000);
    }
  };

  // Pre-create geometries and materials for performance
  const sphereGeo = useMemo(() => new THREE.SphereGeometry(1, 16, 16), []);
  const torusGeo1 = useMemo(() => new THREE.TorusGeometry(3, 0.1, 16, 100), []);
  const torusGeo2 = useMemo(() => new THREE.TorusGeometry(4.5, 0.05, 16, 100), []);
  const torusGeo3 = useMemo(() => new THREE.TorusGeometry(6, 0.02, 16, 100), []);

  const nodeThreeObject = (node: GraphNode) => {
    const group = new THREE.Group();
    const isHovered = node.id === hoverNode?.id;
    const isActive = node.id === activeNode?.id;
    
    // Core glowing sphere
    const material = new THREE.MeshLambertMaterial({ 
      color: node.color,
      emissive: node.color,
      emissiveIntensity: isActive ? 1.5 : isHovered ? 1.0 : 0.6,
      transparent: true,
      opacity: 0.9
    });
    
    const sphere = new THREE.Mesh(sphereGeo, material);
    const size = Math.max(1, Math.sqrt(node.val) * 1.5);
    sphere.scale.set(size, size, size);
    group.add(sphere);

    // Hub holographic rings
    if (node.group === "hub") {
      const ringMat = new THREE.MeshBasicMaterial({ 
        color: node.color, 
        transparent: true, 
        opacity: theme === "amber" ? 0.6 : 0.4,
        side: THREE.DoubleSide
      });
      
      const r1 = new THREE.Mesh(torusGeo1, ringMat);
      const r2 = new THREE.Mesh(torusGeo2, ringMat);
      const r3 = new THREE.Mesh(torusGeo3, ringMat);
      
      // Animate rings using userData
      r1.userData = { axis: new THREE.Vector3(1, 0, 0), speed: 0.02 };
      r2.userData = { axis: new THREE.Vector3(0, 1, 0), speed: -0.015 };
      r3.userData = { axis: new THREE.Vector3(0, 0, 1), speed: 0.01 };
      
      group.add(r1, r2, r3);
      group.userData = { isHub: true, rings: [r1, r2, r3] };
    } 
    // Add text label only for domains/subdomains (or active/hovered nodes)
    else if (node.group === "domain" || node.group === "subdomain" || isActive || isHovered) {
      const sprite = new SpriteText(node.name);
      sprite.color = "rgba(255,255,255,0.8)";
      sprite.textHeight = node.group === "domain" ? 4 : 2;
      sprite.position.y = -(size + sprite.textHeight); // Position below the node
      group.add(sprite);
    }

    return group;
  };

  // Animation loop for hub rings
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

  const cinematicBg = {
    position: "relative" as const,
    width: "100%",
    height: "100%",
    backgroundColor: "#000000",
    overflow: "hidden",
    color: "#fff",
    fontFamily: "Inter, sans-serif"
  };

  return (
    <div style={cinematicBg}>
      
      {/* Top Navbar */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, padding: "1.5rem 2rem", display: "flex", justifyContent: "space-between", alignItems: "center", zIndex: 10, pointerEvents: "none" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: theme === "amber" ? "#f59e0b" : "#10b981", boxShadow: `0 0 15px ${theme === "amber" ? "#f59e0b" : "#10b981"}, 0 0 30px ${theme === "amber" ? "#f59e0b" : "#10b981"}`, animation: "pulse 2s infinite" }} />
          <h1 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 500, letterSpacing: "0.2em", textTransform: "uppercase", textShadow: `0 0 10px ${theme === "amber" ? "rgba(245,158,11,0.5)" : "rgba(16,185,129,0.5)"}` }}>Sift Neural Engine</h1>
        </div>
      </div>

      {/* Force Graph 3D Canvas */}
      {data && (
        <ForceGraph3D
          ref={fgRef}
          graphData={data}
          nodeThreeObject={nodeThreeObject}
          linkColor={(link: any) => {
             const s = typeof link.source === "object" ? link.source : data.nodes.find(n => n.id === link.source);
             return s?.color ? `${s.color}${theme === "amber" ? "60" : "40"}` : "#222222";
          }}
          linkWidth={(link: any) => link.value === 3 ? 1.0 : 0.5}
          linkDirectionalParticles={(link: any) => (link.value === 3 ? 5 : link.value === 2 ? 3 : 2)}
          linkDirectionalParticleWidth={(link: any) => link.value === 3 ? 2 : 1}
          linkDirectionalParticleSpeed={0.005}
          linkDirectionalParticleColor={(link: any) => {
             const s = typeof link.source === "object" ? link.source : data.nodes.find(n => n.id === link.source);
             return s?.color || "#ffffff";
          }}
          onNodeHover={(node: any) => setHoverNode(node || null)}
          onNodeClick={(node: any) => handleNodeClick(node)}
          onBackgroundClick={handleBackgroundClick}
          backgroundColor="#020204"
          d3AlphaDecay={0.015}
          d3VelocityDecay={0.25}
          showNavInfo={false}
        />
      )}

      {/* Loading / Error States */}
      {!data && !error && (
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", color: "#52525b", letterSpacing: "0.1em" }}>
          INITIALIZING 3D TOPOLOGY...
        </div>
      )}
      {error && (
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", color: "#f43f5e" }}>
          {error}
        </div>
      )}

      {/* Theme Toggle */}
      <div style={{ position: "absolute", top: "2rem", right: "2rem", zIndex: 10, display: "flex", gap: "0.5rem" }}>
        <button 
          onClick={() => setTheme("amber")}
          style={{ padding: "0.5rem 1rem", borderRadius: "20px", background: theme === "amber" ? "rgba(245, 158, 11, 0.2)" : "rgba(255,255,255,0.05)", border: `1px solid ${theme === "amber" ? "#f59e0b" : "transparent"}`, color: theme === "amber" ? "#fcd34d" : "#a1a1aa", cursor: "pointer", transition: "all 0.2s" }}
        >
          Evolution
        </button>
        <button 
          onClick={() => setTheme("blue")}
          style={{ padding: "0.5rem 1rem", borderRadius: "20px", background: theme === "blue" ? "rgba(59, 130, 246, 0.2)" : "rgba(255,255,255,0.05)", border: `1px solid ${theme === "blue" ? "#3b82f6" : "transparent"}`, color: theme === "blue" ? "#93c5fd" : "#a1a1aa", cursor: "pointer", transition: "all 0.2s" }}
        >
          Deep Blue
        </button>
      </div>

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
          @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.1); opacity: 0.8; }
            100% { transform: scale(1); opacity: 1; }
          }
        `}
      </style>
    </div>
  );
}
