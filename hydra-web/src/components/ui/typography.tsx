import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const textVariants = cva('', {
  variants: {
    variant: {
      h1: 'text-4xl font-bold tracking-tight',
      h2: 'text-3xl font-semibold tracking-tight',
      h3: 'text-2xl font-semibold tracking-tight',
      h4: 'text-xl font-semibold tracking-tight',
      h5: 'text-lg font-medium',
      h6: 'text-base font-medium',
      body: 'text-sm',
      'body-lg': 'text-base',
      small: 'text-xs',
      caption: 'text-xs text-muted-foreground',
      label: 'text-sm font-medium leading-none',
      code: 'text-sm font-mono bg-muted px-1.5 py-0.5 rounded',
    },
    tone: {
      default: 'text-foreground',
      muted: 'text-muted-foreground',
      primary: 'text-primary',
      success: 'text-success',
      warning: 'text-warning',
      destructive: 'text-destructive',
      inherit: 'text-inherit',
    },
    weight: {
      normal: 'font-normal',
      medium: 'font-medium',
      semibold: 'font-semibold',
      bold: 'font-bold',
    },
    align: {
      left: 'text-left',
      center: 'text-center',
      right: 'text-right',
    },
    truncate: {
      true: 'truncate',
      false: '',
    },
  },
  defaultVariants: {
    variant: 'body',
    tone: 'default',
    truncate: false,
  },
});

type TextElement = 'p' | 'span' | 'div' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'label' | 'code';

export interface TextProps
  extends Omit<React.HTMLAttributes<HTMLElement>, 'color'>,
    VariantProps<typeof textVariants> {
  as?: TextElement;
}

const defaultElementMap: Record<string, TextElement> = {
  h1: 'h1',
  h2: 'h2',
  h3: 'h3',
  h4: 'h4',
  h5: 'h5',
  h6: 'h6',
  label: 'label',
  code: 'code',
};

const Text = React.forwardRef<HTMLElement, TextProps>(
  ({ className, variant, tone, weight, align, truncate, as, ...props }, ref) => {
    const Component = as || defaultElementMap[variant || ''] || 'p';
    return (
      <Component
        // @ts-expect-error - ref typing for dynamic elements
        ref={ref}
        className={cn(textVariants({ variant, tone, weight, align, truncate, className }))}
        {...props}
      />
    );
  }
);
Text.displayName = 'Text';

// Convenience components for common headings
const H1 = React.forwardRef<HTMLHeadingElement, Omit<TextProps, 'variant' | 'as'>>(
  (props, ref) => <Text ref={ref as React.Ref<HTMLElement>} variant="h1" as="h1" {...props} />
);
H1.displayName = 'H1';

const H2 = React.forwardRef<HTMLHeadingElement, Omit<TextProps, 'variant' | 'as'>>(
  (props, ref) => <Text ref={ref as React.Ref<HTMLElement>} variant="h2" as="h2" {...props} />
);
H2.displayName = 'H2';

const H3 = React.forwardRef<HTMLHeadingElement, Omit<TextProps, 'variant' | 'as'>>(
  (props, ref) => <Text ref={ref as React.Ref<HTMLElement>} variant="h3" as="h3" {...props} />
);
H3.displayName = 'H3';

const H4 = React.forwardRef<HTMLHeadingElement, Omit<TextProps, 'variant' | 'as'>>(
  (props, ref) => <Text ref={ref as React.Ref<HTMLElement>} variant="h4" as="h4" {...props} />
);
H4.displayName = 'H4';

const Muted = React.forwardRef<HTMLParagraphElement, Omit<TextProps, 'tone'>>(
  (props, ref) => <Text ref={ref as React.Ref<HTMLElement>} tone="muted" {...props} />
);
Muted.displayName = 'Muted';

const Code = React.forwardRef<HTMLElement, Omit<TextProps, 'variant' | 'as'>>(
  (props, ref) => <Text ref={ref} variant="code" as="code" {...props} />
);
Code.displayName = 'Code';

export { Text, H1, H2, H3, H4, Muted, Code, textVariants };
