# NodeDetails Component

A unified component for displaying detailed node information across the application.

## Usage

```tsx
import { NodeDetails, findNodeById } from './NodeDetails';

// Basic usage
<NodeDetails node={nodeData} mode="sidebar" />

// Inline usage (for findings)
<NodeDetails node={nodeData} mode="inline" showHeader={false} />

// Compact usage
<NodeDetails node={nodeData} mode="compact" />
```

## Props

- `node: Node` - The node data to display
- `mode?: 'inline' | 'sidebar' | 'compact'` - Display mode (default: 'sidebar')
- `showHeader?: boolean` - Whether to show the node header (default: true)
- `className?: string` - Additional CSS classes

## Modes

- **sidebar**: Full detail view for graph sidebar (default)
- **inline**: Embedded view for findings cards
- **compact**: Minimal view for space-constrained areas

## Utility Functions

- `findNodeById(nodeId: string, argirData: any): Node | null` - Find a node by ID
- `getNodeSummary(node: Node): string` - Get a short summary of the node

## Integration

This component is used by:
- **ArgumentGraph**: For the detail pane when nodes are clicked
- **FindingCard**: For inline node details in findings
- **ResultDisplay**: Via FindingCard for enhanced findings display

The component ensures consistent node information display across the entire application.
