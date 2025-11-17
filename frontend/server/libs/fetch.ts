import Cookies from "js-cookie";
import { API_BASE_URL } from "./constants/api";

export const parseStreamingResponse = async (
    response: Response
): Promise<{ content?: string; done?: boolean } | null> => {
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let accumulatedContent = "";
    let isDone = false;

    if (!reader) return null;

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const dataStr = line.slice(6).trim();
                    if (dataStr === "") continue;

                    try {
                        const data = JSON.parse(dataStr);
                        // Накапливаем контент из всех чанков
                        if (data.content) {
                            accumulatedContent = data.content; // Последний чанк содержит полный контент
                        }
                        if (data.done) {
                            isDone = true;
                        }
                    } catch (e) {
                        // Игнорируем ошибки парсинга отдельных чанков
                    }
                }
            }
        }

        // Если получили done или есть накопленный контент, возвращаем его
        if (isDone || accumulatedContent) {
            return { content: accumulatedContent, done: isDone };
        }

        return null;
    } catch (error) {
        console.error("Ошибка чтения streaming ответа:", error);
        return null;
    }
};

export const customFetch = async <T>(
    url: string,
    options?: RequestInit
): Promise<T> => {
    const token = Cookies.get("token");

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

    // Проверяем статус ответа
    const status = response.status;

    if (!response.ok) {
        // Для ошибок пытаемся получить JSON, но если не получается - возвращаем текстовую ошибку
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

    // Проверяем Content-Type для обработки streaming ответов ПЕРЕД чтением тела
    const contentType = response.headers.get("content-type") || "";

    // Если это streaming ответ (text/event-stream), парсим его
    if (
        contentType.includes("text/event-stream") ||
        contentType.includes("application/x-ndjson") ||
        (contentType.includes("text/plain") && url.includes("/message"))
    ) {
        const streamingData = await parseStreamingResponse(response);
        return {
            data: streamingData || {},
            status: status,
            headers: response.headers,
        } as T;
    }

    if (status === 204) {
        return {
            data: {},
            status: status,
            headers: response.headers,
        } as T;
    }

    if (status === 201) {
        // Для 201 проверяем, есть ли тело
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            return {
                data: {},
                status: status,
                headers: response.headers,
            } as T;
        }
    }

    // Пытаемся получить текст ответа для проверки
    let text: string;
    try {
        text = await response.text();
    } catch (e) {
        // Если не удалось прочитать тело, возвращаем пустой объект
        return {
            data: {},
            status: status,
            headers: response.headers,
        } as T;
    }

    // Если тело пустое или начинается с "data: " (SSE формат), возвращаем пустой объект
    if (!text || text.trim() === "" || text.trim().startsWith("data:")) {
        return {
            data: {},
            status: status,
            headers: response.headers,
        } as T;
    }

    // Пытаемся парсить как JSON
    let data;
    try {
        data = JSON.parse(text);
    } catch (e) {
        // Если не удалось распарсить, возвращаем пустой объект
        // Это нормально для streaming ответов или ответов без тела
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
};

export default customFetch;
