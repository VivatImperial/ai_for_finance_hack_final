"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

interface AttachedDocument {
    id: number;
    name: string;
}

interface AttachedDocumentsContextType {
    attachedDocuments: AttachedDocument[];
    addAttachment: (id: number, name: string) => void;
    removeAttachment: (id: number) => void;
    setAttachedDocuments: (documents: AttachedDocument[]) => void;
    clearAttachments: () => void;
}

const AttachedDocumentsContext = createContext<
    AttachedDocumentsContextType | undefined
>(undefined);

export const AttachedDocumentsProvider = ({
    children,
}: {
    children: ReactNode;
}) => {
    const [attachedDocuments, setAttachedDocuments] = useState<
        AttachedDocument[]
    >([]);

    const addAttachment = useCallback((id: number, name: string) => {
        setAttachedDocuments((prev) => {
            if (!prev.some((doc) => doc.id === id)) {
                return [...prev, { id, name }];
            }
            return prev;
        });
    }, []);

    const removeAttachment = useCallback((id: number) => {
        setAttachedDocuments((prev) => prev.filter((doc) => doc.id !== id));
    }, []);

    const clearAttachments = useCallback(() => {
        setAttachedDocuments([]);
    }, []);

    const setAttachedDocumentsCallback = useCallback((documents: AttachedDocument[]) => {
        setAttachedDocuments(documents);
    }, []);

    return (
        <AttachedDocumentsContext.Provider
            value={{
                attachedDocuments,
                addAttachment,
                removeAttachment,
                setAttachedDocuments: setAttachedDocumentsCallback,
                clearAttachments,
            }}
        >
            {children}
        </AttachedDocumentsContext.Provider>
    );
};

export const useAttachedDocuments = () => {
    const context = useContext(AttachedDocumentsContext);
    if (context === undefined) {
        throw new Error(
            "useAttachedDocuments must be used within an AttachedDocumentsProvider"
        );
    }
    return context;
};

