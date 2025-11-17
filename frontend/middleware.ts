import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
    const token = request.cookies.get("token")?.value;
    const { pathname } = request.nextUrl;

    // Защита /chat - только для авторизованных
    if (pathname.startsWith("/chat")) {
        if (!token) {
            return NextResponse.redirect(new URL("/login", request.url));
        }
    }
    console.log(pathname, token);
    // Редирект авторизованных пользователей с публичных страниц
    if (
        (pathname === "/login" ||
            pathname === "/register" ||
            pathname === "/") &&
        token
    ) {
        return NextResponse.redirect(new URL("/chat", request.url));
    }

    return NextResponse.next();
}

export const config = {
    matcher: ["/", "/chat/:path*", "/login", "/register"],
};
