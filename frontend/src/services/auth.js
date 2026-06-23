import {
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  updateProfile
} from 'firebase/auth';
import { auth, googleProvider, isFirebaseMock } from './firebase';

// Mock state wrapper for developer preview (when VITE_FIREBASE_API_KEY is missing)
const mockState = {
  currentUser: null,
  listeners: []
};

const triggerListeners = () => {
  mockState.listeners.forEach(cb => cb(mockState.currentUser));
};

export const googleSignIn = async () => {
  if (isFirebaseMock) {
    const mockUser = {
      uid: 'mock-google-uid-12345',
      email: 'trial-google@alphamatrix.io',
      displayName: 'Trial Google Operator',
      photoURL: 'https://api.dicebear.com/7.x/bottts/svg?seed=Google',
      providerData: [{ providerId: 'google.com' }],
      getIdToken: async () => 'mock-google-id-token-payload-alphamatrix'
    };
    mockState.currentUser = mockUser;
    triggerListeners();
    return mockUser;
  }
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
};

export const emailSignUp = async (email, password) => {
  if (isFirebaseMock) {
    const mockUser = {
      uid: `mock-email-uid-${email.split('@')[0]}`,
      email,
      displayName: email.split('@')[0].toUpperCase(),
      photoURL: `https://api.dicebear.com/7.x/bottts/svg?seed=${email}`,
      providerData: [{ providerId: 'password' }],
      getIdToken: async () => `mock-user-token-${email.split('@')[0]}`
    };
    mockState.currentUser = mockUser;
    triggerListeners();
    return mockUser;
  }
  const result = await createUserWithEmailAndPassword(auth, email, password);
  return result.user;
};

export const emailSignIn = async (email, password) => {
  if (isFirebaseMock) {
    if (password.length < 6) {
      throw new Error('Password must be at least 6 characters');
    }
    const mockUser = {
      uid: `mock-email-uid-${email.split('@')[0]}`,
      email,
      displayName: email.split('@')[0].toUpperCase(),
      photoURL: `https://api.dicebear.com/7.x/bottts/svg?seed=${email}`,
      providerData: [{ providerId: 'password' }],
      getIdToken: async () => `mock-user-token-${email.split('@')[0]}`
    };
    mockState.currentUser = mockUser;
    triggerListeners();
    return mockUser;
  }
  const result = await signInWithEmailAndPassword(auth, email, password);
  return result.user;
};

export const updateDisplayName = async (name) => {
  if (isFirebaseMock) {
    if (mockState.currentUser) {
      mockState.currentUser.displayName = name;
      triggerListeners();
    }
    return mockState.currentUser;
  }
  if (auth.currentUser) {
    await updateProfile(auth.currentUser, { displayName: name });
    return auth.currentUser;
  }
  throw new Error("No authenticated user session.");
};

export const signOutUser = async () => {
  if (isFirebaseMock) {
    mockState.currentUser = null;
    triggerListeners();
    return;
  }
  await signOut(auth);
};

export const onAuthStateChange = (callback) => {
  if (isFirebaseMock) {
    mockState.listeners.push(callback);
    // Initial emit
    callback(mockState.currentUser);
    return () => {
      mockState.listeners = mockState.listeners.filter(cb => cb !== callback);
    };
  }
  return onAuthStateChanged(auth, callback);
};
