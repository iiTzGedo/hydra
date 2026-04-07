/**
 * Vitest test setup file.
 *
 * This file is loaded before each test file and sets up the testing environment.
 */

import '@testing-library/jest-dom';
import { act } from '@testing-library/react';
import { notifyManager } from '@tanstack/react-query';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';
import { server } from './msw/server';
import { resetMockState } from './msw/mock-state';

// TanStack Query batches async notifications outside React's event loop by default.
// Wrapping them in act() keeps query-driven test updates aligned with React 18 expectations.
notifyManager.setNotifyFunction((callback) => {
  act(callback);
});

vi.mock('framer-motion', async () => {
  const React = await import('react');

  const motionPropNames = new Set([
    'animate',
    'custom',
    'exit',
    'initial',
    'layout',
    'layoutId',
    'transition',
    'variants',
  ]);

  const sanitizeMotionProps = (props: Record<string, unknown>) =>
    Object.fromEntries(
      Object.entries(props).filter(
        ([key]) => !motionPropNames.has(key) && !key.startsWith('while')
      )
    );

  const createMotionComponent = (tag: keyof HTMLElementTagNameMap = 'div') =>
    React.forwardRef<HTMLElement, React.HTMLAttributes<HTMLElement>>(
      ({ children, ...props }, ref) =>
        React.createElement(tag, { ...sanitizeMotionProps(props), ref }, children)
    );

  return {
    AnimatePresence: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    motion: new Proxy(
      {},
      {
        get: (_target, key) =>
          typeof key === 'string'
            ? createMotionComponent(key as keyof HTMLElementTagNameMap)
            : createMotionComponent(),
      }
    ),
  };
});

vi.mock('@/components/ui/tooltip', async () => {
  const React = await import('react');

  const TooltipProvider = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);

  const Tooltip = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);

  const TooltipTrigger = ({
    children,
    asChild,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => {
    if (asChild && React.isValidElement(children)) {
      return children;
    }
    return React.createElement('span', null, children);
  };

  const TooltipContent = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);

  return {
    TooltipProvider,
    Tooltip,
    TooltipTrigger,
    TooltipContent,
  };
});

vi.mock('@/components/ui/scroll-area', async () => {
  const React = await import('react');

  const ScrollArea = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) =>
    React.createElement('div', { ...props, ref }, children)
  );

  const ScrollBar = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) =>
    React.createElement('div', { ...props, ref }, children)
  );

  return {
    ScrollArea,
    ScrollBar,
  };
});

vi.mock('@/components/ui/slider', async () => {
  const React = await import('react');

  const Slider = React.forwardRef<
    HTMLDivElement,
      React.HTMLAttributes<HTMLDivElement> & {
        value?: number[];
        defaultValue?: number[];
        min?: number;
        max?: number;
        step?: number;
        onValueChange?: (value: number[]) => void;
      }
  >(({ children, value, defaultValue, min: _min, max: _max, step: _step, onValueChange: _onValueChange, ...props }, ref) =>
    React.createElement(
      'div',
      {
        ...props,
        ref,
        role: 'slider',
        'aria-valuenow': value?.[0] ?? defaultValue?.[0] ?? 0,
      },
      children
    )
  );

  return { Slider };
});

vi.mock('@/components/ui/switch', async () => {
  const React = await import('react');

  const Switch = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & {
      checked?: boolean;
      defaultChecked?: boolean;
      onCheckedChange?: (checked: boolean) => void;
    }
  >(({ checked, defaultChecked, onCheckedChange, onClick, disabled, ...props }, ref) => {
    const [internalChecked, setInternalChecked] = React.useState(defaultChecked ?? false);
    const isChecked = checked ?? internalChecked;

    return React.createElement('button', {
      ...props,
      ref,
      type: 'button',
      role: 'switch',
      'aria-checked': isChecked,
      disabled,
      onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
        if (disabled) {
          return;
        }

        const nextChecked = !isChecked;
        if (checked === undefined) {
          act(() => {
            setInternalChecked(nextChecked);
          });
        }
        onCheckedChange?.(nextChecked);
        onClick?.(event);
      },
    });
  });

  return { Switch };
});

