import type { CommandCategory, CommandType } from '@/api/commands';
import type { IconDescriptor } from '@/types/icons';

/**
 * Derive an integration / plugin slug from a command registryId.
 *
 * Command registry IDs follow the convention `<namespace>::<category>::<action>`
 * where namespace is either a core category (service, node, agent) or a plugin
 * slug (ansible, docker, proxmox, home-assistant, …). When the namespace is a
 * core category the inner segments may still carry the plugin (e.g.
 * `reg::docker::container::restart`), so the resolver checks every segment.
 *
 * Returns `null` when no known integration slug can be extracted — callers
 * should then fall back to the category icon.
 */
const KNOWN_INTEGRATION_SLUGS = new Set<string>([
  'ansible',
  'docker',
  'podman',
  'proxmox',
  'home-assistant',
  'homeassistant',
  'ha',
  'prometheus',
  'grafana',
  'terraform',
  'kubernetes',
  'kubernetes-pod',
  'k8s',
  'ssh',
  'github',
  'gitlab',
  'git',
  'gitea',
  'systemd',
  'lxc',
  'containerd',
  'postgres',
  'postgresql',
  'mysql',
  'mongodb',
  'redis',
  'sqlite',
  'nginx',
  'apache',
  'caddy',
  'traefik',
]);

const CORE_NAMESPACES = new Set<string>(['reg', 'service', 'node', 'agent']);

export function extractIntegrationSlug(registryId: string | null | undefined): string | null {
  if (!registryId) return null;
  const parts = registryId.toLowerCase().split('::').filter(Boolean);
  for (const part of parts) {
    if (CORE_NAMESPACES.has(part)) continue;
    if (KNOWN_INTEGRATION_SLUGS.has(part)) return part;
  }
  return null;
}

/**
 * Resolve an IconDescriptor for a command based on (in order):
 *
 *   1. an explicit integration slug (from registryId)
 *   2. the command type (package, config, system, custom, metadata)
 *   3. the command category (service, node, agent)
 *
 * The descriptor is consumed by <HydraIcon>, which resolves the slug via
 * LUCIDE_FALLBACKS. This keeps command icon selection co-located with the
 * existing icon system rather than introducing a parallel lookup.
 */
export function getCommandIconDescriptor(opts: {
  registryId?: string | null;
  category?: CommandCategory | null;
  type?: CommandType | null;
}): IconDescriptor {
  const integration = extractIntegrationSlug(opts.registryId);
  if (integration) {
    return {
      source: 'fallback',
      slug: integration,
      label: integration.replace(/-/g, ' '),
    };
  }

  // Type takes precedence over category when it encodes more-specific intent
  // (e.g. type=package while category=service should still render a package).
  if (opts.type && opts.type !== 'service' && opts.type !== 'node' && opts.type !== 'agent') {
    return { source: 'fallback', slug: opts.type, label: opts.type };
  }

  if (opts.category) {
    return { source: 'fallback', slug: opts.category, label: opts.category };
  }

  return { source: 'fallback', slug: 'terminal', label: 'command' };
}

/**
 * Map a command category to a design-system command-kind token. Workflows
 * and non-category commands resolve to the generic `custom` kind so the rail/
 * chip colour remains stable.
 */
export function categoryToCommandKind(
  category: CommandCategory | null | undefined,
  type?: CommandType | null,
): 'service' | 'node' | 'agent' | 'metadata' | 'package' | 'config' | 'system' | 'custom' | 'workflow' {
  if (type === 'package') return 'package';
  if (type === 'config') return 'config';
  if (type === 'system') return 'system';
  if (type === 'metadata') return 'metadata';
  if (type === 'custom') return 'custom';
  if (category === 'service') return 'service';
  if (category === 'node') return 'node';
  if (category === 'agent') return 'agent';
  return 'custom';
}
