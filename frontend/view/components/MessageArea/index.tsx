import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useGetChatApiV1ChatChatIdGet } from "@/server/generated";
import { MessageBubble } from "@/view/components/MessageBubble";
import { TypingMessage } from "@/view/components/TypingMessage";
import ShinyText from "@/view/components/ShinyText";
import { useMessages } from "@/view/libs/MessagesContext";
import type { ExtendedMessageResponse } from "@/types/messages";
import type { MessageResponse } from "@/types/api";

interface IMessageAreaProps {
    chatId: number;
    isSending?: boolean;
}

export const MessageArea = ({
    chatId,
    isSending = false,
}: IMessageAreaProps) => {
    const { data: chatResponse, isLoading } =
        useGetChatApiV1ChatChatIdGet(chatId);
    const { optimisticMessages } = useMessages();
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [typingComplete, setTypingComplete] = useState<number | null>(null);
    const [isInitialLoad, setIsInitialLoad] = useState(true);

    const chat = useMemo(
        () => (chatResponse?.status === 200 ? chatResponse.data : null),
        [chatResponse]
    );

    // Объединяем сообщения из кэша с оптимистичными сообщениями
    const messages = useMemo(() => {
        const cachedMessages: ExtendedMessageResponse[] = (
            chat?.messages || []
        ).map((msg: MessageResponse) => ({
            ...msg,
            fresh: false, // Сообщения из кэша не fresh
        }));
        const optimistic = optimisticMessages
            .filter((item) => item.chatId === chatId)
            .map((item) => item.message);

        // Фильтруем дубликаты - если сообщение уже есть в кэше, не показываем оптимистичное
        const uniqueOptimistic = optimistic.filter(
            (optMsg) =>
                !cachedMessages.some(
                    (cacheMsg) =>
                        cacheMsg.content === optMsg.content &&
                        cacheMsg.message_type === optMsg.message_type &&
                        Math.abs(
                            new Date(cacheMsg.created_at).getTime() -
                                new Date(optMsg.created_at).getTime()
                        ) < 5000 // В пределах 5 секунд считаем дубликатом
                )
        );

        return [...cachedMessages, ...uniqueOptimistic];
    }, [chat, optimisticMessages, chatId]);

    // Находим последнее сообщение от ассистента с fresh === true для анимации typewriting
    const typingMessage = useMemo(() => {
        // Ищем последнее сообщение от ассистента с fresh === true
        for (let i = messages.length - 1; i >= 0; i--) {
            const msg = messages[i];
            if (
                msg.message_type === 1 &&
                msg.fresh === true &&
                typingComplete !== msg.message_id
            ) {
                return msg;
            }
        }
        return null;
    }, [messages, typingComplete]);

    // Функция для скролла (используется при тайпврайтинге)
    const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior });
        }
    };

    // Сбрасываем флаг начальной загрузки при смене чата
    useEffect(() => {
        setIsInitialLoad(true);
    }, [chatId]);

    // Автоскролл при изменении сообщений
    // useLayoutEffect выполняется синхронно перед отрисовкой, предотвращая "дергание"
    useLayoutEffect(() => {
        if (messagesEndRef.current && !isLoading && messages.length > 0) {
            // При первой загрузке - мгновенный скролл, потом - плавный
            messagesEndRef.current.scrollIntoView({
                behavior: isInitialLoad ? "auto" : "smooth",
            });

            // После первого скролла отмечаем, что начальная загрузка завершена
            if (isInitialLoad) {
                setIsInitialLoad(false);
            }
        }
    }, [messages, isLoading, isInitialLoad]);

    if (isLoading) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="text-gray-500">Загрузка...</div>
            </div>
        );
    }

    if (!chat) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="text-gray-500">
                    Выберите чат или создайте новый
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col">
            {/* Header с названием чата */}
            <div className="h-[92px] px-6 py-4 border-b border-gray-200 flex items-center">
                <div className="max-w-4xl mx-auto w-full">
                    <h1 className="text-xl font-medium text-gray-900">
                        Чат #{chatId}
                    </h1>
                    <p className="text-sm text-gray-500">
                        Добавляйте документы для более точного ответа, храните
                        их и просматривайте в панеле справа!
                    </p>
                </div>
            </div>

            {/* Область сообщений с внутренним скроллом */}
            <div
                className="flex-1 overflow-y-auto max-h-[calc(100vh-92px-210px)] px-6 py-6"
                style={{ overflowAnchor: "auto" }}
            >
                <div className="max-w-4xl mx-auto space-y-6 flex flex-col gap-4">
                    {messages.map((message: ExtendedMessageResponse) => {
                        // Пропускаем сообщение, если оно показывается с анимацией печати
                        if (
                            typingMessage &&
                            message.message_id === typingMessage.message_id
                        ) {
                            return null;
                        }

                        return (
                            <MessageBubble
                                key={message.message_id}
                                message={message}
                            />
                        );
                    })}

                    {/* Показываем сообщение ассистента с анимацией typewriting */}
                    {typingMessage && (
                        <TypingMessage
                            content={typingMessage.content}
                            onComplete={() => {
                                setTypingComplete(typingMessage.message_id);
                            }}
                            speed={Math.floor(Math.random() * 500) + 500} // 500-1000мс рандомно (общее время)
                            onTextUpdate={() => scrollToBottom("smooth")}
                        />
                    )}

                    {/* Показываем ShinyText пока ждем ответа */}
                    {isSending && (
                        <div className="flex flex-col gap-4 items-start animate-fade-in-up">
                            <div className="text-gray-600 text-sm">
                                {new Date().toLocaleTimeString("ru-RU", {
                                    hour: "2-digit",
                                    minute: "2-digit",
                                })}
                            </div>
                            <div className="text-black">
                                <ShinyText text="Думает..." />
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>
            </div>
        </div>
    );
};