vi.mock('@/components/ui/tabs', async () => {
  const React = await import('react');

  interface TabsContextValue {
    value: string | undefined;
    setValue: (value: string) => void;
  }

  const TabsContext = React.createContext<TabsContextValue | null>(null);

  const useTabsContext = () => {
    const context = React.useContext(TabsContext);
    if (!context) {
      throw new Error('Tabs components must be used within Tabs.');
    }
    return context;
  };

  const Tabs = ({
    value,
    defaultValue,
    onValueChange,
    children,
  }: {
    value?: string;
    defaultValue?: string;
    onValueChange?: (value: string) => void;
    children: React.ReactNode;
  }) => {
    const [internalValue, setInternalValue] = React.useState(defaultValue);
    const activeValue = value ?? internalValue;

    const setValue = (nextValue: string) => {
      if (value === undefined) {
        act(() => {
          setInternalValue(nextValue);
        });
      }
      onValueChange?.(nextValue);
    };

    return React.createElement(
      TabsContext.Provider,
      { value: { value: activeValue, setValue } },
      children
    );
  };

  const TabsList = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) =>
    React.createElement('div', { ...props, ref, role: 'tablist' }, children)
  );

  const TabsTrigger = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string }
  >(({ children, value, onClick, ...props }, ref) => {
    const context = useTabsContext();
    return React.createElement(
      'button',
      {
        ...props,
        ref,
        type: 'button',
        role: 'tab',
        'aria-selected': context.value === value,
        onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
          context.setValue(value);
          onClick?.(event);
        },
      },
      children
    );
  });

  const TabsContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement> & { value: string }
  >(({ children, value, ...props }, ref) => {
    const context = useTabsContext();
    if (context.value !== value) {
      return null;
    }
    return React.createElement('div', { ...props, ref, role: 'tabpanel' }, children);
  });

  return {
    Tabs,
    TabsList,
    TabsTrigger,
    TabsContent,
  };
});

vi.mock('@/components/ui/dialog', async () => {
  const React = await import('react');

  interface DialogContextValue {
    open: boolean;
    setOpen: (open: boolean) => void;
  }

  const DialogContext = React.createContext<DialogContextValue | null>(null);

  const useDialogContext = () => {
    const context = React.useContext(DialogContext);
    if (!context) {
      throw new Error('Dialog components must be used within Dialog.');
    }
    return context;
  };

  const Dialog = ({
    open,
    defaultOpen,
    onOpenChange,
    children,
  }: {
    open?: boolean;
    defaultOpen?: boolean;
    onOpenChange?: (open: boolean) => void;
    children: React.ReactNode;
  }) => {
    const [internalOpen, setInternalOpen] = React.useState(defaultOpen ?? false);
    const isOpen = open ?? internalOpen;

    const setOpen = (nextOpen: boolean) => {
      if (open === undefined) {
        act(() => {
          setInternalOpen(nextOpen);
        });
      }
      onOpenChange?.(nextOpen);
    };

    return React.createElement(
      DialogContext.Provider,
      { value: { open: isOpen, setOpen } },
      children
    );
  };

  const DialogTrigger = ({
    children,
    asChild,
    onClick,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    children: React.ReactNode;
    asChild?: boolean;
  }) => {
    const context = useDialogContext();
    const triggerProps = {
      ...props,
      onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
        context.setOpen(true);
        onClick?.(event);
      },
    };

    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children, triggerProps);
    }

    return React.createElement('button', { ...triggerProps, type: 'button' }, children);
  };

  const DialogClose = ({
    children,
    asChild,
    onClick,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    children: React.ReactNode;
    asChild?: boolean;
  }) => {
    const context = useDialogContext();
    const closeProps = {
      ...props,
      onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
        context.setOpen(false);
        onClick?.(event);
      },
    };

    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children, closeProps);
    }

    return React.createElement('button', { ...closeProps, type: 'button' }, children);
  };

  const DialogPortal = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);

  const DialogOverlay = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >((props, ref) => {
    const context = useDialogContext();
    if (!context.open) {
      return null;
    }
    return React.createElement('div', { ...props, ref, 'data-testid': 'dialog-overlay' });
  });

  const DialogContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) => {
    const context = useDialogContext();
    if (!context.open) {
      return null;
    }
    return React.createElement('div', { ...props, ref, role: 'dialog' }, children);
  });

  const DialogHeader = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) =>
    React.createElement('div', { ...props, ref }, children)
  );

  const DialogFooter = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) =>
    React.createElement('div', { ...props, ref }, children)
  );

  const DialogTitle = React.forwardRef<
    HTMLHeadingElement,
    React.HTMLAttributes<HTMLHeadingElement>
  >(({ children, ...props }, ref) =>
    React.createElement('h2', { ...props, ref }, children)
  );

  const DialogDescription = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLParagraphElement>
  >(({ children, ...props }, ref) =>
    React.createElement('p', { ...props, ref }, children)
  );

  return {
    Dialog,
    DialogPortal,
    DialogOverlay,
    DialogTrigger,
    DialogClose,
    DialogContent,
    DialogHeader,
    DialogFooter,
    DialogTitle,
    DialogDescription,
  };
});

