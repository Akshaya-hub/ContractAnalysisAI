import React from 'react';
import { Link } from 'react-router-dom';
import '../styles/global.css';

export default function HomePage() {
  return (
    <div className="homepage">
      {/* Navbar */}
      <header className="navbar">
        <div className="logo">Contract<span>AI</span></div>
        <nav>
          <ul>
            <li><Link to="/">Home</Link></li>
            <li><Link to="/upload">Upload</Link></li>
            <li><Link to="/dashboard">Dashboard</Link></li>
            <li><Link to="/login">Login</Link></li>
          </ul>
        </nav>
        <Link to="/upload" className="nav-btn">Start Now</Link>
      </header>

      {/* Hero Section */}
      <section className="hero">
        <div className="hero-content">
          <h1>Unlocking the Future of <span>Contract Analysis</span></h1>
          <p>
            Powered by AI, our platform extracts clauses, highlights risks, and delivers 
            quick summaries so you can review contracts faster and smarter.
          </p>
          <div className="hero-buttons">
            <Link to="/upload" className="primary-btn">Upload a Contract</Link>
            <Link to="/learn" className="secondary-btn">Learn More</Link>
          </div>
        </div>

        <div className="hero-graphic">
          <img src="/robot.png" alt="Contract AI" />
        </div>
      </section>

      {/* Stats Section */}
      <section className="stats">
        <div className="stat"><h2>10,000+</h2><p>Contracts Analyzed</p></div>
        <div className="stat"><h2>95%</h2><p>Accuracy in Risk Detection</p></div>
        <div className="stat"><h2>1M+</h2><p>Users Worldwide</p></div>
        <div className="stat"><h2>24/7</h2><p>AI Insights Anytime</p></div>
      </section>
    </div>
  );
}
