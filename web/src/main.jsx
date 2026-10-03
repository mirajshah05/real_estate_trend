import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./index.css";
import "leaflet/dist/leaflet.css";
import ThemeProvider, { bootstrapAppearance } from "./ThemeProvider.jsx";
import "./themes.css";

const initialAppearance = bootstrapAppearance();

ReactDOM.createRoot(document.getElementById("root")).render(
  <ThemeProvider initialAppearance={initialAppearance}><BrowserRouter>
    <App />
  </BrowserRouter></ThemeProvider>
);
