import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { applyResolved, browserDisplay, loadPrefs, resolve } from "./display";
import "./styles.css";

// Apply the saved look before the first paint.
applyResolved(resolve(loadPrefs(), browserDisplay()));

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
