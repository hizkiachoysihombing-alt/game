'use client';

import { ReactNode } from 'react';
import { AuthProvider } from '@/app/providers/auth-context';

export function AuthProvider_({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

export { AuthProvider };
