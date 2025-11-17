"use client";

import Link from "next/link";
import { Button, Input } from "@heroui/react";
import { useRegisterPage } from "./useRegisterPage";

export const RegisterPage = () => {
    const { form, onSubmit, isLoading } = useRegisterPage();
    const {
        register,
        handleSubmit,
        formState: { errors },
    } = form;

    return (
        <div className="min-h-screen flex items-center justify-center p-4">
            <div className="max-w-md w-full px-8">
                <h1 className="text-4xl font-normal text-center mb-3 text-gray-900">
                    Регистрация
                </h1>
                <p className="text-center text-lg font-light text-gray-600 mb-12">
                    Есть аккаунт?{" "}
                    <Link href="/login" className="text-black underline">
                        Войдите
                    </Link>
                </p>

                <form
                    onSubmit={handleSubmit(onSubmit)}
                    className="flex flex-col gap-4"
                >
                    <div className="flex flex-col">
                        <label
                            htmlFor="email"
                            className="block text-sm font-normal text-gray-700 mb-2"
                        >
                            Почта
                        </label>
                        <Input
                            {...register("email")}
                            id="email"
                            type="email"
                            placeholder="example@mail.ru"
                            radius="lg"
                            size="lg"
                            isInvalid={!!errors.email}
                            errorMessage={errors.email?.message}
                            classNames={{
                                input: "text-base",
                                inputWrapper:
                                    "bg-gray-100 border-0 shadow-none",
                            }}
                        />
                    </div>

                    <div className="flex flex-col">
                        <label
                            htmlFor="password"
                            className="block text-sm font-normal text-gray-700 mb-2"
                        >
                            Пароль
                        </label>
                        <Input
                            {...register("password")}
                            id="password"
                            type="password"
                            placeholder="password"
                            radius="lg"
                            size="lg"
                            isInvalid={!!errors.password}
                            errorMessage={errors.password?.message}
                            classNames={{
                                input: "text-base",
                                inputWrapper:
                                    "bg-gray-100 border-0 shadow-none",
                            }}
                        />
                    </div>

                    <div className="flex flex-col">
                        <label
                            htmlFor="confirmPassword"
                            className="block text-sm font-normal text-gray-700 mb-2"
                        >
                            Повторите пароль
                        </label>
                        <Input
                            {...register("confirmPassword")}
                            id="confirmPassword"
                            type="password"
                            placeholder="password"
                            radius="lg"
                            size="lg"
                            isInvalid={!!errors.confirmPassword}
                            errorMessage={errors.confirmPassword?.message}
                            classNames={{
                                input: "text-base",
                                inputWrapper:
                                    "bg-gray-100 border-0 shadow-none",
                            }}
                        />
                    </div>

                    <Button
                        type="submit"
                        fullWidth
                        isDisabled={isLoading}
                        isLoading={isLoading}
                        radius="lg"
                        size="lg"
                        className="mt-6 bg-gray-200 text-gray-900 font-normal hover:bg-gray-300"
                    >
                        {isLoading ? "Создание аккаунта..." : "Создать аккаунт"}
                    </Button>
                </form>
            </div>
        </div>
    );
};
