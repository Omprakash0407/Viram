import Header from "./components/Header";
import Hero from "./components/Hero";
import Destinations from "./components/Destinations";
import Banners from "./components/Banners";
import WhyViram from "./components/WhyViram";
import Footer from "./components/Footer";
import { ChatBubble } from "./components/Hero";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <Hero image="/images/hero.svg" />
        <Destinations />
        <Banners />
        <WhyViram />
      </main>
      <Footer />
      <ChatBubble />
    </div>
  );
}
