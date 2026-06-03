import { useLocation, useNavigate } from "react-router-dom";
import StyleCard from "../components/StyleCard";
// import api from '../api/axios';

/**
 * Function to display the style recommendations 
 * and user pick a style to generate try-on images in the next step.
 */
export default function StylePickerPage() { 
    const navigate = useNavigate();
    const location = useLocation();
    // handle empty state
    if (!location.state || !location.state.recommendations) {
        navigate('/');  // back to OccasionPage
        return null;
    }

    const { occasion, recommendations } = location.state || {};

    async function handleSelectStyle(style) {
        // next: navigate to try-on page with the chosen style
        console.log('User selected:', style);
    }

    return (
        <div className="min-h-screen bg-[#F7F0E8] p-6">
            <div className="max-w-xl mx-auto"></div>

            {/* Back button */}
            <button
                onClick={() => navigate('/')}
                className="text-[#B8875B] hover:text-[#8A5A3B] text-sm mb-4 transition-colors"
            >
                ← Back
            </button>

            {/* Page header */}
            <section className="bg-[#D8C3A5] rounded-2xl p-6 mb-6">
                <h1 className="text-2xl font-medium text-[#3B2F2F]">
                    Style Recommendations
                </h1>
                <p className="text-sm text-[#5A4040] mt-1">
                    For: <span className="font-medium">{occasion}</span>
                </p>
            </section>

            {/* Style cards */}
            <div className="flex flex-col gap-4">
                {recommendations.map((style, index) => (
                    <StyleCard
                        key={index}     // special prop to loop a list of components
                        style={style}   // variable to pass 
                        index={index}   // variable
                        onSelect={handleSelectStyle}    // function variable 
                    />
                ))}
            </div>
        </div>
    );
}
