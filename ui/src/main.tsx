import React from "react";
import ReactDOM from "react-dom/client";
import { applySavedDisplay } from "pnd-lib-react";
import "pnd-lib-react/styles.css";
import App from "./App";
import { displayHost } from "./displayHost";
import "./styles.css";

// Apply the saved look before the first paint.
applySavedDisplay(displayHost);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
