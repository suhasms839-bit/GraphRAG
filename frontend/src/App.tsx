import React, { useState, useEffect } from "react";
import {
  Send,
  Bot,
  User,
  Loader2,
  LogOut,
  File,
  Plus,
  Trash2,
  GraduationCap,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import DashboardPage from "./pages/DashboardPage";

export default function App() {
  const [currentPage, setCurrentPage] = useState<"login" | "signup" | "dashboard">("login");
  const [token, setToken] = useState<string | null>(localStorage.getItem("authToken"));
  const [user, setUser] = useState<any>(null);
  const [isCheckingSession, setIsCheckingSession] = useState<boolean>(true);

  useEffect(() => {
    const checkSession = async () => {
      if (!token) {
        setCurrentPage("login");
        setIsCheckingSession(false);
        return;
      }

      try {
        const response = await fetch("/api/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          localStorage.removeItem("authToken");
          setToken(null);
          setUser(null);
          setCurrentPage("login");
          setIsCheckingSession(false);
          return;
        }

        const userData = await response.json();
        setUser(userData);
        setCurrentPage("dashboard");
      } catch {
        localStorage.removeItem("authToken");
        setToken(null);
        setUser(null);
        setCurrentPage("login");
      } finally {
        setIsCheckingSession(false);
      }
    };

    checkSession();
  }, [token]);

  const handleLoginSuccess = (token: string, userData: any) => {
    setToken(token);
    setUser(userData);
    localStorage.setItem("authToken", token);
    setCurrentPage("dashboard");
  };

  const handleSignupSuccess = (token: string, userData: any) => {
    setToken(token);
    setUser(userData);
    localStorage.setItem("authToken", token);
    setCurrentPage("dashboard");
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("authToken");
    setCurrentPage("login");
  };

  const toggleAuthPage = (page: "login" | "signup") => {
    setCurrentPage(page);
  };

  if (isCheckingSession) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900 text-slate-200">
        Checking session...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-slate-900 text-slate-50 font-sans">
      <AnimatePresence mode="wait">
        {!token ? (
          <motion.div
            key="auth"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            {currentPage === "login" ? (
              <LoginPage
                onLoginSuccess={handleLoginSuccess}
                onToggleSignup={() => toggleAuthPage("signup")}
              />
            ) : (
              <SignupPage
                onSignupSuccess={handleSignupSuccess}
                onToggleLogin={() => toggleAuthPage("login")}
              />
            )}
          </motion.div>
        ) : (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="flex flex-col h-full"
          >
            <DashboardPage user={user} token={token} onLogout={handleLogout} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
