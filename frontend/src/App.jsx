import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import OccasionPage from './pages/OccasionPage';
import StylePickerPage from './pages/StylePickerPage'

// create one queryClient object to manage API data/cache

const queryClient = new QueryClient();

export default function App() {

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<OccasionPage />} />
          <Route path="/styles" element={<StylePickerPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
