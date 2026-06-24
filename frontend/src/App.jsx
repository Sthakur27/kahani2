import { Routes, Route, Link } from "react-router-dom";
import StoriesList from "./pages/StoriesList.jsx";
import StoryView from "./pages/StoryView.jsx";
import CampaignPlay from "./pages/CampaignPlay.jsx";
import Trending from "./pages/Trending.jsx";
import Profile from "./pages/Profile.jsx";
import Login from "./pages/Login.jsx";
import { useAuth } from "./auth.jsx";

function HeaderAuth() {
  const { user, logout } = useAuth();
  if (user) {
    return (
      <span className="header-auth">
        Hi, <Link to="/me" className="link-like">{user.username}</Link>
        <span className="sep"> · </span>
        <button type="button" className="link-btn" onClick={logout}>
          Log out
        </button>
      </span>
    );
  }
  return (
    <Link to="/login" className="header-auth link-like">
      Log in
    </Link>
  );
}

export default function App() {
  return (
    <div className="app">
      <header className="site-header">
        <Link to="/" className="brand">
          StorySim
        </Link>
        <span className="tagline">a new story every day — branch it</span>
        <div className="header-spacer" />
        <Link to="/trending" className="header-auth link-like">
          🔥 Trending
        </Link>
        <span className="sep"> · </span>
        <HeaderAuth />
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<StoriesList />} />
          <Route path="/trending" element={<Trending />} />
          <Route path="/me" element={<Profile />} />
          <Route path="/login" element={<Login />} />
          <Route path="/stories/:id" element={<StoryView />} />
          <Route path="/stories/:id/play" element={<CampaignPlay />} />
          <Route path="/stories/:id/nodes/:nodeId" element={<StoryView />} />
        </Routes>
      </main>
    </div>
  );
}