vi.mock('@/components/ui/select', async () => {
  const React = await import('react');

  interface SelectContextValue {
    value: string | undefined;
    label: React.ReactNode;
    open: boolean;
    setOpen: (open: boolean) => void;
    selectOption: (value: string, label: React.ReactNode) => void;
  }

  const SelectContext = React.createContext<SelectContextValue | null>(null);
  const MOCK_SELECT_ITEM = Symbol('mock-select-item');

  const useSelectContext = () => {
    const context = React.useContext(SelectContext);
    if (!context) {
      throw new Error('Select components must be used within Select.');
    }
    return context;
  };

  const isMarkedSelectItem = (
    element: React.ReactElement
  ): element is React.ReactElement<{ value: string; children: React.ReactNode }> => {
    const type = element.type as { __mockType?: symbol };
    return type.__mockType === MOCK_SELECT_ITEM;
  };

  const findSelectedLabel = (
    children: React.ReactNode,
    selectedValue: string | undefined
  ): React.ReactNode | undefined => {
    if (!selectedValue) {
      return undefined;
    }

    let match: React.ReactNode | undefined;

    React.Children.forEach(children, (child) => {
      if (match || !React.isValidElement(child)) {
        return;
      }

      if (isMarkedSelectItem(child) && child.props.value === selectedValue) {
        match = child.props.children;
        return;
      }

      if ('children' in child.props) {
        match = findSelectedLabel(child.props.children, selectedValue);
      }
    });

    return match;
  };

  const Select = ({
    value,
    defaultValue,
    onValueChange,
    disabled,
    children,
  }: {
    value?: string;
    defaultValue?: string;
    onValueChange?: (value: string) => void;
    disabled?: boolean;
    children: React.ReactNode;
  }) => {
    const [internalValue, setInternalValue] = React.useState(defaultValue);
    const [open, setOpen] = React.useState(false);
    const selectedValue = value ?? internalValue;
    const selectedLabel = findSelectedLabel(children, selectedValue);

    const selectOption = (nextValue: string) => {
      if (value === undefined) {
        act(() => {
          setInternalValue(nextValue);
        });
      }
      onValueChange?.(nextValue);
      act(() => {
        setOpen(false);
      });
    };

    return React.createElement(
      SelectContext.Provider,
      {
        value: {
          value: selectedValue,
          label: selectedLabel ?? null,
          open: disabled ? false : open,
          setOpen: disabled
            ? () => {}
            : (nextOpen) => {
                act(() => {
                  setOpen(nextOpen);
                });
              },
          selectOption: (nextValue, _label) => selectOption(nextValue),
        },
      },
      children
    );
  };

  const SelectGroup = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);

  const SelectValue = ({
    placeholder,
  }: {
    placeholder?: React.ReactNode;
  }) => {
    const context = useSelectContext();
    return React.createElement('span', null, context.label ?? placeholder ?? null);
  };

  const SelectTrigger = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement>
  >(({ children, onClick, ...props }, ref) => {
    const context = useSelectContext();
    return React.createElement(
      'button',
      {
        ...props,
        ref,
        type: 'button',
        role: 'combobox',
        'aria-expanded': context.open,
        disabled: props.disabled,
        onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
          if (props.disabled) {
            return;
          }
          act(() => {
            context.setOpen(!context.open);
          });
          onClick?.(event);
        },
      },
      children
    );
  });

  const SelectContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) => {
    const context = useSelectContext();
    if (!context.open) {
      return null;
    }
    return React.createElement('div', { ...props, ref, role: 'listbox' }, children);
  });

  const SelectLabel = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) =>
    React.createElement('div', { ...props, ref }, children)
  );

  const SelectItem = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string }
  >(({ children, value, onClick, ...props }, ref) => {
    const context = useSelectContext();
    return React.createElement(
      'button',
      {
        ...props,
        ref,
        type: 'button',
        role: 'option',
        'aria-selected': context.value === value,
        onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
          act(() => {
            context.selectOption(value, children);
          });
          onClick?.(event);
        },
      },
      children
    );
  });
  (SelectItem as { __mockType?: symbol }).__mockType = MOCK_SELECT_ITEM;

  const SelectSeparator = React.forwardRef<
    HTMLHRElement,
    React.HTMLAttributes<HTMLHRElement>
  >((props, ref) => React.createElement('hr', { ...props, ref }));

  const SelectScrollUpButton = ({
    children,
  }: {
    children?: React.ReactNode;
  }) => React.createElement(React.Fragment, null, children ?? null);

  const SelectScrollDownButton = ({
    children,
  }: {
    children?: React.ReactNode;
  }) => React.createElement(React.Fragment, null, children ?? null);

  return {
    Select,
    SelectGroup,
    SelectValue,
    SelectTrigger,
    SelectContent,
    SelectLabel,
    SelectItem,
    SelectSeparator,
    SelectScrollUpButton,
    SelectScrollDownButton,
  };
});

