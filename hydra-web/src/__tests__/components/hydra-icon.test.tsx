import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { HydraIcon } from '@/components/icons/hydra-icon';

describe('HydraIcon', () => {
  it('falls back to a local glyph when a proxied image fails to load', () => {
    const { container } = render(
      <HydraIcon
        icon={{
          source: 'simple-icons',
          slug: 'proxmox',
          label: 'Proxmox',
          url: '/api/v1/icons/simple-icons/proxmox.svg',
          fallback: 'server',
        }}
        fallback="server"
      />,
    );

    const image = screen.getByRole('img', { name: 'Proxmox' });
    fireEvent.error(image);

    expect(screen.queryByRole('img', { name: 'Proxmox' })).not.toBeInTheDocument();
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
