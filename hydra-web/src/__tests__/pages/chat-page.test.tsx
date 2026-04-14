import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatPage from '@/views/chat';
import { renderWithRoute } from '../page-test-utils';

const mockUseChatOrchestration = vi.fn();

const ANTHROPIC_PROVIDER = {
  configId: 'llm-anthropic',
  name: 'Anthropic Primary',
  type: 'anthropic',
  apiKeySet: true,
  model: 'claude-3-5-sonnet',
  isDefault: true,
  createdBy: 'user-001',
  createdAt: '2026-03-09T12:00:00Z',
  updatedAt: '2026-03-09T12:00:00Z',
} as const;

const OLLAMA_PROVIDER = {
  configId: 'llm-ollama',
  name: 'Local Ollama',
  type: 'ollama',
  apiKeySet: false,
  model: 'llama3.1',
  isDefault: false,
  createdBy: 'user-001',
  createdAt: '2026-03-09T12:00:00Z',
  updatedAt: '2026-03-09T12:00:00Z',
} as const;

vi.mock('@/views/chat/hooks/use-chat-orchestration', () => ({
  useChatOrchestration: () => mockUseChatOrchestration(),
}));

function createChatState(overrides: Record<string, unknown> = {}) {
  return {
    projects: [],
    standaloneSessions: [],
    sessions: [],
    currentSessionId: null,
    currentSession: null,
    modelConfig: {},
    setModelConfig: vi.fn(),
    reasoningLevel: 'medium',
    setReasoningLevel: vi.fn(),
    webSearchEnabled: false,
    setWebSearchEnabled: vi.fn(),
    supportsReasoning: true,
    supportsWebSearch: false,
    isStreaming: false,
    sessionUsage: null,
    sessionContext: null,
    activeLLMProvider: ANTHROPIC_PROVIDER,
    activeLLMProviderId: 'llm-anthropic',
    llmProviders: [ANTHROPIC_PROVIDER],
    activeTools: [],
    activePrompts: [],
    hydraMcpHealth: null,
    hydraMcpTools: [],
    hydraMcpPrompts: [],
    isHydraMcpInSession: false,
    isHydraMcpHealthy: true,
    serversWithTools: [],
    infraContext: {
      nodes: 2,
      services: 3,
      networks: 1,
      notifications: 0,
    },
    input: 'Need LLM config',
    setInput: vi.fn(),
    handleSend: vi.fn().mockResolvedValue({ needsLLMConfig: false }),
    handleSelectSession: vi.fn(),
    handleNewChat: vi.fn(),
    handleCreateProject: vi.fn(),
    handleRenameSession: vi.fn(),
    handleMoveSessionToProject: vi.fn(),
    handleDuplicateSession: vi.fn(),
    handleExportSession: vi.fn(),
    handleDeleteSession: vi.fn(),
    handleRenameProject: vi.fn(),
    handleDeleteProject: vi.fn(),
    handleConnectServer: vi.fn(),
    handleDisconnectServer: vi.fn(),
    handleSetActiveProvider: vi.fn(),
    handleUpdateProvider: vi.fn(),
    handleCreateProvider: vi.fn(),
    handleDeleteProvider: vi.fn(),
    handleValidateProvider: vi.fn(),
    allMessages: [],
    streamingContent: '',
    retryMessage: vi.fn(),
    messagesEndRef: { current: null },
    llmConfigLocked: false,
    ...overrides,
  };
}

describe('Chat Page Integration', () => {
  beforeEach(() => {
    mockUseChatOrchestration.mockReset();
  });

  it('renders the disconnected Hydra MCP banner and toggles the mobile sidebar button label', async () => {
    const user = userEvent.setup();
    mockUseChatOrchestration.mockReturnValue(createChatState());

    renderWithRoute(<ChatPage />, {
      path: '/chat',
      route: '/chat',
    });

    expect(
      await screen.findByText(/access infrastructure tools/i, {
        selector: 'span',
      })
    ).toBeInTheDocument();

    const toggle = screen.getByRole('button', { name: 'Open sidebar' });
    await act(async () => {
      await user.click(toggle);
    });
    expect(screen.getByRole('button', { name: 'Close sidebar' })).toBeInTheDocument();
  });

  it('renders the unhealthy Hydra MCP banner when the server is unreachable', async () => {
    mockUseChatOrchestration.mockReturnValue(
      createChatState({
        isHydraMcpInSession: true,
        isHydraMcpHealthy: false,
      })
    );

    renderWithRoute(<ChatPage />, {
      path: '/chat',
      route: '/chat',
    });

    expect(
      await screen.findByText(/check if the hydra-mcp service is running/i, {
        selector: 'span',
      })
    ).toBeInTheDocument();
  });

  it('opens the LLM configuration modal when sending requires configuration', async () => {
    const user = userEvent.setup();
    mockUseChatOrchestration.mockReturnValue(
      createChatState({
        handleSend: vi.fn().mockResolvedValue({ needsLLMConfig: true }),
      })
    );

    renderWithRoute(<ChatPage />, {
      path: '/chat',
      route: '/chat',
    });

    await act(async () => {
      await user.click(await screen.findByRole('button', { name: 'Send message' }));
    });

    expect(await screen.findByText('LLM Configurations')).toBeInTheDocument();
  });

  it('surfaces provider capability limits in config mode and switches providers from the header', async () => {
    const user = userEvent.setup();
    const handleSetActiveProvider = vi.fn();

    mockUseChatOrchestration.mockReturnValue(
      createChatState({
        supportsReasoning: false,
        supportsWebSearch: false,
        llmProviders: [ANTHROPIC_PROVIDER, OLLAMA_PROVIDER],
        handleSetActiveProvider,
      })
    );

    renderWithRoute(<ChatPage />, {
      path: '/chat',
      route: '/chat',
    });

    await act(async () => {
      await user.click(await screen.findByRole('tab', { name: 'Config' }));
    });
    expect(await screen.findByText('Reasoning not available for this model')).toBeInTheDocument();
    expect(screen.getByText('Not available for this model')).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole('combobox'));
    });
    await user.click(await screen.findByRole('option', { name: 'Local Ollama' }));

    expect(handleSetActiveProvider).toHaveBeenCalledWith('llm-ollama');
  });

  it('shows the empty configured-provider state when only API-key-backed providers are unavailable', async () => {
    const user = userEvent.setup();

    mockUseChatOrchestration.mockReturnValue(
      createChatState({
        activeLLMProvider: null,
        activeLLMProviderId: null,
        llmProviders: [
          {
            ...ANTHROPIC_PROVIDER,
            apiKeySet: false,
          },
        ],
      })
    );

    renderWithRoute(<ChatPage />, {
      path: '/chat',
      route: '/chat',
    });

    await act(async () => {
      await user.click(screen.getByRole('combobox'));
    });

    expect(await screen.findByText('No LLMs configured')).toBeInTheDocument();
  });
});
