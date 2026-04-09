import { useState } from 'react';
import {
  Activity,
  Link2,
  List,
  Route,
  Settings2,
} from 'lucide-react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PluginRegistry } from './components/plugin-registry';
import { PluginConfig } from './components/plugin-config';
import { PluginHealth } from './components/plugin-health';
import { PluginNodeBindings } from './components/plugin-node-bindings';
import { PluginCommandRouting } from './components/plugin-command-routing';

export default function IntegrationsPage() {
  useDocumentTitle('Integrations');
  const [activeTab, setActiveTab] = useState('registry');

  return (
    <div className="space-y-6">
      <PageHeaderLayout
        title="Integrations"
        subtitle="Manage plugins, configure connections, and monitor integration health"
        showBackButton={false}
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="registry">
            <List className="h-4 w-4 mr-1.5" />
            Registry
          </TabsTrigger>
          <TabsTrigger value="config">
            <Settings2 className="h-4 w-4 mr-1.5" />
            Configuration
          </TabsTrigger>
          <TabsTrigger value="health">
            <Activity className="h-4 w-4 mr-1.5" />
            Health
          </TabsTrigger>
          <TabsTrigger value="bindings">
            <Link2 className="h-4 w-4 mr-1.5" />
            Node Bindings
          </TabsTrigger>
          <TabsTrigger value="routing">
            <Route className="h-4 w-4 mr-1.5" />
            Command Routing
          </TabsTrigger>
        </TabsList>

        <TabsContent value="registry">
          <PluginRegistry />
        </TabsContent>

        <TabsContent value="config">
          <PluginConfig />
        </TabsContent>

        <TabsContent value="health">
          <PluginHealth />
        </TabsContent>

        <TabsContent value="bindings">
          <PluginNodeBindings />
        </TabsContent>

        <TabsContent value="routing">
          <PluginCommandRouting />
        </TabsContent>
      </Tabs>
    </div>
  );
}
