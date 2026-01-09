import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import {
  User,
  Mail,
  Shield,
  Key,
  Clock,
  Save,
  Plus,
  Trash2,
  Copy,
  Check,
  Eye,
  EyeOff,
  AlertTriangle,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth-store';

// Mock personal API tokens
const personalTokens = [
  {
    id: 'pt-001',
    name: 'CLI Access',
    prefix: 'hyd_cli_',
    created_at: '2024-05-01T10:00:00Z',
    last_used: new Date().toISOString(),
    expires_at: '2025-05-01T10:00:00Z',
    scopes: ['read:nodes', 'read:services'],
  },
  {
    id: 'pt-002',
    name: 'VS Code Extension',
    prefix: 'hyd_vsc_',
    created_at: '2024-06-15T08:00:00Z',
    last_used: new Date(Date.now() - 86400000).toISOString(),
    expires_at: null,
    scopes: ['read:all'],
  },
];

// Mock sessions
const activeSessions = [
  {
    id: 'sess-001',
    device: 'Chrome on macOS',
    ip: '192.168.1.100',
    location: 'San Francisco, CA',
    last_active: new Date().toISOString(),
    current: true,
  },
  {
    id: 'sess-002',
    device: 'Firefox on Windows',
    ip: '10.0.0.50',
    location: 'New York, NY',
    last_active: new Date(Date.now() - 3600000).toISOString(),
    current: false,
  },
];

const availableScopes = [
  { id: 'read:nodes', label: 'Read Nodes', description: 'View node information' },
  { id: 'write:nodes', label: 'Write Nodes', description: 'Modify node configuration' },
  { id: 'read:services', label: 'Read Services', description: 'View service information' },
  { id: 'write:services', label: 'Write Services', description: 'Manage services' },
  { id: 'read:networks', label: 'Read Networks', description: 'View network information' },
  { id: 'read:all', label: 'Read All', description: 'Full read access' },
  { id: 'write:all', label: 'Write All', description: 'Full write access' },
];

export default function ProfilePage() {
  const { user } = useAuthStore();
  const [showCreateTokenModal, setShowCreateTokenModal] = useState(false);
  const [showTokenResult, setShowTokenResult] = useState(false);
  const [generatedToken, setGeneratedToken] = useState('');
  const [copiedToken, setCopiedToken] = useState(false);
  const [showToken, setShowToken] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Token creation form state
  const [tokenName, setTokenName] = useState('');
  const [tokenExpiry, setTokenExpiry] = useState('90');
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);

  const handleCreateToken = () => {
    // Simulate token creation
    const newToken = `hyd_${tokenName.toLowerCase().replace(/\s/g, '_')}_${Math.random().toString(36).substring(2, 15)}`;
    setGeneratedToken(newToken);
    setShowCreateTokenModal(false);
    setShowTokenResult(true);
    // Reset form
    setTokenName('');
    setTokenExpiry('90');
    setSelectedScopes([]);
  };

  const copyToken = async (token: string, id?: string) => {
    await navigator.clipboard.writeText(token);
    if (id) {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } else {
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2000);
    }
  };

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Profile</h2>
        <p className="text-sm text-muted-foreground">Manage your account settings and preferences</p>
      </div>

      {/* Two Column Layout for Profile Info and Security */}
      <div className="grid gap-6 xl:grid-cols-2">
        {/* Profile Info Card */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-foreground flex items-center gap-2">
              <User className="h-5 w-5 text-primary" />
              Account Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center gap-6">
              <Avatar className="h-20 w-20">
                <AvatarFallback className="bg-primary text-primary-foreground text-2xl">
                  {user?.username?.charAt(0)?.toUpperCase() || 'A'}
                </AvatarFallback>
              </Avatar>
              <div className="space-y-1">
                <h3 className="text-xl font-semibold text-foreground">
                  {user?.username || 'Admin User'}
                </h3>
                <p className="text-muted-foreground">@{user?.username || 'admin'}</p>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="destructive" className="gap-1">
                    <Shield className="mr-1 h-3 w-3" />
                    {user?.role || 'admin'}
                  </Badge>
                  <Badge variant="outline" className="border-success/30 text-success">
                    Active
                  </Badge>
                </div>
              </div>
            </div>

            <Separator className="bg-border" />

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label className="text-foreground">Username</Label>
                <Input
                  defaultValue={user?.username || 'admin'}
                  disabled
                  className="bg-muted border-border text-muted-foreground"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-foreground">User ID</Label>
                <Input
                  defaultValue={user?.userId || 'usr-001'}
                  disabled
                  className="bg-muted border-border text-muted-foreground font-mono text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-foreground">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    defaultValue={user?.email || 'admin@example.com'}
                    className="bg-background border-border text-foreground pl-9"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-foreground">Member Since</Label>
                <div className="relative">
                  <Clock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    defaultValue={new Date(user?.createdAt || '2024-01-01').toLocaleDateString()}
                    disabled
                    className="bg-muted border-border text-muted-foreground pl-9"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <Button>
                <Save className="mr-2 h-4 w-4" />
                Save Changes
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Security Settings - in same grid row */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-foreground flex items-center gap-2">
              <Shield className="h-5 w-5 text-destructive" />
              Security
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              Manage your security preferences
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-foreground font-medium">Two-factor authentication</p>
                <p className="text-sm text-muted-foreground">Add an extra layer of security to your account</p>
              </div>
              <Button
                variant="outline"
                className="border-border text-foreground bg-transparent hover:bg-muted hover:text-foreground"
              >
                Enable 2FA
              </Button>
            </div>

            <Separator className="bg-border" />

            <div className="space-y-2">
              <Label className="text-foreground">Change Password</Label>
              <div className="space-y-2">
                <Input
                  type="password"
                  placeholder="Current password"
                  className="bg-background border-border text-foreground"
                />
                <Input
                  type="password"
                  placeholder="New password"
                  className="bg-background border-border text-foreground"
                />
              </div>
              <Button
                variant="outline"
                className="border-border text-foreground bg-transparent hover:bg-muted hover:text-foreground mt-2"
              >
                Update Password
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Full Width Section - API Tokens & Sessions */}
      <div className="grid gap-6 xl:grid-cols-2">
        {/* Personal API Tokens */}
        <Card className="bg-card border-border overflow-hidden xl:col-span-2">
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <CardTitle className="text-foreground flex items-center gap-2">
                <Key className="h-5 w-5 text-warning" />
                Personal API Tokens
              </CardTitle>
              <CardDescription className="text-muted-foreground">
                Tokens for personal CLI and integration use
              </CardDescription>
            </div>
            <Button onClick={() => setShowCreateTokenModal(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Token
            </Button>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="text-muted-foreground">Name</TableHead>
                    <TableHead className="text-muted-foreground">Token</TableHead>
                    <TableHead className="text-muted-foreground">Last Used</TableHead>
                    <TableHead className="text-muted-foreground">Expires</TableHead>
                    <TableHead className="text-muted-foreground w-[80px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {personalTokens.map((token) => (
                    <TableRow key={token.id} className="border-border hover:bg-muted/60">
                      <TableCell className="text-foreground font-medium">{token.name}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <code className="text-muted-foreground text-sm">
                            {showToken === token.id
                              ? `${token.prefix}••••••••••••`
                              : `${token.prefix}••••••`}
                          </code>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 text-muted-foreground hover:text-foreground"
                            onClick={() => setShowToken(showToken === token.id ? null : token.id)}
                          >
                            {showToken === token.id ? (
                              <EyeOff className="h-3 w-3" />
                            ) : (
                              <Eye className="h-3 w-3" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 text-muted-foreground hover:text-foreground"
                            onClick={() => copyToken(`${token.prefix}secret-value`, token.id)}
                          >
                            {copiedId === token.id ? (
                              <Check className="h-3 w-3 text-success" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
                        {new Date(token.last_used).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        {token.expires_at ? (
                          <span className="text-muted-foreground text-sm whitespace-nowrap">
                            {new Date(token.expires_at).toLocaleDateString()}
                          </span>
                        ) : (
                          <Badge variant="outline" className="border-border text-muted-foreground">
                            Never
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
        </CardContent>
        </Card>

        {/* Active Sessions */}
        <Card className="bg-card border-border xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-foreground flex items-center gap-2">
              <Clock className="h-5 w-5 text-info" />
              Active Sessions
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              Devices where you're currently logged in
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {activeSessions.map((session) => (
              <div
                key={session.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-lg bg-muted/60"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-foreground font-medium">{session.device}</p>
                    {session.current && (
                      <Badge className="bg-success/10 text-success border-success/20">
                        Current
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {session.ip} • {session.location}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Last active: {new Date(session.last_active).toLocaleString()}
                  </p>
                </div>
                {!session.current && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-destructive/30 text-destructive bg-transparent hover:bg-destructive/10 hover:text-destructive shrink-0"
                  >
                    Revoke
                  </Button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Create Token Modal */}
      <Dialog open={showCreateTokenModal} onOpenChange={setShowCreateTokenModal}>
        <DialogContent className="bg-popover border-border text-foreground max-w-lg">
          <DialogHeader>
            <DialogTitle>Create Personal API Token</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Generate a new token for CLI access or integrations.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="tokenName" className="text-foreground">
                Token Name
              </Label>
              <Input
                id="tokenName"
                placeholder="e.g., CLI Access"
                value={tokenName}
                onChange={(e) => setTokenName(e.target.value)}
                className="bg-background border-border text-foreground"
              />
            </div>

            <div className="space-y-2">
              <Label className="text-foreground">Expiration</Label>
              <Select value={tokenExpiry} onValueChange={setTokenExpiry}>
                <SelectTrigger className="bg-background border-border text-foreground">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover border-border">
                  <SelectItem value="30">30 days</SelectItem>
                  <SelectItem value="90">90 days</SelectItem>
                  <SelectItem value="365">1 year</SelectItem>
                  <SelectItem value="never">No expiration</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-foreground">Scopes</Label>
              <div className="grid grid-cols-2 gap-2 p-3 rounded-lg bg-muted/60 max-h-[200px] overflow-y-auto">
                {availableScopes.map((scope) => (
                  <label
                    key={scope.id}
                    className="flex items-start gap-2 cursor-pointer p-2 rounded hover:bg-muted/60"
                  >
                    <Checkbox
                      checked={selectedScopes.includes(scope.id)}
                      onCheckedChange={() => toggleScope(scope.id)}
                      className="mt-0.5 border-border data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                    />
                    <div>
                      <p className="text-sm text-foreground">{scope.label}</p>
                      <p className="text-xs text-muted-foreground">{scope.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCreateTokenModal(false)}
              className="border-border text-foreground hover:bg-muted bg-transparent"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateToken}
              disabled={!tokenName || selectedScopes.length === 0}
            >
              <Key className="mr-2 h-4 w-4" />
              Generate Token
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Token Result Modal */}
      <Dialog open={showTokenResult} onOpenChange={setShowTokenResult}>
        <DialogContent className="bg-popover border-border text-foreground max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Check className="h-5 w-5 text-success" />
              Token Created Successfully
            </DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Copy your token now. You won't be able to see it again.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <div className="p-4 rounded-lg bg-muted/60 border border-border">
              <div className="flex items-center justify-between gap-2">
                <code className="text-success text-sm break-all">{generatedToken}</code>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-foreground shrink-0"
                  onClick={() => copyToken(generatedToken)}
                >
                  {copiedToken ? (
                    <Check className="h-4 w-4 text-success" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <div className="flex items-start gap-2 mt-4 p-3 rounded-lg bg-warning/10 border border-warning/20">
              <AlertTriangle className="h-5 w-5 text-warning shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-warning font-medium">Important</p>
                <p className="text-xs text-warning/80">
                  Make sure to copy your token now. For security reasons, it won't be shown again.
                </p>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={() => setShowTokenResult(false)}
              className="w-full"
            >
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
