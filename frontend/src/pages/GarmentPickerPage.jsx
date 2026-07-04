import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

/**
 * Garment Picker page that receives user's selected outfit;
 * and call /styles/garments to show searched products (top/bottom/shoes);
 * and user confirms selection
 * Handles three response shapes from /styles:
 *   needs_clarification → inline question banner, user refines and resubmits
 *   cached              → inline suggestion card (view liked look / generate new)
 *   recommendations     → navigate to StylePickerPage
 */