import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../api/axios';

/**
 * Garment picker page. After the user selects a style, this page fetches
 * shoppable products for each garment category (top / bottom / shoes) from
 * Google Shopping and lets the user pick one per category.
 * Empty categories are a valid state — the piece is still included in the
 * try-on via the outfit description; there's just no product image for it.
 * Continue requires a selection from every NON-EMPTY category.
 */
export default function GarmentPickerPage() {
    const navigate = useNavigate();
    const location = useLocation();

    const [garments, setGarments] = useState(null);          // {top: [...], bottom: [...], shoes: [...]}
    const [selectedGarments, setSelectedGarments] = useState({}); // {top: {...}, bottom: {...}}
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // handle empty state — user landed here without picking a style
    if (!location.state || !location.state.selectedStyle) {
        navigate('/');
        return null;
    }

    const { selectedStyle, occasion, recommendations } = location.state || {};

    // fetch shoppable garments for the chosen style on mount
    useEffect(() => {
        async function fetchGarments() {
            setLoading(true);
            setError(null);

            try {
                const response = await api.post('/styles/garments', {
                    occasion,
                    style: selectedStyle,
                    // gender term sharpens shopping queries; persisted by OccasionPage
                    style_preference: localStorage.getItem('stylePreference') || null,
                });
                setGarments(response.data.garments);
            } catch (err) {
                setError(err.response?.data?.detail || 'Could not fetch products right now.');
            } finally {
                setLoading(false);
            }
        }
        fetchGarments();
    }, []); // run once on mount

    // select one product per category (click again to deselect)
    function handleSelectGarment(category, product) {
        setSelectedGarments((prev) => ({
            ...prev,
            [category]: prev[category]?.title === product.title ? null : product,
        }));
    }

    // only these categories can be photo-fitted by IDM-VTON — shoes (or any
    // other category) are display/shopping-only and never gate Continue
    const TRYON_CATEGORIES = ['top', 'bottom'];

    // try-on-able categories that actually have products — these gate Continue
    const requiredCategories = garments
        ? Object.entries(garments)
            .filter(([category, products]) => TRYON_CATEGORIES.includes(category) && products.length > 0)
            .map(([category]) => category)
        : [];
    const allSelected = requiredCategories.every((c) => selectedGarments[c]);

    // continue to body photo upload, threading everything through
    function handleContinue() {
        navigate('/upload', {
            state: {
                selectedStyle,
                occasion,
                recommendations,
                selectedGarments,
            },
        });
    }

    return (
        <div className="min-h-screen bg-[#F7F0E8] p-6">
            <div className="max-w-xl mx-auto">

                {/* Back button */}
                <button
                    onClick={() => navigate('/styles', { state: { occasion, recommendations } })}
                    className="text-[#B8875B] hover:text-[#8A5A3B] text-sm mb-4 transition-colors"
                >
                    ← Back to styles
                </button>

                {/* Page header */}
                <section className="bg-[#D8C3A5] rounded-2xl p-6 mb-6">
                    <h1 className="text-2xl font-medium text-[#3B2F2F]">
                        Pick your garments
                    </h1>
                    <p className="text-sm text-[#5A4040] mt-1">
                        Style: <span className="font-medium">{selectedStyle.style_name}</span>
                        {' '}for <span className="font-medium">{occasion}</span>
                    </p>
                </section>

                {/* Loading state — 3 shopping searches take a couple seconds */}
                {loading && (
                    <div className="bg-[#FFFAF3] border border-[#D8C3A5] rounded-2xl p-12 flex flex-col items-center gap-3">
                        <div className="w-8 h-8 border-2 border-[#B8875B] border-t-transparent rounded-full animate-spin" />
                        <p className="text-sm text-[#7A5E5E]">Finding products for your look...</p>
                    </div>
                )}

                {/* Error state — fetch itself failed; user can still continue */}
                {error && !loading && (
                    <div className="bg-[#FFFAF3] border border-[#D8C3A5] rounded-2xl p-6 mb-4">
                        <p className="text-sm text-[#7A5E5E] mb-4">
                            {error} You can continue with the outfit as described.
                        </p>
                        <button
                            onClick={handleContinue}
                            className="bg-[#B8875B] hover:bg-[#8A5A3B] text-[#FFFAF3] px-6 py-3 rounded-lg text-sm font-medium transition-colors"
                        >
                            Continue without products
                        </button>
                    </div>
                )}

                {/* Category sections */}
                {garments && !loading && (
                    <div className="flex flex-col gap-6">
                        {Object.entries(garments).map(([category, products]) => (
                            <section key={category}>
                                <div className="flex items-baseline gap-2 mb-3">
                                    <h2 className="text-lg font-medium text-[#3B2F2F] capitalize">
                                        {category}
                                    </h2>
                                    {/* subtle tag: which sections actually reach the try-on image */}
                                    <span className="bg-[#F0E6D8] text-[#5A3E2B] text-xs px-2.5 py-0.5 rounded-full">
                                        {TRYON_CATEGORIES.includes(category)
                                            ? 'shown in your try-on'
                                            : 'display only'}
                                    </span>
                                </div>

                                {products.length === 0 ? (
                                    // empty category — valid state, quiet note
                                    <p className="text-sm text-[#7A5E5E] bg-[#F0E6D8] rounded-lg p-3">
                                        No products found for this piece — it'll still be
                                        included in your look.
                                    </p>
                                ) : (
                                    <div className="grid grid-cols-2 gap-3">
                                        {products.map((product, index) => {
                                            const isSelected =
                                                selectedGarments[category]?.title === product.title;
                                            const selectable = TRYON_CATEGORIES.includes(category);
                                            return (
                                                // flex column + flex-1 title keeps Select buttons
                                                // bottom-aligned across cards with 1- vs 2-line titles
                                                <div
                                                    key={index}
                                                    className={`bg-[#FFFAF3] rounded-2xl p-3 text-left transition-colors flex flex-col ${
                                                        isSelected
                                                            ? 'border-2 border-[#B8875B]'
                                                            : 'border border-[#D8C3A5]'
                                                    }`}
                                                >
                                                    {/* image links out to the store page */}
                                                    <a
                                                        href={product.product_link}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        title="View in store"
                                                    >
                                                        <img
                                                            src={product.image_url}
                                                            alt={product.title}
                                                            className="w-full h-40 rounded-xl object-cover mb-2 bg-[#F0E6D8] hover:opacity-80 transition-opacity"
                                                        />
                                                    </a>
                                                    <p className="text-xs text-[#3B2F2F] line-clamp-2 mb-2 flex-1">
                                                        {product.title}
                                                    </p>
                                                    {/* selection only exists for try-on categories —
                                                        display-only sections (shoes) are just shoppable */}
                                                    {selectable && (
                                                        <button
                                                            type="button"
                                                            onClick={() => handleSelectGarment(category, product)}
                                                            className={`w-full py-1.5 rounded-lg text-xs font-medium transition-colors ${
                                                                isSelected
                                                                    ? 'bg-[#B8875B] text-[#FFFAF3] hover:bg-[#8A5A3B]'
                                                                    : 'border border-[#CBB89D] bg-[#F7F0E8] text-[#3B2F2F] hover:bg-[#F0E6D8]'
                                                            }`}
                                                        >
                                                            {isSelected ? 'Selected ✓' : 'Select'}
                                                        </button>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </section>
                        ))}

                        {/* Continue — requires a pick from every non-empty category */}
                        <button
                            onClick={handleContinue}
                            disabled={!allSelected}
                            className="bg-[#B8875B] hover:bg-[#8A5A3B] disabled:opacity-60 text-[#FFFAF3] py-3 rounded-lg text-sm font-medium transition-colors"
                        >
                            {allSelected
                                ? 'Continue to try-on'
                                : 'Select your try-on garments (top & bottom)'}
                        </button>
                    </div>
                )}

            </div>
        </div>
    );
}