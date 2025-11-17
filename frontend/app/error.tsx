"use client";

import { Button } from "@heroui/react";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    const router = useRouter();
    const status = (error as any)?.status;
    const is401 =
        status === 401 ||
        error.message?.includes("401") ||
        error.digest?.includes("401");

    useEffect(() => {
        // Логирование ошибки можно добавить здесь
        console.error(error);

        // Удаляем токены при ошибке 401
        if (is401) {
            Cookies.remove("token");
            Cookies.remove("token_type");
            Cookies.remove("refresh_token");
        }
    }, [error, is401]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-linear-to-br from-white via-gray-50 to-blue-50">
            <div className="max-w-3xl w-full px-8 text-center relative">
                {/* Декоративный элемент */}
                <div className="absolute -top-20 -left-20 w-64 h-64 bg-blue-100 rounded-full opacity-20 blur-3xl animate-pulse"></div>
                <div
                    className="absolute -bottom-20 -right-20 w-64 h-64 bg-gray-200 rounded-full opacity-20 blur-3xl animate-pulse"
                    style={{ animationDelay: "1s" }}
                ></div>

                <div className="relative z-10">
                    {/* Крупный код ошибки с эффектом */}
                    <div className="mb-8">
                        <h1 className="text-[12rem] font-black text-transparent bg-clip-text bg-linear-to-r from-black via-gray-800 to-blue-600 leading-none mb-2 tracking-tighter">
                            {is401 ? "401" : "!"}
                        </h1>
                        <div className="h-1 w-32 bg-linear-to-r from-blue-600 to-blue-400 mx-auto rounded-full"></div>
                    </div>

                    {/* Заголовок */}
                    <h2 className="text-4xl font-bold text-gray-900 mb-4 tracking-tight">
                        {is401
                            ? "Необходима авторизация"
                            : "Что-то пошло не так"}
                    </h2>

                    {/* Описание */}
                    <p className="text-xl font-light text-gray-600 mb-12 max-w-md mx-auto leading-relaxed">
                        {is401
                            ? "Пожалуйста, войдите в систему для доступа к этой странице"
                            : "Произошла непредвиденная ошибка. Попробуйте обновить страницу или вернуться на главную."}
                    </p>

                    {/* Кнопки */}
                    <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                        <Button
                            onPress={() => {
                                if (is401) {
                                    window.location.href = "/login";
                                } else {
                                    window.location.reload();
                                }
                            }}
                            size="lg"
                            radius="lg"
                            className="bg-blue-600 text-white font-medium hover:bg-blue-700 px-10 py-6 text-lg shadow-lg shadow-blue-600/30 hover:shadow-xl hover:shadow-blue-600/40 transition-all duration-300 min-w-[200px]"
                        >
                            {is401 ? "Войти в систему" : "Попробовать снова"}
                        </Button>
                        {!is401 && (
                            <Button
                                onClick={() => router.push("/")}
                                size="lg"
                                radius="lg"
                                variant="bordered"
                                className="border-2 border-gray-300 text-gray-700 font-medium hover:bg-gray-100 hover:border-gray-400 px-10 py-6 text-lg transition-all duration-300 min-w-[200px]"
                            >
                                На главную
                            </Button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
