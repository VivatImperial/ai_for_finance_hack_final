import { Button } from "@heroui/react";
import Link from "next/link";

export default function NotFound() {
    return (
        <div className="min-h-screen flex items-center justify-center bg-linear-to-br from-white via-gray-50 to-blue-50">
            <div className="max-w-3xl w-full px-8 text-center relative">
                {/* Декоративные элементы */}
                <div className="absolute -top-20 -left-20 w-64 h-64 bg-blue-100 rounded-full opacity-20 blur-3xl animate-pulse"></div>
                <div className="absolute -bottom-20 -right-20 w-64 h-64 bg-gray-200 rounded-full opacity-20 blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
                
                <div className="relative z-10">
                    {/* Крупный код ошибки с эффектом */}
                    <div className="mb-8">
                        <h1 className="text-[12rem] font-black text-transparent bg-clip-text bg-linear-to-r from-black via-gray-800 to-blue-600 leading-none mb-2 tracking-tighter">
                            404
                        </h1>
                        <div className="h-1 w-32 bg-linear-to-r from-blue-600 to-blue-400 mx-auto rounded-full"></div>
                    </div>

                    {/* Заголовок */}
                    <h2 className="text-4xl font-bold text-gray-900 mb-4 tracking-tight">
                        Страница не найдена
                    </h2>

                    {/* Описание */}
                    <p className="text-xl font-light text-gray-600 mb-12 max-w-md mx-auto leading-relaxed">
                        Запрашиваемая страница не существует или была перемещена
                    </p>

                    {/* Кнопка */}
                    <Link href="/">
                        <Button
                            size="lg"
                            radius="lg"
                            className="bg-blue-600 text-white font-medium hover:bg-blue-700 px-10 py-6 text-lg shadow-lg shadow-blue-600/30 hover:shadow-xl hover:shadow-blue-600/40 transition-all duration-300 min-w-[200px]"
                        >
                            На главную
                        </Button>
                    </Link>
                </div>
            </div>
        </div>
    );
}

