"use client";

import { createContext, useContext, useState, useCallback } from "react";
import type { ExtendedMessageResponse } from "@/types/messages";

interface OptimisticMessage {
    chatId: number;
    message: ExtendedMessageResponse;
}

interface MessagesContextValue {
    optimisticMessages: OptimisticMessage[];
    addOptimisticMessage: (
        chatId: number,
        message: ExtendedMessageResponse
    ) => void;
    removeOptimisticMessage: (chatId: number, messageId: number) => void;
    clearOptimisticMessages: (chatId: number) => void;
}

const MessagesContext = createContext<MessagesContextValue | undefined>(
    undefined
);

export const MessagesProvider = ({
    children,
}: {
    children: React.ReactNode;
}) => {
    const [optimisticMessages, setOptimisticMessages] = useState<
        OptimisticMessage[]
    >([]);

    const addOptimisticMessage = useCallback(
        (chatId: number, message: ExtendedMessageResponse) => {
            setOptimisticMessages((prev) => [...prev, { chatId, message }]);
        },
        []
    );

    const removeOptimisticMessage = useCallback(
        (chatId: number, messageId: number) => {
            setOptimisticMessages((prev) =>
                prev.filter(
                    (item) =>
                        !(
                            item.chatId === chatId &&
                            item.message.message_id === messageId
                        )
                )
            );
        },
        []
    );

    const clearOptimisticMessages = useCallback((chatId: number) => {
        setOptimisticMessages((prev) =>
            prev.filter((item) => item.chatId !== chatId)
        );
    }, []);

    return (
        <MessagesContext.Provider
            value={{
                optimisticMessages,
                addOptimisticMessage,
                removeOptimisticMessage,
                clearOptimisticMessages,
            }}
        >
            {children}
        </MessagesContext.Provider>
    );
};

export const useMessages = () => {
    const context = useContext(MessagesContext);
    if (!context) {
        throw new Error("useMessages must be used within MessagesProvider");
    }
    return context;
};
