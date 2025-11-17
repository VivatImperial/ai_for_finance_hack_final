"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState, ReactNode } from "react";
import { ToastProvider } from "@heroui/react";
import { HeroUIProvider } from "@heroui/react";
import NextTopLoader from "nextjs-toploader";

export const Providers = ({ children }: { children: ReactNode }) => {
    const [queryClient] = useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: {
                        staleTime: 60 * 1000,
                        refetchOnWindowFocus: false,
                        retry: false,
                        throwOnError: (error) => {
                            // Пробрасываем ошибки, особенно 401, чтобы они попали в error.tsx
                            const status = (error as any)?.status;
                            if (status === 401) {
                                return true;
                            }
                            // Для других ошибок можно настроить по необходимости
                            return false;
                        },
                    },
                    mutations: {
                        retry: false,
                        throwOnError: (error) => {
                            const status = (error as any)?.status;
                            if (status === 401) {
                                return true;
                            }
                            return false;
                        },
                    },
                },
            })
    );

    return (
        <QueryClientProvider client={queryClient}>
            <HeroUIProvider>
                <ToastProvider placement="top-right" maxVisibleToasts={5} />
                {children}
                <NextTopLoader
                    color="#0070f3"
                    height={4}
                    showSpinner={false}
                    crawl={true}
                    zIndex={100000000}
                    crawlSpeed={500}
                    initialPosition={0.15}
                    easing="ease"
                    speed={200}
                />
                <ReactQueryDevtools initialIsOpen={false} />
            </HeroUIProvider>
        </QueryClientProvider>
    );
};
