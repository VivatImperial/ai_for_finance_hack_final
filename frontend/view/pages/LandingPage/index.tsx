"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button, Input } from "@heroui/react";
import { isAuthenticated } from "@/view/libs/auth";
import { Paperclip } from "lucide-react";

export const LandingPage = () => {
    const router = useRouter();

    useEffect(() => {
        if (isAuthenticated()) {
            router.push("/chat");
        }
    }, [router]);

    const handleInputClick = () => {
        router.push("/login");
    };

    const handleLoginClick = () => {
        router.push("/login");
    };

    const handleRegisterClick = () => {
        router.push("/register");
    };

    return (
        <div className="flex flex-col min-h-screen">
            <div className="flex justify-end items-center gap-2 w-full p-4">
                <Button
                    onPress={handleLoginClick}
                    radius="full"
                    color="primary"
                >
                    Войти
                </Button>
                <Button
                    onPress={handleRegisterClick}
                    variant="bordered"
                    radius="full"
                >
                    Регистрация
                </Button>
            </div>

            <div className="flex flex-col items-center justify-center flex-1 px-4">
                <div className="flex flex-col items-center gap-8 w-full max-w-4xl">
                    <h1 className="text-5xl font-bold text-gray-900 text-center">
                        Готов помочь вам с документами
                    </h1>

                    <p className="text-gray-600 text-lg text-center">
                        Чтобы хранить документы в базе{" "}
                        <span
                            className="underline cursor-pointer hover:text-gray-900 transition-colors"
                            onClick={handleLoginClick}
                        >
                            войдите
                        </span>{" "}
                        в аккаунт
                    </p>

                    <div className="w-full" onClick={handleInputClick}>
                        <Input
                            type="text"
                            placeholder="Спросите что-нибудь или перетащите файл"
                            readOnly
                            radius="full"
                            size="lg"
                            classNames={{
                                input: "cursor-pointer py-6",
                                inputWrapper:
                                    "cursor-pointer bg-white rounded-2xl shadow-md px-6 py-8",
                            }}
                            endContent={
                                <div className="flex items-center gap-2">
                                    <Button
                                        variant="light"
                                        radius="full"
                                        startContent={
                                            <Paperclip className="w-5 h-5" />
                                        }
                                        isDisabled
                                    >
                                        Файл
                                    </Button>
                                    <Button radius="full" color="primary">
                                        Отправить
                                    </Button>
                                </div>
                            }
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};
