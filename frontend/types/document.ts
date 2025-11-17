export interface IUploadingFile {
  file: File;
  progress: number;
  id: string;
  error?: string;
}

export interface IDocumentSelection {
  selectedIds: number[];
}

