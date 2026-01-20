import { useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import {
  Server,
  Network,
  Cpu,
  ArrowLeft,
  Edit,
  Archive,
  RefreshCw,
  Info,
  Boxes,
  GitBranch,
  Globe,
  FolderTree,
  FileText,
} from 'lucide-react';
import { useNode } from '@/api/nodes';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, NODE_CLASS_COLORS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  OverviewTab,
  ProfileTab,
  ServicesTab,
  TopologyTab,
  NetworksTab,
  GroupsTab,
} from './tabs';

const classIcons = {
  compute: Server,
  networking: Network,
  iot: Cpu,
};

const tabs = [
  { id: 'overview', label: 'Overview', icon: Info },
  { id: 'profile', label: 'Profile', icon: FileText },
  { id: 'services', label: 'Services', icon: Boxes },
  { id: 'topology', label: 'Topology', icon: GitBranch },
  { id: 'networks', label: 'Networks', icon: Globe },
  { id: 'groups', label: 'Groups', icon: FolderTree },
];

export default function NodeDetailPage() {
  const { nodeId } = useParams<{ nodeId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') || 'overview';
  const [activeTab, setActiveTab] = useState(initialTab);

  const { data: node, isLoading, error } = useNode(nodeId!);

  useDocumentTitle(node ? `${node.displayName || node.id} - Node` : 'Node Details');

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    setSearchParams({ tab: value });
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <Skeleton className="h-8 w-48 mb-6" />
        <div className="space-y-6">
          <Skeleton className="h-32" />
          <Skeleton className="h-12" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (error || !node) {
    return (
      <div className="p-6">
        <Link
          to={ROUTES.NODES}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Nodes
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <Server className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Node not found</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            The node "{nodeId}" could not be found
          </p>
        </div>
      </div>
    );
  }

  const Icon = classIcons[node.class] || Server;
  const colors = NODE_CLASS_COLORS[node.class];

  return (
    <div className="p-6">
      <Link
        to={ROUTES.NODES}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Nodes
      </Link>

      <PageHeader
        title={node.displayName || node.id}
        description={`${node.class} node - ${node.type}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" asChild>
              <Link to={ROUTES.NODES + '/' + node.id + '/profiles'}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Profiles
              </Link>
            </Button>
            <Button variant="outline">
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </Button>
            <Button variant="outline" className="text-destructive hover:text-destructive">
              <Archive className="mr-2 h-4 w-4" />
              Archive
            </Button>
          </div>
        }
      />

      <Tabs value={activeTab} onValueChange={handleTabChange} className="mt-6">
        <TabsList className="bg-card border border-border p-1 h-auto flex-wrap">
          {tabs.map((tab) => {
            const TabIcon = tab.icon;
            return (
              <TabsTrigger
                key={tab.id}
                value={tab.id}
                className="data-[state=active]:bg-muted data-[state=active]:text-foreground text-muted-foreground px-4 py-2 text-sm"
              >
                <TabIcon className="h-4 w-4 mr-2" />
                {tab.label}
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <OverviewTab node={node} />
        </TabsContent>

        <TabsContent value="profile" className="mt-6">
          <ProfileTab nodeId={nodeId!} />
        </TabsContent>

        <TabsContent value="services" className="mt-6">
          <ServicesTab nodeId={nodeId!} />
        </TabsContent>

        <TabsContent value="topology" className="mt-6">
          <TopologyTab nodeId={nodeId!} />
        </TabsContent>

        <TabsContent value="networks" className="mt-6">
          <NetworksTab node={node} />
        </TabsContent>

        <TabsContent value="groups" className="mt-6">
          <GroupsTab node={node} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
