import { format } from 'date-fns';
import {
  AlertTriangle,
  Check,
  CheckCircle,
  Clock,
  ExternalLink,
  Info,
  Server,
  ShieldAlert,
  Trash2,
  User,
  XCircle,
} from 'lucide-react';
import { useRouter } from 'next/navigation';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import type { Notification, NotificationTier } from '@/types/notification';
import { ACKNOWLEDGE_MIN_TIER, RESOLVE_MIN_TIER, TIER_COLORS } from '@/types/notification';

const tierIcons: Record<NotificationTier, React.ElementType> = {
  1: Info,
  2: CheckCircle,
  3: AlertTriangle,
  4: ShieldAlert,
  5: XCircle,
};

interface NotificationDetailsModalProps {
  notification: Notification | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAcknowledge?: (id: string) => void;
  onResolve?: (id: string) => void;
  onDelete?: (id: string) => void;
  canWrite?: boolean;
}

function formatTimestamp(ts: string | null | undefined): string {
  if (!ts) return '-';
  return format(new Date(ts), 'MMM d, yyyy HH:mm:ss');
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className="text-xs font-medium text-muted-foreground w-28 flex-shrink-0">{label}</span>
      <span className="text-sm text-foreground min-w-0 break-all">{children}</span>
    </div>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mt-4 mb-1.5 border-b border-border/50 pb-1">
      {children}
    </h4>
  );
}

