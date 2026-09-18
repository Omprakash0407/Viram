export interface Destination {
  name: string;
  tagline: string;
  image: string;
}

export const destinations: Destination[] = [
  {
    name: "Uttarakhand",
    tagline: "Mountains. Spirituality. Serenity.",
    image: "/images/uttarakhand.svg",
  },
  {
    name: "Rajasthan",
    tagline: "Royalty. Culture. Timeless Beauty.",
    image: "/images/rajasthan.svg",
  },
  {
    name: "Kerala",
    tagline: "Backwaters. Nature. Pure Bliss.",
    image: "/images/kerala.svg",
  },
  {
    name: "Himachal Pradesh",
    tagline: "Adventure. Views. Tranquility.",
    image: "/images/himachal.svg",
  },
  {
    name: "Madhya Pradesh",
    tagline: "History. Heritage. Hidden Gems.",
    image: "/images/madhya-pradesh.svg",
  },
  {
    name: "Goa",
    tagline: "Beaches. Food. Good Vibes.",
    image: "/images/goa.svg",
  },
];

export interface Feature {
  icon: "users" | "map" | "shield" | "leaf" | "zap";
  title: string;
  description: string;
}

export const features: Feature[] = [
  {
    icon: "users",
    title: "Authentic Local Insights",
    description: "Discover hidden gems and cultural stories.",
  },
  {
    icon: "map",
    title: "Personalized Itineraries",
    description: "Trips tailored to your interests.",
  },
  {
    icon: "shield",
    title: "Verified Information",
    description: "Reliable and curated content.",
  },
  {
    icon: "leaf",
    title: "Support Local Communities",
    description: "Travel responsibly, make a positive impact.",
  },
  {
    icon: "zap",
    title: "All in One Platform",
    description: "Places, food, culture, and more.",
  },
];
