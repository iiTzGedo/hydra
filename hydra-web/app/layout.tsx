import type { Metadata } from 'next';
import { Providers } from './providers';
import '@/index.css';

export const metadata: Metadata = {
  title: {
    default: 'Hydra',
    template: '%s | Hydra',
  },
  description: 'Hydra - AI-powered infrastructure management platform',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('hydra-theme');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark')}else{document.documentElement.classList.add('light')}}catch(e){document.documentElement.classList.add('light')}})()`,
          }}
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
