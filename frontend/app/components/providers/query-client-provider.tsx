'use client';

import { ReactNode } from 'react';
import { QueryClient, QueryClientProvider as QCProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 10, // 10 minutes
      retry: 1,
    },
  },
});

export function QueryClientProvider({ children }: { children: ReactNode }) {
  return <QCProvider client={queryClient}>{children}</QCProvider>;
}
