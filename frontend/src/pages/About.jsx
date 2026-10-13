import { useNavigate } from "react-router-dom";

import AppNav from "../components/AppNav";
import "./About.css";


export default function About() {
  const navigate = useNavigate();

  return (
    <main className="about-page">

      <AppNav />

      <section className="about-card">

        <p className="eyebrow">
          CARE+
        </p>

        <h1>
          About the System
        </h1>

        <p className="about-description">
          Smart hospital queue management with
          QR access, machine-learning waiting-time
          prediction and Bayesian probability analysis.
        </p>

        <button
          type="button"
          className="button secondary"
          onClick={() => navigate("/")}
        >
          Return Home
        </button>

      </section>

    </main>
  );
}