import { useState } from 'react';
import { Key, Fingerprint } from 'lucide-react';
import { cn } from '@/lib/utils';
import { RegistrationTokens } from './registration-tokens';
import { ApiKeysSection } from './api-keys-section';

export function SecretsSection() {
  const [secretsTab, setSecretsTab] = useState<'tokens' | 'apikeys'>('tokens');

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 border-b border-border">
        <button
          onClick={() => setSecretsTab('tokens')}
          className={cn(
            'pb-3 text-sm font-medium transition-colors border-b-2 -mb-px',
            secretsTab === 'tokens'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <Key className="h-4 w-4 inline mr-2" />
          Registration Tokens
        </button>
        <button
          onClick={() => setSecretsTab('apikeys')}
          className={cn(
            'pb-3 text-sm font-medium transition-colors border-b-2 -mb-px',
            secretsTab === 'apikeys'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <Fingerprint className="h-4 w-4 inline mr-2" />
          API Keys
        </button>
      </div>

      {secretsTab === 'tokens' && <RegistrationTokens />}
      {secretsTab === 'apikeys' && <ApiKeysSection />}
    </div>
  );
}
