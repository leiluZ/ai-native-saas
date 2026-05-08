import React from "react";
import ReactDOM from "react-dom/client";
import { ChatContainer } from "./components/ChatContainer";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ChatContainer />
  </React.StrictMode>,
);
