import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../api/axios';

/**
 * TryOn page for user to view the generated try-on image.
 */
export default function TryOnPage() {
    const [image, setImage] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // set state to track liked
    const [liked, setLiked] = useState(false);

    // get user selected  style, occasion and uploaded image from UploadPage
    const location = useLocation();
    const navigate = useNavigate();

    // function to fetch generated try-on image
    useEffect(() => {
        async function generateTryOn() {
            // directly return the cached image if user chose to
            if (location.state?.fromCache) {
                setImage(location.state.cachedImage);
                return;
            }

            setLoading(true);
            setError(null);

            try {
                // make POST request to backend to fetch try-on image
                const response = await api.post(
                    '/tryon',
                    {
                        style: location.state.selectedStyle,
                        occasion: location.state.occasion,
                        filepath: location.state.filepath
                    },
                );
                // set the received json image string to state to display on the page
                setImage(response.data.image); 
                
            } catch (err) {
                setError(err.response?.data?.detail || 'An error occurred while generating the try-on image. Please try again.');
            } finally {
                setLoading(false);
            }
        }
        generateTryOn();
    }, []); // empty array - run once when page loads

    // functions to handle Like/Dislike image
    async function handleLike() {
        try {
            // make POST request to backend to store liked-outfit
            await api.post(
                '/tryon/like',
                {
                    occasion: location.state.occasion,
                    style: location.state.selectedStyle,
                    tryon_image: image
                },
            );
            setLiked(true);
        } catch (err) {
            setLiked(false);
        }
    }

    function handleDislike() {
        // in case user selected a style and doesn't like the try_on 
        // then switch to another style
        navigate('/styles', {
            state: {
                occasion: location.state.occasion,
                recommendations: location.state.recommendations
            }
        });
    }

    // function to handle user wants to generate new recommendations
    async function handleGenerateNew() {
        const response = await api.post('/styles', {
            occasion: location.state.occasion,
            skip_cache: true,
        });
        navigate('/styles', {
            state: {
                occasion: response.data.occasion,
                recommendations: response.data.recommendations,
            }
        });
    }

    return (
        <div className="min-h-screen bg-[#F7F0E8] p-6">
            <div className="max-w-xl mx-auto">

                {/* Page header */}
                <section className="bg-[#D8C3A5] rounded-2xl p-6 mb-6">
                    <h1 className="text-2xl font-medium text-[#3B2F2F]">
                        Your try-on
                    </h1>
                    <p className="text-sm text-[#5A4040] mt-1">
                        For: <span className="font-medium">{location.state?.occasion}</span>
                    </p>
                </section>

                {/* Loading state */}
                {loading && (
                    <div className="bg-[#FFFAF3] border border-[#D8C3A5] rounded-2xl p-12 flex flex-col items-center gap-3">
                        <div className="w-8 h-8 border-2 border-[#B8875B] border-t-transparent rounded-full animate-spin" />
                        <p className="text-sm text-[#7A5E5E]">Generating your try-on image...</p>
                    </div>
                )}

                {/* Error state */}
                {error && (
                    <div className="bg-[#FFFAF3] border border-[#D8C3A5] rounded-2xl p-6">
                        <p className="text-sm text-red-700 mb-4">{error}</p>
                        <button
                            onClick={() => navigate('/')}
                            className="text-[#B8875B] hover:text-[#8A5A3B] text-sm transition-colors"
                        >
                            ← Back to home
                        </button>
                    </div>
                )}

                {/* Result state */}
                {image && !loading && (
                    <div className="bg-[#FFFAF3] border border-[#D8C3A5] rounded-2xl p-6 flex flex-col gap-4">

                        {/* Try-on image */}
                        <img
                            src={`data:image/png;base64,${image}`}
                            alt="Your try-on"
                            className="w-full rounded-xl object-cover"
                        />

                        {/* Action buttons — differ for cached vs freshly generated */}
                        {location.state?.fromCache ? (
                            // cached view: no like/dislike; offer to generate fresh instead
                            <div className="flex flex-col gap-2">
                                <button
                                    onClick={handleGenerateNew}
                                    className="w-full bg-[#B8875B] hover:bg-[#8A5A3B] text-[#FFFAF3] py-3 rounded-lg text-sm font-medium transition-colors"
                                >
                                    Generate new recommendations
                                </button>
                                <button
                                    onClick={() => navigate('/')}
                                    className="w-full text-[#B8875B] hover:text-[#8A5A3B] py-2 text-sm transition-colors"
                                >
                                    Back to home
                                </button>
                            </div>
                        ) : (
                            // normal generated view: like / dislike
                            <div className="flex gap-3">
                                <button
                                    onClick={handleDislike}
                                    className="flex-1 border border-[#D8C3A5] bg-[#F7F0E8] hover:bg-[#EDE3D6] text-[#3B2F2F] py-3 rounded-lg text-sm font-medium transition-colors"
                                >
                                    Dislike
                                </button>
                                <button
                                    onClick={handleLike}
                                    className="flex-1 bg-[#B8875B] hover:bg-[#8A5A3B] text-[#FFFAF3] py-3 rounded-lg text-sm font-medium transition-colors"
                                >
                                    {liked ? 'Liked ✓' : 'Like'}
                                </button>
                            </div>
                        )}

                    </div>
                )}

            </div>
        </div>
    );
}