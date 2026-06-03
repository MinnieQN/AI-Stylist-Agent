import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

/**
 * Occasion page for user to inpute an occasion
 * and submit to get style recommendations from the backend.
 */
export default function OccasionPage() {
    // state variables to manage user input, loading status, and error messages
    const [occasion, setOccasion] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    // function to handle user submission
    async function handleSubmit(e) {
        e.preventDefault(); // prevent default form submission behavior
        if (!occasion.trim()) return;   // do nothing if the input is empty
        setLoading(true); // set loading state to true while waiting for response
        setError(null); // reset any previous errors
    
        try {
            // make POST request to backend with the occasion input
            const response = await api.post('/styles', { occasion });
            
            // navigate to the style picker page, passing the received style recommendations as state
            navigate('/styles', {
                state: {
                    occasion: response.data.occasion,
                    recommendations: response.data.recommendations
                }
            });
        } catch (err) {
            // if there's an error, set the error state to display the message
            setError(err.response?.data?.error || 'An error occurred. Please try again.');
        } finally {
            setLoading(false); // set loading state back to false after response is received or error occurs
        }
    }

    return (
        <div className="min-h-screen bg-[#F7F0E8] text-[#3B2F2F] flex items-center justify-center p-6">
            <section className="bg-[#D8C3A5] p-10 rounded-2xl max-w-xl w-full">

                {/* Header and description */}
                <h1 className="text-4xl font-bold">Welcome to your AI Stylist!</h1>
                <p className="text-[#7A6A5E] mt-4">
                    Tell me about your occasion and I'll suggest outfits for you.
                </p>

                {/* Form for user to input occasion and submit */}
                <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
                    <input
                        value={occasion}
                        onChange={(e) => setOccasion(e.target.value)}
                        placeholder="Enter an occasion (e.g., wedding, job interview)"
                        className="px-4 py-3 rounded-lg border border-[#CBB89D] bg-[#FFFCF8] outline-none focus:ring-2 focus:ring-[#B8875B]"
                    />

                    {/* Submit button, disabled while loading to prevent multiple submissions */}
                    <button 
                        type="submit" 
                        disabled={loading}
                        className="bg-[#B8875B] hover:bg-[#8A5A3B] disabled:opacity-60 text-[#FFFAF3] px-6 py-3 rounded-full"
                    >
                        {loading ? 'Loading...' : 'Get Style Recommendations'}
                    </button>
                </form>

                {error && <p className="text-red-700 mt-4">{error}</p>}
            </section>
        </div>  
    )
}