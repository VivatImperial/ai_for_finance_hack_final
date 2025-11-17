import Orb from "@/view/components/Orb";

export default function AuthLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="relative min-h-screen overflow-hidden">
            {/* Animated background - persists across auth pages */}
            <div className="fixed inset-0 flex items-center justify-center opacity-30 pointer-events-none z-0">
                <div className="w-[800px] h-[800px]">
                    <Orb
                        hue={240}
                        hoverIntensity={0}
                        rotateOnHover={false}
                        forceHoverState={false}
                    />
                </div>
            </div>

            {/* Content */}
            <div className="relative z-10">{children}</div>
        </div>
    );
}
