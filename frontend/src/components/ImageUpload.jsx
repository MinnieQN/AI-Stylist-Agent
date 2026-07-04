import { useState } from 'react';
import api from '../api/axios';

/**
 * Component for uploading user images to the backend for try-on image generation.
 * Handles file selection, validation, upload to backend,
 * and calls onUploadSuccess(fileRef, filePath) when done
 */
export default function ImageUpload({ onUploadSuccess }) {
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);

    // function to handle file selection
    async function handleFileChange(e) {
        const file = e.target.files[0];
        if (!file) return; // do nothing if no file is selected

        setSelectedFile(file);
        setUploading(true);
        setError(null); // reset any previous errors
    
        try {
            // create fromData to send the file in a multipart/form-data request
            const formData = new FormData();
            formData.append('file', file);

            // make POST request to backend with selected file
            const response = await api.post('/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });

            // call onUploadSuccess with the file name and path returned from the backend
            onUploadSuccess(response.data.filename, response.data.filepath);

        } catch (err) {
            // if there's an error, set the error state to display the message
            setError(err.response?.data?.error || 'An error occurred during upload. Please try again.');
        } finally {
            setUploading(false); // set uploading state back to false after response is received or error occurs
        }
    }

    return (
        <div className="flex flex-col gap-4">

        <label className="flex flex-col items-center justify-center border-2 border-dashed border-[#D8C3A5] hover:border-[#B8875B] rounded-xl p-8 cursor-pointer transition-colors">
            <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileChange}
            className="hidden"
            />
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#B8875B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <span className="text-sm font-medium text-[#3B2F2F] mt-2">
                {uploading ? 'Uploading...' : 'Click to browse your files'}
            </span>
            <span className="text-xs text-[#7A5E5E] mt-1">
                JPEG, PNG or WebP — max 10MB
            </span>
        </label>

        {/* Preview generated from the File object */}
        {selectedFile && (
            <div className="flex justify-center">
            <img
                src={URL.createObjectURL(selectedFile)}
                alt="Your uploaded photo"
                className="h-56 rounded-xl object-cover"
            />
            </div>
        )}

        {error && (
            <p className="text-red-700 text-sm">{error}</p>
        )}

        </div>
    );
}