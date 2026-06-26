/* GARUDA — self-contained canvas force-directed graph (Phase 8).
   No dependencies. Renders the co-offender ego-network: node radius by weighted
   degree (strength), color by Louvain community, kingpin emphasized + amber ring.
   Interactions: hover (highlight neighbours + tooltip), click (select), drag. */
(function () {
  'use strict';
  var COMMUNITY = ['#3b82f6', '#f9a825', '#22c55e', '#a78bfa', '#f472b6',
                   '#38bdf8', '#fb923c', '#4ade80', '#e879f9', '#2dd4bf'];

  function render(canvas, data, opts) {
    opts = opts || {};
    var tip = document.getElementById('tip');
    var dpr = Math.max(1, window.devicePixelRatio || 1);
    var raf = null, W = 0, H = 0;
    var nodes = (data.nodes || []).map(function (n) { return Object.assign({}, n); });
    var idx = {}; nodes.forEach(function (n, i) { idx[n.id] = i; });
    var links = (data.edges || []).filter(function (e) {
      return idx[e.source] != null && idx[e.target] != null;
    }).map(function (e) { return { s: idx[e.source], t: idx[e.target], w: e.weight || 1, kinds: e.kinds || [] }; });

    var maxStr = Math.max(1, Math.max.apply(null, nodes.map(function (n) { return n.strength || 1; })));
    var kingId = opts.kingpin;
    nodes.forEach(function (n) {
      n.r = 7 + 17 * Math.sqrt((n.strength || 1) / maxStr);
      if (n.id === kingId) n.r += 4;
      n.col = (n.community != null) ? COMMUNITY[n.community % COMMUNITY.length] : '#3b82f6';
    });

    function size() {
      var rect = canvas.getBoundingClientRect();
      W = rect.width; H = rect.height;
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    var ctx = canvas.getContext('2d');
    size();
    nodes.forEach(function (n, i) {
      var a = (i / nodes.length) * Math.PI * 2;
      n.x = W / 2 + Math.cos(a) * 90 * Math.random() + (Math.random() - .5) * 40;
      n.y = H / 2 + Math.sin(a) * 90 * Math.random() + (Math.random() - .5) * 40;
      n.vx = n.vy = 0;
    });

    var alpha = 1, hover = null, sel = null, drag = null, adj = {};
    links.forEach(function (l) { (adj[l.s] = adj[l.s] || {})[l.t] = 1; (adj[l.t] = adj[l.t] || {})[l.s] = 1; });

    function tick() {
      alpha *= 0.985; if (alpha < 0.02) alpha = 0.02;
      var cx = W / 2, cy = H / 2;
      for (var i = 0; i < nodes.length; i++) {
        var a = nodes[i];
        for (var j = i + 1; j < nodes.length; j++) {
          var b = nodes[j], dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy || 1;
          var f = (2600 * alpha) / d2, d = Math.sqrt(d2);
          var fx = (dx / d) * f, fy = (dy / d) * f;
          a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
        }
        a.vx += (cx - a.x) * 0.012 * alpha; a.vy += (cy - a.y) * 0.012 * alpha;
      }
      links.forEach(function (l) {
        var a = nodes[l.s], b = nodes[l.t], dx = b.x - a.x, dy = b.y - a.y;
        var d = Math.sqrt(dx * dx + dy * dy) || 1, target = 70 + 90 / (l.w);
        var f = (d - target) * 0.05 * alpha, fx = (dx / d) * f, fy = (dy / d) * f;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      });
      nodes.forEach(function (n) {
        if (n === drag) return;
        n.x += (n.vx *= 0.82); n.y += (n.vy *= 0.82);
        n.x = Math.max(n.r + 6, Math.min(W - n.r - 6, n.x));
        n.y = Math.max(n.r + 6, Math.min(H - n.r - 6, n.y));
      });
    }

    function draw() {
      ctx.clearRect(0, 0, W, H);
      var focus = hover != null ? hover : sel;
      links.forEach(function (l) {
        var a = nodes[l.s], b = nodes[l.t];
        var on = focus != null && (l.s === focus || l.t === focus);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = on ? 'rgba(249,168,37,.55)' : 'rgba(120,150,200,' + (focus != null ? .06 : .16) + ')';
        ctx.lineWidth = on ? Math.min(4, 1 + l.w * .5) : Math.min(3, .6 + l.w * .35);
        ctx.stroke();
      });
      nodes.forEach(function (n, i) {
        var dim = focus != null && i !== focus && !(adj[focus] && adj[focus][i]);
        ctx.globalAlpha = dim ? 0.25 : 1;
        if (n.id === kingId) {
          ctx.beginPath(); ctx.arc(n.x, n.y, n.r + 6, 0, 7); ctx.strokeStyle = '#f9a825';
          ctx.lineWidth = 2; ctx.stroke();
        }
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 7);
        ctx.fillStyle = n.col; ctx.shadowColor = n.col; ctx.shadowBlur = (i === focus) ? 18 : 8;
        ctx.fill(); ctx.shadowBlur = 0;
        ctx.lineWidth = 1.5; ctx.strokeStyle = 'rgba(255,255,255,.25)'; ctx.stroke();
        if (n.type === 'phone' || n.type === 'vehicle') {
          ctx.fillStyle = 'rgba(8,13,24,.9)'; ctx.font = '700 ' + Math.round(n.r * .9) + "px 'Fira Code',monospace";
          ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
          ctx.fillText(n.type === 'phone' ? '☎' : '⌗', n.x, n.y + .5);
        }
        if (n.id === kingId || i === focus || n.r > 16) {
          ctx.globalAlpha = dim ? 0.25 : 1;
          ctx.fillStyle = '#e8eef9'; ctx.font = "600 11px 'Fira Sans',sans-serif";
          ctx.textAlign = 'center'; ctx.textBaseline = 'top';
          ctx.fillText(n.label || n.id, n.x, n.y + n.r + 4);
        }
        ctx.globalAlpha = 1;
      });
    }

    function loop() { tick(); draw(); raf = requestAnimationFrame(loop); }
    loop();

    function at(ev) {
      var rect = canvas.getBoundingClientRect(), mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i]; if ((mx - n.x) * (mx - n.x) + (my - n.y) * (my - n.y) <= (n.r + 3) * (n.r + 3)) return i;
      }
      return null;
    }
    canvas.onmousemove = function (ev) {
      if (drag) { var rect = canvas.getBoundingClientRect(); drag.x = ev.clientX - rect.left; drag.y = ev.clientY - rect.top; alpha = Math.max(alpha, .3); return; }
      var h = at(ev); hover = h; canvas.style.cursor = h != null ? 'pointer' : 'default';
      if (h != null) {
        var n = nodes[h];
        tip.innerHTML = '<b>' + (n.label || n.id) + '</b> · ' + n.type + ' · str ' + (n.strength || 0) +
          ' · ' + (n.incident_count || 0) + ' incidents';
        tip.style.left = (ev.clientX + 14) + 'px'; tip.style.top = (ev.clientY + 14) + 'px'; tip.style.opacity = 1;
      } else tip.style.opacity = 0;
    };
    canvas.onmousedown = function (ev) { var h = at(ev); if (h != null) { drag = nodes[h]; } };
    window.addEventListener('mouseup', function () { drag = null; });
    canvas.onclick = function (ev) {
      var h = at(ev); sel = h;
      if (h != null && opts.onSelect) opts.onSelect(nodes[h]);
    };
    canvas.onmouseleave = function () { hover = null; tip.style.opacity = 0; };
    var ro = new ResizeObserver(function () { size(); alpha = Math.max(alpha, .4); });
    ro.observe(canvas);
    return { stop: function () { cancelAnimationFrame(raf); ro.disconnect(); }, communityColor: function (c) { return COMMUNITY[c % COMMUNITY.length]; } };
  }
  window.GARUDA_GRAPH = { render: render, COMMUNITY: COMMUNITY };
})();
