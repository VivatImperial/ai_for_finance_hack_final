export interface IMessageWithMeta {
  message_id: number;
  content: string;
  message_type: number;
  documents_ids: number[];
  created_at: string;
  hidden_comments: string | null;
  isTyping?: boolean;
}

export interface IActiveChatState {
  chatId: number | null;
  attachedDocumentIds: number[];
}

