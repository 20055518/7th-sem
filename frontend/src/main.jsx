import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";   

import App from "./App";
import "./styles/global.css";
import "./index.css";


console.log(
  "Google Client ID configured:",
  Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID)
);

createRoot(document.getElementById("root")).render(
  <GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </GoogleOAuthProvider>
);