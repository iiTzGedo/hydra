import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Server, Network, Cpu, GitBranch } from 'lucide-react';
import { useLatestTopology } from '@/api/topologies';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/common/empty-state';

interface TopologyTabProps {
  nodeId: string;
}

export function TopologyTab({ nodeId }: TopologyTabProps) {
  const { data: topology, isLoading, error } = useLatestTopology('infrastructure', true);

  // Extract subgraph for the current node from the full topology
  const subgraphData = useMemo(() => {
    if (!topology?.graph) return null;

    const currentNode = topology.graph.nodes.find(n => n.id === nodeId || n.data?.nodeId === nodeId);
    if (!currentNode) return null;

    // Find all edges connected to this node
    const connectedEdges = topology.graph.edges.filter(
      e => e.source === nodeId || e.target === nodeId ||
           e.source === currentNode.id || e.target === currentNode.id
    );

    // Find all adjacent node IDs
    const adjacentNodeIds = new Set<string>();
    connectedEdges.forEach(edge => {
      if (edge.source !== nodeId && edge.source !== currentNode.id) {
        adjacentNodeIds.add(edge.source);
      }
      if (edge.target !== nodeId && edge.target !== currentNode.id) {
        adjacentNodeIds.add(edge.target);
      }
    });

    // Get adjacent node details
    const adjacentNodes = topology.graph.nodes.filter(n =>
      adjacentNodeIds.has(n.id) || adjacentNodeIds.has(n.data?.nodeId || '')
    );

    // Count services and networks from the current node's data
    const serviceCount = topology.graph.nodes.filter(n => n.data?.type === 'service').length;
    const networkCount = topology.graph.nodes.filter(n => n.data?.type === 'network').length;

    return {
      adjacentNodes,
      stats: {
        nodeCount: adjacentNodes.length,
        edgeCount: connectedEdges.length,
        serviceCount,
        networkCount,
      }
    };
  }, [topology, nodeId]);

  if (isLoading) {
    return (
      <div className="grid gap-6 md:grid-cols-2">
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
    );
  }

  if (error || !subgraphData) {
    return (
      <EmptyState
        icon={GitBranch}
        title="No topology data"
        description="Topology data is not available for this node. Generate a topology from the Topology page."
        action={{
          label: 'View Full Topology',
          href: ROUTES.TOPOLOGY,
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Node Connections</h3>
          <p className="text-sm text-muted-foreground">
            Direct connections within the infrastructure topology
          </p>
        </div>
        <Link
          to={ROUTES.TOPOLOGY}
          className="text-sm text-primary hover:underline"
        >
          View full topology
        </Link>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Stats */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Connection Statistics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
              <span className="text-muted-foreground">Connected Nodes</span>
              <span className="font-medium">{subgraphData.stats.nodeCount}</span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
              <span className="text-muted-foreground">Connections</span>
              <span className="font-medium">{subgraphData.stats.edgeCount}</span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
              <span className="text-muted-foreground">Total Services</span>
              <span className="font-medium">{subgraphData.stats.serviceCount}</span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
              <span className="text-muted-foreground">Total Networks</span>
              <span className="font-medium">{subgraphData.stats.networkCount}</span>
            </div>
          </CardContent>
        </Card>

        {/* Connected nodes list */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Adjacent Nodes</CardTitle>
          </CardHeader>
          <CardContent>
            {subgraphData.adjacentNodes.length === 0 ? (
              <p className="text-sm text-muted-foreground">No adjacent nodes found</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {subgraphData.adjacentNodes.slice(0, 10).map((graphNode) => {
                  const NodeIcon = graphNode.data?.class === 'networking'
                    ? Network
                    : graphNode.data?.class === 'iot'
                      ? Cpu
                      : Server;
                  return (
                    <Link
                      key={graphNode.id}
                      to={ROUTES.NODES + '/' + (graphNode.data?.nodeId || graphNode.id)}
                      className="flex items-center gap-2 rounded-lg border p-2 hover:bg-muted/50 transition-colors"
                    >
                      <NodeIcon className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm truncate flex-1">{String(graphNode.data?.label || graphNode.id)}</span>
                      {graphNode.data?.status && (
                        <span
                          className={cn(
                            'h-2 w-2 rounded-full',
                            graphNode.data.status === 'active' ? 'bg-success' : 'bg-muted-foreground'
                          )}
                        />
                      )}
                    </Link>
                  );
                })}
                {subgraphData.adjacentNodes.length > 10 && (
                  <p className="text-xs text-muted-foreground text-center pt-2">
                    +{subgraphData.adjacentNodes.length - 10} more nodes
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
