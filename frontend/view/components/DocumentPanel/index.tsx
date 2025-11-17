import {
    Upload,
    Download,
    Trash2,
    FileText,
    X,
    CheckCircle,
    AlertCircle,
    ArrowRight,
    File,
    Paperclip,
    ArrowLeft,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { Button, Checkbox, Progress } from "@heroui/react";
import { useDocumentPanel } from "./useDocumentPanel";
import { FileUploadView } from "@/view/components/FileUploadView";
import { useAttachedDocuments } from "@/view/libs/AttachedDocumentsContext";

interface IDocumentPanelProps {
    isOpen: boolean;
    onToggle: () => void;
}

// Helper function to get file icon based on extension
const getFileIcon = (filename: string) => {
    const extension = filename.split(".").pop()?.toLowerCase();
    switch (extension) {
        case "pdf":
            return (
                <Image
                    src="/images/pdf.png"
                    alt="PDF"
                    width={24}
                    height={24}
                    className="w-6 h-6"
                />
            );
        case "docx":
        case "doc":
            return (
                <Image
                    src="/images/word.png"
                    alt="Word"
                    width={24}
                    height={24}
                    className="w-6 h-6"
                />
            );
        case "txt":
            return (
                <Image
                    src="/images/txt.png"
                    alt="Text"
                    width={24}
                    height={24}
                    className="w-6 h-6"
                />
            );
        default:
            return (
                <Image
                    src="/images/txt.png"
                    alt="File"
                    width={24}
                    height={24}
                    className="w-6 h-6"
                />
            );
    }
};

export const DocumentPanel = ({
    isOpen,
    onToggle,
}: IDocumentPanelProps) => {
    const { attachedDocuments } = useAttachedDocuments();
    const attachedDocumentIds = attachedDocuments.map(doc => doc.id);
    const panelRef = useRef<HTMLDivElement>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [dragOffset, setDragOffset] = useState(0);
    const dragOffsetRef = useRef<number>(0);
    const dragStartX = useRef<number>(0);
    const dragStartIsOpen = useRef<boolean>(false);
    const isHandlingDrag = useRef<boolean>(false);
    const clickOutsideHandled = useRef<boolean>(false);

    const {
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
        uploadingFiles,
        addUploadingFiles,
        updateUploadingFile,
        removeUploadingFile,
        queryClient,
    } = useDocumentPanel();

    // Handle drag to open/close panel
    const dragStartY = useRef<number>(0);
    const panelWidth = 920;
    const openThreshold = 50; // Distance to drag to fully open/close

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDragging) return;

            // Calculate horizontal movement relative to start position
            // Use pageX to handle scroll correctly
            // Positive deltaX = mouse moved left, Negative deltaX = mouse moved right
            const deltaX = dragStartX.current - e.pageX;

            // Calculate new offset based on initial state
            let newOffset = 0;
            if (dragStartIsOpen.current) {
                // Panel was open (at translateX(0)), dragging right closes it
                // When dragging right, deltaX is negative, so -deltaX is positive
                // Limit from 0 (fully open) to panelWidth (fully closed)
                newOffset = Math.max(0, Math.min(panelWidth, -deltaX));
            } else {
                // Panel was closed (at translateX(panelWidth)), dragging left opens it
                // When dragging left, deltaX is positive (e.g., if startX=1000, currentX=900, deltaX=100)
                // We need negative offset to move from panelWidth (920px) towards 0
                // So if deltaX = 100, offset should be -100, moving panel to 820px
                // Limit from -panelWidth (fully open) to 0 (fully closed)
                if (deltaX > 0) {
                    // Dragging left - opening the panel, offset should be negative
                    newOffset = Math.max(-panelWidth, Math.min(0, -deltaX));
                } else {
                    // Dragging right or no movement - keep closed
                    newOffset = 0;
                }
            }

            dragOffsetRef.current = newOffset;
            setDragOffset(newOffset);
        };

        const handleMouseUp = (e: MouseEvent) => {
            if (!isDragging) return;

            // If click outside was already handled, don't do anything
            if (clickOutsideHandled.current) {
                setDragOffset(0);
                setIsDragging(false);
                return;
            }

            // Mark that we're handling drag to prevent click outside handler
            isHandlingDrag.current = true;

            // Check if mouse is still over the button or panel
            const toggleButton = document.getElementById("panel-toggle-button");
            const isOverButton = toggleButton?.contains(e.target as Node);
            const isOverPanel = panelRef.current?.contains(e.target as Node);

            const deltaX = Math.abs(e.pageX - dragStartX.current);
            const deltaY = Math.abs(e.pageY - dragStartY.current);
            const absDragOffset = Math.abs(dragOffsetRef.current);
            const dragOffset = dragOffsetRef.current;
            const dragDirection = dragStartX.current - e.pageX; // Positive = left, Negative = right

            // Only handle toggle if mouse is over button or panel
            if (isOverButton || isOverPanel) {
                // Determine if we should toggle based on drag distance
                if (deltaX < 5 && deltaY < 5) {
                    // Simple click without drag - toggle panel
                    e.stopPropagation(); // Prevent click outside handler
                    onToggle();
                } else if (absDragOffset > openThreshold && deltaX > deltaY) {
                    // Dragged more than threshold - check direction matches intent
                    e.stopPropagation(); // Prevent click outside handler

                    if (dragStartIsOpen.current) {
                        // Was open - should close if dragged right
                        if (dragDirection < 0 && isOpen) {
                            onToggle();
                        }
                    } else {
                        // Was closed - should open if dragged left
                        if (dragDirection > 0 && !isOpen) {
                            onToggle();
                        }
                    }
                } else {
                    // Dragged less than threshold - revert to original state
                    e.stopPropagation(); // Prevent click outside handler
                    if (dragStartIsOpen.current !== isOpen) {
                        onToggle();
                    }
                }
            }

            setDragOffset(0);
            setIsDragging(false);

            // Reset flag after a short delay to allow event propagation to complete
            setTimeout(() => {
                isHandlingDrag.current = false;
            }, 0);
        };

        if (isDragging) {
            // Use capture phase to ensure events are caught even if mouse leaves button area
            document.addEventListener("mousemove", handleMouseMove, {
                passive: true,
            });
            document.addEventListener("mouseup", handleMouseUp, {
                capture: true,
            });
            document.body.style.cursor = "grab";
            document.body.style.userSelect = "none";
        }

        return () => {
            document.removeEventListener("mousemove", handleMouseMove);
            document.removeEventListener("mouseup", handleMouseUp);
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
        };
    }, [isDragging, onToggle, isOpen]);

    // Handle click outside to close
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            // Don't handle click outside if we're currently dragging or handling drag
            if (isDragging || isHandlingDrag.current) return;
            if (!isOpen) return;

            const target = event.target as HTMLElement;
            if (!target) return;

            const toggleButton = document.getElementById("panel-toggle-button");
            const fileInput = document.getElementById("file-input");
            
            // Use composedPath to get full event path (works with portals and shadow DOM)
            const path = event.composedPath ? event.composedPath() : [];
            
            // Check if click is on button or its children
            const isOverButton = toggleButton?.contains(target) || 
                                path.some((node) => node === toggleButton);
            
            // Check if click is on file input or its trigger
            const isOverFileInput = fileInput?.contains(target) || 
                                   target.id === "file-input" ||
                                   path.some((node) => node === fileInput);
            
            // Check if click is inside panel - more robust check using composedPath
            let isOverPanel = false;
            if (panelRef.current) {
                // Check if target is inside panel
                isOverPanel = panelRef.current.contains(target);
                
                // Check event path for panel element
                if (!isOverPanel) {
                    isOverPanel = path.some((node) => {
                        if (node === panelRef.current) return true;
                        if (node instanceof HTMLElement) {
                            return node.hasAttribute('data-panel-content') || 
                                   panelRef.current?.contains(node);
                        }
                        return false;
                    });
                }
                
                // Also check if any parent element is inside panel (for portals or nested elements)
                if (!isOverPanel) {
                    let parent = target.parentElement;
                    while (parent && parent !== document.body) {
                        if (panelRef.current.contains(parent) || 
                            parent.hasAttribute('data-panel-content')) {
                            isOverPanel = true;
                            break;
                        }
                        parent = parent.parentElement;
                    }
                }
            }

            // Close panel only if clicked outside both panel and button
            if (!isOverButton && !isOverPanel && !isOverFileInput) {
                clickOutsideHandled.current = true;
                onToggle();
                // Reset flag after a short delay
                setTimeout(() => {
                    clickOutsideHandled.current = false;
                }, 100);
            }
        };

        // Use bubble phase to allow React handlers to process first
        document.addEventListener("mousedown", handleClickOutside, {
            capture: false,
        });
        return () =>
            document.removeEventListener("mousedown", handleClickOutside, {
                capture: false,
            });
    }, [isOpen, onToggle, isDragging]);

    const handleDragStart = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();

        // Store initial state - use pageX instead of clientX to handle scroll
        dragStartX.current = e.pageX;
        dragStartY.current = e.pageY;
        dragStartIsOpen.current = isOpen;
        dragOffsetRef.current = 0;
        setDragOffset(0);

        // Start dragging
        setIsDragging(true);
    };

    return (
        <>
            <div
                ref={panelRef}
                data-panel-content
                className={`dark fixed right-0 top-0 h-full w-[920px] z-30 ${
                    !isDragging ? "transition-transform duration-300" : ""
                }`}
                style={{
                    backgroundColor: "#2B2D33",
                    transform: isDragging
                        ? dragStartIsOpen.current
                            ? `translateX(${dragOffset}px)`
                            : `translateX(${panelWidth + dragOffset}px)`
                        : isOpen
                          ? "translateX(0)"
                          : `translateX(${panelWidth}px)`,
                }}
            >
                {/* Toggle button with slanted design */}
                <button
                    id="panel-toggle-button"
                    onMouseDown={handleDragStart}
                    className={`absolute left-0 top-1/2 -translate-y-1/2 -translate-x-full text-white transition-all flex flex-col gap-4 justify-center items-center py-6 select-none ${
                        isDragging ? "cursor-grabbing" : "cursor-grab"
                    }`}
                    style={{
                        width: "48px",
                        height: "220px",
                        backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='249' viewBox='0 0 60 249' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M60 248.944C57.3297 248.722 54.6819 248.037 52.1836 246.976C41.0341 242.239 26.4639 237.971 15.5537 235.078C6.4972 232.677 0 224.566 0 215.196V33.8008C0 24.6303 6.25597 16.6883 15.0947 14.2441C28.5001 10.5373 39.1652 6.93636 53.2354 1.41113C55.4096 0.557329 57.6987 0.0833446 60 0V248.944Z' fill='%232B2D33'/%3E%3C/svg%3E")`,
                        backgroundSize: "cover",
                        backgroundPosition: "center",
                        backgroundRepeat: "no-repeat",
                    }}
                    title={
                        isOpen
                            ? "Перетащите для закрытия панели"
                            : "Перетащите для открытия документов"
                    }
                >
                    <span
                        className="text-md tracking-wider"
                        style={{
                            writingMode: "vertical-rl",
                            textOrientation: "mixed",
                            transform: "rotate(180deg)",
                        }}
                    >
                        Документы
                    </span>
                    <div className="p-1 rounded-full flex items-center justify-center border-2 border-yellow-500">
                        <ArrowRight
                            size={14}
                            className={`text-yellow-500 transition-transform duration-300 stroke-2 ${
                                isOpen ? "rotate-180" : ""
                            }`}
                            strokeWidth={2}
                        />
                    </div>
                </button>
                <div className="h-full flex flex-col">
                    {/* Fixed header - always visible */}
                    <div className="p-6 border-b border-gray-700">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-semibold text-white">
                                У вас{" "}
                                <span className="text-gray-500 underline">
                                    {documents.length}
                                </span>{" "}
                                файлов
                            </h2>
                            <div className="flex gap-2">
                                <Button
                                    onPress={switchToMainView}
                                    radius="full"
                                    className={
                                        !isUploadView
                                            ? "bg-transparent border-2 border-yellow-500 text-white"
                                            : ""
                                    }
                                    color={!isUploadView ? "default" : "default"}
                                >
                                    Документы
                                </Button>
                                <Button
                                    onPress={switchToUploadView}
                                    radius="full"
                                    className={
                                        isUploadView
                                            ? "bg-transparent border-2 border-yellow-500 text-white"
                                            : ""
                                    }
                                    color={isUploadView ? "default" : "default"}
                                >
                                    Загрузить документ
                                </Button>
                            </div>
                        </div>

                    </div>

                    {/* Content area that changes based on view */}
                    {isUploadView ? (
                        <FileUploadView
                            onComplete={switchToMainView}
                            addUploadingFiles={addUploadingFiles}
                            updateUploadingFile={updateUploadingFile}
                            removeUploadingFile={removeUploadingFile}
                            queryClient={queryClient}
                        />
                    ) : (
                        <div className="flex-1 overflow-y-auto p-6">
                            {isLoading ? (
                                <div className="space-y-3">
                                    {[1, 2, 3].map((i) => (
                                        <div
                                            key={i}
                                            className="h-24 bg-gray-800 rounded-lg animate-pulse"
                                        />
                                    ))}
                                </div>
                            ) : documents.length === 0 ? (
                                <div className="text-center py-12 text-gray-400">
                                    <FileText
                                        size={48}
                                        className="mx-auto mb-4 opacity-30"
                                    />
                                    <p className="font-medium mb-1 text-gray-300">
                                        Нет документов
                                    </p>
                                    <p className="text-sm">
                                        Загрузите первый документ
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-1">
                                    {documents.map((doc) => {
                                        const isUploading = (doc as any).isUploading;
                                        const progress = (doc as any).progress;
                                        return (
                                            <div
                                                key={doc.document_id}
                                                onClick={() => {
                                                    if (!isUploading) {
                                                        toggleSelection(doc.document_id);
                                                    }
                                                }}
                                                className={`px-4 py-3 cursor-pointer transition-colors hover:bg-gray-800/30 ${
                                                    isUploading ? "opacity-50" : ""
                                                }`}
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div className="flex-shrink-0">
                                                        {getFileIcon(doc.filename)}
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <p className="font-medium text-white truncate">
                                                            {doc.filename}
                                                        </p>
                                                        {!isUploading && (
                                                            <p className="text-xs text-gray-400 mt-1">
                                                                {new Date(
                                                                    doc.created_at
                                                                ).toLocaleDateString(
                                                                    "ru-RU"
                                                                )}
                                                            </p>
                                                        )}
                                                        {isUploading && progress !== undefined && (
                                                            <Progress
                                                                value={progress}
                                                                color="primary"
                                                                size="sm"
                                                                className="mt-2"
                                                            />
                                                        )}
                                                        {doc.is_general && (
                                                            <span className="inline-block mt-2 px-2 py-1 text-xs bg-green-900/50 text-green-300 rounded">
                                                                Общий
                                                            </span>
                                                        )}
                                                    </div>
                                                    {!isUploading && (
                                                        <div
                                                            onClick={(e) =>
                                                                e.stopPropagation()
                                                            }
                                                            className="flex-shrink-0"
                                                        >
                                                            <Checkbox
                                                                isSelected={selectedIds.includes(
                                                                    doc.document_id
                                                                )}
                                                                onValueChange={() =>
                                                                    toggleSelection(
                                                                        doc.document_id
                                                                    )
                                                                }
                                                                classNames={{
                                                                    base: "dark",
                                                                }}
                                                            />
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Fixed action buttons at the bottom */}
                    {(selectedIds.length > 0 || uploadingFiles.filter(f => !f.error).length > 0) && (
                        <div className="border-t border-gray-700 p-4 bg-[#2B2D33]">
                            {/* First row: Selected files count and uploading files */}
                            <div className="mb-3 space-y-2">
                                {selectedIds.length > 0 && (
                                    <div className="text-sm text-gray-400">
                                        Выбрано файлов:{" "}
                                        <span className="text-yellow-500">
                                            [{selectedIds.length}]
                                        </span>
                                    </div>
                                )}
                                {uploadingFiles.filter(f => !f.error).length > 0 && (
                                    <div>
                                        <div className="text-sm text-gray-400 mb-2">
                                            Загрузка файлов{" "}
                                            <span className="text-gray-500">
                                                [{uploadingFiles.filter(f => !f.error).length}]
                                            </span>
                                        </div>
                                        <div className="w-[280px]">
                                            <Progress
                                                value={
                                                    uploadingFiles.filter(f => !f.error).reduce(
                                                        (sum, f) => sum + f.progress,
                                                        0
                                                    ) /
                                                    uploadingFiles.filter(f => !f.error).length
                                                }
                                                color="primary"
                                                size="sm"
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Second row: Action buttons */}
                            {selectedIds.length > 0 && (
                                <div className="flex gap-3">
                                    <Button
                                        onPress={onToggle}
                                        className="w-fit bg-white text-black hover:bg-gray-100"
                                        startContent={<ArrowLeft size={16} style={{ color: '#2563eb' }} />}
                                    >
                                        Перейти к чату
                                    </Button>
                                    <Button
                                        onPress={handleDelete}
                                        className="w-fit bg-transparent border-2 border-red-600 text-white hover:bg-red-600/10"
                                        startContent={<Trash2 size={16} style={{ color: '#dc2626' }} />}
                                    >
                                        Удалить файлы
                                    </Button>
                                    <Button
                                        onPress={() => {
                                            const selectedDocs = documents.filter(
                                                (doc) =>
                                                    selectedIds.includes(
                                                        doc.document_id
                                                    ) && !(doc as any).isUploading
                                            );
                                            selectedDocs.forEach((doc) => {
                                                handleDownload(
                                                    doc.minio_url,
                                                    doc.filename
                                                );
                                            });
                                        }}
                                        className="w-fit bg-transparent border-2 border-blue-600 text-white hover:bg-blue-600/10"
                                        startContent={<Download size={16} style={{ color: '#2563eb' }} />}
                                    >
                                        Скачать
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
};
