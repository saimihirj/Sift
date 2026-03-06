type SignalLockupProps = {
  compact?: boolean;
  showTagline?: boolean;
  className?: string;
};

export function SignalMark({ compact = false }: { compact?: boolean }) {
  return (
    <span className={compact ? "signal-mark signal-mark-compact" : "signal-mark"} aria-hidden="true">
      <svg viewBox="0 0 160 136" role="img" focusable="false">
        <path
          className="signal-mark-pulse"
          d="M8 86 H30 L38 64 L46 108 L56 42 L66 94 L76 78 H92"
        />
        <text x="64" y="98" className="signal-mark-letter">S</text>
        <path
          className="signal-mark-arrow"
          d="M86 26 C110 10 132 14 146 30"
        />
        <path
          className="signal-mark-arrow-head"
          d="M132 12 L150 14 L142 32"
        />
      </svg>
    </span>
  );
}

export function SignalLockup({ compact = false, showTagline = true, className = "" }: SignalLockupProps) {
  const classes = ["signal-lockup", compact ? "compact" : "", className].filter(Boolean).join(" ");
  return (
    <div className={classes}>
      <SignalMark compact={compact} />
      <div className="signal-word-stack">
        <strong className="signal-wordmark">Signal</strong>
        {showTagline ? <span className="signal-tagline">Cut Through The Noise.</span> : null}
      </div>
    </div>
  );
}
