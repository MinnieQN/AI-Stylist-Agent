import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import OccasionPage from './pages/OccasionPage';
import StylePickerPage from './pages/StylePickerPage';
import UploadPage from './pages/UploadPage';
import TryOnPage from './pages/TryOnPage';

// create one queryClient object to manage API data/cache

const queryClient = new QueryClient();

export default function App() {

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<OccasionPage />} />
          <Route path="/styles" element={<StylePickerPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/tryon" element={<TryOnPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