vi.mock('@/components/ui/dropdown-menu', async () => {
  const React = await import('react');

  interface DropdownMenuContextValue {
    open: boolean;
    setOpen: (open: boolean) => void;
  }

  const DropdownMenuContext = React.createContext<DropdownMenuContextValue | null>(null);

  const useDropdownMenuContext = () => {
    const context = React.useContext(DropdownMenuContext);
    if (!context) {
      throw new Error('Dropdown menu components must be used within DropdownMenu.');
    }
    return context;
  };

  const DropdownMenu = ({
    open,
    defaultOpen,
    onOpenChange,
    children,
  }: {
    open?: boolean;
    defaultOpen?: boolean;
    onOpenChange?: (open: boolean) => void;
    children: React.ReactNode;
  }) => {
    const [internalOpen, setInternalOpen] = React.useState(defaultOpen ?? false);
    const isOpen = open ?? internalOpen;

    const setOpen = (nextOpen: boolean) => {
      if (open === undefined) {
        setInternalOpen(nextOpen);
      }
      onOpenChange?.(nextOpen);
    };

    return React.createElement(
      DropdownMenuContext.Provider,
      { value: { open: isOpen, setOpen } },
      children
    );
  };

  const DropdownMenuTrigger = ({
    children,
    asChild,
    onClick,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    children: React.ReactNode;
    asChild?: boolean;
  }) => {
    const context = useDropdownMenuContext();
    const triggerProps = {
      ...props,
      'aria-haspopup': 'menu',
      'aria-expanded': context.open,
      onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
        act(() => {
          context.setOpen(!context.open);
        });
        onClick?.(event);
      },
    };

    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children, triggerProps);
    }

    return React.createElement('button', { ...triggerProps, type: 'button' }, children);
  };

  const DropdownMenuContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) => {
    const context = useDropdownMenuContext();
    if (!context.open) {
      return null;
    }
    return React.createElement('div', { ...props, ref, role: 'menu' }, children);
  });

  const DropdownMenuItem = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement>
  >(({ children, disabled, onClick, ...props }, ref) => {
    const context = useDropdownMenuContext();
    return React.createElement(
      'button',
      {
        ...props,
        ref,
        type: 'button',
        role: 'menuitem',
        disabled,
        onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
          onClick?.(event);
          act(() => {
            context.setOpen(false);
          });
        },
      },
      children
    );
  });

  const DropdownMenuCheckboxItem = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & { checked?: boolean }
  >(({ children, checked, disabled, onClick, ...props }, ref) => {
    const context = useDropdownMenuContext();
    return React.createElement(
      'button',
      {
        ...props,
        ref,
        type: 'button',
        role: 'menuitemcheckbox',
        'aria-checked': checked ?? false,
        disabled,
        onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
          onClick?.(event);
          act(() => {
            context.setOpen(false);
          });
        },
      },
      children
    );
  });

  const DropdownMenuRadioItem = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & { checked?: boolean }
  >(({ children, checked, disabled, onClick, ...props }, ref) => {
    const context = useDropdownMenuContext();
    return React.createElement(
      'button',
      {
        ...props,
        ref,
        type: 'button',
        role: 'menuitemradio',
        'aria-checked': checked ?? false,
        disabled,
        onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
          onClick?.(event);
          act(() => {
            context.setOpen(false);
          });
        },
      },
      children
    );
  });

  const DropdownMenuLabel = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) =>
    React.createElement('div', { ...props, ref }, children)
  );

  const DropdownMenuSeparator = React.forwardRef<
    HTMLHRElement,
    React.HTMLAttributes<HTMLHRElement>
  >((props, ref) => React.createElement('hr', { ...props, ref }));

  const DropdownMenuShortcut = ({
    children,
    ...props
  }: React.HTMLAttributes<HTMLSpanElement>) =>
    React.createElement('span', props, children);

  const DropdownMenuGroup = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);

  const DropdownMenuPortal = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);

  const DropdownMenuSub = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);

  const DropdownMenuSubContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
  >(({ children, ...props }, ref) =>
    React.createElement('div', { ...props, ref, role: 'menu' }, children)
  );

  const DropdownMenuSubTrigger = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement>
  >(({ children, ...props }, ref) =>
    React.createElement('button', { ...props, ref, type: 'button', role: 'menuitem' }, children)
  );

  const DropdownMenuRadioGroup = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);

  return {
    DropdownMenu,
    DropdownMenuTrigger,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuCheckboxItem,
    DropdownMenuRadioItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuShortcut,
    DropdownMenuGroup,
    DropdownMenuPortal,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuRadioGroup,
  };
});

