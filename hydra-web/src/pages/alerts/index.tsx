import { useState } from 'react';
import { format } from 'date-fns';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  Search,
  Bell,
  BellOff,
  Clock,
  Server,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

// Mock alerts data - in production this would come from API
const alerts = [
  {
    id: 'alert-1',
    severity: 'critical',
    title: 'High CPU Usage',
    message: 'CPU usage exceeded 95% on web-server-01',
    nodeId: 'node-1',
    nodeName: 'web-server-01',
    timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    acknowledged: false,
  },
  {
    id: 'alert-2',
    severity: 'warning',
    title: 'Memory Pressure',
    message: 'Memory usage at 87% on db-primary',
    nodeId: 'node-2',
    nodeName: 'db-primary',
    timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    acknowledged: false,
  },
  {
    id: 'alert-3',
    severity: 'warning',
    title: 'Disk Space Low',
    message: 'Disk usage at 82% on storage-nas-01',
    nodeId: 'node-6',
    nodeName: 'storage-nas-01',
    timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    acknowledged: true,
  },
  {
    id: 'alert-4',
    severity: 'info',
    title: 'Service Restarted',
    message: 'nginx service restarted on web-server-02',
    nodeId: 'node-4',
    nodeName: 'web-server-02',
    timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    acknowledged: true,
  },
  {
    id: 'alert-5',
    severity: 'critical',
    title: 'Node Offline',
    message: 'Lost connection to edge-sensor-03',
    nodeId: 'node-8',
    nodeName: 'edge-sensor-03',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    acknowledged: false,
  },
];

const severityConfig = {
  critical: {
    icon: AlertCircle,
    color: 'text-destructive',
    bg: 'bg-destructive/10',
    border: 'border-destructive/20',
  },
  warning: {
    icon: AlertTriangle,
    color: 'text-warning',
    bg: 'bg-warning/10',
    border: 'border-warning/20',
  },
  info: {
    icon: Info,
    color: 'text-info',
    bg: 'bg-info/10',
    border: 'border-info/20',
  },
  success: {
    icon: CheckCircle,
    color: 'text-success',
    bg: 'bg-success/10',
    border: 'border-success/20',
  },
};

export default function AlertsPage() {
  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  const filteredAlerts = alerts.filter((alert) => {
    const matchesSearch =
      alert.title.toLowerCase().includes(search.toLowerCase()) ||
      alert.message.toLowerCase().includes(search.toLowerCase()) ||
      alert.nodeName.toLowerCase().includes(search.toLowerCase());
    const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter;
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'active' && !alert.acknowledged) ||
      (statusFilter === 'acknowledged' && alert.acknowledged);
    return matchesSearch && matchesSeverity && matchesStatus;
  });

  const activeCount = alerts.filter((a) => !a.acknowledged).length;
  const criticalCount = alerts.filter((a) => a.severity === 'critical' && !a.acknowledged).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Notifications</h2>
          <p className="text-sm text-muted-foreground">
            {activeCount} active alerts, {criticalCount} critical
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
          >
            <BellOff className="mr-2 h-4 w-4" />
            Acknowledge All
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <Card className="bg-destructive/10 border-destructive/20">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <div>
              <p className="text-2xl font-bold text-foreground">
                {alerts.filter((a) => a.severity === 'critical').length}
              </p>
              <p className="text-sm text-muted-foreground">Critical</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-warning/10 border-warning/20">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertTriangle className="h-8 w-8 text-warning" />
            <div>
              <p className="text-2xl font-bold text-foreground">
                {alerts.filter((a) => a.severity === 'warning').length}
              </p>
              <p className="text-sm text-muted-foreground">Warning</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-info/10 border-info/20">
          <CardContent className="p-4 flex items-center gap-4">
            <Info className="h-8 w-8 text-info" />
            <div>
              <p className="text-2xl font-bold text-foreground">
                {alerts.filter((a) => a.severity === 'info').length}
              </p>
              <p className="text-sm text-muted-foreground">Info</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-muted/60 border-border">
          <CardContent className="p-4 flex items-center gap-4">
            <CheckCircle className="h-8 w-8 text-success" />
            <div>
              <p className="text-2xl font-bold text-foreground">
                {alerts.filter((a) => a.acknowledged).length}
              </p>
              <p className="text-sm text-muted-foreground">Acknowledged</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="text-foreground">History</CardTitle>
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search alerts..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9 bg-background w-full sm:w-64"
                />
              </div>
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="w-full sm:w-32">
                  <SelectValue placeholder="Severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-36">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="acknowledged">Acknowledged</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-border">
            {filteredAlerts.map((alert) => {
              const config = severityConfig[alert.severity as keyof typeof severityConfig];
              const Icon = config.icon;
              return (
                <div
                  key={alert.id}
                  className={cn(
                    'p-4 flex items-start gap-4 hover:bg-muted/60 transition-colors',
                    alert.acknowledged && 'opacity-60'
                  )}
                >
                  <div className={cn('p-2 rounded-lg', config.bg)}>
                    <Icon className={cn('h-5 w-5', config.color)} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-medium text-foreground">{alert.title}</p>
                        <p className="text-sm text-muted-foreground mt-0.5">{alert.message}</p>
                        <div className="flex items-center gap-3 mt-2">
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Server className="h-3 w-3" />
                            {alert.nodeName}
                          </div>
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Clock className="h-3 w-3" />
                            {format(new Date(alert.timestamp), 'MMM d, HH:mm')}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {alert.acknowledged ? (
                          <Badge variant="outline" className="border-border text-muted-foreground">
                            Acknowledged
                          </Badge>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                          >
                            <Bell className="h-3 w-3 mr-1" />
                            Acknowledge
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
            {filteredAlerts.length === 0 && (
              <div className="p-12 text-center">
                <CheckCircle className="h-12 w-12 text-success mx-auto mb-4" />
                <p className="text-muted-foreground">No alerts match your filters</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
