import React from 'react';
import './DiagnosisDisplay.css';

interface Issue {
  id: string;
  type: string;
  target_node_ids: string[];
  evidence: any;
  detector_name: string;
  notes?: string;
}

interface Repair {
  id: string;
  issue_id: string;
  kind: string;
  patch: any;
  cost: number;
  verification: any;
}

interface DiagnosisDisplayProps {
  issues: Issue[];
  repairs: Repair[];
}

export const DiagnosisDisplay: React.FC<DiagnosisDisplayProps> = ({ issues, repairs }) => {
  const getIssueTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      'unsupported_inference': 'Unsupported Inference',
      'circular_support': 'Circular Reasoning',
      'contradiction_unresolved': 'Unresolved Contradiction',
      'weak_scheme_instantiation': 'Weak Argumentation Scheme',
      'goal_unreachable': 'Goal Unreachable',
    };
    return labels[type] || type;
  };

  const getIssueIcon = (type: string) => {
    const icons: Record<string, string> = {
      'unsupported_inference': '⚠️',
      'circular_support': '🔄',
      'contradiction_unresolved': '⚡',
      'weak_scheme_instantiation': '❓',
      'goal_unreachable': '🎯',
    };
    return icons[type] || '📍';
  };

  const getRepairsForIssue = (issueId: string) => {
    return repairs.filter(r => r.issue_id === issueId);
  };

  if (issues.length === 0) {
    return (
      <div className="diagnosis-display">
        <div className="no-issues">
          <span className="check-icon">✅</span>
          <p>No logical issues detected in the argument structure.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="diagnosis-display">
      <div className="issues-header">
        <h3>Detected Issues ({issues.length})</h3>
      </div>

      {issues.map((issue) => {
        const issueRepairs = getRepairsForIssue(issue.id);

        return (
          <div key={issue.id} className="issue-card">
            <div className="issue-header">
              <span className="issue-icon">{getIssueIcon(issue.type)}</span>
              <div className="issue-title">
                <h4>{getIssueTypeLabel(issue.type)}</h4>
                <span className="issue-id">{issue.id}</span>
              </div>
            </div>

            <div className="issue-body">
              {issue.target_node_ids.length > 0 && (
                <div className="affected-nodes">
                  <strong>Affected nodes:</strong> {issue.target_node_ids.join(', ')}
                </div>
              )}

              {issue.notes && (
                <div className="issue-description">
                  <p>{issue.notes}</p>
                </div>
              )}

              {issueRepairs.length > 0 ? (
                <div className="repairs-section">
                  <h5>Proposed Repairs</h5>
                  {issueRepairs.map((repair) => (
                    <div key={repair.id} className="repair-card">
                      <div className="repair-header">
                        <span className="repair-type">{repair.kind}</span>
                        <span className="repair-cost">Cost: {repair.cost}</span>
                      </div>

                      {repair.patch && (
                        <div className="repair-actions">
                          {repair.patch.add_nodes?.length > 0 && (
                            <div className="action">
                              <strong>Add nodes:</strong>
                              <ul>
                                {repair.patch.add_nodes.map((node: any, i: number) => (
                                  <li key={i}>{node.text || node.id}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {repair.patch.add_edges?.length > 0 && (
                            <div className="action">
                              <strong>Add edges:</strong>
                              <ul>
                                {repair.patch.add_edges.map((edge: any, i: number) => (
                                  <li key={i}>{edge.source} → {edge.target} ({edge.kind})</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {repair.patch.del_edges?.length > 0 && (
                            <div className="action">
                              <strong>Remove edges:</strong>
                              <ul>
                                {repair.patch.del_edges.map((edge: any, i: number) => (
                                  <li key={i}>{edge.source} → {edge.target}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {repair.patch.fol_hypotheses?.length > 0 && (
                            <div className="action">
                              <strong>FOL hypotheses:</strong>
                              <ul>
                                {repair.patch.fol_hypotheses.map((hyp: string, i: number) => (
                                  <li key={i}>{hyp}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}

                      {repair.verification && (
                        <div className="verification">
                          <strong>Verification:</strong>
                          {repair.verification.fol_entailed ? (
                            <span className="verified">✅ FOL verified</span>
                          ) : (
                            <span className="not-verified">❌ FOL failed</span>
                          )}
                          {repair.verification.af_goal_accepted !== null && !repair.verification.af_goal_accepted && (
                            <span className="af-status" title="No clear goal was identified for AF acceptance checking">
                              ⚠️ AF goal not set
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="no-repairs">
                  <strong>Status:</strong> No automated repair available
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};