import { useEffect, useState, FormEvent, useRef } from "react";
import { Paperclip, X } from "lucide-react";
import { Button, Textarea, Chip } from "@heroui/react";
import { useAttachedDocuments } from "@/view/libs/AttachedDocumentsContext";
import { useMessages } from "@/view/libs/MessagesContext";
import {
    useCreateMessageApiV1ChatChatIdMessagePost,
    useCreateChatApiV1ChatPost,
    getGetChatApiV1ChatChatIdGetQueryKey,
} from "@/server/generated";
import { useRouter } from "next/navigation";
import { addToast } from "@heroui/react";
import { useQueryClient } from "@tanstack/react-query";
import type { ExtendedMessageResponse } from "@/types/messages";
import type { MessageResponse } from "@/types/api";

interface IMessageInputProps {
    chatId: number | null;
    onAttachClick: () => void;
    onSendingChange?: (isSending: boolean) => void;
}

export const MessageInput = ({
    chatId,
    onAttachClick,
    onSendingChange,
}: IMessageInputProps) => {
    const router = useRouter();
    const queryClient = useQueryClient();
    const { attachedDocuments, removeAttachment, clearAttachments } =
        useAttachedDocuments();
    const { addOptimisticMessage, clearOptimisticMessages } = useMessages();
    const [inputValue, setInputValue] = useState("");
    const pendingMessageDataRef = useRef<{
        messageContent: string;
        documentIds: number[];
    } | null>(null);

    const sendMessageMutation = useCreateMessageApiV1ChatChatIdMessagePost({
        mutation: {
            onSuccess: async (response, variables) => {
                const currentChatId = variables.chatId;

                // Очищаем оптимистичные сообщения для этого чата
                clearOptimisticMessages(currentChatId);

                // Инвалидируем запрос для получения обновленных данных с сервера
                // Сервер вернет полный чат с новым сообщением ассистента
                // После получения данных, новое сообщение ассистента будет помечено как fresh в MessageArea
                await queryClient.invalidateQueries({
                    queryKey:
                        getGetChatApiV1ChatChatIdGetQueryKey(currentChatId),
                });
            },
            onError: (error, variables) => {
                console.error("Ошибка отправки сообщения:", error);

                // Очищаем оптимистичные сообщения при ошибке
                clearOptimisticMessages(variables.chatId);

                addToast({
                    title: "Ошибка отправки сообщения",
                    color: "danger",
                });
            },
        },
    });

    const createChatMutation = useCreateChatApiV1ChatPost({
        mutation: {
            onSuccess: async (response) => {
                if (response.status === 201) {
                    const newChatId = response.data.chat_id;

                    // Получаем значения из ref
                    const messageData = pendingMessageDataRef.current;

                    if (messageData) {
                        const { messageContent, documentIds } = messageData;

                        // Очищаем ref после использования
                        pendingMessageDataRef.current = null;

                        // Создаем оптимистичное сообщение
                        const optimisticUserMessage: ExtendedMessageResponse = {
                            message_id: Date.now(),
                            content: messageContent,
                            message_type: 0,
                            created_at: new Date().toISOString(),
                            documents_ids: documentIds,
                            hidden_comments: null,
                            fresh: false, // Сообщения пользователя не fresh
                        };

                        // Добавляем сообщение в контекст ДО перехода на страницу чата
                        addOptimisticMessage(newChatId, optimisticUserMessage);

                        // СНАЧАЛА переходим на страницу чата (сообщение уже в контексте)
                        router.push(`/chat?id=${newChatId}`);

                        // ПОТОМ отправляем сообщение на сервер (в фоне)
                        sendMessageMutation.mutate({
                            chatId: newChatId,
                            data: {
                                content: messageContent,
                                documents_ids: documentIds,
                            },
                        });

                        // Инвалидируем список чатов
                        queryClient.invalidateQueries({
                            queryKey: ["getAllChatsApiV1ChatGet"],
                        });
                    } else {
                        // Если нет сообщения, просто переходим
                        queryClient.invalidateQueries({
                            queryKey: ["getAllChatsApiV1ChatGet"],
                        });
                        router.push(`/chat?id=${newChatId}`);
                    }
                }
            },
            onError: (error) => {
                console.error("Ошибка создания чата:", error);
                // Очищаем ref при ошибке
                pendingMessageDataRef.current = null;
                addToast({ title: "Ошибка создания чата", color: "danger" });
            },
        },
    });

    const handleSubmit = (e: FormEvent) => {
        e.preventDefault();

        if (!inputValue.trim()) {
            addToast({ title: "Введите сообщение", color: "danger" });
            return;
        }

        const messageContent = inputValue.trim();
        const documentIdsToSend = attachedDocuments.map((doc) => doc.id); // Сохраняем копию перед очисткой

        // Очищаем поле ввода и прикрепленные документы сразу при отправке
        setInputValue("");
        clearAttachments();

        if (!chatId) {
            // Сохраняем данные сообщения перед созданием чата
            pendingMessageDataRef.current = {
                messageContent,
                documentIds: documentIdsToSend,
            };

            createChatMutation.mutate(
                { data: { prompt_id: 1 } } // Using prompt_id 1 as default, adjust if needed
            );
            return;
        }

        // Создаем оптимистичное сообщение пользователя
        const optimisticUserMessage: ExtendedMessageResponse = {
            message_id: Date.now(), // Временный ID
            content: messageContent,
            message_type: 0, // 0 = user
            created_at: new Date().toISOString(),
            documents_ids: documentIdsToSend,
            hidden_comments: null,
            fresh: false, // Сообщения пользователя не fresh
        };

        // СНАЧАЛА добавляем сообщение в контекст (оно сразу отобразится)
        addOptimisticMessage(chatId, optimisticUserMessage);

        // ПОТОМ отправляем запрос на сервер
        sendMessageMutation.mutate({
            chatId,
            data: {
                content: messageContent,
                documents_ids: documentIdsToSend,
            },
        });
    };

    // isSending должен быть true пока идет мутация
    const isSending =
        sendMessageMutation.isPending || createChatMutation.isPending;

    // Уведомляем родительский компонент об изменении isSending
    useEffect(() => {
        onSendingChange?.(isSending);
    }, [isSending, onSendingChange]);

    return (
        <div className="fixed bottom-[120px] left-[280px] right-0 px-6">
            <div className="max-w-4xl mx-auto">
                {attachedDocuments.length > 0 && (
                    <div className="flex items-center gap-2 mb-3 flex-nowrap overflow-hidden">
                        {attachedDocuments.slice(0, 3).map((doc) => (
                            <Chip
                                key={doc.id}
                                size="lg"
                                className="bg-blue-500 text-white shrink-0"
                                onClose={() => removeAttachment(doc.id)}
                            >
                                {doc.name.length > 15
                                    ? doc.name.slice(0, 15) + "..."
                                    : doc.name}
                            </Chip>
                        ))}
                        {attachedDocuments.length > 3 && (
                            <Chip
                                size="lg"
                                className="bg-blue-500 text-white shrink-0"
                            >
                                +{attachedDocuments.length - 3}
                            </Chip>
                        )}
                        <button
                            onClick={clearAttachments}
                            className="ml-auto shrink-0 bg-gray-200 hover:bg-gray-300 rounded-full p-2 transition-colors"
                            aria-label="Удалить все файлы"
                        >
                            <X
                                className="w-5 h-5 text-black"
                                strokeWidth={1.5}
                            />
                        </button>
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div className="bg-white rounded-2xl shadow-md px-6 py-1 flex items-start gap-3">
                        <Textarea
                            value={inputValue}
                            onValueChange={setInputValue}
                            placeholder="Спросите что-нибудь или перетащите файл"
                            radius="lg"
                            minRows={1}
                            maxRows={20}
                            classNames={{
                                input: "py-2 text-base resize-none h-[40px]",
                                inputWrapper:
                                    "shadow-none border-none bg-transparent px-0 hover:bg-transparent data-[hover=true]:bg-transparent group-data-[focus=true]:bg-transparent",
                                base: "flex-1 min-w-0",
                            }}
                        />
                        <div className="flex items-start gap-2 shrink-0 pt-2">
                            <Button
                                type="button"
                                variant="light"
                                radius="full"
                                startContent={<Paperclip className="w-5 h-5" />}
                                onPress={onAttachClick}
                            >
                                Файл
                            </Button>
                            <Button
                                type="submit"
                                radius="full"
                                color="primary"
                                isDisabled={isSending || !inputValue.trim()}
                            >
                                Отправить
                            </Button>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
};
