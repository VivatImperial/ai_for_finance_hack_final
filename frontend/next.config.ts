/* eslint-disable no-undef */
import crypto from "crypto";
import path from "path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    compiler: {
        removeConsole:
            process.env.NODE_ENV === "production"
                ? {
                      exclude: ["error", "warn"],
                  }
                : false,
        styledComponents: true,
    },
    compress: true,

    eslint: {
        ignoreDuringBuilds: true,
    },

    env: {
        BUILD_ID: process.env.VERCEL_GIT_COMMIT_SHA || "local",
        BUILD_TIME: new Date().toISOString(),
    },

    experimental: {
        optimizeCss: true,
        reactCompiler: true,
        webpackBuildWorker: true,
    },

    turbopack: {
        rules: {
            "*.svg": {
                loaders: ["@svgr/webpack"],
                as: "*.js",
            },
        },
    },

    generateEtags: true,

    headers: async () => [
        {
            headers: [
                {
                    key: "X-Frame-Options",
                    value: "DENY",
                },
                {
                    key: "X-Content-Type-Options",
                    value: "nosniff",
                },
                {
                    key: "Referrer-Policy",
                    value: "strict-origin-when-cross-origin",
                },
                {
                    key: "X-DNS-Prefetch-Control",
                    value: "on",
                },
                {
                    key: "Strict-Transport-Security",
                    value: "max-age=31536000; includeSubDomains",
                },
                {
                    key: "Permissions-Policy",
                    value: "camera=(), microphone=(), geolocation=()",
                },
            ],
            source: "/(.*)",
        },
        {
            headers: [
                {
                    key: "Cache-Control",
                    value: "public, max-age=31536000, immutable",
                },
            ],
            source: "/static/(.*)",
        },
        {
            headers: [
                {
                    key: "Cache-Control",
                    value: "public, max-age=0, must-revalidate",
                },
            ],
            source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
        },
    ],

    images: {
        deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
        formats: ["image/avif", "image/webp"],
        imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
        minimumCacheTTL: 31536000,
        remotePatterns: [
            {
                hostname: "**",
                protocol: "https",
            },
            {
                hostname: "**",
                protocol: "http",
            },
        ],
    },

    output: "standalone",

    outputFileTracingRoot: __dirname,

    poweredByHeader: false,

    productionBrowserSourceMaps: false,

    reactStrictMode: true,

    sassOptions: {
        includePaths: ["./view/styles"],
        prependData: `@import "variables.css";`,
    },

    typescript: {
        ignoreBuildErrors: process.env.NODE_ENV === "production",
    },

    webpack: (config, { dev, isServer }) => {
        config.module.rules.push({
            test: /\.svg$/,
            use: ["@svgr/webpack"],
        });

        config.resolve.alias = {
            ...config.resolve.alias,
            "types/*": path.resolve(__dirname, "./types"),
            "view/*": path.resolve(__dirname, "./view/*"),
            "app/*": path.resolve(__dirname, "./app/*"),
            mocks: path.resolve(__dirname, "./mocks"),
            "mocks/*": path.resolve(__dirname, "./mocks/*"),
            "server/*": path.resolve(__dirname, "./server/*"),
            "@i18n/*": path.resolve(__dirname, "./i18n/*"),
            "@cypress/*": path.resolve(__dirname, "./cypress/*"),
            "@goji-core/*": path.resolve(__dirname, "./goji-core/*"),
            "@router/*": path.resolve(__dirname, "./router/*"),
            "@router": path.resolve(__dirname, "./router"),
        };

        if (!dev) {
            config.resolve.alias = {
                ...config.resolve.alias,
                lodash: "lodash-es",
            };
            config.devtool = false;

            if (!isServer) {
                config.optimization.splitChunks = {
                    chunks: "all",
                    cacheGroups: {
                        default: false,
                        vendors: false,
                        framework: {
                            chunks: "all",
                            enforce: true,
                            name: "framework",
                            priority: 40,
                            test: /(?<!node_modules.*)[\\/]node_modules[\\/](react|react-dom|scheduler|prop-types|use-subscription)[\\/]/,
                        },
                        lib: {
                            minChunks: 1,
                            name(module: {
                                identifier: () => string;
                                size: () => number;
                            }) {
                                const hash = crypto.createHash("sha1");
                                hash.update(module.identifier());
                                return hash.digest("hex").substring(0, 8);
                            },
                            priority: 30,
                            reuseExistingChunk: true,
                            test(module: { size: () => number }) {
                                return module.size() > 160000;
                            },
                        },
                        commons: {
                            minChunks: 2,
                            name: "commons",
                            priority: 20,
                        },
                    },
                    maxInitialRequests: 25,
                    minSize: 20000,
                };
            }
        }

        return config;
    },
};

export default nextConfig;
