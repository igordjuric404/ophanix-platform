import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./app/App";
import "./styles/globals.css";

const rootElement = document.getElementById("app");

if (!rootElement) {
  throw new Error("App root element was not found.");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

