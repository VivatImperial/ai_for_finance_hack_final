import { ChatPage } from "@/view/pages/ChatPage";
import {
    QueryClient,
    dehydrate,
    HydrationBoundary,
} from "@tanstack/react-query";
import { cookies } from "next/headers";
import {
    getReadUsersMeApiV1AuthMeGetQueryOptions,
    getGetAllChatsApiV1ChatGetQueryOptions,
    getGetChatApiV1ChatChatIdGetQueryOptions,
    getGetDocumentsForUserApiV1DocumentGetQueryOptions,
    type readUsersMeApiV1AuthMeGetResponse,
    type getAllChatsApiV1ChatGetResponse,
    type getChatApiV1ChatChatIdGetResponse,
    type getDocumentsForUserApiV1DocumentGetResponse,
} from "@/server/generated";
import { API_BASE_URL } from "@/server/libs/constants/api";

// Серверная функция fetch с поддержкой cookies
async function serverFetch<T>(url: string, options?: RequestInit): Promise<T> {
    const cookieStore = await cookies();
    const token = cookieStore.get("token")?.value;

    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(options?.headers as Record<string, string>),
    };

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const fullUrl = `${API_BASE_URL}${url}`;

    const response = await fetch(fullUrl, {
        ...options,
        headers,
    });

    const status = response.status;

    if (!response.ok) {
        try {
            const error = await response.json();
            const errorMessage = new Error(
                error.detail || `HTTP error! status: ${status}`
            );
            (errorMessage as any).status = status;
            throw errorMessage;
        } catch (e) {
            const text = await response.text().catch(() => "An error occurred");
            const errorMessage = new Error(
                text || `HTTP error! status: ${status}`
            );
            (errorMessage as any).status = status;
            throw errorMessage;
        }
    }

    const contentType = response.headers.get("content-type") || "";

    if (status === 204) {
        return {
            data: {},
            status: status,
            headers: response.headers,
        } as T;
    }

    if (status === 201) {
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            return {
                data: {},
                status: status,
                headers: response.headers,
            } as T;
        }
    }

    let text: string;
    try {
        text = await response.text();
    } catch (e) {
        return {
            data: {},
            status: status,
            headers: response.headers,
        } as T;
    }

    if (!text || text.trim() === "" || text.trim().startsWith("data:")) {
        return {
            data: {},
            status: status,
            headers: response.headers,
        } as T;
    }

    let data;
    try {
        data = JSON.parse(text);
    } catch (e) {
        return {
            data: {},
            status: status,
            headers: response.headers,
        } as T;
    }

    return {
        data,
        status: status,
        headers: response.headers,
    } as T;
}

export default async function Chat({
    searchParams,
}: {
    searchParams: Promise<{ id?: string }>;
}) {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: {
                staleTime: 60 * 1000,
                refetchOnWindowFocus: false,
                retry: false,
            },
        },
    });

    // Получаем chatId из searchParams (await для Next.js 15+)
    const params = await searchParams;
    const chatId = params?.id ? parseInt(params.id) : null;

    // Prefetch запросы
    try {
        // Prefetch me
        await queryClient.prefetchQuery({
            ...getReadUsersMeApiV1AuthMeGetQueryOptions(),
            queryFn: async () => {
                return serverFetch<readUsersMeApiV1AuthMeGetResponse>(
                    "/api/v1/auth/me",
                    { method: "GET" }
                );
            },
        });

        // Prefetch chat list
        await queryClient.prefetchQuery({
            ...getGetAllChatsApiV1ChatGetQueryOptions(),
            queryFn: async () => {
                return serverFetch<getAllChatsApiV1ChatGetResponse>(
                    "/api/v1/chat",
                    { method: "GET" }
                );
            },
        });

        // Prefetch конкретный чат, если указан chatId
        if (chatId && !isNaN(chatId)) {
            await queryClient.prefetchQuery({
                ...getGetChatApiV1ChatChatIdGetQueryOptions(chatId),
                queryFn: async () => {
                    return serverFetch<getChatApiV1ChatChatIdGetResponse>(
                        `/api/v1/chat/${chatId}`,
                        { method: "GET" }
                    );
                },
            });
        }

        // Prefetch documents
        await queryClient.prefetchQuery({
            ...getGetDocumentsForUserApiV1DocumentGetQueryOptions(),
            queryFn: async () => {
                return serverFetch<getDocumentsForUserApiV1DocumentGetResponse>(
                    "/api/v1/document",
                    { method: "GET" }
                );
            },
        });
    } catch (error) {
        // Игнорируем ошибки prefetch, чтобы не блокировать рендеринг
        console.error("Prefetch error:", error);
    }

    return (
        <HydrationBoundary state={dehydrate(queryClient)}>
            <ChatPage />
        </HydrationBoundary>
    );
}
