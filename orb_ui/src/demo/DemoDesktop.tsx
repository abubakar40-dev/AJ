/**
 * Stand-in for the user's desktop wallpaper (browser demo only).
 * Mirrors the purple → blue swoosh background of reference image 2 so the
 * orb and radial menu can be judged against the same backdrop.
 */
export function DemoDesktop() {
  return (
    <div className="fixed inset-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 70% at 60% -10%, #7a4fe0 0%, rgba(122,79,224,0) 60%), linear-gradient(180deg, #5a35d4 0%, #3d3fd6 30%, #1650d0 62%, #0a3fb8 100%)",
        }}
      />
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1600 1000" preserveAspectRatio="none">
        <defs>
          <filter id="blur-a" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="22" />
          </filter>
          <filter id="blur-b">
            <feGaussianBlur stdDeviation="2.2" />
          </filter>
        </defs>
        <path d="M-100 430 C 300 380, 650 470, 1000 410 S 1500 330, 1700 360 L1700 520 C 1300 470, 900 560, 500 520 S -50 560 -100 560Z" fill="#8ea2ff" opacity=".42" filter="url(#blur-a)" />
        <path d="M-60 640 C 300 740, 700 800, 1100 880 S 1500 870, 1700 800" fill="none" stroke="#e6ecff" strokeWidth="7" strokeLinecap="round" opacity=".85" filter="url(#blur-b)" />
        <path d="M900 880 C 1200 905, 1450 870, 1700 790" fill="none" stroke="#b9c8ff" strokeWidth="9" strokeLinecap="round" opacity=".5" filter="url(#blur-b)" />
        <path d="M-100 380 C 200 350, 420 420, 640 400" fill="none" stroke="#c9d2ff" strokeWidth="10" strokeLinecap="round" opacity=".45" filter="url(#blur-b)" />
      </svg>
    </div>
  );
}
