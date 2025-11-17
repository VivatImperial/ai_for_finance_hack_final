import { useCallback } from 'react';
import Cookies from 'js-cookie';
import { API_BASE_URL } from '@/server/libs/constants/api';
import type { DocumentResponse } from '@/types';

export const useFileUploadWithProgress = () => {
  const uploadFile = useCallback(
    (file: File, onProgress: (progress: number) => void): Promise<DocumentResponse> => {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        const token = Cookies.get('token');

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const progress = (e.loaded / e.total) * 100;
            onProgress(progress);
          }
        };

        xhr.onload = () => {
          if (xhr.status === 200) {
            try {
              const response = JSON.parse(xhr.response);
              resolve(response);
            } catch (error) {
              reject(new Error('Invalid response'));
            }
          } else {
            reject(new Error(`Upload failed: ${xhr.statusText}`));
          }
        };

        xhr.onerror = () => reject(new Error('Network error'));
        xhr.onabort = () => reject(new Error('Upload cancelled'));

        xhr.open('POST', `${API_BASE_URL}/api/v1/document`);
        
        if (token) {
          xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        }

        const formData = new FormData();
        formData.append('file', file);
        xhr.send(formData);
      });
    },
    []
  );

  return { uploadFile };
};

