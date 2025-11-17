import { z } from "zod";

export const loginSchema = z.object({
    email: z.string().email("Некорректный email"),
    password: z.string().min(1, "Введите пароль"),
});

export type ILoginForm = z.infer<typeof loginSchema>;
