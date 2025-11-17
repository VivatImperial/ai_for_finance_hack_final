import { useState, useEffect, useRef } from "react";
import {
    useGetDocumentsForUserApiV1DocumentGet,
    useDeleteDocumentApiV1DocumentDocumentIdDelete,
    getGetDocumentsForUserApiV1DocumentGetQueryKey,
} from "@/server/generated";
import { addToast } from "@heroui/react";
import { useQueryClient } from "@tanstack/react-query";
import type { IUploadingFile } from "@/types/document";
import { useAttachedDocuments } from "@/view/libs/AttachedDocumentsContext";

export const useDocumentPanel = () => {
    const queryClient = useQueryClient();
    const { attachedDocuments, setAttachedDocuments } = useAttachedDocuments();
    const attachedDocumentIds = attachedDocuments.map((doc) => doc.id);
    const [selectedIds, setSelectedIds] = useState<number[]>([]);
    const [isUploadView, setIsUploadView] = useState(false);
    const [uploadingFiles, setUploadingFiles] = useState<IUploadingFile[]>([]);
    const prevAttachedIdsRef = useRef<number[]>([]);
    const documentsRef = useRef<any[]>([]);
    const isSyncingFromContextRef = useRef(false);

    // Sync selectedIds with attachedDocumentIds from context
    useEffect(() => {
        // Only sync if the array actually changed
        const idsChanged =
            prevAttachedIdsRef.current.length !== attachedDocumentIds.length ||
            !prevAttachedIdsRef.current.every(
                (id, idx) => id === attachedDocumentIds[idx]
            );

        if (idsChanged) {
            isSyncingFromContextRef.current = true;
            if (attachedDocumentIds.length > 0) {
                setSelectedIds(attachedDocumentIds);
            } else {
                // Only clear if we had attached documents before
                if (prevAttachedIdsRef.current.length > 0) {
                    setSelectedIds([]);
                }
            }
            prevAttachedIdsRef.current = [...attachedDocumentIds];
            // Reset flag after state update
            setTimeout(() => {
                isSyncingFromContextRef.current = false;
            }, 0);
        }
    }, [attachedDocumentIds]);

    const { data: documentsResponse, isLoading } =
        useGetDocumentsForUserApiV1DocumentGet();
    const serverDocuments =
        documentsResponse?.status === 200 ? documentsResponse.data : [];

    // Combine server documents with uploading files (without errors)
    // Filter out uploading files that already exist in serverDocuments (by filename)
    const serverFilenames = new Set(
        serverDocuments.map((doc) => doc.filename.toLowerCase())
    );

    const uploadingDocuments = uploadingFiles
        .filter(
            (file) =>
                !file.error &&
                !serverFilenames.has(file.file.name.toLowerCase())
        )
        .map((file, index) => {
            // Generate a unique negative ID based on file.id hash
            // Convert string ID to a number hash to ensure uniqueness
            let hash = 0;
            for (let i = 0; i < file.id.length; i++) {
                const char = file.id.charCodeAt(i);
                hash = (hash << 5) - hash + char;
                hash = hash & hash; // Convert to 32-bit integer
            }
            // Use negative hash with index to ensure uniqueness
            // Multiply by large number and add index to avoid collisions
            const uniqueId = -(Math.abs(hash) * 1000 + index);

            return {
                document_id: uniqueId,
                filename: file.file.name,
                minio_url: "",
                created_at: new Date().toISOString(),
                is_general: false,
                isUploading: true,
                progress: file.progress,
                uploadId: file.id, // Store original upload ID for reference
            };
        });

    const documents = [...serverDocuments, ...uploadingDocuments];

    // Update documents ref for use in toggleSelection
    useEffect(() => {
        documentsRef.current = documents;
    }, [documents]);

    const deleteMutation = useDeleteDocumentApiV1DocumentDocumentIdDelete({
        mutation: {
            onSuccess: () => {
                // Invalidation will be handled in handleDelete after all deletions
            },
            onError: () => {
                addToast({
                    title: "Ошибка удаления документа",
                    color: "danger",
                });
            },
        },
    });

    const toggleSelection = (id: number) => {
        setSelectedIds((prev) =>
            prev.includes(id)
                ? prev.filter((docId) => docId !== id)
                : [...prev, id]
        );
    };

    // Sync context with selectedIds when it changes (but not from context sync)
    useEffect(() => {
        // Skip if this change came from context sync
        if (isSyncingFromContextRef.current) {
            return;
        }

        const selectedDocs = documentsRef.current
            .filter(
                (doc) =>
                    selectedIds.includes(doc.document_id) &&
                    !(doc as any).isUploading
            )
            .map((doc) => ({
                id: doc.document_id,
                name: doc.filename,
            }));

        // Only update if different
        const currentIds = attachedDocuments
            .map((doc) => doc.id)
            .sort((a, b) => a - b);
        const newIds = selectedDocs.map((doc) => doc.id).sort((a, b) => a - b);
        const areEqual =
            currentIds.length === newIds.length &&
            currentIds.every((id, idx) => id === newIds[idx]);

        if (!areEqual) {
            setAttachedDocuments(selectedDocs);
        }
    }, [selectedIds, attachedDocuments, setAttachedDocuments]);

    const clearSelection = () => {
        setSelectedIds([]);
        setAttachedDocuments([]);
    };

    const handleDelete = async () => {
        const idsToDelete = [...selectedIds];
        try {
            // Delete all files in parallel
            await Promise.all(
                idsToDelete.map((id) =>
                    deleteMutation.mutateAsync({ documentId: id })
                )
            );

            // Invalidate queries after all deletions are complete
            // This will automatically trigger a refetch for active queries
            queryClient.invalidateQueries({
                queryKey: getGetDocumentsForUserApiV1DocumentGetQueryKey(),
            });

            // Show success toast
            if (idsToDelete.length === 1) {
                addToast({ title: "Документ удален", color: "success" });
            } else {
                addToast({
                    title: `Удалено документов: ${idsToDelete.length}`,
                    color: "success",
                });
            }

            // Clear selection after successful deletion
            clearSelection();
        } catch (error) {
            // Error handling is done in mutation onError
            console.error("Error deleting documents:", error);
        }
    };

    const handleDownload = (minioUrl: string, filename: string) => {
        const link = document.createElement("a");
        link.href = minioUrl;
        link.download = filename;
        link.target = "_blank";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const switchToUploadView = () => {
        setIsUploadView(true);
    };

    const switchToMainView = () => {
        setIsUploadView(false);
    };

    const addUploadingFiles = (files: IUploadingFile[]) => {
        setUploadingFiles((prev) => [...prev, ...files]);
    };

    const updateUploadingFile = (
        id: string,
        updates: Partial<IUploadingFile>
    ) => {
        setUploadingFiles((prev) =>
            prev.map((f) => (f.id === id ? { ...f, ...updates } : f))
        );
    };

    const removeUploadingFile = (id: string) => {
        setUploadingFiles((prev) => prev.filter((f) => f.id !== id));
    };

    // Automatically remove uploading files when they appear in serverDocuments
    useEffect(() => {
        if (serverDocuments.length === 0 || uploadingFiles.length === 0) return;

        const serverFilenames = new Set(
            serverDocuments.map((doc) => doc.filename.toLowerCase())
        );
        const filesToRemove: string[] = [];

        uploadingFiles.forEach((file) => {
            if (serverFilenames.has(file.file.name.toLowerCase())) {
                filesToRemove.push(file.id);
            }
        });

        if (filesToRemove.length > 0) {
            filesToRemove.forEach((id) => {
                removeUploadingFile(id);
            });
        }
    }, [serverDocuments, uploadingFiles, removeUploadingFile]);

    return {
        documents,
        isLoading,
        selectedIds,
        toggleSelection,
        clearSelection,
        handleDelete,
        handleDownload,
        isUploadView,
        switchToUploadView,
        switchToMainView,
        isDeleting: deleteMutation.isPending,
        uploadingFiles,
        addUploadingFiles,
        updateUploadingFile,
        removeUploadingFile,
        queryClient,
    };
};
