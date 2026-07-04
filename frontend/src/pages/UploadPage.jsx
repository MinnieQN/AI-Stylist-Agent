import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ImageUpload from '../components/ImageUpload';

/**
 * Upload page for user to upload a full-body image to the backend for try-on image generation.
 */

export default function UploadPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const [filename, setFileName] = useState('');
    const [filepath, setFilePath] = useState('');

    // handle empty state
    if (!location.state || !location.state.selectedStyle) {
        navigate('/styles');  // back to StylePickerPage
        return null;
    }

    const { occasion, selectedStyle, recommendations } = location.state || {};

    // handle successful upload
    function handleUploadSuccess(filename, filepath) {
        setFileName(filename);
        setFilePath(filepath);
    }

    // handle generate try-on images button click
    function handleGenerateTryon() {
        navigate('/tryon', {
            state: { selectedStyle, occasion, filename, filepath, recommendations }
        });
    }

    return (
        <div className="min-h-screen bg-[#F7F0E8] p-6">
            <div className="max-w-xl mx-auto">

                {/* Back button */}
                <button
                onClick={() => navigate(-1)}
                className="text-[#B8875B] hover:text-[#8A5A3B] text-sm mb-4 transition-colors"
                >
                ← Back
                </button>

                {/* Page header */}
                <section className="bg-[#D8C3A5] rounded-2xl p-6 mb-6">
                    <h1 className="text-2xl font-medium text-[#3B2F2F]">Virtual try-on</h1>
                    <p className="text-sm text-[#5A4040] mt-1">
                        For: <span className="font-medium">{occasion}</span>
                    </p>
                </section>

                {/* Selected style card — stays visible, highlighted */}
                <div className="bg-[#FFFAF3] border-2 border-[#B8875B] rounded-2xl p-6 mb-6">
                    <div className="flex justify-between items-start mb-3">
                        <div>
                        <h2 className="text-base font-medium text-[#3B2F2F]">
                            {selectedStyle.style_name}
                        </h2>
                        <p className="text-sm text-[#7A5E5E] mt-1">
                            {selectedStyle.description}
                        </p>
                        </div>
                        <span className="bg-[#B8875B] text-[#FFFAF3] text-xs px-3 py-1 rounded-full">
                        Selected
                        </span>
                    </div>

                    <div className="flex flex-wrap gap-2 mb-3">
                        {selectedStyle.key_pieces.map((piece, i) => (
                            <span
                                key={i}
                                className="bg-[#F0E6D8] text-[#5A3E2B] text-xs px-3 py-1 rounded-full"
                            >
                                {piece}
                            </span>
                        ))}
                    </div>

                    <p className="text-sm text-[#5A4040] italic border-l-2 border-[#B8875B] pl-3">
                        {selectedStyle.reasoning}
                    </p>
                </div>

                {/* Upload section */}
                <div className="bg-[#FFFAF3] border border-[#D8C3A5] rounded-2xl p-6">
                    <h2 className="text-base font-medium text-[#3B2F2F] mb-1">
                        Upload your photo
                    </h2>
                    <p className="text-sm text-[#7A5E5E] mb-4">
                        Upload a full-body photo for virtual try-on
                    </p>

                    <ImageUpload onUploadSuccess={handleUploadSuccess} />

                    {/* Generate button — only appears after successful upload */}
                    {filename && (
                        <button
                        onClick={handleGenerateTryon}
                        className="w-full mt-4 bg-[#B8875B] hover:bg-[#8A5A3B] text-[#FFFAF3] py-3 rounded-lg text-sm font-medium transition-colors"
                        >
                        Generate try-on image
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}

