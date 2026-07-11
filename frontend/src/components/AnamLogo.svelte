<script>
  // SVG recreation of The Anam sunburst emblem: a wide fan of rays bursting
  // from a focal point, with a small shell fan beneath it. Gold on whatever
  // it sits on — pass `color` to tint.
  export let size = 40;
  export let color = '#c99a3c';
  export let opacity = 1;

  const FX = 32;
  const FY = 50;
  // upper burst: 13 rays sweeping edge to edge, slightly elliptical
  const upper = Array.from({ length: 13 }, (_, i) => {
    const a = (Math.PI * i) / 12; // 0..180°
    return {
      x: FX - 29 * Math.cos(a),
      y: FY - 42 * Math.sin(a) * (0.55 + 0.45 * Math.sin(a)),
      w: i === 0 || i === 12 ? 1.4 : 1.9
    };
  });
  // lower shell: shorter, denser fan below the focal point
  const lower = Array.from({ length: 9 }, (_, i) => {
    const a = (Math.PI * (i + 1)) / 10; // avoid pure horizontals
    return { x: FX - 15 * Math.cos(a), y: FY + 4 + 15 * Math.sin(a) };
  });
</script>

<svg
  width={size}
  height={size * 1.3}
  viewBox="0 0 64 84"
  fill="none"
  aria-hidden="true"
  style="opacity:{opacity}"
>
  {#each upper as r}
    <line x1={FX} y1={FY} x2={r.x} y2={r.y} stroke={color} stroke-width={r.w} />
  {/each}
  {#each lower as r}
    <line x1={FX} y1={FY + 6} x2={r.x} y2={r.y} stroke={color} stroke-width="1.5" />
  {/each}
</svg>
