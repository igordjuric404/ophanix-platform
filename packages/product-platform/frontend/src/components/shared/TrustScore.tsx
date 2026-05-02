export function TrustScore({ score }: { score: number }) {
  return (
    <span className="font-semibold tabular-nums text-foreground" aria-label={`Trust score ${score}`}>
      {Math.round(score)}
    </span>
  );
}

