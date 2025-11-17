import type { MessageResponse } from "@/types/api";

/**
 * Расширенный тип сообщения с дополнительными полями для UI
 */
export interface ExtendedMessageResponse extends MessageResponse {
    /**
     * Флаг указывающий, что сообщение только что пришло с бэкенда
     * Используется для отображения эффекта печати
     */
    fresh?: boolean;
}
