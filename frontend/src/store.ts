import { configureStore } from '@reduxjs/toolkit';

import agentPreviewReducer from './agents/agentPreviewSlice';
import { conversationSlice } from './conversation/conversationSlice';
import { sharedConversationSlice } from './conversation/sharedConversationSlice';
import {
  Preference,
  prefListenerMiddleware,
  prefSlice,
} from './preferences/preferenceSlice';
import uploadReducer from './upload/uploadSlice';

const getStoredValue = (primaryKey: string, legacyKey: string) =>
  localStorage.getItem(primaryKey) ?? localStorage.getItem(legacyKey);

const key = getStoredValue('LegalKRAGApiKey', 'AppApiKey');
const prompt = getStoredValue('LegalKRAGPrompt', 'AppPrompt');
const chunks = getStoredValue('LegalKRAGChunks', 'AppChunks');
const token_limit = getStoredValue('LegalKRAGTokenLimit', 'AppTokenLimit');
const doc = getStoredValue('LegalKRAGRecentDocs', 'AppRecentDocs');
const selectedModel = getStoredValue(
  'LegalKRAGSelectedModel',
  'AppSelectedModel',
);

const preloadedState: { preference: Preference } = {
  preference: {
    apiKey: key ?? '',
    token: localStorage.getItem('authToken') ?? null,
    prompt:
      prompt !== null
        ? JSON.parse(prompt)
        : { name: 'default', id: 'default', type: 'private' },
    chunks: JSON.parse(chunks ?? '2').toString(),
    token_limit: token_limit ? parseInt(token_limit) : 2000,
    selectedDocs: doc !== null ? JSON.parse(doc) : [],
    conversations: {
      data: null,
      loading: false,
    },
    sourceDocs: [
      {
        name: 'default',
        date: '',
        model: '1.0',
        type: 'remote',
        id: 'default',
        retriever: 'clasic',
      },
    ],
    modalState: 'INACTIVE',
    paginatedDocuments: null,
    templateAgents: null,
    agents: null,
    sharedAgents: null,
    selectedAgent: null,
    selectedModel: selectedModel ? JSON.parse(selectedModel) : null,
    availableModels: [],
    modelsLoading: false,
  },
};
const store = configureStore({
  preloadedState: preloadedState,
  reducer: {
    preference: prefSlice.reducer,
    conversation: conversationSlice.reducer,
    sharedConversation: sharedConversationSlice.reducer,
    upload: uploadReducer,
    agentPreview: agentPreviewReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(prefListenerMiddleware.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
export default store;

// TODO : use https://redux-toolkit.js.org/tutorials/typescript#define-typed-hooks everywere instead of direct useDispatch

// TODO : streamline async state management
