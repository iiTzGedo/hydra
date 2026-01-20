import { Link } from 'react-router-dom';
import { Terminal, Globe, Store } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { MCPServer } from '@/types/mcp';
import { ROUTES } from '@/lib/constants';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface MCPConfigModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  servers: MCPServer[];
  onConnectServer: (serverId: string) => void;
  onDisconnectServer: (serverId: string) => void;
}

export function MCPConfigModal({
  open,
  onOpenChange,
  servers,
  onConnectServer,
  onDisconnectServer,
}: MCPConfigModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border text-foreground max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>MCP Configuration</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Manage connected MCP servers and browse available tools.
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="flex-1 -mx-6 px-6">
          <div className="space-y-4 py-4">
            {servers.map((mcp) => (
              <Card key={mcp.id} className="bg-muted/60 border-border">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-card">
                        {mcp.type === 'builtin' ? (
                          <Terminal className="h-5 w-5 text-violet-500" />
                        ) : (
                          <Globe className="h-5 w-5 text-cyan-500" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-foreground">{mcp.name}</h4>
                          <Badge
                            variant="outline"
                            className={cn(
                              mcp.status === 'connected'
                                ? 'border-emerald-500/30 text-emerald-400'
                                : 'border-border text-muted-foreground'
                            )}
                          >
                            {mcp.status}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">{(mcp.tools || []).length} tools</p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        mcp.status === 'connected'
                          ? onDisconnectServer(mcp.id)
                          : onConnectServer(mcp.id)
                      }
                      className={cn(
                        mcp.status === 'connected'
                          ? 'text-red-400 hover:text-red-300 hover:bg-red-500/10'
                          : 'text-blue-400 hover:text-blue-300 hover:bg-blue-500/10'
                      )}
                    >
                      {mcp.status === 'connected' ? 'Disconnect' : 'Connect'}
                    </Button>
                  </div>
                  {(mcp.tools || []).length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {(mcp.tools || []).slice(0, 8).map((tool) => (
                        <Badge
                          key={typeof tool === 'string' ? tool : tool.name}
                          variant="secondary"
                          className="text-[10px] bg-card text-muted-foreground"
                        >
                          {typeof tool === 'string' ? tool : tool.name}
                        </Badge>
                      ))}
                      {(mcp.tools || []).length > 8 && (
                        <Badge variant="secondary" className="text-[10px] bg-card text-muted-foreground">
                          +{(mcp.tools || []).length - 8} more
                        </Badge>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
        <DialogFooter className="border-t border-border pt-4">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-border text-foreground hover:bg-muted bg-transparent"
          >
            Close
          </Button>
          <Link to={ROUTES.MCP_MARKETPLACE}>
            <Button className="bg-blue-600 hover:bg-blue-700 text-white">
              <Store className="h-4 w-4 mr-2" />
              Browse Marketplace
            </Button>
          </Link>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
