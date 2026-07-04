/**
 * Function to display each style recommendation card with details and "Choose this style" button
 * @param {Object} props.style - The style recommendation object containing style_name, description, key_pieces, and reasoning
 * @param {number} props.index - The index of the style recommendation (used for display purposes)ß
 * @param {function} props.onSelect - The function to call when the user selects this style
 * @returns {JSX.Element} The JSX element representing the style card
 */
export default function StyleCard({ style, index, onSelect }) {
  return (
    <div className="bg-[#FFFAF3] border border-[#D8C3A5] rounded-2xl p-6 flex flex-col gap-4">

      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-base font-medium text-[#3B2F2F]">
            {style.style_name}
          </h2>
          <p className="text-sm text-[#7A5E5E] mt-1">
            {style.description}
          </p>
        </div>
        <span className="bg-[#D8C3A5] text-[#3B2F2F] text-xs px-3 py-1 rounded-full whitespace-nowrap ml-4">
          {/* display the style number (1, 2, or 3) */}
          Style {index + 1}
        </span>
      </div>

      {/* Key pieces */}
      <div className="flex flex-wrap gap-2">
        {style.key_pieces.map((piece, i) => (
          <span
            key={i}
            className="bg-[#F0E6D8] text-[#5A3E2B] text-xs px-3 py-1 rounded-full"
          >
            {piece}
          </span>
        ))}
      </div>

      {/* Reasoning */}
      <p className="text-sm text-[#5A4040] italic border-l-2 border-[#B8875B] pl-3">
        {style.reasoning}
      </p>

      {/* Button */}
      <button
        onClick={() => onSelect(style, index)}
        className="w-full bg-[#B8875B] hover:bg-[#8A5A3B] text-[#FFFAF3] py-2.5 rounded-lg text-sm font-medium transition-colors"
      >
        Choose this style
      </button>

    </div>
  );
}