import {
    Plus,
    Trash2,
    MessageSquare,
    LogOut,
    MoreVertical,
} from "lucide-react";
import {
    Button,
    Modal,
    ModalContent,
    ModalHeader,
    ModalBody,
    ModalFooter,
    Skeleton,
    Dropdown,
    DropdownTrigger,
    DropdownMenu,
    DropdownItem,
} from "@heroui/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useChat } from "./useChat";
import { useReadUsersMeApiV1AuthMeGet } from "@/server/generated";
import {
    getColorFromString,
    getInitials,
} from "@/view/libs/getColorFromString";
import { removeToken } from "@/view/libs/auth";

interface IChatListProps {
    currentChatId: number | null;
}

export const ChatList = ({ currentChatId }: IChatListProps) => {
    const router = useRouter();
    const { data: userResponse, isLoading: isUserLoading } =
        useReadUsersMeApiV1AuthMeGet();
    const user = userResponse?.status === 200 ? userResponse.data : null;

    const {
        chats,
        isLoading,
        handleDeleteChat,
        deleteDialogChatId,
        confirmDelete,
        cancelDelete,
    } = useChat(currentChatId);

    const handleLogout = () => {
        removeToken();
        router.push("/login");
    };

    if (isLoading || isUserLoading) {
        return (
            <div className="w-[280px] bg-white border-r border-gray-200 flex flex-col">
                <div className="p-4 border-b border-gray-200">
                    <Skeleton className="h-16 rounded-lg mb-4" />
                    <Skeleton className="h-10 rounded-lg" />
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-2">
                    {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-16 rounded-lg" />
                    ))}
                </div>
            </div>
        );
    }

    return (
        <>
            <div className="w-[280px] bg-gray-100 flex flex-col">
                <div className="p-4">
                    {user && (
                        <div className="flex items-center gap-3 mb-4">
                            <div
                                className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm"
                                style={{
                                    backgroundColor: getColorFromString(
                                        user.username
                                    ),
                                }}
                            >
                                {getInitials(user.username)}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="font-medium text-gray-900 truncate">
                                    {user.username}
                                </div>
                                <div className="text-xs text-gray-500 truncate font-normal">
                                    {user.email}
                                </div>
                            </div>
                            <Button
                                isIconOnly
                                size="sm"
                                variant="light"
                                onPress={handleLogout}
                                title="Выйти"
                                className="border p-2 border-gray-200"
                            >
                                <LogOut size={16} className="text-blue-600" />
                            </Button>
                        </div>
                    )}

                    <Link
                        href="/chat"
                        className="w-full p-2 px-4 border-2 border-gray-200 rounded-md flex items-center gap-2 text-sm transition-colors duration-200 hover:bg-gray-50 hover:border-gray-300"
                    >
                        <Plus size={20} className="text-blue-600" />
                        Новый чат
                    </Link>
                </div>

                <div className="flex-1 overflow-y-auto p-4">
                    <div className="mb-2 text-sm font-medium text-gray-500 px-2">
                        Чаты
                    </div>
                    <div>
                        {chats.length === 0 ? (
                            <div className="text-center py-8 text-gray-500">
                                <MessageSquare
                                    size={32}
                                    className="mx-auto mb-2 opacity-50"
                                />
                                <p className="text-sm">Нет чатов</p>
                                <p className="text-xs">Создайте новый чат</p>
                            </div>
                        ) : (
                            chats.map((chat) => (
                                <div
                                    key={chat.chat_id}
                                    className={`w-full transition-all duration-200 text-sm font-light text-black rounded-xl ${
                                        currentChatId === chat.chat_id
                                            ? "bg-blue-50 shadow-sm"
                                            : "hover:bg-gray-50 hover:shadow-sm"
                                    }`}
                                >
                                    <div className="flex items-center justify-between gap-2">
                                        <Link
                                            href={`/chat?id=${chat.chat_id}`}
                                            className="flex-1 pl-3 py-2  truncate cursor-pointer"
                                        >
                                            Чат #{chat.chat_id}
                                        </Link>
                                        <Dropdown>
                                            <DropdownTrigger>
                                                <button className="p-1 mr-3 cursor-pointer hover:bg-gray-200 rounded transition-colors duration-150 text-gray-600 hover:text-gray-900">
                                                    <MoreVertical size={16} />
                                                </button>
                                            </DropdownTrigger>
                                            <DropdownMenu aria-label="Chat actions">
                                                <DropdownItem
                                                    key="delete"
                                                    className="text-danger"
                                                    color="danger"
                                                    startContent={
                                                        <Trash2 size={16} />
                                                    }
                                                    onPress={(e) => {
                                                        handleDeleteChat(
                                                            chat.chat_id
                                                        );
                                                    }}
                                                >
                                                    Удалить чат
                                                </DropdownItem>
                                            </DropdownMenu>
                                        </Dropdown>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            <Modal isOpen={!!deleteDialogChatId} onClose={cancelDelete}>
                <ModalContent>
                    <ModalHeader>Удалить чат?</ModalHeader>
                    <ModalBody>
                        <p>Это действие нельзя отменить.</p>
                    </ModalBody>
                    <ModalFooter>
                        <Button variant="light" onPress={cancelDelete}>
                            Отмена
                        </Button>
                        <Button color="danger" onPress={confirmDelete}>
                            Удалить
                        </Button>
                    </ModalFooter>
                </ModalContent>
            </Modal>
        </>
    );
};
