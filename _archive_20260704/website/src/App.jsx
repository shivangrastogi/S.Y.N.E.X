import Nav from './components/Nav.jsx';
import Hero from './components/Hero.jsx';
import Marquee from './components/Marquee.jsx';
import Features from './components/Features.jsx';
import HowItWorks from './components/HowItWorks.jsx';
import Showcase from './components/Showcase.jsx';
import Aeris from './components/Aeris.jsx';
import CTA from './components/CTA.jsx';
import Footer from './components/Footer.jsx';

export default function App() {
  return (
    <>
      <div className="bg-aurora" />
      <div className="grain" />
      <Nav />
      <main>
        <Hero />
        <Marquee />
        <Features />
        <HowItWorks />
        <Showcase />
        <Aeris />
        <CTA />
      </main>
      <Footer />
    </>
  );
}
