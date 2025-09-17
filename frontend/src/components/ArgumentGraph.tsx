import React, { useState, useMemo, useRef, useEffect } from 'react';

interface Node {
  id: string;
  premises?: any[];
  conclusion?: { text?: string };
  rule?: string | {
    name?: string;
    strict?: boolean;
    antecedents?: any[];
    consequents?: any[];
    exceptions?: any[];
  };
}

interface Edge {
  source: string;
  target: string;
  kind: 'support' | 'attack';
  rationale?: string;
}

interface GraphData {
  nodes: Node[];
  edges: Edge[];
}

interface ArgumentGraphProps {
  data: GraphData | null;
}

type SelectedItem = 
  | { type: 'node'; data: Node }
  | { type: 'edge'; data: Edge }
  | null;

const DetailPane: React.FC<{ selectedItem: SelectedItem; onClose: () => void }> = ({ selectedItem, onClose }) => {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (!selectedItem) return null;

  const renderNodeDetails = (node: Node) => (
    <div>
      <h3 style={{ margin: '0 0 1rem 0', color: '#1f2937', fontSize: '18px' }}>Node: {node.id}</h3>
      
      {node.conclusion?.text && (
        <div style={{ marginBottom: '1rem' }}>
          <h4 style={{ margin: '0 0 0.5rem 0', color: '#374151', fontSize: '14px', fontWeight: '600' }}>Conclusion:</h4>
          <div style={{ 
            margin: 0, 
            color: '#4b5563', 
            fontSize: '14px', 
            lineHeight: '1.5', 
            padding: '0.5rem', 
            background: '#f9fafb', 
            borderRadius: '4px', 
            border: '1px solid #e5e7eb',
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
            maxHeight: '200px',
            overflow: 'auto'
          }}>
            {node.conclusion.text}
          </div>
        </div>
      )}
      
      {node.rule && (
        <div style={{ marginBottom: '1rem' }}>
          <h4 style={{ margin: '0 0 0.5rem 0', color: '#374151', fontSize: '14px', fontWeight: '600' }}>Rule:</h4>
          <div style={{ 
            margin: 0, 
            color: '#4b5563', 
            fontSize: '14px', 
            lineHeight: '1.5', 
            padding: '0.5rem', 
            background: '#f0f9ff', 
            borderRadius: '4px', 
            border: '1px solid #bae6fd',
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
            maxHeight: '200px',
            overflow: 'auto'
          }}>
            {typeof node.rule === 'string' ? node.rule : (
              <div>
                {node.rule.name && (
                  <div style={{ fontWeight: '600', marginBottom: '0.5rem' }}>
                    {node.rule.name}
                    {node.rule.strict !== undefined && (
                      <span style={{ 
                        marginLeft: '0.5rem', 
                        padding: '0.125rem 0.25rem', 
                        fontSize: '10px', 
                        borderRadius: '2px',
                        background: node.rule.strict ? '#dcfce7' : '#fef3c7',
                        color: node.rule.strict ? '#166534' : '#92400e'
                      }}>
                        {node.rule.strict ? 'STRICT' : 'DEFEASIBLE'}
                      </span>
                    )}
                  </div>
                )}
                {node.rule.antecedents && node.rule.antecedents.length > 0 && (
                  <div style={{ marginBottom: '0.5rem' }}>
                    <strong>If:</strong> {node.rule.antecedents.map((ant: any) => ant.text || JSON.stringify(ant)).join(', ')}
                  </div>
                )}
                {node.rule.consequents && node.rule.consequents.length > 0 && (
                  <div style={{ marginBottom: '0.5rem' }}>
                    <strong>Then:</strong> {node.rule.consequents.map((cons: any) => cons.text || JSON.stringify(cons)).join(', ')}
                  </div>
                )}
                {node.rule.exceptions && node.rule.exceptions.length > 0 && (
                  <div style={{ marginBottom: '0.5rem' }}>
                    <strong>Except:</strong> {node.rule.exceptions.map((exc: any) => exc.text || JSON.stringify(exc)).join(', ')}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      
      {node.premises && node.premises.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <h4 style={{ margin: '0 0 0.5rem 0', color: '#374151', fontSize: '14px', fontWeight: '600' }}>Premises:</h4>
          <div style={{ padding: '0.5rem', background: '#fefce8', borderRadius: '4px', border: '1px solid #fde047' }}>
            {node.premises.map((premise, idx) => (
              <div key={idx} style={{ 
                marginBottom: idx < node.premises!.length - 1 ? '0.5rem' : 0,
                color: '#4b5563', 
                fontSize: '14px', 
                lineHeight: '1.5',
                whiteSpace: 'pre-wrap',
                wordWrap: 'break-word'
              }}>
                {typeof premise === 'string' ? premise : JSON.stringify(premise, null, 2)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderEdgeDetails = (edge: Edge) => (
    <div>
      <h3 style={{ margin: '0 0 1rem 0', color: '#1f2937', fontSize: '18px' }}>
        Edge: {edge.source} → {edge.target}
      </h3>
      
      <div style={{ marginBottom: '1rem' }}>
        <h4 style={{ margin: '0 0 0.5rem 0', color: '#374151', fontSize: '14px', fontWeight: '600' }}>Type:</h4>
        <span style={{ 
          display: 'inline-block',
          padding: '0.25rem 0.5rem', 
          borderRadius: '4px', 
          fontSize: '12px', 
          fontWeight: '500',
          color: edge.kind === 'attack' ? '#dc2626' : '#059669',
          background: edge.kind === 'attack' ? '#fee2e2' : '#d1fae5',
          border: edge.kind === 'attack' ? '1px solid #fca5a5' : '1px solid #86efac'
        }}>
          {edge.kind.toUpperCase()}
        </span>
      </div>
      
      {edge.rationale && (
        <div style={{ marginBottom: '1rem' }}>
          <h4 style={{ margin: '0 0 0.5rem 0', color: '#374151', fontSize: '14px', fontWeight: '600' }}>Rationale:</h4>
          <div style={{ 
            margin: 0, 
            color: '#4b5563', 
            fontSize: '14px', 
            lineHeight: '1.5', 
            padding: '0.5rem', 
            background: '#f9fafb', 
            borderRadius: '4px', 
            border: '1px solid #e5e7eb',
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
            maxHeight: '200px',
            overflow: 'auto'
          }}>
            {edge.rationale}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div style={{
      width: isMobile ? '100%' : '350px',
      height: '100%',
      background: 'white',
      borderLeft: !isMobile ? '1px solid #e5e7eb' : 'none',
      borderTop: isMobile ? '1px solid #e5e7eb' : 'none',
      padding: '1rem',
      overflow: 'auto',
      boxShadow: !isMobile ? '-2px 0 8px rgba(0, 0, 0, 0.1)' : '0 -2px 8px rgba(0, 0, 0, 0.1)',
      position: isMobile ? 'absolute' : 'static',
      bottom: isMobile ? 0 : 'auto',
      left: isMobile ? 0 : 'auto',
      right: isMobile ? 0 : 'auto',
      zIndex: isMobile ? 10 : 'auto',
      maxHeight: isMobile ? '50%' : '100%'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 style={{ margin: 0, color: '#1f2937', fontSize: '16px', fontWeight: '600' }}>Details</h2>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '18px',
            color: '#6b7280',
            cursor: 'pointer',
            padding: '0.25rem',
            borderRadius: '4px',
            width: '28px',
            height: '28px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#f3f4f6'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
        >
          ×
        </button>
      </div>
      
      {selectedItem.type === 'node' ? renderNodeDetails(selectedItem.data) : renderEdgeDetails(selectedItem.data)}
    </div>
  );
};

export const ArgumentGraph: React.FC<ArgumentGraphProps> = ({ data }) => {
  if (!data || !data.nodes || data.nodes.length === 0) {
    return <div className="muted">No graph data available</div>;
  }

  const [draggedNode, setDraggedNode] = useState<string | null>(null);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [selectedItem, setSelectedItem] = useState<SelectedItem>(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const { layout, initialPositions } = useMemo(() => {
    // Simple force-directed layout simulation
    const nodes = data.nodes;
    const edges = data.edges || [];

    // Initialize positions randomly
    const positions: Record<string, { x: number; y: number }> = {};
    const width = 800;
    const height = 600;
    const centerX = width / 2;
    const centerY = height / 2;

    // Place nodes in a circle initially
    nodes.forEach((node, i) => {
      const angle = (i / nodes.length) * 2 * Math.PI;
      const radius = Math.min(width, height) * 0.3;
      positions[node.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      };
    });

    // Simple force simulation (just a few iterations for basic layout)
    for (let iter = 0; iter < 50; iter++) {
      const forces: Record<string, { x: number; y: number }> = {};

      // Initialize forces
      nodes.forEach(node => {
        forces[node.id] = { x: 0, y: 0 };
      });

      // Repulsion between all nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const n1 = nodes[i];
          const n2 = nodes[j];
          const p1 = positions[n1.id];
          const p2 = positions[n2.id];

          const dx = p2.x - p1.x;
          const dy = p2.y - p1.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist > 0) {
            const force = 5000 / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            forces[n1.id].x -= fx;
            forces[n1.id].y -= fy;
            forces[n2.id].x += fx;
            forces[n2.id].y += fy;
          }
        }
      }

      // Attraction along edges
      edges.forEach(edge => {
        const p1 = positions[edge.source];
        const p2 = positions[edge.target];

        if (p1 && p2) {
          const dx = p2.x - p1.x;
          const dy = p2.y - p1.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist > 0) {
            const force = dist * 0.1;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            forces[edge.source].x += fx;
            forces[edge.source].y += fy;
            forces[edge.target].x -= fx;
            forces[edge.target].y -= fy;
          }
        }
      });

      // Apply forces with damping
      const damping = 0.1;
      nodes.forEach(node => {
        const force = forces[node.id];
        positions[node.id].x += force.x * damping;
        positions[node.id].y += force.y * damping;

        // Keep nodes within bounds
        positions[node.id].x = Math.max(50, Math.min(width - 50, positions[node.id].x));
        positions[node.id].y = Math.max(50, Math.min(height - 50, positions[node.id].y));
      });
    }

    return { layout: { width, height }, initialPositions: positions };
  }, [data]);

  // Initialize positions on first load or data change
  React.useEffect(() => {
    setPositions(initialPositions);
  }, [initialPositions]);

  const getNodeLabel = (node: Node) => {
    if (node.conclusion?.text) {
      return node.conclusion.text.substring(0, 30) + (node.conclusion.text.length > 30 ? '...' : '');
    }
    return node.id;
  };

  const getNodeColor = (node: Node) => {
    if (node.rule) return '#60a5fa'; // Light blue for rules
    if (node.conclusion?.text) return '#86efac'; // Light green for conclusions
    return '#9ca3af'; // Light gray for others
  };

  const handleNodeClick = (node: Node, event: React.MouseEvent<SVGCircleElement>) => {
    event.stopPropagation();
    setSelectedItem({ type: 'node', data: node });
  };

  const handleEdgeClick = (edge: Edge, event: React.MouseEvent<SVGLineElement>) => {
    event.stopPropagation();
    setSelectedItem({ type: 'edge', data: edge });
  };

  const handleMouseDown = (nodeId: string, event: React.MouseEvent<SVGCircleElement>) => {
    setDraggedNode(nodeId);
    event.preventDefault();
  };

  const handleMouseMove = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!draggedNode || !svgRef.current) return;

    const rect = svgRef.current.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    setPositions(prev => ({
      ...prev,
      [draggedNode]: { x, y }
    }));
  };

  const handleMouseUp = () => {
    setDraggedNode(null);
  };

  const nodePositions = positions;

  return (
    <div 
      style={{ 
        display: 'flex', 
        flexDirection: isMobile ? 'column' : 'row',
        width: '100%', 
        height: '600px', 
        overflow: 'hidden',
        position: 'relative'
      }}
      onClick={() => isMobile && selectedItem && setSelectedItem(null)}
    >
      <div style={{ 
        flex: 1, 
        overflow: 'auto',
        minHeight: isMobile ? '50%' : 'auto'
      }}>
        <svg
        ref={svgRef}
        width={layout.width}
        height={layout.height}
        style={{
          background: '#f9fafb',
          borderRadius: '8px',
          border: '1px solid #e5e7eb',
          cursor: draggedNode ? 'grabbing' : 'grab'
        }}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* Draw edges */}
        {data.edges?.map((edge, i) => {
          const source = nodePositions[edge.source];
          const target = nodePositions[edge.target];

          if (!source || !target) return null;

          // Calculate arrow position
          const dx = target.x - source.x;
          const dy = target.y - source.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const normX = dx / dist;
          const normY = dy / dist;

          // Offset to account for node radius
          const nodeRadius = 30;
          const startX = source.x + normX * nodeRadius;
          const startY = source.y + normY * nodeRadius;
          const endX = target.x - normX * nodeRadius;
          const endY = target.y - normY * nodeRadius;

          return (
            <g key={`edge-${i}`}>
              <defs>
                <marker
                  id={`arrow-${i}`}
                  markerWidth="10"
                  markerHeight="10"
                  refX="9"
                  refY="3"
                  orient="auto"
                  markerUnits="strokeWidth"
                >
                  <path
                    d="M0,0 L0,6 L9,3 z"
                    fill={edge.kind === 'attack' ? '#ef4444' : '#6b7280'}
                  />
                </marker>
              </defs>
              <line
                x1={startX}
                y1={startY}
                x2={endX}
                y2={endY}
                stroke={selectedItem?.type === 'edge' && selectedItem.data.source === edge.source && selectedItem.data.target === edge.target ? '#2563eb' : (edge.kind === 'attack' ? '#ef4444' : '#6b7280')}
                strokeWidth={selectedItem?.type === 'edge' && selectedItem.data.source === edge.source && selectedItem.data.target === edge.target ? 3 : 2}
                strokeDasharray={edge.kind === 'attack' ? '5,5' : '0'}
                markerEnd={`url(#arrow-${i})`}
                style={{ cursor: 'pointer' }}
                onClick={(e) => handleEdgeClick(edge, e)}
              />
              {edge.rationale && (
                <text
                  x={(startX + endX) / 2}
                  y={(startY + endY) / 2 - 5}
                  fontSize="10"
                  fill="#6b7280"
                  textAnchor="middle"
                >
                  {edge.rationale.substring(0, 20)}
                </text>
              )}
            </g>
          );
        })}

        {/* Draw nodes */}
        {data.nodes.map((node) => {
          const pos = nodePositions[node.id];
          if (!pos) return null;

          const nodeColor = getNodeColor(node);
          const isDragging = draggedNode === node.id;

          return (
            <g key={node.id}>
              <circle
                cx={pos.x}
                cy={pos.y}
                r="35"
                fill={nodeColor}
                stroke={isDragging ? '#2563eb' : (selectedItem?.type === 'node' && selectedItem.data.id === node.id ? '#2563eb' : '#ffffff')}
                strokeWidth={isDragging ? 3 : (selectedItem?.type === 'node' && selectedItem.data.id === node.id ? 3 : 2)}
                style={{
                  filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.15))',
                  cursor: isDragging ? 'grabbing' : 'pointer',
                  transition: isDragging ? 'none' : 'all 0.2s'
                }}
                onMouseDown={(e) => handleMouseDown(node.id, e)}
                onClick={(e) => handleNodeClick(node, e)}
              />
              <text
                x={pos.x}
                y={pos.y - 45}
                fontSize="13"
                fontWeight="600"
                fill="#1f2937"
                textAnchor="middle"
                style={{ pointerEvents: 'none', userSelect: 'none' }}
              >
                {node.id}
              </text>
              <text
                x={pos.x}
                y={pos.y + 5}
                fontSize="11"
                fill="#1f2937"
                textAnchor="middle"
                style={{ pointerEvents: 'none', userSelect: 'none' }}
              >
                {getNodeLabel(node).substring(0, 12)}
              </text>
            </g>
          );
        })}

        {/* Legend */}
        <g transform="translate(10, 20)">
          <rect x="0" y="0" width="150" height="90" fill="white" fillOpacity="0.95" stroke="#e5e7eb" rx="4" />
          <text x="10" y="20" fontSize="12" fontWeight="bold" fill="#1f2937">Legend:</text>
          <circle cx="20" cy="35" r="5" fill="#86efac" />
          <text x="30" y="39" fontSize="11" fill="#4b5563">Conclusion</text>
          <circle cx="20" cy="50" r="5" fill="#60a5fa" />
          <text x="30" y="54" fontSize="11" fill="#4b5563">Rule</text>
          <line x1="10" y1="65" x2="30" y2="65" stroke="#6b7280" strokeWidth="2" markerEnd="url(#arrow-legend)" />
          <text x="35" y="69" fontSize="11">Support</text>
          <line x1="10" y1="80" x2="30" y2="80" stroke="#ef4444" strokeWidth="2" strokeDasharray="3,3" />
          <text x="35" y="84" fontSize="11">Attack</text>
        </g>
        </svg>
      </div>
      <DetailPane 
        selectedItem={selectedItem} 
        onClose={() => setSelectedItem(null)} 
      />
    </div>
  );
};