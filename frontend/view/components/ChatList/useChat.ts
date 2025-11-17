import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
    useGetAllChatsApiV1ChatGet,
    useCreateChatApiV1ChatPost,
    useDeleteChatApiV1ChatChatIdDelete,
    getGetAllChatsApiV1ChatGetQueryKey,
} from "@/server/generated";
import { addToast } from "@heroui/react";
import { useQueryClient } from "@tanstack/react-query";

export const useChat = (currentChatId: number | null) => {
    const router = useRouter();
    const queryClient = useQueryClient();
    const [deleteDialogChatId, setDeleteDialogChatId] = useState<number | null>(
        null
    );

    const { data: chatsResponse, isLoading } = useGetAllChatsApiV1ChatGet();
    const chats = useMemo(() => {
        return chatsResponse?.status === 200
            ? [...chatsResponse.data].reverse()
            : [];
    }, [chatsResponse]);

    const createChatMutation = useCreateChatApiV1ChatPost({
        mutation: {
            onSuccess: (response) => {
                if (response.status === 201) {
                    addToast({ title: "Чат создан", color: "success" });
                    queryClient.invalidateQueries({
                        queryKey: getGetAllChatsApiV1ChatGetQueryKey(),
                    });
                    router.push(`/chat?id=${response.data.chat_id}`);
                }
            },
            onError: () => {
                addToast({ title: "Ошибка создания чата", color: "danger" });
            },
        },
    });

    const deleteChatMutation = useDeleteChatApiV1ChatChatIdDelete({
        mutation: {
            onSuccess: () => {
                addToast({ title: "Чат удален", color: "success" });
                queryClient.invalidateQueries({
                    queryKey: getGetAllChatsApiV1ChatGetQueryKey(),
                });
                if (deleteDialogChatId === currentChatId) {
                    router.push("/chat");
                }
                setDeleteDialogChatId(null);
            },
            onError: () => {
                addToast({ title: "Ошибка удаления чата", color: "danger" });
                setDeleteDialogChatId(null);
            },
        },
    });

    const handleDeleteChat = (chatId: number) => {
        setDeleteDialogChatId(chatId);
    };

    const confirmDelete = () => {
        if (deleteDialogChatId) {
            deleteChatMutation.mutate({ chatId: deleteDialogChatId });
        }
    };

    const cancelDelete = () => {
        setDeleteDialogChatId(null);
    };

    return {
        chats,
        isLoading,
        currentChatId,
        handleDeleteChat,
        deleteDialogChatId,
        confirmDelete,
        cancelDelete,
        isCreating: createChatMutation.isPending,
    };
};
