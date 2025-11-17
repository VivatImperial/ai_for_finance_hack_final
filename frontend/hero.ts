import { heroui } from "@heroui/react";

export default heroui({
    themes: {
        light: {
            colors: {
                primary: {
                    DEFAULT: "#2e2e2e",
                    foreground: "#fff",
                },
                warning: {
                    DEFAULT: "#ABC5E5",
                    foreground: "#fff",
                },
                secondary: {
                    DEFAULT: "#CACACA",
                    foreground: "#fff",
                },
            },
        },
        dark: {
            colors: {},
        },
    },
});
