/** Shared by the Quality Certifications card and its dialogs. */
export const STATUS_TONES = { Active: 'green', 'Expiring Soon': 'amber', Expired: 'red', 'Pending Verification': 'blue', Suspended: 'red' }

export const fileSize = (bytes) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`)
