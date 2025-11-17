import { useCallback, useEffect } from "react";
import { Upload } from "lucide-react";
import { Button } from "@heroui/react";
import { useFileUploadWithProgress } from "@/view/hooks/useFileUploadWithProgress";
import { addToast } from "@heroui/react";
import type { QueryClient } from "@tanstack/react-query";
import type { IUploadingFile } from "@/types/document";
import { getGetDocumentsForUserApiV1DocumentGetQueryKey } from "@/server/generated";

interface IFileUploadViewProps {
    onComplete: () => void;
    addUploadingFiles: (files: IUploadingFile[]) => void;
    updateUploadingFile: (id: string, updates: Partial<IUploadingFile>) => void;
    removeUploadingFile: (id: string) => void;
    queryClient: QueryClient;
}

export const FileUploadView = ({
    onComplete,
    addUploadingFiles,
    updateUploadingFile,
    removeUploadingFile,
    queryClient,
}: IFileUploadViewProps) => {
    const { uploadFile } = useFileUploadWithProgress();

    const handleFilesSelected = useCallback(
        (files: FileList | File[]) => {
            const fileArray = Array.from(files);

            // Validate file types
            const allowedTypes = [
                ".docx",
                ".pdf",
                ".txt",
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/plain",
            ];

            const invalidFiles = fileArray.filter((file) => {
                const extension =
                    "." + file.name.split(".").pop()?.toLowerCase();
                return (
                    !allowedTypes.includes(extension) &&
                    !allowedTypes.includes(file.type)
                );
            });

            if (invalidFiles.length > 0) {
                addToast({
                    title: "Неподдерживаемый формат файла",
                    color: "danger",
                    description: "Поддерживаемые форматы: .docx, .pdf, .txt",
                });
                return;
            }

            const newFiles: IUploadingFile[] = fileArray.map((file) => ({
                file,
                progress: 0,
                id: Math.random().toString(36).substring(7),
            }));

            addUploadingFiles(newFiles);

            // Immediately switch to main view to show uploading files
            onComplete();

            let completedCount = 0;
            const totalFiles = fileArray.length;
            let invalidated = false;

            const checkAndInvalidate = () => {
                completedCount++;
                // Invalidate only once when all files are processed
                if (completedCount === totalFiles && !invalidated) {
                    invalidated = true;
                    // Wait longer to ensure server processed all files and they appear in the list
                    setTimeout(() => {
                        queryClient.invalidateQueries({
                            queryKey:
                                getGetDocumentsForUserApiV1DocumentGetQueryKey(),
                        });
                        // Remove uploading files after invalidation to let server files appear
                        setTimeout(() => {
                            newFiles.forEach((file) => {
                                removeUploadingFile(file.id);
                            });
                        }, 500);
                    }, 2000);
                }
            };

            fileArray.forEach((file, index) => {
                const fileId = newFiles[index].id;
                uploadFile(file, (progress) => {
                    updateUploadingFile(fileId, { progress });
                })
                    .then(() => {
                        updateUploadingFile(fileId, { progress: 100 });
                        // Don't remove file immediately - let it stay until server confirms
                        // The file will be removed after invalidation when it appears in serverDocuments
                        checkAndInvalidate();
                    })
                    .catch((error) => {
                        // Remove file with error from uploading list
                        removeUploadingFile(fileId);
                        addToast({
                            title: `Ошибка загрузки ${file.name}`,
                            color: "danger",
                        });
                        checkAndInvalidate();
                    });
            });
        },
        [
            uploadFile,
            queryClient,
            addUploadingFiles,
            updateUploadingFile,
            removeUploadingFile,
            onComplete,
        ]
    );

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.stopPropagation();
        if (e.target.files && e.target.files.length > 0) {
            handleFilesSelected(e.target.files);
        }
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFilesSelected(e.dataTransfer.files);
        }
    };

    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
    };

    return (
        <div className="flex-1 overflow-y-auto p-6 flex flex-col items-center justify-center">
            <div
                onClick={(e) => {
                    e.stopPropagation();
                    document.getElementById("file-input")?.click();
                }}
                onDrop={(e) => {
                    e.stopPropagation();
                    handleDrop(e);
                }}
                onDragOver={(e) => {
                    e.stopPropagation();
                    handleDragOver(e);
                }}
                className="w-[450px] h-[450px] border-2 border-dashed rounded-lg cursor-pointer hover:border-opacity-60 transition-all flex flex-col items-center justify-center"
                style={{
                    backgroundColor: "rgba(254, 254, 254, 0.05)",
                    borderColor: "rgba(254, 254, 254, 0.2)",
                }}
            >
                <Upload size={64} className="text-yellow-500 mb-6" />
                <p className="text-white font-semibold text-lg mb-3">
                    Перетащите файлы сюда
                </p>
                <p className="text-gray-500 text-sm mb-6">
                    Поддерживаемые форматы: .docx, .pdf, .txt
                </p>
                <input
                    id="file-input"
                    type="file"
                    multiple
                    accept=".docx,.pdf,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                    onChange={handleFileInput}
                    className="hidden"
                />
            </div>
        </div>
    );
};
