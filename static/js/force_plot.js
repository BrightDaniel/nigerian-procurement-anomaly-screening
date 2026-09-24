/* ═══════════════════════════════════════════════════════════
   FORCE_PLOT.JS — Simplified feature contribution visualization
   NOT a technically accurate SHAP force plot.
   Authoritative values are in the contribution table above.
   ═══════════════════════════════════════════════════════════ */

function renderForcePlot(container, data) {
  'use strict';

  container.innerHTML = '';
  container.style.padding = 'var(--space-4) 0';

  var features = data.features || [];
  var values = data.values || [];
  var directions = data.directions || [];
  var levels = data.levels || [];

  if (features.length === 0) return;

  // Sort by absolute value descending
  var items = features.map(function(f, i) {
    return { name: f, value: values[i], dir: directions[i], level: levels[i] };
  });
  items.sort(function(a, b) { return Math.abs(b.value) - Math.abs(a.value); });

  var row = document.createElement('div');
  row.style.display = 'flex';
  row.style.alignItems = 'center';
  row.style.gap = 'var(--space-2)';
  row.style.padding = 'var(--space-2) var(--space-3)';
  row.style.background = 'var(--color-neutral-50)';
  row.style.borderRadius = 'var(--radius-lg)';
  row.style.overflowX = 'auto';
  row.style.flexWrap = 'nowrap';

  items.forEach(function(item, idx) {
    var isPos = item.dir === 1 || item.value > 0;
    var color = isPos ? 'var(--color-priority-high)' : 'var(--color-info)';
    var bgColor = isPos ? 'var(--color-priority-high-bg)' : 'var(--color-info-bg)';
    var arrow = isPos ? '+' : '';

    var el = document.createElement('div');
    el.style.display = 'inline-flex';
    el.style.flexDirection = 'column';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'center';
    el.style.minWidth = '70px';
    el.style.padding = 'var(--space-2) var(--space-3)';
    el.style.borderRadius = 'var(--radius-md)';
    el.style.background = bgColor;
    el.style.border = '1px solid ' + color;
    el.style.textAlign = 'center';
    el.style.flexShrink = '0';

    var valEl = document.createElement('div');
    valEl.style.fontSize = 'var(--text-small)';
    valEl.style.fontWeight = 'var(--weight-semibold)';
    valEl.style.fontFamily = 'var(--font-mono)';
    valEl.style.color = color;
    valEl.textContent = arrow + (typeof item.value === 'number' ? item.value.toFixed(2) : item.value);

    var nameEl = document.createElement('div');
    nameEl.style.fontSize = 'var(--text-caption)';
    nameEl.style.color = 'var(--color-text-secondary)';
    nameEl.style.marginTop = '2px';
    nameEl.style.whiteSpace = 'nowrap';
    nameEl.style.overflow = 'hidden';
    nameEl.style.textOverflow = 'ellipsis';
    nameEl.style.maxWidth = '90px';
    nameEl.textContent = item.name;

    el.appendChild(valEl);
    el.appendChild(nameEl);
    row.appendChild(el);

    if (idx < items.length - 1) {
      var arrowSep = document.createElement('div');
      arrowSep.style.fontSize = 'var(--text-body)';
      arrowSep.style.color = 'var(--color-text-muted)';
      arrowSep.style.flexShrink = '0';
      row.appendChild(arrowSep);
    }
  });

  container.appendChild(row);
}
