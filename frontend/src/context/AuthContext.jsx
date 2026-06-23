import { createContext, useState, useEffect } from 'react';
import {
  googleSignIn,
  emailSignIn,
  emailSignUp,
  signOutUser,
  onAuthStateChange,
  updateDisplayName
} from '../services/auth';

export const AuthContext = createContext({
  user: null,
  loading: true,
  loginWithGoogle: async () => {},
  loginWithEmail: async () => {},
  signUpWithEmail: async () => {},
  editProfile: async () => {},
  logout: async () => {}
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChange(async (currentUser) => {
      try {
        if (currentUser) {
          const token = await currentUser.getIdToken();
          localStorage.setItem('alphamatrix_token', token);
          localStorage.setItem('alphamatrix_user_email', currentUser.email);
          setUser(currentUser);
        } else {
          localStorage.removeItem('alphamatrix_token');
          localStorage.removeItem('alphamatrix_user_email');
          setUser(null);
        }
      } catch (error) {
        console.error('Error handling auth state change token retrieval:', error);
        setUser(null);
      } finally {
        setLoading(false);
      }
    });

    return () => unsubscribe();
  }, []);

  const loginWithGoogle = async () => {
    setLoading(true);
    try {
      const u = await googleSignIn();
      setUser(u);
      return u;
    } finally {
      setLoading(false);
    }
  };

  const loginWithEmail = async (email, password) => {
    setLoading(true);
    try {
      const u = await emailSignIn(email, password);
      setUser(u);
      return u;
    } finally {
      setLoading(false);
    }
  };

  const signUpWithEmail = async (email, password) => {
    setLoading(true);
    try {
      const u = await emailSignUp(email, password);
      setUser(u);
      return u;
    } finally {
      setLoading(false);
    }
  };

  const editProfile = async (name) => {
    const updated = await updateDisplayName(name);
    setUser({ ...updated });
    return updated;
  };

  const logout = async () => {
    setLoading(true);
    try {
      await signOutUser();
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const value = {
    user,
    loading,
    loginWithGoogle,
    loginWithEmail,
    signUpWithEmail,
    editProfile,
    logout
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
