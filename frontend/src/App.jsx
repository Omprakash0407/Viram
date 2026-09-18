import { useState } from "react";

const destinations = [
  ["Uttarakhand", "Mountains. Spirituality. Serenity.", "https://images.unsplash.com/photo-1483347756197-71ef80e95f73?auto=format&fit=crop&w=900&q=85"],
  ["Rajasthan", "Royalty. Culture. Timeless Beauty.", "https://images.unsplash.com/photo-1599661046827-dacff0c0f09a?auto=format&fit=crop&w=900&q=85"],
  ["Kerala", "Backwaters. Nature. Pure Bliss.", "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?auto=format&fit=crop&w=900&q=85"],
  ["Himachal Pradesh", "Adventure. Views. Tranquility.", "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=900&q=85"],
  ["Madhya Pradesh", "History. Heritage. Hidden Gems.", "https://images.unsplash.com/photo-1548013146-72479768bada?auto=format&fit=crop&w=900&q=85"],
  ["Goa", "Beaches. Food. Good Vibes.", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=85"],
];

const shortcuts = [
  ["map-pin", "Places"], ["bed", "Stays"], ["user-focus", "Local Guides"],
  ["mask-happy", "Culture"], ["bowl-food", "Food"], ["calendar-check", "Itineraries"],
];

const reasons = [
  ["users-three", "Authentic Local Insights", "Discover hidden gems and cultural stories."],
  ["map-trifold", "Personalized Itineraries", "Trips tailored to your interests."],
  ["shield-check", "Verified Information", "Reliable and curated content."],
  ["leaf", "Support Local Communities", "Travel responsibly, make a positive impact."],
  ["compass", "All in One Platform", "Places, stays, guides, routes and more."],
];

export function App() {
  const [active, setActive] = useState("Home");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const search = () => setMessage(query.trim() ? `Finding thoughtful journeys in ${query.trim()}…` : "Tell us where you would like to explore.");
  const scrollToDestinations = () => document.querySelector("#destinations")?.scrollIntoView({ behavior: "smooth" });

  return <main>
    <nav className="topbar" aria-label="Main navigation">
      <button className="brand" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} aria-label="VIRĀM home">
        <span className="brand-mark"><i className="ph ph-mountains" /></span><span><strong>VIRĀM</strong><small>Bhraman Saathi</small></span>
      </button>
      <div className="nav-links">{["Home", "Destinations", "Plan Trip", "Local Experiences", "Stays", "Guides", "About"].map(item =>
        <button className={active === item ? "active" : ""} onClick={() => { setActive(item); item === "Destinations" ? scrollToDestinations() : setMessage(`${item} is ready to explore.`); }} key={item}>{item}</button>)}</div>
      <div className="account"><button className="icon-button" aria-label="Search" onClick={() => document.querySelector("#travel-search")?.focus()}><i className="ph ph-magnifying-glass" /></button><button className="login" onClick={() => setMessage("Welcome back — login is coming next.")}>Login</button><button className="signup" onClick={() => setMessage("Your VIRĀM account journey starts here.")}>Sign Up</button></div>
    </nav>

    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-shade" />
      <div className="hero-content">
        <p className="eyebrow">VIRĀM — your travel companion</p>
        <h1 id="hero-title">Pause. Explore. Belong.</h1>
        <p className="hero-copy">Discover India’s soul through its places, people and culture.<br />Your intelligent travel companion.</p>
        <div className="searchbar"><i className="ph ph-map-pin" /><input id="travel-search" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && search()} placeholder="Where do you want to explore?" /><button onClick={search}>Search</button></div>
        <div className="shortcut-row">{shortcuts.map(([icon, label]) => <button key={label} onClick={() => setMessage(`${label} recommendations selected.`)}><span><i className={`ph ph-${icon}`} /></span>{label}</button>)}</div>
      </div>
      <div className="hero-script">More<br />Than Travel<br /><em>A Deeper Connection</em></div>
      <p className="location"><i className="ph ph-map-pin" /> Rishikesh, Uttarakhand</p>
    </section>

    <section id="destinations" className="section destinations">
      <header className="section-heading"><h2>Explore by Destination</h2><button onClick={() => setMessage("Showing all destinations soon.")}>View All <i className="ph ph-arrow-right" /></button></header>
      <div className="destination-grid">{destinations.map(([name, caption, image]) => <button className="destination-card" key={name} style={{ backgroundImage: `url(${image})` }} onClick={() => { setQuery(name); setMessage(`${name} selected. Search when you are ready.`); }}><span><strong>{name}</strong><small>{caption}</small></span></button>)}</div>
    </section>

    <section className="feature-grid section">
      <article className="culture-panel"><img src="https://images.unsplash.com/photo-1609519904734-5f09f7b5e27f?auto=format&fit=crop&w=1200&q=85" alt="Classical Indian dance performer" /><div><h2>Experience<br />the real India</h2><p>Traditions, festivals, food, crafts and stories from the heart of every destination.</p><button className="light-cta" onClick={() => setMessage("Local culture experiences are being curated.")}>Explore Culture <i className="ph ph-arrow-right" /></button></div></article>
      <article className="plan-panel"><div><h2>Plan Smarter<br />Travel Better</h2><p>Get personalized itineraries, routes, weather updates and local recommendations.</p><button className="dark-cta" onClick={() => { setActive("Plan Trip"); setMessage("Let’s plan a trip around what matters to you."); }}>Plan Your Trip <i className="ph ph-arrow-right" /></button></div><div className="route-art" aria-label="Places, food, stays and guides connected as a route"><span className="route-dot p1"><i className="ph ph-map-pin" />Places</span><span className="route-dot p2"><i className="ph ph-map-pin" />Stays</span><span className="route-dot p3"><i className="ph ph-map-pin" />Guides</span><span className="route-dot p4"><i className="ph ph-map-pin" />Food</span></div></article>
    </section>

    <section className="section why"><h2>Why Travel with VIRĀM?</h2><div className="reasons">{reasons.map(([icon, title, copy]) => <article key={title}><i className={`ph ph-${icon}`} /><h3>{title}</h3><p>{copy}</p></article>)}</div></section>
    <footer><div className="brand footer-brand"><span className="brand-mark"><i className="ph ph-mountains" /></span><span><strong>VIRĀM</strong><small>Bhraman Saathi</small></span></div><p>“Not just places, but the stories that stay with you.”</p><div className="socials"><i className="ph ph-instagram-logo" /><i className="ph ph-youtube-logo" /><i className="ph ph-x-logo" /><i className="ph ph-linkedin-logo" /></div></footer>
    {message && <div className="toast" role="status"><span>{message}</span><button onClick={() => setMessage("")} aria-label="Close message">×</button></div>}
  </main>;
}
