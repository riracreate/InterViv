/** Resume upload limit. Must match the server limit in backend/routes/resume.py. */
export const MAX_RESUME_BYTES = 5 * 1024 * 1024;
export const MAX_RESUME_LABEL = '5 MB';

/** Returns an error message when the file cannot be sent, otherwise ''. */
export function resumeFileError(file) {
  if (!file) return 'Please upload a PDF file.';
  if (file.type !== 'application/pdf') return 'Please upload a PDF file.';
  if (file.size > MAX_RESUME_BYTES) {
    return `That PDF is too large. Please choose a file up to ${MAX_RESUME_LABEL}.`;
  }
  return '';
}