export function NotificationDetailsModal({
  notification,
  open,
  onOpenChange,
  onAcknowledge,
  onResolve,
  onDelete,
  canWrite = true,
}: NotificationDetailsModalProps) {
  const router = useRouter();

  if (!notification) return null;

  const tier = notification.tier as NotificationTier;
  const colors = TIER_COLORS[tier];
  const Icon = tierIcons[tier];
  const isActive = notification.status === 'active';
  const canAcknowledge = canWrite && isActive && !notification.acknowledgedAt && tier >= ACKNOWLEDGE_MIN_TIER;
  const canResolve = canWrite && isActive && tier >= RESOLVE_MIN_TIER;
  const primaryLink = notification.links?.[0];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[80vh] overflow-hidden flex flex-col bg-card border-border text-foreground">
        <DialogHeader className="flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className={cn('rounded-full p-2', colors.bg)}>
              <Icon className={cn('h-5 w-5', colors.text)} />
            </div>
            <div className="flex-1 min-w-0">
              <DialogTitle className="text-base leading-tight">{notification.title}</DialogTitle>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className={cn('text-[10px] px-1.5 py-0', colors.bg, colors.text, colors.border)}>
                  {colors.label}
                </Badge>
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                  {notification.status}
                </Badge>
                {notification.acknowledgedAt && notification.status === 'active' && (
                  <span className="flex items-center gap-1 text-xs text-success">
                    <Check className="h-3 w-3" />
                    Acknowledged
                  </span>
                )}
              </div>
            </div>
          </div>
        </DialogHeader>

        <ScrollArea className="flex-1 -mx-6 px-6">
          <div className="space-y-0.5 pb-4">
            {/* Message */}
            <SectionHeader>Message</SectionHeader>
            <p className="text-sm text-foreground/90 whitespace-pre-wrap">{notification.message}</p>

            {/* Source */}
            <SectionHeader>Source</SectionHeader>
            <DetailRow label="Component">
              <span className="flex items-center gap-1.5">
                <Server className="h-3.5 w-3.5 text-muted-foreground" />
                {notification.source.component}
              </span>
            </DetailRow>
            {notification.source.service && (
              <DetailRow label="Service">{notification.source.service}</DetailRow>
            )}
            {notification.source.nodeId && (
              <DetailRow label="Node ID">{notification.source.nodeId}</DetailRow>
            )}
            {notification.source.serviceId && (
              <DetailRow label="Service ID">{notification.source.serviceId}</DetailRow>
            )}

            {/* Actor */}
            {notification.actor && (
              <>
                <SectionHeader>Actor</SectionHeader>
                <DetailRow label="Type">
                  <span className="flex items-center gap-1.5">
                    <User className="h-3.5 w-3.5 text-muted-foreground" />
                    {notification.actor.type}
                  </span>
                </DetailRow>
                <DetailRow label="ID">{notification.actor.id}</DetailRow>
                {notification.actor.ip && (
                  <DetailRow label="IP">{notification.actor.ip}</DetailRow>
                )}
              </>
            )}

            {/* Event / Occurrences */}
            {notification.event && (
              <>
                <SectionHeader>Event</SectionHeader>
                <DetailRow label="First seen">{formatTimestamp(notification.event.firstSeenAt)}</DetailRow>
                <DetailRow label="Last seen">{formatTimestamp(notification.event.lastSeenAt)}</DetailRow>
                <DetailRow label="Occurrences">
                  <Badge variant="outline" className="text-xs">
                    {notification.event.occurrenceCount}x
                  </Badge>
                </DetailRow>
              </>
            )}

            {/* Details (arbitrary metadata) */}
            {notification.details && Object.keys(notification.details).length > 0 && (
              <>
                <SectionHeader>Details</SectionHeader>
                {Object.entries(notification.details).map(([key, value]) => (
                  <DetailRow key={key} label={key}>
                    {typeof value === 'object' ? JSON.stringify(value) : String(value ?? '-')}
                  </DetailRow>
                ))}
              </>
            )}

            {/* Links */}
            {notification.links && notification.links.length > 0 && (
              <>
                <SectionHeader>Links</SectionHeader>
                <div className="flex flex-wrap gap-2 mt-1">
                  {notification.links.map((link, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => {
                        if (link.href.startsWith('/') && !link.href.startsWith('//')) {
                          router.push(link.href);
                        }
                        onOpenChange(false);
                      }}
                    >
                      <ExternalLink className="mr-1 h-3 w-3" />
                      {link.label}
                    </Button>
                  ))}
                </div>
              </>
            )}

            {/* Timestamps */}
            <SectionHeader>Timestamps</SectionHeader>
            <DetailRow label="Created">
              <span className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                {formatTimestamp(notification.createdAt)}
              </span>
            </DetailRow>
            {notification.acknowledgedAt && (
              <DetailRow label="Acknowledged">
                {formatTimestamp(notification.acknowledgedAt)}
                {notification.acknowledgedBy && (
                  <span className="text-muted-foreground ml-1">by {notification.acknowledgedBy}</span>
                )}
              </DetailRow>
            )}
            {notification.resolvedAt && (
              <DetailRow label="Resolved">
                {formatTimestamp(notification.resolvedAt)}
                {notification.resolvedBy && (
                  <span className="text-muted-foreground ml-1">by {notification.resolvedBy}</span>
                )}
              </DetailRow>
            )}
            {notification.expiresAt && (
              <DetailRow label="Expires">{formatTimestamp(notification.expiresAt)}</DetailRow>
            )}

            {/* Metadata */}
            <SectionHeader>Metadata</SectionHeader>
            <DetailRow label="Notification ID">
              <code className="text-xs bg-muted px-1 py-0.5 rounded">{notification.notificationId}</code>
            </DetailRow>
            <DetailRow label="Type">
              <code className="text-xs bg-muted px-1 py-0.5 rounded">{notification.type}</code>
            </DetailRow>
            <DetailRow label="Group Key">
              <code className="text-xs bg-muted px-1 py-0.5 rounded">{notification.groupKey}</code>
            </DetailRow>
            {notification.correlationId && (
              <DetailRow label="Correlation ID">
                <code className="text-xs bg-muted px-1 py-0.5 rounded">{notification.correlationId}</code>
              </DetailRow>
            )}
            {notification.auditEntryId && (
              <DetailRow label="Audit Entry">
                <code className="text-xs bg-muted px-1 py-0.5 rounded">{notification.auditEntryId}</code>
              </DetailRow>
            )}
          </div>
        </ScrollArea>

        <DialogFooter className="flex-shrink-0 gap-2 sm:gap-2">
          {onDelete && (
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive mr-auto"
              onClick={() => {
                onDelete(notification.notificationId);
                onOpenChange(false);
              }}
            >
              <Trash2 className="mr-1.5 h-3.5 w-3.5" />
              Delete
            </Button>
          )}
          {primaryLink && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (primaryLink.href.startsWith('/') && !primaryLink.href.startsWith('//')) {
                  router.push(primaryLink.href);
                }
                onOpenChange(false);
              }}
            >
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
              {primaryLink.label}
            </Button>
          )}
          {canAcknowledge && onAcknowledge && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                onAcknowledge(notification.notificationId);
                onOpenChange(false);
              }}
            >
              <Check className="mr-1.5 h-3.5 w-3.5" />
              Acknowledge
            </Button>
          )}
          {canResolve && onResolve && (
            <Button
              size="sm"
              onClick={() => {
                onResolve(notification.notificationId);
                onOpenChange(false);
              }}
            >
              <CheckCircle className="mr-1.5 h-3.5 w-3.5" />
              Resolve
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
