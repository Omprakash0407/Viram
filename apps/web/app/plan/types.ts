export type PlaceInfo = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  city_id: string;
  classification: "POPULAR" | "LESSER_KNOWN";
  lesser_known_note: string | null;
  rating_avg: number | null;
  popularity_score: number | null;
  typical_visit_minutes: number | null;
};

export type RecommendationUI = {
  id?: string;
  place_id: string;
  rank?: number;
  score?: number | null;
  classification: "POPULAR" | "LESSER_KNOWN";
  explanation: string;
  accepted?: boolean;
};
