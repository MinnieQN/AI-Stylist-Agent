import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

/**
 * Occasion page for user to input an occasion
 * and submit to get style recommendations from the backend.
 * Handles three response shapes from /styles:
 *   needs_clarification → inline question banner, user refines and resubmits
 *   cached              → inline suggestion card (view liked look / generate new)
 *   recommendations     → navigate to StylePickerPage
 */
export default function OccasionPage() {
    // state variables to manage user input, loading status, and error messages
    const [occasion, setOccasion] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [cacheSuggestion, setCacheSuggestion] = useState(null);
    const [clarification, setClarification] = useState(null);
    const navigate = useNavigate();

    // function to handle user submission
    async function handleSubmit(e) {
        e.preventDefault(); // prevent default form submission behavior
        if (!occasion.trim()) return;
        setCacheSuggestion(null);   // clear any previous suggestion
        setClarification(null);     // clear any previous clarification
        setLoading(true);
        setError(null);

        try {
            // make POST request to backend with the occasion input
            const response = await api.post('/styles', { occasion });

            if (response.data.needs_clarification) {
                // agent couldn't parse the occasion — show its question inline
                setClarification(response.data.question);
            } else if (response.data.cached) {
                // cache hit — show the inline suggestion card
                setCacheSuggestion({
                    occasion: response.data.occasion,
                    style: response.data.outfit.style,
                    image: response.data.outfit.tryon_image,
                });
            } else {
                // normal flow — navigate with fresh recommendations
                navigate('/styles', {
                    state: {
                        occasion: response.data.occasion,
                        recommendations: response.data.recommendations,
                    },
                });
            }
        } catch (err) {
            // if there's an error, set the error state to display the message
            setError(err.response?.data?.detail || 'An error occurred. Please try again.');
        } finally {
            setLoading(false); // reset loading state after response or error
        }
    }

    // user chooses to view the cached look
    function handleViewCached() {
        navigate('/tryon', {
            state: {
                occasion: cacheSuggestion.occasion,
                cachedStyle: cacheSuggestion.style,
                cachedImage: cacheSuggestion.image,
                fromCache: true,
            },
        });
    }

    // user wants fresh recommendations instead of the cached look
    async function handleSubmitNew() {
        setLoading(true);
        setError(null);

        try {
            const response = await api.post('/styles', {
                occasion: cacheSuggestion.occasion,
                skip_cache: true,   // force the agent, bypass cache
            });

            if (response.data.needs_clarification) {
                setClarification(response.data.question);
                setCacheSuggestion(null);
            } else {
                navigate('/styles', {
                    state: {
                        occasion: response.data.occasion,
                        recommendations: response.data.recommendations,
                    },
                });
            }
        } catch (err) {
            setError(err.response?.data?.detail || 'An error occurred. Please try again.');
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="min-h-screen bg-[#F7F0E8] text-[#3B2F2F] flex items-center justify-center p-6">
            <section className="bg-[#D8C3A5] p-10 rounded-2xl max-w-xl w-full">
                <h1 className="text-4xl font-bold">Welcome to your AI Stylist!</h1>
                <p className="text-[#7A6A5E] mt-4">
                    Enter an occasion, and your stylist will recommend some outfit styles for you.
                </p>
                <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
                    <input
                        value={occasion}
                        onChange={(e) => setOccasion(e.target.value)}
                        placeholder="Enter an occasion (e.g., wedding, job interview)"
                        className="px-4 py-3 rounded-lg border border-[#CBB89D] bg-[#FFFCF8] outline-none focus:ring-2 focus:ring-[#B8875B]"
                    />

                    <button
                        type="submit"
                        disabled={loading}
                        className="bg-[#B8875B] hover:bg-[#8A5A3B] disabled:opacity-60 text-[#FFFAF3] px-6 py-3 rounded-full"
                    >
                        {loading ? 'Loading...' : 'Get Style Recommendations'}
                    </button>
                </form>

                {error && <p className="text-red-700 mt-4">{error}</p>}

                {/* Clarification banner — agent needs a clearer occasion */}
                {clarification && (
                    <div className="bg-[#F0E6D8] border-l-4 border-[#B8875B] rounded-lg p-4 mt-4">
                        <p className="text-sm font-medium text-[#3B2F2F] mb-1">
                            Help me understand your occasion
                        </p>
                        <p className="text-sm text-[#5A4040]">
                            {clarification}
                        </p>
                    </div>
                )}

                {/* Cache suggestion card — user liked a look for a similar occasion */}
                {cacheSuggestion && (
                    <div className="bg-[#FFFAF3] border border-[#D8C3A5] rounded-2xl p-5 mt-4 flex gap-4 items-center">

                        {/* Thumbnail of the cached try-on */}
                        <img
                            src={`data:image/png;base64,${cacheSuggestion.image}`}
                            alt="A look you liked before"