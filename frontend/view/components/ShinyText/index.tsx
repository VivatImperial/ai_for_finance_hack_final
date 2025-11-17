import React from "react";

interface ShinyTextProps {
    text: string;
    disabled?: boolean;
    speed?: number;
    className?: string;
}

const ShinyText: React.FC<ShinyTextProps> = ({
    text,
    disabled = false,
    speed = 5,
    className = "",
}) => {
    const animationDuration = `${speed}s`;

    return (
        <span className={`relative inline-block ${className}`}>
            {/* Черный текст */}
            <span style={{ color: "#b5b5b5a4" }}>{text}</span>
            {/* Градиент поверх текста */}
            <span
                className={`absolute left-0 top-0 inline-block ${disabled ? "" : "animate-shine"}`}
                style={{
                    backgroundImage:
                        "linear-gradient(120deg, rgba(255, 255, 255, 0) 40%, rgba(255, 255, 255, 0.8) 50%, rgba(255, 255, 255, 0) 60%)",
                    backgroundSize: "200% 100%",
                    WebkitBackgroundClip: "text",
                    backgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    color: "transparent",
                    animationDuration: disabled ? undefined : animationDuration,
                    pointerEvents: "none",
                    mixBlendMode: "lighten",
                }}
            >
                {text}
            </span>
        </span>
    );
};

export default ShinyText;
