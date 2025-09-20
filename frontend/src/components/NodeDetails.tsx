import React from 'react';

export interface Node {
  id: string;
  premises?: any[];
  conclusion?: { text?: string; atoms?: any[] };
  rule?: string | {
    name?: string;
    strict?: boolean;
    antecedents?: any[];
    consequents?: any[];
    exceptions?: any[];
    scheme?: string;
  };
  span?: string | { start: number; end: number; text: string };
  rationale?: string;
}

interface NodeDetailsProps {
  node: Node;
  mode?: 'inline' | 'sidebar' | 'compact';
  showHeader?: boolean;
  className?: string;
}

export const NodeDetails: React.FC<NodeDetailsProps> = ({ 
  node, 
  mode = 'sidebar', 
  showHeader = true,
  className = ''
}) => {
  const isCompact = mode === 'compact';
  const isInline = mode === 'inline';

  const renderNodeDetails = () => (
    <div className={`node-details ${mode} ${className}`}>
      {showHeader && (
        <h3 className="node-header">
          Node: {node.id}
        </h3>
      )}

      {node.span && (
        <div className="detail-section">
          <h4>Evidence from text:</h4>
          <div className="detail-content evidence-text">
            "{typeof node.span === 'object' ? node.span.text : node.span}"
          </div>
        </div>
      )}

      {node.conclusion?.text && (
        <div className="detail-section">
          <h4>Conclusion:</h4>
          <div className="detail-content conclusion">
            {node.conclusion.text}
          </div>
        </div>
      )}

      {node.rationale && !isCompact && (
        <div className="detail-section">
          <h4>Rationale:</h4>
          <div className="detail-content">
            {node.rationale}
          </div>
        </div>
      )}
      
      {node.rule && !isCompact && (
        <div className="detail-section">
          <h4>Rule:</h4>
          <div className="detail-content rule">
            {typeof node.rule === 'string' ? node.rule : (
              <div>
                {node.rule.name && (
                  <div className="rule-name">
                    {node.rule.name}
                    {node.rule.strict !== undefined && (
                      <span className={`rule-badge ${node.rule.strict ? 'strict' : 'defeasible'}`}>
                        {node.rule.strict ? 'STRICT' : 'DEFEASIBLE'}
                      </span>
                    )}
                  </div>
                )}
                {node.rule.antecedents && node.rule.antecedents.length > 0 && (
                  <div className="rule-section">
                    <strong>If:</strong> {node.rule.antecedents.map((ant: any) => ant.text || JSON.stringify(ant)).join(', ')}
                  </div>
                )}
                {node.rule.consequents && node.rule.consequents.length > 0 && (
                  <div className="rule-section">
                    <strong>Then:</strong> {node.rule.consequents.map((cons: any) => cons.text || JSON.stringify(cons)).join(', ')}
                  </div>
                )}
                {node.rule.exceptions && node.rule.exceptions.length > 0 && (
                  <div className="rule-section">
                    <strong>Except:</strong> {node.rule.exceptions.map((exc: any) => exc.text || JSON.stringify(exc)).join(', ')}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      
      {node.premises && node.premises.length > 0 && !isCompact && (
        <div className="detail-section">
          <h4>Premises:</h4>
          <div className="detail-content premises">
            {node.premises.map((premise, idx) => (
              <div key={idx} className="premise-item">
                {typeof premise === 'string' ? premise : JSON.stringify(premise, null, 2)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  if (isInline) {
    return (
      <div className="node-details-inline">
        {renderNodeDetails()}
      </div>
    );
  }

  return renderNodeDetails();
};

// Utility function to find a node by ID in the ARGIR data
export const findNodeById = (nodeId: string, argirData: any): Node | null => {
  // Try direct nodes first (for compatibility)
  if (argirData?.nodes) {
    return argirData.nodes.find((n: Node) => n.id === nodeId) || null;
  }
  // Try nodes nested in graph object
  if (argirData?.graph?.nodes) {
    return argirData.graph.nodes.find((n: Node) => n.id === nodeId) || null;
  }
  return null;
};

// Utility function to get node summary text
export const getNodeSummary = (node: Node): string => {
  if (node.conclusion?.text) {
    return node.conclusion.text.length > 50 
      ? node.conclusion.text.substring(0, 50) + '...'
      : node.conclusion.text;
  }
  if (node.rule && typeof node.rule === 'object' && node.rule.name) {
    return node.rule.name;
  }
  return node.id;
};
