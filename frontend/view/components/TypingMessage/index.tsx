import { useEffect, useRef } from 'react';
import { useTypingEffect } from '@/view/hooks/useTypingEffect';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

interface ITypingMessageProps {
  content: string;
  onComplete: () => void;
  speed?: number; // Общее время анимации в миллисекундах
  onTextUpdate?: () => void; // Callback для скролла во время печати
}

export const TypingMessage = ({ content, onComplete, speed, onTextUpdate }: ITypingMessageProps) => {
  const { displayedText, isComplete } = useTypingEffect(content, speed);
  const hasCalledCompleteRef = useRef(false);

  // Вызываем onComplete в useEffect, а не во время рендера
  useEffect(() => {
    if (isComplete && !hasCalledCompleteRef.current) {
      hasCalledCompleteRef.current = true;
      onComplete();
    }
  }, [isComplete, onComplete]);

  // Скролл во время печати
  useEffect(() => {
    if (displayedText && onTextUpdate) {
      onTextUpdate();
    }
  }, [displayedText, onTextUpdate]);

  // Сбрасываем флаг при изменении content
  useEffect(() => {
    hasCalledCompleteRef.current = false;
  }, [content]);

  return (
    <div className="flex flex-col gap-4 items-start animate-fade-in-up">
      <div className="text-gray-600 text-sm">
        {new Date().toLocaleTimeString("ru-RU", {
          hour: "2-digit",
          minute: "2-digit",
        })}
      </div>
      <div className="max-w-[70%] text-black">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
          {displayedText}
        </ReactMarkdown>
      </div>
    </div>
  );
};

