import { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext(null);
const THEME_KEY = "ai_data_analyst_theme";

function preferredTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {}
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(preferredTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {}
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme: () => setTheme((value) => value === "light" ? "dark" : "light") }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider");
  return context;
}