import "./Footer.css";

export default function Footer() {
  return (
    <footer className="careplus-footer">
      <div className="careplus-footer-container">

        {/* Brand */}
        <div className="careplus-footer-brand">
          <h2>Care<span>+</span></h2>
          <p className="careplus-footer-title">
            Smart Hospital Queue Management
          </p>
          <p className="careplus-footer-description">
            Smart and seamless patient queue management
            for a better hospital experience.
          </p>
        </div>

        {/* Quick Links */}
        <div className="careplus-footer-column">
          <h3>Quick Links</h3>

          <a href="/">Home</a>
          <a href="/about">About</a>
          <a href="/login">Login</a>
          <a href="/signup">Register</a>
        </div>

        {/* Patient */}
        <div className="careplus-footer-column">
          <h3>Patient</h3>

          <a href="/join-queue">Join Queue</a>
          <a href="/patient-dashboard">Patient Dashboard</a>
        </div>

        {/* Social Media */}
        <div className="careplus-footer-column">
          <h3>Follow Us</h3>

          <a
            href="INSTAGRAM_LINK"
            target="_blank"
            rel="noopener noreferrer"
          >
            Instagram
          </a>

          <a
            href="FACEBOOK_LINK"
            target="_blank"
            rel="noopener noreferrer"
          >
            Facebook
          </a>
        </div>

      </div>

      <div className="careplus-footer-bottom">
        <p>© 2026 Care+ Hospital. All rights reserved.</p>
      </div>
    </footer>
  );
}