import React, { useState } from 'react';
import { NodeDetails, findNodeById, getNodeSummary } from './NodeDetails';
import './NodeDetails.css';
import './FindingCard.css';

interface Finding {
  kind: string;
  message: string;
  node?: string;
  cycle?: string[];
  edge?: string[];
}

interface FindingCardProps {
  finding: Finding;
  argirData: any;
}

const CycleVisualization: React.FC<{ cycle: string[], argirData: any }> = ({ cycle, argirData }) => {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  const toggleNode = (nodeId: string) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId);
    } else {
      newExpanded.add(nodeId);
    }
    setExpandedNodes(newExpanded);
  };

  return (
    <div className="cycle-visualization">
      <div className="cycle-path">
        <strong>Cycle:</strong> {cycle.join(' → ')} → {cycle[0]}
      </div>
      <div className="cycle-nodes">
        {cycle.map((nodeId) => {
          const node = findNodeById(nodeId, argirData);
          const isExpanded = expandedNodes.has(nodeId);
          
          return (
            <div key={nodeId} className="cycle-node">
              <div 
                className="cycle-node-header"
                onClick={() => toggleNode(nodeId)}
                style={{ cursor: 'pointer' }}
              >
                <span className="cycle-node-id">{nodeId}</span>
                <span className="cycle-node-summary">
                  {node ? getNodeSummary(node) : 'Node not found'}
                </span>
                <span className="expand-indicator">
                  {isExpanded ? '▼' : '▶'}
                </span>
              </div>
              {isExpanded && node && (
                <NodeDetails 
                  node={node} 
                  mode="inline" 
                  showHeader={false}
                  className="cycle-node-details"
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const EdgeVisualization: React.FC<{ edge: string[], argirData: any }> = ({ edge, argirData }) => {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [sourceId, targetId] = edge;

  const toggleNode = (nodeId: string) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId);
    } else {
      newExpanded.add(nodeId);
    }
    setExpandedNodes(newExpanded);
  };

  const sourceNode = findNodeById(sourceId, argirData);
  const targetNode = findNodeById(targetId, argirData);

  return (
    <div className="edge-visualization">
      <div className="edge-path">
        <strong>Edge:</strong> {sourceId} → {targetId}
      </div>
      <div className="edge-nodes">
        {[
          { id: sourceId, node: sourceNode, label: 'Source' },
          { id: targetId, node: targetNode, label: 'Target' }
        ].map(({ id, node, label }) => {
          const isExpanded = expandedNodes.has(id);
          
          return (
            <div key={id} className="edge-node">
              <div 
                className="edge-node-header"
                onClick={() => toggleNode(id)}
                style={{ cursor: 'pointer' }}
              >
                <span className="edge-node-label">{label}:</span>
                <span className="edge-node-id">{id}</span>
                <span className="edge-node-summary">
                  {node ? getNodeSummary(node) : 'Node not found'}
                </span>
                <span className="expand-indicator">
                  {isExpanded ? '▼' : '▶'}
                </span>
              </div>
              {isExpanded && node && (
                <NodeDetails 
                  node={node} 
                  mode="inline" 
                  showHeader={false}
                  className="edge-node-details"
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const FindingCard: React.FC<FindingCardProps> = ({ finding, argirData }) => {
  const [isNodeExpanded, setIsNodeExpanded] = useState(false);

  // Map kind to severity level for display
  const severityMap: Record<string, string> = {
    'derivability_gap': 'warning',
    'circular_support': 'error',
    'edge_mismatch': 'warning'
  };
  const severity = severityMap[finding.kind] || 'info';

  const node = finding.node ? findNodeById(finding.node, argirData) : null;

  return (
    <div
      className={`finding finding-${severity}`}
      style={{
        marginBottom: '1rem',
        padding: '1rem',
        background: 'white',
        borderRadius: '6px',
        borderLeft: `4px solid ${
          severity === 'error' ? '#dc2626' :
          severity === 'warning' ? '#f59e0b' : '#3b82f6'
        }`
      }}
    >
      <div className="finding-header">
        <strong>{finding.kind?.replace(/_/g, ' ').toUpperCase()}:</strong> {finding.message}
      </div>

      {finding.node && (
        <div className="finding-node-section">
          <div 
            className="node-reference"
            onClick={() => setIsNodeExpanded(!isNodeExpanded)}
            style={{ 
              cursor: 'pointer',
              marginTop: '0.75rem',
              padding: '0.5rem',
              background: '#f8fafc',
              borderRadius: '4px',
              border: '1px solid #e2e8f0'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <span style={{ fontWeight: 600, color: '#3b82f6' }}>Node: {finding.node}</span>
                {node && (
                  <div style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: '0.25rem' }}>
                    {getNodeSummary(node)}
                  </div>
                )}
                {!node && (
                  <div style={{ fontSize: '0.875rem', color: '#ef4444', marginTop: '0.25rem' }}>
                    Node data not found
                  </div>
                )}
              </div>
              <span className="expand-indicator" style={{ color: '#6b7280' }}>
                {isNodeExpanded ? '▼ Hide details' : '▶ Show details'}
              </span>
            </div>
          </div>
          
          {isNodeExpanded && node && (
            <NodeDetails 
              node={node} 
              mode="inline" 
              showHeader={false}
              className="finding-node-details"
            />
          )}
        </div>
      )}

      {finding.cycle && (
        <div style={{ marginTop: '0.75rem' }}>
          <CycleVisualization cycle={finding.cycle} argirData={argirData} />
        </div>
      )}

      {finding.edge && (
        <div style={{ marginTop: '0.75rem' }}>
          <EdgeVisualization edge={finding.edge} argirData={argirData} />
        </div>
      )}
    </div>
  );
};
