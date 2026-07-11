<script>
  export let data = [];
  export let width = 120;
  export let height = 30;
  export let color = 'var(--accent)';

  $: min = Math.min(...data);
  $: max = Math.max(...data);
  $: span = max - min || 1;
  $: pts = data
    .map((v, i) => {
      const x = (i / Math.max(1, data.length - 1)) * (width - 4) + 2;
      const y = height - 3 - ((v - min) / span) * (height - 8);
      return [x, y];
    });
  $: line = pts.map((p) => p.join(',')).join(' ');
  $: last = pts[pts.length - 1];
</script>

<svg {width} {height} viewBox="0 0 {width} {height}" aria-hidden="true">
  <polyline
    points={line}
    fill="none"
    stroke={color}
    stroke-width="1.5"
    stroke-linejoin="round"
    stroke-linecap="round"
  />
  {#if last}
    <circle cx={last[0]} cy={last[1]} r="2.5" fill={color} />
  {/if}
</svg>
