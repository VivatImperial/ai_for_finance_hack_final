"use client";

import { useState, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { ChatList } from "@/view/components/ChatList";
import { MessageArea } from "@/view/components/MessageArea";
import { MessageInput } from "@/view/components/MessageInput";
import { DocumentPanel } from "@/view/components/DocumentPanel";
import {
    AttachedDocumentsProvider,
    useAttachedDocuments,
} from "@/view/libs/AttachedDocumentsContext";
import { MessagesProvider, useMessages } from "@/view/libs/MessagesContext";
import Folder from "@/view/components/Folder";
import { Paperclip } from "lucide-react";

const ChatPageContent = () => {
    const searchParams = useSearchParams();
    const chatId = searchParams.get("id")
        ? parseInt(searchParams.get("id")!)
        : null;

    const [isPanelOpen, setIsPanelOpen] = useState(false);
    const { clearAttachments } = useAttachedDocuments();
    const { clearOptimisticMessages } = useMessages();
    const prevChatIdRef = useRef<number | null>(chatId);
    const [isSending, setIsSending] = useState(false);

    // Очищаем прикрепленные документы и оптимистичные сообщения при смене чата
    useEffect(() => {
        if (
            prevChatIdRef.current !== chatId &&
            prevChatIdRef.current !== null
        ) {
            clearAttachments();
            // Очищаем оптимистичные сообщения предыдущего чата
            clearOptimisticMessages(prevChatIdRef.current);
            prevChatIdRef.current = chatId;
        } else if (prevChatIdRef.current === null) {
            prevChatIdRef.current = chatId;
        }
    }, [chatId, clearAttachments, clearOptimisticMessages]);

    const handleAttachClick = () => {
        setIsPanelOpen(true);
    };

    return (
        <div className="h-screen flex bg-gray-50">
            <ChatList currentChatId={chatId} />

            <div className="flex-1 flex flex-col relative">
                {chatId ? (
                    <MessageArea chatId={chatId} isSending={isSending} />
                ) : (
                    <div className="flex-1 flex flex-col pt-[300px] items-center">
                        <Folder
                            color="#5227FF"
                            size={1}
                            items={[
                                <div
                                    key="paper1"
                                    className="w-full h-full flex items-center justify-center"
                                >
                                    <Paperclip
                                        className="text-gray-400"
                                        size={24}
                                    />
                                </div>,
                                <div
                                    key="paper2"
                                    className="w-full h-full flex items-center justify-center"
                                >
                                    <Paperclip
                                        className="text-gray-400"
                                        size={24}
                                    />
                                </div>,
                                <div
                                    key="paper3"
                                    className="w-full h-full flex items-center justify-center"
                                >
                                    <span className="text-lg font-semibold text-gray-800 text-center">
                                        AI Скрепка
                                    </span>
                                </div>,
                            ]}
                        />
                        <div className="text-center mt-8">
                            <h2 className="text-2xl font-bold text-gray-900 mb-2">
                                Готов помочь вам с документами
                            </h2>
                        </div>
                    </div>
                )}
                <MessageInput
                    chatId={chatId}
                    onAttachClick={handleAttachClick}
                    onSendingChange={setIsSending}
                />
            </div>

            <DocumentPanel
                isOpen={isPanelOpen}
                onToggle={() => setIsPanelOpen(!isPanelOpen)}
            />
        </div>
    );
};

export const ChatPage = () => {
    return (
        <AttachedDocumentsProvider>
            <MessagesProvider>
                <ChatPageContent />
            </MessagesProvider>
        </AttachedDocumentsProvider>
    );
};
