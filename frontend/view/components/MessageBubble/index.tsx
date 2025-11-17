import { Copy, Check } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { Chip } from "@heroui/react";
import type { ExtendedMessageResponse } from "@/types/messages";

interface IMessageBubbleProps {
    message: ExtendedMessageResponse;
}

export const MessageBubble = ({ message }: IMessageBubbleProps) => {
    const isUser = message.message_type === 0; // 0 = user, 1 = assistant
    const [isCopied, setIsCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(message.content);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleTimeString("ru-RU", {
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    if (isUser) {
        // Пользователь - справа
        return (
            <div className="flex flex-col gap-4 items-end">
                <div className="text-gray-600 text-sm">
                    {formatDate(message.created_at)}
                </div>
                <div className="max-w-[70%] bg-gray-200 text-black rounded-3xl p-3">
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    {message.documents_ids.length > 0 && (
                        <div className="mt-2 flex items-center gap-2 flex-nowrap overflow-hidden">
                            {message.documents_ids
                                .slice(0, 3)
                                .map((id: number) => (
                                    <Chip
                                        key={id}
                                        size="lg"
                                        className="bg-blue-500 text-white shrink-0"
                                    >
                                        Документ #{id}
                                    </Chip>
                                ))}
                            {message.documents_ids.length > 3 && (
                                <Chip
                                    size="lg"
                                    className="bg-blue-500 text-white shrink-0"
                                >
                                    +{message.documents_ids.length - 3}
                                </Chip>
                            )}
                        </div>
                    )}
                </div>
                <button
                    onClick={handleCopy}
                    className={`p-2 rounded-xl transition-colors ${
                        isCopied
                            ? "bg-green-100 text-green-600"
                            : "bg-gray-100 hover:bg-gray-200"
                    }`}
                    title="Копировать"
                >
                    {isCopied ? <Check size={16} /> : <Copy size={16} />}
                </button>
            </div>
        );
    }

    // Ассистент - слева
    return (
        <div className="flex flex-col ">
            <div className="text-gray-500 text-sm">
                {formatDate(message.created_at)}
            </div>
            <div className="max-w-[70%] text-black markdown">
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                    components={{
                        p: ({ children }) => <p>{children}</p>,
                        h1: ({ children }) => <h1>{children}</h1>,
                        h2: ({ children }) => <h2>{children}</h2>,
                        h3: ({ children }) => <h3>{children}</h3>,
                        h4: ({ children }) => <h4>{children}</h4>,
                        h5: ({ children }) => <h5>{children}</h5>,
                        h6: ({ children }) => <h6>{children}</h6>,
                        ul: ({ children }) => <ul>{children}</ul>,
                        ol: ({ children }) => <ol>{children}</ol>,
                        li: ({ children }) => <li>{children}</li>,
                        a: ({ href, children }) => (
                            <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                {children}
                            </a>
                        ),
                        code: ({ inline, children, ...props }: any) =>
                            inline ? (
                                <code {...props}>{children}</code>
                            ) : (
                                <code {...props}>{children}</code>
                            ),
                        pre: ({ children }) => <pre>{children}</pre>,
                        blockquote: ({ children }) => (
                            <blockquote>{children}</blockquote>
                        ),
                        table: ({ children }) => <table>{children}</table>,
                        thead: ({ children }) => <thead>{children}</thead>,
                        tbody: ({ children }) => <tbody>{children}</tbody>,
                        tr: ({ children }) => <tr>{children}</tr>,
                        th: ({ children }) => <th>{children}</th>,
                        td: ({ children }) => <td>{children}</td>,
                        strong: ({ children }) => <strong>{children}</strong>,
                        em: ({ children }) => <em>{children}</em>,
                        hr: () => <hr />,
                    }}
                >
                    {message.content}
                </ReactMarkdown>
            </div>
            <button
                onClick={handleCopy}
                className={`p-2 rounded-xl transition-colors self-start ${
                    isCopied
                        ? "bg-green-100 text-green-600"
                        : "bg-gray-100 hover:bg-gray-200"
                }`}
                title="Копировать"
            >
                {isCopied ? <Check size={16} /> : <Copy size={16} />}
            </button>
        </div>
    );
};