// Mock IntersectionObserver for components that use it
class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | null = null;
  readonly rootMargin: string = '';
  readonly thresholds: ReadonlyArray<number> = [];

  constructor() {}

  disconnect(): void {}
  observe(): void {}
  unobserve(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

global.IntersectionObserver = MockIntersectionObserver;

// Mock ResizeObserver for components that use it
class MockResizeObserver implements ResizeObserver {
  constructor() {}

  disconnect(): void {}
  observe(): void {}
  unobserve(): void {}
}

global.ResizeObserver = MockResizeObserver;

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Mock scrollTo
Object.defineProperty(window, 'scrollTo', {
  writable: true,
  value: () => {},
});

Object.defineProperty(window, 'requestAnimationFrame', {
  writable: true,
  value: (callback: FrameRequestCallback) => window.setTimeout(() => callback(performance.now()), 0),
});

Object.defineProperty(window, 'cancelAnimationFrame', {
  writable: true,
  value: (id: number) => window.clearTimeout(id),
});

// Radix Select relies on pointer capture APIs that jsdom does not implement.
if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = () => false;
}
if (!HTMLElement.prototype.setPointerCapture) {
  HTMLElement.prototype.setPointerCapture = () => {};
}
if (!HTMLElement.prototype.releasePointerCapture) {
  HTMLElement.prototype.releasePointerCapture = () => {};
}
if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = () => {};
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  resetMockState();
});
afterAll(() => server.close());
