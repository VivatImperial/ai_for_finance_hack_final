/**
 * Generates a consistent color from a string (username)
 * Uses simple hash algorithm to convert string to a hue value
 */
export const getColorFromString = (str: string): string => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    // Convert hash to hue (0-360)
    const hue = Math.abs(hash) % 360;
    
    // Use HSL with fixed saturation and lightness for consistent looking colors
    // Saturation: 65% for vibrant but not overwhelming colors
    // Lightness: 50% for good contrast with white text
    return `hsl(${hue}, 65%, 50%)`;
};

/**
 * Gets initials from a full name or username
 */
export const getInitials = (name: string): string => {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
};

