import { useState, useEffect } from 'react';

export const useTypingEffect = (text: string, totalDuration?: number) => {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    let currentIndex = 0;
    setDisplayedText('');
    setIsComplete(false);

    // Если указана общая длительность, рассчитываем задержку между символами
    // Иначе используем стандартную задержку 20мс
    const delay = totalDuration 
      ? Math.max(1, Math.floor(totalDuration / text.length)) // Минимум 1мс между символами
      : 20;

    const interval = setInterval(() => {
      if (currentIndex < text.length) {
        setDisplayedText((prev) => prev + text[currentIndex]);
        currentIndex++;
      } else {
        setIsComplete(true);
        clearInterval(interval);
      }
    }, delay);

    return () => clearInterval(interval);
  }, [text, totalDuration]);

  return { displayedText, isComplete };
};

